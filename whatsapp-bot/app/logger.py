import logging
import os

# Ensure the logs directory exists
os.makedirs("logs", exist_ok=True)

def setup_logger(name: str):
    """
    Sets up and returns a logger that writes to logs/bot.log 
    with a specific format (timestamp, level, message).
    """
    logger = logging.getLogger(name)
    
    # Set the minimum log level
    logger.setLevel(logging.INFO)
    
    # Avoid adding multiple handlers if the logger is already initialized
    if not logger.handlers:
        # File handler to write logs to logs/bot.log
        file_handler = logging.FileHandler("logs/bot.log")
        file_handler.setLevel(logging.INFO)
        
        # Console handler to output logs to the terminal as well
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter: timestamp, level, message
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
    return logger
