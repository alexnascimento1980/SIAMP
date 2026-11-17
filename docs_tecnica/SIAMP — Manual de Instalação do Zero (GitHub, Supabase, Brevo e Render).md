# SIAMP — Manual de Instalação do Zero (GitHub, Supabase, Brevo e Render)

Nov 17, 2026 · @Alex Nascimento

## 1. Visão geral

Instalar o SIAMP do zero é criar quatro serviços na ordem certa: o código no GitHub, o banco no Supabase, o e-mail no Brevo e a aplicação no Render. No fim há um único endereço público, em HTTPS, que serve as páginas e a API, e que os operadores também instalam como aplicativo no celular.

| Serviço | Para que serve | O que você cria |
| --- | --- | --- |
| GitHub | Guarda o código e dispara o deploy | Um repositório com o código do SIAMP, na conta ou organização da empresa |
| Supabase | Banco de dados PostgreSQL | Um projeto e a connection string do Session pooler |
| Brevo | Envio do relatório de turno por e-mail | Uma conta, um remetente validado e uma chave de API |
| Render | Executa o sistema (nginx e API num só container) | Um Web Service com Docker e as variáveis de ambiente |

Ordem dos passos (cada um está numa seção deste manual):

1. Abrir as contas e instalar as ferramentas (seção 2).
2. Colocar o código no GitHub da empresa (seção 3).
3. Criar o banco no Supabase (seção 4).
4. Criar a conta e o remetente no Brevo (seção 5).
5. Criar o serviço no Render com as variáveis e fazer o primeiro deploy (seção 6).
6. Entrar pela primeira vez e cadastrar máquinas, peças e destinatários (seção 7).
7. Validar e instalar o app nos celulares (seção 8).

O banco começa vazio: ao subir, o sistema cria as tabelas sozinho (migrations Alembic) e, se `SEED_ON_START=true`, carrega as peças e máquinas de exemplo. Os dados de produção de outra instalação não vêm junto; para isso existe o manual de transferência.

## 2. Antes de começar

Você precisa de quatro contas e de duas ferramentas no computador; nada mais é instalado na sua máquina, porque o sistema roda inteiro na nuvem.

**Contas** (use um e-mail institucional que a empresa controle, e ative a autenticação em dois fatores em todas):

