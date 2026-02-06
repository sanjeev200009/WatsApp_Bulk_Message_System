import logging
import sys
import json
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from .config import settings

def setup_logging():
    """
    Configure logging for the application.
    Sets up console handler, file handler, and result logger.
    """
    # Create logs directory if it doesn't exist
    log_file = Path(settings.LOG_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    result_file = Path(settings.RESULT_LOG_FILE)
    result_file.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    logger = logging.getLogger("whatsapp_cli")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # Clear existing handlers
    logger.handlers = []

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    ))
    logger.addHandler(console_handler)

    # File Handler
    file_handler = RotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(file_handler)

    return logger

class ResultLogger:
    """
    Specialized logger for recording send results in JSONL format.
    """
    def __init__(self):
        self.file_path = Path(settings.RESULT_LOG_FILE)
        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def log_result(self, 
                   user_id: str, 
                   phone: str, 
                   status: str, 
                   error: str = None, 
                   wa_message_id: str = None, 
                   http_code: int = None,
                   template_name: str = None):
        """
        Log a single send result to the JSONL file.
        """
        from .validators import mask_phone
        
        record = {
            "timestamp": datetime.now().isoformat(),
            "env": getattr(settings, 'ENV', 'unknown'),
            "user_id": str(user_id),
            "phone": mask_phone(phone),  # Always mask phone in logs
            "status": status,  # success, failed, skipped
            "error": error,
            "wa_message_id": wa_message_id,
            "http_code": http_code,
            "template_name": template_name or getattr(settings, 'TEMPLATE_NAME', 'unknown')
        }
        
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    
    def generate_daily_summary(self) -> dict:
        """Generate daily summary from result logs."""
        today = datetime.now().date().isoformat()
        
        summary = {
            "date": today,
            "env": getattr(settings, 'ENV', 'unknown'),
            "total_selected": 0,
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "error_codes": {},
            "skip_reasons": {}
        }
        
        if not self.file_path.exists():
            return summary
            
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        record_date = record.get("timestamp", "")[:10]  # Get YYYY-MM-DD part
                        
                        if record_date != today:
                            continue
                            
                        summary["total_selected"] += 1
                        
                        status = record.get("status", "unknown")
                        if status == "success":
                            summary["sent"] += 1
                        elif status == "failed":
                            summary["failed"] += 1
                            # Track error codes
                            http_code = record.get("http_code")
                            if http_code:
                                summary["error_codes"][str(http_code)] = summary["error_codes"].get(str(http_code), 0) + 1
                        elif status == "skipped":
                            summary["skipped"] += 1
                            # Track skip reasons
                            error = record.get("error", "unknown reason")
                            summary["skip_reasons"][error] = summary["skip_reasons"].get(error, 0) + 1
                            
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error generating daily summary: {e}")
            
        return summary
    
    def log_daily_summary(self):
        """Log daily summary to main log file."""
        summary = self.generate_daily_summary()
        
        logger.info("=== Daily Summary ===")
        logger.info(f"Environment: {summary['env']}")
        logger.info(f"Date: {summary['date']}")
        logger.info(f"Total selected: {summary['total_selected']}")
        logger.info(f"Sent: {summary['sent']}")
        logger.info(f"Failed: {summary['failed']}")
        logger.info(f"Skipped: {summary['skipped']}")
        
        if summary['error_codes']:
            logger.info(f"Error codes: {summary['error_codes']}")
        if summary['skip_reasons']:
            logger.info(f"Skip reasons: {summary['skip_reasons']}")
        
        logger.info("===================")

# Initialize loggers
logger = setup_logging()
result_logger = ResultLogger()
