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

# ✅ FIX: Use GitHub token for authentication in the HTTPS URL
repo_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{ORG_NAME}/{REPO_NAME}.git"

DEST_PATH = f"{REPO_NAME}/content/reference/{FOLDER_NAME}/en/"

# Clone repository with authentication
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

# Change directory to cloned repo
os.chdir(REPO_NAME)

try:
    # Configure Git user
    subprocess.run(["git", "config", "--global", "user.name", "github-actions"], check=True)
    subprocess.run(["git", "config", "--global", "user.email", "github-actions@github.com"], check=True)

    # Create a new branch
    subprocess.run(["git", "checkout", "-b", BRANCH_NAME], check=True)

    # Stage only updated markdown files
    subprocess.run(["git", "add", f"content/reference/{FOLDER_NAME}/en/"], check=True)

    # Check if there are any changes
    commit_status = subprocess.run(["git", "diff", "--cached", "--exit-code"], check=False)
    if commit_status.returncode != 0:
        subprocess.run(["git", "commit", "-m", f"Update API reference for {FOLDER_NAME}"], check=True)
        subprocess.run(["git", "push", "--set-upstream", "origin", BRANCH_NAME], check=True)

        # Create a pull request using GitHub CLI
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
