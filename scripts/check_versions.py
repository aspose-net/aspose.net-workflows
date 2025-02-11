import json
import requests
import sys

STATUS_FILE = "reference/status.json"
NUGET_API_URL = "https://api.nuget.org/v3-flatcontainer/{}/index.json"

# Load existing status.json
with open(STATUS_FILE, "r", encoding="utf-8") as f:
    status_data = json.load(f)

updates_needed = {}

# Check latest NuGet versions
for family, data in status_data.items():
    nuget_name = data["nuget"].lower()  # Convert to lowercase for NuGet API
    print(f"Checking {family} ({nuget_name})...")  # Debugging line

    response = requests.get(NUGET_API_URL.format(nuget_name))

    if response.status_code == 200:
        versions = response.json().get("versions", [])
        latest_version = versions[-1] if versions else None

        if latest_version:
            print(f"Latest NuGet version for {family}: {latest_version}")
            print(f"Current version in status.json: {data['version']}")

            # Store the latest version for future reference
            status_data[family]["latest_version"] = latest_version

            if latest_version != data["version"]:
                updates_needed[family] = {
                    "nuget": data["nuget"],
                    "version": latest_version
                }
                print(f"✅ Update needed for {family}.")
            else:
                print(f"Skipping {family}, version is up-to-date.")

        else:
            print(f"❌ No versions found for {family}!")

    elif response.status_code == 404:
        print(f"❌ ERROR: NuGet package not found for {family} ({nuget_name})!")
        print(f"Check if {nuget_name} exists on https://www.nuget.org/packages/{nuget_name}/")
    
    else:
        print(f"❌ Failed to fetch data for {family}, HTTP {response.status_code}")

# Save the latest versions back to status.json
with open(STATUS_FILE, "w", encoding="utf-8") as f:
    json.dump(status_data, f, indent=2)

# Output results for GitHub Actions
print("Final updates needed:", json.dumps(updates_needed, indent=2))
print(json.dumps(updates_needed))  # Ensures GitHub Actions captures it
