#!/usr/bin/env bash
# Deploy KAIROS backend to Hugging Face Spaces.
# Usage: ./scripts/deploy_hf.sh <your-hf-username>
# Example: ./scripts/deploy_hf.sh baljotchohan
set -euo pipefail

HF_USERNAME="${1:-baljotchohan}"
SPACE_NAME="kairos-backend"
REMOTE="hf"
HF_BRANCH="hf-deploy"
REMOTE_URL="https://huggingface.co/spaces/${HF_USERNAME}/${SPACE_NAME}"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "=== KAIROS → HF Spaces deploy ==="
echo "Remote: ${REMOTE_URL}"
echo ""

# Add HF remote if not already present
if ! git remote get-url "${REMOTE}" &>/dev/null; then
  echo "[1/5] Adding remote '${REMOTE}'..."
  git remote add "${REMOTE}" "${REMOTE_URL}"
else
  echo "[1/5] Remote '${REMOTE}' already exists."
fi

# Clean up any existing hf-deploy branch
git branch -D "${HF_BRANCH}" 2>/dev/null || true

# Create hf-deploy branch from current main
echo "[2/5] Creating '${HF_BRANCH}' branch..."
git checkout -b "${HF_BRANCH}"

# Swap Dockerfile → HF version (port 7860, /data paths)
echo "[3/5] Swapping Dockerfile and README..."
cp Dockerfile.hf Dockerfile
cp hf_space_README.md README.md

# Commit the swapped files
git add Dockerfile README.md
git commit -m "chore: HF Spaces deployment — swap Dockerfile + README"

# Push hf-deploy → main on HF Space
echo "[4/5] Pushing to HF Space (this may prompt for credentials)..."
echo "      Username: ${HF_USERNAME}"
echo "      Password: your HF access token (Settings → Access Tokens)"
echo ""
git push "${REMOTE}" "${HF_BRANCH}:main" --force

# Go back to original branch and clean up
echo "[5/5] Cleaning up..."
git checkout "${CURRENT_BRANCH}"
git branch -D "${HF_BRANCH}"

echo ""
echo "=== Done! ==="
echo "Space URL: https://huggingface.co/spaces/${HF_USERNAME}/${SPACE_NAME}"
echo ""
echo "Now set these secrets in HF Space Settings → Variables and Secrets:"
echo "  FIREWORKS_API_KEY  — required"
echo "  FRONTEND_URL       — your Vercel URL (set after frontend deploy)"
echo "  SLACK_BOT_TOKEN    — optional"
echo "  GOOGLE_CLIENT_ID   — optional"
echo "  GOOGLE_CLIENT_SECRET — optional"
