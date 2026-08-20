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
> crie o backend como *Private Service*, pegue o endereço interno dele
> em *Connect → Internal* e use como `BACKEND_INTERNAL_URL` no
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

   | Variável | Valor |
   |---|---|
   | `DATABASE_URL` | A connection string do Supabase (passo 1) |
   | `JWT_SECRET_KEY` | Gere uma nova - **não reaproveite** a do `.env` local. Rode `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
   | `COOKIE_SECURE` | `true` (o Render serve tudo via HTTPS) |
   | `CORS_ORIGINS` | A URL pública do próprio serviço (ex.: `https://siamp.onrender.com`) - você só sabe isso depois do primeiro deploy; pode deixar em branco e voltar aqui para preencher depois |
   | `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` | Mesmos valores do provedor que você já validou (ver seção de e-mail do `README.md`) |
   | `REPORT_RECIPIENTS` | Opcional - prefira cadastrar pela tela Destinatários depois do primeiro login |
   | `SEED_ON_START` | `true` no primeiro deploy (carrega as 102 peças e as 6 máquinas de exemplo); pode deixar `true` sempre, é seguro repetir (usa `ON CONFLICT DO NOTHING`) |

5. Clica em **Create Web Service**. O primeiro build demora alguns
   minutos (instala dependências Python + nginx).

## 3. Primeiro acesso

O `entrypoint.sh` já roda `alembic upgrade head` (e o seed, se
`SEED_ON_START=true`) automaticamente toda vez que o container sobe -
não precisa de nenhum passo manual de migration.

O que falta é **criar o primeiro usuário administrador**, já que não
existe cadastro público. Como o plano gratuito não dá acesso a shell
dentro do container, rode o script direto da sua máquina, conectando
no mesmo banco Supabase:

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

## Limitações do plano gratuito, para não ser surpresa

- **Cold start**: o serviço "dorme" depois de 15 minutos sem tráfego;
  a próxima requisição demora de 30 a 60 segundos para responder
  enquanto ele acorda.
- **Banco Supabase gratuito**: fica pausado depois de alguns dias sem
  uso (você reativa manualmente pelo painel do Supabase quando
  precisar voltar a usar).
