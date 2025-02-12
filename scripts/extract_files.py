import os
import sys
import requests
import zipfile

if len(sys.argv) < 3:
    print("Error: No NuGet package specified.")
    sys.exit(1)

nuget_name = sys.argv[1]
nuget_version = sys.argv[2]

download_url = f"https://www.nuget.org/api/v2/package/{nuget_name}/{nuget_version}"
nupkg_path = f"packages/{nuget_name}.{nuget_version}.nupkg"

# Ensure packages directory exists
os.makedirs("packages", exist_ok=True)

# Download NuGet package
try:
    response = requests.get(download_url, stream=True)
    response.raise_for_status()
    with open(nupkg_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Downloaded: {nupkg_path}")
except requests.RequestException as e:
    print(f"Error downloading NuGet package: {e}")
    sys.exit(1)

extract_folder = f"workspace/{nuget_name}"
os.makedirs(extract_folder, exist_ok=True)

try:
    with zipfile.ZipFile(nupkg_path, "r") as zip_ref:
        zip_ref.extractall(extract_folder)
    print(f"Extraction complete: {nuget_name} -> {extract_folder}")
except zipfile.BadZipFile:
    print(f"Error: Corrupt or invalid zip file {nupkg_path}.")
    sys.exit(1)

# Validate DLL and XML existence
dll_path = os.path.join(extract_folder, f"{nuget_name}.dll")
xml_path = os.path.join(extract_folder, f"{nuget_name}.xml")

if not os.path.exists(dll_path):
    print(f"Error: Extracted DLL missing for {nuget_name}.")
    sys.exit(1)
if not os.path.exists(xml_path):
    print(f"Warning: Extracted XML missing for {nuget_name}, documentation might be incomplete.")
