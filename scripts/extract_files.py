import os
import glob
import zipfile
import sys

if len(sys.argv) < 2:
    print("Error: No NuGet package specified.")
    sys.exit(1)

nuget_name = sys.argv[1]
package_path = glob.glob(f"packages/{nuget_name}.*.nupkg")

if not package_path:
    print(f"Error: No NuGet package found for {nuget_name}.")
    sys.exit(1)

package_path = package_path[0]  # Use the first match

# Rename .nupkg to .zip and extract
zip_path = package_path.replace(".nupkg", ".zip")
os.rename(package_path, zip_path)

extract_folder = f"workspace/{nuget_name}"
os.makedirs(extract_folder, exist_ok=True)

with zipfile.ZipFile(zip_path, "r") as zip_ref:
    zip_ref.extractall(extract_folder)

print(f"✅ Extracted {nuget_name} to {extract_folder}")
