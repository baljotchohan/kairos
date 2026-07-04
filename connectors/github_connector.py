"""
GitHub connector — reads pull requests and issues via the GitHub REST API
(async httpx). Requires a per-user OAuth access token obtained through the
standard OAuth App flow in api/routes/oauth.py (github.com/settings/developers).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import httpx

GITHUB_API_BASE = "https://api.github.com"


class GitHubConnector:
    def __init__(self, access_token: str):
        self._token = access_token
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _ok(self) -> bool:
        return bool(self._token)

    # ── Public async API ───────────────────────────────────────────────────────

    async def fetch_all(self, days_back: int = 30, max_repos: int = 10) -> list[dict]:
        """
        Fetch recently-updated PRs + issues across the user's most recently
        active repos. Returns [{id, title, text, url, date, source}].
        """
        if not self._ok():
            return []

        cutoff = datetime.utcnow() - timedelta(days=days_back)

        async with httpx.AsyncClient(timeout=30, headers=self._headers) as client:
            repos = await self._list_repos(client, max_repos=max_repos)
            print(f"[GitHubConnector] Scanning {len(repos)} repos")

            results: list[dict] = []

            async def _process_repo(repo: dict):
                full_name = repo["full_name"]
                prs = await self._fetch_pulls(client, full_name, cutoff)
                issues = await self._fetch_issues(client, full_name, cutoff)
                results.extend(prs)
                results.extend(issues)

            await asyncio.gather(*[_process_repo(r) for r in repos])

        print(f"[GitHubConnector] Fetched {len(results)} items")
        return results

    # ── Live-query API (LiveDataAgent — on-demand, not ingestion) ────────────────

    async def get_user_login(self) -> str | None:
        if not self._ok():
            return None
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

    async def _search_issues(self, q: str, limit: int) -> list[dict]:
        if not self._ok():
            return []
        try:
            async with httpx.AsyncClient(timeout=20, headers=self._headers) as client:
                resp = await client.get(
                    f"{GITHUB_API_BASE}/search/issues",
                    params={"q": q, "sort": "updated", "order": "desc", "per_page": min(limit, 30)},
                )
                resp.raise_for_status()
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
            resp = await client.get(
                f"{GITHUB_API_BASE}/user/repos",
                params={"sort": "updated", "direction": "desc", "per_page": max_repos},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[GitHubConnector] list_repos error: {e}")
            return []

    async def _fetch_pulls(self, client: httpx.AsyncClient, full_name: str, cutoff: datetime) -> list[dict]:
        prs: list[dict] = []
        try:
            for page in range(1, 6):  # cap at 5 pages (100 PRs) per repo per cycle
                resp = await client.get(
                    f"{GITHUB_API_BASE}/repos/{full_name}/pulls",
                    params={"state": "closed", "sort": "updated", "direction": "desc", "per_page": 20, "page": page},
                )
                resp.raise_for_status()
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
            comments = await self._fetch_comments(client, full_name, pr["number"])
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

    async def _fetch_issues(self, client: httpx.AsyncClient, full_name: str, cutoff: datetime) -> list[dict]:
        issues: list[dict] = []
        try:
            for page in range(1, 6):  # cap at 5 pages (100 issues) per repo per cycle
                resp = await client.get(
                    f"{GITHUB_API_BASE}/repos/{full_name}/issues",
                    params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 20, "page": page},
                )
                resp.raise_for_status()
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
            comments = await self._fetch_comments(client, full_name, issue["number"])
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

    async def _fetch_comments(self, client: httpx.AsyncClient, full_name: str, number: int) -> list[str]:
        # Same endpoint serves both issue and PR conversation comments.
        try:
            resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{full_name}/issues/{number}/comments",
                params={"per_page": 10},
            )
            resp.raise_for_status()
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
