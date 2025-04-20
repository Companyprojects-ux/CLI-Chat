"""
Environment variable utilities.
"""

import os
import dotenv
from pathlib import Path

def load_env(env_file=None):
    """Load environment variables from .env file."""
    if env_file is None:
        # Try to find .env file in the project root
        project_root = Path(__file__).parent.parent.parent
        env_file = project_root / '.env'
    
    # Load environment variables from .env file
    dotenv.load_dotenv(env_file)
    
    return {
        'MYSQL_HOST': os.getenv('MYSQL_HOST', 'localhost'),
        'MYSQL_PORT': os.getenv('MYSQL_PORT', '3306'),
        'MYSQL_USER': os.getenv('MYSQL_USER', 'chatuser'),
        'MYSQL_PASSWORD': os.getenv('MYSQL_PASSWORD', 'chatpassword'),
        'MYSQL_DATABASE': os.getenv('MYSQL_DATABASE', 'cli_chat'),
        'REDIS_HOST': os.getenv('REDIS_HOST', 'localhost'),
        'REDIS_PORT': os.getenv('REDIS_PORT', '6379'),
        'JWT_SECRET': os.getenv('JWT_SECRET', 'your-secret-key-change-in-production'),
    }
