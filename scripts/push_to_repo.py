import os
import subprocess
import sys

ORG_NAME = "Aspose"
REPO_NAME = "aspose.net"
FOLDER_NAME = sys.argv[1]
BRANCH_NAME = f"api-update-{FOLDER_NAME}"
GITHUB_TOKEN = os.getenv("REPO_TOKEN")

if not GITHUB_TOKEN:
    print("Error: GitHub token not set.")
    sys.exit(1)

repo_url = f"https://{GITHUB_TOKEN}@github.com/{ORG_NAME}/{REPO_NAME}.git"

# Clone repo
try:
    subprocess.run(["git", "clone", repo_url], check=True)
except subprocess.CalledProcessError:
    print("Error: Failed to clone repository.")
    sys.exit(1)

DEST_PATH = f"{REPO_NAME}/content/reference.aspose.net/{FOLDER_NAME}/en/"
os.makedirs(DEST_PATH, exist_ok=True)

# Copy files
subprocess.run(["cp", "-r", "api", DEST_PATH], check=True)

# Commit & push
os.chdir(REPO_NAME)
subprocess.run(["git", "checkout", "-b", BRANCH_NAME], check=True)
subprocess.run(["git", "add", "."], check=True)
subprocess.run(["git", "commit", "-m", f"Update API reference for {FOLDER_NAME}"], check=True)
subprocess.run(["git", "push", "--set-upstream", "origin", BRANCH_NAME], check=True)

# Create PR
subprocess.run([
    "gh", "pr", "create",
    "--title", f"Update API reference for {FOLDER_NAME}",
    "--body", "This PR updates the API reference.",
    "--base", "main"
], check=True)

print(f"API reference for {FOLDER_NAME} pushed and PR created successfully.")
