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

## `com_retry()` — repetido em 3 arquivos

`auth/routes.py`, `events.py` e `main/routes.py` têm cada um sua própria
cópia de um helper `com_retry(fn, tentativas=3-4, espera=...)` que reexecuta
uma query se ela lançar `OperationalError` (cold start do Neon). Isso existia
só no login originalmente; foi estendido para os handlers de mapa/servidor/
perfil porque com `NullPool` qualquer operação pode sofrer cold start, não
só a primeira. Se for adicionar um novo handler que grava no banco, **use
`com_retry()` para o `db.session.commit()`**, não só faça a query direta.

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

## Convenções

- Nomes de eventos de socket, funções e variáveis em **português** (`criar_servidor_discord`, `plantar_servidor`, `apagar_geonote`...). Siga o padrão existente.
- Emoji/toast/mensagens de UI em português informal.
- `br_now()` em `models.py` — sempre usar em vez de `datetime.utcnow()` pra
  timestamps mostrados ao usuário (fuso de Brasília).

## Estado atual

- PR aberto: https://github.com/AqueleSales/Bazinga-hub-gg/pull/1 — persistência
  de mapa/servidores/canais/perfil, várias correções de bugs herdados.
  **Precisa rodar `python atualizar_banco.py` depois do merge.**
- Funcionalidades sem persistência real ainda: edição de nota/servidor no
  mapa não atualiza visualmente em outros clientes já conectados (só no
  reload); posição dos amigos no radar (`atualizar_localizacao`) é
  retransmitida mas não desenhada no mapa do lado de quem recebe.
