#!/usr/bin/env python3
"""
MEISTROVERSE Runner Script

This script provides easy commands to run different parts of the MEISTROVERSE system.
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from meistroverse.config import settings
from meistroverse.database import create_tables, drop_tables
from meistroverse.core.knowledge_indexer import knowledge_indexer
from meistroverse.core.suggestion_loop import suggestion_loop
from meistroverse.utils.logger import get_logger

logger = get_logger(__name__)


async def init_database():
    """Initialize the database with tables"""
    logger.info("Initializing database...")
    try:
        create_tables()
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        return False
    return True


async def reset_database():
    """Reset the database (drop and recreate tables)"""
    logger.info("Resetting database...")
    try:
        drop_tables()
        create_tables()
        logger.info("✅ Database reset successfully")
    except Exception as e:
        logger.error(f"❌ Failed to reset database: {e}")
        return False
    return True


async def rebuild_index():
    """Rebuild the knowledge index"""
    logger.info("Rebuilding knowledge index...")
    try:
        knowledge_indexer.rebuild_index()
        logger.info("✅ Knowledge index rebuilt successfully")
    except Exception as e:
        logger.error(f"❌ Failed to rebuild index: {e}")
        return False
    return True


async def run_daily_analysis():
    """Run the daily suggestion loop analysis"""
    logger.info("Running daily analysis...")
    try:
        result = await suggestion_loop.run_daily_analysis()
        logger.info("✅ Daily analysis completed successfully")
        print(f"Analysis results: {result}")
    except Exception as e:
        logger.error(f"❌ Failed to run daily analysis: {e}")
        return False
    return True


async def start_server():
    """Start the MEISTROVERSE web server"""
    logger.info("Starting MEISTROVERSE server...")
    import uvicorn
    
    try:
        # Import main app
        from main import app
        
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            reload=settings.reload,
            log_level=settings.log_level.lower()
        )
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        return False
    return True


def check_environment():
    """Check if environment is properly configured"""
    logger.info("Checking environment configuration...")
    
    issues = []
    
    # Check database URL
    if not settings.database_url or settings.database_url == "mysql+pymysql://user:password@localhost/meistroverse":
        issues.append("❌ Database URL not configured (update DATABASE_URL in .env)")
    else:
        logger.info("✅ Database URL configured")
    
    # Check Redis URL
    if not settings.redis_url:
        issues.append("⚠️  Redis URL not configured (some features may not work)")
    else:
        logger.info("✅ Redis URL configured")
    
    # Check API keys
    if not settings.openai_api_key and not settings.anthropic_api_key:
        issues.append("⚠️  No LLM API keys configured (some agents may not work)")
    else:
        if settings.openai_api_key:
            logger.info("✅ OpenAI API key configured")
        if settings.anthropic_api_key:
            logger.info("✅ Anthropic API key configured")
    
    # Check secret key
    if settings.secret_key == "your_secret_key_here":
        issues.append("⚠️  Default secret key in use (update SECRET_KEY in .env)")
    else:
        logger.info("✅ Secret key configured")
    
    if issues:
        logger.warning("Environment configuration issues found:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        logger.info("✅ Environment configuration looks good")
        return True


def create_env_file():
    """Create a .env file from the example"""
    env_file = project_root / ".env"
    env_example = project_root / ".env.example"
    
    if env_file.exists():
        logger.info("📄 .env file already exists")
        return True
    
    if not env_example.exists():
        logger.error("❌ .env.example file not found")
        return False
    
    try:
        import shutil
        shutil.copy(env_example, env_file)
        logger.info("✅ Created .env file from .env.example")
        logger.info("📝 Please edit .env file with your configuration")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create .env file: {e}")
        return False


async def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="MEISTROVERSE Management CLI")
    
    parser.add_argument(
        "command",
        choices=[
            "init", "reset-db", "rebuild-index", "daily-analysis", 
            "server", "check-env", "create-env"
        ],
        help="Command to execute"
    )
    
    args = parser.parse_args()
    
    print("🤖 MEISTROVERSE Management CLI")
    print("=" * 40)
    
    success = True
    
    if args.command == "init":
        success = await init_database()
        
    elif args.command == "reset-db":
        confirm = input("⚠️  This will delete all data. Are you sure? (y/N): ")
        if confirm.lower() == 'y':
            success = await reset_database()
        else:
            print("Operation cancelled")
            
    elif args.command == "rebuild-index":
        success = await rebuild_index()
        
    elif args.command == "daily-analysis":
        success = await run_daily_analysis()
        
    elif args.command == "server":
        success = await start_server()
        
    elif args.command == "check-env":
        success = check_environment()
        
    elif args.command == "create-env":
        success = create_env_file()
    
    if success:
        print("\n✅ Command completed successfully")
    else:
        print("\n❌ Command failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())