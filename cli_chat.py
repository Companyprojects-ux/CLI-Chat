#!/usr/bin/env python3
"""
CLI Chat Application - Main Entry Point
"""

import os
import sys
import click
from rich.console import Console

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backend.server import ChatServer
from src.frontend.client import ChatClient
from src.utils.config import Config
from src.database.models import User, init_db, get_engine, get_session
from src.utils.security import hash_password

console = Console()

@click.group()
def cli():
    """CLI Chat Application - A terminal-based real-time chat system."""
    pass

@cli.command()
@click.option("--port", default=8000, type=int, help="Port to run the server on")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--moderator", required=True, help="Moderator username")
@click.option("--db-url", help="Database URL (default: uses environment variables)")
@click.option("--redis-host", default="localhost", help="Redis host")
@click.option("--redis-port", default=6379, type=int, help="Redis port")
def server(port, host, moderator, db_url, redis_host, redis_port):
    """Start a chat server."""
    import asyncio

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
        console.print(f"[bold green]Starting server on {host}:{port} with moderator '{moderator}'[/bold green]")
        asyncio.run(server.start(with_client=False))
    except KeyboardInterrupt:
        console.print("[yellow]Server shutting down...[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Server error: {e}[/bold red]")

@cli.command()
@click.option("--host", default="localhost", help="Server host")
@click.option("--port", default=8000, type=int, help="Server port")
@click.option("--username", required=True, help="Your username")
def connect(host, port, username):
    """Connect to a chat server."""
    import asyncio

    # Load configuration
    config = Config()

    # Create and start client
    client = ChatClient(host, port, username, config)

    try:
        console.print(f"[bold green]Connecting to server at {host}:{port} as '{username}'[/bold green]")
        asyncio.run(client.connect())
    except KeyboardInterrupt:
        console.print("[yellow]Client disconnected.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Client error: {e}[/bold red]")

@cli.command()
@click.option("--db-url", help="Database URL (default: uses environment variables)")
@click.option("--username", required=True, help="Username to register")
@click.option("--password", required=True, help="Password for the user")
@click.option("--email", help="Email address (optional)")
@click.option("--admin", is_flag=True, help="Register as admin user")
def register(db_url, username, password, email, admin):
    """Register a new user."""
    # Initialize database connection
    engine = get_engine(db_url)
    init_db(engine)

    # Check if user already exists
    session = get_session(engine)
    try:
        existing_user = session.query(User).filter_by(username=username).first()
        if existing_user:
            console.print(f"[bold red]User '{username}' already exists.[/bold red]")
            return

        # Create new user
        password_hash = hash_password(password)
        user = User(
            username=username,
            password_hash=password_hash,
            email=email,
            is_admin=admin
        )

        session.add(user)
        session.commit()

        console.print(f"[bold green]User '{username}' registered successfully.[/bold green]")
        if admin:
            console.print("[yellow]User has administrator privileges.[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error registering user: {e}[/bold red]")
    finally:
        session.close()

@cli.command()
@click.option("--db-url", help="Database URL (default: uses environment variables)")
def init(db_url):
    """Initialize the database."""
    try:
        # Initialize database
        engine = get_engine(db_url)
        init_db(engine)

        console.print("[bold green]Database initialized successfully.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error initializing database: {e}[/bold red]")

@cli.command()
def version():
    """Show version information."""
    console.print("[bold]CLI Chat Application[/bold]")
    console.print("Version: 1.1.0")
    console.print("A terminal-based real-time chat system")

if __name__ == "__main__":
    cli()
