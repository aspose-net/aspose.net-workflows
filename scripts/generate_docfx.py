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
    family = nuget_name.replace(".", "").lower()  # Normalize folder name
    dll_name = f"workspace/{nuget_name}.dll"
    xml_name = f"workspace/{nuget_name}.xml"

    docfx = DOCFX_TEMPLATE.copy()
    docfx["metadata"][0]["src"][0]["files"] = [dll_name, xml_name]

    # Check for filterConfig.yml
    filter_config_path = os.path.join(REFERENCE_DIR, family, "filterConfig.yml")
    if os.path.exists(filter_config_path):
        docfx["metadata"][0]["filter"] = filter_config_path

    # Save docfx.json
    with open("workspace/docfx.json", "w", encoding="utf-8") as f:
        json.dump(docfx, f, indent=2)

    print(f"Generated docfx.json for {nuget_name}: {json.dumps(docfx, indent=2)}")

if __name__ == "__main__":
    generate_docfx(sys.argv[1])
