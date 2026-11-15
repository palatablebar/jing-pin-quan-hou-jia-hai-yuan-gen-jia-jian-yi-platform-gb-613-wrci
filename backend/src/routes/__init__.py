"""路由聚合：统一 /api 前缀（Nginx 反代时剥掉 /api）。"""
from fastapi import APIRouter

from src.routes.advices import router as advices_router
from src.routes.audit import router as audit_router
from src.routes.auth import router as auth_router
from src.routes.competitors import router as competitors_router
from src.routes.exports import router as exports_router
from src.routes.health import router as health_router
from src.routes.overview import router as overview_router
from src.routes.rules import router as rules_router
from src.routes.runs import router as runs_router
from src.routes.skus import router as skus_router
from src.routes.snapshots import router as snapshots_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(overview_router)
api_router.include_router(competitors_router)
api_router.include_router(skus_router)
api_router.include_router(rules_router)
api_router.include_router(snapshots_router)
api_router.include_router(runs_router)
api_router.include_router(advices_router)
api_router.include_router(exports_router)
api_router.include_router(audit_router)
