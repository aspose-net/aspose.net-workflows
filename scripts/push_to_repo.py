import os
import subprocess
import sys
from datetime import datetime

# GitHub repository details
ORG_NAME = "Aspose"
REPO_NAME = "aspose.net"
FOLDER_NAME = sys.argv[1].strip()  # Ensure the family name is correctly passed
if not FOLDER_NAME:
    print("Error: FOLDER_NAME is empty. Cannot proceed.")
    sys.exit(1)

# ✅ Fix: Use a valid timestamp format
timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
BRANCH_NAME = f"api-update-{FOLDER_NAME}-{timestamp}"

GITHUB_TOKEN = os.getenv("REPO_TOKEN")
if not GITHUB_TOKEN:
    print("Error: GitHub token not set. Skipping repository push.")
    sys.exit(1)

repo_url = f"https://{GITHUB_TOKEN}@github.com/{ORG_NAME}/{REPO_NAME}.git"
DEST_PATH = f"{REPO_NAME}/content/reference.aspose.net/{FOLDER_NAME}/en/"

# Clone repository
try:
    print(f"Cloning repository {REPO_NAME} from {repo_url}...")
    subprocess.run(["git", "clone", repo_url], check=True)
except subprocess.CalledProcessError:
    print("Error: Failed to clone repository.")
    sys.exit(1)

# ✅ Fix: Copy only the files inside `api/`, not the folder itself
print(f"Copying updated API files to {DEST_PATH}...")
os.makedirs(DEST_PATH, exist_ok=True)
subprocess.run(["cp", "-r", "workspace/docfx/api/.", DEST_PATH], check=True)  # Copy files, not the 'api/' folder

# Change directory to cloned repo
os.chdir(REPO_NAME)

try:
    # Configure Git user
    subprocess.run(["git", "config", "--global", "user.name", "github-actions"], check=True)
    subprocess.run(["git", "config", "--global", "user.email", "github-actions@github.com"], check=True)

    # ✅ Fix: Ensure correct branch name
    subprocess.run(["git", "checkout", "-b", BRANCH_NAME], check=True)

    # ✅ Fix: Ensure correct staging path
    subprocess.run(["git", "add", f"content/reference.aspose.net/{FOLDER_NAME}/en/"], check=True)

    # Check if there are any changes
    commit_status = subprocess.run(["git", "diff", "--cached", "--exit-code"], check=False)
    if commit_status.returncode != 0:
        subprocess.run(["git", "commit", "-m", f"Update API reference for {FOLDER_NAME}"], check=True)
        subprocess.run(["git", "push", "--set-upstream", "origin", BRANCH_NAME], check=True)

        # ✅ Fix: Authenticate GitHub CLI before creating PR
        print("Authenticating GitHub CLI...")
        auth_check = subprocess.run(["gh", "auth", "status"], check=False)
        if auth_check.returncode != 0:
            print("Error: GitHub CLI is not authenticated. PR creation may fail.")

        # ✅ Fix: Ensure valid PR title & body
        print("Creating a pull request...")
        pr_result = subprocess.run([
            "gh", "pr", "create",
            "--repo", f"{ORG_NAME}/{REPO_NAME}",
            "--title", f"Update API Docs for {FOLDER_NAME}",
            "--body", f"This PR updates the API documentation for {FOLDER_NAME}.",
            "--base", "main",
            "--head", BRANCH_NAME
        ], check=False)  # Allow failure without breaking the script

        if pr_result.returncode == 0:
            print(f"Pull request created for {BRANCH_NAME}.")
        else:
            print("Warning: PR creation failed. Check GitHub CLI authentication.")

    else:
        print("No changes detected. Skipping commit and push.")

except subprocess.CalledProcessError as e:
    print(f"Error during Git operations: {e}")
    sys.exit(1)

print(f"API reference for {FOLDER_NAME} pushed successfully.")
