"""
Cria o primeiro usuário administrador, se ele ainda não existir, e
garante que ele fique protegido, ativo, e com perfil ADMIN - mesmo se
a conta já existir mas tiver sido excluída/recriada, desativada, ou
rebaixada de perfil por engano. Idempotente: pode ser rodado várias
vezes sem risco de duplicar (constraint de e-mail único) - inclusive
é executado automaticamente a cada início do container (ver
entrypoint.sh) quando ADMIN_SENHA está definida, sem precisar rodar
manualmente no terminal. A senha e o nome de uma conta já existente
NUNCA são sobrescritos por este script, mesmo que a conta precise de
outro ajuste - evita desfazer uma troca de senha feita
deliberadamente depois pela tela de Usuários.

Uso (dentro do container, valores padrão entre parênteses):
    docker compose exec backend_api python -m app.scripts.create_admin \\
        --nome "Admin" \\
        --email admin@empresa.com \\
        --senha "troque-esta-senha"

Ou via variáveis de ambiente (usado automaticamente pelo entrypoint.sh
a cada `docker compose up`, sem precisar do comando acima):
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
            alteracoes = []
            if not existente.protegido:
                existente.protegido = True
                alteracoes.append("marcado como protegido")
            if not existente.ativo:
                existente.ativo = True
                alteracoes.append("reativado")
            if existente.perfil != "ADMIN":
                existente.perfil = "ADMIN"
                alteracoes.append("perfil restaurado para ADMIN")

            if alteracoes:
                db.commit()
                print(f"[create_admin] Usuário '{args.email}' já existia (id={existente.id}) - {', '.join(alteracoes)}.")
            else:
                print(f"[create_admin] Usuário '{args.email}' já existe (id={existente.id}) e já está correto; nada a fazer.")
            return

        usuario = Usuario(
            nome=args.nome,
            email=args.email,
            senha_hash=gerar_hash_senha(args.senha),
            perfil="ADMIN",
            ativo=True,
            protegido=True,
        )
        db.add(usuario)
        db.commit()
        print(f"[create_admin] Usuário admin '{args.email}' criado com sucesso, já protegido contra exclusão/desativação.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
