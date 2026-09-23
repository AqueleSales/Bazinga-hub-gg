# Bazinga Hub

Clone do Discord em Flask + Socket.IO, com um diferencial: um mapa (Leaflet)
onde os usuários "plantam" servidores e deixam notas geolocalizadas.

## Stack

- **Backend**: Flask, Flask-SQLAlchemy, Flask-SocketIO (eventlet), Authlib (login Google OAuth)
- **Banco**: Neon (Postgres serverless) em produção. `config.py` usa `NullPool` —
  **toda query abre uma conexão nova**. Isso causa falhas intermitentes de
  "cold start" (Neon "acordando"). Veja `com_retry()` abaixo.
- **Frontend**: um único arquivo `app/templates/chat.html` (~6600 linhas) com
  CSS e JS inline — sem build step, sem framework. PeerJS para voz/vídeo
  (WebRTC), Leaflet para o mapa, qrcodejs para o QR do convite.
- **Deploy**: Render, free tier (pode dormir). Veja a seção Deploy.

## Arquivos principais

| Arquivo | O quê |
|---|---|
| `app/models.py` | Todos os modelos SQLAlchemy |
| `app/utils.py` | `com_retry()`, `comitar_com_retry()` e **todas** as checagens de permissão |
| `app/events.py` | Os 39 handlers de Socket.IO (`@socketio.on(...)`) |
| `app/main/routes.py` | Rotas REST (`/chat`, `/api/...`, `/convite/<code>`) |
| `app/auth/routes.py` | Login Google OAuth |
| `app/templates/chat.html` | O app inteiro (HTML+CSS+JS) — ~6600 linhas |
| `app/templates/entrar.html` / `abrir.html` | Porta de entrada independente (ver seção) |
| `atualizar_banco.py` | Migração manual — **rodar sempre que mexer em `models.py`** |
| `seed.py` / `seed_loja.py` | Popula cargos/canais/produtos padrão |

---

# As 5 regras que já causaram bug real

Cada uma destas seções existe porque o problema **aconteceu** neste projeto.
Não são preferências de estilo.

## 1. ⚠️ Sem Flask-Migrate/Alembic — migração é na mão

`db.create_all()` (chamado no boot) só cria tabelas que **não existem** —
nunca adiciona colunas em tabela já existente. Toda coluna nova em
`models.py` precisa também de um `ALTER TABLE` em `atualizar_banco.py`
(`add_column_se_nao_existir(...)`), senão a coluna existe no modelo Python
mas não no banco real, e a query falha em produção (Postgres) mesmo
funcionando no teste local com SQLite, que é mais tolerante.

**O bug**: `geo_note.duration_hours`/`expires_at` e colunas de `map_server`
existiam no modelo havia tempo mas nunca tinham sido migradas no Neon —
toda criação de nota/servidor no mapa falhava em silêncio (o toast dizia
"sucesso" e nada era salvo).

```bash
python atualizar_banco.py     # depois de QUALQUER mudança em models.py
```

## 2. `com_retry()` / `comitar_com_retry()` — em `app/utils.py`

`com_retry(fn)` reexecuta uma query se ela lançar `OperationalError` (cold
start do Neon). Com `NullPool` **qualquer** operação pode sofrer cold start,
não só a primeira, então todo handler que toca o banco deve usar.

Para **escritas**, use `comitar_com_retry(preparar)`: a função `preparar`
monta as alterações e o helper comita.

**O bug**: `com_retry(db.session.commit)` parece certo e não é — se o commit
falha, o `rollback()` do retry descarta as alterações e a tentativa seguinte
comita uma sessão vazia. Por isso `preparar` precisa refazer as alterações
a cada tentativa.

## 3. Erro de banco não pode falhar em silêncio

Handlers antigos capturavam só `(OperationalError, PendingRollbackError)` e
voltavam vazio. Qualquer outro erro (ex: `ProgrammingError` de coluna
inexistente) passava batido, sem log e sem toast. Padrão atual:

```python
except Exception as e:
    db.session.rollback()
    print(f"[ERRO ALGO] {e}")
    emit('erro_bazinga', {'msg': f'Não foi possível fazer X: {e}'})
```

