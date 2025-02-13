import os
import requests
import xml.etree.ElementTree as ET
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# List of subdomains
SUBDOMAINS = [
    "www.aspose.net",
    "products.aspose.net",
    "blog.aspose.net",
    "docs.aspose.net",
    "kb.aspose.net",
    "about.aspose.net",
    "reference.aspose.net",
    "websites.aspose.net"
]

# Bing Webmaster API Endpoint for JSON submission
BING_API_ENDPOINT = "https://ssl.bing.com/webmaster/api.svc/json/SubmitFeed"

# Your Bing API Key
BING_API_KEY = '128aa611839c4078a7d1d812aceb839a'#os.getenv('BING_API_KEY')

# Retry settings
MAX_RETRIES = 3
BACKOFF_FACTOR = 2  # Exponential backoff (2, 4, 8 seconds)

def is_site_verified(site_url):
    """Checks if the site is verified in Bing Webmaster Tools before submission."""
    verification_url = f"https://ssl.bing.com/webmaster/api.svc/json/GetUserSites?apikey={BING_API_KEY}"
    
    try:
        response = requests.get(verification_url, timeout=5)
        if response.status_code == 200:
            sites = response.json().get("d", [])
            if site_url in sites:
                logging.info(f"[INFO] Site verified: {site_url}")
                return True
            else:
                logging.error(f"[ERROR] Site NOT verified in Bing Webmaster Tools: {site_url}")
        else:
            logging.error(f"[ERROR] Could not verify site status: {site_url}, Status Code: {response.status_code}")
    except Exception as e:
        logging.error(f"[ERROR] Exception while checking site verification: {site_url}, Error: {e}")
    
    return False  # Default to unverified if there's an issue


def extract_sitemaps_from_index(sitemap_url):
    """Extracts direct sitemap URLs from an index sitemap."""
    sitemaps = []
    try:
        response = requests.get(sitemap_url, timeout=5)
        if response.status_code == 200:
            tree = ET.ElementTree(ET.fromstring(response.text))
            sitemaps = [loc.text.strip() for loc in tree.findall(".//{*}loc")]
            logging.info(f"Extracted {len(sitemaps)} direct sitemaps from index: {sitemap_url}")
    except Exception as e:
        logging.error(f"Failed to extract sitemaps from index: {sitemap_url}, Error: {e}")
    return sitemaps


def is_index_sitemap(sitemap_url):
    """Checks if a sitemap is an index sitemap."""
    try:
        response = requests.get(sitemap_url, timeout=5)
        if response.status_code == 200:
            tree = ET.ElementTree(ET.fromstring(response.text))
            return bool(tree.findall(".//{*}sitemap"))  # Index sitemaps contain <sitemap> elements
    except Exception as e:
        logging.error(f"Failed to check if sitemap is an index: {sitemap_url}, Error: {e}")
    return False


def is_sitemap_accessible(sitemap_url):
    """Checks if the sitemap is accessible before submission."""
    try:
        response = requests.head(sitemap_url, timeout=5)
        if response.status_code == 200:
            return True
        logging.warning(f"Sitemap not accessible (Status {response.status_code}): {sitemap_url}")
    except Exception as e:
        logging.error(f"Failed to check sitemap accessibility: {sitemap_url}, Error: {e}")
    return False


def submit_sitemap_to_bing(site_url, sitemap_url):
    """Submits a sitemap to Bing only if the site is verified."""
    if not is_site_verified(site_url):
        logging.error(f"[SKIPPING] Sitemap submission skipped. Site is NOT verified in Bing: {site_url}")
        return

    headers = {"Content-Type": "application/json"}
    payload = {"siteUrl": site_url, "feedUrl": sitemap_url}
    params = {"apikey": BING_API_KEY}

    if not is_sitemap_accessible(sitemap_url):
        logging.error(f"Skipping submission. Sitemap is not accessible: {sitemap_url}")
        return

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(BING_API_ENDPOINT, headers=headers, json=payload, params=params)
            if response.status_code == 200:
                logging.info(f"Successfully submitted sitemap to Bing: {sitemap_url}")
                return
            else:
                logging.error(f"Attempt {attempt}/{MAX_RETRIES}: Failed to submit sitemap: {sitemap_url}, "
                              f"Status Code: {response.status_code}, Response: {response.text}")
                if attempt < MAX_RETRIES:
                    wait_time = BACKOFF_FACTOR ** attempt
                    logging.warning(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
        except Exception as e:
            logging.error(f"Exception while submitting sitemap to Bing: {sitemap_url}, Error: {e}")

    logging.critical(f"All retries failed for sitemap: {sitemap_url}")


def process_sitemaps_for_subdomain(subdomain):
    """Processes the sitemaps for a given subdomain."""
    site_url = f"https://{subdomain}"
    sitemap_url = f"{site_url}/sitemap.xml"

    if is_index_sitemap(sitemap_url):
        logging.info(f"Skipping index sitemap: {sitemap_url}")
        direct_sitemaps = extract_sitemaps_from_index(sitemap_url)
        for direct_sitemap in direct_sitemaps:
            submit_sitemap_to_bing(site_url, direct_sitemap)
    else:
        submit_sitemap_to_bing(site_url, sitemap_url)


def main():
    """Main function to process sitemap submission for all subdomains."""
    if not BING_API_KEY:
        logging.critical("Bing API Key not found. Set BING_API_KEY in environment variables.")
        return

    for subdomain in SUBDOMAINS:
        process_sitemaps_for_subdomain(subdomain)


if __name__ == "__main__":
    main()
