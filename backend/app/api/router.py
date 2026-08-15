from fastapi import APIRouter

from app.api.v1 import auth, dashboard, maquinas, paradas, predictions, turnos, usuarios

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)
api_router.include_router(maquinas.router)
api_router.include_router(turnos.router)
api_router.include_router(paradas.router)
api_router.include_router(dashboard.router)
api_router.include_router(predictions.router)