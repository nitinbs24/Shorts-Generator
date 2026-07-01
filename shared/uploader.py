"""
shared/uploader.py — YouTube Data API v3 upload handler.

Handles OAuth 2.0 token refresh and uploads a completed MP4 Short to YouTube.

Public API:
    upload_short(
        video_path,
        title,
        description,
        category_id,
        channel_label,
        tags=None,
        privacy="public",
    ) -> str   # YouTube video ID

Environment variables required (set in .env or GitHub Secrets):
    YOUTUBE_CLIENT_ID      — OAuth client ID from Google Cloud Console
    YOUTUBE_CLIENT_SECRET  — OAuth client secret
    YOUTUBE_REFRESH_TOKEN_A — Refresh token for Channel A
    YOUTUBE_REFRESH_TOKEN_B — Refresh token for Channel B
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# Chunk size for resumable upload (5 MB)
_CHUNK_SIZE = 5 * 1024 * 1024

# Max file size guard (500 MB — well above realistic Shorts size)
_MAX_VIDEO_SIZE_MB = 500


# ── Auth ──────────────────────────────────────────────────────────────────────

def _get_env(var: str) -> str:
    """Retrieve a required env var or raise a descriptive error."""
    val = os.environ.get(var, "")
    if not val:
        raise EnvironmentError(
            f"Environment variable '{var}' is not set. "
            f"Check your .env file or GitHub Secrets."
        )
    return val


def _build_credentials(channel_label: str):
    """
    Build an OAuth2 Credentials object from env vars, refreshing if needed.

    channel_label: 'a' or 'b' (selects the correct refresh token env var).
    """
    try:
        from google.oauth2.credentials import Credentials  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "google-auth and google-auth-httplib2 are required. "
            "Install with: pip install google-auth google-auth-httplib2"
        ) from exc

    client_id = _get_env("YOUTUBE_CLIENT_ID")
    client_secret = _get_env("YOUTUBE_CLIENT_SECRET")

    token_env = f"YOUTUBE_REFRESH_TOKEN_{channel_label.upper()}"
    refresh_token = _get_env(token_env)

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=[YOUTUBE_UPLOAD_SCOPE],
    )

    # Refresh to get a valid access token
    creds.refresh(Request())
    logger.info("OAuth token refreshed for Channel %s.", channel_label.upper())
    return creds


def _build_youtube_client(credentials):
    """Build the YouTube API client."""
    try:
        from googleapiclient.discovery import build  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "google-api-python-client is required. "
            "Install with: pip install google-api-python-client"
        ) from exc

    return build(
        YOUTUBE_API_SERVICE_NAME,
        YOUTUBE_API_VERSION,
        credentials=credentials,
    )


# ── Upload ────────────────────────────────────────────────────────────────────

def _validate_video_file(video_path: Path) -> None:
    """Basic sanity checks before attempting upload."""
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    size_mb = video_path.stat().st_size / (1024 * 1024)
    if size_mb > _MAX_VIDEO_SIZE_MB:
        raise ValueError(
            f"Video file is {size_mb:.1f} MB — exceeds the {_MAX_VIDEO_SIZE_MB} MB guard."
        )
    logger.info("Video size: %.2f MB", size_mb)


def _build_video_metadata(
    title: str,
    description: str,
    category_id: int,
    tags: Optional[list[str]],
    privacy: str,
) -> dict:
    """Construct the YouTube video resource metadata dict."""
    # Ensure #Shorts is in the title
    if "#Shorts" not in title:
        title = f"{title} #Shorts"
    if "#Shorts" not in description:
        description = f"{description}\n\n#Shorts"

    snippet = {
        "title": title[:100],           # YouTube max title length
        "description": description[:5000],  # YouTube max description length
        "categoryId": str(category_id),
        "defaultLanguage": "en",
    }
    if tags:
        snippet["tags"] = tags[:500]    # YouTube max 500 tags

    return {
        "snippet": snippet,
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }


# ── Public API ────────────────────────────────────────────────────────────────

def upload_short(
    video_path: Path,
    title: str,
    description: str,
    category_id: int,
    channel_label: str,
    tags: Optional[list[str]] = None,
    privacy: str = "public",
) -> str:
    """
    Upload an MP4 Short to YouTube using resumable upload.

    Args:
        video_path:    Path to the final MP4 file.
        title:         Video title (max 100 chars; #Shorts auto-appended if missing).
        description:   Video description.
        category_id:   YouTube category ID (25 for News, 27 for Education).
        channel_label: 'a' or 'b' — determines which refresh token to use.
        tags:          Optional list of tag strings.
        privacy:       'public', 'private', or 'unlisted' (default 'public').

    Returns:
        YouTube video ID string on success.

    Raises:
        EnvironmentError:   If required OAuth env vars are missing.
        FileNotFoundError:  If video_path does not exist.
        RuntimeError:       On quota exceeded (HTTP 403) or other API errors.
    """
    try:
        from googleapiclient.errors import HttpError  # type: ignore
        from googleapiclient.http import MediaFileUpload  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "google-api-python-client is required. "
            "Install with: pip install google-api-python-client"
        ) from exc

    _validate_video_file(video_path)

    logger.info("Authenticating YouTube upload for Channel %s…", channel_label.upper())
    credentials = _build_credentials(channel_label)
    youtube = _build_youtube_client(credentials)

    body = _build_video_metadata(title, description, category_id, tags, privacy)

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        chunksize=_CHUNK_SIZE,
        resumable=True,
    )

    logger.info("Starting upload: '%s' (privacy=%s)…", body["snippet"]["title"], privacy)

    try:
        request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress_pct = int(status.progress() * 100)
                logger.info("Upload progress: %d%%", progress_pct)

    except HttpError as exc:
        if exc.resp.status == 403:
            raise RuntimeError(
                "YouTube upload quota exceeded (HTTP 403). "
                "The upload will be skipped. Quota resets at midnight Pacific Time."
            ) from exc
        raise RuntimeError(
            f"YouTube API error during upload (HTTP {exc.resp.status}): {exc.content}"
        ) from exc

    video_id = response.get("id", "")
    if not video_id:
        raise RuntimeError("Upload appeared to succeed but no video ID was returned.")

    logger.info(
        "Upload complete! YouTube video ID: %s  URL: https://youtu.be/%s",
        video_id,
        video_id,
    )
    return video_id
