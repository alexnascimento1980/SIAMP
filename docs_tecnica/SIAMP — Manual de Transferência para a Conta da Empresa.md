# SIAMP — Manual de Transferência para a Conta da Empresa

Nov 17, 2026 · @Alex Nascimento

## 1. Visão geral

Para o SIAMP passar a rodar inteiro nas contas da empresa, são quatro movimentos: mover o código (GitHub), mover o banco (Supabase), recriar o serviço (Render) e trocar os segredos e o e-mail. O sistema antigo continua no ar até o novo estar validado, então a virada não tem parada para os operadores.

| Peça | O que é hoje | Como vai para a empresa |
| --- | --- | --- |
| Código | Repositório no GitHub do dono atual | Transferir o repositório para a organização da empresa (seção 3) |
| Banco de dados | Projeto no Supabase (PostgreSQL) | Transferir o projeto para a organização da empresa, ou criar um novo e restaurar uma cópia (seção 4) |
| Aplicação | Um serviço web no Render (Docker, `deploy/Dockerfile`) | Criar um serviço novo na conta da empresa; não há cópia automática (seção 5) |
| E-mail dos relatórios | API do Brevo (`BREVO_API_KEY`) | Conta Brevo da empresa, com remetente validado (seção 6) |
| Segredos | `JWT_SECRET_KEY`, senha do banco, chave do Brevo | Gerar tudo novo na mudança (seção 7) |

Ordem recomendada:

1. Levantar o inventário e abrir as contas da empresa (seção 2).
2. Transferir o repositório (seção 3).
3. Mover o banco e anotar a nova `DATABASE_URL` (seção 4).
4. Criar o serviço no Render com as variáveis novas e fazer o primeiro deploy (seção 5).
5. Configurar o e-mail e, se quiser, um domínio próprio (seção 6).
6. Trocar segredos e conferir o administrador (seção 7).
7. Validar, avisar os usuários do endereço novo e desligar o antigo (seção 8).

As seções 3 a 8 dizem em cada passo quem faz: o dono atual (quem hoje administra as contas) ou a empresa (quem vai assumir).

## 2. Antes de começar

Antes de mexer em qualquer conta, a empresa precisa ter as quatro contas abertas e o dono atual precisa ter feito uma cópia de segurança do banco.

**Contas da empresa** (todas em nome de uma pessoa ou e-mail institucional que a empresa controle, não de um funcionário individual):

