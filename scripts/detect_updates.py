import json
import sys

STATUS_FILE = "reference/status.json"

# Load `status.json`
with open(STATUS_FILE, "r", encoding="utf-8") as f:
    status_data = json.load(f)

# Get products from GitHub Actions input
products = sys.argv[1].split(",") if len(sys.argv) > 1 else []

to_process = []

# Compare versions
for family, data in status_data.items():
    if family in products or "all" in products:
        if "new_version" in data:
            to_process.append({"family": family, "nuget": data["nuget"], "version": data["new_version"]})

print(json.dumps(to_process))
