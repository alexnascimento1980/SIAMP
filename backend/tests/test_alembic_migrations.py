import ast
from pathlib import Path

VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"

# alembic_version.version_num é VARCHAR(32) por padrão (definido pelo
# próprio Alembic ao criar a tabela de controle, não pelo nosso
# schema). Um id de revisão maior que isso faz o "alembic upgrade"
# falhar bem no fim de cada migration - depois de já ter aplicado as
# mudanças de schema dela, no meio da mesma transação - com
# psycopg2.errors.StringDataRightTruncation ao tentar gravar o novo
# id na tabela de controle. Isso não aparece em SQLite (usado nos
# testes) porque SQLite não impõe limite de tamanho em colunas TEXT/
# VARCHAR, then esse teste lê os arquivos diretamente, sem depender
# de rodar contra um Postgres de verdade.
LIMITE_VERSION_NUM = 32


def _extrair_revision_ids(caminho_arquivo: Path) -> tuple[str | None, str | None]:
    """Lê 'revision' e 'down_revision' de um arquivo de migration sem
    executá-lo (só parseando a árvore sintática) - mais seguro e
    rápido do que importar o módulo."""
    arvore = ast.parse(caminho_arquivo.read_text(encoding="utf-8"))
    revision = None
    down_revision = None
    for node in arvore.body:
        if isinstance(node, ast.Assign):
            for alvo in node.targets:
                if not isinstance(alvo, ast.Name):
                    continue
                valor = node.value
                texto = valor.value if isinstance(valor, ast.Constant) else None
                if alvo.id == "revision":
                    revision = texto
                elif alvo.id == "down_revision":
                    down_revision = texto
    return revision, down_revision


def test_nenhum_id_de_migration_passa_do_limite_do_postgres():
    arquivos_migration = sorted(VERSIONS_DIR.glob("*.py"))
    assert arquivos_migration, "Nenhum arquivo de migration encontrado - caminho errado?"

    problemas = []
    for arquivo in arquivos_migration:
        revision, _down_revision = _extrair_revision_ids(arquivo)
        if revision and len(revision) > LIMITE_VERSION_NUM:
            problemas.append(f"{arquivo.name}: revision '{revision}' tem {len(revision)} caracteres")

    assert not problemas, (
        "Migration(s) com id de revisão maior que 32 caracteres "
        "(limite da coluna alembic_version.version_num no Postgres):\n"
        + "\n".join(problemas)
    )


def test_cadeia_de_migrations_esta_integra():
    """Confere que down_revision de cada migration aponta para um
    revision que realmente existe em algum outro arquivo - um id
    digitado errado (ex.: cópia/cola de outro arquivo) quebraria a
    cadeia silenciosamente até alguém rodar 'alembic upgrade' de
    verdade."""
    arquivos_migration = sorted(VERSIONS_DIR.glob("*.py"))
    revisions_existentes = set()
    down_revisions_referenciadas = set()

    for arquivo in arquivos_migration:
        revision, down_revision = _extrair_revision_ids(arquivo)
        assert revision, f"{arquivo.name} não define 'revision'"
        revisions_existentes.add(revision)
        if down_revision:
            down_revisions_referenciadas.add(down_revision)

    orfaos = down_revisions_referenciadas - revisions_existentes
    assert not orfaos, (
        "down_revision referenciando uma migration que não existe: "
        f"{orfaos}"
    )
