import logging
import os
from datetime import datetime
from pathlib import Path

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

LOG_FILENAME = f"housing_finder_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
LOG_FILEPATH = os.path.join(LOGS_DIR, LOG_FILENAME)

def setup_logger(name: str = "housing_finder", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if logger.handlers:
        return logger
    
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    
    file_handler = logging.FileHandler(LOG_FILEPATH, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # Log everything to file
    file_handler.setFormatter(detailed_formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)  # Use specified level for console
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info(f"Logging initialized. Log file: {LOG_FILEPATH}")
    
    return logger

logger = setup_logger()

