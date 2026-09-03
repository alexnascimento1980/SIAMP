# Deploy no Render + Supabase

Guia para publicar o SIAMP no [Render](https://render.com) (hospedagem)
com [Supabase](https://supabase.com) como banco Postgres.

## Por que um único serviço, não dois?

`onrender.com` está na [Public Suffix List](https://publicsuffix.org/) -
isso faz o navegador tratar `algo-a.onrender.com` e `algo-b.onrender.com`
como **sites diferentes**, mesmo sendo do mesmo projeto. O cookie de
sessão do SIAMP (`SameSite=Lax`, necessário para a autenticação
funcionar) não seria enviado entre eles, e o login pareceria funcionar
mas as chamadas seguintes dariam 401.

O plano gratuito do Render também não permite tráfego de rede privada
entre dois serviços separados (isso só existe em planos pagos).

Por isso, `deploy/Dockerfile` empacota **frontend e backend no mesmo
container**: o nginx serve as páginas estáticas e repassa `/api/` para
o backend, que roda localmente dentro do mesmo container, sem nunca
ficar exposto fora dele. Para o navegador, é tudo uma origem só.

> **Tem um plano pago do Render e prefere dois serviços separados?**
> `frontend/nginx.conf.template` já suporta isso via a variável
> `BACKEND_INTERNAL_URL` (é o que o `docker-compose.yml` local usa) -
> crie o backend como _Private Service_, pegue o endereço interno dele
> em _Connect → Internal_ e use como `BACKEND_INTERNAL_URL` no
> frontend. Para a maioria dos casos de teste, o serviço único do
> `deploy/Dockerfile` é mais simples e já resolve.

## 1. Banco de dados no Supabase

1. Crie uma conta e um projeto em [supabase.com](https://supabase.com).
2. No painel do projeto: **Settings → Database → Connection string**.
3. Escolha a aba **Session pooler** (não a conexão direta) - ela
   funciona por IPv4, necessário para se conectar a partir do Render.
   A conexão direta do Supabase é só IPv6, e pode não funcionar
   dependendo da infraestrutura do Render.
4. Copie a connection string completa (formato
   `postgresql://postgres.xxxx:SENHA@aws-x-regiao.pooler.supabase.com:5432/postgres`)
   - já vem com a senha do banco preenchida (a que você definiu ao
     criar o projeto). Guarde essa string - é o `DATABASE_URL`.

> Não é necessário adicionar `+psycopg2` na string - o SQLAlchemy já
> usa o psycopg2 automaticamente para URLs `postgresql://`.

## 2. Criar o serviço no Render

1. Em [dashboard.render.com](https://dashboard.render.com): **New →
   Web Service**.
2. Conecta o repositório do GitHub do projeto.
3. Configuração do serviço:
   - **Runtime**: Docker
   - **Dockerfile Path**: `deploy/Dockerfile`
   - **Docker Build Context Directory**: `.` (raiz do repositório -
     importante, o Dockerfile copia tanto `backend/` quanto
     `frontend/`)
   - **Instance Type**: Free (ou o que preferir)
4. Variáveis de ambiente (**Environment**), as mesmas que já existem
   no `.env` local, com os valores certos para produção:

   | Variável            | Valor                                                                                                                                                                         |
   | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
   | `DATABASE_URL`      | A connection string do Supabase (passo 1)                                                                                                                                     |
   | `JWT_SECRET_KEY`    | Gere uma nova - **não reaproveite** a do `.env` local. Rode `python -c "import secrets; print(secrets.token_urlsafe(64))"`                                                    |
   | `COOKIE_SECURE`     | `true` (o Render serve tudo via HTTPS)                                                                                                                                        |
   | `CORS_ORIGINS`      | A URL pública do próprio serviço (ex.: `https://siamp.onrender.com`) - você só sabe isso depois do primeiro deploy; pode deixar em branco e voltar aqui para preencher depois |
   | `SMTP_FROM`         | O e-mail remetente validado no Brevo                                                                                                                                          |
   | `BREVO_API_KEY`     | Chave da **API** do Brevo (Settings → SMTP & API → API Keys) - **não** a chave SMTP                                                                                           |
   | `REPORT_RECIPIENTS` | Opcional - prefira cadastrar pela tela Destinatários depois do primeiro login                                                                                                 |
   | `SEED_ON_START`     | `true` no primeiro deploy (carrega as 102 peças e as 6 máquinas de exemplo); pode deixar `true` sempre, é seguro repetir (usa `ON CONFLICT DO NOTHING`)                       |
   | `ADMIN_EMAIL` / `ADMIN_SENHA` / `ADMIN_NOME` | Opcional - cria o primeiro usuário admin automaticamente, sem precisar de acesso a shell. Ver passo 3 abaixo.                                              |

5. Clica em **Create Web Service**. O primeiro build demora alguns
   minutos (instala dependências Python + nginx).

> **Por que Brevo via API, e não SMTP com Gmail?** Desde setembro de
> 2025, o Render **bloqueia tráfego de saída para as portas SMTP
> (25, 465, 587) em serviços gratuitos** ([changelog
> oficial](https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports)).
> O SMTP local (ex.: Gmail) continua funcionando normalmente no seu
> `docker-compose.yml`, mas não funcionaria no Render gratuito -
> `BREVO_API_KEY` usa a API HTTPS do Brevo (porta 443, não afetada
> por esse bloqueio) em vez de SMTP. Sem essa variável definida, o
> sistema volta a usar SMTP normalmente (é o que acontece localmente).
> **Confirmado em produção**: com `BREVO_API_KEY` configurada no
> Render, o e-mail de fechamento de turno chega normalmente.

## 3. Primeiro acesso

O `entrypoint.sh` já roda `alembic upgrade head` (e o seed, se
`SEED_ON_START=true`) automaticamente toda vez que o container sobe -
não precisa de nenhum passo manual de migration.

O que falta é **criar o primeiro usuário administrador**, já que não
existe cadastro público. Duas formas:

**Opção 1 — automática (recomendada, principalmente aqui):** como o
plano gratuito do Render não dá acesso a shell dentro do container, o
jeito mais simples é deixar o próprio `entrypoint.sh` garantir essa
conta sozinho a cada início do container - sem precisar rodar nada da
sua máquina. Adiciona três variáveis de ambiente ao serviço no Render
(mesma tabela do passo 2):

| Variável       | Valor                                              |
| -------------- | --------------------------------------------------- |
| `ADMIN_NOME`   | Nome de exibição, ex.: `Admin`                       |
| `ADMIN_EMAIL`  | E-mail de login do primeiro admin                    |
| `ADMIN_SENHA`  | Senha forte - troque depois pela tela de Usuários se quiser |

No próximo deploy (ou `Manual Deploy` pelo painel), essa conta é
criada automaticamente - já nasce marcada como **protegida** contra
exclusão/desativação acidental, e é restaurada sozinha (ativa,
perfil ADMIN, protegida) se um dia for excluída ou alterada por
engano, sem precisar de nenhuma ação manual. A senha nunca é
sobrescrita automaticamente depois da primeira criação, mesmo que a
variável continue definida - trocar pela tela de Usuários é seguro.

**Opção 2 — manual, sob demanda:** conectando no mesmo banco Supabase
direto da sua máquina:

```bash
cd backend
pip install -r requirements-dev.txt   # se ainda não tiver localmente

# Windows PowerShell:
$env:DATABASE_URL="<a mesma connection string do Supabase usada no Render>"
$env:JWT_SECRET_KEY="<mesmo valor configurado no Render>"

python -m app.scripts.create_admin --nome "Admin" --email admin@empresa.com --senha "troque-esta-senha"
```

Depois disso, acessa a URL pública que o Render te deu (algo como
`https://siamp.onrender.com`) e faz login normalmente.

## 4. Depois do primeiro deploy

- Volta nas variáveis de ambiente do serviço e preenche `CORS_ORIGINS`
  com a URL pública real, agora que você já sabe qual é.
- Todo `git push` na branch conectada dispara um novo deploy
  automaticamente (auto-deploy vem ligado por padrão).

## 5. Levar máquinas/peças customizadas do ambiente local

Se você já cadastrou máquinas ou peças reais (além das que vêm no
`database/seeds.sql` genérico) no seu ambiente local, dá para exportar
esses dados e aplicar no Supabase, em vez de digitar tudo de novo pela
tela.

O volume `database/` dentro do container é montado somente leitura, então
o arquivo precisa ser gerado num caminho gravável (`/tmp`) e depois
copiado para fora:

```powershell
# 1. Exporta do banco de ORIGEM (local), de dentro do container
docker compose exec backend_api sh -c "EXPORT_FILE=/tmp/exportado_catalogos.sql python -m app.scripts.exportar_catalogos"
docker compose cp backend_api:/tmp/exportado_catalogos.sql database/exportado_catalogos.sql

# 2. Aplica no banco de DESTINO (Supabase), da sua máquina
cd backend
$env:DATABASE_URL="<connection string do Supabase>"
$env:SEEDS_FILE="../database/exportado_catalogos.sql"
python -m app.scripts.seed_db
```

Gera um `.sql` com `ON CONFLICT DO NOTHING` (mesmo formato do
`seeds.sql`) - seguro rodar mais de uma vez sem duplicar nada.

## Limitações do plano gratuito, para não ser surpresa

- **Cold start**: o serviço "dorme" depois de 15 minutos sem tráfego;
  a próxima requisição demora de 30 a 60 segundos para responder
  enquanto ele acorda.
- **Banco Supabase gratuito**: fica pausado depois de alguns dias sem
  uso (você reativa manualmente pelo painel do Supabase quando
  precisar voltar a usar).
