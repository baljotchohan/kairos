"""
KAIROS Memory API Routes.

Provides endpoints to retrieve user profiles, session lists,
and full session conversation histories.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from api.auth import get_current_user, UserProfile as AuthUserProfile
from core.user_memory import UserMemory, UserProfile


router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/sessions")
async def get_sessions(
    current_user: AuthUserProfile = Depends(get_current_user)
):
    """List all past conversation sessions for the authenticated user."""
    from core.user_memory import UserMemory
    # We can instantiate UserMemory. It gets db_path from config.
    um = UserMemory()
    return um.list_sessions(current_user.uid)


@router.get("/sessions/{session_id}")
async def get_session_details(
    session_id: str,
    current_user: AuthUserProfile = Depends(get_current_user)
):
    """Retrieve full conversation history of a specific session."""
    um = UserMemory()
    history = um.get_session_history(current_user.uid, session_id)
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found or has no messages."
        )
    return [
        {
            "id": turn.id,
            "role": turn.role,
            "content": turn.content,
            "query_intent": turn.query_intent,
            "timestamp": turn.timestamp,
            "metadata": turn.metadata
        }
        for turn in history
    ]


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: AuthUserProfile = Depends(get_current_user)
):
    """Delete a conversation session."""
    um = UserMemory()
    deleted_count = um.delete_session(current_user.uid, session_id)
    return {"success": True, "deleted_count": deleted_count}


@router.get("/profile")
async def get_profile(
    current_user: AuthUserProfile = Depends(get_current_user)
):
    """Retrieve user's learned profile context."""
    um = UserMemory()
    profile = um.get_profile(current_user.uid)
    return {
        "user_id": profile.user_id,
        "display_name": profile.display_name or current_user.name or "",
        "department": profile.department,
        "role_context": profile.role_context,
        "frequent_topics": profile.frequent_topics,
        "preferred_sources": profile.preferred_sources,
        "interaction_summary": profile.interaction_summary,
        "total_queries": profile.total_queries,
        "last_active": profile.last_active,
        "created_at": profile.created_at
    }


@router.post("/profile/reset")
async def reset_profile(
    current_user: AuthUserProfile = Depends(get_current_user)
):
    """Reset user's learned preferences (retains conversation history)."""
    um = UserMemory()
    um.reset_profile(current_user.uid)
    return {"success": True}
