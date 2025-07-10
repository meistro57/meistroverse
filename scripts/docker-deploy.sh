#!/bin/bash
# MEISTROVERSE Docker Deployment Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_PROJECT_NAME="meistroverse"
ENV_FILE=".env"
BACKUP_DIR="./backups"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    log_success "Dependencies check passed"
}

create_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        log_info "Creating environment file from template..."
        cp .env.example "$ENV_FILE"
        log_warning "Please edit $ENV_FILE with your configuration before proceeding"
        log_warning "At minimum, set secure passwords for MYSQL_PASSWORD and SECRET_KEY"
        read -p "Press Enter to continue after editing $ENV_FILE..."
    else
        log_info "Environment file already exists"
    fi
}

create_directories() {
    log_info "Creating necessary directories..."
    mkdir -p "$BACKUP_DIR"
    mkdir -p data/logs
    mkdir -p data/exports
    log_success "Directories created"
}

build_images() {
    log_info "Building Docker images..."
    docker-compose build --no-cache
    log_success "Images built successfully"
}

start_services() {
    log_info "Starting services..."
    
    # Start core services first
    log_info "Starting database and cache services..."
    docker-compose up -d mysql redis
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    sleep 30
    
    # Check database health
    if docker-compose exec mysql mysqladmin ping -h localhost --silent; then
        log_success "Database is ready"
    else
        log_error "Database failed to start properly"
        exit 1
    fi
    
    # Start application services
    log_info "Starting application services..."
    docker-compose up -d meistroverse celery-worker celery-beat
    
    # Start optional services if requested
    if [ "$1" = "--with-monitoring" ]; then
        log_info "Starting monitoring services..."
        docker-compose --profile monitoring up -d
    fi
    
    if [ "$1" = "--with-nginx" ]; then
        log_info "Starting nginx reverse proxy..."
        docker-compose --profile nginx up -d
    fi
    
    log_success "All services started"
}

check_health() {
    log_info "Checking service health..."
    
    # Wait for application to start
    sleep 15
    
    # Check application health
    if curl -f http://localhost:8000/health &> /dev/null; then
        log_success "Application is healthy"
    else
        log_error "Application health check failed"
        log_info "Checking logs..."
        docker-compose logs meistroverse
        exit 1
    fi
}

initialize_database() {
    log_info "Initializing database..."
    
    # Run database initialization
    docker-compose exec meistroverse python scripts/run.py init
    
    log_success "Database initialized"
}

backup_database() {
    log_info "Creating database backup..."
    
    BACKUP_FILE="$BACKUP_DIR/meistroverse_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    docker-compose exec mysql mysqldump \
        -u meistroverse \
        -p$(grep MYSQL_PASSWORD $ENV_FILE | cut -d '=' -f2) \
        meistroverse > "$BACKUP_FILE"
    
    log_success "Backup created: $BACKUP_FILE"
}

show_status() {
    log_info "Service status:"
    docker-compose ps
    
    echo ""
    log_info "Access URLs:"
    echo "  Dashboard: http://localhost:8000/dashboard/"
    echo "  Task Launcher: http://localhost:8000/launcher/"
    echo "  API Documentation: http://localhost:8000/docs"
    echo "  Health Check: http://localhost:8000/health"
    
    if docker-compose ps | grep -q grafana; then
        echo "  Grafana: http://localhost:3000 (admin/admin123)"
    fi
    
    if docker-compose ps | grep -q prometheus; then
        echo "  Prometheus: http://localhost:9090"
    fi
}

show_logs() {
    if [ -z "$1" ]; then
        docker-compose logs -f
    else
        docker-compose logs -f "$1"
    fi
}

stop_services() {
    log_info "Stopping services..."
    docker-compose down
    log_success "Services stopped"
}

cleanup() {
    log_warning "This will remove all containers, networks, and images"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Cleaning up..."
        docker-compose down -v --rmi all --remove-orphans
        docker system prune -f
        log_success "Cleanup completed"
    else
        log_info "Cleanup cancelled"
    fi
}

update_services() {
    log_info "Updating services..."
    
    # Create backup before update
    backup_database
    
    # Pull latest images and rebuild
    docker-compose pull
    docker-compose build --no-cache
    
    # Restart services
    docker-compose up -d
    
    # Check health
    check_health
    
    log_success "Update completed"
}

# Main script
case "$1" in
    "install")
        log_info "Installing MEISTROVERSE..."
        check_dependencies
        create_env_file
        create_directories
        build_images
        start_services "$2"
        initialize_database
        check_health
        show_status
        log_success "Installation completed!"
        ;;
    "start")
        log_info "Starting MEISTROVERSE..."
        start_services "$2"
        check_health
        show_status
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        stop_services
        start_services "$2"
        check_health
        show_status
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs "$2"
        ;;
    "backup")
        backup_database
        ;;
    "update")
        update_services
        ;;
    "cleanup")
        cleanup
        ;;
    "build")
        build_images
        ;;
    *)
        echo "MEISTROVERSE Docker Deployment Script"
        echo ""
        echo "Usage: $0 [command] [options]"
        echo ""
        echo "Commands:"
        echo "  install [--with-monitoring|--with-nginx]  Install and start MEISTROVERSE"
        echo "  start [--with-monitoring|--with-nginx]    Start services"
        echo "  stop                                      Stop services"
        echo "  restart [--with-monitoring|--with-nginx]  Restart services"
        echo "  status                                    Show service status"
        echo "  logs [service]                           Show logs for all or specific service"
        echo "  backup                                   Create database backup"
        echo "  update                                   Update and restart services"
        echo "  build                                    Build Docker images"
        echo "  cleanup                                  Remove all containers and images"
        echo ""
        echo "Options:"
        echo "  --with-monitoring    Include Prometheus and Grafana"
        echo "  --with-nginx         Include Nginx reverse proxy"
        echo ""
        echo "Examples:"
        echo "  $0 install                    # Basic installation"
        echo "  $0 install --with-monitoring # Install with monitoring"
        echo "  $0 logs meistroverse         # Show application logs"
        echo "  $0 backup                    # Create database backup"
        ;;
esac