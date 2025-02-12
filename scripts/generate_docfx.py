import json
import sys
import os
import shutil
import subprocess

REFERENCE_DIR = "reference/"
WORKSPACE_DIR = "workspace/"
DOCFX_OUTPUT_DIR = "workspace/docfx/"
DOCFX_EXECUTABLE = "C:\\path-to\\docfx.exe"  # Update with the correct DocFX path

DOCFX_TEMPLATE = {
    "metadata": [
        {
            "src": [{"files": []}],
            "dest": "api",
            "outputFormat": "markdown"
        }
    ]
}

def generate_docfx(nuget_name):
    """Generates docfx.json and runs docfx metadata processing."""
    
    # Normalize family name by removing 'Aspose.' and converting to lowercase
    family_name = nuget_name.replace("Aspose.", "").lower()

    files_txt = f"{WORKSPACE_DIR}{nuget_name}_files.txt"
    if not os.path.exists(files_txt):
        print(f"Error: DLL path file {files_txt} not found. Run extract_files.py first.")
        sys.exit(1)

    # Ensure docfx workspace directory exists
    os.makedirs(DOCFX_OUTPUT_DIR, exist_ok=True)

    with open(files_txt, "r") as f:
        paths = [line.strip() for line in f.readlines()]
    
    dll_path = paths[0] if paths else None
    xml_path = paths[1] if len(paths) > 1 else None

    if not dll_path or not os.path.exists(dll_path):
        print(f"Error: DLL file not found for {nuget_name}.")
        sys.exit(1)

    # Copy DLL and XML to docfx output directory
    copied_dll_path = os.path.join(DOCFX_OUTPUT_DIR, os.path.basename(dll_path))
    shutil.copy(dll_path, copied_dll_path)

    copied_xml_path = None
    if xml_path and os.path.exists(xml_path):
        copied_xml_path = os.path.join(DOCFX_OUTPUT_DIR, os.path.basename(xml_path))
        shutil.copy(xml_path, copied_xml_path)

    # Check if filterConfig.yml exists in /reference/{family_name}/ and copy it
    filter_config_path = os.path.join(REFERENCE_DIR, family_name, "filterConfig.yml")
    copied_filter_path = None
    if os.path.exists(filter_config_path):
        copied_filter_path = os.path.join(DOCFX_OUTPUT_DIR, "filterConfig.yml")
        shutil.copy(filter_config_path, copied_filter_path)
        print(f"DEBUG: Copied filterConfig.yml for {nuget_name}.")

    # Prepare docfx.json content
    docfx = DOCFX_TEMPLATE.copy()
    docfx["metadata"][0]["src"][0]["files"] = [os.path.basename(copied_dll_path)]
    
    if copied_xml_path:
        docfx["metadata"][0]["src"][0]["files"].append(os.path.basename(copied_xml_path))
    
    if copied_filter_path:
        docfx["metadata"][0]["filter"] = "filterConfig.yml"

    # Write docfx.json in the same directory
    docfx_json_path = os.path.join(DOCFX_OUTPUT_DIR, "docfx.json")
    with open(docfx_json_path, "w", encoding="utf-8") as f:
        json.dump(docfx, f, indent=2)

    print(f"Generated docfx.json for {nuget_name}: {json.dumps(docfx, indent=2)}")

    # Run docfx metadata processing
    try:
        print("Running docfx.exe metadata...")
        subprocess.run([DOCFX_EXECUTABLE, "metadata"], cwd=DOCFX_OUTPUT_DIR, check=True)
        print("DocFX metadata processing completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error: DocFX metadata processing failed. {e}")
        sys.exit(1)

if __name__ == "__main__":
    generate_docfx(sys.argv[1])
