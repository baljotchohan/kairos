"""
GitHub connector — reads pull requests and issues via the GitHub REST API
(async httpx). Requires a per-user OAuth access token obtained through the
standard OAuth App flow in api/routes/oauth.py (github.com/settings/developers).
"""

from __future__ import annotations

import asyncio
import base64
import time
from datetime import datetime, timedelta
from typing import Callable

import httpx

from config import config

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"


class GitHubConnector:
    def __init__(
        self,
        access_token: str,
        refresh_token: str | None = None,
        expires_at: int | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        on_token_refresh: Callable[[dict], None] | None = None,
    ):
        self._token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.client_id = client_id or config.GITHUB_CLIENT_ID
        self.client_secret = client_secret or config.GITHUB_CLIENT_SECRET
        self.on_token_refresh = on_token_refresh
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _ok(self) -> bool:
        return bool(self._token)

    async def _ensure_fresh_token(self) -> None:
        """Refresh the access token if it's expiring and we have a refresh_token.

        Most GitHub OAuth Apps never expire tokens (no "expires_at" stored at
        all, in which case this is a no-op) — only apps with "token expiration"
        enabled issue a refresh_token, per api/routes/oauth.py's github_callback.
        """
        if not self.refresh_token or not self.expires_at:
            return
        if time.time() < self.expires_at - 60:
            return
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    GITHUB_TOKEN_URL,
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": self.refresh_token,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                if "error" in data or not data.get("access_token"):
                    print(f"[GitHubConnector] token refresh failed: {data}")
                    return
                self._token = data["access_token"]
                self._headers["Authorization"] = f"Bearer {self._token}"
                if data.get("refresh_token"):
                    self.refresh_token = data["refresh_token"]
                expires_in = data.get("expires_in", 28800)
                self.expires_at = int(time.time()) + int(expires_in)
                if self.on_token_refresh:
                    self.on_token_refresh({
                        "access_token": self._token,
                        "refresh_token": self.refresh_token,
                        "expires_at": self.expires_at,
                    })
        except Exception as e:
            print(f"[GitHubConnector] token refresh error: {e}")

    # ── Rate-limit-aware GET ───────────────────────────────────────────────────

    async def _get_with_retry(self, client: httpx.AsyncClient, url: str,
                               params: dict | None = None, max_retries: int = 3) -> httpx.Response:
        """GET that distinguishes a rate limit from every other failure.

        A bare `resp.raise_for_status()` makes a 429/secondary-rate-limit 403
        indistinguishable from any other HTTPStatusError to callers here, which
        catch broadly and just stop paginating — so a rate-limited request used
        to silently return whatever partial data had already been fetched as if
        it were the complete result, with zero backoff or retry. This respects
        Retry-After / X-RateLimit-Reset and retries a bounded number of times
        before finally raising.
        """
        resp = None
        for attempt in range(max_retries + 1):
            resp = await client.get(url, params=params)
            is_rate_limited = resp.status_code == 429 or (
                resp.status_code == 403 and resp.headers.get("x-ratelimit-remaining") == "0"
            )
            if is_rate_limited and attempt < max_retries:
                wait = self._retry_wait_seconds(resp)
                print(f"[GitHubConnector] Rate limited on {url} — retrying in {wait:.0f}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        resp.raise_for_status()
        return resp

    @staticmethod
    def _retry_wait_seconds(resp: httpx.Response) -> float:
        retry_after = resp.headers.get("retry-after")
        if retry_after:
            try:
                return min(float(retry_after), 60.0)
            except ValueError:
                pass
        reset = resp.headers.get("x-ratelimit-reset")
        if reset:
            try:
                return max(1.0, min(float(reset) - time.time(), 60.0))
            except ValueError:
                pass
        return 5.0

    # ── Public async API ───────────────────────────────────────────────────────

    async def fetch_all(self, days_back: int = 30, max_repos: int = 10) -> list[dict]:
        """
        Fetch recently-updated PRs + issues across the user's most recently
        active repos. Returns [{id, title, text, url, date, source}].
        """
        if not self._ok():
            return []

        await self._ensure_fresh_token()
        cutoff = datetime.utcnow() - timedelta(days=days_back)

        # Bounds total concurrent comment-fetch requests across ALL repos in
        # this run. Without it, gathering up to `max_repos` repos concurrently
        # — each issuing one comment request per PR/issue (up to 100 each) —
        # can fire ~1000 requests within seconds and trip GitHub's secondary
        # (abuse-detection) rate limiter well before the per-request retry
        # logic in _get_with_retry ever gets a chance to back off cleanly.
        comment_semaphore = asyncio.Semaphore(6)

        async with httpx.AsyncClient(timeout=30, headers=self._headers) as client:
            repos = await self._list_repos(client, max_repos=max_repos)
            print(f"[GitHubConnector] Scanning {len(repos)} repos")

            results: list[dict] = []

            async def _process_repo(repo: dict):
                full_name = repo["full_name"]
                prs = await self._fetch_pulls(client, full_name, cutoff, comment_semaphore)
                issues = await self._fetch_issues(client, full_name, cutoff, comment_semaphore)
                results.extend(prs)
                results.extend(issues)

            await asyncio.gather(*[_process_repo(r) for r in repos])

        print(f"[GitHubConnector] Fetched {len(results)} items")
        return results

    # ── Live-query API (LiveDataAgent — on-demand, not ingestion) ────────────────

    async def get_user_login(self) -> str | None:
        if not self._ok():
            return None
        await self._ensure_fresh_token()
        try:
            async with httpx.AsyncClient(timeout=15, headers=self._headers) as client:
                resp = await client.get(f"{GITHUB_API_BASE}/user")
                resp.raise_for_status()
                return resp.json().get("login")
        except Exception as e:
            print(f"[GitHubConnector] get_user_login error: {e}")
            return None

    async def list_repos(self, limit: int = 15) -> list[dict]:
        """Repos the user owns/collaborates on, most recently updated first.

        Raises RuntimeError on a real API failure (bad/expired token, wrong
        scope, network error) instead of swallowing it into an empty list —
        LiveDataAgent needs to tell "0 repos" apart from "couldn't check",
        otherwise a broken token silently reports as an empty GitHub account."""
        if not self._ok():
            return []
        await self._ensure_fresh_token()
        try:
            async with httpx.AsyncClient(timeout=20, headers=self._headers) as client:
                resp = await client.get(
                    f"{GITHUB_API_BASE}/user/repos",
                    params={"sort": "updated", "direction": "desc", "per_page": min(limit, 50)},
                )
                resp.raise_for_status()
                return [
                    {
                        "name": r["full_name"],
                        "private": r.get("private", False),
                        "stars": r.get("stargazers_count", 0),
                        "open_issues": r.get("open_issues_count", 0),
                        "language": r.get("language"),
                        "updated": (r.get("updated_at") or "")[:10],
                        "url": r.get("html_url", ""),
                    }
                    for r in resp.json()
                ]
        except httpx.HTTPStatusError as e:
            print(f"[GitHubConnector] list_repos error: {e.response.status_code} {e.response.text[:200]}")
            raise RuntimeError(f"GitHub API returned {e.response.status_code}: {e.response.text[:200]}") from e
        except Exception as e:
            print(f"[GitHubConnector] list_repos error: {e}")
            raise RuntimeError(f"GitHub request failed: {e}") from e

    async def my_open_pull_requests(self, limit: int = 15) -> list[dict]:
        """PRs authored by the authenticated user, open, across all their repos."""
        return await self._search_issues("is:pr is:open author:@me", limit)

    async def my_open_issues(self, limit: int = 15) -> list[dict]:
        """Issues assigned to the authenticated user, open, across all their repos."""
        return await self._search_issues("is:issue is:open assignee:@me", limit)

    async def search_issues(self, query: str, limit: int = 15) -> list[dict]:
        """Full-text search across the user's accessible issues + PRs."""
        safe_query = query.replace('"', '\\"')
        return await self._search_issues(f'"{safe_query}" in:title,body', limit)

    async def get_repo_summary(self, repo: str) -> dict:
        """Fetch a repo's metadata (description, language, topics, stars) plus
        its README content. `repo` may be "owner/name" or a bare name, which
        is resolved against the authenticated user's own account.

        Raises RuntimeError on a real API failure (not found, bad token,
        rate limit) instead of swallowing it — this is what lets
        LiveDataAgent quote the real reason instead of guessing."""
        if not self._ok():
            return {}

        await self._ensure_fresh_token()
        full_name = repo
        if "/" not in full_name:
            login = await self.get_user_login()
            if not login:
                raise RuntimeError("Could not resolve GitHub username to look up the repo.")
            full_name = f"{login}/{repo}"

        try:
            async with httpx.AsyncClient(timeout=20, headers=self._headers) as client:
                meta_resp = await client.get(f"{GITHUB_API_BASE}/repos/{full_name}")
                meta_resp.raise_for_status()
                meta = meta_resp.json()

                readme_text = ""
                readme_resp = await client.get(f"{GITHUB_API_BASE}/repos/{full_name}/readme")
                if readme_resp.status_code == 200:
                    data = readme_resp.json()
                    if data.get("encoding") == "base64" and data.get("content"):
                        try:
                            readme_text = base64.b64decode(data["content"]).decode("utf-8", errors="replace")[:4000]
                        except Exception:
                            readme_text = ""
                elif readme_resp.status_code != 404:
                    readme_resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise RuntimeError(f"Repo '{full_name}' not found, or not accessible with this token.") from e
            print(f"[GitHubConnector] get_repo_summary error ({full_name}): {e.response.status_code} {e.response.text[:200]}")
            raise RuntimeError(f"GitHub API returned {e.response.status_code}: {e.response.text[:200]}") from e
        except Exception as e:
            print(f"[GitHubConnector] get_repo_summary error ({full_name}): {e}")
            raise RuntimeError(f"GitHub request failed: {e}") from e

        return {
            "name": meta.get("full_name", full_name),
            "description": meta.get("description") or "",
            "language": meta.get("language"),
            "topics": meta.get("topics", []),
            "stars": meta.get("stargazers_count", 0),
            "open_issues": meta.get("open_issues_count", 0),
            "default_branch": meta.get("default_branch", "main"),
            "url": meta.get("html_url", ""),
            "readme": readme_text,
        }

    async def _search_issues(self, q: str, limit: int) -> list[dict]:
        if not self._ok():
            return []
        await self._ensure_fresh_token()
        try:
            async with httpx.AsyncClient(timeout=20, headers=self._headers) as client:
                resp = await self._get_with_retry(
                    client, f"{GITHUB_API_BASE}/search/issues",
                    params={"q": q, "sort": "updated", "order": "desc", "per_page": min(limit, 30)},
                )
                data = resp.json()
        except httpx.HTTPStatusError as e:
            print(f"[GitHubConnector] search_issues error ({q}): {e.response.status_code} {e.response.text[:200]}")
            raise RuntimeError(f"GitHub API returned {e.response.status_code}: {e.response.text[:200]}") from e
        except Exception as e:
            print(f"[GitHubConnector] search_issues error ({q}): {e}")
            raise RuntimeError(f"GitHub request failed: {e}") from e

        out = []
        for item in data.get("items", []):
            repo_full = item.get("repository_url", "").split("/repos/")[-1]
            out.append({
                "number": item.get("number"),
                "title": item.get("title", ""),
                "repo": repo_full,
                "state": item.get("state", ""),
                "is_pr": "pull_request" in item,
                "author": (item.get("user") or {}).get("login", ""),
                "updated": (item.get("updated_at") or "")[:10],
                "url": item.get("html_url", ""),
            })
        return out

    # ── Internals (ingestion) ─────────────────────────────────────────────────

    async def _list_repos(self, client: httpx.AsyncClient, max_repos: int) -> list[dict]:
        try:
            resp = await self._get_with_retry(
                client, f"{GITHUB_API_BASE}/user/repos",
                params={"sort": "updated", "direction": "desc", "per_page": max_repos},
            )
            return resp.json()
        except Exception as e:
            print(f"[GitHubConnector] list_repos error: {e}")
            return []

    async def _fetch_pulls(self, client: httpx.AsyncClient, full_name: str, cutoff: datetime,
                           comment_semaphore: asyncio.Semaphore) -> list[dict]:
        prs: list[dict] = []
        try:
            for page in range(1, 6):  # cap at 5 pages (100 PRs) per repo per cycle
                resp = await self._get_with_retry(
                    client, f"{GITHUB_API_BASE}/repos/{full_name}/pulls",
                    params={"state": "closed", "sort": "updated", "direction": "desc", "per_page": 20, "page": page},
                )
                page_items = resp.json()
                if not page_items:
                    break
                prs.extend(page_items)
                # Sorted updated-desc — once a full page's oldest item is already
                # past the cutoff, every later page is too; stop paging.
                oldest = self._parse_date(page_items[-1].get("updated_at"))
                if oldest and oldest < cutoff:
                    break
        except Exception as e:
            print(f"[GitHubConnector] pulls error ({full_name}): {e}")
            if not prs:
                return []

        out = []
        for pr in prs:
            updated = self._parse_date(pr.get("updated_at"))
            if updated and updated < cutoff:
                continue
            comments = await self._fetch_comments(client, full_name, pr["number"], comment_semaphore)
            body = (pr.get("body") or "").strip()
            merged = "Merged" if pr.get("merged_at") else "Closed (not merged)"
            text_parts = [
                f"Pull Request #{pr['number']}: {pr['title']}",
                f"Status: {merged}",
                f"Author: {(pr.get('user') or {}).get('login', 'unknown')}",
            ]
            if body:
                text_parts.append(f"Description: {body[:1000]}")
            if comments:
                text_parts.append("Discussion:\n" + "\n".join(comments[:8]))
            out.append({
                "id": f"gh-pr-{full_name}-{pr['number']}",
                "title": f"[{full_name}] PR #{pr['number']}: {pr['title']}",
                "text": "\n".join(text_parts),
                "url": pr.get("html_url", ""),
                "date": (pr.get("updated_at") or "")[:10] or datetime.utcnow().strftime("%Y-%m-%d"),
                "source": "GitHub",
            })
        return out

    async def _fetch_issues(self, client: httpx.AsyncClient, full_name: str, cutoff: datetime,
                            comment_semaphore: asyncio.Semaphore) -> list[dict]:
        issues: list[dict] = []
        try:
            for page in range(1, 6):  # cap at 5 pages (100 issues) per repo per cycle
                resp = await self._get_with_retry(
                    client, f"{GITHUB_API_BASE}/repos/{full_name}/issues",
                    params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 20, "page": page},
                )
                page_items = resp.json()
                if not page_items:
                    break
                issues.extend(page_items)
                oldest = self._parse_date(page_items[-1].get("updated_at"))
                if oldest and oldest < cutoff:
                    break
        except Exception as e:
            print(f"[GitHubConnector] issues error ({full_name}): {e}")
            if not issues:
                return []

        out = []
        for issue in issues:
            if "pull_request" in issue:
                # GitHub's /issues endpoint also returns PRs — those are
                # already covered (with richer merge/review context) by
                # _fetch_pulls, so skip here to avoid double-counting.
                continue
            updated = self._parse_date(issue.get("updated_at"))
            if updated and updated < cutoff:
                continue
            comments = await self._fetch_comments(client, full_name, issue["number"], comment_semaphore)
            body = (issue.get("body") or "").strip()
            text_parts = [
                f"Issue #{issue['number']}: {issue['title']}",
                f"Status: {issue.get('state', 'unknown')}",
                f"Author: {(issue.get('user') or {}).get('login', 'unknown')}",
            ]
            if body:
                text_parts.append(f"Description: {body[:1000]}")
            if comments:
                text_parts.append("Discussion:\n" + "\n".join(comments[:8]))
            out.append({
                "id": f"gh-issue-{full_name}-{issue['number']}",
                "title": f"[{full_name}] Issue #{issue['number']}: {issue['title']}",
                "text": "\n".join(text_parts),
                "url": issue.get("html_url", ""),
                "date": (issue.get("updated_at") or "")[:10] or datetime.utcnow().strftime("%Y-%m-%d"),
                "source": "GitHub",
            })
        return out

    async def _fetch_comments(self, client: httpx.AsyncClient, full_name: str, number: int,
                              comment_semaphore: asyncio.Semaphore) -> list[str]:
        # Same endpoint serves both issue and PR conversation comments. Gated by
        # a shared semaphore (see fetch_all) — this is the highest-volume call
        # in the whole connector (one request per PR/issue, up to ~100 per repo
        # across up to 10 repos), so it's the one most likely to trip GitHub's
        # secondary rate limiter if left unbounded.
        try:
            async with comment_semaphore:
                resp = await self._get_with_retry(
                    client, f"{GITHUB_API_BASE}/repos/{full_name}/issues/{number}/comments",
                    params={"per_page": 10},
                )
            return [
                f"{(c.get('user') or {}).get('login', 'unknown')}: {(c.get('body') or '')[:300]}"
                for c in resp.json()
            ]
        except Exception:
            return []

    @staticmethod
    def _parse_date(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None