- **GitHub** ([github.com](https://github.com)): de preferência uma organização da empresa, para o código não ficar preso a uma pessoa.
- **Supabase** ([supabase.com](https://supabase.com)): uma organização da empresa.
- **Brevo** ([brevo.com](https://www.brevo.com)): para o envio dos relatórios.
- **Render** ([render.com](https://render.com)): um workspace da empresa, entrando com o GitHub.

**No computador:**

- Um navegador atual (Chrome recomendado, por causa do teste do app).
- Git, para baixar e enviar o código (seção 3).

**Para gerar a chave de segurança** (seção 6) você precisa de Python 3 instalado, ou de qualquer gerador de senha que crie 64 caracteres aleatórios.

**O que anotar durante a instalação.** Abra um documento seguro (um gerenciador de senhas da empresa) e vá guardando: a connection string do Supabase com a senha do banco, a chave de API do Brevo, a `JWT_SECRET_KEY`, o e-mail e a senha do administrador e a URL final do sistema. Esses valores não vão para o GitHub, para e-mail nem para chat.

**Limites dos planos gratuitos**, para ninguém ser pego de surpresa:

- O Render gratuito coloca o serviço para dormir após 15 minutos sem tráfego; a primeira abertura depois disso demora de 30 a 60 segundos.
- O Supabase gratuito pausa o projeto depois de alguns dias sem uso; é preciso reativar no painel.
- O Render gratuito bloqueia as portas SMTP (25, 465 e 587); por isso o e-mail sai pela API do Brevo, não por SMTP.
- O Supabase gratuito, no modo de sessão do pooler, aceita 15 conexões simultâneas; os valores padrão do SIAMP (5 mais 5) respeitam esse limite.

## 3. GitHub: o código

O Render publica o sistema a partir de um repositório do GitHub, então o primeiro passo é ter uma cópia do código do SIAMP na conta da empresa. O código de origem está em `github.com/alexnascimento1980/siamp`; a empresa precisa de acesso de leitura a ele (ou receber o código por transferência, que é o caso do outro manual).

**Opção A: cópia independente (recomendada)**

1. No GitHub da empresa, crie um repositório **vazio** (sem README, sem .gitignore, sem licença), por exemplo `siamp`. Pode ser privado.
2. No computador, baixe o código e envie para o repositório novo:

```bash
git clone https://github.com/alexnascimento1980/siamp.git
cd siamp
git remote set-url origin https://github.com/<organizacao>/siamp.git
git push -u origin main
```

3. Atualize o endereço do `git clone` no `README.md` para o repositório da empresa.

**Opção B: fork.** Em `github.com/alexnascimento1980/siamp`, use Fork e escolha a organização da empresa. O fork mantém a ligação com o original, o que facilita receber melhorias, mas o repositório fica vinculado a ele no GitHub.

**Receber atualizações depois (opção A).** Se a empresa quiser trazer correções do repositório original:

```bash
git remote add upstream https://github.com/alexnascimento1980/siamp.git
git fetch upstream
git merge upstream/main
```

**Confira depois de enviar:**

- A branch `main` aparece com as pastas `backend`, `frontend`, `deploy`, `database`, `e2e` e os arquivos `DEPLOY.md` e `.env.example`.
- Na aba Actions, os workflows `tests.yml` e `e2e.yml` aparecem; eles rodam sem segredos do GitHub.
- Não há nenhum arquivo `.env` no repositório. Ele está no `.gitignore`; os valores reais entram só como variáveis de ambiente no Render.

## 4. Supabase: o banco de dados

O banco é um projeto vazio do Supabase; você não cria tabelas à mão, porque o SIAMP as cria sozinho no primeiro deploy. O que você precisa levar desta etapa é a connection string do **Session pooler**, que será a variável `DATABASE_URL`.

1. Entre no Supabase, crie a organização da empresa (se ainda não existir) e clique em New project.
2. Preencha o nome (por exemplo `siamp`) e escolha a região mais próxima de onde ficará o serviço do Render.
3. Defina a **senha do banco**. Use uma senha forte e, para evitar problemas na connection string, prefira letras e números; se usar símbolos como `@`, `/` ou `#`, eles precisam ser codificados na URL. Guarde a senha no gerenciador de senhas.
4. Espere o projeto terminar de criar.
5. No painel do projeto, abra Settings, Database, Connection string, e escolha a aba **Session pooler**. Ela funciona por IPv4, que o Render exige; a conexão direta do Supabase é só IPv6 e pode não funcionar a partir do Render.
6. Copie a string, que tem este formato, e troque o marcador da senha pela senha que você definiu:

```text
postgresql://postgres.xxxx:SENHA@aws-x-regiao.pooler.supabase.com:5432/postgres
```

7. Guarde a string completa. Não acrescente `+psycopg2`: o SQLAlchemy já usa o psycopg2 para URLs `postgresql://`.

**Confira:** o projeto aparece como ativo no painel e o Table Editor está vazio. Isso é o esperado; as tabelas aparecem depois do primeiro deploy (seção 6).

**Atenção:** use a aba Session pooler (porta 5432 do pooler), não a conexão direta. O limite de 15 clientes simultâneos do plano gratuito vale para esse modo; os valores padrão `DB_POOL_SIZE=5` e `DB_MAX_OVERFLOW=5` ficam abaixo dele.

## 5. Brevo: o e-mail dos relatórios

Quando um turno fecha, o SIAMP envia o relatório em PDF por e-mail aos destinatários cadastrados, usando a API HTTP do Brevo. Desta etapa você leva duas coisas: um remetente validado (`SMTP_FROM`) e uma chave de API (`BREVO_API_KEY`).

1. Crie a conta em [brevo.com](https://www.brevo.com) com o e-mail da empresa.
2. Valide o remetente: o e-mail (por exemplo `relatorios@suaempresa.com.br`) ou, melhor, o domínio inteiro, seguindo as instruções do painel do Brevo. Sem remetente validado, o Brevo não entrega os e-mails.
3. Em Settings, SMTP & API, API Keys, gere uma chave nova. Use a chave da **API**, não a chave SMTP.
4. Copie a chave assim que ela aparecer e guarde no gerenciador de senhas.
5. Anote o e-mail do remetente validado: é o valor de `SMTP_FROM`.

**Por que API e não SMTP.** O Render gratuito bloqueia as portas SMTP de saída, então o envio por SMTP (Gmail, por exemplo) não funcionaria lá. A chave de API usa HTTPS (porta 443), que não é afetada. Quando `BREVO_API_KEY` está definida, ela tem prioridade sobre qualquer configuração SMTP.

**Quem recebe.** Os destinatários são cadastrados na tela Destinatários do sistema, depois do primeiro login (seção 7). A variável `REPORT_RECIPIENTS` é opcional.

**Limites.** O plano gratuito do Brevo tem limite diário de envios; confira o valor atual no painel e compare com a quantidade de turnos fechados por dia vezes o número de destinatários.

## 6. Render: a aplicação

No Render você cria um único Web Service que roda o nginx e a API juntos (é o `deploy/Dockerfile`). Um serviço só é intencional: assim as páginas e a API ficam na mesma origem e o cookie de sessão funciona. Ao subir, o container espera o banco, aplica as migrations, cria o administrador (se `ADMIN_SENHA` estiver definida) e carrega os dados de exemplo (se `SEED_ON_START=true`).

**Gerar a chave de segurança** (`JWT_SECRET_KEY`) no seu computador:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

**Criar o serviço**

1. Entre em [dashboard.render.com](https://dashboard.render.com) com o GitHub da empresa.
2. Clique em New, Web Service, e conecte o repositório `siamp` da empresa (o Render pede para autorizar o acesso a ele no GitHub).
3. Configure:
   - Branch: `main`.
   - Runtime: Docker.
   - Dockerfile Path: `deploy/Dockerfile`.
   - Docker Build Context Directory: `.` (a raiz do repositório, porque o Dockerfile copia `backend/` e `frontend/`).
   - Instance Type: Free, ou o plano que a empresa preferir.
4. Em Environment, preencha as variáveis da tabela abaixo.
5. Clique em Create Web Service e espere o primeiro build, que leva alguns minutos.
6. Nos logs, confirme as mensagens do `entrypoint`: banco disponível, migrations aplicadas e aplicação iniciada.
7. Anote a URL pública do serviço (algo como `https://siamp.onrender.com`), volte em Environment, preencha `CORS_ORIGINS` com ela e salve; o serviço reinicia.

| Variável | Valor | Obrigatória |
| --- | --- | --- |
| `DATABASE_URL` | Connection string do Session pooler (seção 4) | Sim |
| `JWT_SECRET_KEY` | A chave gerada acima; sem ela a API não sobe | Sim |
| `COOKIE_SECURE` | `true` | Sim |
| `CORS_ORIGINS` | URL pública do serviço (depois do primeiro deploy) | Sim |
| `BREVO_API_KEY` | Chave da API do Brevo (seção 5) | Para e-mail |
| `SMTP_FROM` | Remetente validado no Brevo | Para e-mail |
| `REPORT_RECIPIENTS` | E-mails reais dos destinatários, separados por vírgula (veja o aviso abaixo) | Recomendada |
| `ADMIN_NOME` | Nome do primeiro administrador | Para criar o admin |
| `ADMIN_EMAIL` | E-mail de login do primeiro administrador | Para criar o admin |
| `ADMIN_SENHA` | Senha forte do primeiro administrador; use 10 caracteres ou mais, o mínimo que a tela Usuários exige | Para criar o admin |
| `SEED_ON_START` | `true` no primeiro deploy (carrega as peças e máquinas de exemplo; repetir é seguro) | Opcional |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | Padrão `5` e `5`; a soma precisa ficar abaixo de 15 | Opcional |
| `JWT_EXPIRES_MINUTES` | Duração do login em minutos; padrão `480` | Opcional |

**Aviso sobre `REPORT_RECIPIENTS`.** Se nenhum destinatário estiver cadastrado na tela Destinatários, o sistema usa esta variável; e o valor padrão dela são endereços de exemplo (`gerente.producao@empresa.com` e `supervisao@empresa.com`). Defina-a com os e-mails reais ou cadastre os destinatários antes do primeiro turno fechado, para não enviar relatórios a endereços que não são da empresa.

**Sem acesso ao terminal.** O plano gratuito do Render não dá acesso a shell no container; por isso o administrador é criado por variáveis de ambiente, sem nenhum comando manual. A conta nasce protegida contra exclusão e desativação acidental, e a senha dela nunca é sobrescrita depois da primeira criação.

## 7. Primeiro acesso e cadastros

Com o serviço no ar, entre pela URL pública com o e-mail e a senha do administrador e deixe o sistema pronto para os operadores: não há cadastro público, então tudo parte desta conta.

1. Abra a URL do Render e entre com `ADMIN_EMAIL` e `ADMIN_SENHA`. Na primeira abertura depois de um tempo parado, espere de 30 a 60 segundos.
2. Na tela **Usuários**, troque a senha do administrador por uma que só a pessoa responsável conhece e, se quiser, remova a variável `ADMIN_SENHA` do Render depois disso.
3. Crie um segundo administrador da empresa, para não depender de uma pessoa só.
4. Cadastre as demais pessoas, cada uma com o perfil certo (tabela abaixo). A senha precisa ter pelo menos 10 caracteres.
5. Na tela **Máquinas**, ajuste as máquinas: o número, o ciclo padrão e as cavidades.
6. Na tela **Peças**, ajuste as peças: código, descrição, ciclo, cavidades e peso em gramas (o peso é usado para calcular o refugo).
7. Na tela **Ordens de Produção**, cadastre ou importe as ordens em andamento.
8. Na tela **Destinatários**, cadastre os e-mails que devem receber o relatório de cada turno fechado.

| Perfil | Pode |
| --- | --- |
| OPERADOR | Lançar e fechar turnos, registrar paradas, consultar histórico e dashboard |
| SUPERVISOR | Tudo do operador, mais corrigir turnos, reenviar o relatório por e-mail, marcar turnos como teste e editar máquinas |
| ADMIN | Tudo do supervisor, mais usuários, peças, ordens de produção, destinatários e exclusão de turnos |

**Dados de exemplo.** Com `SEED_ON_START=true`, o primeiro deploy carrega 102 peças e 6 máquinas genéricas. Elas servem para testar; antes de operar, edite ou desative o que não for da empresa, para o operador não escolher uma máquina que não existe. Depois disso, `SEED_ON_START` pode ficar `true` ou ser removida: repetir o seed não duplica nada.

**Levar cadastros de outro ambiente.** Se a empresa já tem máquinas e peças num ambiente local, dá para exportá-las e aplicá-las no Supabase em vez de digitar tudo; o procedimento está na seção 5 do `DEPLOY.md`.

## 8. Validação e instalação do app

A instalação está pronta quando um turno de teste é lançado, fechado, enviado por e-mail e visto no histórico, e quando o app instala e fecha turno sem sinal. Marque cada item.

**Servidor**

- [ ] Nos logs do Render, o container subiu e o `alembic upgrade head` terminou sem erro.
- [ ] No Supabase, o Table Editor agora mostra as tabelas (`usuarios`, `turnos`, `lancamentos_turno` e as demais).
- [ ] Depois de abrir o Dashboard e as Ordens de Produção, os logs não mostram `EMAXCONNSESSION`.

**Sistema**

- [ ] O login do administrador funciona e a tela Usuários lista as contas criadas.
- [ ] Um turno de teste é lançado pelo Apontamento e fechado.
- [ ] O turno aparece no Histórico uma única vez, com o PDF abrindo e a exportação CSV funcionando.
- [ ] O e-mail do relatório chega aos destinatários (se não chegou, use o reenvio no Histórico depois de corrigir a configuração).
- [ ] O Dashboard carrega os gráficos.
- [ ] Os turnos de teste foram marcados como teste no Histórico, para não entrarem nas estatísticas.

**App no celular (PWA)**

- [ ] No Chrome do computador, F12, Application: o Manifest aparece sem erros, com o nome SIAMP e 3 ícones, e o Service Workers mostra o `sw.js` ativo.
- [ ] No Android (Chrome), abrir o endereço, entrar, tocar em Instalar e abrir pelo ícone na tela inicial.
- [ ] Fila offline: com o Apontamento já aberto uma vez com internet, ative o modo avião, finalize um turno de teste e confira o aviso de turno aguardando envio. Desative o modo avião, espere alguns segundos e confirme que o turno aparece uma única vez no Histórico.

**Como instalar em cada aparelho**

- **Android (Chrome):** abra a URL do sistema e use Instalar app (ou o aviso de instalação que o sistema mostra).
- **iPhone e iPad (Safari):** não há aviso de instalação; toque em Compartilhar e depois em Adicionar à Tela de Início.
- **Computador:** o Chrome oferece instalar o app pelo ícone na barra de endereços.

**O que funciona sem sinal.** Só o fechamento de turno: ele entra numa fila no aparelho e é enviado quando a rede volta, com o app aberto. Cadastros, correções e consultas exigem rede. Se um item da fila for recusado pelo servidor, o app avisa e permite baixar os dados ou descartar o item.

## 9. Operação: atualizações, backup e domínio

Depois de instalado, o dia a dia se resume a três rotinas: publicar mudanças pelo GitHub, copiar o banco de tempos em tempos e, se a empresa quiser, usar um domínio próprio.

**Atualizar o sistema.** Todo `git push` na branch `main` dispara um novo deploy no Render (o auto-deploy vem ligado). O fluxo recomendado é criar uma branch, abrir um Pull Request, esperar os testes do GitHub Actions ficarem verdes e fazer o merge. As migrations do banco rodam sozinhas no deploy (`alembic upgrade head`). Depois de qualquer deploy que mexa em backend, nginx ou app, repita a seção 8, ao menos os itens do servidor e um turno de teste.

**App instalado preso numa versão antiga.** Aumente `VERSAO` em `frontend/sw.js` e faça novo deploy; os aparelhos renovam o cache sozinhos.

**Backup do banco.** Faça uma cópia periódica, em computador com as ferramentas de cliente do PostgreSQL, usando a connection string do Session pooler:

```bash
pg_dump "<DATABASE_URL>" --no-owner --no-privileges --schema=public -f siamp_backup.sql
```

Guarde o arquivo em local restrito: ele contém os dados de produção e os hashes das senhas. Confira no painel do Supabase quais backups o plano da empresa inclui; não conte com isso sem verificar.

**Segredos.** Para trocar a `JWT_SECRET_KEY`, altere a variável no Render; todos precisam entrar de novo. Para trocar a senha do banco, redefina no Supabase e atualize a `DATABASE_URL` no Render na sequência, pois o sistema fica sem acesso ao banco entre os dois passos.

**Domínio próprio (opcional).** O endereço `onrender.com` funciona, mas um domínio da empresa não muda numa próxima hospedagem, e a troca de endereço obriga todos a reinstalar o app.

1. No serviço do Render, abra Settings, Custom Domains, e adicione o domínio.
2. Crie no provedor do domínio o registro DNS que o Render mostrar.
3. Quando o Render confirmar o domínio e o certificado HTTPS, atualize `CORS_ORIGINS` com o endereço novo.
4. Mantenha `COOKIE_SECURE=true` e peça aos usuários para instalar o app de novo pelo endereço definitivo.

**Banco pausado.** No plano gratuito, o Supabase pausa o projeto após alguns dias sem uso; reative pelo painel do Supabase e reinicie o serviço no Render se ele não reconectar sozinho.

## 10. Problemas comuns

Quase todo problema de instalação vem de uma variável de ambiente errada, da connection string do banco ou do acesso do Render ao repositório; comece pelos logs do serviço no Render.

| Sintoma | Causa provável | O que fazer |
| --- | --- | --- |
| O serviço não sobe e o log fala em `JWT_SECRET_KEY` | Variável ausente | Definir `JWT_SECRET_KEY` no Render com a chave gerada na seção 6 |
| Build falha | Dockerfile ou contexto errados | Dockerfile Path `deploy/Dockerfile` e Docker Build Context Directory `.` |
| O Render não lista o repositório | Acesso do Render ao GitHub não liberado | Reconectar o GitHub no Render e liberar o repositório |
| O log repete "banco indisponível" | `DATABASE_URL` errada, senha com símbolo sem codificação ou projeto pausado | Conferir a string e a senha, usar a aba Session pooler e ver se o projeto está ativo |
| Não conecta ao banco a partir do Render | Connection string direta (só IPv6) | Trocar pela connection string da aba Session pooler |
| Erro 500 com `EMAXCONNSESSION` | Conexões do pooler esgotadas | Manter `DB_POOL_SIZE` mais `DB_MAX_OVERFLOW` abaixo de 15 |
| Não consigo entrar | Administrador não criado | Conferir se `ADMIN_EMAIL` e `ADMIN_SENHA` estavam definidos no deploy e olhar o log do `entrypoint` |
| Login parece funcionar, mas as telas dão 401 | `COOKIE_SECURE` incorreto ou acesso por HTTP | Usar `COOKIE_SECURE=true` e abrir o sistema pelo endereço HTTPS do Render |
| E-mail não chega | Chave do Brevo, remetente não validado ou destinatários vazios | Conferir `BREVO_API_KEY`, `SMTP_FROM`, a validação no Brevo, a tela Destinatários e a pasta de spam |
| Relatório indo para `empresa.com` de exemplo | `REPORT_RECIPIENTS` com o valor padrão e nenhum destinatário cadastrado | Cadastrar os destinatários reais (seção 7) ou definir `REPORT_RECIPIENTS` |
| A primeira página demora 30 a 60 segundos | O plano gratuito do Render dorme após 15 minutos sem tráfego | Esperar o serviço acordar ou usar um plano pago |
| O app instalado parece preso numa versão antiga | Cache do service worker | Aumentar `VERSAO` em `frontend/sw.js` e fazer novo deploy |

Se nada disso resolver, junte o trecho do log do Render com a mensagem de erro e a seção em que você parou, para quem for ajudar achar a causa mais rápido. Para entender o que cada parte do sistema faz, consulte a Documentação Técnica do SIAMP e o `DEPLOY.md` do repositório.
