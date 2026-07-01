"""
dashboard/github_trigger.py — GitHub Actions workflow_dispatch helper.

Sends a POST to the GitHub API to manually trigger a workflow run.
Requires GITHUB_PAT (Personal Access Token) with the 'workflow' scope.
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

REPO = "nitinbs24/Shorts-Generator"
BRANCH = "master"

_WORKFLOW_MAP = {
    "a": "channel_a.yml",
    "b": "channel_b.yml",
}


def trigger_workflow(channel: str) -> tuple[bool, str]:
    """
    Trigger a GitHub Actions workflow_dispatch for the given channel.

    Args:
        channel: 'a' or 'b'

    Returns:
        (success: bool, message: str)
    """
    pat = os.environ.get("GITHUB_PAT", "")
    if not pat:
        return False, "GITHUB_PAT environment variable is not set."

    workflow_file = _WORKFLOW_MAP.get(channel.lower())
    if not workflow_file:
        return False, f"Unknown channel: {channel}"

    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow_file}/dispatches"
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"ref": BRANCH}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 204:
            logger.info(f"Workflow triggered for channel {channel.upper()}")
            return True, f"✅ Workflow dispatched for Channel {channel.upper()}! Check GitHub Actions for progress."
        else:
            msg = resp.json().get("message", resp.text)
            logger.warning(f"Workflow dispatch failed: {resp.status_code} — {msg}")
            return False, f"GitHub API error {resp.status_code}: {msg}"
    except requests.RequestException as exc:
        logger.error(f"Workflow dispatch request failed: {exc}")
        return False, f"Network error: {exc}"


def get_recent_runs(channel: str, limit: int = 5) -> list[dict]:
    """
    Fetch recent workflow runs for a channel from the GitHub API.

    Returns a list of run dicts with keys: id, status, conclusion, created_at, html_url.
    """
    pat = os.environ.get("GITHUB_PAT", "")
    if not pat:
        return []

    workflow_file = _WORKFLOW_MAP.get(channel.lower())
    if not workflow_file:
        return []

    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow_file}/runs"
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        resp = requests.get(url, headers=headers, params={"per_page": limit}, timeout=10)
        if resp.status_code == 200:
            runs = resp.json().get("workflow_runs", [])
            return [
                {
                    "id": r["id"],
                    "status": r["status"],
                    "conclusion": r.get("conclusion", ""),
                    "created_at": r["created_at"],
                    "html_url": r["html_url"],
                }
                for r in runs
            ]
    except requests.RequestException:
        pass
    return []
