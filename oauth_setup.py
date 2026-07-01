"""
oauth_setup.py — One-time YouTube OAuth2 refresh-token generator.

Run this script locally (not in GitHub Actions) to generate the OAuth refresh
tokens needed for automated YouTube uploads. Store the resulting tokens as
GitHub Secrets: YOUTUBE_REFRESH_TOKEN_A and YOUTUBE_REFRESH_TOKEN_B.

Usage:
    python oauth_setup.py --channel a
    python oauth_setup.py --channel b

Prerequisites:
    1. Create a Google Cloud project at https://console.cloud.google.com
    2. Enable the YouTube Data API v3
    3. Create OAuth 2.0 credentials (Desktop App type)
    4. Download the client_secret JSON and set YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET
       in your .env file, OR pass them as env vars.

Requirements:
    pip install google-auth-oauthlib python-dotenv
"""

import argparse
import json
import os
import sys
from pathlib import Path


def _load_env() -> None:
    """Load .env file if present."""
    try:
        from dotenv import load_dotenv  # type: ignore
        env_file = Path(__file__).parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            print(f"[oauth_setup] Loaded .env from {env_file}")
    except ImportError:
        pass  # python-dotenv not installed — env vars must be set manually


def _get_required_env(var: str) -> str:
    """Get an env var or exit with a helpful message."""
    val = os.environ.get(var, "")
    if not val:
        print(
            f"\n[ERROR] Environment variable '{var}' is not set.\n"
            "Please set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in your .env file\n"
            "or as environment variables before running this script.\n",
            file=sys.stderr,
        )
        sys.exit(1)
    return val


def run_oauth_flow(channel: str) -> str:
    """
    Run the InstalledAppFlow OAuth dance and return the refresh token.

    Opens a browser window for Google authentication. On success, prints
    the refresh token to stdout and saves it to tokens/channel_{channel}.json.

    Args:
        channel: 'a' or 'b'

    Returns:
        The refresh token string.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    except ImportError as exc:
        print(
            "\n[ERROR] google-auth-oauthlib not installed.\n"
            "Run: pip install google-auth-oauthlib\n",
            file=sys.stderr,
        )
        sys.exit(1)

    client_id = _get_required_env("YOUTUBE_CLIENT_ID")
    client_secret = _get_required_env("YOUTUBE_CLIENT_SECRET")

    # Build the client config dict (equivalent to downloaded client_secret.json)
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    scopes = ["https://www.googleapis.com/auth/youtube.upload"]

    print(f"\n[oauth_setup] Starting OAuth flow for Channel {channel.upper()}…")
    print("[oauth_setup] A browser window will open for Google authentication.\n")

    flow = InstalledAppFlow.from_client_config(client_config, scopes)
    # port=0 picks a random free port; open_browser=True opens the default browser
    credentials = flow.run_local_server(port=0, open_browser=True)

    refresh_token = credentials.refresh_token
    if not refresh_token:
        print(
            "\n[ERROR] No refresh token returned. "
            "Ensure you requested 'offline' access and cleared previous grants.\n"
            "Visit https://myaccount.google.com/permissions and revoke access, then retry.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Save token to local file for reference
    token_dir = Path(__file__).parent / "tokens"
    token_dir.mkdir(exist_ok=True)
    token_file = token_dir / f"channel_{channel.lower()}.json"
    token_data = {
        "channel": channel.upper(),
        "refresh_token": refresh_token,
        "client_id": client_id,
        "note": "Store refresh_token as GitHub Secret YOUTUBE_REFRESH_TOKEN_A or _B",
    }
    token_file.write_text(json.dumps(token_data, indent=2), encoding="utf-8")

    return refresh_token


def main() -> None:
    _load_env()

    parser = argparse.ArgumentParser(
        description="Generate YouTube OAuth refresh token for a channel.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python oauth_setup.py --channel a    # Generate token for Channel A (TrendByte Shorts)
  python oauth_setup.py --channel b    # Generate token for Channel B (Rhymie Kids)

After running, copy the printed REFRESH TOKEN and add it as a GitHub Secret:
  Channel A → YOUTUBE_REFRESH_TOKEN_A
  Channel B → YOUTUBE_REFRESH_TOKEN_B
        """,
    )
    parser.add_argument(
        "--channel",
        choices=["a", "b"],
        required=True,
        help="Which channel to generate the token for (a=TrendByte, b=Rhymie Kids)",
    )
    args = parser.parse_args()

    channel = args.channel
    channel_names = {"a": "TrendByte Shorts", "b": "Rhymie Kids"}
    print(f"\n{'='*60}")
    print(f"  YouTube OAuth Setup — Channel {channel.upper()} ({channel_names[channel]})")
    print(f"{'='*60}")

    refresh_token = run_oauth_flow(channel)

    secret_name = f"YOUTUBE_REFRESH_TOKEN_{channel.upper()}"
    print(f"\n{'='*60}")
    print("  ✅ SUCCESS — OAuth token generated!")
    print(f"{'='*60}")
    print(f"\n  Channel: {channel.upper()} — {channel_names[channel]}")
    print(f"  GitHub Secret name: {secret_name}")
    print(f"\n  REFRESH TOKEN:\n")
    print(f"  {refresh_token}")
    print(f"\n{'='*60}")
    print("\n  📋 Next steps:")
    print("  1. Copy the refresh token above")
    print(f"  2. Go to your GitHub repo → Settings → Secrets → New secret")
    print(f"  3. Name: {secret_name}")
    print("  4. Paste the token as the value")
    print("  5. Save and repeat for the other channel if needed")
    print(f"\n  Token also saved to: tokens/channel_{channel.lower()}.json")
    print("  ⚠️  Add tokens/ to .gitignore — never commit refresh tokens!\n")


if __name__ == "__main__":
    main()
