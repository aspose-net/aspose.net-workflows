import os
import json
import time
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Constants
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

SITEMAP_RECORD_FILE = os.path.join(LOGS_DIR, "processed_urls.json")
BATCH_FILE = os.path.join(LOGS_DIR, "batches_to_submit.json")
INDEXING_ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"

# Authenticate with Google Indexing API
def authenticate_google_service():
    try:
        credentials_info = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info, scopes=['https://www.googleapis.com/auth/indexing']
        )
        return credentials
    except Exception as e:
        print(f"[ERROR] Authentication failed: {e}")
        return None

# Load & Save JSON data
def load_json(file):
    return json.load(open(file)) if os.path.exists(file) else {}

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# Submit URL to Google Indexing API with exponential backoff
def submit_url(service, url, attempt=1):
    if attempt > 5:  # Stop after 5 failed attempts
        print(f"[ERROR] Skipping {url} after multiple failures.")
        return False

    try:
        request_body = {"url": url, "type": "URL_UPDATED"}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {service.token}"
        }

        response = requests.post(INDEXING_ENDPOINT, json=request_body, headers=headers)

        if response.status_code == 200:
            print(f"[INFO] Successfully submitted: {url}")
            return True
        elif response.status_code == 429:  # Rate limit exceeded
            wait_time = 2 ** attempt  # Exponential backoff
            print(f"[WARNING] Rate limit exceeded. Retrying {url} in {wait_time} seconds...")
            time.sleep(wait_time)
            return submit_url(service, url, attempt + 1)
        else:
            print(f"[ERROR] Failed to submit {url}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Exception while submitting {url}: {e}")
        return False

# Submit URL batches
def submit_batches():
    credentials = authenticate_google_service()
    if not credentials:
        print("[ERROR] Google API Authentication failed. Exiting.")
        return

    processed_urls = load_json(SITEMAP_RECORD_FILE)
    batches = load_json(BATCH_FILE)

    for subdomain, batch_list in batches.items():
        print(f"[INFO] Submitting URLs for subdomain: {subdomain}")

        for batch in batch_list:
            success_count = 0
            for url in batch:
                if submit_url(credentials, url):
                    processed_urls[url] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                    success_count += 1
                    time.sleep(1)  # Avoid API limits
            
            print(f"[INFO] Successfully submitted {success_count} URLs for {subdomain}.")
            save_json(SITEMAP_RECORD_FILE, processed_urls)

    print("[INFO] Batch submission complete.")

if __name__ == "__main__":
    submit_batches()
