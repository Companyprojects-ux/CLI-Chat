"""
CLI Chat Server implementation.
"""

import asyncio
import json
import os
import datetime
import logging
import websockets
import click
from typing import Dict, Set, Any, Optional
# Try to import Redis, but make it optional
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("Redis not available. Some features may be limited.")

from src.database import User, Server, Message, Group, get_session, init_db, get_engine
from src.utils.security import hash_password, verify_password, generate_token, verify_token
from src.utils.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("chat_server.log")
    ]
)
logger = logging.getLogger("chat_server")

class ChatServer:
    """Chat server implementation."""

    def __init__(self, port: int, moderator_username: str, config: Config):
        """Initialize the chat server."""
        self.port = port
        self.moderator_username = moderator_username
        self.config = config
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.online_users: Dict[websockets.WebSocketServerProtocol, str] = {}
        self.user_websockets: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.moderator_ws: Optional[websockets.WebSocketServerProtocol] = None
        self.moderator_disconnect_event = asyncio.Event()
        self.db_engine = get_engine(self.config.database_url)
        self.redis_client = None

    async def start(self, with_client: bool = False):
        """Start the chat server."""
        # Initialize database
        init_db(self.db_engine)

        # Initialize Redis connection if available
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host=self.config.redis_host,
                    port=self.config.redis_port,
                    decode_responses=True
                )
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")
                self.redis_client = None
        else:
            self.redis_client = None

        # Register server in database
        session = get_session(self.db_engine)
        try:
            # Check if moderator exists
            moderator = session.query(User).filter_by(username=self.moderator_username).first()
            if not moderator:
                logger.warning(f"Moderator {self.moderator_username} does not exist. Creating...")
                moderator = User(
                    username=self.moderator_username,
                    password_hash=hash_password("temporary_password"),  # This should be changed
                    is_admin=True
                )
                session.add(moderator)
                session.commit()

            # Register server
            server = Server(
                port=self.port,
                moderator=self.moderator_username,
                started=datetime.datetime.now(datetime.timezone.utc),
                active=True
            )
            session.add(server)
            session.commit()
            logger.info(f"Server registered with ID {server.id}")
        finally:
            session.close()

        # Start WebSocket server
        self.server = await websockets.serve(
            lambda websocket: self.handle_client(websocket),
            self.config.host,
            self.port,
            ping_interval=30,
            ping_timeout=10
        )

        logger.info(f"Server started on {self.config.host}:{self.port} with moderator '{self.moderator_username}'")

        # If with_client is True, start a client for the moderator
        if with_client:
            # This would be implemented in a separate client module
            logger.info("Starting moderator client...")
            # For now, just wait for the moderator to disconnect
            await self.moderator_disconnect_event.wait()
        else:
            await self.moderator_disconnect_event.wait()

        # Shutdown server
        await self.shutdown()

    async def shutdown(self):
        """Shutdown the server gracefully."""
        logger.info("Shutting down server...")

        # Notify all clients
        shutdown_data = {
            "type": "notification",
            "username": f"*{self.moderator_username}",
            "content": "Moderator disconnected. Server shutting down."
        }
        await self.notify_all(json.dumps(shutdown_data))

        # Update server status in database
        session = get_session(self.db_engine)
        try:
            server = session.query(Server).filter_by(port=self.port, active=True).first()
            if server:
                server.active = False
                session.commit()
                logger.info(f"Server {server.id} marked as inactive")
        finally:
            session.close()

        # Close Redis connection if available
        if self.redis_client and REDIS_AVAILABLE:
            try:
                await self.redis_client.close()
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")

        # Close WebSocket server
        self.server.close()
        await self.server.wait_closed()
        logger.info("Server has shut down gracefully")

    async def notify_all(self, message: str):
        """Send a message to all connected clients."""
        if not self.clients:
            return

        results = await asyncio.gather(
            *(client.send(message) for client in self.clients),
            return_exceptions=True
        )

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error sending message: {result}")

    async def notify_user(self, username: str, message: str):
        """Send a message to a specific user."""
        if username in self.user_websockets:
            try:
                await self.user_websockets[username].send(message)
                return True
            except Exception as e:
                logger.error(f"Error sending message to {username}: {e}")
        return False

    async def handle_client(self, websocket: websockets.WebSocketServerProtocol):
        """Handle a client connection."""
        self.clients.add(websocket)
        username = None

        try:
            # Authentication
            auth_message = await websocket.recv()
            auth_data = json.loads(auth_message)

            if auth_data.get("type") == "login":
                username = auth_data.get("username")
                password = auth_data.get("password")

                # Validate credentials
                session = get_session(self.db_engine)
                try:
                    user = session.query(User).filter_by(username=username).first()

                    if not user or not verify_password(password, user.password_hash):
                        await websocket.send(json.dumps({
                            "type": "auth_response",
                            "success": False,
                            "message": "Invalid username or password"
                        }))
                        return

                    # Update last login
                    user.last_login = datetime.datetime.now(datetime.timezone.utc)
                    session.commit()

                    # Generate token
                    token = generate_token(user.id, user.username, user.is_admin)

                    await websocket.send(json.dumps({
                        "type": "auth_response",
                        "success": True,
                        "token": token,
                        "username": username,
                        "is_admin": user.is_admin
                    }))

                finally:
                    session.close()

            elif auth_data.get("type") == "token":
                token = auth_data.get("token")
                payload = verify_token(token)

                if not payload:
                    await websocket.send(json.dumps({
                        "type": "auth_response",
                        "success": False,
                        "message": "Invalid or expired token"
                    }))
                    return

                username = payload.get("username")

                # Verify user exists
                session = get_session(self.db_engine)
                try:
                    user = session.query(User).filter_by(username=username).first()

                    if not user:
                        await websocket.send(json.dumps({
                            "type": "auth_response",
                            "success": False,
                            "message": "User not found"
                        }))
                        return

                    # Update last login
                    user.last_login = datetime.datetime.now(datetime.timezone.utc)
                    session.commit()

                    await websocket.send(json.dumps({
                        "type": "auth_response",
                        "success": True,
                        "username": username,
                        "is_admin": user.is_admin
                    }))

                finally:
                    session.close()
            else:
                await websocket.send(json.dumps({
                    "type": "auth_response",
                    "success": False,
                    "message": "Invalid authentication method"
                }))
                return

            # Register user as online
            self.online_users[websocket] = username
            self.user_websockets[username] = websocket

            # Set moderator websocket if this is the moderator
            if username == self.moderator_username and self.moderator_ws is None:
                self.moderator_ws = websocket

            # Send message history
            await self.send_message_history(websocket)

            # Broadcast join notification
            display_username = username
            if username == self.moderator_username:
                display_username = f"*{username}"

            join_data = {
                "type": "notification",
                "username": display_username,
                "content": "joined the chat."
            }

            # Save join message
            session = get_session(self.db_engine)
            try:
                user = session.query(User).filter_by(username=username).first()
                message = Message(
                    user_id=user.id,
                    content="joined the chat.",
                    type="join"
                )
                session.add(message)
                session.commit()
            finally:
                session.close()

            await self.notify_all(json.dumps(join_data))

            # Handle messages
            async for message in websocket:
                await self.process_message(websocket, username, message)

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed by client: {username}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            # Clean up
            self.clients.discard(websocket)

            if websocket in self.online_users:
                username = self.online_users.pop(websocket)
                if username in self.user_websockets:
                    del self.user_websockets[username]

                # Broadcast leave notification
                display_username = username
                if username == self.moderator_username:
                    display_username = f"*{username}"

                leave_data = {
                    "type": "notification",
                    "username": display_username,
                    "content": "left the chat."
                }

                # Save leave message
                session = get_session(self.db_engine)
                try:
                    user = session.query(User).filter_by(username=username).first()
                    if user:
                        message = Message(
                            user_id=user.id,
                            content="left the chat.",
                            type="leave"
                        )
                        session.add(message)
                        session.commit()
                finally:
                    session.close()

                await self.notify_all(json.dumps(leave_data))

            # If this was the moderator, trigger shutdown
            if websocket == self.moderator_ws:
                self.moderator_ws = None
                self.moderator_disconnect_event.set()

    async def send_message_history(self, websocket: websockets.WebSocketServerProtocol):
        """Send message history to a client."""
        session = get_session(self.db_engine)
        try:
            # Get last 100 messages
            messages = session.query(Message).filter(
                Message.type.in_(["chat", "notification"])
            ).order_by(Message.timestamp.desc()).limit(100).all()

            # Reverse to get chronological order
            messages.reverse()

            for msg in messages:
                user = session.query(User).filter_by(id=msg.user_id).first()
                if not user:
                    continue

                display_username = user.username
                if user.username == self.moderator_username:
                    display_username = f"*{user.username}"

                data = {
                    "type": msg.type,
                    "username": display_username,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                }

                await websocket.send(json.dumps(data))

        finally:
            session.close()

    async def process_message(self, websocket: websockets.WebSocketServerProtocol, username: str, message: str):
        """Process a message from a client."""
        # Check if it's a command
        if message.startswith("/"):
            await self.handle_command(websocket, username, message)
            return

        # Regular chat message
        display_username = username
        if username == self.moderator_username:
            display_username = f"*{username}"

        data = {
            "type": "chat",
            "username": display_username,
            "content": message,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        # Save message to database
        session = get_session(self.db_engine)
        try:
            user = session.query(User).filter_by(username=username).first()
            msg = Message(
                user_id=user.id,
                content=message,
                type="chat"
            )
            session.add(msg)
            session.commit()
        finally:
            session.close()

        # Broadcast message
        await self.notify_all(json.dumps(data))

    async def handle_command(self, websocket: websockets.WebSocketServerProtocol, username: str, command: str):
        """Handle a command from a client."""
        cmd = command.strip().lower()

        if cmd == "/users":
            user_list = ", ".join(self.online_users.values())
            response = {
                "type": "command_response",
                "content": f"Online users: {user_list}"
            }
            await websocket.send(json.dumps(response))

        elif cmd == "/clear":
            # Only moderator can clear chat
            if username == self.moderator_username:
                clear_point = datetime.datetime.now(datetime.timezone.utc)

                # Clear messages in database
                session = get_session(self.db_engine)
                try:
                    session.query(Message).filter(
                        Message.timestamp < clear_point,
                        Message.type.in_(["chat", "notification"])
                    ).delete(synchronize_session=False)

                    # Add clear notification
                    user = session.query(User).filter_by(username=username).first()
                    msg = Message(
                        user_id=user.id,
                        content="cleared the chat history.",
                        type="clear"
                    )
                    session.add(msg)
                    session.commit()
                finally:
                    session.close()

                # Notify all clients
                notification = {
                    "type": "notification",
                    "username": f"*{self.moderator_username}",
                    "content": "cleared the chat history."
                }
                await self.notify_all(json.dumps(notification))
            else:
                await websocket.send(json.dumps({
                    "type": "command_response",
                    "content": "Permission denied. Only moderators can clear chat history."
                }))

        elif cmd in ["/quit", "/exit"]:
            await websocket.send(json.dumps({
                "type": "command_response",
                "content": "Disconnecting..."
            }))
            await websocket.close()

        elif cmd.startswith("/whisper ") or cmd.startswith("/w "):
            # Private message
            parts = cmd.split(" ", 2)
            if len(parts) < 3:
                await websocket.send(json.dumps({
                    "type": "command_response",
                    "content": "Usage: /whisper <username> <message> or /w <username> <message>"
                }))
                return

            target_username = parts[1]
            private_message = parts[2]

            if target_username not in self.user_websockets:
                await websocket.send(json.dumps({
                    "type": "command_response",
                    "content": f"User {target_username} is not online."
                }))
                return

            # Send to recipient
            whisper_data = {
                "type": "whisper",
                "username": username,
                "content": private_message,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }

            await self.notify_user(target_username, json.dumps(whisper_data))

            # Send confirmation to sender
            await websocket.send(json.dumps({
                "type": "command_response",
                "content": f"Whisper sent to {target_username}"
            }))

        elif cmd.startswith("/file "):
            # File transfer
            parts = cmd.split(" ", 2)
            if len(parts) < 3:
                await websocket.send(json.dumps({
                    "type": "command_response",
                    "content": "Usage: /file <username> <base64_encoded_file>"
                }))
                return

            target_username = parts[1]
            file_data = parts[2]

            # Check if the target user is online
            if target_username not in self.user_websockets:
                await websocket.send(json.dumps({
                    "type": "command_response",
                    "content": f"User {target_username} is not online."
                }))
                return

            try:
                # Parse the file data (format: filename;base64data)
                file_parts = file_data.split(";", 1)
                if len(file_parts) != 2:
                    raise ValueError("Invalid file format")

                filename = file_parts[0]
                base64_data = file_parts[1]

                # Validate base64 data
                import base64
                try:
                    decoded_data = base64.b64decode(base64_data)
                    file_size = len(decoded_data)
                except Exception:
                    raise ValueError("Invalid base64 data")

                # Check file size (limit to 10MB)
                if file_size > 10 * 1024 * 1024:  # 10MB
                    await websocket.send(json.dumps({
                        "type": "command_response",
                        "content": "File too large. Maximum size is 10MB."
                    }))
                    return

                # Create file transfer record in database
                session = get_session(self.db_engine)
                try:
                    sender = session.query(User).filter_by(username=username).first()
                    receiver = session.query(User).filter_by(username=target_username).first()

                    if not sender or not receiver:
                        raise ValueError("User not found")

                    # Calculate file hash for integrity
                    import hashlib
                    file_hash = hashlib.sha256(decoded_data).hexdigest()

                    # Create file transfer record
                    from src.database.models import FileTransfer
                    file_transfer = FileTransfer(
                        filename=filename,
                        size=file_size,
                        sender_id=sender.id,
                        receiver_id=receiver.id,
                        status="completed",
                        file_hash=file_hash
                    )
                    session.add(file_transfer)
                    session.commit()

                    # Send file to recipient
                    file_transfer_data = {
                        "type": "file",
                        "username": username,
                        "filename": filename,
                        "size": file_size,
                        "data": base64_data,
                        "hash": file_hash,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }

                    await self.notify_user(target_username, json.dumps(file_transfer_data))

                    # Send confirmation to sender
                    await websocket.send(json.dumps({
                        "type": "command_response",
                        "content": f"File '{filename}' ({file_size} bytes) sent to {target_username}"
                    }))

                finally:
                    session.close()

            except ValueError as e:
                await websocket.send(json.dumps({
                    "type": "command_response",
                    "content": f"Error: {str(e)}"
                }))
            except Exception as e:
                logger.error(f"Error processing file transfer: {e}")
                await websocket.send(json.dumps({
                    "type": "command_response",
                    "content": "An error occurred while processing the file transfer."
                }))

        else:
            await websocket.send(json.dumps({
                "type": "command_response",
                "content": "Unknown command. Available commands: /users, /whisper, /w, /file, /clear, /quit, /exit"
            }))

@click.command()
@click.option("--port", default=8000, help="Port to run the server on")
@click.option("--moderator", required=True, help="Moderator username")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--db-url", help="Database URL")
@click.option("--redis-host", default="localhost", help="Redis host")
@click.option("--redis-port", default=6379, help="Redis port")
def main(port, moderator, host, db_url, redis_host, redis_port):
    """Start the chat server."""
    # Load configuration
    config = Config(
        host=host,
        database_url=db_url,
        redis_host=redis_host,
        redis_port=redis_port
    )

    # Create and start server
    server = ChatServer(port, moderator, config)

    try:
        asyncio.run(server.start(with_client=False))
    except KeyboardInterrupt:
        logger.info("Server shutting down due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    main()
