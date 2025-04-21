"""
Unit tests for client-side file transfer and encryption functionality.
"""

import os
import tempfile
import unittest
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.frontend.client import ChatClient
from src.utils.config import Config


class TestClientFeatures(unittest.TestCase):
    """Test cases for client-side file transfer and encryption functionality."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock config
        self.mock_config = Config()

        # Create a client instance
        self.client = ChatClient("localhost", 8000, "testuser", self.mock_config)

        # Mock console
        self.client.console = MagicMock()

        # Mock encryption manager
        self.mock_encryption_manager = MagicMock()
        self.client.encryption_manager = self.mock_encryption_manager
        self.client.encryption_enabled = True

        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.test_file_path = os.path.join(self.test_dir, "test_file.txt")
        with open(self.test_file_path, "w") as f:
            f.write("This is a test file content.")

    def tearDown(self):
        """Clean up test environment."""
        # Remove test directory
        import shutil
        shutil.rmtree(self.test_dir)

    @pytest.mark.asyncio
    @patch('websockets.connect', new_callable=AsyncMock)
    async def test_send_file(self, mock_connect):
        """Test sending a file."""
        # Set up mock websocket
        mock_websocket = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_websocket

        # Create a message to send a file
        message = f"/file recipient {self.test_file_path}"

        # Call the send_messages method with our test message
        with patch.object(self.client, 'authenticate', return_value=True):
            # Start the client connection
            # Note: We're not awaiting the connect task as we're just testing the send_message method
            _ = self.client.connect()

            # Simulate sending a message
            await self.client.send_message(mock_websocket, message)

            # Check that the file was sent
            mock_websocket.send.assert_called_once()
            sent_message = mock_websocket.send.call_args[0][0]

            # Verify the message format
            self.assertTrue(sent_message.startswith("/file recipient test_file.txt;"))
            self.assertIn("test_file.txt;", sent_message)

            # Verify console output
            self.client.console.print.assert_called()
            console_output = self.client.console.print.call_args[0][0]
            self.assertIn("Sending file", str(console_output))

    @pytest.mark.asyncio
    @patch('websockets.connect', new_callable=AsyncMock)
    async def test_receive_file(self, mock_connect):
        """Test receiving a file."""
        # Set up mock websocket
        mock_websocket = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_websocket

        # Create test file data
        import base64
        file_content = b"This is test file content."
        base64_data = base64.b64encode(file_content).decode('utf-8')

        # Create a file message
        file_message = {
            "type": "file",
            "username": "sender",
            "filename": "received_file.txt",
            "size": len(file_content),
            "data": base64_data,
            "hash": "file_hash"
        }

        # Mock Prompt.ask to simulate user confirming file save
        with patch('rich.prompt.Prompt.ask', return_value="y"), \
             patch('os.makedirs'), \
             patch('builtins.open', unittest.mock.mock_open()), \
             patch('hashlib.sha256') as mock_hashlib:

            # Mock hash verification
            mock_hash = MagicMock()
            mock_hash.hexdigest.return_value = "file_hash"
            mock_hashlib.return_value = mock_hash

            # Call the display_message method
            await self.client.display_message(file_message)

            # Check console output
            self.client.console.print.assert_called()

            # Check that file was saved
            open.assert_called_once()

    @pytest.mark.asyncio
    @patch('websockets.connect', new_callable=AsyncMock)
    async def test_send_encrypted_message(self, mock_connect):
        """Test sending an encrypted message."""
        # Set up mock websocket
        mock_websocket = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_websocket

        # Mock encryption manager
        self.mock_encryption_manager.load_peer_key.return_value = True
        self.mock_encryption_manager.encrypt_message.return_value = "encrypted_content"

        # Create a whisper message
        message = "/whisper recipient This is a secret message."

        # Call the send_message method
        await self.client.send_message(mock_websocket, message)

        # Check that the message was encrypted
        self.mock_encryption_manager.encrypt_message.assert_called_once_with(
            "This is a secret message.", "recipient"
        )

        # Check that the encrypted message was sent
        mock_websocket.send.assert_called_once_with("/whisper recipient [ENCRYPTED]encrypted_content")

    @pytest.mark.asyncio
    @patch('websockets.connect', new_callable=AsyncMock)
    async def test_receive_encrypted_message(self, mock_connect):
        """Test receiving an encrypted message."""
        # Set up mock websocket
        mock_websocket = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_websocket

        # Mock encryption manager
        self.mock_encryption_manager.decrypt_message.return_value = "Decrypted secret message"

        # Create an encrypted whisper message
        encrypted_message = {
            "type": "whisper",
            "username": "sender",
            "content": "[ENCRYPTED]encrypted_content"
        }

        # Call the display_message method
        await self.client.display_message(encrypted_message)

        # Check that the message was decrypted
        self.mock_encryption_manager.decrypt_message.assert_called_once_with("encrypted_content")

        # Check console output
        self.client.console.print.assert_called()
        console_output = self.client.console.print.call_args[0][0]
        self.assertIn("Decrypted secret message", str(console_output))

    @pytest.mark.asyncio
    @patch('websockets.connect', new_callable=AsyncMock)
    async def test_key_exchange(self, mock_connect):
        """Test key exchange between users."""
        # Set up mock websocket
        mock_websocket = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_websocket

        # Mock encryption manager
        self.mock_encryption_manager.get_public_key_bytes.return_value = b"-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...\n-----END PUBLIC KEY-----\n"

        # Create a sendkey message
        message = "/sendkey recipient"

        # Call the send_message method
        await self.client.send_message(mock_websocket, message)

        # Check that the public key was retrieved
        self.mock_encryption_manager.get_public_key_bytes.assert_called_once()

        # Check that the key was sent
        mock_websocket.send.assert_called_once()
        sent_message = mock_websocket.send.call_args[0][0]
        self.assertTrue(sent_message.startswith("/whisper recipient /pubkey"))

        # Check console output
        self.client.console.print.assert_called()
        console_output = self.client.console.print.call_args[0][0]
        self.assertIn("Public key sent", str(console_output))


if __name__ == '__main__':
    unittest.main()
