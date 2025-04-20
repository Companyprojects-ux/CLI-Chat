#!/usr/bin/env python3
"""
Setup script for CLI Chat application.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def setup_environment():
    """Set up the Python environment."""
    print("Setting up Python environment...")

    # Check if virtual environment exists
    venv_dir = Path("venv")
    if not venv_dir.exists():
        print("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)

    # Determine the pip and python commands based on the platform
    if sys.platform == "win32":
        pip_cmd = os.path.join("venv", "Scripts", "pip")
        python_cmd = os.path.join("venv", "Scripts", "python")
    else:
        pip_cmd = os.path.join("venv", "bin", "pip")
        python_cmd = os.path.join("venv", "bin", "python")

    # Install dependencies
    print("Installing dependencies...")
    subprocess.run([pip_cmd, "install", "--upgrade", "pip"], check=True)
    subprocess.run([pip_cmd, "install", "-r", "requirements.txt"], check=True)

    return python_cmd

def setup_database(python_cmd):
    """Set up the database."""
    print("Setting up database...")

    # Create scripts directory if it doesn't exist
    scripts_dir = Path("scripts")
    if not scripts_dir.exists():
        scripts_dir.mkdir()

    # Run database setup script
    setup_script = os.path.join("scripts", "setup_db.py")
    if not os.path.exists(setup_script):
        print("Database setup script not found. Skipping database setup.")
        return

    try:
        subprocess.run([python_cmd, setup_script], check=True)
    except subprocess.CalledProcessError:
        print("Database setup failed. Please check your database configuration.")
        sys.exit(1)

def create_admin_user(python_cmd, username, password):
    """Create an admin user."""
    print(f"Creating admin user '{username}'...")

    try:
        subprocess.run([
            python_cmd, "cli_chat.py", "register",
            "--username", username,
            "--password", password,
            "--admin"
        ], check=True)
    except subprocess.CalledProcessError:
        print("Failed to create admin user. Please check your database configuration.")
        sys.exit(1)

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Set up CLI Chat application")
    parser.add_argument("--admin-username", default="admin", help="Admin username")
    parser.add_argument("--admin-password", default="admin", help="Admin password")
    args = parser.parse_args()

    # Set up environment
    python_cmd = setup_environment()

    # Set up database
    setup_database(python_cmd)

    # Create admin user
    create_admin_user(python_cmd, args.admin_username, args.admin_password)

    print("\nSetup completed successfully!")
    print(f"Admin user '{args.admin_username}' created.")
    print("\nTo start the server:")
    print(f"  {python_cmd} cli_chat.py server --port 8000 --moderator {args.admin_username}")
    print("\nTo connect as a client:")
    print(f"  {python_cmd} cli_chat.py connect --host localhost --port 8000 --username <your_username>")

if __name__ == "__main__":
    main()
