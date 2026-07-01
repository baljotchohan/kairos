"""
Notion connector — reads pages and databases via Notion API (async httpx).
Requires NOTION_API_KEY (Internal Integration Secret from notion.so/my-integrations).
Pages must be shared with the integration in Notion settings.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import httpx

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionConnector:
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    # ── Public async API ───────────────────────────────────────────────────────

    async def search_pages(self, days_back: int = 30) -> list[dict]:
        """Return all pages+databases shared with the integration, filtered by last edited."""
        if not self._api_key:
            return []

        cutoff = datetime.utcnow() - timedelta(days=days_back)
        results = []
        start_cursor = None

        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                payload: dict = {"page_size": 100}
                if start_cursor:
                    payload["start_cursor"] = start_cursor

                try:
                    resp = await client.post(
                        f"{NOTION_API_BASE}/search",
                        headers=self._headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    print(f"[NotionConnector] search error: {e}")
                    break

                for obj in data.get("results", []):
                    edited = obj.get("last_edited_time", "")
                    try:
                        edited_dt = datetime.fromisoformat(edited.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        edited_dt = datetime.utcnow()

                    if edited_dt < cutoff:
                        continue

                    results.append(obj)

                if not data.get("has_more"):
                    break
                start_cursor = data.get("next_cursor")

        return results

    async def get_page_text(self, block_id: str) -> str:
        """Recursively fetch all text blocks under a page/block, return as plain text."""
        if not self._api_key:
            return ""

        lines: list[str] = []
        start_cursor = None

        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                url = f"{NOTION_API_BASE}/blocks/{block_id}/children"
                params = {"page_size": 100}
                if start_cursor:
                    params["start_cursor"] = start_cursor

                try:
                    resp = await client.get(url, headers=self._headers, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    print(f"[NotionConnector] blocks error ({block_id}): {e}")
                    break

                for block in data.get("results", []):
                    text = self._extract_block_text(block)
                    if text:
                        lines.append(text)

                    # Recurse into child blocks (e.g. toggle, bulleted list with children)
                    if block.get("has_children"):
                        child_text = await self.get_page_text(block["id"])
                        if child_text:
                            lines.append(child_text)

                if not data.get("has_more"):
                    break
                start_cursor = data.get("next_cursor")

        return "\n".join(lines)

    async def get_database_rows(self, database_id: str) -> list[dict]:
        """Query a Notion database and return rows as {title, properties_text, url}."""
        if not self._api_key:
            return []

        rows = []
        start_cursor = None

        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                payload: dict = {"page_size": 100}
                if start_cursor:
                    payload["start_cursor"] = start_cursor

                try:
                    resp = await client.post(
                        f"{NOTION_API_BASE}/databases/{database_id}/query",
                        headers=self._headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    print(f"[NotionConnector] database query error ({database_id}): {e}")
                    break

                for page in data.get("results", []):
                    title = self._extract_page_title(page)
                    props = self._extract_properties_text(page.get("properties", {}))
                    rows.append({
                        "id": page["id"],
                        "title": title,
                        "properties_text": props,
                        "url": page.get("url", ""),
                        "last_edited": page.get("last_edited_time", ""),
                    })

                if not data.get("has_more"):
                    break
                start_cursor = data.get("next_cursor")

        return rows

    async def fetch_all(self, days_back: int = 30) -> list[dict]:
        """
        Fetch all pages and databases. For each page returns:
        {id, title, text, url, date, source_type}
        For databases, fetches rows and their content.
        """
        if not self._api_key:
            return []

        objects = await self.search_pages(days_back=days_back)
        print(f"[NotionConnector] Found {len(objects)} objects in Notion")

        results: list[dict] = []

        async def _process(obj: dict):
            obj_type = obj.get("object")  # "page" or "database"
            obj_id = obj["id"]
            url = obj.get("url", "")
            edited = obj.get("last_edited_time", "")

            try:
                date = datetime.fromisoformat(edited.replace("Z", "+00:00")).strftime("%Y-%m-%d")
            except Exception:
                date = datetime.utcnow().strftime("%Y-%m-%d")

            if obj_type == "database":
                rows = await self.get_database_rows(obj_id)
                for row in rows:
                    row_text = f"{row['title']}\n{row['properties_text']}"
                    results.append({
                        "id": row["id"],
                        "title": row["title"],
                        "text": row_text,
                        "url": row["url"] or url,
                        "date": date,
                        "source": "Notion Database",
                        "source_type": "notion_db",
                    })

            elif obj_type == "page":
                title = self._extract_page_title(obj)
                text = await self.get_page_text(obj_id)
                if not text.strip():
                    return
                results.append({
                    "id": obj_id,
                    "title": title,
                    "text": f"{title}\n\n{text}",
                    "url": url,
                    "date": date,
                    "source": "Notion Page",
                    "source_type": "notion_page",
                })

        await asyncio.gather(*[_process(obj) for obj in objects])
        print(f"[NotionConnector] Fetched {len(results)} Notion items")
        return results

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _extract_block_text(self, block: dict) -> str:
        block_type = block.get("type", "")
        type_data = block.get(block_type, {})

        # Most text-bearing blocks have a "rich_text" array
        rich_text = type_data.get("rich_text", [])
        if rich_text:
            return "".join(rt.get("plain_text", "") for rt in rich_text)

        # Code blocks
        if block_type == "code":
            code = type_data.get("rich_text", [])
            return "".join(rt.get("plain_text", "") for rt in code)

        return ""

    def _extract_page_title(self, page: dict) -> str:
        props = page.get("properties", {})
        for key in ("Name", "Title", "title"):
            prop = props.get(key, {})
            if prop.get("type") == "title":
                rich = prop.get("title", [])
                return "".join(rt.get("plain_text", "") for rt in rich)
        # Fallback: find any title-type property
        for prop in props.values():
            if prop.get("type") == "title":
                rich = prop.get("title", [])
                text = "".join(rt.get("plain_text", "") for rt in rich)
                if text:
                    return text
        return "Untitled"

    def _extract_properties_text(self, properties: dict) -> str:
        parts = []
        for name, prop in properties.items():
            ptype = prop.get("type", "")
            val = ""

            if ptype == "title":
                val = "".join(rt.get("plain_text", "") for rt in prop.get("title", []))
            elif ptype == "rich_text":
                val = "".join(rt.get("plain_text", "") for rt in prop.get("rich_text", []))
            elif ptype == "select":
                sel = prop.get("select")
                val = sel["name"] if sel else ""
            elif ptype == "multi_select":
                val = ", ".join(s["name"] for s in prop.get("multi_select", []))
            elif ptype == "date":
                d = prop.get("date")
                val = d["start"] if d else ""
            elif ptype == "checkbox":
                val = str(prop.get("checkbox", ""))
            elif ptype == "number":
                val = str(prop.get("number", ""))
            elif ptype == "people":
                val = ", ".join(p.get("name", "") for p in prop.get("people", []))
            elif ptype == "status":
                s = prop.get("status")
                val = s["name"] if s else ""

            if val:
                parts.append(f"{name}: {val}")

        return "\n".join(parts)
