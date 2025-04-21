"""
Database models for the CLI Chat application.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import os
import datetime

Base = declarative_base()

class User(Base):
    """User model for authentication and identification."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    # Relationships
    messages = relationship("Message", back_populates="user")
    group_memberships = relationship("GroupMember", back_populates="user")

class Server(Base):
    """Server model for tracking active chat servers."""
    __tablename__ = 'servers'

    id = Column(Integer, primary_key=True)
    port = Column(Integer, nullable=False)
    moderator = Column(String(50), nullable=False)
    started = Column(DateTime, default=datetime.datetime.utcnow)
    active = Column(Boolean, default=True)

class Message(Base):
    """Message model for storing chat messages."""
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=True)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    type = Column(String(20), default='chat')  # chat, join, leave, notification, etc.
    is_encrypted = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="messages")
    group = relationship("Group", back_populates="messages")

class Group(Base):
    """Group model for group chats."""
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    is_private = Column(Boolean, default=False)

    # Relationships
    members = relationship("GroupMember", back_populates="group")
    messages = relationship("Message", back_populates="group")

class GroupMember(Base):
    """GroupMember model for tracking group membership."""
    __tablename__ = 'group_members'

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_admin = Column(Boolean, default=False)

    # Relationships
    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="group_memberships")

class FileTransfer(Base):
    """FileTransfer model for tracking file transfers."""
    __tablename__ = 'file_transfers'

    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    size = Column(Integer, nullable=False)  # Size in bytes
    sender_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    receiver_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(20), default='pending')  # pending, completed, failed
    file_hash = Column(String(64), nullable=True)  # For integrity verification

def get_engine(connection_string=None):
    """Create and return a database engine."""
    if connection_string is None:
        # Check if we should use MySQL or SQLite
        db_type = os.getenv('DB_TYPE', 'sqlite').lower()

        if db_type == 'mysql':
            # MySQL connection string
            user = os.getenv('MYSQL_USER', 'chatuser')
            password = os.getenv('MYSQL_PASSWORD', 'chatpassword')
            host = os.getenv('MYSQL_HOST', 'localhost')
            port = os.getenv('MYSQL_PORT', '3306')
            database = os.getenv('MYSQL_DATABASE', 'cli_chat')
            connection_string = f"mysql+mysqldb://{user}:{password}@{host}:{port}/{database}"
        else:
            # SQLite connection string (default)
            db_path = os.getenv('SQLITE_PATH', 'cli_chat.db')
            connection_string = f"sqlite:///{db_path}"

    return create_engine(connection_string)

def get_session(engine=None):
    """Create and return a database session."""
    if engine is None:
        engine = get_engine()

    Session = sessionmaker(bind=engine)
    return Session()

def init_db(engine=None):
    """Initialize the database by creating all tables."""
    if engine is None:
        engine = get_engine()

    Base.metadata.create_all(engine)
