import json
import sys
import os

REFERENCE_DIR = "reference/"
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
    files_txt = f"workspace/{nuget_name}_files.txt"
    if not os.path.exists(files_txt):
        print(f"Error: DLL path file {files_txt} not found. Run extract_files.py first.")
        sys.exit(1)

    with open(files_txt, "r") as f:
        paths = [line.strip() for line in f.readlines()]
    
    dll_name = paths[0] if paths else None
    xml_name = paths[1] if len(paths) > 1 else None

    if not dll_name or not os.path.exists(dll_name):
        print(f"Error: DLL file not found for {nuget_name}.")
        sys.exit(1)

    docfx = DOCFX_TEMPLATE.copy()
    docfx["metadata"][0]["src"][0]["files"] = [dll_name]
    
    if xml_name and os.path.exists(xml_name):
        docfx["metadata"][0]["src"][0]["files"].append(xml_name)

    filter_config_path = os.path.join(REFERENCE_DIR, nuget_name.lower(), "filterConfig.yml")
    if os.path.exists(filter_config_path):
        docfx["metadata"][0]["filter"] = filter_config_path

    with open("workspace/docfx.json", "w", encoding="utf-8") as f:
        json.dump(docfx, f, indent=2)

    print(f"Generated docfx.json for {nuget_name}: {json.dumps(docfx, indent=2)}")

if __name__ == "__main__":
    generate_docfx(sys.argv[1])
