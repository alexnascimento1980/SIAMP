import os
from dataclasses import dataclass


def _parse_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


@dataclass(frozen=True)
class Settings:
    cors_origins: list[str]
    smtp_server: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    smtp_from: str
    report_recipients: list[str]
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_expires_minutes: int
    cookie_secure: bool


def _build_settings() -> Settings:
    cors_value = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5500",
    )
    recipients_value = os.getenv(
        "REPORT_RECIPIENTS",
        "gerente.producao@empresa.com,supervisao@empresa.com",
    )

    jwt_secret_key = os.getenv("JWT_SECRET_KEY", "")
    if not jwt_secret_key:
        # Falha alto (fail-loud) em vez de rodar com uma chave previsível:
        # um SECRET_KEY ausente/óbvio permitiria forjar tokens válidos.
        raise RuntimeError(
            "JWT_SECRET_KEY não configurada. Defina uma chave aleatória "
            "forte na variável de ambiente JWT_SECRET_KEY."
        )

    smtp_user_value = os.getenv("SMTP_USER", "")

    return Settings(
        cors_origins=_parse_origins(cors_value),
        smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=smtp_user_value,
        smtp_pass=os.getenv("SMTP_PASS", ""),
        # Em provedores transacionais (Brevo, SendGrid etc.), o usuário
        # de autenticação (SMTP_USER) costuma ser só um token/login
        # técnico, diferente do endereço que precisa ser validado como
        # remetente (From:) - por isso são variáveis separadas. Sem
        # SMTP_FROM definida, cai no SMTP_USER (comportamento do Gmail,
        # onde os dois são o mesmo endereço).
        smtp_from=os.getenv("SMTP_FROM", "") or smtp_user_value,
        report_recipients=_parse_origins(recipients_value),
        jwt_secret_key=jwt_secret_key,
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        jwt_expires_minutes=int(os.getenv("JWT_EXPIRES_MINUTES", "480")),
        # Padrão seguro (exige HTTPS) caso a variável não seja definida.
        # O .env.example de desenvolvimento define explicitamente "false",
        # já que o fluxo local roda em http://localhost sem TLS.
        cookie_secure=os.getenv("COOKIE_SECURE", "true").lower() == "true",
    )


settings = _build_settings()
