"""
Production-grade Dependency Injection Container for NLP Service

Features:
- Automatic dependency resolution and injection
- Singleton management with lifecycle control
- Factory functions with auto-wiring
- Easy testing with mock swapping
- Type-safe access patterns
- Support for async initialization

Pattern: Service Locator + Factory + Container
Best for: Decoupling components, testing, configuration management
"""

import logging
import inspect
import functools
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import asyncio

logger = logging.getLogger(__name__)

T = TypeVar('T')


class LifecycleScope(Enum):
    """Lifecycle management for service instances"""
    TRANSIENT = "transient"  # New instance each time
    SINGLETON = "singleton"   # Single instance forever
    SCOPED = "scoped"        # Single per request/scope


@dataclass
class ServiceDefinition:
    """Definition of a service in the container"""
    name: str
    factory: Callable
    lifecycle: LifecycleScope = LifecycleScope.SINGLETON
    instance: Optional[Any] = None
    dependencies: list = field(default_factory=list)
    is_async: bool = False
    initialized: bool = False


class DIContainer:
    """
    Dependency Injection Container with lifecycle management.
    
    Example:
        container = DIContainer()
        container.register('cache', lambda: InMemoryCache())
        container.register(
            'intent_recognizer',
            lambda cache: IntentRecognizer(cache=cache)
        )
        recognizer = container.get('intent_recognizer')
    """
    
    def __init__(self):
        """Initialize empty container"""
        self._services: Dict[str, ServiceDefinition] = {}
        self._scope_stack: list = []
        self._initializing: set = set()  # Prevent circular deps
    
    def register(
        self,
        service_name: str,
        factory: Callable,
        lifecycle: LifecycleScope = LifecycleScope.SINGLETON,
        overwrite: bool = False
    ) -> None:
        """
        Register a service factory in the container.
        
        Args:
            service_name: Name for service lookup
            factory: Callable that creates the service
            lifecycle: SINGLETON, TRANSIENT, or SCOPED
            overwrite: Allow overwriting existing registration
        
        Example:
            container.register(
                'sentiment_analyzer',
                lambda: SentimentAnalyzer(),
                lifecycle=LifecycleScope.SINGLETON
            )
        """
        if service_name in self._services and not overwrite:
            raise ValueError(
                f"Service '{service_name}' already registered. "
                "Use overwrite=True to replace."
            )
        
        # Extract dependencies from factory signature
        sig = inspect.signature(factory)
        dependencies = list(sig.parameters.keys())
        
        # Check if factory is async
        is_async = inspect.iscoroutinefunction(factory)
        
        definition = ServiceDefinition(
            name=service_name,
            factory=factory,
            lifecycle=lifecycle,
            dependencies=dependencies,
            is_async=is_async
        )
        
        self._services[service_name] = definition
        logger.debug(f"Registered service: {service_name} ({lifecycle.value})")
    
    def register_instance(
        self,
        service_name: str,
        instance: Any,
        overwrite: bool = False
    ) -> None:
        """
        Register a pre-created instance (useful for testing).
        
        Args:
            service_name: Name for service lookup
            instance: Pre-created instance
            overwrite: Allow overwriting existing registration
        
        Example:
            container.register_instance('cache', MockCache())
        """
        if service_name in self._services and not overwrite:
            raise ValueError(
                f"Service '{service_name}' already registered. "
                "Use overwrite=True to replace."
            )
        
        definition = ServiceDefinition(
            name=service_name,
            factory=lambda: instance,
            lifecycle=LifecycleScope.SINGLETON,
            instance=instance,
            initialized=True
        )
        
        self._services[service_name] = definition
        logger.debug(f"Registered instance: {service_name}")
    
    def get(self, service_name: str) -> Any:
        """
        Get service instance (synchronous).
        
        Args:
            service_name: Name of service to retrieve
        
        Returns:
            Service instance
        
        Raises:
            ValueError: If service not registered
            RuntimeError: If circular dependency detected
        
        Example:
            recognizer = container.get('intent_recognizer')
        """
        if service_name not in self._services:
            raise ValueError(f"Service '{service_name}' not registered")
        
        # Detect circular dependencies
        if service_name in self._initializing:
            raise RuntimeError(
                f"Circular dependency detected for service '{service_name}'"
            )
        
        definition = self._services[service_name]
        
        # Return singleton instance if already created
        if definition.lifecycle == LifecycleScope.SINGLETON:
            if definition.initialized:
                return definition.instance
        
        # Mark as initializing
        self._initializing.add(service_name)
        
        try:
            # Resolve dependencies
            kwargs = self._resolve_dependencies(definition.dependencies)
            
            # Create instance
            if definition.is_async:
                # Can't call async factory from sync context
                raise RuntimeError(
                    f"Service '{service_name}' is async. "
                    "Use 'await get_async()' instead."
                )
            
            instance = definition.factory(**kwargs)
            
            # Cache singleton
            if definition.lifecycle == LifecycleScope.SINGLETON:
                definition.instance = instance
                definition.initialized = True
            
            return instance
        
        finally:
            self._initializing.discard(service_name)
    
    async def get_async(self, service_name: str) -> Any:
        """
        Get service instance (async, supports async initialization).
        
        Args:
            service_name: Name of service to retrieve
        
        Returns:
            Service instance
        
        Example:
            recognizer = await container.get_async('intent_recognizer')
        """
        if service_name not in self._services:
            raise ValueError(f"Service '{service_name}' not registered")
        
        # Detect circular dependencies
        if service_name in self._initializing:
            raise RuntimeError(
                f"Circular dependency detected for service '{service_name}'"
            )
        
        definition = self._services[service_name]
        
        # Return singleton instance if already created
        if definition.lifecycle == LifecycleScope.SINGLETON:
            if definition.initialized:
                return definition.instance
        
        # Mark as initializing
        self._initializing.add(service_name)
        
        try:
            # Resolve dependencies (async)
            kwargs = await self._resolve_dependencies_async(
                definition.dependencies
            )
            
            # Create instance
            if definition.is_async:
                instance = await definition.factory(**kwargs)
            else:
                # Sync factory in async context
                instance = await asyncio.to_thread(
                    definition.factory, **kwargs
                )
            
            # Cache singleton
            if definition.lifecycle == LifecycleScope.SINGLETON:
                definition.instance = instance
                definition.initialized = True
            
            return instance
        
        finally:
            self._initializing.discard(service_name)
    
    def _resolve_dependencies(self, dep_names: list) -> Dict[str, Any]:
        """Resolve all dependencies synchronously"""
        kwargs = {}
        for dep_name in dep_names:
            if dep_name in self._services:
                kwargs[dep_name] = self.get(dep_name)
        return kwargs
    
    async def _resolve_dependencies_async(self, dep_names: list) -> Dict[str, Any]:
        """Resolve all dependencies asynchronously"""
        kwargs = {}
        for dep_name in dep_names:
            if dep_name in self._services:
                kwargs[dep_name] = await self.get_async(dep_name)
        return kwargs
    
    def is_registered(self, service_name: str) -> bool:
        """Check if service is registered"""
        return service_name in self._services
    
    def list_services(self) -> Dict[str, str]:
        """List all registered services with their lifecycle"""
        return {
            name: def_.lifecycle.value
            for name, def_ in self._services.items()
        }
    
    def reset(self) -> None:
        """Clear all singletons (useful for testing)"""
        for definition in self._services.values():
            if definition.lifecycle == LifecycleScope.SINGLETON:
                definition.instance = None
                definition.initialized = False
        logger.debug("Container reset - all singletons cleared")
    
    def reset_service(self, service_name: str) -> None:
        """Clear specific service singleton"""
        if service_name not in self._services:
            raise ValueError(f"Service '{service_name}' not registered")
        
        definition = self._services[service_name]
        definition.instance = None
        definition.initialized = False
        logger.debug(f"Service '{service_name}' singleton cleared")
    
    async def initialize_async(self) -> None:
        """Pre-initialize all async singletons"""
        for service_name, definition in self._services.items():
            if (definition.lifecycle == LifecycleScope.SINGLETON and
                definition.is_async):
                await self.get_async(service_name)
                logger.info(f"Pre-initialized async service: {service_name}")


