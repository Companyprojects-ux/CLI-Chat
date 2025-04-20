"""
Utilities package initialization.
"""

from .security import (
    hash_password, verify_password, generate_token, verify_token, generate_encryption_key
)
from .config import Config
from .env import load_env

# Try to import encryption module, but make it optional
try:
    from .encryption import EncryptionManager
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    print("Encryption module not available. End-to-end encryption will be disabled.")

__all__ = [
    'hash_password', 'verify_password', 'generate_token', 'verify_token', 'generate_encryption_key',
    'Config', 'load_env'
]

if ENCRYPTION_AVAILABLE:
    __all__.append('EncryptionManager')
