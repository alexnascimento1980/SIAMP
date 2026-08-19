from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.router import api_router
from app.core.config import settings
from app.core.rate_limit import limiter


app = FastAPI(
    title="SIAMP API",
    description="Sistema Integrado de Apontamento, Machine Learning e Gestão de Produção",
    version="1.1.0",
)

# Rate limiting (usado principalmente em /auth/login, para mitigar força
# bruta de senha). O handler traduz o estouro de limite em HTTP 429.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS controlado por variável de ambiente.
# Em desenvolvimento, use por exemplo:
# CORS_ORIGINS=http://localhost:5173,http://localhost:5500
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    # Content-Disposition não está na lista de headers "simples" que o
    # navegador expõe ao JS por padrão em respostas cross-origin (o
    # frontend roda em porta diferente do backend). Sem isto, o nome do
    # arquivo do relatório (definido no header pelo backend) fica
    # invisível para o histórico.js, mesmo a resposta chegando certa.
    expose_headers=["Content-Disposition"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "online",
        "sistema": "SIAMP",
        "versao": "1.1.0",
    }
