from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings


app = FastAPI(
    title="SIAMP API",
    description="Sistema Integrado de Apontamento, Machine Learning e Gestão de Produção",
    version="1.1.0",
)

# CORS controlado por variável de ambiente.
# Em desenvolvimento, use por exemplo:
# CORS_ORIGINS=http://localhost:5173,http://localhost:5500
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "online",
        "sistema": "SIAMP",
        "versao": "1.1.0",
    }
