import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Ensure the backend directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import sync_data_job

if __name__ == "__main__":
    print("==================================================")
    print("Testing the sync data job / scheduler task locally")
    print("==================================================")
    try:
        sync_data_job()
        print("==================================================")
        print("Success: Local scheduler sync job executed successfully!")
        print("==================================================")
    except Exception as e:
        print(f"Error running scheduler sync job: {e}")
        sys.exit(1)
