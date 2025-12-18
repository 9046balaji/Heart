# HeartGuard / Cardio AI – Future Implementation & Architecture Report

**Date:** December 17, 2025
**Reference Document:** `future.md`
**Status:** 🔵 **FUTURE ROADMAP & ARCHITECTURE DESIGN**

---

## 1. Executive Summary

This report outlines the detailed technical implementation plan for the "Future Work" identified in the HeartGuard roadmap. It addresses critical gaps in **Security (Auth/Encryption)**, **Architecture (Refactoring)**, and **Quality Assurance (Testing)**.

**Key Additions in this Version:**
*   **Token Refresh & User Management:** Full OAuth2 flow.
*   **Key Rotation Strategy:** Handling key lifecycle for PHI.
*   **SQL Injection Remediation:** Replacing custom query builders with ORM.
*   **Unit Testing Framework:** Concrete test examples.

---

## 2. Phase 1: Identified Requirements & Issues

| ID | Feature/Issue | Priority | Description |
|----|---------------|----------|-------------|
| **F1** | **Authentication System** | 🔴 High | JWT/OAuth2, User Management, Token Refresh. |
| **F2** | **Authorization (RBAC)** | 🔴 High | Role-based access, Audit trails for PHI. |
| **F3** | **PHI Encryption** | 🔴 High | Encryption at rest, Key Rotation, HSM/KMS integration. |
| **F4** | **Route Refactoring** | 🟡 Medium | Extract `nlp_core`, `health`, reduce `main.py`. |
| **F5** | **Unit Tests** | 🟡 Medium | Test routers, dependencies, and security. |
| **F6** | **SQL Injection** | 🔴 High | Replace custom query builders with safe ORM patterns. |

---

## 3. Phase 2: Detailed Technical Solution Design

### Solution F1 & F2: Advanced Authentication & RBAC

**Architecture:**
*   **Access Token:** JWT (15 min expiry).
*   **Refresh Token:** Opaque secure string (7 day expiry), stored in DB with rotation.
*   **User Model:** SQLAlchemy model with hashed passwords.

#### 1. Auth Models & Security Logic (`nlp-service/auth/security.py`)

```python
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"

def create_tokens(subject: str, role: str) -> dict:
    # Access Token
    access_expire = datetime.utcnow() + timedelta(minutes=15)
    access_payload = {"sub": subject, "role": role, "exp": access_expire, "type": "access"}
    access_token = jwt.encode(access_payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    
    # Refresh Token (Long lived)
    refresh_expire = datetime.utcnow() + timedelta(days=7)
    refresh_payload = {"sub": subject, "exp": refresh_expire, "type": "refresh"}
    refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    
    return {"access_token": access_token, "refresh_token": refresh_token}

def verify_token(token: str, expected_type: str = "access"):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            raise ValueError("Invalid token type")
        return payload
    except Exception:
        return None
```

#### 2. Refresh Endpoint (`nlp-service/routes/auth.py`)

```python
from fastapi import APIRouter, HTTPException, Depends, Header
from auth.security import verify_token, create_tokens
# Assume get_user_by_id is a DB crud function

router = APIRouter(tags=["Auth"])

@router.post("/auth/refresh")
async def refresh_token(refresh_token: str = Header(..., alias="X-Refresh-Token")):
    payload = verify_token(refresh_token, expected_type="refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    # In a real app, check if refresh token is revoked in DB here
    
    user_id = payload["sub"]
    # user = await get_user_by_id(user_id) 
    # For demo:
    user_role = "patient" # fetch from DB
    
    new_tokens = create_tokens(user_id, user_role)
    return new_tokens
```

---

### Solution F3: PHI Encryption with Key Rotation

**Strategy:**
Support multiple keys. Always encrypt with the *primary* (latest) key. Attempt decryption with primary, then fallback to secondary keys.

#### 1. Key Rotation Logic (`nlp-service/utils/crypto.py`)