- **GitHub:** uma organização da empresa, com pelo menos um proprietário (owner) da empresa.
- **Supabase:** uma organização da empresa. Para transferir o projeto, o dono atual precisa ser membro dela; a [documentação do Supabase](https://supabase.com/docs/guides/platform/project-transfer) trata disso.
- **Render:** uma conta ou workspace da empresa, com o GitHub da empresa conectado.
- **Brevo:** uma conta da empresa, para o envio dos relatórios por e-mail.

**Inventário do que existe hoje** (feito pelo dono atual):

| Item | Onde encontrar | Para que serve na mudança |
| --- | --- | --- |
| URL pública do sistema | Painel do Render, serviço do SIAMP | Avisar os usuários e comparar antes e depois |
| Variáveis de ambiente | Render, aba Environment | Copiar os **nomes**; os valores sensíveis serão gerados de novo (seção 7) |
| `DATABASE_URL` | Supabase, Settings, Database, aba Session pooler | Conectar o serviço novo ao banco |
| Destinatários do relatório | Tela Destinatários do sistema | Conferir que vieram com o banco |
| Usuários e perfis | Tela Usuários do sistema | Conferir que vieram com o banco |
| Remetente validado | Painel do Brevo | Refazer a validação na conta da empresa |

**Ferramentas no computador de quem executa:** Git e as ferramentas de cliente do PostgreSQL (`pg_dump` e `psql`), em versão igual ou mais nova que a do banco.

**Cópia de segurança antes de tudo.** Com a `DATABASE_URL` do Session pooler do projeto atual:

```bash
pg_dump "<DATABASE_URL atual>" --no-owner --no-privileges --schema=public -f siamp_backup.sql
```

Guarde o `siamp_backup.sql` em local restrito: ele contém os dados de produção e os hashes das senhas dos usuários. Não envie por e-mail nem por chat, e apague as cópias soltas ao fim da mudança.

**Horário.** Escolha uma janela sem turno em fechamento. Turnos fechados sem sinal ficam na fila do aparelho e são enviados quando o sistema responde, mas é mais seguro não depender disso.

## 3. GitHub: o código

O jeito mais seguro é transferir o repositório atual para a organização da empresa: o histórico, os PRs e os workflows vêm juntos, e o endereço antigo passa a redirecionar. Quem faz: o dono atual, com a empresa a postos para aceitar.

**Opção A: transferir o repositório (recomendada)**

1. A empresa cria a organização no GitHub e adiciona o dono atual como membro, com permissão para criar repositórios.
2. O dono atual abre o repositório, vai em Settings, General, Danger Zone, Transfer ownership, informa a organização de destino e confirma o nome do repositório.
3. A empresa confere em Actions se os dois workflows (`tests.yml` e `e2e.yml`) aparecem e roda um deles com um commit pequeno.
4. Cada pessoa com clone local aponta para o endereço novo:

```bash
git remote set-url origin https://github.com/<organizacao>/<repositorio>.git
git fetch --prune
```

5. Depois da transferência, a empresa remove o dono atual da organização, se for o caso, e define quem pode fazer merge na `main`.

**Opção B: criar um repositório novo e copiar tudo.** Serve se a transferência não for possível. Perde-se o histórico de PRs e issues; o histórico de commits e as branches vêm junto.

```bash
git clone --mirror https://github.com/<dono-atual>/<repositorio>.git
cd <repositorio>.git
git push --mirror https://github.com/<organizacao>/<repositorio-novo>.git
```

**Confira depois:**

- O repositório não contém segredos (`.env` está no `.gitignore`; o modelo é o `.env.example`).
- Os workflows rodam sem segredos do GitHub: o `tests.yml` instala dependências e roda ruff e pytest, e o `e2e.yml` sobe o `docker compose`.
- O README tem um `git clone` com o endereço do dono atual (`github.com/alexnascimento1980/siamp`): troque pelo endereço da organização. O `DEPLOY.md` só cita `siamp.onrender.com` como exemplo.

## 4. Supabase: o banco de dados

Transferir o projeto existente para a organização da empresa é o caminho mais simples, porque o banco, os dados e a `DATABASE_URL` continuam os mesmos. Criar um projeto novo e restaurar uma cópia só vale se a transferência não for possível ou se a empresa quiser outra região.

**Opção A: transferir o projeto (recomendada)**

1. A empresa cria a organização no Supabase e convida o dono atual como membro.
2. O dono atual abre o projeto, vai em Settings, General, e inicia a transferência para a organização da empresa ([guia oficial](https://supabase.com/docs/guides/platform/project-transfer)). O uso até a transferência é cobrado na organização antiga; o uso depois, na nova.
3. A empresa confere em Table Editor que as tabelas e os dados estão lá (`usuarios`, `turnos`, `lancamentos_turno`).
4. A empresa copia a connection string da aba **Session pooler**.
5. A troca da senha do banco fica para a virada (seção 8), porque ela derruba o serviço antigo. A connection string é a `DATABASE_URL` da seção 5.

**Opção B: projeto novo e restauração**

1. A empresa cria o projeto na organização dela, de preferência na mesma região do serviço do Render, e anota a connection string da aba **Session pooler** (a conexão direta do Supabase é só IPv6, e o `DEPLOY.md` recomenda o pooler).
2. Com o backup da seção 2, restaure no banco **vazio**:

```bash
psql "<DATABASE_URL nova>" -f siamp_backup.sql
```

3. Conferir as contagens nos dois bancos (devem ser iguais):

```sql
SELECT 'usuarios' AS tabela, count(*) FROM usuarios
UNION ALL SELECT 'turnos', count(*) FROM turnos
UNION ALL SELECT 'lancamentos_turno', count(*) FROM lancamentos_turno
UNION ALL SELECT 'ordens_producao', count(*) FROM ordens_producao;
```

4. Anotar a `DATABASE_URL` nova para a seção 5.

**Cuidados da opção B**

- Restaure **antes** do primeiro deploy no Render. Se o serviço subir primeiro, o `alembic upgrade head` cria as tabelas vazias e a restauração falha com erros de "já existe".
- O backup carrega a tabela `alembic_version`, então no primeiro deploy as migrations já constam como aplicadas e o `alembic upgrade head` não recria nada.
- Turnos fechados no sistema antigo depois do backup não estão na cópia. Por isso, no dia da virada (seção 8) faça um backup novo e restaure de novo num banco vazio.
- Se o que importa são só os cadastros de máquinas e peças, e não o histórico de turnos, dá para começar com banco limpo e usar `exportar_catalogos` e `seed_db` (seção 5 do `DEPLOY.md`). Os usuários e as ordens de produção não vêm por esse caminho.

**Limites do plano gratuito que continuam valendo na conta da empresa:** o pooler em modo sessão aceita 15 clientes simultâneos (por isso `DB_POOL_SIZE` mais `DB_MAX_OVERFLOW` precisam ficar abaixo disso) e o projeto pausa depois de alguns dias sem uso.

## 5. Render: a aplicação

O serviço do Render não é copiado: a empresa cria um serviço novo na conta dela, ligado ao repositório e ao banco já movidos, e o antigo segue no ar até a virada. O passo a passo de fundo está no `DEPLOY.md`; aqui está o que muda numa mudança de conta.

1. No Render da empresa, conecte o GitHub e libere o acesso ao repositório na nova organização.
2. Crie **New, Web Service** com o repositório, e configure:
   - Runtime: Docker.
   - Dockerfile Path: `deploy/Dockerfile`.
   - Docker Build Context Directory: `.` (a raiz do repositório, porque o Dockerfile copia `backend/` e `frontend/`).
   - Instance Type: o plano que a empresa escolher.
3. Preencha as variáveis da tabela abaixo antes de criar o serviço.
4. Crie o serviço e espere o primeiro build. Nos logs, confirme que o `alembic upgrade head` terminou sem erro.
5. Anote a URL pública que o Render gerou, volte em Environment e preencha `CORS_ORIGINS` com ela. Salve para o serviço reiniciar.

| Variável | Valor no serviço novo |
| --- | --- |
| `DATABASE_URL` | Connection string do Session pooler (seção 4) |
| `JWT_SECRET_KEY` | Chave nova (seção 7); não reaproveite a antiga |
| `COOKIE_SECURE` | `true` |
| `CORS_ORIGINS` | URL pública do serviço novo |
| `BREVO_API_KEY` | Chave da API da conta Brevo da empresa (seção 6) |
| `SMTP_FROM` | Remetente validado na conta Brevo da empresa |
| `SEED_ON_START` | `true` só se o banco for novo e vazio; com o banco movido, o seed só repete inserções que já existem |
| `ADMIN_NOME`, `ADMIN_EMAIL` | O administrador da empresa (seção 7) |
| `ADMIN_SENHA` | Preencha para criar o administrador da empresa no primeiro deploy (a conta nasce protegida); a senha de uma conta que já existe nunca é sobrescrita. Com o campo em branco nada é criado |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | `2` e `2` enquanto o serviço antigo ainda usa o mesmo banco; depois da virada, `5` e `5` |
| `JWT_EXPIRES_MINUTES` | Opcional; 480 por padrão |

**Por que o pool fica menor durante a sobreposição.** O pooler do Supabase aceita 15 clientes. O serviço antigo usa até 10 (5 mais 5); se o novo também usasse 10, passaria do limite e daria `EMAXCONNSESSION`. Com `2` e `2` o total fica em 14.

**O que não muda.** O frontend e a API continuam num serviço só, com o nginx repassando `/api/`; o domínio `onrender.com` serve a mesma origem para páginas e API, e o cookie de sessão funciona sem configuração extra.

**O que muda para quem usa.** A URL é outra, então o app instalado no celular é outro app: cada pessoa instala de novo a partir do endereço novo, e turnos que ainda estejam na fila offline do app antigo precisam ser enviados antes de desinstalá-lo.

## 6. E-mail dos relatórios e domínio

O relatório de turno sai por e-mail pela API HTTP do Brevo, e a empresa precisa ter a conta e o remetente dela. O Render gratuito bloqueia as portas SMTP (25, 465 e 587), então o SMTP direto não funciona lá e a chave de API é o caminho que o sistema usa em produção.

**Brevo da empresa**

1. Crie a conta no Brevo e valide o e-mail ou domínio que será o remetente dos relatórios.
2. Em Settings, SMTP & API, API Keys, gere uma chave da **API** (não a chave SMTP).
3. No Render, preencha `BREVO_API_KEY` com essa chave e `SMTP_FROM` com o remetente validado. Quando `BREVO_API_KEY` está definida, ela tem prioridade sobre o SMTP.
4. Os destinatários ficam no banco (tela Destinatários) e vêm junto na migração do banco. Confira se a lista está certa para a empresa.

**Teste do e-mail.** No sistema novo, feche um turno de teste e use a ação de reenviar e-mail no Histórico (`POST /turnos/{id}/reenviar-email`, para ADMIN e SUPERVISOR). Depois marque o turno como teste, para ele não entrar no dashboard. Se o e-mail não chegar, veja nos logs do Render a resposta do Brevo e a pasta de spam; remetente não validado é a causa mais comum.

**Domínio próprio (opcional, recomendado).** O endereço `onrender.com` serve, mas um domínio da empresa evita trocar a URL (e reinstalar o app nos celulares) numa próxima mudança de hospedagem.

1. No serviço do Render, abra Settings, Custom Domains, e adicione o domínio. O Render mostra o registro DNS a criar; crie-o no provedor do domínio.
2. Quando o Render confirmar o domínio e o certificado HTTPS, atualize `CORS_ORIGINS` com a URL nova e salve.
3. Mantenha `COOKIE_SECURE=true`.
4. Avise os usuários do endereço definitivo antes de pedir para reinstalarem o app.

Como o frontend e a API continuam no mesmo serviço e na mesma origem, o domínio próprio não exige nenhuma outra mudança no código.

## 7. Segredos, administrador e usuários

Na mudança, todo segredo é gerado de novo e passa a existir só na conta da empresa; o que o dono atual conhecia deixa de valer. Nenhum segredo vai para o repositório, para e-mail ou para chat.

| Segredo | O que fazer | Efeito |
| --- | --- | --- |
| `JWT_SECRET_KEY` | Gerar uma chave nova para o serviço novo | Todos precisam entrar de novo |
| Senha do banco (Supabase) | Redefinir no dia da virada (seção 8) e atualizar a `DATABASE_URL` no serviço novo | O serviço antigo perde o acesso ao banco |
| `BREVO_API_KEY` | Usar a chave da conta da empresa; revogar a antiga na conta antiga | E-mails passam a sair pelo Brevo da empresa |
| `ADMIN_SENHA` | Definir uma senha forte, trocar pela tela Usuários no primeiro acesso e depois remover a variável, se preferir | A conta de bootstrap deixa de depender da variável |
| Acesso ao Render, Supabase e GitHub | Só contas da empresa, com autenticação em dois fatores | Ninguém de fora fica com acesso |

Para gerar a `JWT_SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

**Administrador da empresa.**

1. Defina `ADMIN_NOME`, `ADMIN_EMAIL` (e-mail da empresa) e `ADMIN_SENHA` no serviço novo. No deploy, o `entrypoint.sh` cria essa conta como ADMIN protegida.
2. Entre com ela e confira a tela Usuários: os usuários e perfis que vieram com o banco devem estar lá.
3. Crie, se for o caso, um segundo administrador da empresa, para não depender de uma pessoa só.
4. Troque a senha da conta pelo botão de senha na tela Usuários e use a senha nova a partir daí.

**Saída do dono atual.** A conta de administrador dele provavelmente está protegida, e conta protegida não pode ser desativada nem excluída. Com o administrador da empresa logado:

1. Na tela Usuários, clique no ícone do escudo da conta antiga para remover a proteção.
2. Desative a conta (ou exclua, se não precisar manter o rastro). Excluir um usuário não apaga turnos nem ordens: o campo de autoria só fica vazio.
3. Se o dono atual criou contas de teste ou compartilhou alguma senha, troque essas senhas pela tela Usuários ou exclua as contas.

**O que os usuários veem.** A troca de `JWT_SECRET_KEY` encerra as sessões abertas, então todos fazem login de novo na primeira vez. As senhas continuam as mesmas (estão no banco como hash bcrypt).

## 8. Validação e virada

A virada só acontece depois que o sistema novo passa em todas as verificações abaixo, com o antigo ainda no ar como plano de volta.

**Validação no sistema novo** (use turnos de teste e marque-os como teste no Histórico ao final):

- [ ] Nos logs do Render, o container subiu e o `alembic upgrade head` terminou sem erro.
- [ ] Os logs não mostram `EMAXCONNSESSION` depois de abrir Dashboard e Ordens de Produção.
- [ ] O login do administrador da empresa funciona e a tela Usuários lista as contas esperadas.
- [ ] Máquinas, peças e ordens de produção aparecem como no sistema antigo.
- [ ] Um turno de teste é lançado e fechado, e aparece no Histórico uma única vez.
- [ ] O PDF do turno abre e a exportação CSV funciona.
- [ ] O e-mail do relatório chega aos destinatários (reenvio pelo Histórico).
- [ ] O Dashboard carrega os gráficos.
- [ ] No Chrome, F12, Application: o Manifest não tem erros e o `sw.js` está ativo.
- [ ] No Android, o app instala pelo endereço novo e abre pelo ícone.
- [ ] A fila offline funciona: com o Apontamento aberto, ative o modo avião, feche um turno de teste, desative o modo avião e confirme que o turno chega uma vez.

**Virada**

1. Combine a data e a hora e avise os usuários: o endereço novo, que será preciso entrar de novo e que o app precisa ser instalado de novo.
2. Peça que todos fechem os turnos abertos e enviem o que estiver na fila offline do app antigo. A partir daí, ninguém lança no sistema antigo.
3. Se o banco foi movido pela opção B, faça um backup novo do banco antigo, restaure num banco vazio (um projeto novo do Supabase) e atualize a `DATABASE_URL` do serviço novo. Na opção A, não há nada a copiar: o banco é o mesmo.
4. Na opção A, redefina a senha do banco no Supabase e atualize a `DATABASE_URL` no serviço novo. A partir desse momento o serviço antigo não acessa mais o banco; confirme que ele falha e que o novo segue funcionando.
5. No serviço novo, volte `DB_POOL_SIZE` e `DB_MAX_OVERFLOW` para `5` e `5`.
6. Repita rápido o teste de login, de fechamento de turno e do e-mail.
7. Avise os usuários de que o sistema novo já está liberado.

**Depois da virada**

1. No Render antigo, suspenda o serviço (Suspend) e mantenha suspenso por alguns dias, como plano de volta. Se tudo correr bem, exclua.
2. Revogue a chave antiga do Brevo e apague os backups `.sql` soltos nos computadores.
3. No GitHub, confira que só contas da empresa têm acesso ao repositório e remova a integração do Render antigo.
4. Atualize o endereço do sistema onde ele estiver anotado (README, atalhos, manuais internos).

## 9. Problemas comuns e plano de volta

A maioria dos problemas de uma mudança de conta vem de variável de ambiente errada, de conexão com o banco ou de acesso do Render ao repositório; a tabela resume o que olhar primeiro.

| Sintoma | Causa provável | O que fazer |
| --- | --- | --- |
| Build falha no Render | Dockerfile ou contexto errados | Dockerfile Path `deploy/Dockerfile` e Docker Build Context Directory `.` |
| Render não enxerga o repositório | Integração do GitHub sem acesso à organização nova | Reconectar o GitHub no Render e liberar o repositório |
| Erro 500 com `EMAXCONNSESSION` nos logs | Soma dos pools dos serviços passa de 15 conexões | Reduzir `DB_POOL_SIZE` e `DB_MAX_OVERFLOW` do serviço novo durante a sobreposição |
| Não conecta ao banco | Connection string direta (só IPv6) | Usar a connection string da aba Session pooler |
| `alembic upgrade head` falha com "já existe" | Serviço subiu antes da restauração do backup | Restaurar o backup de novo num banco vazio e subir o serviço depois |
| Login funciona mas as telas dão 401 | `COOKIE_SECURE` ou origem incorretos, ou `JWT_SECRET_KEY` trocada com sessão antiga aberta | Conferir `COOKIE_SECURE=true`, abrir a URL pelo endereço público em HTTPS e entrar de novo |
| E-mail não chega | Chave do Brevo ou remetente não validado | Conferir `BREVO_API_KEY`, `SMTP_FROM` e a validação do remetente no Brevo; ver spam |
| Primeira página demora 30 a 60 segundos | Plano gratuito do Render dorme após 15 minutos sem tráfego | Esperar o serviço acordar ou usar um plano pago |
| Banco não responde depois de dias parado | Projeto gratuito do Supabase pausado | Reativar pelo painel do Supabase |
| App instalado parece preso numa versão antiga | Cache do service worker | Aumentar `VERSAO` em `frontend/sw.js` e fazer novo deploy |

**Plano de volta.** Enquanto o serviço antigo estiver suspenso e não excluído, dá para voltar:

1. No Render antigo, retome o serviço (Resume).
2. Na opção A do banco, atualize a `DATABASE_URL` do serviço antigo com a senha nova do Supabase. Na opção B, o banco antigo continua com os dados até a virada.
3. Turnos lançados no sistema novo depois da virada não estão no banco antigo, quando o banco é separado (opção B). Faça um backup do banco novo antes de desligar o sistema novo e combine com a empresa como esses turnos serão tratados.
4. Avise os usuários de que o endereço antigo voltou a valer.

Para dúvidas do dia a dia depois da mudança, a referência é a Documentação Técnica do SIAMP (seções 8 e 9, segurança e operação) e o `DEPLOY.md` do repositório.
