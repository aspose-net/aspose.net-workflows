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
BATCH_SIZE = 500  # ✅ Decreased batch size to 500
REPROCESS_DAYS_LIMIT = 30  

# Extract nested sitemaps (including multilingual ones)
def extract_sitemaps_from_index(sitemap_url):
    """Extracts only sitemap URLs (.xml) from an index sitemap."""
    try:
        if not sitemap_url.endswith(".xml"):
            return []

        response = requests.get(sitemap_url, timeout=10)
        if response.status_code != 200:
            return []

        content = response.text.strip()
        if not content.startswith("<?xml"):
            return []

        tree = ET.ElementTree(ET.fromstring(content))
        return [url.text for url in tree.findall(".//{*}loc") if url.text.endswith(".xml")]
    except Exception:
        return []

# Fetch all sitemaps for a subdomain
def get_all_sitemaps(subdomain):
    """Gets all sitemaps for a given subdomain, including multilingual and family-based sitemaps."""
    index_sitemap_url = f"https://{subdomain}/sitemap.xml"
    extracted_sitemaps = [index_sitemap_url]

    try:
        response = requests.get(index_sitemap_url, timeout=10)
        if response.status_code != 200:
            return []

        content = response.text.strip()
        if not content.startswith("<?xml"):
            return []

        tree = ET.ElementTree(ET.fromstring(content))
        extracted_sitemaps.extend([sitemap.text for sitemap in tree.findall(".//{*}loc") if sitemap.text.endswith(".xml")])

        for sitemap in extracted_sitemaps.copy():
            multilingual_sitemaps = extract_sitemaps_from_index(sitemap)
            extracted_sitemaps.extend(multilingual_sitemaps)

        if subdomain in FAMILY_SUBDOMAINS:
            for family in FAMILIES:
                family_sitemap_url = f"https://{subdomain}/{family}/sitemap.xml"
                response = requests.head(family_sitemap_url, timeout=5)
                if response.status_code == 200:
                    extracted_sitemaps.append(family_sitemap_url)
                    multilingual_sitemaps = extract_sitemaps_from_index(family_sitemap_url)
                    extracted_sitemaps.extend(multilingual_sitemaps)

    except Exception:
        pass
    
    return extracted_sitemaps

# Prepare URL batches for submission
def prepare_batches():
    processed_urls = load_json(SITEMAP_RECORD_FILE)
    batches = {}

    for subdomain in SUBDOMAINS:
        all_sitemaps = get_all_sitemaps(subdomain)
        urls_to_submit = []

        for sitemap_url in all_sitemaps:
            extracted_urls = extract_sitemap_urls(sitemap_url)
            for url, _ in extracted_urls:
                if not url.endswith(".xml"):  
                    urls_to_submit.append(url)

        batches[subdomain] = [urls_to_submit[i:i + BATCH_SIZE] for i in range(0, len(urls_to_submit), BATCH_SIZE)]

    save_json(BATCH_FILE, batches)
    print(f"[INFO] Batches prepared for submission.")

if __name__ == "__main__":
    prepare_batches()
