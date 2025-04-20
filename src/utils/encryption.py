"""
Encryption utilities for the CLI Chat application.
"""

import os
import base64
import json
from typing import Dict, Tuple, Optional, Any
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class EncryptionManager:
    """Manager for end-to-end encryption."""

    def __init__(self, keys_dir: str = None):
        """Initialize the encryption manager."""
        if keys_dir is None:
            self.keys_dir = os.path.join(os.path.expanduser("~"), ".cli_chat_keys")
        else:
            self.keys_dir = keys_dir

        os.makedirs(self.keys_dir, exist_ok=True)

        self.private_key = None
        self.public_key = None
        self.peer_keys: Dict[str, Any] = {}

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """Generate a new RSA key pair."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        public_key = private_key.public_key()

        # Serialize keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        self.private_key = private_key
        self.public_key = public_key

        return private_pem, public_pem

    def load_or_generate_keypair(self, username: str) -> Tuple[bytes, bytes]:
        """Load existing keys or generate new ones."""
        private_key_path = os.path.join(self.keys_dir, f"{username}_private.pem")
        public_key_path = os.path.join(self.keys_dir, f"{username}_public.pem")

        if os.path.exists(private_key_path) and os.path.exists(public_key_path):
            # Load existing keys
            with open(private_key_path, "rb") as f:
                private_pem = f.read()

            with open(public_key_path, "rb") as f:
                public_pem = f.read()

            self.private_key = serialization.load_pem_private_key(
                private_pem,
                password=None,
                backend=default_backend()
            )

            self.public_key = serialization.load_pem_public_key(
                public_pem,
                backend=default_backend()
            )
        else:
            # Generate new keys
            private_pem, public_pem = self.generate_keypair()

            # Save keys
            with open(private_key_path, "wb") as f:
                f.write(private_pem)

            with open(public_key_path, "wb") as f:
                f.write(public_pem)

        return private_pem, public_pem

    def add_peer_key(self, username: str, public_key_pem: bytes) -> None:
        """Add a peer's public key."""
        try:
            # Debug the key content
            print(f"Key content: {public_key_pem[:50]}...")

            # Fix the key format if needed
            if not public_key_pem.startswith(b'-----BEGIN PUBLIC KEY-----'):
                # Try to fix common formatting issues
                # Convert to uppercase if needed
                upper_key = public_key_pem.upper()
                if b'-----BEGIN PUBLIC KEY-----' in upper_key:
                    # Extract the key part
                    start = upper_key.find(b'-----BEGIN PUBLIC KEY-----')
                    end = upper_key.find(b'-----END PUBLIC KEY-----')
                    if end > start:
                        # Use the original case but with correct positions
                        public_key_pem = public_key_pem[start:end + len(b'-----END PUBLIC KEY-----')]
                    else:
                        raise ValueError("Invalid public key format: missing END marker")
                else:
                    # Try to fix case issues
                    fixed_key = public_key_pem.replace(b'-----begin public key-----', b'-----BEGIN PUBLIC KEY-----')
                    fixed_key = fixed_key.replace(b'-----end public key-----', b'-----END PUBLIC KEY-----')

                    if fixed_key.startswith(b'-----BEGIN PUBLIC KEY-----'):
                        public_key_pem = fixed_key
                    else:
                        raise ValueError("Invalid public key format: missing PEM header")

            # Load the public key
            public_key = serialization.load_pem_public_key(
                public_key_pem,
                backend=default_backend()
            )

            self.peer_keys[username] = public_key

            # Save peer key
            peer_key_path = os.path.join(self.keys_dir, f"{username}_peer.pem")
            with open(peer_key_path, "wb") as f:
                f.write(public_key_pem)

            print(f"Successfully added peer key for {username}")
        except Exception as e:
            print(f"Error adding peer key: {e}")
            # Re-raise the exception for the caller to handle
            raise

    def load_peer_key(self, username: str) -> Optional[Any]:
        """Load a peer's public key."""
        if username in self.peer_keys:
            return self.peer_keys[username]

        peer_key_path = os.path.join(self.keys_dir, f"{username}_peer.pem")
        if os.path.exists(peer_key_path):
            with open(peer_key_path, "rb") as f:
                public_key_pem = f.read()

            public_key = serialization.load_pem_public_key(
                public_key_pem,
                backend=default_backend()
            )

            self.peer_keys[username] = public_key
            return public_key

        return None

    def encrypt_message(self, message: str, recipient_username: str) -> Optional[str]:
        """Encrypt a message for a specific recipient."""
        recipient_key = self.load_peer_key(recipient_username)
        if not recipient_key:
            return None

        # Generate a random AES key
        aes_key = os.urandom(32)  # 256-bit key

        # Encrypt the AES key with the recipient's public key
        encrypted_key = recipient_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        # Generate a random IV
        iv = os.urandom(16)  # 128-bit IV for AES

        # Create an AES cipher
        cipher = Cipher(
            algorithms.AES(aes_key),
            modes.CFB(iv),
            backend=default_backend()
        )

        # Encrypt the message
        encryptor = cipher.encryptor()
        message_bytes = message.encode('utf-8')
        ciphertext = encryptor.update(message_bytes) + encryptor.finalize()

        # Create the encrypted message package
        encrypted_package = {
            "encrypted_key": base64.b64encode(encrypted_key).decode('utf-8'),
            "iv": base64.b64encode(iv).decode('utf-8'),
            "ciphertext": base64.b64encode(ciphertext).decode('utf-8')
        }

        # Return the encrypted package as a JSON string
        return json.dumps(encrypted_package)

    def decrypt_message(self, encrypted_message: str) -> Optional[str]:
        """Decrypt a message."""
        if not self.private_key:
            return None

        try:
            # Parse the encrypted package
            encrypted_package = json.loads(encrypted_message)

            encrypted_key = base64.b64decode(encrypted_package["encrypted_key"])
            iv = base64.b64decode(encrypted_package["iv"])
            ciphertext = base64.b64decode(encrypted_package["ciphertext"])

            # Decrypt the AES key
            aes_key = self.private_key.decrypt(
                encrypted_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            # Create an AES cipher
            cipher = Cipher(
                algorithms.AES(aes_key),
                modes.CFB(iv),
                backend=default_backend()
            )

            # Decrypt the message
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            # Return the decrypted message
            return plaintext.decode('utf-8')

        except Exception as e:
            print(f"Error decrypting message: {e}")
            return None

    def get_public_key_str(self) -> str:
        """Get the public key as a base64 string."""
        if not self.public_key:
            return ""

        public_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # Use a simpler encoding that preserves the PEM format
        return base64.b64encode(public_pem).decode('utf-8')

    def get_public_key_bytes(self) -> bytes:
        """Get the public key as bytes."""
        if not self.public_key:
            return b""

        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def is_encrypted_message(self, message: str) -> bool:
        """Check if a message is encrypted."""
        try:
            package = json.loads(message)
            return all(key in package for key in ["encrypted_key", "iv", "ciphertext"])
        except:
            return False
