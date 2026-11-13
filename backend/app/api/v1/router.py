from fastapi import APIRouter

from app.api.v1.admin_auth import router as admin_auth_router
from app.api.v1.admin_documents import router as admin_documents_router
from app.api.v1.admin_workflows import router as admin_workflows_router
from app.api.v1.citizen import router as citizen_router
from app.api.v1.citizen_auth import router as citizen_auth_router
from app.api.v1.eligibility import router as eligibility_router
from app.api.v1.grounding import router as grounding_router
from app.api.v1.monitoring import router as monitoring_router
from app.api.v1.schemes import router as scheme_router

router = APIRouter(prefix="/api/v1")
router.include_router(scheme_router)
router.include_router(eligibility_router)
router.include_router(admin_auth_router)
router.include_router(admin_documents_router)
router.include_router(admin_workflows_router)
router.include_router(grounding_router)


router.include_router(monitoring_router)

router.include_router(citizen_router)
router.include_router(citizen_auth_router)
