"""
Error handling module for NLP Service

PHASE 2 TASK 2.1: Enhanced exception hierarchy with proper HTTP status codes
- Custom exception classes with proper categorization
- Automatic status code mapping
- Better error differentiation for debugging
- Transient vs permanent failure classification
"""
import logging
import traceback
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    """Structured error response model"""
    error_code: str
    error_message: str
    error_details: Optional[Dict[str, Any]] = None
    timestamp: str


# PHASE 2 TASK 2.1: Custom Exception Hierarchy
class NLPServiceError(Exception):
    """
    Base exception for all NLP service errors.
    
    Attributes:
        http_status: HTTP status code for response
        error_code: Machine-readable error code
        user_message: User-friendly error message
        log_level: Logging level (info, warning, error, critical)
        is_transient: True if error is transient (can retry)
    """
    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    user_message: str = "An error occurred"
    log_level: str = "error"
    is_transient: bool = False
    
    def __init__(self, message: str = None, details: Dict[str, Any] = None):
        self.message = message or self.user_message
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(NLPServiceError):
    """Raised when input validation fails"""
    http_status = status.HTTP_400_BAD_REQUEST
    error_code = "INVALID_INPUT"
    user_message = "Invalid input provided"
    log_level = "warning"
    is_transient = False


class TimeoutError(NLPServiceError):
    """Raised when operation exceeds timeout"""
    http_status = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "SERVICE_TIMEOUT"
    user_message = "Service timeout"
    log_level = "warning"
    is_transient = True  # Can retry


class ExternalServiceError(NLPServiceError):
    """Raised when external service fails (API, DB, etc.)"""
    http_status = status.HTTP_502_BAD_GATEWAY
    error_code = "EXTERNAL_SERVICE_FAILED"
    user_message = "External service failed"
    log_level = "error"
    is_transient = True  # Can retry


class RateLimitError(NLPServiceError):
    """Raised when rate limit is exceeded"""
    http_status = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT_EXCEEDED"
    user_message = "Too many requests"
    log_level = "info"
    is_transient = True  # Can retry


class ModelLoadError(NLPServiceError):
    """Raised when model fails to load"""
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "MODEL_LOADING_FAILED"
    user_message = "Model service unavailable"
    log_level = "error"
    is_transient = True  # Can retry


class AuthenticationError(NLPServiceError):
    """Raised when authentication fails"""
    http_status = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTHENTICATION_FAILED"
    user_message = "Authentication failed"
    log_level = "warning"
    is_transient = False


class NotFoundError(NLPServiceError):
    """Raised when resource not found"""
    http_status = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"
    user_message = "Resource not found"
    log_level = "warning"
    is_transient = False


class CacheError(NLPServiceError):
    """Raised when cache operation fails"""
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "CACHE_ERROR"
    user_message = "Cache operation failed"
    log_level = "error"
    is_transient = True  # Can retry


class ProcessingError(NLPServiceError):
    """Raised when NLP processing fails"""
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "PROCESSING_ERROR"
    user_message = "Processing error"
    log_level = "error"
    is_transient = False


