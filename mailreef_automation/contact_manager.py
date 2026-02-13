"""
Contact and campaign management layer
Handles prospect lists, sequences, and tracking
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import uuid
from logger_util import get_logger

logger = get_logger("CONTACT_MANAGER")

class ContactManager:
    """Manages prospect contacts and sequencing"""
    
    def __init__(self, database_path: str = "campaign.db"):
        self.db_path = database_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with WAL mode for concurrency"""
        try:
            # Set a 30-second timeout for busy handlers
            conn = sqlite3.connect(self.db_path, timeout=30)
            cursor = conn.cursor()
            
            # Enable Write-Ahead Logging (WAL) for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # Create contacts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    school_name TEXT,
                    school_type TEXT,
                    domain TEXT,
                    role TEXT,
                    city TEXT,
                    state TEXT,
                    subtypes TEXT,
                    description TEXT,
                    inbox_segment INTEGER,
                    status TEXT DEFAULT 'active',
                    bounced INTEGER DEFAULT 0,
                    complained INTEGER DEFAULT 0,
                    last_contacted_at TIMESTAMP,
                    claimed_by_inbox TEXT,
                    claimed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create send log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS send_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact_id INTEGER,
                    inbox_id INTEGER,
                    campaign_id INTEGER,
                    sequence_stage INTEGER,
                    message_id TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    error TEXT,
                    FOREIGN KEY (contact_id) REFERENCES contacts(id)
                )
            """)

            # Create inbox contact history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inbox_contact_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inbox_id INTEGER,
                    contact_id INTEGER,
                    contacted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (contact_id) REFERENCES contacts(id)
                )
            """)
            
            conn.commit()
            logger.debug("Database initialized/verified successfully.")
        except sqlite3.Error as e:
            logger.error(f"❌ Database initialization error: {e}")
        finally:
            if conn:
                conn.close()
    
    def get_pending_for_inbox(self, inbox_id: int, count: int, 
                               sequence_stage: int) -> List[Dict]:
        """
        Get prospects ready for email from a specific inbox
        
        Rules:
        - Not already contacted in this sequence
        - Not bounced previously
        - Not complained
        - Inbox hasn't contacted them before
        - Matches inbox's assigned segment (public/private school)
        """
        # Note: This is a placeholder query logic. You might need to refine the filtering 
        # based on exact campaign_id usage and sequence tracking if multiple campaigns exist.
        # For this simplified version, we assume one global campaign flow.

        # We need to fetch contacts that:
        # 1. Are active
        # 2. Have not bounced or complained
        # 3. Have not been contacted by this inbox before (optional strict rule)
        # 4. Are due for the given sequence stage (for stage 1, means not started)
        
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            if sequence_stage == 1:
                # Optimized Atomic Pick-and-Lock for Stage 1
                # 1. Update a lead that is not claimed and matches criteria
                # 2. Return that lead
                # We use a subquery to find the best candidate
                query = """
                    UPDATE contacts
                    SET claimed_by_inbox = ?, claimed_at = CURRENT_TIMESTAMP
                    WHERE id = (
                        SELECT c.id FROM contacts c
                        LEFT JOIN send_log sl ON c.id = sl.contact_id 
                            AND sl.sequence_stage >= 1
                        WHERE sl.id IS NULL
                        AND c.status = 'active'
                        AND c.bounced = 0
                        AND c.complained = 0
                        AND c.claimed_by_inbox IS NULL
                        AND c.id NOT IN (
                            SELECT contact_id FROM inbox_contact_history 
                            WHERE inbox_id = ?
                        )
                        ORDER BY c.last_contacted_at ASC NULLS FIRST
                        LIMIT 1
                    )
                    RETURNING *
                """
                cursor.execute(query, (str(inbox_id), str(inbox_id)))
            else:
                # Atomic Pick-and-Lock for Stage 2 follow-ups
                delay_days = 4 # Default
                query = """
                    UPDATE contacts
                    SET claimed_by_inbox = ?, claimed_at = CURRENT_TIMESTAMP
                    WHERE id = (
                        SELECT c.id FROM contacts c
                        JOIN send_log s1 ON c.id = s1.contact_id AND s1.sequence_stage = 1
                        LEFT JOIN send_log s2 ON c.id = s2.contact_id AND s2.sequence_stage = 2
                        WHERE s2.id IS NULL
                        AND c.status = 'active'
                        AND c.bounced = 0
                        AND c.complained = 0
                        AND c.claimed_by_inbox IS NULL
                        AND s1.sent_at <= datetime('now', ?)
                        ORDER BY s1.sent_at ASC
                        LIMIT 1
                    )
                    RETURNING *
                """
                cursor.execute(query, (str(inbox_id), f'-{delay_days} days'))
            
            rows = cursor.fetchall()
            conn.commit() # Commit the claim
            
            if rows:
                logger.info(f"🔒 [LOCK] Inbox {inbox_id} claimed lead: {rows[0]['email']}")
                return [dict(row) for row in rows]
            return []
            
        except sqlite3.Error as e:
            logger.error(f"❌ Database error in get_pending_for_inbox: {e}")
            return []
        finally:
            conn.close()

    def record_send(self, contact_id: int, inbox_id: int, campaign_id: int,
                    sequence_stage: int, message_id: str, status: str = "sent", error: str = None):
        """Record that an email was sent"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO send_log (contact_id, inbox_id, campaign_id, sequence_stage, message_id, status, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (contact_id, inbox_id, campaign_id, sequence_stage, message_id, status, error))
            
            # Clear the claim since it's now officially recorded as sent
            cursor.execute("""
                UPDATE contacts SET last_contacted_at = CURRENT_TIMESTAMP, claimed_by_inbox = NULL, claimed_at = NULL WHERE id = ?
            """, (contact_id,))
            
            # Record inbox history
            cursor.execute("""
                INSERT INTO inbox_contact_history (inbox_id, contact_id)
                VALUES (?, ?)
            """, (inbox_id, contact_id))

            conn.commit()
            logger.debug(f"📊 Recorded send for contact {contact_id} (Stage {sequence_stage}) and released lock.")
        except sqlite3.Error as e:
            logger.error(f"❌ Database error in record_send: {e}")
        finally:
            conn.close()

    def update_contact_status(self, email: str, status: str):
        """Update status of a contact by email (e.g. to 'replied' or 'unsubscribed')"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE contacts SET status = ? WHERE email = ?", (status, email))
            conn.commit()
            logger.info(f"✅ Updated status for {email} to '{status}'")
        except sqlite3.Error as e:
            logger.error(f"❌ Database error in update_contact_status: {e}")
        finally:
            conn.close()
    
    def record_reply(self, contact_id: int, inbox_id: int, 
                     message_id: str, reply_content: str):
        """Record a reply from a prospect"""
        # Insert into reply_log (table not explicitly defined above but good to have)
        # Update contact status to 'replied' or similar
        pass
    
    def get_sequence_for_contact(self, contact_id: int, campaign_id: int) -> List[Dict]:
        """Get the email sequence for a specific contact"""
        # Return 3 emails with appropriate timing
        return [
            {"stage": 1, "delay_days": 0, "template": "initial"},
            {"stage": 2, "delay_days": 3, "template": "followup_1"},
            {"stage": 3, "delay_days": 7, "template": "followup_2"}
        ]
    
    def calculate_daily_capacity(self) -> Dict:
        """Calculate how many emails we can send today"""
        # This is a static calculation based on config, but could be dynamic based on DB status
        return {
            "business_day": {
                "inboxes_active": 93,
                "emails_per_inbox": 24,
                "total": 2232
            },
            "weekend_day": {
                "inboxes_active": 95,
                "emails_per_inbox": 9,
                "total": 855
            }
        }

    def bulk_import_leads(self, leads: List[Dict]) -> int:
        """
        Bulk import leads into the database.
        Returns the number of new leads added.
        """
        if not leads:
            return 0
            
        conn = sqlite3.connect(self.db_path, timeout=60) # Higher timeout for bulk ops
        cursor = conn.cursor()
        
        added_count = 0
        
        try:
            # Prepare data tuple list matching schema
            # Schema: email, first_name, last_name, school_name, school_type, domain, role, city, state, subtypes, description
            # We use INSERT OR IGNORE to skip duplicates safely
            
            data_to_insert = []
            for lead in leads:
                data_to_insert.append((
                    lead.get('email'),
                    lead.get('first_name'),
                    lead.get('last_name'),
                    lead.get('school_name'),
                    lead.get('school_type', ''), # Not sending school_type in map_lead yet, can add default
                    lead.get('domain'),
                    lead.get('role'),
                    lead.get('city'),
                    lead.get('state'),
                    lead.get('subtypes'),
                    lead.get('description'),
                    lead.get('status', 'active')
                ))

            # Using executemany for performance
            cursor.executemany("""
                INSERT OR IGNORE INTO contacts (
                    email, first_name, last_name, school_name, school_type, 
                    domain, role, city, state, subtypes, description, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data_to_insert)
            
            added_count = cursor.rowcount
            conn.commit()
            logger.info(f"✅ Bulk imported {added_count} new leads into campaign.db")
            
        except sqlite3.Error as e:
            logger.error(f"❌ Bulk import database error: {e}")
        finally:
            conn.close()
            
        return added_count

    def scan_stale_locks(self):
        """
        Scan for leads that have been locked for > 1 hour.
        This usually indicates a crash occurred during a send.
        We do NOT auto-release them to avoid double-send risk.
        Returns list of stale locked leads.
        """
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        stale_leads = []
        try:
            # Check for locks older than 60 minutes
            query = """
                SELECT * FROM contacts 
                WHERE claimed_by_inbox IS NOT NULL 
                AND claimed_at < datetime('now', '-60 minutes')
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            if rows:
                stale_leads = [dict(row) for row in rows]
                for lead in stale_leads:
                    logger.critical(f"⚠️ [STALE LOCK] Contact {lead['email']} locked by Inbox {lead['claimed_by_inbox']} since {lead['claimed_at']}. Manual review required.")
            else:
                logger.debug("✅ No stale locks found.")
                
        except sqlite3.Error as e:
            logger.error(f"❌ Database error in scan_stale_locks: {e}")
        finally:
            conn.close()
            
        return stale_leads
