import os
import logging
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Config:
    """Central configuration for OmniBot Platform."""
    
    # API Keys (from environment)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    MAILREEF_API_KEY = os.getenv("MAILREEF_API_KEY")
    SMARTLEAD_API_KEY = os.getenv("SMARTLEAD_API_KEY")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")  # Corrected from SERPAPI
    
    # Campaign Settings
    DAILY_SEND_LIMIT = int(os.getenv("DAILY_SEND_LIMIT", 100))
    RATE_LIMIT = float(os.getenv("RATE_LIMIT", 1.0))
    TIMEOUT = int(os.getenv("TIMEOUT", 30))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))

    # Monitoring
    PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", 8000))

    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    CACHE_DIR = os.path.join(DATA_DIR, "cache")
    LOGS_DIR = os.path.join(DATA_DIR, "logs")
    
    # Pipeline-specific directories
    LEADS_DIR = os.path.join(BASE_DIR, "leads")
    SCHOOL_LEADS_DIR = os.path.join(LEADS_DIR, "school")
    REAL_ESTATE_LEADS_DIR = os.path.join(LEADS_DIR, "real_estate")
    PAC_LEADS_DIR = os.path.join(LEADS_DIR, "pac")
    
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

    @classmethod
    def validate(cls):
        """Validates critical configuration presence."""
        missing = []
        if not cls.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        if not cls.SERPER_API_KEY:
            missing.append("SERPER_API_KEY")
        
        # Create directories if they don't exist
        for directory in [
            cls.DATA_DIR, cls.CACHE_DIR, cls.LOGS_DIR, cls.LEADS_DIR,
            cls.SCHOOL_LEADS_DIR, cls.REAL_ESTATE_LEADS_DIR, cls.PAC_LEADS_DIR,
            cls.TEMPLATES_DIR
        ]:
            os.makedirs(directory, exist_ok=True)

        if missing:
            logger.warning(f"Missing configuration keys: {', '.join(missing)}")

    @classmethod
    def get_secret(cls, key: str) -> Optional[str]:
        """Retrieves a secret from environment."""
        return os.getenv(key)


class PipelineConfig:
    """Pipeline-specific settings."""
    
    # Volume Configuration
    MONTHLY_ACTIVE_EMAIL_LIMIT = int(os.getenv("MONTHLY_ACTIVE_EMAIL_LIMIT", 66000))
    MONTHLY_WARMING_EMAIL_LIMIT = int(os.getenv("MONTHLY_WARMING_EMAIL_LIMIT", 33000))
    
    # Warmup Configuration
    WARMUP_DAYS = 14  # Days of warming before cold sends allowed
    WARMUP_START_DATE = os.getenv("WARMUP_START_DATE")  # Format: YYYY-MM-DD
    
    @classmethod
    def is_warmup_complete(cls) -> bool:
        """Check if 14-day warmup period is complete."""
        from datetime import datetime
        if not cls.WARMUP_START_DATE:
            logger.warning("WARMUP_START_DATE not set - blocking cold sends")
            return False
        try:
            start = datetime.strptime(cls.WARMUP_START_DATE, "%Y-%m-%d")
            days_elapsed = (datetime.now() - start).days
            if days_elapsed < cls.WARMUP_DAYS:
                logger.info(f"Warmup in progress: Day {days_elapsed}/{cls.WARMUP_DAYS}")
                return False
            return True
        except ValueError:
            logger.error(f"Invalid WARMUP_START_DATE format: {cls.WARMUP_START_DATE}")
            return False
    
    # Distribution across 3 campaigns
    SCHOOL_CAMPAIGN_ALLOCATION = 0.33
    REAL_ESTATE_CAMPAIGN_ALLOCATION = 0.33
    PAC_CAMPAIGN_ALLOCATION = 0.34
    
    # Inbox Configuration
    TOTAL_INBOXES = int(os.getenv("TOTAL_INBOXES", 200))
    INBOXES_PER_CAMPAIGN = TOTAL_INBOXES // 3
    
    # Email Sequence Configuration
    EMAILS_PER_SEQUENCE = 3
    SEQUENCE_DAYS_BETWEEN_EMAILS = [0, 4, 11]  # Day 0, Day 4, Day 11
