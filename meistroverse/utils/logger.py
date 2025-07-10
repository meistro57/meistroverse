import logging
import sys
from typing import Optional
from pythonjsonlogger import jsonlogger

from meistroverse.config import settings


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Get a configured logger instance"""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # Set log level
        log_level = level or settings.log_level
        logger.setLevel(getattr(logging, log_level.upper()))
        
        # Create handler
        handler = logging.StreamHandler(sys.stdout)
        
        # Create formatter
        if settings.debug:
            # Human-readable format for development
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        else:
            # JSON format for production
            formatter = jsonlogger.JsonFormatter(
                '%(asctime)s %(name)s %(levelname)s %(message)s'
            )
            
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Prevent duplicate logs
        logger.propagate = False
        
    return logger