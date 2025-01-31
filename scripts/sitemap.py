import os
import json
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build

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

# Subdomains that include family-based sitemaps
FAMILY_SUBDOMAINS = [
    "kb.aspose.net",
    "docs.aspose.net",
    "products.aspose.net",
    "reference.aspose.net"
]

# List of families (kept separately)
FAMILIES = ['words', 'pdf', 'cells', 'imaging', 'barcode', 'tasks', 'ocr', 'cad', 'html', 'zip', 'page', 'psd', 'tex']


# Helper function to authenticate Google services
def authenticate_google_service(scopes, key_info):
    try:
        credentials = service_account.Credentials.from_service_account_info(
            key_info, scopes=scopes
        )
        return credentials
    except Exception as e:
        print(f"[ERROR] Authentication failed: {e}")
        return None


# Check sitemap status before submitting
def check_sitemap_status(service, site_url, sitemap_url):
    try:
        request = service.sitemaps().list(siteUrl=site_url)
        response = request.execute()
        for sitemap in response.get('sitemap', []):
            if sitemap.get('path') == sitemap_url:
                print(f"[INFO] Sitemap already submitted: {sitemap_url}")
                return True
        return False
    except Exception as e:
        print(f"[ERROR] Failed to check sitemap status for {sitemap_url}: {e}")
        return False


# Submit sitemap to Google
def submit_sitemap_to_google(service, site_url, sitemap_url):
    try:
        request = service.sitemaps().submit(siteUrl=site_url, feedpath=sitemap_url)
        request.execute()
        print(f"[INFO] Submitted sitemap to Google: {sitemap_url}")
    except Exception as e:
        print(f"[ERROR] Failed to submit sitemap: {sitemap_url}: {e}")


# Check sitemap availability for given index sitemaps
def check_sitemap_availability(base_url, include_families):
    available_sitemaps = []
    try:
        # Check main index sitemap
        index_sitemap_url = f"{base_url}/sitemap.xml"
        response = requests.get(index_sitemap_url, timeout=5)
        if response.status_code == 200:
            print(f"[INFO] Sitemap index found: {index_sitemap_url}")
            available_sitemaps.append((base_url, index_sitemap_url))

        # Check family-specific sitemaps only if the subdomain supports it
        if include_families:
            for family in FAMILIES:
                family_sitemap_url = f"{base_url}/{family}/sitemap.xml"
                response = requests.head(family_sitemap_url, timeout=5)  # Lightweight check
                if response.status_code == 200:
                    print(f"[INFO] Family sitemap found: {family_sitemap_url}")
                    available_sitemaps.append((base_url, family_sitemap_url))

    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch sitemaps from {base_url}: {e}")

    return available_sitemaps


# Helper function to check sitemaps for all subdomains
def check_all_subdomain_sitemaps(subdomains):
    all_available_sitemaps = []
    for subdomain in subdomains:
        print(f"[INFO] Checking sitemaps for subdomain: {subdomain}")
        include_families = subdomain in FAMILY_SUBDOMAINS
        available_sitemaps = check_sitemap_availability(f"https://{subdomain}", include_families)
        all_available_sitemaps.extend(available_sitemaps)
    return all_available_sitemaps


# Main execution
def main():
    # Load credentials from GitHub Actions secret
    try:
        credentials_info = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
    except KeyError:
        print("[ERROR] GOOGLE_CREDENTIALS_JSON environment variable not set.")
        return
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to decode GOOGLE_CREDENTIALS_JSON: {e}")
        return

    webmaster_scopes = ['https://www.googleapis.com/auth/webmasters']

    # Authenticate Google service
    webmaster_credentials = authenticate_google_service(webmaster_scopes, credentials_info)
    if not webmaster_credentials:
        print("[ERROR] Unable to authenticate Google service. Exiting.")
        return

    try:
        webmaster_service = build('searchconsole', 'v1', credentials=webmaster_credentials)
    except Exception as e:
        print(f"[ERROR] Failed to initialize Google Search Console service: {e}")
        return

    # Process sitemaps for all subdomains and submit to Google
    try:
        all_sitemaps = check_all_subdomain_sitemaps(SUBDOMAINS)
        for site_url, sitemap in all_sitemaps:
            if not check_sitemap_status(webmaster_service, site_url, sitemap):
                submit_sitemap_to_google(webmaster_service, site_url, sitemap)
    except Exception as e:
        print(f"[ERROR] Unexpected error processing sitemaps: {e}")


if __name__ == "__main__":
    main()
