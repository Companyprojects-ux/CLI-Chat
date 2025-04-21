# CLI Chat Application v1.1.0

A real-time terminal-based chat application built with Python, Node.js, MySQL, Docker, and AWS.

## Features

- 1:1 Messaging with online/offline status
- Group Chats
- Message History
- File Transfers with integrity verification
- End-to-End Encryption for private messages
- Tab Completion
- Colorized Output
- Command History
- Notifications
- User Authentication and Authorization

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

### Prerequisites

- Python 3.8+
- MySQL
- Redis (optional)
- Docker and Docker Compose (optional)
- Cryptography library (for end-to-end encryption)
- pytest and pytest-asyncio (for running tests)

### Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/CLI-Chat.git
cd CLI-Chat
```

2. Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Initialize the database:

```bash
python cli_chat.py init
```

4. Register a user:

```bash
python cli_chat.py register --username admin --password your_password --admin
```

### Running with Docker

1. Build and start the containers:

```bash
docker-compose up -d
```

2. Register a user:

```bash
docker-compose exec chat-server python cli_chat.py register --username admin --password your_password --admin
```

### Usage

#### Starting a Server

```bash
python cli_chat.py server --port 8000 --moderator admin
```

#### Connecting to a Server

```bash
python cli_chat.py connect --host localhost --port 8000 --username your_username
```

#### Available Commands

##### General Commands
- `/users` - Show online users
- `/whisper <username> <message>` - Send a private message
- `/w <username> <message>` - Short form of whisper
- `/clear` - Clear chat history (moderators only)
- `/quit` or `/exit` - Disconnect from the server
- `/help` - Show help information

##### File Transfer
- `/file <username> <filepath>` - Send a file to a specific user

##### End-to-End Encryption
- `/keygen` - Generate new encryption keys
- `/sendkey <username>` - Send your public key to a user
- `/encrypt <username>` - Enable end-to-end encryption with a user

### Advanced Features

#### File Transfer

The CLI Chat application supports secure file transfers between users with the following features:

- Send files of up to 10MB in size
- Files are automatically saved to a `cli_chat_downloads` directory in the user's home folder
- SHA-256 hash verification ensures file integrity
- User confirmation before saving received files
- Database tracking of all file transfers

To send a file:
```bash
/file username /path/to/your/file.txt
```

#### End-to-End Encryption

Private messages can be encrypted using RSA/AES hybrid encryption:

- RSA 2048-bit keys for secure key exchange
- AES-256 for message encryption
- Keys are automatically generated and stored in the user's home directory
- Visual indicators (🔒) show when messages are encrypted
- Encryption keys persist between sessions

To set up encrypted communication:

1. Generate keys (if not already done):
   ```
   /keygen
   ```

2. Send your public key to another user:
   ```
   /sendkey username
   ```

3. Enable encryption with that user:
   ```
   /encrypt username
   ```

4. Send encrypted messages using the normal whisper command:
   ```
   /whisper username Your secret message here
   ```

## Testing

The CLI Chat application includes comprehensive unit tests for all features, including file transfer and end-to-end encryption.

### Running Tests

To run all tests:

```bash
./run_tests.py
```

To run specific test types:

```bash
./run_tests.py --type unit       # Run all unit tests
./run_tests.py --type encryption # Run encryption tests only
./run_tests.py --type file       # Run file transfer tests only
./run_tests.py --type client     # Run client feature tests only
```

### Continuous Integration

The repository includes GitHub Actions workflows that automatically run tests on push and pull requests to ensure code quality and prevent regressions.

## Deployment to AWS

### Prerequisites

- AWS Account
- AWS CLI configured

### Steps

1. Create an EC2 instance
2. Set up RDS for MySQL
3. Set up ElastiCache for Redis
4. Deploy the application

Detailed deployment instructions can be found in the [deployment guide](docs/deployment.md).

## Changelog

For a detailed list of changes and features, see the [CHANGELOG.md](CHANGELOG.md) file.

## License

[MIT License](LICENSE)