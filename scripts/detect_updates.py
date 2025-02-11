import sys
import json

if len(sys.argv) < 2:
    print("Error: No products specified.")
    sys.exit(1)

products_to_check = sys.argv[1].split(",")

# Load updates needed from check_versions.py output
with open("reference/status.json", "r", encoding="utf-8") as f:
    status_data = json.load(f)

updates_needed = {
    product: status_data[product]
    for product in products_to_check if product in status_data
}

# Print JSON output for debugging
print("Products to process:", json.dumps(updates_needed, indent=2))

# Output JSON so GitHub Actions can parse it
print(json.dumps(list(updates_needed.keys())))
