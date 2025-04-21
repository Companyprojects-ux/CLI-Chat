"""
CLI Chat Client implementation.
"""

import asyncio
import json
import os
import sys
import datetime
import click
import websockets
from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style

from src.utils.config import Config

# Try to import encryption module, but make it optional
try:
    from src.utils.encryption import EncryptionManager
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    print("Encryption module not available. End-to-end encryption will be disabled.")

class ChatClient:
    """Chat client implementation."""

    def __init__(self, server_host: str, server_port: int, username: str, config: Config):
        """Initialize the chat client."""
        self.server_host = server_host
        self.server_port = server_port
        self.username = username
        self.config = config
        self.token: Optional[str] = None
        self.console = Console()
        self.prompt_style = Style.from_dict({
            'username': '#00aa00 bold',
            'at': '#999999',
            'server': '#0000aa',
            'colon': '#999999',
            'pound': '#aa0000',
        })
        self.command_completer = WordCompleter([
            '/users', '/whisper', '/w', '/quit', '/exit', '/help', '/clear',
            '/file', '/encrypt', '/keygen', '/sendkey'
        ])
        self.history = InMemoryHistory()
        self.prompt_session = PromptSession(history=self.history)
        self.online_users = set()

        # Initialize encryption if available
        self.encryption_manager = None
        self.encryption_enabled = False
        if ENCRYPTION_AVAILABLE:
            try:
                self.encryption_manager = EncryptionManager()
                # Load or generate keys
                self.encryption_manager.load_or_generate_keypair(self.username)
                self.console.print("[green]End-to-end encryption is available.[/green]")
                self.console.print("[yellow]Use /encrypt <username> to enable encryption for a user.[/yellow]")
                self.encryption_enabled = True
            except Exception as e:
                self.console.print(f"[red]Error initializing encryption: {e}[/red]")
                self.encryption_manager = None
                self.encryption_enabled = False

    async def connect(self):
        """Connect to the chat server."""
        uri = f"ws://{self.server_host}:{self.server_port}"

        try:
            async with websockets.connect(uri) as websocket:
                # Authenticate
                if not await self.authenticate(websocket):
                    return

                # Start message handling
                receive_task = asyncio.create_task(self.receive_messages(websocket))
                send_task = asyncio.create_task(self.send_messages(websocket))

                # Wait for either task to complete
                done, pending = await asyncio.wait(
                    [receive_task, send_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()

        except ConnectionRefusedError:
            self.console.print("[bold red]Failed to connect to the server.[/bold red]")
        except websockets.exceptions.InvalidStatusCode as e:
            self.console.print(f"[bold red]Connection error: {e}[/bold red]")
        except KeyboardInterrupt:
            self.console.print("[yellow]Disconnected.[/yellow]")

    async def authenticate(self, websocket: websockets.WebSocketClientProtocol) -> bool:
        """Authenticate with the server."""
        # Check if we have a saved token
        token_file = os.path.join(os.path.expanduser("~"), f".cli_chat_token_{self.username}")

        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    self.token = f.read().strip()

                # Try to authenticate with token
                auth_data = {
                    "type": "token",
                    "token": self.token
                }

                await websocket.send(json.dumps(auth_data))
                response = await websocket.recv()
                auth_response = json.loads(response)

                if auth_response.get("success"):
                    self.console.print(f"[green]Authenticated as {auth_response.get('username')}[/green]")
                    return True
                else:
                    # Token invalid, remove it
                    os.remove(token_file)
                    self.token = None
            except Exception as e:
                self.console.print(f"[yellow]Error reading token: {e}[/yellow]")
                self.token = None

        # If no token or token invalid, prompt for password
        password = Prompt.ask(f"Enter password for {self.username}", password=True)

        auth_data = {
            "type": "login",
            "username": self.username,
            "password": password
        }

        await websocket.send(json.dumps(auth_data))
        response = await websocket.recv()
        auth_response = json.loads(response)

        if auth_response.get("success"):
            self.console.print(f"[green]Authenticated as {auth_response.get('username')}[/green]")

            # Save token for future use
            self.token = auth_response.get("token")
            if self.token:
                try:
                    with open(token_file, 'w') as f:
                        f.write(self.token)
                except Exception as e:
                    self.console.print(f"[yellow]Error saving token: {e}[/yellow]")

            return True
        else:
            self.console.print(f"[bold red]Authentication failed: {auth_response.get('message')}[/bold red]")
            return False

    async def receive_messages(self, websocket: websockets.WebSocketClientProtocol):
        """Receive and display messages from the server."""
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.display_message(data)
                except json.JSONDecodeError:
                    self.console.print(f"[red]Invalid message format: {message}[/red]")
        except websockets.exceptions.ConnectionClosed:
            self.console.print("[bold red]Connection closed by server.[/bold red]")

    async def send_messages(self, websocket: websockets.WebSocketClientProtocol):
        """Send messages to the server."""
        self.console.print("[bold green]Type your message or command (/help for available commands)[/bold green]")

        while True:
            try:
                # Create a custom prompt with username and server info
                prompt_text = [
                    ('class:username', self.username),
                    ('class:at', '@'),
                    ('class:server', f"{self.server_host}:{self.server_port}"),
                    ('class:colon', ':'),
                    ('class:pound', '> ')
                ]

                # Get user input with command completion
                message = await self.prompt_session.prompt_async(
                    prompt_text,
                    style=self.prompt_style,
                    completer=self.command_completer
                )

                if not message.strip():
                    continue

                # Handle local commands
                if message.lower() == "/help":
                    self.show_help()
                    continue

                # Handle encryption commands
                if self.encryption_enabled and message.startswith("/keygen"):
                    try:
                        private_pem, public_pem = self.encryption_manager.generate_keypair()
                        self.console.print("[green]New encryption keys generated.[/green]")
                        continue
                    except Exception as e:
                        self.console.print(f"[bold red]Error generating keys: {e}[/bold red]")
                        continue

                if self.encryption_enabled and message.startswith("/sendkey "):
                    parts = message.split(" ", 1)
                    if len(parts) < 2:
                        self.console.print("[yellow]Usage: /sendkey <username>[/yellow]")
                        continue

                    target_username = parts[1]

                    try:
                        # Get public key as bytes
                        public_key_bytes = self.encryption_manager.get_public_key_bytes()
                        if not public_key_bytes:
                            self.console.print("[bold red]No encryption keys available. Use /keygen first.[/bold red]")
                            continue

                        # Convert to string directly (already in PEM format)
                        # Make sure the PEM format is preserved correctly
                        public_key_str = public_key_bytes.decode('utf-8')

                        # Debug output
                        self.console.print(f"[dim]Sending key: {public_key_str[:50]}...[/dim]")

                        # Format key message
                        key_message = f"/pubkey {public_key_str}"

                        # Send as a whisper
                        whisper_cmd = f"/whisper {target_username} {key_message}"
                        await websocket.send(whisper_cmd)

                        self.console.print(f"[green]Public key sent to {target_username}.[/green]")
                    except Exception as e:
                        self.console.print(f"[bold red]Error sending public key: {e}[/bold red]")

                    continue

                if self.encryption_enabled and message.startswith("/encrypt "):
                    parts = message.split(" ", 1)
                    if len(parts) < 2:
                        self.console.print("[yellow]Usage: /encrypt <username>[/yellow]")
                        continue

                    target_username = parts[1]

                    # Check if we have the user's public key
                    if self.encryption_manager.load_peer_key(target_username):
                        self.console.print(f"[green]End-to-end encryption enabled for {target_username}.[/green]")
                    else:
                        self.console.print(f"[yellow]No public key found for {target_username}. Use /sendkey to request their key first.[/yellow]")

                    continue

                # Handle file sending
                if message.startswith("/file "):
                    parts = message.split(" ", 2)
                    if len(parts) < 3:
                        self.console.print("[yellow]Usage: /file <username> <filepath>[/yellow]")
                        continue

                    target_username = parts[1]
                    file_path = parts[2]

                    # Check if file exists
                    if not os.path.isfile(file_path):
                        self.console.print(f"[bold red]Error: File '{file_path}' not found.[/bold red]")
                        continue

                    # Check file size
                    file_size = os.path.getsize(file_path)
                    if file_size > 10 * 1024 * 1024:  # 10MB
                        self.console.print("[bold red]Error: File too large. Maximum size is 10MB.[/bold red]")
                        continue

                    try:
                        # Read file
                        with open(file_path, "rb") as f:
                            file_data = f.read()

                        # Get filename
                        filename = os.path.basename(file_path)

                        # Encode file data as base64
                        import base64
                        base64_data = base64.b64encode(file_data).decode("utf-8")

                        # Format message: /file <username> <filename>;<base64data>
                        file_message = f"/file {target_username} {filename};{base64_data}"

                        # Send file
                        self.console.print(f"[yellow]Sending file '{filename}' to {target_username}...[/yellow]")
                        await websocket.send(file_message)
                        continue

                    except Exception as e:
                        self.console.print(f"[bold red]Error sending file: {e}[/bold red]")
                        continue



                # Handle encrypted whispers
                if self.encryption_enabled and message.startswith("/whisper ") or message.startswith("/w "):
                    parts = message.split(" ", 2)
                    if len(parts) >= 3:
                        cmd = parts[0]
                        target_username = parts[1]
                        content = parts[2]

                        # Check if this is a public key message
                        if content.startswith("/pubkey "):
                            # Don't encrypt key exchange messages
                            await websocket.send(message)
                            continue

                        # Check if we have the user's public key and should encrypt
                        if self.encryption_manager.load_peer_key(target_username):
                            try:
                                # Encrypt the message
                                encrypted_content = self.encryption_manager.encrypt_message(content, target_username)
                                if encrypted_content:
                                    # Format as encrypted whisper
                                    encrypted_message = f"{cmd} {target_username} [ENCRYPTED]{encrypted_content}"
                                    await websocket.send(encrypted_message)
                                    continue
                            except Exception as e:
                                self.console.print(f"[bold red]Error encrypting message: {e}[/bold red]")
                                # Fall back to unencrypted message

                # We don't need to process /pubkey messages here as they're handled in the display_message method
                # This section was causing conflicts with the whisper handling

                # Send message to server
                await websocket.send(message)

                # Handle quit command
                if message.lower() in ["/quit", "/exit"]:
                    await websocket.close()
                    break

            except KeyboardInterrupt:
                await websocket.close()
                break
            except Exception as e:
                self.console.print(f"[red]Error sending message: {e}[/red]")

    async def display_message(self, data: Dict[str, Any]):
        """Display a message from the server."""
        message_type = data.get("type", "unknown")

        if message_type == "chat":
            username = data.get("username", "Unknown")
            content = data.get("content", "")
            timestamp = data.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat())

            # Parse timestamp
            try:
                dt = datetime.datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%H:%M:%S")
            except (ValueError, TypeError):
                time_str = "??:??:??"

            # Format message
            if username.startswith("*"):  # Moderator
                username_text = Text(username, style="bold red")
            elif username == self.username:
                username_text = Text(username, style="bold green")
            else:
                username_text = Text(username, style="bold blue")

            message_text = Text()
            message_text.append(f"[{time_str}] ", style="dim")
            message_text.append(username_text)
            message_text.append(": ")
            message_text.append(content)

            self.console.print(message_text)

        elif message_type == "whisper":
            username = data.get("username", "Unknown")
            content = data.get("content", "")

            # Store the username for key exchange
            self.last_whisper_from = username

            # Check if this is an encrypted message
            if self.encryption_enabled and content.startswith("[ENCRYPTED]"):
                try:
                    # Extract the encrypted content
                    encrypted_content = content[11:]  # Remove [ENCRYPTED] prefix

                    # Decrypt the message
                    decrypted_content = self.encryption_manager.decrypt_message(encrypted_content)

                    if decrypted_content:
                        # Display decrypted message
                        message_text = Text()
                        message_text.append("[Whisper] ", style="bold magenta")
                        message_text.append(username, style="bold magenta")
                        message_text.append(" ")
                        message_text.append("🔒", style="bold green")  # Lock emoji to indicate encryption
                        message_text.append(": ")
                        message_text.append(decrypted_content)

                        self.console.print(message_text)
                        return
                    else:
                        # Decryption failed
                        self.console.print(f"[bold red]Failed to decrypt message from {username}.[/bold red]")
                        return
                except Exception as e:
                    self.console.print(f"[bold red]Error decrypting message: {e}[/bold red]")
                    return

            # Handle public key exchange
            if content.startswith("/pubkey "):
                try:
                    parts = content.split(" ", 1)
                    if len(parts) >= 2:
                        public_key_str = parts[1]
                        import base64

                        # The key is already in PEM format
                        public_key_pem = public_key_str.encode('utf-8')

                        # Debug output to help diagnose issues
                        self.console.print(f"[dim]Received key length: {len(public_key_pem)} bytes[/dim]")

                        # Store the public key
                        self.encryption_manager.add_peer_key(username, public_key_pem)

                        message_text = Text()
                        message_text.append("[System] ", style="bold cyan")
                        message_text.append(f"Received public key from {username}. ", style="cyan")
                        message_text.append(f"You can now use /encrypt {username} to enable encryption.", style="cyan")

                        self.console.print(message_text)
                        return
                except Exception as e:
                    self.console.print(f"[bold red]Error processing public key: {e}[/bold red]")
                    self.console.print(f"[dim]Error details: {str(e)}[/dim]")
                    return

            # Regular unencrypted whisper
            message_text = Text()
            message_text.append("[Whisper] ", style="bold magenta")
            message_text.append(username, style="bold magenta")
            message_text.append(": ")
            message_text.append(content)

            self.console.print(message_text)

        elif message_type == "file":
            username = data.get("username", "Unknown")
            filename = data.get("filename", "unknown_file")
            size = data.get("size", 0)
            file_hash = data.get("hash", "")
            base64_data = data.get("data", "")

            # Format file message
            message_text = Text()
            message_text.append("[File] ", style="bold cyan")
            message_text.append(username, style="bold cyan")
            message_text.append(" sent you a file: ")
            message_text.append(filename, style="bold")
            message_text.append(f" ({size} bytes)")

            self.console.print(message_text)

            # Ask if user wants to save the file
            save = Prompt.ask("Save file?", choices=["y", "n"], default="y")

            if save.lower() == "y":
                try:
                    # Create downloads directory if it doesn't exist
                    downloads_dir = os.path.join(os.path.expanduser("~"), "cli_chat_downloads")
                    os.makedirs(downloads_dir, exist_ok=True)

                    # Save file
                    file_path = os.path.join(downloads_dir, filename)

                    # Decode base64 data
                    import base64
                    decoded_data = base64.b64decode(base64_data)

                    # Verify file integrity
                    import hashlib
                    computed_hash = hashlib.sha256(decoded_data).hexdigest()

                    if computed_hash != file_hash:
                        self.console.print("[bold red]Warning: File integrity check failed![/bold red]")
                        verify = Prompt.ask("Save anyway?", choices=["y", "n"], default="n")
                        if verify.lower() != "y":
                            self.console.print("[yellow]File not saved.[/yellow]")
                            return

                    # Write file
                    with open(file_path, "wb") as f:
                        f.write(decoded_data)

                    self.console.print(f"[green]File saved to {file_path}[/green]")

                except Exception as e:
                    self.console.print(f"[bold red]Error saving file: {e}[/bold red]")
            else:
                self.console.print("[yellow]File not saved.[/yellow]")

        elif message_type == "notification":
            username = data.get("username", "")
            content = data.get("content", "")

            if username:
                if username.startswith("*"):  # Moderator
                    username_style = "bold red"
                else:
                    username_style = "bold yellow"

                message_text = Text()
                message_text.append(username, style=username_style)
                message_text.append(" ")
                message_text.append(content, style="yellow")

                self.console.print(message_text)
            else:
                self.console.print(Text(content, style="yellow"))

        elif message_type == "command_response":
            content = data.get("content", "")
            self.console.print(Text(content, style="cyan"))

            # Update online users list if this is a response to /users command
            if "Online users:" in content:
                users_str = content.replace("Online users:", "").strip()
                self.online_users = set(u.strip() for u in users_str.split(","))

        elif message_type == "auth_response":
            # Already handled in authenticate method
            pass

        else:
            self.console.print(f"[dim]{data}[/dim]")

    def show_help(self):
        """Show help information."""
        help_text = """
Available commands:
/users - Show online users
/whisper <username> <message> - Send a private message
/w <username> <message> - Short form of whisper
/file <username> <filepath> - Send a file to a user
/clear - Clear chat history (moderators only)
/quit or /exit - Disconnect from the server
/help - Show this help message
"""

        # Add encryption commands if available
        if self.encryption_enabled:
            encryption_text = """

Encryption Commands:
/keygen - Generate new encryption keys
/sendkey <username> - Send your public key to a user
/encrypt <username> - Enable end-to-end encryption with a user
"""
            help_text += encryption_text
        self.console.print(Panel(help_text, title="CLI Chat Help", border_style="green"))

@click.command()
@click.option("--host", default="localhost", help="Server host")
@click.option("--port", default=8000, help="Server port")
@click.option("--username", required=True, help="Your username")
def main(host, port, username):
    """Start the chat client."""
    # Load configuration
    config = Config()

    # Create and start client
    client = ChatClient(host, port, username, config)

    try:
        asyncio.run(client.connect())
    except KeyboardInterrupt:
        click.echo("Client disconnected.")
    except Exception as e:
        click.echo(f"Client error: {e}")

if __name__ == "__main__":
    main()