class ExceptionContext:
    """
    Rich context for exceptions to improve debugging and observability.
    
    PHASE 2A ENHANCEMENT: Structured exception context with request correlation,
    field validation details, and root cause information.
    
    Example:
        context = ExceptionContext(
            exception_type="ValidationError",
            message="Invalid health metrics provided",
            context={
                'field': 'blood_pressure',
                'expected': 'int > 0',
                'received': -120,
                'request_id': 'req-12345-abcde'
            }
        )
        raise ValidationError(message, details=context.to_dict())
    """
    
    def __init__(
        self,
        exception_type: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ):
        self.exception_type = exception_type
        self.message = message
        self.context = context or {}
        self.request_id = request_id
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for structured logging"""
        return {
            'error_type': self.exception_type,
            'message': self.message,
            'context': self.context,
            'request_id': self.request_id,
            'timestamp': self.timestamp.isoformat()
        }
    
    def with_field(self, field_name: str, expected, received) -> 'ExceptionContext':
        """Add field validation context"""
        self.context['field'] = field_name
        self.context['expected'] = str(expected)
        self.context['received'] = str(received)
        return self
    
    def with_request_id(self, request_id: str) -> 'ExceptionContext':
        """Add request correlation ID"""
        self.request_id = request_id
        return self
    
    def __str__(self) -> str:
        """String representation for logging"""
        parts = [f"[{self.exception_type}] {self.message}"]
        if self.context:
            context_str = "; ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"({context_str})")
        return " ".join(parts)


class ErrorReporter:
    """Error reporter with support for exception hierarchy
    
    Maps exceptions to proper HTTP status codes and creates structured responses.
    PHASE 2 TASK 2.1 Enhancement: Uses new exception hierarchy for automatic
    status code mapping and transient error detection.
    """
    
    # Legacy error code mappings (backward compatibility)
    ERROR_CODES = {
        "INVALID_INPUT": "Invalid input provided",
        "MODEL_LOADING_FAILED": "Failed to load NLP model",
        "PROCESSING_ERROR": "Error during NLP processing",
        "CACHE_ERROR": "Cache operation failed",
        "AUTHENTICATION_FAILED": "Authentication failed",
        "RATE_LIMIT_EXCEEDED": "Rate limit exceeded",
        "INTERNAL_SERVER_ERROR": "Internal server error",
        "NOT_FOUND": "Resource not found",
        "VALIDATION_ERROR": "Input validation failed"
    }
    
    # Map exception types to custom exceptions
    EXCEPTION_MAP = {
        ValidationError: "INVALID_INPUT",
        TimeoutError: "SERVICE_TIMEOUT",
        ExternalServiceError: "EXTERNAL_SERVICE_FAILED",
        RateLimitError: "RATE_LIMIT_EXCEEDED",
        ModelLoadError: "MODEL_LOADING_FAILED",
        AuthenticationError: "AUTHENTICATION_FAILED",
        NotFoundError: "NOT_FOUND",
        CacheError: "CACHE_ERROR",
        ProcessingError: "PROCESSING_ERROR"
    }
    
    @staticmethod
    def create_error_response(
        error_code: str,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    ) -> JSONResponse:
        """Create a structured error response with proper status code"""
        if error_message is None:
            error_message = ErrorReporter.ERROR_CODES.get(error_code, "Unknown error")
        
        error_response = ErrorResponse(
            error_code=error_code,
            error_message=error_message,
            error_details=error_details,
            timestamp=datetime.utcnow().isoformat()
        )
        
        return JSONResponse(
            status_code=status_code,
            content=error_response.model_dump()
        )
    
    @staticmethod
    def log_error(
        error_code: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
        log_level: str = "error"
    ):
        """Log error with structured information and timestamp"""
        log_data = {
            "error_code": error_code,
            "error_message": error_message,
            "error_details": error_details or {},
            "timestamp": datetime.utcnow().isoformat(),
            "log_level": log_level
        }
        
        if exception:
            log_data["exception_type"] = type(exception).__name__
            log_data["exception_message"] = str(exception)
            log_data["traceback"] = traceback.format_exc()
        
        # Use appropriate log level
        log_func = getattr(logger, log_level, logger.error)
        log_func(f"Error: {error_code} - {error_message}", extra=log_data)
    
    @staticmethod
    def from_nlp_exception(exc: NLPServiceError) -> JSONResponse:
        """Convert NLPServiceError to JSONResponse with automatic status mapping
        
        PHASE 2: Automatic HTTP status code mapping based on exception type
        """
        ErrorReporter.log_error(
            error_code=exc.error_code,
            error_message=exc.message,
            error_details=exc.details,
            exception=exc,
            log_level=exc.log_level
        )
        
        return ErrorReporter.create_error_response(
            error_code=exc.error_code,
            error_message=exc.message,
            error_details=exc.details,
            status_code=exc.http_status
        )
    
    @staticmethod
    def is_transient_error(exc: Exception) -> bool:
        """Check if error is transient (can be retried)
        
        PHASE 2: Supports intelligent retry logic
        """
        if isinstance(exc, NLPServiceError):
            return exc.is_transient
        return False
    
    @staticmethod
    def handle_exception(
        exception: Exception,
        error_code: str = "INTERNAL_SERVER_ERROR",
        error_details: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """Handle exception and return structured error response
        
        PHASE 2: Prioritizes NLPServiceError hierarchy over legacy handling
        """
        error_message = str(exception)
        
        # Log the error
        ErrorReporter.log_error(
            error_code=error_code,
            error_message=error_message,
            error_details=error_details,
            exception=exception
        )
        
        # Create error response
        return ErrorReporter.create_error_response(
            error_code=error_code,
            error_message=error_message,
            error_details=error_details
        )


def structured_exception_handler(request, exc):
    """Global exception handler for FastAPI
    
    PHASE 2: Priority handling for NLPServiceError hierarchy
    1. NLPServiceError subclasses -> Automatic status code mapping
    2. HTTPException -> Standard HTTP error handling
    3. Other exceptions -> Generic 500 Internal Server Error
    """
    # Handle custom NLPServiceError hierarchy (PHASE 2)
    if isinstance(exc, NLPServiceError):
        return ErrorReporter.from_nlp_exception(exc)
    
    # Handle HTTP exceptions
    elif isinstance(exc, HTTPException):
        error_code = {
            400: "INVALID_INPUT",
            401: "AUTHENTICATION_FAILED",
            403: "AUTHENTICATION_FAILED",
            404: "NOT_FOUND",
            429: "RATE_LIMIT_EXCEEDED",
            503: "MODEL_LOADING_FAILED",
        }.get(exc.status_code, "INTERNAL_SERVER_ERROR")
        
        return ErrorReporter.create_error_response(
            error_code=error_code,
            error_message=exc.detail,
            status_code=exc.status_code
        )
    
    # Handle other exceptions
    else:
        return ErrorReporter.handle_exception(exc)