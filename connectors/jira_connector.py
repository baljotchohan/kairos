"""
Jira connector — full read access via Jira REST API v3.
Pure httpx, no Jira Python client dependency.

Two auth modes:
  - OAuth (per-user): access_token/refresh_token/cloud_id supplied — Bearer
    auth against the Atlassian API gateway (api.atlassian.com/ex/jira/{cloud_id}),
    the required proxy for Atlassian's 3LO OAuth apps. Tokens auto-refresh.
  - Legacy (global): no OAuth args supplied — falls back to HTTP Basic Auth
    against config.JIRA_URL/JIRA_EMAIL/JIRA_API_TOKEN directly, exactly as
    before. This is what JIRA_OWNER_UID's ingestion still uses.
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional, Callable

import httpx

from config import config


class JiraConnector:
    OAUTH_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
    ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

    def __init__(
        self,
        access_token: str | None = None,
        refresh_token: str | None = None,
        cloud_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        expires_at: int | None = None,
        on_token_refresh: Callable[[dict], None] | None = None,
    ):
        self._oauth_mode = bool(access_token or refresh_token)
        self._access_token = access_token
        self.refresh_token = refresh_token
        self.cloud_id = cloud_id
        self.client_id = client_id or config.JIRA_CLIENT_ID
        self.client_secret = client_secret or config.JIRA_CLIENT_SECRET
        self.expires_at = expires_at
        self.on_token_refresh = on_token_refresh

        if self._oauth_mode:
            # Atlassian 3LO OAuth apps MUST call through the API gateway proxy —
            # the site's own https://yoursite.atlassian.net/rest/api/3/... URLs
            # only accept Basic Auth / API tokens, not OAuth Bearer tokens.
            self._base = f"https://api.atlassian.com/ex/jira/{cloud_id}" if cloud_id else ""
            self._auth = None
            self._headers = {"Accept": "application/json"}
        else:
            self._base = config.JIRA_URL.rstrip("/") if config.JIRA_URL else ""
            self._auth = (config.JIRA_EMAIL, config.JIRA_API_TOKEN)
            self._headers = {"Accept": "application/json"}

    def _ok(self) -> bool:
        if self._oauth_mode:
            return bool(self.cloud_id and (self._access_token or self.refresh_token))
        return bool(config.JIRA_URL and config.JIRA_EMAIL and config.JIRA_API_TOKEN)

    # ── OAuth token refresh (per-user mode only) ─────────────────────────────────

    async def _ensure_fresh_token(self):
        """Refresh the Bearer token if it's missing/expired. No-op in legacy
        Basic Auth mode. Called at the top of every public async method,
        before dispatching work to the thread executor — the sync methods
        just read self._headers/self._auth, which this sets."""
        if not self._oauth_mode:
            return
        if self._access_token and (self.expires_at is None or time.time() < self.expires_at - 60):
            self._headers = {"Accept": "application/json", "Authorization": f"Bearer {self._access_token}"}
            return
        if not self.refresh_token:
            raise RuntimeError("Jira connection expired and there's no refresh token — please reconnect Jira.")

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                self.OAUTH_TOKEN_URL,
                json={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        self._access_token = data["access_token"]
        if "refresh_token" in data:
            self.refresh_token = data["refresh_token"]
        expires_in = data.get("expires_in", 3600)
        self.expires_at = int(time.time()) + expires_in
        self._headers = {"Accept": "application/json", "Authorization": f"Bearer {self._access_token}"}

        if self.on_token_refresh:
            self.on_token_refresh({
                "access_token": self._access_token,
                "refresh_token": self.refresh_token,
                "expires_at": self.expires_at,
                "cloud_id": self.cloud_id,
            })

    @staticmethod
    async def resolve_accessible_site(access_token: str) -> Optional[dict]:
        """One-time post-authorization step (called from the OAuth callback,
        not per-request): exchange the access token for the list of Atlassian
        sites the user granted, and return the first one as
        {cloud_id, url, name}. A user with multiple Jira Cloud sites can
        re-run the OAuth flow (Atlassian's consent screen lets them pick a
        different/additional site) to switch which one KAIROS reads."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    JiraConnector.ACCESSIBLE_RESOURCES_URL,
                    headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                )
                resp.raise_for_status()
                resources = resp.json()
        except Exception as e:
            print(f"[JiraConnector] resolve_accessible_site error: {e}")
            return None

        if not resources:
            return None
        site = resources[0]
        return {"cloud_id": site.get("id"), "url": site.get("url"), "name": site.get("name")}

    # ── Public async API ───────────────────────────────────────────────────────

    async def get_recent_issues(self, days_back: int = 30) -> list[dict]:
        if not self._ok():
            return []
        await self._ensure_fresh_token()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_issues_sync, days_back)

    async def get_my_issues(self, status_filter: str | None = None) -> list[dict]:
        """Issues assigned to the authenticated user, optionally filtered by status."""
        if not self._ok():
            return []
        await self._ensure_fresh_token()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_my_issues_sync, status_filter)

    async def get_projects(self) -> list[dict]:
        """List all Jira projects in the workspace."""
        if not self._ok():
            return []
        await self._ensure_fresh_token()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_projects_sync)

    async def search_issues(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search across issue summaries and descriptions."""
        if not self._ok():
            return []
        await self._ensure_fresh_token()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_issues_text_sync, query, limit)

    async def get_issue_stats(self) -> dict:
        """Return counts of issues by status across the whole workspace."""
        if not self._ok():
            return {}
        await self._ensure_fresh_token()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._issue_stats_sync)

    async def get_sprint_status(self, project_key: str | None = None) -> dict:
        """Get active sprint information for a project (or all projects)."""
        if not self._ok():
            return {}
        await self._ensure_fresh_token()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sprint_status_sync, project_key)

    async def get_issue(self, issue_key: str) -> Optional[dict]:
        """Fetch a single issue by key (e.g. 'KAI-42')."""
        if not self._ok():
            return None
        await self._ensure_fresh_token()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_issue_sync, issue_key)

    # ── Rate-limit-aware request (sync — these run inside run_in_executor) ────

    def _request_with_retry(self, method: str, url: str, max_retries: int = 3, **kwargs) -> httpx.Response:
        """A bare `resp.raise_for_status()` made a 429 indistinguishable from
        any other error to the sync call sites below — they catch broadly and
        just stop paginating/return partial data, so a rate-limited request
        silently returned whatever had already been fetched as if it were
        complete. Jira Cloud sends a `Retry-After` header on 429s; this
        respects it and retries a bounded number of times before finally
        raising."""
        headers = kwargs.pop("headers", self._headers)
        resp = None
        for attempt in range(max_retries + 1):
            resp = httpx.request(method, url, auth=self._auth, headers=headers, **kwargs)
            if resp.status_code == 429 and attempt < max_retries:
                wait = self._retry_wait_seconds(resp)
                print(f"[JiraConnector] Rate limited on {url} — retrying in {wait:.0f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
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
        return 2.0

    # ── Sync internals ─────────────────────────────────────────────────────────

    def _get_issues_sync(self, days_back: int) -> list[dict]:
        jql_queries = [
            f"created >= -{days_back}d ORDER BY created DESC",
            f"updated >= -{days_back}d ORDER BY updated DESC",
        ]
        seen: set[str] = set()
        results: list[dict] = []
        for jql in jql_queries:
            for issue in self._search_issues(jql, max_results=100):
                key = issue.get("key", "")
                if not key or key in seen:
                    continue
                seen.add(key)
                results.append(self._parse_issue(issue))
        print(f"[JiraConnector] Fetched {len(results)} issues")
        return results

    def _get_my_issues_sync(self, status_filter: str | None) -> list[dict]:
        jql = "assignee = currentUser()"
        if status_filter:
            # normalize common aliases
            s = status_filter.lower()
            if s in ("open", "to do", "todo"):
                jql += ' AND status = "To Do"'
            elif s in ("in progress", "active", "doing"):
                jql += ' AND status = "In Progress"'
            elif s in ("done", "closed", "resolved", "complete"):
                jql += ' AND status in ("Done", "Closed", "Resolved")'
            else:
                jql += f' AND status = "{status_filter}"'
        jql += " ORDER BY updated DESC"
        issues = self._search_issues(jql, max_results=50)
        return [self._parse_issue(i) for i in issues]

    def _get_projects_sync(self) -> list[dict]:
        try:
            resp = self._request_with_retry(
                "GET", f"{self._base}/rest/api/3/project/search",
                params={"maxResults": 50, "orderBy": "lastIssueUpdatedTime"},
                timeout=20,
            )
            projects = []
            for p in resp.json().get("values", []):
                projects.append({
                    "key": p.get("key", ""),
                    "name": p.get("name", ""),
                    "type": p.get("projectTypeKey", ""),
                    "lead": (p.get("lead") or {}).get("displayName", ""),
                    "url": f"{self._base}/browse/{p.get('key', '')}",
                })
            return projects
        except Exception as e:
            print(f"[JiraConnector] get_projects error: {e}")
            return []

    def _search_issues_text_sync(self, query: str, limit: int) -> list[dict]:
        # Escape quotes in query
        safe_query = query.replace('"', '\\"')
        jql = f'text ~ "{safe_query}" ORDER BY updated DESC'
        issues = self._search_issues(jql, max_results=limit)
        return [self._parse_issue(i) for i in issues]

    def _issue_stats_sync(self) -> dict:
        stats = {"by_status": {}, "total": 0}
        for status_name in ["To Do", "In Progress", "Done", "In Review", "Blocked"]:
            safe = status_name.replace('"', '\\"')
            jql = f'status = "{safe}"'
            try:
                resp = self._request_with_retry(
                    "POST", f"{self._base}/rest/api/3/search/jql",
                    json={"jql": jql, "maxResults": 0, "fields": []},
                    headers={**self._headers, "Content-Type": "application/json"},
                    timeout=15,
                )
                count = resp.json().get("total", 0)
                if count > 0:
                    stats["by_status"][status_name] = count
                    stats["total"] += count
            except Exception:
                pass
        return stats

    def _sprint_status_sync(self, project_key: str | None) -> dict:
        try:
            # Find boards
            params = {"maxResults": 10}
            if project_key:
                params["projectKeyOrId"] = project_key
            resp = self._request_with_retry(
                "GET", f"{self._base}/rest/agile/1.0/board",
                params=params,
                timeout=20,
            )
            boards = resp.json().get("values", [])
            if not boards:
                return {"error": "No Scrum/Kanban boards found."}

            result = {"boards": []}
            for board in boards[:3]:
                board_id = board.get("id")
                board_name = board.get("name", "")
                try:
                    sprint_resp = self._request_with_retry(
                        "GET", f"{self._base}/rest/agile/1.0/board/{board_id}/sprint",
                        params={"state": "active"},
                        timeout=15,
                    )
                    sprints = sprint_resp.json().get("values", [])
                    for s in sprints:
                        result["boards"].append({
                            "board": board_name,
                            "sprint": s.get("name", ""),
                            "state": s.get("state", ""),
                            "start_date": (s.get("startDate", "") or "")[:10],
                            "end_date": (s.get("endDate", "") or "")[:10],
                            "goal": s.get("goal", ""),
                        })
                except Exception:
                    pass
            return result
        except Exception as e:
            print(f"[JiraConnector] sprint_status error: {e}")
            return {"error": str(e)}

    def _get_issue_sync(self, issue_key: str) -> Optional[dict]:
        try:
            resp = self._request_with_retry(
                "GET", f"{self._base}/rest/api/3/issue/{issue_key}",
                timeout=20,
            )
            return self._parse_issue(resp.json())
        except Exception as e:
            print(f"[JiraConnector] get_issue error ({issue_key}): {e}")
            return None

    def _parse_issue(self, issue: dict) -> dict:
        key = issue.get("key", "")
        fields = issue.get("fields", {})
        summary = fields.get("summary", "")
        description = self._extract_adf(fields.get("description") or {})
        status = (fields.get("status") or {}).get("name", "")
        priority = (fields.get("priority") or {}).get("name", "")
        issue_type = (fields.get("issuetype") or {}).get("name", "")
        created = (fields.get("created") or "")[:10]
        updated = (fields.get("updated") or "")[:10]
        due_date = (fields.get("duedate") or "")[:10]
        reporter = (fields.get("reporter") or {}).get("displayName", "")
        assignee = (fields.get("assignee") or {}).get("displayName", "Unassigned")
        labels = fields.get("labels", [])
        project = (fields.get("project") or {}).get("name", "")
        comments = self._get_comments(key)
        return {
            "key": key,
            "summary": summary,
            "description": description[:500] if description else "",
            "status": status,
            "priority": priority,
            "type": issue_type,
            "project": project,
            "created": created,
            "updated": updated,
            "due_date": due_date,
            "reporter": reporter,
            "assignee": assignee,
            "labels": labels,
            "comments": comments[:3],
            "comment_count": len(comments),
            "source_url": f"{self._base}/browse/{key}",
        }

    def _search_issues(self, jql: str, max_results: int = 100) -> list[dict]:
        issues: list[dict] = []
        next_page_token = None
        try:
            while len(issues) < max_results:
                body = {
                    "jql": jql,
                    "maxResults": min(100, max_results - len(issues)),
                    "fields": [
                        "summary", "description", "assignee", "reporter",
                        "created", "updated", "duedate", "comment", "priority",
                        "status", "issuetype", "labels", "project",
                    ],
                }
                if next_page_token:
                    body["nextPageToken"] = next_page_token

                resp = self._request_with_retry(
                    "POST", f"{self._base}/rest/api/3/search/jql",
                    json=body,
                    headers={**self._headers, "Content-Type": "application/json"},
                    timeout=30,
                )
                data = resp.json()
                page_issues = data.get("issues", [])
                issues.extend(page_issues)

                next_page_token = data.get("nextPageToken")
                if data.get("isLast", not next_page_token) or not page_issues:
                    break
            return issues[:max_results]
        except Exception as e:
            print(f"[JiraConnector] search error: {e}")
            return issues

    def _get_comments(self, issue_key: str) -> list[str]:
        try:
            resp = self._request_with_retry(
                "GET", f"{self._base}/rest/api/3/issue/{issue_key}/comment",
                timeout=20,
            )
            comments = []
            for c in resp.json().get("comments", [])[:10]:
                author = (c.get("author") or {}).get("displayName", "Unknown")
                body = self._extract_adf(c.get("body") or {})
                if body.strip():
                    comments.append(f"{author}: {body[:200]}")
            return comments
        except Exception as e:
            print(f"[JiraConnector] get_comments error ({issue_key}): {e}")
            return []

    def _extract_adf(self, adf: dict) -> str:
        if not adf or not isinstance(adf, dict):
            return ""
        texts: list[str] = []
        self._walk_adf(adf, texts)
        return " ".join(texts).strip()

    def _walk_adf(self, node: dict, out: list[str]):
        if node.get("type") == "text":
            out.append(node.get("text", ""))
        for child in node.get("content", []):
            self._walk_adf(child, out)
