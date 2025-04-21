# Deployment Guide

This guide provides instructions for deploying the CLI Chat application to AWS.

## Prerequisites

- AWS Account
- AWS CLI installed and configured
- Docker installed locally

## AWS Services Used

- **EC2**: For hosting the application
- **RDS**: For MySQL database
- **ElastiCache**: For Redis caching
- **ECR**: For storing Docker images (optional)

## Deployment Steps

### 1. Set Up RDS for MySQL

1. Go to the AWS RDS console
2. Click "Create database"
3. Select "MySQL"
4. Choose "Free tier" for development or select appropriate instance size for production
5. Configure settings:
   - DB instance identifier: `cli-chat-db`
   - Master username: `chatuser`
   - Master password: (create a secure password)
6. Configure advanced settings:
   - Initial database name: `cli_chat`
   - VPC: Default VPC
   - Public accessibility: Yes (for development) / No (for production)
7. Create database

Note the endpoint, port, username, password, and database name for later use.

### 2. Set Up ElastiCache for Redis

1. Go to the AWS ElastiCache console
2. Click "Create"
3. Select "Redis"
4. Configure settings:
   - Name: `cli-chat-redis`
   - Node type: `cache.t2.micro` (free tier) or appropriate size
   - Number of replicas: 0 (for development)
5. Create Redis cluster

Note the endpoint and port for later use.

### 3. Set Up EC2 Instance

1. Go to the AWS EC2 console
2. Click "Launch instance"
3. Select Amazon Linux 2 AMI
4. Choose instance type (t2.micro for free tier)
5. Configure instance:
   - VPC: Same as RDS
   - Auto-assign Public IP: Enable
6. Add storage (default is fine for development)
7. Configure security group:
   - Allow SSH (port 22) from your IP
   - Allow TCP on port 8000 (or your chosen port) from appropriate sources
8. Launch instance and select/create a key pair

### 4. Configure Security Groups

Ensure that:
- EC2 security group allows inbound traffic on the chat server port (8000 by default)
- RDS security group allows inbound MySQL traffic (port 3306) from the EC2 security group
- ElastiCache security group allows inbound Redis traffic (port 6379) from the EC2 security group

### 5. Deploy Application to EC2

#### Option 1: Manual Deployment

1. SSH into your EC2 instance:
   ```bash
   ssh -i your-key.pem ec2-user@your-ec2-public-dns
   ```

2. Install dependencies:
   ```bash
   sudo yum update -y
   sudo yum install -y git python3 python3-pip mysql-devel
   ```

3. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/CLI-Chat.git
   cd CLI-Chat
   ```

4. Set up Python environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. Create a `.env` file with your configuration:
   ```bash
   cat > .env << EOF
   MYSQL_HOST=your-rds-endpoint
   MYSQL_PORT=3306
   MYSQL_USER=chatuser
   MYSQL_PASSWORD=your-password
   MYSQL_DATABASE=cli_chat
   REDIS_HOST=your-redis-endpoint
   REDIS_PORT=6379
   JWT_SECRET=your-secret-key
   EOF
   ```

6. Initialize the database:
   ```bash
   python cli_chat.py init
   ```

7. Register an admin user:
   ```bash
   python cli_chat.py register --username admin --password your-password --admin
   ```

8. Start the server:
   ```bash
   nohup python cli_chat.py server --port 8000 --moderator admin &
   ```

#### Option 2: Docker Deployment

1. SSH into your EC2 instance:
   ```bash
   ssh -i your-key.pem ec2-user@your-ec2-public-dns
   ```

2. Install Docker and Docker Compose:
   ```bash
   sudo yum update -y
   sudo amazon-linux-extras install docker
   sudo service docker start
   sudo usermod -a -G docker ec2-user
   sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

3. Log out and log back in to apply the docker group changes:
   ```bash
   exit
   ssh -i your-key.pem ec2-user@your-ec2-public-dns
   ```

4. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/CLI-Chat.git
   cd CLI-Chat
   ```

5. Create a `.env` file with your configuration:
   ```bash
   cat > .env << EOF
   MYSQL_HOST=your-rds-endpoint
   MYSQL_PORT=3306
   MYSQL_USER=chatuser
   MYSQL_PASSWORD=your-password
   MYSQL_DATABASE=cli_chat
   REDIS_HOST=your-redis-endpoint
   REDIS_PORT=6379
   JWT_SECRET=your-secret-key
   EOF
   ```

6. Update the `docker-compose.yml` file to use external MySQL and Redis:
   ```bash
   sed -i 's/mysql:/# mysql:/g' docker-compose.yml
   sed -i 's/redis:/# redis:/g' docker-compose.yml
   ```

7. Build and start the containers:
   ```bash
   docker-compose up -d
   ```

8. Register an admin user:
   ```bash
   docker-compose exec chat-server python cli_chat.py register --username admin --password your-password --admin
   ```

## Connecting to the Server

Clients can connect to the server using:

```bash
python cli_chat.py connect --host your-ec2-public-dns --port 8000 --username your-username
```

## Production Considerations

For a production deployment, consider:

1. Setting up a load balancer for high availability
2. Using Auto Scaling Groups for the application servers
3. Implementing proper monitoring with CloudWatch
4. Setting up backups for RDS
5. Using a more robust security strategy (VPC, private subnets, etc.)
6. Setting up CI/CD pipelines for automated deployment
