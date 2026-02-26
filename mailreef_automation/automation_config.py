"""
Configuration for 50,000/month Mailreef cold email automation
Target: School administrators (public + private schools)
"""
import os
from dotenv import load_dotenv

# Add project root to path for .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# ==================== TARGET METRICS ====================
MONTHLY_EMAIL_TARGET = 50000
BUSINESS_DAYS_PER_MONTH = 22
WEEKEND_DAYS_PER_MONTH = 8

# ==================== INBOX CONFIGURATION ====================
TOTAL_INBOXES = 95
INBOXES_PER_DAY_BUSINESS = 95  # Maximize: All inboxes active
INBOXES_PER_DAY_WEEKEND = 95   # All inboxes active on weekends
INBOX_PAUSED_IDS = []          # Dynamic pause list for health monitoring

EMAILS_PER_INBOX_DAY_BUSINESS = 50 # Scaled from 25
EMAILS_PER_INBOX_DAY_WEEKEND = 50  # Scaled from 9

# ==================== TELEGRAM ALERTS ====================
TELEGRAM_BOT_TOKEN = "7224632370:AAFgWL94FbffWBO6COKnYyhrMKymFJQV0po"
TELEGRAM_CHAT_ID = "7059103286" # Auto-discovered (Andrew Rollins)

# ==================== SENDING WINDOWS (24-hour format, EST) ====================
# Business days: 6:00 - 19:30 (avoid 11:00-14:00 busy hours)
BUSINESS_DAY_WINDOWS = [
    {"start": 6, "end": 7, "emails_per_inbox": 4},
    {"start": 7, "end": 8, "emails_per_inbox": 4},
    {"start": 8, "end": 9, "emails_per_inbox": 6},
    {"start": 9, "end": 10, "emails_per_inbox": 8},
    {"start": 10, "end": 11, "emails_per_inbox": 6},
    {"start": 12, "end": 13, "emails_per_inbox": 6},
    {"start": 15, "end": 16, "emails_per_inbox": 4},
    {"start": 16, "end": 17, "emails_per_inbox": 4},
    {"start": 17, "end": 18, "emails_per_inbox": 4},
    {"start": 18, "end": 19, "emails_per_inbox": 4},
]

# Weekend days: Match Business days for maximum persistent volume
WEEKEND_DAY_WINDOWS = BUSINESS_DAY_WINDOWS

# Quiet hours: No sending
QUIET_HOURS = {"start": 21, "end": 5}

# ==================== MAILREEF API CONFIG ====================
MAILREEF_API_BASE = os.environ.get("MAILREEF_API_BASE") or "https://api.mailreef.com"
MAILREEF_API_KEY = os.environ.get("MAILREEF_API_KEY")

# Check if key is missing and try to reload if local
if not MAILREEF_API_KEY:
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
    MAILREEF_API_KEY = os.environ.get("MAILREEF_API_KEY")

# ==================== SUPPRESSION ====================
SUPPRESSION_SHEET_NAME = "Master Suppression List"

# ==================== CAMPAIGN SETTINGS ====================
CAMPAIGN_CONFIG = {
    "sequence_length": 1,  # Single email campaign
    "days_between_sequence": 4,  # Day 0, Day 4
    "max_retries": 3,
    "retry_delay_hours": 24,
    "stop_on_hard_bounce": True,
    "pause_on_complaint": True,
}

# ==================== DAY MAPPING ====================
# 0 = Monday, 6 = Sunday
BUSINESS_DAY_INDICES = [0, 1, 2, 3, 4]  # Mon-Fri
WEEKEND_DAY_INDICES = [5, 6]  # Sat-Sun

# ==================== CAMPAIGN PROFILES ====================
# Inbox Indices: Slicing logic [start, end)
CAMPAIGN_PROFILES = {
    "IVYBOUND": {
        "input_sheet": "Ivy Bound - Campaign Leads",
        "replies_sheet": "Ivy Bound - Reply Tracking",
        "replies_sheet_id": "1jeLkdufaMub4rylaPnoTQZwDiLpHmut5hcQQStl8UxI",
        "send_window_group": "default",
        "inbox_indices": (0, 50), # Uses first 50 inboxes
        "log_file": "ivybound.log",
        "templates_dir": "templates",
        "campaign_type": "school"
    },
    "STRATEGY_B": {
        "input_sheet": "Web4Guru - Campaign Leads",
        "replies_sheet": "Web4Guru - Reply Tracking",
        "send_window_group": "default",
        "campaign_type": "b2b",
        "inbox_indices": (95, 190), # Uses the 95 birdsgeese inboxes (verified 95-190)
        "log_file": "web4guru.log",
        "templates_dir": "templates_strategy_b",
        "archetypes": {
            "executive": ["ceo", "founder", "owner", "president", "partner", "vp", "executive"],
            "marketing": ["marketing", "growth", "branding", "digital"],
            "sales": ["sales", "revenue", "business development", "partnerships"],
            "operations": ["operations", "coo", "manager", "principal"]
        }
    },
    "WEB4GURU_ACCOUNTANTS": {
        "input_sheet": "Web4Guru Accountants - Campaign Leads",
        "replies_sheet": "Web4Guru Accountants - Reply Tracking",
        "send_window_group": "default", # Same window as others
        "campaign_type": "b2b",
        "inbox_indices": (95, 190), # Moved to birdsgeese inboxes (95-190)
        "log_file": "web4guru_accountants.log",
        "templates_dir": "templates/web4guru/accountants", # Base dir for templates
        "reply_prompt": "prompts/web4guru_accountant_reply.txt",
        # "auto_reply_template": "b2b/general/email_2.txt" # DISABLED by user request
    }
}

# ==================== INBOX ROTATION ====================
# Rotation is now handled dynamically in scheduler.py

