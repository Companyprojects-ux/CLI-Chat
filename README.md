# CLI Chat Application

A real-time terminal-based chat application built with Python, Node.js, MySQL, Docker, and AWS.

## Features

- 1:1 Messaging with online/offline status
- Group Chats
- Message History
- File Transfers
- Typing Indicators
- End-to-End Encryption
- Tab Completion
- Colorized Output
- Command History
- Notifications

## Tech Stack

- **Backend**: Python (WebSockets, SQLAlchemy)
- **Frontend**: Python (Rich library for terminal UI)
- **Database**: MySQL
- **Caching**: Redis
- **Containerization**: Docker
- **Deployment**: AWS (EC2, RDS, ElastiCache)

## Project Structure

```
CLI-Chat/
├── src/
│   ├── backend/       # Python backend code
│   ├── frontend/      # Terminal UI code
│   ├── database/      # Database models and migrations
│   └── utils/         # Shared utilities
├── tests/             # Test files
├── config/            # Configuration files
├── docker/            # Docker configuration
├── cli_chat.py        # Main CLI entry point
├── docker-compose.yml # Docker Compose configuration
└── Dockerfile.server  # Server Dockerfile
```

## Getting Started

Instructions for setting up and running the application will be added here.

## License

[MIT License](LICENSE)