O frontend escuta `erro_bazinga` e mostra um toast vermelho com a mensagem
real. **Incluir `{e}` na mensagem do usuário** (não só no log) foi o que
permitiu diagnosticar o bug da regra 1 sem acesso ao terminal.

## 4. Permissão se checa no servidor, sempre

`app/utils.py` concentra tudo:

| Função | Para quê |
|---|---|
| `pode_ver_canal(usuario, canal)` | Membro do servidor **e**, se o canal for privado, estar em `allowed_members` (o dono sempre entra) |
| `canal_permitido(usuario, canal_id)` | Busca o canal e devolve só se puder acessar |
| `pode_gerenciar_servidor(usuario, srv)` | Hoje: só o dono |
| `servidor_gerenciavel(usuario, server_id)` | Busca o servidor e devolve só se puder administrar |

**O bug**: `is_private` só escondia o canal na sidebar. Quem chutasse o id
entrava, lia e escrevia normalmente. Hoje a checagem é real e passa por
`entrar_canal`, `enviar_mensagem`, `entrar_call` e `/api/mensagens/<id>`.

Nunca confie num id vindo do cliente: `_membros_escolhidos()` em `events.py`
só aceita ids de quem **já é membro** do servidor, senão dava pra adicionar
qualquer usuário do banco a um canal privado.

Apagar/editar exige conferir o dono (`author_id`, `owner_id`, `person_id`)
contra o usuário da sessão.

## 5. XSS — nunca jogue dado de usuário cru em `innerHTML`

Três helpers em `chat.html`, definidos logo antes de `showToast()`:

- `esc(valor)` — texto (mensagem, nome, nota, descrição de produto)
- `escUrl(url)` — para `src`/`href`; só deixa passar `http(s)` e caminhos do
  próprio site, barrando `javascript:` e `data:`
- `escJs(valor)` — para valores dentro de um `onclick="..."`

**O bug**: `appendMessageGrouped()` interpolava `texto`/`autor`/`avatar`
direto no `innerHTML`, então `<img src=x onerror=...>` executava script no
navegador de todo mundo que abrisse o canal. Valia também para nota do mapa,
nome de servidor, participante de call e produtos do bazar.

**Pegadinha do `escUrl`**: ele bloqueia `blob:` de propósito. Para preview
local de arquivo escolhido, defina `img.src` **por propriedade**, fora do
`innerHTML` — já quebrou o preview do ícone na criação de servidor.

---

# Onde as coisas moram

## `chat.html` — mapa do arquivo

Ele é grande; estes são os marcos (a linha muda, o nome não):

| Seção | O que tem |
|---|---|
| Injeção de variáveis do Flask | `currentUserId`, `currentUserName`, `currentChannelId` |
| Segurança | `esc()`, `escUrl()`, `escJs()` |
| Toasts e modais genéricos | `showToast()`, `openConfirmModal()`, `openInputModal()` |
| Envio de mídia | `comprimirImagem()`, `uploadMidiaCompleto()`, `uploadMidia()` |
| Servidor: sidebar | `entrarNoServidor()`, `htmlDoCanal()`, `souDonoDoServidor()` |
| Modais de servidor/canal/convite | `abrirModalCanal()`, `abrirConfigServidor()`, `abrirModalConvite()` |
| Configurações completas | `abrirConfigCompleta()`, `trocarSecaoConfig()`, `desenharMembrosDaConfig()` |
| Calendário | `abrirCalendario()`, `desenharCalendario()`, `abrirModalEvento()` |
| Mapa | `renderizarGeoNote()`, `renderizarServidorMapa()`, `carregarDadosDoMapa()` |
| DMs | `setupDMClickListeners()`, `iniciarDMTemporaria()` |
| Ações da mensagem | `appendMessageGrouped()`, `abrirMenuMensagem()`, `iniciarEdicao()` |
| Anexos | `adicionarAnexos()`, `desenharAnexosPendentes()` |
| Editor de imagem | `abrirEditorImagem()`, `desenharEditor()` |
| Voz/vídeo | `initVoiceChannel()`, `disconnectCall()` |
| Mercado | `carregarMercado()` |

## Abas (`vistaAtual`)

