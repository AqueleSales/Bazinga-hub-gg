# Bazinga Hub

Clone do Discord em Flask + Socket.IO, com um diferencial: um mapa (Leaflet)
onde os usuários "plantam" servidores e deixam notas geolocalizadas.

## Stack

- **Backend**: Flask, Flask-SQLAlchemy, Flask-SocketIO (eventlet), Authlib (login Google OAuth)
- **Banco**: Neon (Postgres serverless) em produção. `config.py` usa `NullPool` —
  **toda query abre uma conexão nova**. Isso causa falhas intermitentes de
  "cold start" (Neon "acordando"). Veja `com_retry()` abaixo.
- **Frontend**: um único arquivo `app/templates/chat.html` (~3400 linhas) com
  CSS e JS inline — sem build step, sem framework. PeerJS para chamadas de
  voz/vídeo (WebRTC), Leaflet para o mapa.
- **Deploy**: Render (Procfile: `gunicorn run:app`). Free tier — pode dormir.

## Arquivos principais

| Arquivo | O quê |
|---|---|
| `app/models.py` | Todos os modelos SQLAlchemy |
| `app/utils.py` | `com_retry()`, `comitar_com_retry()` e as checagens de permissão de canal |
| `app/events.py` | Todos os handlers de Socket.IO (`@socketio.on(...)`) |
| `app/main/routes.py` | Rotas REST (`/chat`, `/api/...`) |
| `app/auth/routes.py` | Login Google OAuth, tem o `com_retry()` original |
| `app/templates/chat.html` | Frontend inteiro (HTML+CSS+JS) |
| `atualizar_banco.py` | Migração manual (ver seção abaixo — **rodar sempre que mexer em `models.py`**) |
| `seed.py` / `seed_loja.py` | Popula canais/cargos/produtos padrão |

## ⚠️ Regra de ouro: sem Flask-Migrate/Alembic

Este projeto **não usa Alembic**. `db.create_all()` (chamado no boot da app)
só cria tabelas que não existem — **nunca adiciona colunas em tabelas já
existentes**. Toda vez que uma coluna nova for adicionada a `models.py`,
ela também precisa de um `ALTER TABLE` em `atualizar_banco.py`
(`add_column_se_nao_existir(...)`), senão a coluna existe no modelo Python
mas não no banco real — e a query falha em produção (Postgres) mesmo que
funcione em teste local com SQLite (que costuma ser mais tolerante).

**Isso já causou um bug real**: `geo_note.duration_hours`/`expires_at` e
colunas de `map_server` existiam no modelo havia tempo mas nunca tinham
sido migradas no Neon de produção — toda criação de nota/servidor no mapa
falhava silenciosamente (toast dizia "sucesso", nada era salvo) até isso
ser descoberto e corrigido.

Depois de qualquer mudança em `models.py`:
```bash
python atualizar_banco.py
```

## `com_retry()` / `comitar_com_retry()` — em `app/utils.py`

Os dois vivem em `app/utils.py` (antes cada um dos três arquivos tinha a sua
cópia). `com_retry(fn)` reexecuta uma query se ela lançar `OperationalError`
(cold start do Neon). Com `NullPool` qualquer operação pode sofrer cold start,
não só a primeira, então **todo handler que toca o banco deve usar**.

Para **escritas**, use `comitar_com_retry(preparar)`: a função `preparar`
monta as alterações e o helper comita. Nunca faça
`com_retry(db.session.commit)` — se o commit falha, o `rollback()` do retry
descarta as alterações e a tentativa seguinte comita uma sessão vazia.

## Erros de banco não podem falhar em silêncio

Vários handlers antigos capturavam só `(OperationalError, PendingRollbackError)`
e voltavam vazio sem avisar ninguém — na prática, qualquer outro tipo de erro
(ex: `ProgrammingError` do Postgres para coluna inexistente) passava batido,
sem log e sem toast. Padrão atual nos handlers de socket:

```python
except Exception as e:
    db.session.rollback()
    print(f"[ERRO ALGO] {e}")
    emit('erro_bazinga', {'msg': f'Não foi possível fazer X: {e}'})
```

O frontend escuta `socket.on('erro_bazinga', ...)` e mostra um toast vermelho
com a mensagem real. **Mantenha esse padrão** em qualquer handler novo —
incluir `{e}` na mensagem pro usuário (não só no log) foi o que permitiu
diagnosticar o bug do parágrafo acima sem acesso ao terminal do usuário.

## Permissões — todo handler novo precisa checar

