import json
import requests
import sys

STATUS_FILE = "reference/status.json"
NUGET_API_URL = "https://api.nuget.org/v3-flatcontainer/{}/index.json"

# Load existing status.json
try:
    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        status_data = json.load(f)
except FileNotFoundError:
    print("Error: status.json not found.")
    sys.exit(1)

updates_needed = {}
modified = False  # Track if we need to update the file

# Check latest NuGet versions
for family, data in status_data.items():
    nuget_name = data.get("nuget", "").lower()
    if not nuget_name:
        print(f"Warning: NuGet package name missing for {family}, skipping.")
        continue

    print(f"Checking NuGet package: {family} ({nuget_name})...")

    try:
        response = requests.get(NUGET_API_URL.format(nuget_name), timeout=10)
        response.raise_for_status()
        versions = response.json().get("versions", [])
        if not versions:
            print(f"Warning: No versions found for {family}, skipping.")
            continue
        latest_version = versions[-1]  # Get the latest version from the list
    except requests.RequestException as e:
        print(f"Error fetching NuGet data for {family}: {e}")
        continue
    except IndexError:
        print(f"Error: Empty versions list received for {family}, skipping.")
        continue

    print(f"Latest version: {latest_version}, Current version: {data.get('version', 'N/A')}")

    # Update status.json if a newer version is found
    if data.get("version") != latest_version:
        status_data[family]["version"] = latest_version
        updates_needed[family] = {"nuget": nuget_name, "version": latest_version}
        print(f"Update required for {family}.")
        modified = True  # Mark that we need to update status.json
    else:
        print(f"{family} is up-to-date.")

# Save updated versions only if there were changes
if modified:
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_data, f, indent=2)

# Output results for GitHub Actions
output_json = json.dumps(updates_needed)
print("Updates needed:", output_json)
print(output_json)  # Ensures GitHub Actions captures it