`switchMainView(nome)` troca a aba e guarda em `vistaAtual`:
`home` (radar+DM) · `dm` · `server` · `market` · `calendar`.

Tudo que redesenha em cima de um evento do servidor deve respeitar a aba
atual. `entrarNoServidor(id, manterVista)` existe por isso.

**O bug**: `servidor_discord_criado` serve para duas coisas — servidor
**novo** (criado ou acabou de entrar) e servidor **atualizado** (dono mexeu
no nome/ícone/canais). O frontend chamava `entrarNoServidor()` nos dois
casos, então qualquer edição arrastava todo mundo para dentro do servidor,
mesmo quem estava no mapa ou numa DM.

## Modelos

`Role` · `Person` · `Server` · `Channel` · `Message` · `Reaction` ·
`Invite` · `Event` · `DirectMessage` · `Product` · `Purchase` · `GeoNote` ·
`MapServer`

Tabelas de associação: `server_members` (quem está no servidor) e
`channel_members` (quem entra num canal **privado**).

## Eventos de Socket.IO

39 handlers em `events.py`. Agrupados:

- **Canal/mensagem**: `entrar_canal`, `sair_canal`, `enviar_mensagem`,
  `editar_mensagem`, `apagar_mensagem`, `reagir_mensagem`
- **Servidor**: `criar_servidor_discord`, `editar_servidor`,
  `apagar_servidor`, `sair_do_servidor`, `expulsar_membro`,
  `transferir_posse`, `listar_membros_servidor`
- **Canais**: `criar_canal`, `editar_canal`, `apagar_canal`
- **Convites**: `criar_convite`, `listar_convites`, `apagar_convite`,
  `entrar_por_convite`
- **Eventos**: `listar_eventos`, `criar_evento`, `editar_evento`,
  `apagar_evento`
- **Mapa**: `criar_geonote`, `editar_geonote`, `apagar_geonote`,
  `plantar_servidor`, `editar_servidor_mapa`, `apagar_servidor_mapa`,
  `atualizar_localizacao`, `entrar_servidor_pin`
- **Voz**: `entrar_call`, `sair_call`
- **DM/perfil**: `entrar_dm`, `enviar_mensagem_direta`, `atualizar_perfil`,
  `mudar_status`

### Salas

- `sala_pessoal(user_id)` → `user_<id>` — DMs e notificações direcionadas
- `sala_servidor(server_id)` → `srv_<id>` — o que interessa só aos membros
- o id do canal (string) — mensagens do canal
- `voz_<canal_id>` — participantes da call

**Canal privado não pode ser anunciado para a sala do servidor inteiro**:
`_anunciar_canal()` manda só para quem pode ver, senão quem não tem acesso
descobre que o canal existe. Pelo mesmo motivo `servidor_para_json(srv,
usuario)` recebe o destinatário e filtra os canais — cada membro recebe a
sua própria versão do servidor.

## Rotas REST

`/` · `/entrar` · `/abrir` · `/chat` · `/convite/<code>` ·
`/manifest.webmanifest` · `/sw.js` ·
`/api/mensagens/<id>` · `/api/dms/<id>` · `/api/mapa/dados` ·
`/api/produtos` · `/api/produtos/<id>/comprar` · `/api/inventario` ·
`/api/upload`

---

# Subsistemas

## Porta de entrada (`/entrar`)

Página de login própria, fora da home da Bazinga — é o link para mandar a
quem é de fora do grupo. Fluxo: `/entrar` → OAuth Google → `/abrir`. O
callback olha `session['veio_do_entrar']` para decidir se volta para a home
ou para `/abrir`.

O que é honesto em cada botão de `/abrir`:

- **Instalar app** nasce escondido e só aparece quando o navegador dispara
  `beforeinstallprompt`, ou seja, quando o site é mesmo instalável. Para
  isso existem `/manifest.webmanifest` e `/sw.js`. O service worker **não
  faz cache de propósito** (o app é todo dinâmico; cache só serviria para
  mostrar tela velha) — ele existe porque o navegador exige um registrado
  para permitir a instalação.
- **Abrir no Chrome** usa `intent://` no Android. No desktop **não existe**
  forma de uma página abrir outro navegador; lá ele copia o link e explica,
  em vez de fingir que abriu.

