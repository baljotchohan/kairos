from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from api.auth import get_current_user, UserProfile
from core.personas import AgentPersonaStore, TONE_PRESETS

router = APIRouter()


def get_persona_store(request: Request) -> AgentPersonaStore:
    memory = request.app.state.memory
    return AgentPersonaStore(db_path=memory.db_path)


class PersonaUpdateRequest(BaseModel):
    display_name: str | None = None
    tone_preset: str | None = None


@router.get("/agents")
async def list_agents(
    store: AgentPersonaStore = Depends(get_persona_store),
    current_user: UserProfile = Depends(get_current_user),
):
    """List every internal agent with this user's display name/tone override, or the default."""
    return {"agents": store.list_for_user(current_user.uid), "tone_presets": list(TONE_PRESETS)}


@router.put("/agents/{agent_key}")
async def update_agent_persona(
    agent_key: str,
    body: PersonaUpdateRequest,
    store: AgentPersonaStore = Depends(get_persona_store),
    current_user: UserProfile = Depends(get_current_user),
):
    """Rename an agent and/or change its tone, scoped to this user only. Purely a
    presentation layer — never touches the underlying agent's extraction logic."""
    try:
        return store.upsert(current_user.uid, agent_key, display_name=body.display_name, tone_preset=body.tone_preset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/agents/{agent_key}")
async def reset_agent_persona(
    agent_key: str,
    store: AgentPersonaStore = Depends(get_persona_store),
    current_user: UserProfile = Depends(get_current_user),
):
    """Reset an agent back to its default display name/tone for this user."""
    return store.reset(current_user.uid, agent_key)
