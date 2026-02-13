import sys
import os
import logging
import argparse
from datetime import datetime

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mailreef_automation.scheduler import EmailScheduler
from mailreef_automation.mailreef_client import MailreefClient
from mailreef_automation import automation_config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("TEST_PIPELINE")

def main():
    profile_name = "WEB4GURU_ACCOUNTANTS"
    
    # 1. Setup Config
    class ConfigWrapper:
        pass
    cfg = ConfigWrapper()
    for name in dir(automation_config):
        if not name.startswith("__"):
            setattr(cfg, name, getattr(automation_config, name))
            
    # OVERRIDE LIMITS FOR TEST
    cfg.DAILY_SEND_LIMIT = 2
    cfg.EMAILS_PER_INBOX_DAY_BUSINESS = 1
    cfg.EMAILS_PER_INBOX_DAY_WEEKEND = 1
    
    # 2. Init Client
    logger.info("Initializing Mailreef Client...")
    mailreef = MailreefClient(
        api_key=cfg.MAILREEF_API_KEY,
        base_url=cfg.MAILREEF_API_BASE
    )

    # 3. Init Scheduler
    logger.info(f"Initializing Scheduler for {profile_name}...")
    scheduler = EmailScheduler(
        mailreef_client=mailreef,
        config=cfg,
        campaign_profile=profile_name
    )
    
    # 4. Manual Execution of 2 Leads
    logger.info("🚀 Starting Test Execution (Limit: 2 Leads)...")
    
    # Get Inbox ID to use (any active one from the profile range)
    start_idx, end_idx = scheduler.profile_config.get("inbox_indices", (0, 95))
    all_inboxes = mailreef.get_inboxes()
    # Sort by ID
    all_inboxes.sort(key=lambda x: x['id'])
    target_inboxes = all_inboxes[start_idx:end_idx]
    
    if not target_inboxes:
        logger.error("No inboxes found for this profile!")
        return

    # Pick first 2 unique inboxes to simulate distribution if possible
    # Or just use first one twice? 
    # Let's try to use 2 different inboxes for better coverage.
    test_inboxes = target_inboxes[:2]

    processed_count = 0
    
    for inbox in test_inboxes:
        logger.info(f"Testing send from Inbox {inbox['id']} ({inbox.get('email')})...")
        
        # Select 1 prospect for Stage 1 (New Lead)
        # We assume we just imported fresh leads, so they are sequence_stage=1
        try:
            prospects = scheduler.select_prospects_for_send(inbox['id'], count=1, sequence_stage=1)
            
            if prospects:
                logger.info(f"Selected prospect: {prospects[0]['email']}")
                scheduler.execute_send(inbox['id'], prospects, sequence_number=1)
                processed_count += 1
            else:
                logger.warning(f"No prospects found for inbox {inbox['id']}")
                
        except Exception as e:
            logger.error(f"Error executing test for inbox {inbox['id']}: {e}")
            
        if processed_count >= 2:
            break
            
    if processed_count == 0:
        logger.error("❌ Test failed: No emails were sent.")
    else:
        logger.info(f"✅ Test complete. Sent {processed_count} emails.")

if __name__ == "__main__":
    main()
