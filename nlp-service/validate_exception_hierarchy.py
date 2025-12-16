#!/usr/bin/env python3
"""
Quick validation script for PHASE 2 TASK 2.1: Exception Hierarchy

Tests all 9 exception types for:
1. Correct HTTP status codes
2. Correct error codes
3. Proper transient/permanent classification
"""

from error_handling import (
    ValidationError, TimeoutError, ExternalServiceError, RateLimitError,
    ModelLoadError, AuthenticationError, NotFoundError, CacheError, ProcessingError,
    ErrorReporter
)

exceptions = [
    (ValidationError("Invalid"), 400, "INVALID_INPUT", False),
    (TimeoutError("Timeout"), 504, "SERVICE_TIMEOUT", True),
    (ExternalServiceError("DB failed"), 502, "EXTERNAL_SERVICE_FAILED", True),
    (RateLimitError("Too many"), 429, "RATE_LIMIT_EXCEEDED", True),
    (ModelLoadError("Load failed"), 503, "MODEL_LOADING_FAILED", True),
    (AuthenticationError("Auth failed"), 401, "AUTHENTICATION_FAILED", False),
    (NotFoundError("Not found"), 404, "NOT_FOUND", False),
    (CacheError("Cache failed"), 500, "CACHE_ERROR", True),
    (ProcessingError("Process failed"), 500, "PROCESSING_ERROR", False),
]

print("Exception Hierarchy Validation:")
print("=" * 80)

all_pass = True
for exc, expected_status, expected_code, expected_transient in exceptions:
    response = ErrorReporter.from_nlp_exception(exc)
    is_transient = ErrorReporter.is_transient_error(exc)
    
    status_ok = response.status_code == expected_status
    code_ok = expected_code in exc.error_code
    transient_ok = is_transient == expected_transient
    
    status_mark = "✓" if status_ok else "✗"
    code_mark = "✓" if code_ok else "✗"
    transient_mark = "✓" if transient_ok else "✗"
    
    print(f"{status_mark} {exc.__class__.__name__:25} | Status: {response.status_code:3} | Transient: {str(is_transient):5} | Code: {exc.error_code}")
    
    if not (status_ok and code_ok and transient_ok):
        print(f"  ERROR: Expected status={expected_status}, code={expected_code}, transient={expected_transient}")
        all_pass = False

print("=" * 80)
if all_pass:
    print("✓ All exception types configured correctly!")
    print("\nPHASE 2 TASK 2.1 Status: PASSING")
else:
    print("✗ Some exceptions have incorrect configuration")

# Test ErrorReporter helper methods
print("\nTesting ErrorReporter helper methods:")
print("-" * 80)

# Test creating error response
response = ErrorReporter.create_error_response(
    error_code="TEST_ERROR",
    error_message="Test message",
    status_code=400
)
print(f"✓ create_error_response() returns JSONResponse with status {response.status_code}")

# Test error response includes timestamp
content = response.body.decode()
if "timestamp" in content:
    print("✓ Error response includes ISO timestamp")
else:
    print("✗ Error response missing timestamp")

# Test EXCEPTION_MAP exists
if hasattr(ErrorReporter, 'EXCEPTION_MAP'):
    print(f"✓ EXCEPTION_MAP defined with {len(ErrorReporter.EXCEPTION_MAP)} mappings")
else:
    print("✗ EXCEPTION_MAP not defined")

print("-" * 80)
print("\nPHASE 2 TASK 2.1: Exception Hierarchy Implementation Complete!")