## Mídia (foto, GIF, vídeo)

A compressão é **no navegador, antes do upload** (`comprimirImagem()`):
redimensiona para no máximo 1600px no maior lado e exporta em WebP (JPEG se
o navegador não suportar). Uma foto de 7 MB vira ~180 KB.

Duas exceções que não são óbvias:

- **GIF passa direto**, sem canvas — o canvas só captura o primeiro quadro e
  mataria a animação.
- **Vídeo não é recomprimido** — o navegador não faz isso de forma
  confiável. É só validado (25 MB no `/api/upload`, com checagem da
  assinatura real do arquivo, não da extensão) e renderizado com
  `preload="metadata"`, senão abrir o canal baixaria todos os vídeos de uma
  vez.

O upload começa quando o arquivo entra na fila, não no Enter — quando a
pessoa termina de digitar, o arquivo já está no servidor. O socket só recebe
a URL, e `enviar_mensagem` recusa qualquer `anexo_url` que não comece com
`/` (nada de `blob:` nem link externo).

## Editor de imagem

`abrirEditorImagem(file, { formato, titulo, aoConfirmar })` — usado pelo
avatar (`circulo`) e pelo ícone do servidor (`quadrado`), tanto na criação
quanto na edição. Corta, gira 90°, espelha, dá zoom, arrasta com mouse ou
dedo.

- A imagem girada/espelhada vira um canvas offscreen (`corrigida`), e o
  corte é calculado em cima dele. Assim o recorte continua sendo só
  "desenhar um retângulo reto", sem matriz de transformação no meio.
- **O preview e a exportação chamam a mesma função** (`desenharEditor`),
  mudando só o tamanho — é o que garante que o que aparece é o que sai.
- GIF mostra aviso e o botão "Usar como está", que envia o original.
- `editarIconeAtual()` busca a foto que o servidor já tem (mesma origem) e
  devolve para o editor, para não precisar reescolher o arquivo só para
  cortar.

## Configurações de servidor — dois níveis

- **Popup rápido** (`abrirConfigServidor`): nome, foto, descrição, cor.
- **Tela cheia** (`abrirConfigCompleta`): menu lateral com Perfil, Canais,
  Membros, Convites, Eventos e excluir o servidor.

## Mapa

O pino do servidor usa a foto real do servidor, e o nome/ícone vêm do
`Server` ligado — **não** da cópia feita na hora de plantar, senão renomear
o servidor não mudava nada no mapa.

O pino cai nas iniciais quando não há ícone **ou quando a imagem não
carrega** (`onerror`). Isso não é firula: a pasta de uploads é efêmera, então
uma foto enviada antes pode ter sumido do disco — sem o fallback sobrava só
o quadrado colorido do fundo, que era o "a imagem não aparece no mapa".

## Reações e densidade do chat

A linha de reações nasce **vazia** quando não há reação nenhuma e some via
`.msg-reacoes:empty { display: none }`.

**O bug**: quando ela sempre trazia o botão de "+", toda mensagem ganhava
~20px invisíveis de altura, e o chat ficava com aquele espaçamento estranho
(46px entre linhas agrupadas, contra 24px hoje). O "+" continua acessível
pela barra de hover.

---

# Convenções

- Nomes de eventos de socket, funções e variáveis em **português**
  (`criar_servidor_discord`, `plantar_servidor`, `apagar_geonote`...).
- Emoji/toast/mensagens de UI em português informal.
- Toasts: `showToast(msg, tipo)` com `info`/`success`/`warning`/`error`.
  Para ações que envolvem o banco: toast `info` otimista ("Salvando...") no
  emit, e `success` só quando a confirmação voltar do servidor — não assuma
  sucesso no emit.
- Use `openConfirmModal()` / `openInputModal()` em vez de criar modal novo
  para pergunta simples (e nunca `confirm()`/`prompt()` nativos).

## `br_now()` — sempre, e **sem fuso**

Use `br_now()` de `models.py` em vez de `datetime.utcnow()` para qualquer
timestamp mostrado ao usuário.

Ele devolve o horário de Brasília **sem tzinfo**, de propósito: todas as
colunas são `db.DateTime` (TIMESTAMP sem fuso), que guardam só a hora de
parede.

