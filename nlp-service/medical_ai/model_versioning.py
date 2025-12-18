"""
Model Versioning System for NLP Service
Manages different versions of NLP models and enables A/B testing
"""
import logging
from typing import Dict, Any, Optional
from config import MODEL_VERSIONS, DEFAULT_MODEL_VERSION
from error_handling import ModelLoadError, ProcessingError  # PHASE 2: Import exception hierarchy

logger = logging.getLogger(__name__)


class ModelVersionManager:
    """
    Manages model versions for NLP components.
    Supports A/B testing and version switching.
    """

    def __init__(self):
        """Initialize model version manager"""
        self.model_versions = MODEL_VERSIONS.copy()
        self.active_models: Dict[str, Any] = {}
        self.version_history: Dict[str, list] = {}
        
        # Initialize version history
        for model_name in self.model_versions:
            self.version_history[model_name] = [self.model_versions[model_name]]
        
        logger.info("ModelVersionManager initialized with versions: %s", self.model_versions)

    def get_model_version(self, model_name: str) -> str:
        """
        Get the current version of a model.

        Args:
            model_name: Name of the model

        Returns:
            Current version string
        """
        return self.model_versions.get(model_name, DEFAULT_MODEL_VERSION)

    def set_model_version(self, model_name: str, version: str) -> bool:
        """
        Set the version of a model.

        Args:
            model_name: Name of the model
            version: Version to set

        Returns:
            True if successful, False otherwise
        """
        try:
            old_version = self.model_versions.get(model_name, DEFAULT_MODEL_VERSION)
            
            # Update version
            self.model_versions[model_name] = version
            
            # Add to version history
            if model_name in self.version_history:
                self.version_history[model_name].append(version)
            else:
                self.version_history[model_name] = [old_version, version]
            
            logger.info(f"Model version updated: {model_name} from {old_version} to {version}")
            return True
        except Exception as e:
            logger.error(f"Failed to set model version: {e}")
            return False

    def get_all_versions(self) -> Dict[str, str]:
        """
        Get versions of all models.

        Returns:
            Dictionary with model names and their versions
        """
        return self.model_versions.copy()

    def get_version_history(self, model_name: str) -> list:
        """
        Get version history for a model.

        Args:
            model_name: Name of the model

        Returns:
            List of versions in chronological order
        """
        return self.version_history.get(model_name, []).copy()

    def validate_version(self, model_name: str, version: str) -> bool:
        """
        Validate if a version is available for a model.

        Args:
            model_name: Name of the model
            version: Version to validate

        Returns:
            True if version is valid, False otherwise
        """
        # In a real implementation, this would check if the model version exists
        # For now, we'll just check if it's not empty
        return bool(version and version.strip())

    def rollback_version(self, model_name: str) -> bool:
        """
        Rollback to the previous version of a model.

        Args:
            model_name: Name of the model

        Returns:
            True if successful, False otherwise
        """
        try:
            if model_name not in self.version_history:
                logger.warning(f"No version history for model: {model_name}")
                return False
            
            history = self.version_history[model_name]
            if len(history) < 2:
                logger.warning(f"Not enough version history to rollback: {model_name}")
                return False
            
            # Get previous version (second to last)
            previous_version = history[-2]
            
            # Update current version
            self.model_versions[model_name] = previous_version
            
            # Remove the last entry from history
            self.version_history[model_name] = history[:-1]
            
            logger.info(f"Model version rolled back: {model_name} to {previous_version}")
            return True
        except Exception as e:
            logger.error(f"Failed to rollback model version: {e}")
            return False

    def register_model(self, model_name: str, model_instance: Any, version: str = None) -> bool:
        """
        Register an active model instance.

        Args:
            model_name: Name of the model
            model_instance: Model instance
            version: Version of the model (defaults to current version)

        Returns:
            True if successful, False otherwise
        """
        try:
            version = version or self.get_model_version(model_name)
            key = f"{model_name}:{version}"
            self.active_models[key] = model_instance
            logger.info(f"Model registered: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to register model: {e}")
            return False

    def get_model(self, model_name: str, version: str = None) -> Optional[Any]:
        """
        Get a registered model instance.

        Args:
            model_name: Name of the model
            version: Version of the model (defaults to current version)

        Returns:
            Model instance or None if not found
        """
        try:
            version = version or self.get_model_version(model_name)
            key = f"{model_name}:{version}"
            return self.active_models.get(key)
        except Exception as e:
            logger.error(f"Failed to get model: {e}")
            return None

    def list_available_models(self) -> Dict[str, list]:
        """
        List all available models and their versions.

        Returns:
            Dictionary with model names and their available versions
        """
        # In a real implementation, this would query a model registry
        # For now, we'll return the version history
        return {name: history.copy() for name, history in self.version_history.items()}

    def enable_ab_test(self, model_name: str, version_a: str, version_b: str, split_ratio: float = 0.5) -> bool:
        """
        Enable A/B testing between two versions of a model.

        Args:
            model_name: Name of the model
            version_a: First version (control)
            version_b: Second version (test)
            split_ratio: Ratio of traffic to version B (0.0 to 1.0)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate versions
            if not self.validate_version(model_name, version_a):
                logger.error(f"Invalid version A: {version_a}")
                return False
                
            if not self.validate_version(model_name, version_b):
                logger.error(f"Invalid version B: {version_b}")
                return False
                
            if not 0.0 <= split_ratio <= 1.0:
                logger.error(f"Invalid split ratio: {split_ratio}")
                return False
            
            # In a real implementation, this would set up A/B testing infrastructure
            # For now, we'll just log the configuration
            logger.info(
                f"A/B test enabled for {model_name}: "
                f"{version_a} ({1-split_ratio:.1%}) vs {version_b} ({split_ratio:.1%})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to enable A/B test: {e}")
            return False


# Global model version manager instance
model_version_manager = ModelVersionManager()