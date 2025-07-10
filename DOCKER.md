# 🐳 MEISTROVERSE Docker Deployment Guide

This guide covers how to deploy MEISTROVERSE using Docker and Docker Compose for both development and production environments.

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 4GB+ RAM
- 10GB+ free disk space

### 1. Clone and Setup

```bash
git clone <repository>
cd meistroverse_test_claude
chmod +x scripts/docker-deploy.sh
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

**Required Settings:**
```bash
MYSQL_PASSWORD=your_secure_mysql_password
SECRET_KEY=your_secure_secret_key_here
OPENAI_API_KEY=your_openai_api_key  # Optional
ANTHROPIC_API_KEY=your_anthropic_api_key  # Optional
```

### 3. Deploy

```bash
# Basic deployment
./scripts/docker-deploy.sh install

# With monitoring (Prometheus + Grafana)
./scripts/docker-deploy.sh install --with-monitoring

# With nginx reverse proxy
./scripts/docker-deploy.sh install --with-nginx
```

### 4. Access

- **Dashboard**: http://localhost:8000/dashboard/
- **Task Launcher**: http://localhost:8000/launcher/
- **API Docs**: http://localhost:8000/docs
- **Grafana** (if enabled): http://localhost:3000 (admin/admin123)

## 🏗️ Architecture

### Services Overview

| Service | Description | Port | Dependencies |
|---------|-------------|------|--------------|
| `meistroverse` | Main application | 8000 | mysql, redis |
| `mysql` | Database | 3306 | - |
| `redis` | Cache & message broker | 6379 | - |
| `celery-worker` | Background task processor | - | mysql, redis |
| `celery-beat` | Task scheduler | - | mysql, redis |
| `nginx` | Reverse proxy (optional) | 80, 443 | meistroverse |
| `prometheus` | Metrics collection (optional) | 9090 | meistroverse |
| `grafana` | Monitoring dashboard (optional) | 3000 | prometheus |

### Network Architecture

```
Internet → Nginx (80/443) → MEISTROVERSE (8000)
                              ↓
                           MySQL (3306)
                              ↓
                           Redis (6379)
                              ↓
                        Celery Workers
```

## 🛠️ Configuration

### Environment Variables

#### Application Settings
```bash
DEBUG=false                    # Enable debug mode
LOG_LEVEL=INFO                # Logging level
HOST=0.0.0.0                  # Bind host
PORT=8000                     # Application port
SECRET_KEY=your_secret_key    # Security key
```

#### Database Configuration
```bash
MYSQL_ROOT_PASSWORD=rootpass123
MYSQL_PASSWORD=meistroverse123
MYSQL_PORT=3306
```

#### Redis Configuration
```bash
REDIS_PORT=6379
```

#### AI/LLM Integration
```bash
OPENAI_API_KEY=sk-...         # OpenAI API key
ANTHROPIC_API_KEY=sk-ant-...  # Anthropic Claude API key
```

#### External Services
```bash
PRINTIFY_API_KEY=your_key     # Printify integration
PRINTIFY_SHOP_ID=your_shop_id
```

### Volume Mounts

| Volume | Description | Host Path |
|--------|-------------|-----------|
| `mysql_data` | Database files | Docker volume |
| `redis_data` | Redis persistence | Docker volume |
| `meistroverse_data` | Application data | Docker volume |
| `meistroverse_logs` | Application logs | Docker volume |

## 🔧 Management Commands

### Basic Operations

```bash
# Start services
./scripts/docker-deploy.sh start

# Stop services
./scripts/docker-deploy.sh stop

# Restart services
./scripts/docker-deploy.sh restart

# View status
./scripts/docker-deploy.sh status

# View logs
./scripts/docker-deploy.sh logs
./scripts/docker-deploy.sh logs meistroverse  # Specific service
```

### Maintenance

```bash
# Create database backup
./scripts/docker-deploy.sh backup

# Update services
./scripts/docker-deploy.sh update

# Rebuild images
./scripts/docker-deploy.sh build

# Clean up everything
./scripts/docker-deploy.sh cleanup
```

### Manual Docker Commands

```bash
# View running containers
docker-compose ps

# Execute commands in containers
docker-compose exec meistroverse python scripts/run.py check-env
docker-compose exec mysql mysql -u meistroverse -p meistroverse

# View logs
docker-compose logs -f meistroverse
docker-compose logs --tail=100 celery-worker

# Scale workers
docker-compose up -d --scale celery-worker=3
```

## 🔍 Monitoring & Observability

### Health Checks

All services include health checks:

```bash
# Check application health
curl http://localhost:8000/health

# Check database health
docker-compose exec mysql mysqladmin ping