**O bug**: quando ele devolvia datetime com fuso, gravar funcionava (o driver
descarta o tzinfo), mas qualquer comparação em Python — `br_now() >=
convite.expires_at`, por exemplo — estourava com *"can't compare
offset-naive and offset-aware datetimes"*.

Um irmão desse bug: `enviar_mensagem` subtraía 3h do timestamp que `br_now()`
já devolvia em horário de Brasília, então toda mensagem aparecia 3h no
passado. Não converta de novo o que já veio convertido.

---

# Testando sem tocar no banco de produção

Não existe suite automatizada. O padrão são scripts de fumaça com SQLite em
memória e `socketio.test_client()`:

```python
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as config_mod
config_mod.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
config_mod.Config.SQLALCHEMY_ENGINE_OPTIONS = {}

from app import create_app, db, socketio
app = create_app()
# db.create_all(), popular Role/Person, socketio.test_client(...)
```

**Pegadinha do test_client**: `socketio.test_client()` já dispara o
`connect`, então `carregar_meus_servidores` fica na fila. Se o helper chamar
`get_received()` para "limpar", ele engole esse payload — e o teste parece
mostrar que o usuário não tem servidor nenhum.

Os testes cobrem: permissões de canal e mensagem; loja e inventário;
servidores/canais/convites/eventos; e canal privado (membro comum não vê o
canal, não entra chutando o id, não escreve, toma 403 na API, e perde o
canal da tela ao ser removido).

Para testar a UI de verdade: suba um servidor local com SQLite descartável e
uma rota `/debug-login/<nome>` temporária que seta a sessão direto, sem
OAuth. **Nunca commite essa rota** — ela vive só no script de teste, fora do
repo.

Lembre que o Flask **cacheia templates** com `debug=False`: depois de editar
`chat.html`, reinicie o servidor de teste ou você vai depurar a página
antiga (já aconteceu).

---

# Deploy (Render)

`Procfile`: `gunicorn -k eventlet -w 1 run:app`

- **`-k eventlet` não é opcional** — com o worker sync padrão o WebSocket não
  sobe e o Socket.IO cai para long-polling degradado.
- **Mantenha `-w 1`** — com mais de um worker as salas do Socket.IO ficariam
  divididas entre processos, e seria preciso um message queue (Redis).

`SECRET_KEY` é obrigatória em produção: `config.py` levanta erro no boot se
faltar, em vez de cair num valor fixo que tornaria as sessões forjáveis.

`app/static/uploads/` é **efêmero no Render free**: avatar, ícone de servidor
e anexos somem quando o container reinicia. Para valer, precisa de storage
externo (S3/Cloudinary).

---

# Estado atual

**PR aberto**: https://github.com/AqueleSales/Bazinga-hub-gg/pull/2 —
segurança, sistema de servidores completo e porta de entrada própria.
**Rodar `python atualizar_banco.py` depois do merge.**

## Pendências conhecidas

- **Storage externo para uploads** — é a pendência mais concreta; hoje as
  fotos somem no restart do Render free.
- **Sem cargo por servidor**: `pode_gerenciar_servidor()` devolve `True` só
  para o dono. É o **ponto único** a mudar quando os cargos existirem — por
  isso todo handler passa por essa função em vez de comparar `owner_id` na
  mão. Enquanto não existir, uma tela de "Cargos" seria decorativa.
- **Inventário sem UI**: a compra grava um `Purchase` e existe
  `/api/inventario`, mas o usuário compra e não vê o que tem.
- **Modo Fantasma** salva só no `localStorage`, não no banco (troca de
  aparelho e volta ligado); o duplo clique no mapa ("teletransporte") ainda
  emite a posição sem checar o modo; e ativar o fantasma não remove seu
  marcador de quem já te via — só para de atualizar.
- **Bugs de call não reproduzidos**: tela cheia da chamada e o "clip".
  Precisam de duas pessoas em call real para investigar.
- **Canais globais** (`server_id=NULL`) continuam liberados para qualquer
  logado em `pode_ver_canal()`, por compatibilidade. Não há UI que leve até
  eles. Se forem removidos de vez, dá para apertar essa checagem.
