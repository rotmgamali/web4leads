import logging
import os
from datetime import datetime
from pathlib import Path

# Base directory for logs
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "automation.log"

def get_logger(name: str, log_filename: str = None):
    """Returns a pre-configured logger with obsessive formatting.
    If log_filename is provided, it uses that specific file."""
    
    # We want unique loggers per file, so append filename to logger name if specific
    # Or just rely on the handler being different?
    # Actually, logging.getLogger(name) returns a singleton. 
    # If we add a handler to "SCHEDULER" and it already has one, we skip.
    # But now SCHEDULER might need to log to ivybound.log OR strategy_b.log depending on context.
    # This implies we need context-aware loggers.
    # Easiest fix: Append the log filename/profile to the logger name.
    
    if log_filename:
        # e.g. SCHEDULER_STRATEGY_B
        # But wait, modules call get_logger("SCHEDULER") at import time.
        # They don't know the filename yet.
        # We need to re-configure the logger or fetch a new one at runtime?
        # OR: We make get_logger robust to adding handlers if the file is different.
        
        # Simpler approach: Modules get a generic logger. We add handlers at MAIN based on profile?
        # But the modules import `logger` globally.
        # We will need to re-fetch logger inside the classes with the specific profile context.
        pass

    logger = logging.getLogger(name)
    
    # If logger already has handlers, check if we need to add a new file handler?
    # For simplicity, let's assume one process = one log file.
    # We can clear handlers if we re-init?
    
    # Let's support passing the filename.
    # If provided, we ensure that SPECIFIC file handler exists.
    
    if not log_filename:
         log_filename = "automation.log" # Default
         
    # Check if we already have a handler for this file
    has_file_handler = False
    for h in logger.handlers:
        if isinstance(h, logging.FileHandler):
            if Path(h.baseFilename).name == log_filename:
                has_file_handler = True
                
    if has_file_handler and logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter(
        '%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console Handler
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File Handler
    if not has_file_handler:
        log_path = LOGS_DIR / log_filename
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Telegram Handler (Critical Alerts)
    # Check if TELEGRAM_AVAILABLE and configured
    try:
        # Avoid circular import if possible, but safe here inside function or try-except top level
        # We'll use dynamic import to be safe
        import sys
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from telegram_alert import TelegramNotifier, TelegramLogHandler
        
        # Only add if not present
        if not any(isinstance(h, TelegramLogHandler) for h in logger.handlers):
            notifier = TelegramNotifier()
            if notifier.token and notifier.chat_id:
                tg_handler = TelegramLogHandler(notifier)
                tg_handler.setLevel(logging.ERROR) # Alert on ERROR and CRITICAL
                tg_handler.setFormatter(formatter)
                logger.addHandler(tg_handler)
    except Exception as e:
        # Don't crash logging if telegram fails setup
        pass
        # print(f"Failed to add Telegram handler: {e}")
    
    logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)
    logging.getLogger('apscheduler.scheduler').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('googleapiclient').setLevel(logging.WARNING)
    
    return logger
