import os
import subprocess
import sys

# GitHub repository details
ORG_NAME = "Aspose"
REPO_NAME = "aspose.net"
FOLDER_NAME = sys.argv[1]  # Family name passed as an argument
BRANCH_NAME = f"api-update-{FOLDER_NAME}-{os.popen('date +%Y%m%d%H%M%S').read().strip()}"
GITHUB_TOKEN = os.getenv("REPO_TOKEN")

if not GITHUB_TOKEN:
    print("Error: GitHub token not set. Skipping repository push.")
    sys.exit(1)

repo_url = f"https://{GITHUB_TOKEN}@github.com/{ORG_NAME}/{REPO_NAME}.git"
DEST_PATH = f"{REPO_NAME}/content/reference/{FOLDER_NAME}/en/"

# Clone repository
try:
    print(f"Cloning repository {REPO_NAME} from {repo_url}...")
    subprocess.run(["git", "clone", repo_url], check=True)
except subprocess.CalledProcessError:
    print("Error: Failed to clone repository.")
    sys.exit(1)

# Ensure the destination path exists
os.makedirs(DEST_PATH, exist_ok=True)

# Copy API documentation files
print(f"Copying updated API files to {DEST_PATH}...")
subprocess.run(["cp", "-r", "workspace/docfx/api/", DEST_PATH], check=True)

# Commit & push changes
os.chdir(REPO_NAME)

try:
    subprocess.run(["git", "checkout", "-b", BRANCH_NAME], check=True)
    subprocess.run(["git", "add", "content/reference"], check=True)
    
    commit_status = subprocess.run(["git", "diff", "--cached", "--exit-code"], check=False)
    if commit_status.returncode != 0:
        subprocess.run(["git", "commit", "-m", f"Update API reference for {FOLDER_NAME}"], check=True)
        subprocess.run(["git", "push", "--set-upstream", "origin", BRANCH_NAME], check=True)

        # Create a pull request
        print("Creating a pull request...")
        subprocess.run([
            "gh", "pr", "create",
            "--repo", f"{ORG_NAME}/{REPO_NAME}",
            "--title", f"Update API Docs for {FOLDER_NAME}",
            "--body", f"This PR updates the API documentation for {FOLDER_NAME}.",
            "--base", "main",
            "--head", BRANCH_NAME
        ], check=True)
        print(f"Pull request created for {BRANCH_NAME}.")
    else:
        print("No changes detected. Skipping commit and push.")

except subprocess.CalledProcessError as e:
    print(f"Error during Git operations: {e}")
    sys.exit(1)

print(f"API reference for {FOLDER_NAME} pushed successfully.")
