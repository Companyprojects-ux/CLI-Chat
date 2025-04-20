"""
Broadcast CLI Chat

"""

import asyncio
import click
import websockets
import asyncpg
import json
import os
import sys
import datetime
import colorama
from colorama import Fore, Style

# ---------------------------
# OptionsManager
# ---------------------------
class OptionsManager:
    DEFAULT_OPTIONS = {
        "username_color": "green",
        "own_message_color": "blue",
        "other_message_color": "magenta",
    }
    
    def __init__(self, options_file=None):
        self.options_file = options_file or os.path.join(os.path.expanduser("~"), ".broadcast_server_options.json")
    
    def load(self):
        if os.path.exists(self.options_file):
            try:
                with open(self.options_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                click.echo(f"Error loading options: {e}")
                return self.DEFAULT_OPTIONS.copy()
        else:
            return self.DEFAULT_OPTIONS.copy()
    
    def save(self, options):
        try:
            directory = os.path.dirname(self.options_file)
            if not os.path.exists(directory):
                os.makedirs(directory)
            with open(self.options_file, "w") as f:
                json.dump(options, f, indent=4)
                f.flush()
            click.echo(f"Options saved to {self.options_file}")
        except Exception as e:
            click.echo(f"Error saving options: {e}")

# ---------------------------
# DatabaseManager
# ---------------------------
class DatabaseManager:
    def __init__(self, dsn=None):
        self.dsn = dsn or os.getenv("BROADCAST_DB_DSN", "postgresql://postgres:guest@localhost:5432/broadcast_chat") # configure database to connect: postgresql://{username}:{password}@localhost:{port}/broadcast_chat
    
    async def init_db(self):
        conn = await asyncpg.connect(self.dsn)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS servers (
                id SERIAL PRIMARY KEY,
                port INTEGER,
                moderator TEXT,
                started TIMESTAMPTZ,
                active BOOLEAN
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                username TEXT,
                content TEXT,
                timestamp TIMESTAMPTZ,
                type TEXT
            )
        ''')
        await conn.close()
    
    async def register_server(self, port, moderator):
        conn = await asyncpg.connect(self.dsn)
        utc_now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        await conn.execute('''
            INSERT INTO servers (port, moderator, started, active)
            VALUES ($1, $2, $3, $4)
        ''', port, moderator, utc_now, True)
        await conn.close()
    
    async def unregister_server(self, port):
        conn = await asyncpg.connect(self.dsn)
        await conn.execute('''
            UPDATE servers SET active = false WHERE port = $1
        ''', port)
        await conn.close()
    
    async def get_active_servers(self):
        conn = await asyncpg.connect(self.dsn)
        rows = await conn.fetch('''
            SELECT port, moderator FROM servers WHERE active = true
        ''')
        await conn.close()
        return rows
    
    async def save_message(self, username, content, msg_type="chat"):
        conn = await asyncpg.connect(self.dsn)
        utc_now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        await conn.execute('''
            INSERT INTO messages (username, content, timestamp, type)
            VALUES ($1, $2, $3, $4)
        ''', username, content, utc_now, msg_type)
        await conn.close()
    
    async def get_last_messages(self, limit=100):
        conn = await asyncpg.connect(self.dsn)
        rows = await conn.fetch('''
            SELECT username, content, timestamp, type FROM messages 
            ORDER BY id DESC LIMIT $1
        ''', limit)
        await conn.close()
        return rows[::-1]
    
    async def clear_history(self, clear_time):
        conn = await asyncpg.connect(self.dsn)
        await conn.execute("DELETE FROM messages WHERE timestamp < $1", clear_time)
        await conn.close()

# ---------------------------
# BroadcastServer
# ---------------------------
class BroadcastServer:
    def __init__(self, port, moderator, db_manager: DatabaseManager):
        self.port = port
        self.moderator = moderator
        self.db = db_manager
        self.clients = set()
        self.online_users = {}
        self.moderator_ws = None
        self.moderator_disconnect_event = asyncio.Event()
    
    async def start(self, with_client=False):
        await self.db.init_db()
        await self.db.register_server(self.port, self.moderator)
        self.server = await websockets.serve(self.handle_client, "localhost", self.port)
        click.echo(f"Server started on port {self.port} with moderator '{self.moderator}'.")
        
        if with_client:
            moderator_client_task = asyncio.create_task(BroadcastClient(self.port, self.moderator, OptionsManager()).connect())
            disconnect_wait_task = asyncio.create_task(self.moderator_disconnect_event.wait())
            done, pending = await asyncio.wait(
                [disconnect_wait_task, moderator_client_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            self.moderator_disconnect_event.set()
            for task in pending:
                task.cancel()
        else:
            await self.moderator_disconnect_event.wait()
        
        shutdown_data = {
            "type": "notification",
            "username": "*" + self.moderator,
            "content": "Moderator disconnected. Server shutting down."
        }
        await self.notify_all(json.dumps(shutdown_data))
        await self.db.unregister_server(self.port)
        self.server.close()
        await self.server.wait_closed()
        click.echo("Server has shut down gracefully.")
    
    async def notify_all(self, message):
        if self.clients:
            results = await asyncio.gather(*(client.send(message) for client in self.clients), return_exceptions=True)
            for result in results:
                if isinstance(result, websockets.exceptions.ConnectionClosed):
                    pass
                elif isinstance(result, Exception):
                    click.echo(f"Error sending message: {result}")
    
    async def handle_client(self, websocket, path):
        self.clients.add(websocket)
        try:
            username = await websocket.recv()
            self.online_users[websocket] = username
            if username == self.moderator and self.moderator_ws is None:
                self.moderator_ws = websocket
            
            # Send history: skip messages of type join, leave, clear and empty content.
            last_messages = await self.db.get_last_messages(100)
            for msg in last_messages:
                if msg["type"] in ["join", "leave", "clear"]:
                    continue
                if not msg["content"].strip():
                    continue
                display_username = msg["username"]
                if msg["username"] == self.moderator:
                    display_username = "*" + msg["username"]
                data = {
                    "type": msg["type"],
                    "username": display_username,
                    "content": msg["content"]
                }
                await websocket.send(json.dumps(data))
            
            # Broadcast live join notification.
            display_username = username if username != self.moderator else "*" + username
            join_data = {
                "type": "notification",
                "username": display_username,
                "content": "joined the lodge."
            }
            await self.db.save_message(username, "joined the lodge.", "join")
            await self.notify_all(json.dumps(join_data))
            
            async for message in websocket:
                if message.startswith("/"):
                    cmd = message.strip().lower()
                    if cmd == "/users":
                        user_list = ", ".join(self.online_users.values())
                        response = {
                            "type": "command_response",
                            "content": f"Online users: {user_list}"
                        }
                        await websocket.send(json.dumps(response))
                    elif cmd == "/clear":
                        if username == self.moderator:
                            clear_point = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                            await self.db.clear_history(clear_point)
                            await self.db.save_message(username, "cleared the chat history.", "clear")
                            notification = {
                                "type": "notification",
                                "username": "*" + self.moderator,
                                "content": "cleared the chat history."
                            }
                            await self.notify_all(json.dumps(notification))
                        else:
                            await websocket.send(json.dumps({
                                "type": "command_response",
                                "content": "Permission denied."
                            }))
                    elif cmd in ["/quit", "/quite"]:
                        await websocket.send(json.dumps({
                            "type": "command_response",
                            "content": "Disconnecting..."
                        }))
                        break
                    else:
                        await websocket.send(json.dumps({
                            "type": "command_response",
                            "content": "Unknown command."
                        }))
                else:
                    display_username = username if username != self.moderator else "*" + username
                    data = {
                        "type": "chat",
                        "username": display_username,
                        "content": message
                    }
                    await self.db.save_message(username, message, "chat")
                    await self.notify_all(json.dumps(data))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            if websocket in self.online_users:
                user = self.online_users.pop(websocket)
                display_username = user if user != self.moderator else "*" + user
                leave_data = {
                    "type": "notification",
                    "username": display_username,
                    "content": "left the lodge."
                }
                await self.db.save_message(user, "left the lodge.", "leave")
                await self.notify_all(json.dumps(leave_data))
            if websocket == self.moderator_ws:
                self.moderator_disconnect_event.set()

# ---------------------------
# BroadcastClient
# ---------------------------
class BroadcastClient:
    def __init__(self, server_port, username, options_manager: OptionsManager):
        self.server_port = server_port
        self.username = username
        self.options_manager = options_manager
        self.options = options_manager.load()
        self.color_map = {
            "black": Fore.BLACK,
            "red": Fore.RED,
            "green": Fore.GREEN,
            "yellow": Fore.YELLOW,
            "blue": Fore.BLUE,
            "magenta": Fore.MAGENTA,
            "cyan": Fore.CYAN,
            "white": Fore.WHITE,         
            # Bright colors
            "bright_black": Fore.LIGHTBLACK_EX,
            "bright_red": Fore.LIGHTRED_EX,
            "bright_green": Fore.LIGHTGREEN_EX,
            "bright_yellow": Fore.LIGHTYELLOW_EX,
            "bright_blue": Fore.LIGHTBLUE_EX,
            "bright_magenta": Fore.LIGHTMAGENTA_EX,
            "bright_cyan": Fore.LIGHTCYAN_EX,
            "bright_white": Fore.LIGHTWHITE_EX,
        }
    
    async def connect(self):
        uri = f"ws://localhost:{self.server_port}"
        try:
            async with websockets.connect(uri) as websocket:
                await websocket.send(self.username)
                receive_task = asyncio.create_task(self.receive_messages(websocket))
                send_task = asyncio.create_task(self.send_messages(websocket))
                done, pending = await asyncio.wait(
                    [receive_task, send_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
        except ConnectionRefusedError:
            click.echo("Failed to connect to the server.")
        except KeyboardInterrupt:
            click.echo("Disconnected.")
    
    async def receive_messages(self, websocket):
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    click.echo(message)
                    continue
                if not data.get("content", "").strip():
                    continue
                click.echo("------------------------")
                line = ""
                if data["type"] == "chat":
                    line = f"{data['username']}{Style.RESET_ALL}: "
                    if data["username"].lstrip("*") == self.username:
                        line += f"{self.color_map.get(self.options.get('own_message_color', 'blue'), Fore.BLUE)}{data['content']}{Style.RESET_ALL}"
                    else:
                        line += f"{self.color_map.get(self.options.get('other_message_color', 'magenta'), Fore.MAGENTA)}{data['content']}{Style.RESET_ALL}"
                elif data["type"] == "notification":
                    line = f"{self.color_map.get('yellow', Fore.YELLOW)}{data['username']} {data['content']}{Style.RESET_ALL}"
                elif data["type"] == "command_response":
                    line = f"{self.color_map.get('cyan', Fore.CYAN)}{data['content']}{Style.RESET_ALL}"
                click.echo(line)
                click.echo("------------------------")
        except websockets.exceptions.ConnectionClosed:
            click.echo("Connection closed by server.")
    
    async def send_messages(self, websocket):
        loop = asyncio.get_event_loop()
        while True:
            message = await loop.run_in_executor(None, sys.stdin.readline)
            if not message:
                continue
            message = message.strip()
            if not message:
                continue
            if message.lower() == "/options":
                click.echo("Current options:")
                click.echo(json.dumps(self.options, indent=4))
                new_username_color = click.prompt("Enter username color (or press enter to keep current)", default="", show_default=False)
                new_own_message_color = click.prompt("Enter your message color (or press enter to keep current)", default="", show_default=False)
                new_other_message_color = click.prompt("Enter others' message color (or press enter to keep current)", default="", show_default=False)
                if new_username_color:
                    self.options["username_color"] = new_username_color
                if new_own_message_color:
                    self.options["own_message_color"] = new_own_message_color
                if new_other_message_color:
                    self.options["other_message_color"] = new_other_message_color
                self.options_manager.save(self.options)
                click.echo("Options updated.")
                continue
            if message.lower() in ["/quit", "/quite"]:
                await websocket.send(message)
                await websocket.close()
                break
            if message.lower() == "/users":
                await websocket.send(message)
                continue
            await websocket.send(message)

# ---------------------------
# CLI using Click
# ---------------------------
@click.group()
def cli():
    """Broadcast Chat CLI Application"""
    pass

@cli.command()
@click.option("--port", required=True, type=int, help="Port number for the server")
@click.option("--name", required=True, help="Moderator username")
def start(port, name):
    """Start the broadcast server (and automatically connect as moderator)."""
    db_manager = DatabaseManager()
    server = BroadcastServer(port, name, db_manager)
    try:
        asyncio.run(server.start(with_client=True))
    except KeyboardInterrupt:
        click.echo("Server shutting down...")

@cli.command()
@click.option("--name", required=True, help="Your username")
@click.option("--port", type=int, default=None, help="Directly connect to a server on the specified port")
def connect(name, port):
    """Connect to an active broadcast server."""
    if port is None:
        db_manager = DatabaseManager()
        servers = asyncio.run(db_manager.get_active_servers())
        if not servers:
            click.echo("No active servers found.")
            return
        click.echo("Available servers:")
        for i, server_info in enumerate(servers):
            click.echo(f"{i+1}: Port {server_info['port']} (Moderator: {server_info['moderator']})")
        choice = click.prompt("Choose server number", type=int)
        if 1 <= choice <= len(servers):
            port = servers[choice-1]["port"]
        else:
            click.echo("Invalid choice.")
            return
    options_manager = OptionsManager()
    client = BroadcastClient(port, name, options_manager)
    try:
        asyncio.run(client.connect())
    except KeyboardInterrupt:
        click.echo("Disconnected.")

@cli.command()
@click.option("--username_color", default=None, help="Color for usernames (default green)")
@click.option("--own_message_color", default=None, help="Color for your messages (default blue)")
@click.option("--other_message_color", default=None, help="Color for others' messages (default purple)")
def options(username_color, own_message_color, other_message_color):
    """Update your local chat display options."""
    options_manager = OptionsManager()
    opts = options_manager.load()
    if username_color:
        opts["username_color"] = username_color
    if own_message_color:
        opts["own_message_color"] = own_message_color
    if other_message_color:
        opts["other_message_color"] = other_message_color
    options_manager.save(opts)
    click.echo("Options updated:")
    click.echo(json.dumps(opts, indent=4))

if __name__ == "__main__":
    colorama.init(autoreset=True)
    cli()