```python
from cryptography.fernet import Fernet, MultiFernet
from config import settings
import json

class KeyManager:
    def __init__(self):
        # settings.ENCRYPTION_KEYS should be a JSON list of keys
        # The first key is the PRIMARY (used for encryption)
        keys = json.loads(settings.ENCRYPTION_KEYS)
        self.fernet_instances = [Fernet(k) for k in keys]
        self.multi_fernet = MultiFernet(self.fernet_instances)

    def encrypt(self, data: str) -> str:
        if not data: return ""
        # MultiFernet.encrypt uses the first key in the list
        return self.multi_fernet.encrypt(data.encode()).decode()

    def decrypt(self, token: str) -> str:
        if not token: return ""
        # MultiFernet.decrypt tries all keys in order
        return self.multi_fernet.decrypt(token.encode()).decode()

    def rotate_data(self, token: str) -> str:
        """Re-encrypts data with the primary key if it was encrypted with an old one."""
        return self.multi_fernet.rotate(token.encode()).decode()
```

---

### Solution F6: SQL Injection Remediation

**Problem:** Custom query builders (e.g., string concatenation) allow injection.
**Fix:** Use SQLAlchemy ORM or Core with bound parameters.

#### 1. Vulnerable Code (Example)
```python
# BAD
query = f"SELECT * FROM patients WHERE name = '{user_input}'"
cursor.execute(query)
```

#### 2. Remediated Code (`nlp-service/db/repository.py`)

```python
from sqlalchemy.orm import Session
from .models import Patient

def get_patient_by_name(db: Session, name: str):
    # GOOD: SQLAlchemy handles escaping automatically
    return db.query(Patient).filter(Patient.name == name).first()

def search_patients_safe(db: Session, search_term: str):
    # GOOD: Using bound parameters with text() if raw SQL is absolutely necessary
    from sqlalchemy import text
    stmt = text("SELECT * FROM patients WHERE name LIKE :term")
    return db.execute(stmt, {"term": f"%{search_term}%"}).fetchall()
```

---

### Solution F5: Unit Testing Framework

**Strategy:** Use `pytest` and `httpx` for async integration tests.

#### 1. Test Setup (`tests/conftest.py`)

```python
import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers():
    # Helper to generate a valid token for tests
    from auth.security import create_tokens
    tokens = create_tokens("test_user", "doctor")
    return {"Authorization": f"Bearer {tokens['access_token']}"}
```

#### 2. Auth Tests (`tests/test_auth.py`)

```python
def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_protected_route_without_token(client):
    response = client.get("/nlp/analyze", json={"text": "hello"})
    assert response.status_code == 401

def test_protected_route_with_token(client, auth_headers):
    # Mocking the actual NLP logic might be needed here
    response = client.post("/nlp/analyze", json={"text": "hello"}, headers=auth_headers)
    assert response.status_code in [200, 422] # 422 if validation fails, 200 if success
```

---

## 4. Phase 4: Execution Roadmap

### Week 1: Core Security & Refactoring
1.  **Refactor:** Split `main.py` into `routes/`.
2.  **SQL Fix:** Audit codebase for raw SQL and replace with SQLAlchemy.
3.  **Auth Base:** Implement `security.py` and `KeyManager`.

### Week 2: Advanced Features
1.  **Endpoints:** Implement `/login`, `/refresh`, and protect `/nlp/*`.
2.  **Encryption:** Update DB models to use `KeyManager` for PHI fields.
3.  **Testing:** Write tests for Auth and Crypto modules.

### Week 3: Operations
1.  **Key Rotation:** Document procedure for adding new keys to `ENCRYPTION_KEYS` env var.
2.  **Audit:** Verify SQL injection fixes with `sqlmap` (in dev environment).

---

## 5. Success Criteria

1.  **Zero SQL Injection:** Static analysis (Bandit) returns 0 high-severity issues.
2.  **Key Rotation:** System can decrypt data encrypted with an old key and re-encrypt with the new one.
3.  **Token Refresh:** Client can maintain a session > 15 mins without re-login using the refresh flow.
4.  **Test Coverage:** > 85% coverage for `auth/` and `utils/crypto.py`.
