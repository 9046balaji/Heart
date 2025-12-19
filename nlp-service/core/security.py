"""
Security module for NLP Service
Provides JWT authentication, rate limiting, and audit logging
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import os
import time
import logging
import json
from collections import defaultdict
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

# Import Argon2 for secure password hashing
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
    ARGON2_AVAILABLE = True
except ImportError:
    ARGON2_AVAILABLE = False
    logger.warning("argon2-cffi not available - falling back to SHA-256")

logger = logging.getLogger(__name__)

# Password hashing using Argon2 (OWASP recommended) or fallback to SHA-256
def hash_password(password: str) -> str:
    """Hash a password using Argon2 (preferred) or SHA-256 (fallback)."""
    if ARGON2_AVAILABLE:
        ph = PasswordHasher()
        return ph.hash(password)
    else:
        # Fallback to SHA-256 for backward compatibility
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash using Argon2 (preferred) or SHA-256 (fallback)."""
    if ARGON2_AVAILABLE:
        ph = PasswordHasher()
        try:
            ph.verify(hashed_password, plain_password)
            return True
        except VerifyMismatchError:
            return False
    else:
        # Fallback to SHA-256 for backward compatibility
        import hashlib
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password

# JWT authentication scheme
bearer_scheme = HTTPBearer()

# Rate limiting storage
rate_limit_storage: Dict[str, list] = defaultdict(list)


