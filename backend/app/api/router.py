from fastapi import APIRouter

from app.api.routes import (
    analytics,
    appointments,
    auth,
    calls,
    clinic,
    doctors,
    health,
    knowledge,
    livekit,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(livekit.router)
api_router.include_router(calls.router)
api_router.include_router(appointments.router)
api_router.include_router(doctors.router)
api_router.include_router(knowledge.router)
api_router.include_router(clinic.router)
api_router.include_router(analytics.router)
