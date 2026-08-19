"""
Cria o primeiro usuário administrador, se ele ainda não existir.
Idempotente: pode ser rodado várias vezes sem risco de duplicar ou
quebrar por causa da constraint de e-mail único.

Uso (dentro do container, valores padrão entre parênteses):
    docker compose exec backend_api python -m app.scripts.create_admin \\
        --nome "Admin" \\
        --email admin@empresa.com \\
        --senha "troque-esta-senha"

Ou via variáveis de ambiente (útil para automatizar/CI):
    ADMIN_NOME="Admin" ADMIN_EMAIL="admin@empresa.com" ADMIN_SENHA="troque-esta-senha" \\
        docker compose exec -T backend_api python -m app.scripts.create_admin
"""
import argparse
import os
import sys

from app.core.database import SessionLocal
from app.core.security import gerar_hash_senha
from app.models.usuario import Usuario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nome", default=os.getenv("ADMIN_NOME", "Admin"))
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL", "admin@empresa.com"))
    parser.add_argument("--senha", default=os.getenv("ADMIN_SENHA"))
    args = parser.parse_args()

    if not args.senha:
        print(
            "[create_admin] Informe a senha via --senha ou variável de "
            "ambiente ADMIN_SENHA.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    db = SessionLocal()
    try:
        existente = db.query(Usuario).filter(Usuario.email == args.email).first()
        if existente:
            print(f"[create_admin] Usuário '{args.email}' já existe (id={existente.id}); nada a fazer.")
            return

        usuario = Usuario(
            nome=args.nome,
            email=args.email,
            senha_hash=gerar_hash_senha(args.senha),
            perfil="ADMIN",
            ativo=True,
        )
        db.add(usuario)
        db.commit()
        print(f"[create_admin] Usuário admin '{args.email}' criado com sucesso.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
