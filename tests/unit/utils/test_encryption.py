"""
Unit tests for the encryption module.
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from src.utils.encryption import EncryptionManager


class TestEncryptionManager(unittest.TestCase):
    """Test cases for the EncryptionManager class."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test keys
        self.test_keys_dir = tempfile.mkdtemp()
        self.encryption_manager = EncryptionManager(keys_dir=self.test_keys_dir)

    def tearDown(self):
        """Clean up test environment."""
        # Remove test keys directory
        import shutil
        shutil.rmtree(self.test_keys_dir)

    def test_generate_keypair(self):
        """Test generating a new RSA key pair."""
        private_pem, public_pem = self.encryption_manager.generate_keypair()

        # Check that keys were generated
        self.assertIsNotNone(private_pem)
        self.assertIsNotNone(public_pem)
        self.assertIsInstance(private_pem, bytes)
        self.assertIsInstance(public_pem, bytes)

        # Check that private key has correct format
        self.assertTrue(private_pem.startswith(b'-----BEGIN PRIVATE KEY-----'))
        self.assertTrue(private_pem.endswith(b'-----END PRIVATE KEY-----\n'))

        # Check that public key has correct format
        self.assertTrue(public_pem.startswith(b'-----BEGIN PUBLIC KEY-----'))
        self.assertTrue(public_pem.endswith(b'-----END PUBLIC KEY-----\n'))

    def test_load_or_generate_keypair(self):
        """Test loading or generating a key pair."""
        username = "testuser"
        private_pem, public_pem = self.encryption_manager.load_or_generate_keypair(username)

        # Check that keys were generated
        self.assertIsNotNone(private_pem)
        self.assertIsNotNone(public_pem)

        # Check that key files were created
        private_key_path = os.path.join(self.test_keys_dir, f"{username}_private.pem")
        public_key_path = os.path.join(self.test_keys_dir, f"{username}_public.pem")
        self.assertTrue(os.path.exists(private_key_path))
        self.assertTrue(os.path.exists(public_key_path))

        # Load the keys again and check they're the same
        private_pem2, public_pem2 = self.encryption_manager.load_or_generate_keypair(username)
        self.assertEqual(private_pem, private_pem2)
        self.assertEqual(public_pem, public_pem2)

    def test_add_peer_key(self):
        """Test adding a peer's public key."""
        # Generate a key pair for a peer
        peer_username = "peeruser"
        _, peer_public_pem = self.encryption_manager.generate_keypair()

        # Add the peer's public key
        self.encryption_manager.add_peer_key(peer_username, peer_public_pem)

        # Check that the peer key was stored
        peer_key_path = os.path.join(self.test_keys_dir, f"{peer_username}_peer.pem")
        self.assertTrue(os.path.exists(peer_key_path))

        # Check that the peer key can be loaded
        peer_key = self.encryption_manager.load_peer_key(peer_username)
        self.assertIsNotNone(peer_key)

    def test_encrypt_decrypt_message(self):
        """Test encrypting and decrypting a message."""
        # Generate keys for sender and recipient
        sender_username = "sender"
        recipient_username = "recipient"

        # Set up sender's encryption manager
        sender_manager = EncryptionManager(keys_dir=self.test_keys_dir)
        sender_manager.load_or_generate_keypair(sender_username)

        # Set up recipient's encryption manager
        recipient_manager = EncryptionManager(keys_dir=self.test_keys_dir)
        recipient_private_pem, recipient_public_pem = recipient_manager.load_or_generate_keypair(recipient_username)

        # Add recipient's public key to sender's manager
        sender_manager.add_peer_key(recipient_username, recipient_public_pem)

        # Test message
        original_message = "This is a secret message!"

        # Encrypt the message
        encrypted_message = sender_manager.encrypt_message(original_message, recipient_username)
        self.assertIsNotNone(encrypted_message)

        # Decrypt the message
        decrypted_message = recipient_manager.decrypt_message(encrypted_message)
        self.assertEqual(original_message, decrypted_message)

    def test_is_encrypted_message(self):
        """Test checking if a message is encrypted."""
        # Generate a test encrypted message
        sender_username = "sender"
        recipient_username = "recipient"

        # Set up sender's encryption manager
        sender_manager = EncryptionManager(keys_dir=self.test_keys_dir)
        sender_manager.load_or_generate_keypair(sender_username)

        # Set up recipient's encryption manager
        recipient_manager = EncryptionManager(keys_dir=self.test_keys_dir)
        _, recipient_public_pem = recipient_manager.load_or_generate_keypair(recipient_username)

        # Add recipient's public key to sender's manager
        sender_manager.add_peer_key(recipient_username, recipient_public_pem)

        # Encrypt a message
        encrypted_message = sender_manager.encrypt_message("Secret message", recipient_username)

        # Check that it's recognized as encrypted
        self.assertTrue(sender_manager.is_encrypted_message(encrypted_message))

        # Check that a regular message is not recognized as encrypted
        self.assertFalse(sender_manager.is_encrypted_message("Regular message"))
        self.assertFalse(sender_manager.is_encrypted_message('{"not_encrypted": true}'))


if __name__ == '__main__':
    unittest.main()
