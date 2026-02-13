import os
import sys
import logging

logger = logging.getLogger("LOCK_UTIL")

def ensure_singleton(process_name: str):
    """
    Ensure only one instance of the process is running using a PID file.
    process_name: 'sender' or 'watcher'
    """
    pid_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(pid_dir, exist_ok=True)
    
    pid_file = os.path.join(pid_dir, f"{process_name}.pid")
    pid = str(os.getpid())

    if os.path.isfile(pid_file):
        try:
            with open(pid_file, 'r') as f:
                old_pid_text = f.read().strip()
                if not old_pid_text:
                    raise ValueError("Empty PID file")
                old_pid = int(old_pid_text)
                
            # Check if process with old_pid is actually running
            # In Docker, PID 1 is common, so if current PID matches old PID, 
            # we assume it's a stale lock from a previous container and proceed.
            if old_pid != os.getpid():
                os.kill(old_pid, 0)
                
                # If no error, process is running
                print(f"❌ CRITICAL ERROR: Another instance of {process_name} is already running (PID: {old_pid}).")
                print(f"If you are sure it's not running, delete {pid_file} and try again.")
                logger.critical(f"Aborting start: {process_name} already running with PID {old_pid}")
                sys.exit(1)
            else:
                logger.debug(f"ℹ️ PID in lock matches current PID ({old_pid}). Overwriting stale lock.")
        except (OSError, ValueError, ProcessLookupError, UnboundLocalError):
            # Process is not running or PID file is invalid/corrupt
            pass

    # Write current PID to lock file
    with open(pid_file, 'w') as f:
        f.write(pid)
    
    logger.info(f"🔒 Locked {process_name} with PID {pid}")

def release_lock(process_name: str):
    """Release the lock file on exit."""
    pid_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    pid_file = os.path.join(pid_dir, f"{process_name}.pid")
    if os.path.isfile(pid_file):
        try:
            os.remove(pid_file)
            logger.info(f"🔓 Released {process_name} lock.")
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")
