import os
import zipfile
import sys

PACKAGE_DIR = "packages/"
EXTRACT_DIR = "extracted/"

def extract_nupkg(nuget_name):
    nupkg_path = os.path.join(PACKAGE_DIR, f"{nuget_name}.nupkg")
    extract_path = os.path.join(EXTRACT_DIR, nuget_name)

    with zipfile.ZipFile(nupkg_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)

    # Find DLL & XML pairs
    best_dll = None
    best_xml = None
    largest_xml_size = 0

    for root, _, files in os.walk(extract_path):
        dll_file = xml_file = None
        for file in files:
            if file.endswith(".dll"):
                dll_file = os.path.join(root, file)
            elif file.endswith(".xml"):
                xml_path = os.path.join(root, file)
                xml_size = os.path.getsize(xml_path)
                if xml_size > largest_xml_size:
                    largest_xml_size = xml_size
                    best_dll = dll_file
                    best_xml = xml_path

    if best_dll and best_xml:
        os.makedirs("workspace", exist_ok=True)
        os.rename(best_dll, f"workspace/{nuget_name}.dll")
        os.rename(best_xml, f"workspace/{nuget_name}.xml")

    print(f"Selected: {best_dll}, {best_xml}")

if __name__ == "__main__":
    extract_nupkg(sys.argv[1])
