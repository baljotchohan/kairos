from fastapi import APIRouter

from api.routes.health import router as health_router
from api.routes.query import router as query_router
from api.routes.ingest import router as ingest_router
from api.routes.admin import router as admin_router
from api.routes.decisions import router as decisions_router
from api.routes.memory import router as memory_router
from api.routes.oauth import router as oauth_router
from api.routes.agents import router as agents_router
from api.routes.mcp_remote import mcp_connect_router
from api.routes.mcp_oauth import mcp_oauth_api_router

router = APIRouter()

# Health checks
router.include_router(health_router)

# Mount endpoints under both legacy /api and v1 /api/v1 prefixes
router.include_router(query_router, prefix="/api")
router.include_router(query_router, prefix="/api/v1")

router.include_router(ingest_router, prefix="/api")
router.include_router(ingest_router, prefix="/api/v1")

router.include_router(admin_router, prefix="/api")
router.include_router(admin_router, prefix="/api/v1")

router.include_router(decisions_router, prefix="/api")
router.include_router(decisions_router, prefix="/api/v1")

router.include_router(memory_router, prefix="/api")
router.include_router(memory_router, prefix="/api/v1")

router.include_router(oauth_router, prefix="/api")
router.include_router(oauth_router, prefix="/api/v1")

router.include_router(agents_router, prefix="/api")
router.include_router(agents_router, prefix="/api/v1")

router.include_router(mcp_connect_router, prefix="/api")
router.include_router(mcp_connect_router, prefix="/api/v1")

router.include_router(mcp_oauth_api_router, prefix="/api")
router.include_router(mcp_oauth_api_router, prefix="/api/v1")