Canal não é público: `app/utils.py` tem `canal_permitido(usuario, canal_id)`
(devolve o `Channel` só se o usuário for membro do Servidor dono dele) e
`pode_ver_canal(usuario, canal)`. Use nos handlers de socket e nas rotas REST
que recebem um `canal_id` do cliente — `entrar_canal`, `enviar_mensagem`,
`entrar_call` e `/api/mensagens/<id>` já usam.

Apagar/editar qualquer coisa exige conferir o dono (`author_id`, `owner_id`,
`person_id`) contra o usuário da sessão. Nunca confie em um id que veio do
cliente.

## XSS — nunca jogue dado de usuário cru em `innerHTML`

`chat.html` tem três helpers, definidos logo antes de `showToast()`:

- `esc(valor)` — texto (mensagem, nome, nota do mapa, descrição de produto)
- `escUrl(url)` — para `src=""`/`href=""`; só deixa passar `http(s)` e
  caminhos do próprio site, barrando `javascript:` e `data:`
- `escJs(valor)` — para valores que entram dentro de um `onclick="..."`

**Isso já causou um bug real**: `appendMessageGrouped()` interpolava
`texto`/`autor`/`avatar` direto no `innerHTML`, então uma mensagem
`<img src=x onerror=...>` executava script no navegador de todo mundo que
abrisse o canal. O mesmo valia para nota do mapa, nome de servidor, nome de
participante de call e produtos do bazar.

## Arquitetura do frontend (`chat.html`)

- Não existe mais um servidor "padrão" fixo (era o antigo "Bazinga Hub" de
  teste, removido a pedido). Os únicos servidores são os que o usuário cria
  pela sidebar (`+`), guardados em `meUserServers` (JS) e sincronizados via
  `socket.on('carregar_meus_servidores'/'servidor_discord_criado')`.
- Os canais globais (`server_id=NULL` no modelo `Channel`) ainda existem no
  backend por compatibilidade, mas não há mais nenhum botão que leve até
  eles na UI — são efetivamente mortos. Se um dia quiser reaproveitar, é só
  adicionar de volta um ícone estático na sidebar chamando `switchMainView('server')`
  com `bazinga-sidebar` visível.
- Toasts: `showToast(msg, tipo)` onde tipo é `info/success/warning/error`.
  Padrão para ações que envolvem o banco: mostrar toast `info` otimista
  ("Salvando...") no emit, e só mostrar `success` quando o evento de
  confirmação realmente voltar do servidor (não assumir sucesso no emit).
- Modais genéricos: `openConfirmModal(titulo, desc, callback)` e
  `openInputModal(titulo, desc, placeholder, callback)` substituem
  `confirm()`/`prompt()` nativos — use-os em vez de criar modal novo pra
  perguntas simples.
- Upload de imagem: `/api/upload` (multipart, campo `file`) salva em
  `app/static/uploads/` e devolve `{url}`. Usado por avatar (com recorte
  antes, ver `abrirCropModal`/`finalizarUploadAvatar`) e ícone de servidor.
  **Nunca mande uma URL `blob:` pro backend** — ela só existe na aba que
  criou, não sobrevive a reload nem funciona pra outros usuários.

## Testando localmente sem tocar no banco de produção

Não existe suite de testes automatizada. O padrão usado nesta sessão pra
validar mudanças de backend sem arriscar o Neon de produção:

```python
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as config_mod
config_mod.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
config_mod.Config.SQLALCHEMY_ENGINE_OPTIONS = {}

from app import create_app, db, socketio
app = create_app()
# ... db.create_all(), popular Person/Role, usar socketio.test_client() ...
```

Pra testar a UI de verdade, dá pra subir um servidor local com um banco
SQLite descartável e uma rota `/debug-login/<nome>` temporária que seta a
sessão direto (sem passar pelo OAuth do Google) — só usar em script de
teste fora do repo, nunca commitar essa rota.

## Porta de entrada (`/entrar`)

Fora da home da Bazinga existe uma página de login própria: `/entrar`
(template `entrar.html`) → login Google → `/abrir` (`abrir.html`). É o link
pra mandar pra quem é de fora do grupo. O callback do OAuth olha
`session['veio_do_entrar']` pra decidir se volta pra home ou pra `/abrir`.

Na tela `/abrir`, o que é honesto em cada botão:
- **Instalar app** nasce escondido e só aparece quando o navegador dispara
  `beforeinstallprompt`. Para isso existem `/manifest.webmanifest` e
  `/sw.js`. O service worker não faz cache de propósito (app dinâmico);
  ele existe só porque o navegador exige um registrado pra permitir a
  instalação.
- **Abrir no Chrome** usa `intent://` no Android. No desktop **não existe**
  jeito de uma página abrir outro navegador — lá ele copia o link e
  explica, em vez de fingir.

