import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Constants
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

SITEMAP_RECORD_FILE = os.path.join(LOGS_DIR, "processed_urls.json")
BATCH_FILE = os.path.join(LOGS_DIR, "batches_to_submit.json")
SUBDOMAINS = [
    "www.aspose.net", "products.aspose.net", "blog.aspose.net",
    "docs.aspose.net", "kb.aspose.net", "about.aspose.net",
    "reference.aspose.net", "websites.aspose.net"
]
FAMILY_SUBDOMAINS = [
    "kb.aspose.net", "docs.aspose.net", "products.aspose.net", "reference.aspose.net"
]
FAMILIES = ['words', 'pdf', 'cells', 'imaging', 'barcode', 'tasks', 'ocr', 'cad', 'html', 'zip', 'page', 'psd', 'tex']
BATCH_SIZE = 1000
REPROCESS_DAYS_LIMIT = 30  

# Extract nested sitemaps (including multilingual ones)
def extract_sitemaps_from_index(sitemap_url):
    try:
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code != 200:
            print(f"[ERROR] {sitemap_url} returned status {response.status_code}")
            return []
        
        content = response.text.strip()
        if not content.startswith("<?xml"):
            print(f"[ERROR] {sitemap_url} is not a valid XML sitemap. First 100 chars: {content[:100]}")
            return []

        tree = ET.ElementTree(ET.fromstring(content))
        return [url.text for url in tree.findall(".//{*}loc")]
    except Exception as e:
        print(f"[ERROR] Failed to fetch sitemaps from {sitemap_url}: {e}")
    return []

# Fetch all sitemaps for a subdomain (including multilingual and family-based ones)
def get_all_sitemaps(subdomain):
    index_sitemap_url = f"https://{subdomain}/sitemap.xml"
    extracted_sitemaps = [index_sitemap_url]

    try:
        response = requests.get(index_sitemap_url, timeout=10)
        if response.status_code != 200:
            print(f"[ERROR] Failed to fetch {index_sitemap_url}, Status Code: {response.status_code}")
            return []

        content = response.text.strip()
        if not content.startswith("<?xml"):
            print(f"[ERROR] {index_sitemap_url} is not valid XML. First 100 chars: {content[:100]}")
            return []

        tree = ET.ElementTree(ET.fromstring(content))
        extracted_sitemaps.extend([sitemap.text for sitemap in tree.findall(".//{*}loc")])

        # Extract multilingual & nested sitemaps
        for sitemap in extracted_sitemaps.copy():
            multilingual_sitemaps = extract_sitemaps_from_index(sitemap)
            extracted_sitemaps.extend(multilingual_sitemaps)

        # If the subdomain has family-based sitemaps, check for them
        if subdomain in FAMILY_SUBDOMAINS:
            for family in FAMILIES:
                family_sitemap_url = f"https://{subdomain}/{family}/sitemap.xml"
                response = requests.head(family_sitemap_url, timeout=5)  # Lightweight check
                if response.status_code == 200:
                    print(f"[INFO] Found family-based sitemap: {family_sitemap_url}")
                    extracted_sitemaps.append(family_sitemap_url)

                    # Extract multilingual & nested sitemaps from family sitemap
                    multilingual_sitemaps = extract_sitemaps_from_index(family_sitemap_url)
                    extracted_sitemaps.extend(multilingual_sitemaps)

    except Exception as e:
        print(f"[ERROR] Failed to extract sub-sitemaps from {index_sitemap_url}: {e}")
    
    return extracted_sitemaps

# Extract URLs from sitemap
def extract_sitemap_urls(sitemap_url):
    try:
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code != 200:
            print(f"[ERROR] {sitemap_url} returned status {response.status_code}")
            return []
        
        content = response.text.strip()
        if not content.startswith("<?xml"):
            print(f"[ERROR] {sitemap_url} is not valid XML. First 100 chars: {content[:100]}")
            return []

        tree = ET.ElementTree(ET.fromstring(content))
        urls = []
        for url_elem in tree.findall(".//{*}loc"):
            url = url_elem.text
            lastmod_elem = url_elem.find("./../{*}lastmod")
            lastmod = lastmod_elem.text if lastmod_elem is not None else None
            urls.append((url, lastmod))
        return urls
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
                try:
                    lastmod_date = datetime.strptime(lastmod, "%Y-%m-%d") if lastmod else None
                except ValueError:
                    lastmod_date = None

                last_processed = processed_urls.get(url)

                # Include only URLs not processed in the last 30 days
                if not last_processed or (lastmod_date and last_processed < (datetime.now() - timedelta(days=REPROCESS_DAYS_LIMIT)).isoformat()):
                    urls_to_submit.append(url)

        batches[subdomain] = [urls_to_submit[i:i + BATCH_SIZE] for i in range(0, len(urls_to_submit), BATCH_SIZE)]

    save_json(BATCH_FILE, batches)
    print(f"[INFO] Batches prepared for submission.")

if __name__ == "__main__":
    prepare_batches()
