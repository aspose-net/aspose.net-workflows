import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Constants
LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

SITEMAP_RECORD_FILE = os.path.join(LOGS_DIR, "processed_urls.json")
BATCH_FILE = os.path.join(LOGS_DIR, "batches_to_submit.json")
SUBDOMAINS = [
    "www.aspose.net", "products.aspose.net", "blog.aspose.net",
    "docs.aspose.net", "kb.aspose.net", "about.aspose.net",
    "reference.aspose.net", "websites.aspose.net"
]
BATCH_SIZE = 1000
REPROCESS_DAYS_LIMIT = 30  

# Extract nested sitemaps (including multilingual ones)
def extract_sitemaps_from_index(sitemap_url):
    try:
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code == 200:
            tree = ET.ElementTree(ET.fromstring(response.text))
            return [url.text for url in tree.findall(".//{*}loc")]
    except Exception as e:
        print(f"[ERROR] Failed to fetch sitemaps from {sitemap_url}: {e}")
    return []

# Fetch all sitemaps for a subdomain (including multilingual)
def get_all_sitemaps(subdomain):
    index_sitemap_url = f"https://{subdomain}/sitemap.xml"
    extracted_sitemaps = [index_sitemap_url]

    try:
        response = requests.get(index_sitemap_url, timeout=10)
        if response.status_code == 200:
            tree = ET.ElementTree(ET.fromstring(response.text))
            extracted_sitemaps.extend([sitemap.text for sitemap in tree.findall(".//{*}loc")])

            # Extract multilingual & nested sitemaps
            for sitemap in extracted_sitemaps:
                multilingual_sitemaps = extract_sitemaps_from_index(sitemap)
                extracted_sitemaps.extend(multilingual_sitemaps)
    except Exception as e:
        print(f"[ERROR] Failed to extract sub-sitemaps from {index_sitemap_url}: {e}")
    
    return extracted_sitemaps

# Extract URLs from sitemap
def extract_sitemap_urls(sitemap_url):
    try:
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code == 200:
            tree = ET.ElementTree(ET.fromstring(response.text))
            return [(url.text, url.find("../{*}lastmod").text if url.find("../{*}lastmod") else None) for url in tree.findall(".//{*}loc")]
    except Exception as e:
        print(f"[ERROR] Failed to fetch {sitemap_url}: {e}")
    return []

# Load & Save JSON data
def load_json(file):
    return json.load(open(file)) if os.path.exists(file) else {}

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# Prepare URL batches for submission
def prepare_batches():
    processed_urls = load_json(SITEMAP_RECORD_FILE)
    batches = {}

    for subdomain in SUBDOMAINS:
        print(f"[INFO] Processing subdomain: {subdomain}")
        all_sitemaps = get_all_sitemaps(subdomain)
        urls_to_submit = []

        for sitemap_url in all_sitemaps:
            extracted_urls = extract_sitemap_urls(sitemap_url)
            for url, lastmod in extracted_urls:
                lastmod_date = datetime.strptime(lastmod, "%Y-%m-%d") if lastmod else None
                last_processed = processed_urls.get(url)

                # Include only URLs not processed in the last 30 days
                if not last_processed or (lastmod_date and last_processed < (datetime.now() - timedelta(days=REPROCESS_DAYS_LIMIT)).isoformat()):
                    urls_to_submit.append(url)

        batches[subdomain] = [urls_to_submit[i:i + BATCH_SIZE] for i in range(0, len(urls_to_submit), BATCH_SIZE)]

    save_json(BATCH_FILE, batches)
    print(f"[INFO] Batches prepared for submission.")

if __name__ == "__main__":
    prepare_batches()
