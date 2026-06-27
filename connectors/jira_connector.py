"""
Jira connector — full read access via Jira REST API v3.
Pure httpx, no Jira Python client dependency.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx

from config import config


class JiraConnector:
    def __init__(self):
        self._base = config.JIRA_URL.rstrip("/") if config.JIRA_URL else ""
        self._auth = (config.JIRA_EMAIL, config.JIRA_API_TOKEN)

    def _ok(self) -> bool:
        return bool(config.JIRA_URL and config.JIRA_EMAIL and config.JIRA_API_TOKEN)

    # ── Public async API ───────────────────────────────────────────────────────

    async def get_recent_issues(self, days_back: int = 30) -> list[dict]:
        if not self._ok():
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_issues_sync, days_back)

    async def get_my_issues(self, status_filter: str | None = None) -> list[dict]:
        """Issues assigned to the authenticated user, optionally filtered by status."""
        if not self._ok():
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_my_issues_sync, status_filter)

    async def get_projects(self) -> list[dict]:
        """List all Jira projects in the workspace."""
        if not self._ok():
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_projects_sync)

    async def search_issues(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search across issue summaries and descriptions."""
        if not self._ok():
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_issues_text_sync, query, limit)

    async def get_issue_stats(self) -> dict:
        """Return counts of issues by status across the whole workspace."""
        if not self._ok():
            return {}
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._issue_stats_sync)

    async def get_sprint_status(self, project_key: str | None = None) -> dict:
        """Get active sprint information for a project (or all projects)."""
        if not self._ok():
            return {}
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sprint_status_sync, project_key)

    async def get_issue(self, issue_key: str) -> Optional[dict]:
        """Fetch a single issue by key (e.g. 'KAI-42')."""
        if not self._ok():
            return None
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_issue_sync, issue_key)

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
            resp = httpx.get(
                f"{self._base}/rest/api/3/project/search",
                auth=self._auth,
                headers={"Accept": "application/json"},
                params={"maxResults": 50, "orderBy": "lastIssueUpdatedTime"},
                timeout=20,
            )
            resp.raise_for_status()
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
                resp = httpx.post(
                    f"{self._base}/rest/api/3/search/jql",
                    auth=self._auth,
                    json={"jql": jql, "maxResults": 0, "fields": []},
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                    timeout=15,
                )
                resp.raise_for_status()
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
            resp = httpx.get(
                f"{self._base}/rest/agile/1.0/board",
                auth=self._auth,
                headers={"Accept": "application/json"},
                params=params,
                timeout=20,
            )
            resp.raise_for_status()
            boards = resp.json().get("values", [])
            if not boards:
                return {"error": "No Scrum/Kanban boards found."}

            result = {"boards": []}
            for board in boards[:3]:
                board_id = board.get("id")
                board_name = board.get("name", "")
                try:
                    sprint_resp = httpx.get(
                        f"{self._base}/rest/agile/1.0/board/{board_id}/sprint",
                        auth=self._auth,
                        headers={"Accept": "application/json"},
                        params={"state": "active"},
                        timeout=15,
                    )
                    sprint_resp.raise_for_status()
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
            resp = httpx.get(
                f"{self._base}/rest/api/3/issue/{issue_key}",
                auth=self._auth,
                headers={"Accept": "application/json"},
                timeout=20,
            )
            resp.raise_for_status()
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
        try:
            resp = httpx.post(
                f"{self._base}/rest/api/3/search/jql",
                auth=self._auth,
                json={
                    "jql": jql,
                    "maxResults": max_results,
                    "fields": [
                        "summary", "description", "assignee", "reporter",
                        "created", "updated", "duedate", "comment", "priority",
                        "status", "issuetype", "labels", "project",
                    ],
                },
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get("issues", [])
        except Exception as e:
            print(f"[JiraConnector] search error: {e}")
            return []

    def _get_comments(self, issue_key: str) -> list[str]:
        try:
            resp = httpx.get(
                f"{self._base}/rest/api/3/issue/{issue_key}/comment",
                auth=self._auth,
                headers={"Accept": "application/json"},
                timeout=20,
            )
            resp.raise_for_status()
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
