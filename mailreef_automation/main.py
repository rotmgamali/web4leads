"""
Main entry point for the email automation system
Run this to start the automation
"""

import logging
import time
import sys
# ivyboundblast - Total Automation 🚀 (Deployment Trigger: Feb 4 2026)
import os

# Add project root to path BEFORE any other imports
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add project root to path BEFORE any other imports
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "mailreef_automation"))

# Debug: List root dir to see if automation_scrapers is there
print(f"DEBUG: ROOT_DIR is {ROOT_DIR}")
try:
    print(f"DEBUG: Root contents: {os.listdir(ROOT_DIR)}")
    scrapers_path = os.path.join(ROOT_DIR, 'automation_scrapers')
    if os.path.exists(scrapers_path):
        print(f"DEBUG: automation_scrapers dir exists. Contents: {os.listdir(scrapers_path)}")
    else:
        print(f"DEBUG: automation_scrapers dir NOT FOUND at {scrapers_path}")
except Exception as e:
    print(f"DEBUG: Error listing dir: {e}")

import automation_config
from mailreef_client import MailreefClient
from scheduler import EmailScheduler
from contact_manager import ContactManager
from monitor import DeliverabilityMonitor
from logger_util import get_logger
import lock_util

# Configure logging
logger = get_logger("SYSTEM_MAIN")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=str, default="IVYBOUND", help="Campaign profile (IVYBOUND or STRATEGY_B)")
    args = parser.parse_args()
    
    profile_name = args.profile.upper()
    
    # --- HARDENING: Configure Profile-Specific Logging ---
    # We must access config here to get the log file name
    log_file = automation_config.CAMPAIGN_PROFILES[profile_name].get("log_file", "automation.log")
    logger = get_logger("SYSTEM_MAIN", log_filename=log_file)
    
    lock_name = f'sender_{profile_name.lower()}'

    # Safety first: Ensure only one instance runs per profile
    lock_util.ensure_singleton(lock_name)
    
    try:
        logger.info(f"Initializing Mailreef Email Automation System (Profile: {profile_name})")
        logger.info(f"🔒 [HARDENING] Logging to isolated file: logs/{log_file}")
        
        class ConfigWrapper:
            pass
        
        cfg = ConfigWrapper()
        # Loading attributes from automation_config module to cfg object
        for name in dir(automation_config):
            if not name.startswith("__"):
                setattr(cfg, name, getattr(automation_config, name))
                
        # Check API key
        if not cfg.MAILREEF_API_KEY:
            logger.error("MAILREEF_API_KEY environment variable not set.")
            return

        # 🔍 Run Network Diagnostics (Cloud Debugging)
        try:
            from diagnose_network import run_diagnostics
            run_diagnostics()
        except ImportError:
            logger.warning("diagnose_network.py not found, skipping network check.")
        except Exception as e:
            logger.error(f"Error running diagnostics: {e}")
        
        mailreef = MailreefClient(
            api_key=cfg.MAILREEF_API_KEY,
            base_url=cfg.MAILREEF_API_BASE
        )
        
        # Init Scheduler with Sheets
        try:
            scheduler = EmailScheduler(
                mailreef_client=mailreef,
                config=cfg,
                campaign_profile=profile_name
            )
        except Exception as e:
            logger.critical(f"Failed to initialize scheduler (likely Sheets Auth error): {e}")
            return
        
        monitor = DeliverabilityMonitor(mailreef, cfg)
        
        # Validate setup
        logger.info("Validating inbox configuration...")
        try:
            inboxes = mailreef.get_inboxes()
            
            if len(inboxes) < cfg.TOTAL_INBOXES:
                logger.warning(f"Expected {cfg.TOTAL_INBOXES} inboxes, found {len(inboxes)}")
            
            # Check inbox health
            logger.info("Checking inbox health...")
            for inbox in inboxes:
                try:
                    # Optimized to avoid 95 API calls on startup if not strictly necessary,
                    # but following the prompt's structure:
                    status = mailreef.get_inbox_status(inbox["id"])
                    if status.get("deliverability_score", 100) < 80:
                        logger.warning(f"Inbox {inbox['id']} has low deliverability: {status}")
                except Exception as e:
                    logger.warning(f"Could not check status for inbox {inbox['id']}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to fetch inboxes: {e}")
            # Depending on severity, might exit or continue
        
        # Start the scheduler
        logger.info("Starting email scheduler...")
        scheduler.start()
        
        # Start monitoring
        logger.info("Starting deliverability monitoring...")
        monitor.start()
        
        # Start Reply Watcher (Background Thread)
        logger.info(f"Starting reply watcher for {profile_name}...")
        from reply_watcher import ReplyWatcher
        watcher = ReplyWatcher(
            mailreef_client=mailreef,
            config=cfg,
            profile_name=profile_name
        )
        import threading
        watcher_thread = threading.Thread(target=watcher.run_daemon, daemon=True)
        watcher_thread.start()
        
        logger.info(f"Email automation system is now running (Sheets-First Mode: {profile_name})")
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Critical System Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if 'scheduler' in locals(): scheduler.stop()
        if 'monitor' in locals(): monitor.stop()
        lock_util.release_lock(lock_name)
        # Watcher lock is handled by itself if run standalone, but here it's a thread.
        # Since we use daemon thread, it dies with main.
        # But we might want to release watcher lock if we acquired it?
        # ReplyWatcher.__init__ acquires a lock!
        # We should release it.
        # watcher.lock_name is available if watcher initialized.
        if 'watcher' in locals():
            lock_util.release_lock(watcher.lock_name)

if __name__ == "__main__":
    main()
