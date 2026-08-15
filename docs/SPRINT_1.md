# SIAMP — Sprint 1: Estabilização do Backend

## Objetivo

Organizar o fluxo principal da API e remover duplicidade de responsabilidades sem alterar o modelo de negócio principal.

## Correções

- `main.py` passou a conter somente configuração da aplicação e registro de routers.
- O endpoint `/api/v1/turnos/fechamento` ficou somente em `api/v1/turnos.py`.
- A regra de negócio foi movida para `services/turno_service.py`.
- CORS passou a ser configurável por `CORS_ORIGINS`.
- Credenciais SMTP passaram a ser obtidas por variáveis de ambiente.
- Status de assinatura foi padronizado como `ASSINADO_DIGITALMENTE`.
- O schema do fechamento recebeu validações básicas.
- O envio de e-mail só é agendado quando SMTP está configurado.
- A versão da API foi atualizada para `1.1.0`.

## Importante

Esta Sprint **não implementa ainda o OEE industrial completo**. O cálculo atual de `eficiencia_oee` permanece compatível com a versão existente para evitar alteração de escopo. A reformulação para Disponibilidade × Performance × Qualidade fica para a Sprint 3.

## Validação

Após substituir os arquivos:

1. Subir PostgreSQL.
2. Subir backend.
3. Acessar `/`.
4. Acessar `/docs`.
5. Testar `POST /api/v1/turnos/fechamento`.
6. Confirmar que não existe mais `POST /turnos/fechamento` diretamente no `main.py`.
