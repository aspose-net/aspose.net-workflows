import json
import sys
import os
import subprocess
import time
from datetime import datetime

STATUS_FILE = "reference/status.json"
MAX_RETRIES = 5  # Maximum retries to avoid race conditions
RETRY_DELAY = 5  # Wait time (seconds) before retrying

if len(sys.argv) < 3:
    print("Error: FAMILY and VERSION arguments are required.")
    sys.exit(1)

family_name = sys.argv[1]  # e.g., "Aspose.Slides"
version = sys.argv[2]  # e.g., "25.2.0"
processed_date = datetime.now().strftime("%Y-%m-%d")

# Ensure latest changes are pulled to avoid overwriting updates from other parallel jobs
for attempt in range(MAX_RETRIES):
    try:
        subprocess.run(["git", "pull"], check=True)
        
        # Load status.json
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                status_data = json.load(f)
        except FileNotFoundError:
            print(f"ERROR: {STATUS_FILE} not found. Creating a new status file.")
            status_data = {}
        except json.JSONDecodeError:
            print(f"ERROR: Failed to parse {STATUS_FILE}. JSON format might be corrupted.")
            sys.exit(1)

        # Update or add family entry
        if family_name in status_data:
            status_data[family_name]["version"] = version
            status_data[family_name]["processed"] = processed_date
            print(f"DEBUG: Updated {family_name} -> version: {version}, processed: {processed_date}")
        else:
            print(f"WARNING: {family_name} not found in {STATUS_FILE}. Adding new entry.")
            status_data[family_name] = {"nuget": family_name, "version": version, "processed": processed_date}

        # Write changes
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2)

        print(f"DEBUG: Successfully updated {STATUS_FILE}.")

        # Commit and push changes
        subprocess.run(["git", "add", STATUS_FILE], check=True)
        subprocess.run(["git", "commit", "-m", f"Update processed status for {family_name}"], check=True)
        subprocess.run(["git", "push"], check=True)
        
        print(f"DEBUG: Successfully pushed status update for {family_name}.")
        break  # Exit retry loop on success

    except subprocess.CalledProcessError:
        print(f"WARNING: Git push failed on attempt {attempt + 1}/{MAX_RETRIES}. Retrying...")
        time.sleep(RETRY_DELAY)  # Wait before retrying

else:
    print(f"ERROR: Failed to update {STATUS_FILE} after {MAX_RETRIES} attempts.")
    sys.exit(1)
