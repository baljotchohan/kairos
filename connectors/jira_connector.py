"""
Jira connector — reads issues, decisions, and project history via Jira REST API v3.
Uses basic auth (email + API token). No Jira Python client dependency — pure httpx.
Returns gracefully empty list when credentials are missing.
"""

from __future__ import annotations

import asyncio

import httpx

from config import config


class JiraConnector:
    def __init__(self):
        self._base = config.JIRA_URL.rstrip("/") if config.JIRA_URL else ""
        self._auth = (config.JIRA_EMAIL, config.JIRA_API_TOKEN)

    # ── Public async API ───────────────────────────────────────────────────────

    async def get_recent_issues(self, days_back: int) -> list[dict]:
        """
        Fetch decision-relevant issues updated in the last `days_back` days.
        Returns list of dicts: {key, summary, description, comments, status,
                                created, updated, reporter, assignee, labels}.
        """
        if not config.JIRA_URL or not config.JIRA_EMAIL or not config.JIRA_API_TOKEN:
            return []

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_issues_sync, days_back)

    # ── Sync internals ─────────────────────────────────────────────────────────

    def _get_issues_sync(self, days_back: int) -> list[dict]:
        # Use relative date syntax — new Jira Cloud requires /rest/api/3/search/jql
        jql_queries = [
            f'created >= -{days_back}d ORDER BY created DESC',
            f'updated >= -{days_back}d ORDER BY updated DESC',
        ]

        seen: set[str] = set()
        results: list[dict] = []

        for jql in jql_queries:
            issues = self._search_issues(jql, max_results=100)
            for issue in issues:
                key = issue.get("key", "")
                if not key or key in seen:
                    continue
                seen.add(key)

                fields = issue.get("fields", {})
                summary = fields.get("summary", "")
                description = self._extract_adf(fields.get("description") or {})
                status = (fields.get("status") or {}).get("name", "")
                created = (fields.get("created") or "")[:10]
                updated = (fields.get("updated") or "")[:10]
                reporter = (fields.get("reporter") or {}).get("displayName", "")
                assignee = (fields.get("assignee") or {}).get("displayName", "")
                labels = fields.get("labels", [])

                comments = self._get_comments(key)

                results.append({
                    "key": key,
                    "summary": summary,
                    "description": description,
                    "comments": comments,
                    "status": status,
                    "created": created,
                    "updated": updated,
                    "reporter": reporter,
                    "assignee": assignee,
                    "labels": labels,
                    "source_url": f"{self._base}/browse/{key}",
                })

        print(f"[JiraConnector] Fetched {len(results)} relevant issues")
        return results

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
                        "created", "updated", "comment", "priority",
                        "status", "issuetype", "labels",
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
            for c in resp.json().get("comments", [])[:20]:
                author = (c.get("author") or {}).get("displayName", "Unknown")
                body = self._extract_adf(c.get("body") or {})
                if body.strip():
                    comments.append(f"{author}: {body}")
            return comments
        except Exception as e:
            print(f"[JiraConnector] get_comments error ({issue_key}): {e}")
            return []

    def _extract_adf(self, adf: dict) -> str:
        """Extract plain text from Atlassian Document Format (ADF)."""
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
