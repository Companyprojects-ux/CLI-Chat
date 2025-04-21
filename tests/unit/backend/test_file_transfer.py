"""
Unit tests for file transfer functionality in the server.
"""

import unittest
import pytest
import json
import base64
import hashlib
from unittest.mock import patch, MagicMock, AsyncMock

from src.backend.server import ChatServer


class TestFileTransfer(unittest.TestCase):
    """Test cases for file transfer functionality in the server."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock config
        self.mock_config = MagicMock()
        self.mock_config.database_url = "sqlite:///:memory:"

        # Create a server instance with mocked dependencies
        with patch('src.backend.server.get_engine'), \
             patch('src.backend.server.init_db'):
            self.server = ChatServer(8000, "admin", self.mock_config)

        # Mock the database session
        self.mock_session = MagicMock()
        self.server.db_engine = MagicMock()

        # Mock get_session to return our mock session
        self.get_session_patcher = patch('src.backend.server.get_session', return_value=self.mock_session)
        self.mock_get_session = self.get_session_patcher.start()

        # Set up mock users
        self.mock_sender = MagicMock()
        self.mock_sender.id = 1
        self.mock_sender.username = "sender"

        self.mock_receiver = MagicMock()
        self.mock_receiver.id = 2
        self.mock_receiver.username = "receiver"

        # Mock query results
        self.mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            self.mock_sender,  # First call returns sender
            self.mock_receiver  # Second call returns receiver
        ]

        # Set up mock websocket
        self.mock_websocket = AsyncMock()

        # Add users to online users
        self.server.online_users = {"1": "sender", "2": "receiver"}
        self.server.user_websockets = {"sender": self.mock_websocket, "receiver": self.mock_websocket}

    def tearDown(self):
        """Clean up test environment."""
        self.get_session_patcher.stop()

    @pytest.mark.asyncio
    @patch('src.backend.server.FileTransfer')
    async def test_handle_file_command(self, mock_file_transfer_class):
        """Test handling a file transfer command."""
        # Create test file data
        filename = "test.txt"
        file_content = b"This is a test file content."
        base64_data = base64.b64encode(file_content).decode('utf-8')
        file_data = f"{filename};{base64_data}"

        # Calculate expected hash
        expected_hash = hashlib.sha256(file_content).hexdigest()

        # Create the command
        command = f"/file receiver {file_data}"

        # Call the handle_command method
        with patch.object(self.server, 'notify_user', new_callable=AsyncMock) as mock_notify_user:
            await self.server.handle_command(self.mock_websocket, "sender", command)

        # Check that FileTransfer was created with correct parameters
        mock_file_transfer_class.assert_called_once()
        call_kwargs = mock_file_transfer_class.call_args[1]
        self.assertEqual(call_kwargs['filename'], filename)
        self.assertEqual(call_kwargs['size'], len(file_content))
        self.assertEqual(call_kwargs['sender_id'], self.mock_sender.id)
        self.assertEqual(call_kwargs['receiver_id'], self.mock_receiver.id)
        self.assertEqual(call_kwargs['status'], "completed")
        self.assertEqual(call_kwargs['file_hash'], expected_hash)

        # Check that the file was added to the database
        self.mock_session.add.assert_called_once()
        self.mock_session.commit.assert_called_once()

        # Check that the file was sent to the recipient
        mock_notify_user.assert_called_once()
        recipient, message = mock_notify_user.call_args[0]
        self.assertEqual(recipient, "receiver")

        # Parse the message to check its content
        message_data = json.loads(message)
        self.assertEqual(message_data['type'], "file")
        self.assertEqual(message_data['username'], "sender")
        self.assertEqual(message_data['filename'], filename)
        self.assertEqual(message_data['size'], len(file_content))
        self.assertEqual(message_data['data'], base64_data)
        self.assertEqual(message_data['hash'], expected_hash)

        # Check that confirmation was sent to the sender
        self.mock_websocket.send.assert_called_once()
        response = json.loads(self.mock_websocket.send.call_args[0][0])
        self.assertEqual(response['type'], "command_response")
        self.assertIn(f"File '{filename}'", response['content'])
        self.assertIn("sent to receiver", response['content'])

    @pytest.mark.asyncio
    async def test_handle_file_command_invalid_format(self):
        """Test handling a file command with invalid format."""
        # Create an invalid command (missing file data)
        command = "/file receiver"

        # Call the handle_command method
        await self.server.handle_command(self.mock_websocket, "sender", command)

        # Check that an error response was sent
        self.mock_websocket.send.assert_called_once()
        response = json.loads(self.mock_websocket.send.call_args[0][0])
        self.assertEqual(response['type'], "command_response")
        self.assertIn("Usage:", response['content'])

    @pytest.mark.asyncio
    async def test_handle_file_command_user_offline(self):
        """Test handling a file command when the recipient is offline."""
        # Create a command with an offline recipient
        command = "/file offline_user test.txt;base64data"

        # Call the handle_command method
        await self.server.handle_command(self.mock_websocket, "sender", command)

        # Check that an error response was sent
        self.mock_websocket.send.assert_called_once()
        response = json.loads(self.mock_websocket.send.call_args[0][0])
        self.assertEqual(response['type'], "command_response")
        self.assertIn("not online", response['content'])

    @pytest.mark.asyncio
    async def test_handle_file_command_invalid_base64(self):
        """Test handling a file command with invalid base64 data."""
        # Create a command with invalid base64 data
        command = "/file receiver test.txt;invalid_base64!"

        # Call the handle_command method
        await self.server.handle_command(self.mock_websocket, "sender", command)

        # Check that an error response was sent
        self.mock_websocket.send.assert_called_once()
        response = json.loads(self.mock_websocket.send.call_args[0][0])
        self.assertEqual(response['type'], "command_response")
        self.assertIn("Error:", response['content'])


if __name__ == '__main__':
    unittest.main()
