"""
Database initialization script
"""
from contact_manager import ContactManager
import os

def init_db():
    print("Initializing database...")
    cm = ContactManager()
    cm.init_database()
    if os.path.exists("campaign.db"):
        print("campaign.db created successfully.")
    else:
        print("Failed to create campaign.db")

if __name__ == "__main__":
    init_db()