# Check Redis health
docker-compose exec redis redis-cli ping
```

### Prometheus Metrics

When monitoring is enabled, metrics are available at:
- Application metrics: http://localhost:8000/metrics
- Prometheus UI: http://localhost:9090

### Grafana Dashboards

Pre-configured dashboards for:
- System performance
- Application metrics
- Database statistics
- Task queue monitoring

## 🚀 Production Deployment

### Security Considerations

1. **Change Default Passwords**
   ```bash
   MYSQL_ROOT_PASSWORD=secure_random_password
   MYSQL_PASSWORD=secure_random_password
   SECRET_KEY=secure_random_key_32_chars_min
   ```

2. **Enable HTTPS**
   - Configure SSL certificates in nginx
   - Use Let's Encrypt for free certificates

3. **Network Security**
   - Use firewall rules
   - Limit exposed ports
   - Configure Docker network isolation

4. **Data Persistence**
   - Use external volumes for production
   - Set up regular backups
   - Monitor disk usage

### Performance Tuning

#### MySQL Optimization
```sql
# /docker/mysql/production.cnf
[mysqld]
innodb_buffer_pool_size = 1G
innodb_log_file_size = 256M
max_connections = 500
query_cache_size = 64M
```

#### Redis Optimization
```bash
# docker/redis/production.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

#### Application Scaling
```bash
# Scale workers based on load
docker-compose up -d --scale celery-worker=5

# Use nginx load balancing for multiple app instances
docker-compose up -d --scale meistroverse=3
```

## 🐛 Troubleshooting

### Common Issues

#### Database Connection Errors
```bash
# Check MySQL status
docker-compose exec mysql mysqladmin ping

# Check database logs
docker-compose logs mysql

# Verify credentials
docker-compose exec mysql mysql -u meistroverse -p meistroverse
```

#### Application Won't Start
```bash
# Check application logs
docker-compose logs meistroverse

# Check environment variables
docker-compose exec meistroverse env | grep -E "(DATABASE|REDIS)"

# Verify dependencies
docker-compose exec meistroverse python scripts/run.py check-env
```

#### Performance Issues
```bash
# Check resource usage
docker stats

# Monitor task queue
docker-compose logs celery-worker

# Check database performance
docker-compose exec mysql mysql -u root -p -e "SHOW PROCESSLIST;"
```

### Debug Mode

For development, use the override file:

```bash
# Enable development mode
cp docker-compose.override.yml.example docker-compose.override.yml

# This enables:
# - Live code reloading
# - Debug logging
# - Exposed database ports
# - Development fixtures
```

## 📊 Backup & Recovery

### Automated Backups

```bash
# Setup cron for daily backups
0 2 * * * /path/to/meistroverse/scripts/docker-deploy.sh backup
```

### Manual Backup

```bash
# Database backup
docker-compose exec mysql mysqldump -u meistroverse -p meistroverse > backup.sql

# Volume backup
docker run --rm -v meistroverse_mysql_data:/data -v $(pwd):/backup alpine tar czf /backup/mysql_data.tar.gz -C /data .
```

### Recovery

```bash
# Restore database
docker-compose exec -T mysql mysql -u meistroverse -p meistroverse < backup.sql

# Restore volumes
docker run --rm -v meistroverse_mysql_data:/data -v $(pwd):/backup alpine tar xzf /backup/mysql_data.tar.gz -C /data
```

## 🔧 Development Setup

### Local Development

```bash
# Use development override
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d

# Install development dependencies
docker-compose exec meistroverse pip install -e ".[dev]"

# Run tests
docker-compose exec meistroverse pytest

# Access shell
docker-compose exec meistroverse bash
```

### IDE Integration

For VS Code, add to `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "docker-compose exec meistroverse python",
    "python.terminal.activateEnvironment": false
}
```

## 📈 Monitoring Production

### Resource Monitoring

```bash
# System resources
docker stats

# Application metrics
curl http://localhost:8000/metrics

# Database performance
docker-compose exec mysql mysql -u root -p -e "
  SELECT * FROM information_schema.processlist 
  WHERE command != 'Sleep' 
  ORDER BY time DESC;
"
```

### Log Management

```bash
# Centralized logging with ELK stack
# Add to docker-compose.yml:
elasticsearch:
  image: docker.elastic.co/elasticsearch/elasticsearch:7.15.0
logstash:
  image: docker.elastic.co/logstash/logstash:7.15.0
kibana:
  image: docker.elastic.co/kibana/kibana:7.15.0
```

---

**Need Help?**
- Check the [troubleshooting section](#troubleshooting)
- Review application logs: `docker-compose logs meistroverse`
- Verify configuration: `docker-compose exec meistroverse python scripts/run.py check-env`