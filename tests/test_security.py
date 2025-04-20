"""
Tests for security utilities.
"""

import pytest
import jwt
from datetime import datetime, timedelta

from src.utils.security import (
    hash_password, verify_password, generate_token, verify_token, JWT_SECRET
)

def test_password_hashing():
    """Test password hashing and verification."""
    password = "test_password"
    
    # Hash the password
    password_hash = hash_password(password)
    
    # Verify the password
    assert verify_password(password, password_hash)
    
    # Verify with wrong password
    assert not verify_password("wrong_password", password_hash)

def test_token_generation_and_verification():
    """Test JWT token generation and verification."""
    user_id = 1
    username = "test_user"
    is_admin = False
    
    # Generate token
    token = generate_token(user_id, username, is_admin)
    
    # Verify token
    payload = verify_token(token)
    
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["username"] == username
    assert payload["is_admin"] == is_admin

def test_expired_token():
    """Test that expired tokens are rejected."""
    # Create an expired token
    payload = {
        "sub": 1,
        "username": "test_user",
        "is_admin": False,
        "exp": datetime.utcnow() - timedelta(days=1)  # Expired 1 day ago
    }
    expired_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    
    # Verify token
    payload = verify_token(expired_token)
    
    assert payload is None

def test_invalid_token():
    """Test that invalid tokens are rejected."""
    # Create an invalid token
    invalid_token = "invalid.token.string"
    
    # Verify token
    payload = verify_token(invalid_token)
    
    assert payload is None
