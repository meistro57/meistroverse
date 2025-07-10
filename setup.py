#!/usr/bin/env python3
"""
Setup script for Meistroverse - collects API keys and populates .env file
"""

import os
import shutil
import sys
from pathlib import Path

def get_user_input(prompt, default=None, required=True):
    """Get user input with optional default value"""
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "
    
    while True:
        value = input(full_prompt).strip()
        if value:
            return value
        elif default:
            return default
        elif not required:
            return ""
        else:
            print("This field is required. Please enter a value.")

def generate_secret_key():
    """Generate a secure secret key"""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(50))

def main():
    """Main setup function"""
    print("=== Meistroverse Setup ===")
    print("This script will help you configure your environment variables.")
    print()
    
    # Check if .env already exists
    env_path = Path(".env")
    if env_path.exists():
        overwrite = input(".env file already exists. Overwrite? (y/N): ").lower()
        if overwrite != 'y':
            print("Setup cancelled.")
            return
    
    # Copy from .env.example if it exists
    env_example_path = Path(".env.example")
    if env_example_path.exists():
        shutil.copy2(env_example_path, env_path)
        print("Copied .env.example to .env")
    else:
        print("Warning: .env.example not found. Creating new .env file.")
    
    # Read current .env content
    env_vars = {}
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    print("\n=== Database Configuration ===")
    
    # Database URL
    current_db = env_vars.get('DATABASE_URL', 'mysql+pymysql://user:password@localhost/meistroverse')
    env_vars['DATABASE_URL'] = get_user_input("Database URL", current_db)
    
    # Redis URL
    current_redis = env_vars.get('REDIS_URL', 'redis://localhost:6379/0')
    env_vars['REDIS_URL'] = get_user_input("Redis URL", current_redis)
    
    print("\n=== AI/LLM API Keys ===")
    
    # OpenAI API Key
    current_openai = env_vars.get('OPENAI_API_KEY', '')
    if current_openai == 'your_openai_api_key_here':
        current_openai = ''
    env_vars['OPENAI_API_KEY'] = get_user_input("OpenAI API Key", current_openai, required=False)
    
    # Anthropic API Key
    current_anthropic = env_vars.get('ANTHROPIC_API_KEY', '')
    if current_anthropic == 'your_anthropic_api_key_here':
        current_anthropic = ''
    env_vars['ANTHROPIC_API_KEY'] = get_user_input("Anthropic API Key", current_anthropic, required=False)
    
    print("\n=== Application Settings ===")
    
    # Debug mode
    current_debug = env_vars.get('DEBUG', 'true')
    env_vars['DEBUG'] = get_user_input("Debug mode (true/false)", current_debug)
    
    # Log level
    current_log_level = env_vars.get('LOG_LEVEL', 'INFO')
    env_vars['LOG_LEVEL'] = get_user_input("Log level (DEBUG/INFO/WARNING/ERROR)", current_log_level)
    
    # Secret key
    current_secret = env_vars.get('SECRET_KEY', '')
    if current_secret == 'your_secret_key_here' or not current_secret:
        generate_new = input("Generate new secret key? (Y/n): ").lower()
        if generate_new != 'n':
            env_vars['SECRET_KEY'] = generate_secret_key()
            print("Generated new secret key.")
        else:
            env_vars['SECRET_KEY'] = get_user_input("Secret key")
    else:
        env_vars['SECRET_KEY'] = current_secret
    
    print("\n=== External API Integration ===")
    
    # Printify API Key
    current_printify_key = env_vars.get('PRINTIFY_API_KEY', '')
    if current_printify_key == 'your_printify_api_key_here':
        current_printify_key = ''
    env_vars['PRINTIFY_API_KEY'] = get_user_input("Printify API Key", current_printify_key, required=False)
    
    # Printify Shop ID
    current_printify_shop = env_vars.get('PRINTIFY_SHOP_ID', '')
    if current_printify_shop == 'your_printify_shop_id_here':
        current_printify_shop = ''
    env_vars['PRINTIFY_SHOP_ID'] = get_user_input("Printify Shop ID", current_printify_shop, required=False)
    
    print("\n=== Task Queue Configuration ===")
    
    # Celery Broker URL
    current_celery_broker = env_vars.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    env_vars['CELERY_BROKER_URL'] = get_user_input("Celery Broker URL", current_celery_broker)
    
    # Celery Result Backend
    current_celery_result = env_vars.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
    env_vars['CELERY_RESULT_BACKEND'] = get_user_input("Celery Result Backend", current_celery_result)
    
    print("\n=== Web Server Configuration ===")
    
    # Host
    current_host = env_vars.get('HOST', '0.0.0.0')
    env_vars['HOST'] = get_user_input("Host", current_host)
    
    # Port
    current_port = env_vars.get('PORT', '8000')
    env_vars['PORT'] = get_user_input("Port", current_port)
    
    # Reload
    current_reload = env_vars.get('RELOAD', 'true')
    env_vars['RELOAD'] = get_user_input("Auto-reload (true/false)", current_reload)
    
    # Write the .env file
    print("\n=== Writing .env file ===")
    with open(env_path, 'w') as f:
        f.write("# Database Configuration\n")
        f.write(f"DATABASE_URL={env_vars['DATABASE_URL']}\n")
        f.write(f"REDIS_URL={env_vars['REDIS_URL']}\n")
        f.write("\n")
        
        f.write("# AI/LLM API Keys\n")
        f.write(f"OPENAI_API_KEY={env_vars['OPENAI_API_KEY']}\n")
        f.write(f"ANTHROPIC_API_KEY={env_vars['ANTHROPIC_API_KEY']}\n")
        f.write("\n")
        
        f.write("# Application Settings\n")
        f.write(f"DEBUG={env_vars['DEBUG']}\n")
        f.write(f"LOG_LEVEL={env_vars['LOG_LEVEL']}\n")
        f.write(f"SECRET_KEY={env_vars['SECRET_KEY']}\n")
        f.write("\n")
        
        f.write("# External API Integration\n")
        f.write(f"PRINTIFY_API_KEY={env_vars['PRINTIFY_API_KEY']}\n")
        f.write(f"PRINTIFY_SHOP_ID={env_vars['PRINTIFY_SHOP_ID']}\n")
        f.write("\n")
        
        f.write("# Task Queue\n")
        f.write(f"CELERY_BROKER_URL={env_vars['CELERY_BROKER_URL']}\n")
        f.write(f"CELERY_RESULT_BACKEND={env_vars['CELERY_RESULT_BACKEND']}\n")
        f.write("\n")
        
        f.write("# Web Server\n")
        f.write(f"HOST={env_vars['HOST']}\n")
        f.write(f"PORT={env_vars['PORT']}\n")
        f.write(f"RELOAD={env_vars['RELOAD']}\n")
    
    print(f"Successfully created .env file!")
    print("\nSetup complete! You can now run the application.")
    print("To modify these settings later, you can:")
    print("  1. Run this setup script again")
    print("  2. Edit the .env file directly")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error during setup: {e}")
        sys.exit(1)