# Global container instance
_global_container: Optional[DIContainer] = None


def initialize_global_container() -> DIContainer:
    """Create and return global container instance"""
    global _global_container
    if _global_container is None:
        _global_container = DIContainer()
    return _global_container


def get_container() -> DIContainer:
    """Get global container instance"""
    global _global_container
    if _global_container is None:
        raise RuntimeError("Container not initialized. Call initialize_global_container()")
    return _global_container


def reset_global_container() -> None:
    """Reset global container (testing only)"""
    global _global_container
    if _global_container:
        _global_container.reset()


# Decorator for dependency injection in FastAPI
def inject_dependencies(func: Callable) -> Callable:
    """
    Decorator to inject dependencies into FastAPI route handlers.
    
    Example:
        @app.post("/process")
        @inject_dependencies
        async def process(request: NLPProcessRequest, nlp_service: NLPService):
            return await nlp_service.process(request)
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Get container
        container = get_container()
        
        # Get function signature
        sig = inspect.signature(func)
        
        # Inject missing dependencies
        for param_name, param in sig.parameters.items():
            if param_name not in kwargs and container.is_registered(param_name):
                if param.annotation != inspect.Parameter.empty:
                    # Get from container
                    kwargs[param_name] = await container.get_async(param_name)
        
        # Call original function
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    
    return wrapper


# Type-safe container wrapper
class TypedContainer(Generic[T]):
    """Type-safe wrapper for better IDE support"""
    
    def __init__(self, container: DIContainer):
        self._container = container
    
    def get(self, service_name: str, expected_type: Type[T]) -> T:
        """Get service with type checking"""
        service = self._container.get(service_name)
        if not isinstance(service, expected_type):
            raise TypeError(
                f"Service '{service_name}' is {type(service)}, "
                f"expected {expected_type}"
            )
        return service
    
    async def get_async(self, service_name: str, expected_type: Type[T]) -> T:
        """Get async service with type checking"""
        service = await self._container.get_async(service_name)
        if not isinstance(service, expected_type):
            raise TypeError(
                f"Service '{service_name}' is {type(service)}, "
                f"expected {expected_type}"
            )
        return service


# Export common patterns
__all__ = [
    'DIContainer',
    'LifecycleScope',
    'ServiceDefinition',
    'initialize_global_container',
    'get_container',
    'reset_global_container',
    'inject_dependencies',
    'TypedContainer',
]
