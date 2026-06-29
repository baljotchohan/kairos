"""
KAIROS WebSocket handler — real-time streaming query responses.

Connect to ws://localhost:8000/ws
Send: {"type": "query", "question": "Why do we use AWS?"}
Receive: stream of tokens, then a final sources message
"""

from __future__ import annotations

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.auth import verify_token

log = logging.getLogger(__name__)

ws_router = APIRouter()


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "Authentication required. Missing token parameter."})
        await websocket.close()
        return

    try:
        user_profile = verify_token(token)
    except Exception as e:
        await websocket.accept()
        log.warning("WebSocket auth error", exc_info=True)
        await websocket.send_json({"type": "error", "message": "Authentication failed. Please sign in again."})
        await websocket.close()
        return

    await websocket.accept()
    orchestrator = websocket.app.state.orchestrator
    user_id = user_profile.uid

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = data.get("type")

            # ── Query: stream answer token by token ───────────────────────────
            if msg_type == "query":
                question = data.get("question", "").strip()
                session_id = data.get("session_id")
                if not question:
                    await websocket.send_json({"type": "error", "message": "Empty question"})
                    continue

                await websocket.send_json({"type": "start", "question": question})

                async def stream_cb(msg: dict):
                    await websocket.send_json(msg)

                try:
                    result = await orchestrator.query_with_memory(
                        question=question,
                        user_id=user_id,
                        session_id=session_id,
                        stream_callback=stream_cb
                    )
                    
                    await websocket.send_json({
                        "type": "done",
                        "answer": result["answer"],
                        "sources": [
                            {
                                "id": s["id"],
                                "title": s["title"],
                                "date": s["date"],
                                "source": s["source"],
                                "source_url": s["source_url"],
                            }
                            for s in result["sources"]
                        ],
                        "intent": result["intent"],
                        "confidence": result["confidence"],
                        "traces": result["traces"],
                        "session_id": result["session_id"],
                        "user_context": result["user_context"]
                    })
                except WebSocketDisconnect:
                    raise
                except Exception as e:
                    log.error("Query failed for user %s", user_id, exc_info=True)
                    try:
                        await websocket.send_json({"type": "error", "message": "Something went wrong while processing your question. Please try again."})
                    except Exception:
                        pass
                    continue

            # ── Ingest: trigger ingestion with progress updates ────────────────
            elif msg_type == "ingest":
                async def progress(msg: str):
                    await websocket.send_json({"type": "progress", "message": msg})

                try:
                    result = await orchestrator.run_ingestion(user_id=user_id, progress_callback=progress)
                    await websocket.send_json({
                        "type": "ingest_done",
                        "decisions_extracted": result.get("decisions_extracted", 0),
                        "errors": result.get("errors", []),
                    })
                except WebSocketDisconnect:
                    raise
                except Exception as e:
                    log.error("Ingestion failed for user %s", user_id, exc_info=True)
                    try:
                        await websocket.send_json({"type": "error", "message": "Ingestion encountered an error. Check your connected sources and try again."})
                    except Exception:
                        pass

            # ── Stats ─────────────────────────────────────────────────────────
            elif msg_type == "stats":
                memory = websocket.app.state.memory
                await websocket.send_json({
                    "type": "stats",
                    "data": memory.graph.stats(user_id=user_id),
                })

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error("Unexpected WebSocket error for user %s", user_id if "user_id" in dir() else "unknown", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": "An unexpected error occurred. Please refresh and try again."})
        except Exception:
            pass