## Mídia (foto, GIF, vídeo)

A compressão é **no navegador, antes do upload** (`comprimirImagem()` em
`chat.html`): redimensiona pro máximo de 1600px no maior lado e exporta em
WebP (ou JPEG se o navegador não suportar). Uma foto de 7 MB vira ~180 KB.

Dois cuidados que não são óbvios:
- **GIF passa direto**, sem canvas. O canvas só captura o primeiro quadro,
  então comprimir um GIF mata a animação.
- **Vídeo não é recomprimido** — o navegador não faz isso de forma
  confiável. É só validado (25 MB no `/api/upload`, com checagem da
  assinatura real do arquivo) e renderizado com `preload="metadata"`, senão
  abrir o canal baixaria todos os vídeos de uma vez.

O upload começa quando o arquivo entra na fila, não no Enter — quando a
pessoa termina de digitar, o arquivo já está no servidor. O socket só
recebe a URL, e `enviar_mensagem` recusa qualquer `anexo_url` que não comece
com `/` (nada de `blob:` nem link externo).

Lembre que `app/static/uploads/` é efêmero no Render free: as fotos somem no
restart. Para valer, precisa de storage externo.

## Editor de imagem

`abrirEditorImagem(file, { formato, titulo, aoConfirmar })` em `chat.html` —
usado pelo avatar (`circulo`) e pelo ícone do servidor (`quadrado`). Corta,
gira 90°, espelha, dá zoom, arrasta com mouse ou dedo.

Como funciona, porque não é óbvio:
- A imagem girada/espelhada vira um canvas offscreen (`corrigida`), e o
  corte é calculado em cima dele. Assim o recorte continua sendo só
  "desenhar um retângulo reto".
- **O preview e a exportação chamam a mesma função** (`desenharEditor`),
  mudando só o tamanho. É o que garante que o que aparece é o que sai.
- GIF não passa pelo canvas: aparece o aviso e o botão "Usar como está",
  que envia o arquivo original.

## Convenções

- Nomes de eventos de socket, funções e variáveis em **português** (`criar_servidor_discord`, `plantar_servidor`, `apagar_geonote`...). Siga o padrão existente.
- Emoji/toast/mensagens de UI em português informal.
- `br_now()` em `models.py` — sempre usar em vez de `datetime.utcnow()` pra
  timestamps mostrados ao usuário (fuso de Brasília).

## Deploy (Render)

`Procfile`: `gunicorn -k eventlet -w 1 run:app`. O `-k eventlet` **não é
opcional** — com o worker sync padrão do gunicorn o WebSocket não sobe e o
Socket.IO cai para long-polling degradado. Mantenha `-w 1`: com mais de um
worker as salas do Socket.IO ficariam divididas entre processos (precisaria
de um message queue tipo Redis).

`SECRET_KEY` é obrigatória em produção — `config.py` levanta erro no boot se
ela faltar, em vez de cair num valor fixo que tornaria as sessões forjáveis.

Uploads vão para `app/static/uploads/`, que é **efêmero no Render free**:
avatar e ícone de servidor somem quando o container reinicia. Para valer
mesmo, precisaria de um storage externo (S3/Cloudinary).

## Estado atual

- PR aberto: https://github.com/AqueleSales/Bazinga-hub-gg/pull/1 — persistência
  de mapa/servidores/canais/perfil, várias correções de bugs herdados.
  **Precisa rodar `python atualizar_banco.py` depois do merge.**
- Compra na loja grava um `Purchase` e existe `/api/inventario`, mas **não há
  UI de inventário** — o usuário compra e não vê o que tem.
- Servidores têm configurações (ícone/nome/descrição/cor), canais com tópico
  e flag `is_private`, convites por link/QR, calendário de eventos, reações
  de emoji e anexos de foto/GIF/vídeo.
- Canal privado vale de verdade: a tabela `channel_members` diz quem entra,
  `pode_ver_canal()` exige estar nela, e o canal nem é anunciado pra quem
  não tem acesso. O dono do servidor sempre entra.
- Não existe cargo por servidor ainda: `pode_gerenciar_servidor()` devolve
  True só pro dono. É o único ponto a mudar quando os cargos existirem.
- Posição dos amigos no radar (`atualizar_localizacao`) não é persistida: só
  é retransmitida para as salas dos Servidores em que o usuário é membro
  (`srv_<id>`), nunca em broadcast — é coordenada de GPS real.
- Os canais globais (`server_id=NULL`) continuam liberados para qualquer
  logado em `pode_ver_canal()`, por compatibilidade. Se um dia forem
  removidos de vez, dá pra apertar essa checagem.
