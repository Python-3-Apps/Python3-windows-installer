import requests
import zipfile
import io
import os
import re

def get_repo_name(repo_url: str) -> str:
    """Extract the repository name from the GitHub URL."""
    match = re.search(r"github\.com/[^/]+/([^/]+)", repo_url)
    if match:
        return match.group(1).replace(".git", "")
    return "downloaded_repo"

def get_default_branch(repo_url: str) -> str:
    """Detect the default branch (main/master/etc) via GitHub API."""
    try:
        match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
        if not match:
            return "main"

        owner, repo = match.groups()
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("default_branch", "main")
        return "main"
    except Exception:
        return "main"

def download_latest_release(owner: str, repo: str, save_path: str, progress_callback=None):
    """Downloads the latest release asset for a given GitHub repo."""
    try:
        if progress_callback:
            progress_callback(0.05, f"Checking latest {repo} release...")

        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        release = response.json()

        if not release.get("assets"):
            raise Exception("No release assets found.")

        asset = release["assets"][0]
        download_url = asset["browser_download_url"]
        asset_name = asset["name"]
        local_file = os.path.join(save_path, asset_name)

        if progress_callback:
            progress_callback(0.1, f"Downloading {asset_name}...")

        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            downloaded = 0
            with open(local_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0 and progress_callback:
                            progress_callback(min(1.0, downloaded / total), f"Downloading {asset_name}...")

        if progress_callback:
            progress_callback(1.0, f"{repo} release downloaded successfully.")
        return local_file

    except Exception as e:
        if progress_callback:
            progress_callback(1.0, f"Failed to download release: {e}")
        return None

def download_github_repo(repo_url: str, save_path: str, progress_callback=None):
    """(Unchanged) Downloads the specified repo’s main/master branch ZIP."""
    try:
        repo_name = get_repo_name(repo_url)
        branch = get_default_branch(repo_url)
        zip_url = f"https://github.com/{repo_url.split('github.com/')[-1]}/archive/refs/heads/{branch}.zip"

        if progress_callback:
            progress_callback(0.05, f"Connecting to {repo_name} ({branch})...")

        response = requests.get(zip_url, stream=True)
        response.raise_for_status()

        total = int(response.headers.get('content-length', 0))
        downloaded = 0
        buffer = io.BytesIO()

        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                buffer.write(chunk)
                downloaded += len(chunk)
                if total > 0 and progress_callback:
                    progress_callback(min(0.8, downloaded / total * 0.8), f"Downloading {repo_name}...")

        if progress_callback:
            progress_callback(0.85, f"Extracting {repo_name}...")

        buffer.seek(0)
        with zipfile.ZipFile(buffer) as zip_ref:
            zip_ref.extractall(save_path)

        extracted_folder = None
        for item in os.listdir(save_path):
            if os.path.isdir(os.path.join(save_path, item)) and repo_name.lower() in item.lower():
                extracted_folder = os.path.join(save_path, item)
                break

        if not extracted_folder:
            extracted_folder = save_path

        if progress_callback:
            progress_callback(1.0, f"{repo_name} downloaded successfully.")

        # Check for installerready.exe
        exe_found = False
        for root, _, files in os.walk(extracted_folder):
            if "installerready.exe" in [f.lower() for f in files]:
                exe_found = True
                break

        return {
            "status": "ready" if exe_found else "no_installer",
            "path": extracted_folder,
            "repo_name": repo_name
        }

    except Exception as e:
        if progress_callback:
            progress_callback(1.0, f"Failed to download {repo_url}: {e}")
        return {"status": "error", "error": str(e)}
