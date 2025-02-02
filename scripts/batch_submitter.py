import os
import json
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest

# Constants
LOGS_DIR = "logs"
SITEMAP_RECORD_FILE = os.path.join(LOGS_DIR, "processed_urls.json")
BATCH_FILE = os.path.join(LOGS_DIR, "batches_to_submit.json")

# Authenticate with Google Search Console API
def authenticate_google_service():
    try:
        credentials_info = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info, scopes=['https://www.googleapis.com/auth/indexing']
        )
        return build('indexing', 'v3', credentials=credentials)
    except Exception as e:
        print(f"[ERROR] Authentication failed: {e}")
        return None

# Load & Save JSON data
def load_json(file):
    return json.load(open(file)) if os.path.exists(file) else {}

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# Callback function for batch request
def callback(request_id, response, exception):
    if exception:
        print(f"[ERROR] Failed for request {request_id}: {exception}")
    else:
        print(f"[INFO] Successfully submitted: {response}")

# Submit URL batches
def submit_batches():
    service = authenticate_google_service()
    if not service:
        print("[ERROR] Google API Authentication failed. Exiting.")
        return

    batches = load_json(BATCH_FILE)
    processed_urls = load_json(SITEMAP_RECORD_FILE)

    for subdomain, batch_list in batches.items():
        print(f"[INFO] Submitting URLs for subdomain: {subdomain}")

        for batch in batch_list:
            batch_request = BatchHttpRequest(callback=callback)

            for url in batch:
                request_body = {"url": url, "type": "URL_UPDATED"}
                batch_request.add(service.urlNotifications().publish(body=request_body))
            
            print(f"[INFO] Sending batch of {len(batch)} URLs to Google.")
            batch_request.execute()
            time.sleep(1)  # Avoid API limits

            for url in batch:
                processed_urls[url] = time.strftime("%Y-%m-%dT%H:%M:%SZ")

            save_json(SITEMAP_RECORD_FILE, processed_urls)

    print("[INFO] Batch submission complete.")

if __name__ == "__main__":
    submit_batches()
