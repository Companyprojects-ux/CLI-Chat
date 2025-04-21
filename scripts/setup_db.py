#!/usr/bin/env python3
"""
Database setup script for CLI Chat application.
"""

import os
import sys
import dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
dotenv.load_dotenv()

from src.database.models import init_db, get_engine

def setup_database():
    """Set up the database."""
    # Check which database type to use
    db_type = os.getenv('DB_TYPE', 'sqlite').lower()

    if db_type == 'mysql':
        return setup_mysql_database()
    else:
        return setup_sqlite_database()

def setup_sqlite_database():
    """Set up the SQLite database."""
    db_path = os.getenv('SQLITE_PATH', 'cli_chat.db')
    print(f"Setting up SQLite database at '{db_path}'")

    try:
        # Initialize SQLAlchemy models
        connection_string = f"sqlite:///{db_path}"
        engine = get_engine(connection_string)
        init_db(engine)
        print("Database schema created successfully.")
        return True
    except Exception as e:
        print(f"Error setting up SQLite database: {e}")
        return False

def setup_mysql_database():
    """Set up the MySQL database."""
    # Get database connection parameters from environment variables
    host = os.getenv('MYSQL_HOST', 'localhost')
    port = os.getenv('MYSQL_PORT', '3306')
    user = os.getenv('MYSQL_USER', 'chatuser')
    password = os.getenv('MYSQL_PASSWORD', 'chatpassword')
    database = os.getenv('MYSQL_DATABASE', 'cli_chat')

    print(f"Setting up MySQL database '{database}' on {host}:{port}")

    try:
        # Try to import MySQL connector
        import mysql.connector
        from mysql.connector import errorcode

        # Create database if it doesn't exist
        try:
            # Connect without specifying database
            cnx = mysql.connector.connect(
                host=host,
                port=port,
                user=user,
                password=password
            )
            cursor = cnx.cursor()

            # Create database if it doesn't exist
            try:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
                print(f"Database '{database}' created or already exists.")
            except mysql.connector.Error as err:
                print(f"Failed creating database: {err}")
                return False

            cursor.close()
            cnx.close()

            # Initialize SQLAlchemy models
            connection_string = f"mysql+mysqldb://{user}:{password}@{host}:{port}/{database}"
            engine = get_engine(connection_string)
            init_db(engine)
            print("Database schema created successfully.")

            return True

        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                print("Error: Access denied. Check your MySQL username and password.")
            else:
                print(f"Error: {err}")
            return False
    except ImportError:
        print("MySQL connector not found. Please install it with 'pip install mysql-connector-python'.")
        return False

if __name__ == "__main__":
    if setup_database():
        print("Database setup completed successfully.")
    else:
        print("Database setup failed.")
        sys.exit(1)
