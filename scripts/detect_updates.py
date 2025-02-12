import sys
import json

if len(sys.argv) < 2:
    print("Error: No products specified.")
    sys.exit(1)

products_to_check = [p.strip() for p in sys.argv[1].split(",") if p.strip()]

# Load updates needed from status.json
with open("reference/status.json", "r", encoding="utf-8") as f:
    status_data = json.load(f)

# Filter only selected families and prevent duplicates
updates_needed = []
seen = set()

for product in products_to_check:
    if product in status_data and product not in seen:
        updates_needed.append({"family": product, "nuget": status_data[product]["nuget"]})
        seen.add(product)

# Ensure no duplicates
unique_updates_needed = list({u["family"]: u for u in updates_needed}.values())

# **New: Log full JSON output for debugging**
print("\n🔎 DEBUG: Raw `to_process` JSON Output Before Formatting:\n", json.dumps(unique_updates_needed, indent=2))

# Output a **valid JSON array** for GitHub Actions
formatted_json = json.dumps(unique_updates_needed)
print("\n✅ DEBUG: Final JSON Output Passed to GitHub Actions:\n", formatted_json)

print(formatted_json)  # Ensure GitHub Actions captures it
