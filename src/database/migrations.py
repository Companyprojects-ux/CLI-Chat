"""
Database migration script for the CLI Chat application.
"""

import os
import argparse
import asyncio
import asyncpg
import mysql.connector
from mysql.connector import errorcode
from datetime import datetime
from models import init_db, get_engine

async def export_postgres_data(pg_dsn):
    """Export data from PostgreSQL database."""
    print("Connecting to PostgreSQL database...")
    conn = await asyncpg.connect(pg_dsn)
    
    # Export servers
    print("Exporting servers...")
    servers = await conn.fetch("SELECT id, port, moderator, started, active FROM servers")
    
    # Export messages
    print("Exporting messages...")
    messages = await conn.fetch("SELECT id, username, content, timestamp, type FROM messages")
    
    await conn.close()
    print("PostgreSQL data export completed.")
    
    return {
        'servers': servers,
        'messages': messages
    }

def import_mysql_data(mysql_config, data):
    """Import data into MySQL database."""
    print("Connecting to MySQL database...")
    try:
        cnx = mysql.connector.connect(**mysql_config)
        cursor = cnx.cursor()
        
        # Create a temporary user for old messages
        print("Creating temporary user for old messages...")
        cursor.execute("""
            INSERT IGNORE INTO users (username, password_hash, created_at, is_active)
            VALUES ('migration_user', 'migration_placeholder', %s, TRUE)
        """, (datetime.utcnow(),))
        cnx.commit()
        
        # Get the migration user ID
        cursor.execute("SELECT id FROM users WHERE username = 'migration_user'")
        migration_user_id = cursor.fetchone()[0]
        
        # Import servers
        print("Importing servers...")
        for server in data['servers']:
            cursor.execute("""
                INSERT INTO servers (id, port, moderator, started, active)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                server['id'], 
                server['port'], 
                server['moderator'], 
                server['started'], 
                server['active']
            ))
        
        # Import messages
        print("Importing messages...")
        for message in data['messages']:
            cursor.execute("""
                INSERT INTO messages (id, user_id, content, timestamp, type)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                message['id'],
                migration_user_id,  # Associate with the migration user
                message['content'],
                message['timestamp'],
                message['type']
            ))
        
        cnx.commit()
        cursor.close()
        cnx.close()
        print("MySQL data import completed.")
        
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Error: Access denied. Check your MySQL username and password.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Error: Database does not exist.")
        else:
            print(f"Error: {err}")
        return False
    
    return True

def setup_mysql_database(mysql_config):
    """Set up the MySQL database schema."""
    print("Setting up MySQL database schema...")
    
    # Create database if it doesn't exist
    db_name = mysql_config['database']
    config_without_db = mysql_config.copy()
    config_without_db.pop('database', None)
    
    try:
        cnx = mysql.connector.connect(**config_without_db)
        cursor = cnx.cursor()
        
        # Create database if it doesn't exist
        try:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
            print(f"Database '{db_name}' created or already exists.")
        except mysql.connector.Error as err:
            print(f"Failed creating database: {err}")
            return False
        
        cursor.close()
        cnx.close()
        
        # Initialize SQLAlchemy models
        engine = get_engine(f"mysql+mysqldb://{mysql_config['user']}:{mysql_config['password']}@{mysql_config['host']}:{mysql_config.get('port', 3306)}/{db_name}")
        init_db(engine)
        print("Database schema created successfully.")
        
        return True
        
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Error: Access denied. Check your MySQL username and password.")
        else:
            print(f"Error: {err}")
        return False

async def migrate_data(pg_dsn, mysql_config):
    """Migrate data from PostgreSQL to MySQL."""
    # Set up MySQL database
    if not setup_mysql_database(mysql_config):
        print("Failed to set up MySQL database. Migration aborted.")
        return False
    
    # Export data from PostgreSQL
    try:
        data = await export_postgres_data(pg_dsn)
    except Exception as e:
        print(f"Error exporting data from PostgreSQL: {e}")
        return False
    
    # Import data into MySQL
    if not import_mysql_data(mysql_config, data):
        print("Failed to import data into MySQL. Migration aborted.")
        return False
    
    print("Migration completed successfully!")
    return True

def main():
    """Main function to run the migration script."""
    parser = argparse.ArgumentParser(description='Migrate data from PostgreSQL to MySQL')
    parser.add_argument('--pg-dsn', default=os.getenv('BROADCAST_DB_DSN', 'postgresql://postgres:guest@localhost:5432/broadcast_chat'),
                        help='PostgreSQL connection string')
    parser.add_argument('--mysql-host', default=os.getenv('MYSQL_HOST', 'localhost'),
                        help='MySQL host')
    parser.add_argument('--mysql-port', default=os.getenv('MYSQL_PORT', '3306'),
                        help='MySQL port')
    parser.add_argument('--mysql-user', default=os.getenv('MYSQL_USER', 'chatuser'),
                        help='MySQL username')
    parser.add_argument('--mysql-password', default=os.getenv('MYSQL_PASSWORD', 'chatpassword'),
                        help='MySQL password')
    parser.add_argument('--mysql-database', default=os.getenv('MYSQL_DATABASE', 'cli_chat'),
                        help='MySQL database name')
    
    args = parser.parse_args()
    
    mysql_config = {
        'host': args.mysql_host,
        'port': args.mysql_port,
        'user': args.mysql_user,
        'password': args.mysql_password,
        'database': args.mysql_database
    }
    
    asyncio.run(migrate_data(args.pg_dsn, mysql_config))

if __name__ == "__main__":
    main()
