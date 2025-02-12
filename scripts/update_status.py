import json
import sys
import os
import subprocess
import time
from datetime import datetime

STATUS_FILE = "reference/status.json"
MAX_RETRIES = 5  # Maximum retries for avoiding race conditions
RETRY_DELAY = 5  # Initial wait time (seconds) before retrying
BACKOFF_MULTIPLIER = 2  # Increase wait time on each retry

if len(sys.argv) < 3:
    print("Error: FAMILY and VERSION arguments are required.")
    sys.exit(1)

family_name = sys.argv[1]  # e.g., "Aspose.Slides"
version = sys.argv[2]  # e.g., "25.2.0"
processed_date = datetime.now().strftime("%Y-%m-%d")

for attempt in range(MAX_RETRIES):
    try:
        # ✅ Ensure the latest changes before modifying the file
        subprocess.run(["git", "pull", "--rebase"], check=True)

        # ✅ Load status.json safely
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                status_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"ERROR: Failed to load {STATUS_FILE}. Creating a new file.")
            status_data = {}

        # ✅ Update the entry for the processed family
        if family_name in status_data:
            status_data[family_name]["version"] = version
            status_data[family_name]["processed"] = processed_date
            print(f"DEBUG: Updated {family_name} -> version: {version}, processed: {processed_date}")
        else:
            print(f"WARNING: {family_name} not found in {STATUS_FILE}. Adding new entry.")
            status_data[family_name] = {"nuget": family_name, "version": version, "processed": processed_date}

        # ✅ Write updates safely
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2)

        print(f"DEBUG: Successfully updated {STATUS_FILE}.")

        # ✅ Add and commit the changes with a retry loop
        for push_attempt in range(MAX_RETRIES):
            subprocess.run(["git", "add", STATUS_FILE], check=True)
            commit_result = subprocess.run(["git", "commit", "-m", f"Update processed status for {family_name}"], check=False)

            if commit_result.returncode == 0:  # Only attempt to push if commit succeeds
                push_result = subprocess.run(["git", "push"], check=False)

                if push_result.returncode == 0:
                    print(f"DEBUG: Successfully pushed status update for {family_name}.")
                    break  # Exit the loop on success

                print(f"WARNING: Git push failed (attempt {push_attempt + 1}/{MAX_RETRIES}). Retrying...")
                subprocess.run(["git", "pull", "--rebase"], check=True)  # Pull latest before retrying
                time.sleep(RETRY_DELAY * (BACKOFF_MULTIPLIER ** push_attempt))  # Exponential backoff

            else:
                print(f"WARNING: No changes to commit for {family_name}. Skipping push.")
                break  # No need to retry if there's nothing to push

        else:
            print(f"ERROR: Git push failed after {MAX_RETRIES} attempts.")
            sys.exit(1)

        break  # Exit the retry loop on success

    except subprocess.CalledProcessError:
        print(f"WARNING: Git operation failed on attempt {attempt + 1}/{MAX_RETRIES}. Retrying...")
        time.sleep(RETRY_DELAY * (BACKOFF_MULTIPLIER ** attempt))  # Exponential backoff

else:
    print(f"ERROR: Failed to update {STATUS_FILE} after {MAX_RETRIES} attempts.")
    sys.exit(1)
