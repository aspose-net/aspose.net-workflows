import os
import glob
import zipfile
import sys

if len(sys.argv) < 2:
    print("Error: No NuGet package specified.")
    sys.exit(1)

nuget_name = sys.argv[1]
package_files = glob.glob(f"packages/{nuget_name}.*.nupkg")

if not package_files:
    print(f"Error: No NuGet package found for {nuget_name}.")
    sys.exit(1)

package_path = package_files[0]
zip_path = package_path.replace(".nupkg", ".zip")

try:
    os.rename(package_path, zip_path)
except OSError as e:
    print(f"Error renaming package: {e}")
    sys.exit(1)

extract_folder = f"workspace/{nuget_name}"
os.makedirs(extract_folder, exist_ok=True)

try:
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_folder)
except zipfile.BadZipFile:
    print(f"Error: Corrupt or invalid zip file {zip_path}.")
    sys.exit(1)

# Validate that DLL and XML exist
dll_path = os.path.join(extract_folder, f"{nuget_name}.dll")
xml_path = os.path.join(extract_folder, f"{nuget_name}.xml")

if not os.path.exists(dll_path):
    print(f"Error: Extracted DLL missing for {nuget_name}.")
    sys.exit(1)
if not os.path.exists(xml_path):
    print(f"Warning: Extracted XML missing for {nuget_name}, documentation might be incomplete.")
