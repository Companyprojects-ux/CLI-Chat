"""
Security utilities for the CLI Chat application.
"""

import os
import jwt
import datetime
from typing import Dict, Any, Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Initialize password hasher
password_hasher = PasswordHasher()

# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = datetime.timedelta(days=1)

def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return password_hasher.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a hash."""
    try:
        # The correct order is: verify(hash, password)
        password_hasher.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False
    except Exception as e:
        print(f"Password verification error: {e}")
        return False

def generate_token(user_id: int, username: str, is_admin: bool = False) -> str:
    """Generate a JWT token for a user."""
    payload = {
        "sub": user_id,
        "username": username,
        "is_admin": is_admin,
        "exp": datetime.datetime.utcnow() + JWT_EXPIRATION
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify a JWT token and return the payload."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def generate_encryption_key() -> bytes:
    """Generate a random encryption key."""
    return os.urandom(32)  # 256-bit key
