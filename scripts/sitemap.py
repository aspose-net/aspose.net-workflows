# List of subdomains
SUBDOMAINS = [
    "www.aspose.net",
    "products.aspose.net",
    "blog.aspose.net",
    "docs.aspose.net",
    "kb.aspose.net",
    "about.aspose.net",
    "releases.aspose.net",
    "websites.aspose.net",
    "reference.aspose.net"
]

# Subdomains that include families
FAMILY_SUBDOMAINS = [
    "kb.aspose.net",
    "docs.aspose.net",
    "products.aspose.net",
    "reference.aspose.net"
]

# Helper function to check sitemaps for all subdomains
def check_all_subdomain_sitemaps(subdomains, families):
    all_available_sitemaps = []
    for subdomain in subdomains:
        print(f"[INFO] Checking sitemaps for subdomain: {subdomain}")
        if subdomain in FAMILY_SUBDOMAINS:
            # Check both main and family-specific sitemaps
            available_sitemaps = check_sitemap_availability(f"https://{subdomain}", families)
        else:
            # Only check the main sitemap index
            available_sitemaps = check_sitemap_availability(f"https://{subdomain}", [])
        all_available_sitemaps.extend(available_sitemaps)
    return all_available_sitemaps

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

    # Families list
    families = ['words', 'pdf', 'cells', 'imaging', 'barcode', 'tasks', 'ocr', 'cad', 'html', 'zip', 'page', 'psd', 'tex']

    # Process sitemaps for all subdomains and submit to Google
    try:
        all_sitemaps = check_all_subdomain_sitemaps(SUBDOMAINS, families)
        for site_url, sitemap in all_sitemaps:
            if not check_sitemap_status(webmaster_service, site_url, sitemap):
                submit_sitemap_to_google(webmaster_service, site_url, sitemap)
    except Exception as e:
        print(f"[ERROR] Unexpected error processing sitemaps: {e}")

if __name__ == "__main__":
    main()
