import requests
import zipfile
import io
import os
import re
import subprocess

def get_repo_name(repo_url: str) -> str:
    match = re.search(r"github\.com/[^/]+/([^/]+)", repo_url)
    if match:
        return match.group(1).replace(".git", "")
    return "downloaded_repo"

def download_github_repo(repo_url: str, save_path: str, progress_callback=None):
    try:
        repo_name = get_repo_name(repo_url)
        zip_url = f"{repo_url}/archive/refs/heads/main.zip"
        if progress_callback:
            progress_callback(0.1, f"Downloading {repo_name}...")
        r = requests.get(zip_url, stream=True)
        r.raise_for_status()
        total = int(r.headers.get('content-length', 0))
        downloaded = 0
        buffer = io.BytesIO()
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                buffer.write(chunk)
                downloaded += len(chunk)
                if total > 0 and progress_callback:
                    progress_callback(min(0.8, downloaded / total * 0.8), f"Downloading {repo_name}...")
        buffer.seek(0)
        with zipfile.ZipFile(buffer) as zip_ref:
            zip_ref.extractall(save_path)
        exe_found = any(
            "InstallerReady.exe" in f.lower()
            for root, _, files in os.walk(save_path)
            for f in files
        )
        return {"status": "ready" if exe_found else "no_installer", "path": save_path}
    except Exception as e:
        if progress_callback:
            progress_callback(1.0, f"Failed: {e}")
        return {"status": "error", "error": str(e)}

def download_latest_release(repo_url: str, save_path: str, progress_callback=None):
    try:
        repo_name = get_repo_name(repo_url)
        match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
        if not match:
            raise ValueError("Invalid GitHub repository URL")
        owner, repo = match.groups()
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        if progress_callback:
            progress_callback(0.05, f"Fetching latest release for {repo_name}...")
        r = requests.get(api_url)
        r.raise_for_status()
        release = r.json()
        zip_url = release.get("zipball_url")
        if not zip_url:
            raise RuntimeError("No release ZIP found.")
        if progress_callback:
            progress_callback(0.2, f"Downloading {repo_name} release...")
        zip_resp = requests.get(zip_url, stream=True)
        zip_resp.raise_for_status()
        total = int(zip_resp.headers.get("content-length", 0))
        downloaded = 0
        buffer = io.BytesIO()
        for chunk in zip_resp.iter_content(chunk_size=8192):
            if chunk:
                buffer.write(chunk)
                downloaded += len(chunk)
                if total > 0 and progress_callback:
                    progress_callback(min(1.0, 0.2 + (downloaded / total) * 0.6), f"Downloading {repo_name} release...")
        buffer.seek(0)
        with zipfile.ZipFile(buffer) as zip_ref:
            zip_ref.extractall(save_path)
        exe_path = None
        for root, _, files in os.walk(save_path):
            for file in files:
                if file.lower() == "InstallerReady.exe":
                    exe_path = os.path.join(root, file)
                    break
            if exe_path:
                break
        if exe_path:
            if progress_callback:
                progress_callback(1.0, "Running InstallerReady...")
            subprocess.Popen([exe_path], shell=True)
            return {"status": "ran", "path": exe_path}
        return {"status": "no_exe", "path": save_path}
    except Exception as e:
        if progress_callback:
            progress_callback(1.0, f"Failed: {e}")
        return {"status": "error", "error": str(e)}
