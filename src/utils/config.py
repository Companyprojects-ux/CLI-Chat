"""
Configuration utilities for the CLI Chat application.
"""

import os
import json
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

@dataclass
class Config:
    """Configuration class for the CLI Chat application."""
    host: str = "0.0.0.0"
    database_url: Optional[str] = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    log_level: str = "INFO"
    
    @classmethod
    def from_file(cls, file_path: str) -> 'Config':
        """Load configuration from a JSON file."""
        if not os.path.exists(file_path):
            return cls()
        
        try:
            with open(file_path, 'r') as f:
                config_data = json.load(f)
            return cls(**config_data)
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return cls()
    
    def to_file(self, file_path: str) -> bool:
        """Save configuration to a JSON file."""
        try:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            
            with open(file_path, 'w') as f:
                json.dump(asdict(self), f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to a dictionary."""
        return asdict(self)
