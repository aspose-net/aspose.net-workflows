import sys
import json

if len(sys.argv) < 2:
    print("Error: No products specified.")
    sys.exit(1)

products_to_check = [p.strip() for p in sys.argv[1].split(",") if p.strip()]

# Load updates needed from status.json
with open("reference/status.json", "r", encoding="utf-8") as f:
    status_data = json.load(f)

# Ensure we process only selected families
updates_needed = [
    {"family": product, "nuget": status_data[product]["nuget"]}
    for product in products_to_check if product in status_data
]

# Ensure no duplicates
unique_updates_needed = list({u["family"]: u for u in updates_needed}.values())

# Print JSON for debugging
print("Products to process:", json.dumps(unique_updates_needed, indent=2))

# Output a **valid JSON array** for GitHub Actions
print(json.dumps(unique_updates_needed))
