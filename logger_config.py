"""
Logging Configuration
====================

Centralized logging configuration for the Smart Student Housing Finder project.
All logs are saved to both console and log files.

Urban Technology Relevance:
- Logging enables debugging and performance analysis
- File logs provide audit trails for data processing
- Helps track API usage and geocoding success rates
"""

import logging
import os
from datetime import datetime
from pathlib import Path

# Create logs directory if it doesn't exist
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Create log filename with timestamp
LOG_FILENAME = f"housing_finder_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
LOG_FILEPATH = os.path.join(LOGS_DIR, LOG_FILENAME)

# Configure root logger
def setup_logger(name: str = "housing_finder", level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with both file and console handlers.
    
    Parameters:
    -----------
    name : str
        Logger name
    level : int
        Logging level (default: INFO)
    
    Returns:
    --------
    logging.Logger
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers if logger already exists
    if logger.handlers:
        return logger
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    
    # File handler (detailed logs)
    file_handler = logging.FileHandler(LOG_FILEPATH, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # Log everything to file
    file_handler.setFormatter(detailed_formatter)
    
    # Console handler (simpler output)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)  # Use specified level for console
    console_handler.setFormatter(console_formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info(f"Logging initialized. Log file: {LOG_FILEPATH}")
    
    return logger

# Create default logger
logger = setup_logger()