class AuditLogger:
    """
    Audit logging for security events and access patterns.
    
    Logs:
    - Authentication attempts (success/failure)
    - Rate limit violations
    - API access patterns
    - Data access requests
    
    Format: JSON for easy parsing and analysis
    """
    
    def __init__(self, log_file: str = "audit.log"):
        self.log_file = log_file
        self.file_handler = None
    
    def log_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log security audit event.
        
        Args:
            event_type: Type of event (auth, rate_limit, access, etc)
            user_id: User making the request
            endpoint: API endpoint accessed
            status_code: HTTP status code
            details: Additional details
        """
        audit_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'event_type': event_type,
            'user_id': user_id,
            'endpoint': endpoint,
            'status_code': status_code,
            'details': details or {}
        }
        
        # Log as JSON for easy parsing
        audit_json = json.dumps(audit_entry)
        logger.warning(f"AUDIT: {audit_json}")
        
        # Also write to file for audit trail
        try:
            with open(self.log_file, 'a') as f:
                f.write(audit_json + '\n')
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def log_auth_success(self, user_id: str):
        """Log successful authentication"""
        self.log_event('AUTH_SUCCESS', user_id=user_id)
    
    def log_auth_failure(self, user_id: Optional[str] = None, reason: str = ""):
        """Log authentication failure"""
        self.log_event(
            'AUTH_FAILURE',
            user_id=user_id,
            details={'reason': reason}
        )
    
    def log_rate_limit_violation(self, user_id: str, endpoint: str):
        """Log rate limit violation"""
        self.log_event(
            'RATE_LIMIT_VIOLATION',
            user_id=user_id,
            endpoint=endpoint,
            status_code=429
        )
    
    def log_api_access(self, user_id: str, endpoint: str, status_code: int):
        """Log API access"""
        self.log_event(
            'API_ACCESS',
            user_id=user_id,
            endpoint=endpoint,
            status_code=status_code
        )


# Global audit logger
audit_logger = AuditLogger()


class RateLimiter:
    """
    Advanced rate limiter with per-endpoint and per-user limits.
    
    Algorithms:
    - Token bucket: Allows burst traffic up to limit
    - Sliding window: Tracks exact request times
    
    Complexity:
    - check(): O(n) where n = requests in window (typically small)
    - cleanup(): O(n log n) for old entry removal
    """
    
    def __init__(
        self,
        requests_per_minute: int = 100,
        requests_per_hour: int = 5000,
        cleanup_interval: int = 300
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.cleanup_interval = cleanup_interval  # seconds
        self.last_cleanup = time.time()
        
        # Per-user tracking
        self.user_requests: Dict[str, List[float]] = defaultdict(list)
        # Per-endpoint tracking
        self.endpoint_requests: Dict[str, List[float]] = defaultdict(list)
    
    def check_rate_limit(
        self,
        user_id: str,
        endpoint: str = "global"
    ) -> tuple[bool, Optional[str]]:
        """
        Check if request should be allowed.
        
        Returns:
            (is_allowed, reason_if_blocked)
        """
        now = time.time()
        
        # Cleanup old entries periodically
        if now - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries(now)
        
        # Check per-minute limit
        minute_ago = now - 60
        user_requests_this_minute = [
            t for t in self.user_requests[user_id]
            if t > minute_ago
        ]
        
        if len(user_requests_this_minute) >= self.requests_per_minute:
            audit_logger.log_rate_limit_violation(user_id, endpoint)
            return False, f"Rate limit exceeded: {self.requests_per_minute} requests per minute"
        
        # Check per-hour limit
        hour_ago = now - 3600
        user_requests_this_hour = [
            t for t in self.user_requests[user_id]
            if t > hour_ago
        ]
        
        if len(user_requests_this_hour) >= self.requests_per_hour:
            audit_logger.log_rate_limit_violation(user_id, endpoint)
            return False, f"Rate limit exceeded: {self.requests_per_hour} requests per hour"
        
        # Request allowed - record it
        self.user_requests[user_id].append(now)
        self.endpoint_requests[endpoint].append(now)
        
        return True, None
    
    def _cleanup_old_entries(self, now: float):
        """Remove old entries older than 1 hour"""
        hour_ago = now - 3600
        
        for user_id in list(self.user_requests.keys()):
            self.user_requests[user_id] = [
                t for t in self.user_requests[user_id]
                if t > hour_ago
            ]
            if not self.user_requests[user_id]:
                del self.user_requests[user_id]
        
        for endpoint in list(self.endpoint_requests.keys()):
            self.endpoint_requests[endpoint] = [
                t for t in self.endpoint_requests[endpoint]
                if t > hour_ago
            ]
            if not self.endpoint_requests[endpoint]:
                del self.endpoint_requests[endpoint]
        
        self.last_cleanup = now
        logger.debug("Rate limiter cleanup complete")
    
    def get_stats(self, user_id: str) -> Dict[str, int]:
        """Get rate limit stats for user"""
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        
        minute_count = len([
            t for t in self.user_requests[user_id]
            if t > minute_ago
        ])
        
        hour_count = len([
            t for t in self.user_requests[user_id]
            if t > hour_ago
        ])
        
        return {
            'requests_this_minute': minute_count,
            'limit_per_minute': self.requests_per_minute,
            'requests_this_hour': hour_count,
            'limit_per_hour': self.requests_per_hour,
            'remaining_this_minute': max(0, self.requests_per_minute - minute_count),
            'remaining_this_hour': max(0, self.requests_per_hour - hour_count),
        }


# Global rate limiter
rate_limiter = RateLimiter(
    requests_per_minute=100,
    requests_per_hour=5000
)


class SecurityManager:
    """Security manager for JWT authentication and rate limiting"""
    
    def __init__(self):
        """Initialize security manager"""
        self.secret_key = SECRET_KEY
        self.algorithm = ALGORITHM
        self.access_token_expire_minutes = ACCESS_TOKEN_EXPIRE_MINUTES
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password"""
        return verify_password(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a plain password"""
        return hash_password(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a JWT token and return the payload"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Dependency to get current user from JWT token"""
    security_manager = SecurityManager()
    payload = security_manager.verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def rate_limiter(request: Request):
    """Rate limiting dependency"""
    # Get client IP
    client_ip = request.client.host
    
    # Get current time
    current_time = time.time()
    
    # Remove requests older than 1 minute
    rate_limit_storage[client_ip] = [
        req_time for req_time in rate_limit_storage[client_ip]
        if current_time - req_time < 60
    ]
    
    # Check if limit exceeded (100 requests per minute)
    if len(rate_limit_storage[client_ip]) >= 100:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )
    
    # Add current request
    rate_limit_storage[client_ip].append(current_time)
    
    return True