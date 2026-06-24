"""
One-time script to get Google OAuth refresh token for Gmail + Drive.
Uses InstalledAppFlow with local server — works with Desktop app OAuth clients.
"""
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uris": ["http://localhost:8765"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

print("\n🌐 Opening browser for Google sign-in...")
print("   Sign in, allow access, then come back here.\n")

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=8765, prompt="consent", access_type="offline")

token = creds.refresh_token
print(f"\n✅ Refresh token obtained: {token[:30]}...")

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
with open(env_path, "r") as f:
    content = f.read()
content = content.replace("GOOGLE_REFRESH_TOKEN=", f"GOOGLE_REFRESH_TOKEN={token}")
with open(env_path, "w") as f:
    f.write(content)
print("✅ Saved to .env automatically.\n")
