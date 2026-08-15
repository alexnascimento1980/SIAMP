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
    report_recipients: list[str]


def _build_settings() -> Settings:
    cors_value = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5500",
    )
    recipients_value = os.getenv(
        "REPORT_RECIPIENTS",
        "gerente.producao@empresa.com,supervisao@empresa.com",
    )

    return Settings(
        cors_origins=_parse_origins(cors_value),
        smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_pass=os.getenv("SMTP_PASS", ""),
        report_recipients=_parse_origins(recipients_value),
    )


settings = _build_settings()
