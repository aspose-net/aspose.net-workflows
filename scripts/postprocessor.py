import os
import sys
import json
import re
import openai
from bs4 import BeautifulSoup

API_KEY = os.getenv("OPENAI_API_KEY")
FOLDER_PATH = sys.argv[1]

def optimize_frontmatter(content):
    """Optimize YAML frontmatter using OpenAI."""
    match = re.match(r"---(.*?)---", content, re.DOTALL)
    if not match:
        return content

    yaml_content = match.group(1)
    title_match = re.search(r"title:\s*(.*)", yaml_content)
    title = title_match.group(1).strip() if title_match else None

    # Only optimize descriptions & summaries
    prompt = f"Optimize the following YAML content for SEO but keep the title unchanged:\n\n{yaml_content}"
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    optimized_yaml = response["choices"][0]["message"]["content"]
    return content.replace(yaml_content, optimized_yaml)

def process_files():
    """Process all .md files."""
    for filename in os.listdir(FOLDER_PATH):
        if filename.endswith(".md"):
            filepath = os.path.join(FOLDER_PATH, filename)
            with open(filepath, "r+", encoding="utf-8") as f:
                content = f.read()
                optimized_content = optimize_frontmatter(content)
                f.seek(0)
                f.write(optimized_content)
                f.truncate()

if __name__ == "__main__":
    if not os.path.exists(FOLDER_PATH) or not os.listdir(FOLDER_PATH):
        print("Error: No markdown files found to process.")
        sys.exit(1)
    process_files()
