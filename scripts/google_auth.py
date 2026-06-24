"""
One-time script to get a Google OAuth refresh token for Gmail + Drive.

    python scripts/google_auth.py

Paste the GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET from your GCP OAuth credentials.
This will open a browser, ask you to authorize, then print your refresh token.
Add the refresh token to your .env as GOOGLE_REFRESH_TOKEN.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

def main():
    client_id = config.GOOGLE_CLIENT_ID
    client_secret = config.GOOGLE_CLIENT_SECRET

    if not client_id or client_id == "your_client_id":
        print("❌ Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env first")
        return

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        import json
    except ImportError:
        print("Installing google-auth-oauthlib...")
        os.system(f"{sys.executable} -m pip install google-auth-oauthlib")
        from google_auth_oauthlib.flow import InstalledAppFlow

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n✅ Authorization successful!")
    print(f"\nAdd this to your .env:\n")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print(f"\n(Access token expires — the refresh token is permanent)")

if __name__ == "__main__":
    main()
