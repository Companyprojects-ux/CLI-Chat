# CLI Chat Application Changelog

## Version 1.0.0 - Initial Release

### Core Features
- Real-time terminal-based chat application
- User registration and authentication with password hashing
- Public chat messaging
- Private messaging with `/whisper` command
- User status tracking (online/offline)
- Chat moderation with `/clear` command (admin only)
- Command history and tab completion
- Colorized output for different message types
- SQLite database for message and user storage

## Version 1.1.0 - File Transfer and Encryption Update

### File Transfer Implementation
- Added file transfer functionality between users
- Implemented `/file` command to send files to specific users
- Added base64 encoding for file data transmission
- Implemented file integrity verification with SHA-256 hashing
- Added automatic downloads directory creation
- Limited file size to 10MB for performance
- Added database tracking of file transfers
- Added user confirmation before saving received files

### End-to-End Encryption
- Implemented end-to-end encryption for private messages
- Added RSA key generation and exchange protocol
- Implemented AES message encryption/decryption
- Added secure storage for encryption keys in user's home directory
- Added visual indicators (lock emoji) for encrypted messages
- Added commands for key management:
  - `/keygen` - Generate new encryption keys
  - `/sendkey <username>` - Send your public key to a user
  - `/encrypt <username>` - Enable encryption with a user

### Bug Fixes
- Fixed authentication issues with password verification
- Made Redis optional for environments without Redis installed
- Fixed path handling for file transfers
- Updated deprecated datetime.utcnow() calls to datetime.now(timezone.utc)
- Fixed key exchange mechanism in end-to-end encryption
- Improved error handling for encryption operations
- Fixed conflicts in message processing for encrypted communications

### Code Improvements
- Added proper error handling for file operations
- Improved command parsing and validation
- Enhanced user feedback for file transfers
- Updated help documentation to include new commands
- Added debug output for encryption operations
- Improved PEM key format validation
- Enhanced error reporting for encryption failures

### Testing
- Added comprehensive unit tests for encryption functionality
- Added unit tests for file transfer features
- Added unit tests for client-side encryption and file handling
- Implemented GitHub Actions workflow for automated testing
- Created test runner script for easy test execution
