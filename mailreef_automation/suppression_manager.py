import sqlite3
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Set, Optional

# Add project root to path for sheets_integration
import sys
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from mailreef_automation.logger_util import get_logger
from sheets_integration import GoogleSheetsClient
from mailreef_automation.automation_config import SUPPRESSION_SHEET_NAME

logger = get_logger("SUPPRESSION")

class SuppressionManager:
    """
    Manages a global suppression list to ensure no email address is ever contacted twice.
    Uses SQLite for high-speed local lookups and optionally syncs to Google Sheets for persistence.
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Place in the same dir as the script or a data dir
            db_path = os.path.join(ROOT_DIR, "suppression.db")
        
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """Initialize the SQLite database and table."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS suppressed_emails (
                    email TEXT PRIMARY KEY,
                    campaign TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
            # logger.info(f"💾 Suppression database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize suppression DB: {e}")

    def is_suppressed(self, email: str) -> bool:
        """Check if an email is in the suppression list."""
        if not email:
            return True
            
        email = email.lower().strip()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM suppressed_emails WHERE email = ?", (email,))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception as e:
            logger.error(f"Error checking suppression for {email}: {e}")
            return False

    def add_to_suppression(self, email: str, campaign: Optional[str] = None):
        """Add an email to the suppression list."""
        if not email:
            return
            
        email = email.lower().strip()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO suppressed_emails (email, campaign) VALUES (?, ?)",
                (email, campaign)
            )
            conn.commit()
            conn.close()
            # logger.debug(f"🔇 Added {email} to suppression list.")
        except Exception as e:
            logger.error(f"Error adding {email} to suppression: {e}")

    def bulk_add(self, emails: list, campaign: Optional[str] = None):
        """Add multiple emails at once for efficiency during backfill."""
        if not emails:
            return
            
        data = [(e.lower().strip(), campaign) for e in emails if e]
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT OR IGNORE INTO suppressed_emails (email, campaign) VALUES (?, ?)",
                data
            )
            conn.commit()
            conn.close()
            logger.info(f"✅ Bulk added {len(data)} emails to suppression.")
        except Exception as e:
            logger.error(f"Error in bulk suppression add: {e}")

    def sync_to_sheets(self):
        """
        Push local suppression list to a Google Sheet for persistence.
        """
        try:
            sheets = GoogleSheetsClient(input_sheet_name=SUPPRESSION_SHEET_NAME)
            sheets.setup_sheets()
            
            # Fetch current local items
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT email, campaign, added_at FROM suppressed_emails")
            local_items = cursor.fetchall()
            conn.close()
            
            if not local_items:
                return

            # Prepare data for sheet
            rows = [["Email", "Campaign", "Added At"]]
            for item in local_items:
                rows.append(list(item))
                
            # Full overwrite of the suppression sheet (Master list)
            sheets.input_sheet.clear()
            sheets.input_sheet.update('A1', rows)
            logger.info(f"📤 Successfully synced {len(local_items)} emails to '{SUPPRESSION_SHEET_NAME}'")
            
        except Exception as e:
            logger.error(f"❌ Failed to sync to sheets: {e}")

    def sync_from_sheets(self):
        """
        Pull from Master Suppression sheet to local DB. Useful on container startup.
        """
        try:
            sheets = GoogleSheetsClient(input_sheet_name=SUPPRESSION_SHEET_NAME)
            sheets.setup_sheets()
            
            records = sheets._fetch_all_records()
            if not records:
                return
                
            logger.info(f"📥 Pulling {len(records)} suppression records from sheets...")
            emails = [r.get('email') for r in records if r.get('email')]
            self.bulk_add(emails, campaign="SHEETS_SYNC")
            
        except Exception as e:
            logger.error(f"❌ Failed to sync from sheets: {e}")

if __name__ == "__main__":
    # Test
    sm = SuppressionManager()
    test_email = "test_duplicate@example.com"
    sm.add_to_suppression(test_email, "TEST")
    print(f"Is {test_email} suppressed? {sm.is_suppressed(test_email)}")
    print(f"Is unknown@example.com suppressed? {sm.is_suppressed('unknown@example.com')}")
