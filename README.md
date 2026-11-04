# Pantheon (repositório: Bazinga Hub)

Clone do Discord feito em **Flask + Socket.IO**, com um diferencial: um **mapa** (Leaflet) onde as pessoas plantam servidores, deixam notas geolocalizadas e encontram amigos. Tem também economia própria (moeda **Dracmas / DRC**), Passe de Batalha de temporada, loja de cosméticos, um bazar de comunidade com Pix e um app desktop em Electron.

> **Sobre os nomes:** o repositório se chama *Bazinga Hub*, mas o produto foi renomeado para **Pantheon** (antes "Panteão"). O nome exibido mora em `APP_NOME` (`app/__init__.py`). Alguns identificadores ficaram com o nome antigo de propósito (`panteao://`, `appId gg.panteao.desktop`, `Panteao-Setup-*.exe`, o repo `panteao-releases`), porque trocá-los quebraria o login do app desktop e as atualizações.

---

## Sumário

1. [Funcionalidades](#funcionalidades)
2. [Stack](#stack)
3. [Estrutura do repositório](#estrutura-do-repositório)
4. [Rodando localmente](#rodando-localmente)
5. [Variáveis de ambiente](#variáveis-de-ambiente)
6. [Banco de dados e migrações](#banco-de-dados-e-migrações)
7. [Testes](#testes)
8. [Deploy (Render)](#deploy-render)
9. [App desktop (Electron)](#app-desktop-electron)
10. [Regras e convenções do projeto](#regras-e-convenções-do-projeto)
11. [Segurança](#segurança)
12. [Documentação interna](#documentação-interna)

---

## Funcionalidades

**Chat e comunidade**
- Servidores, canais de texto e de voz, canais privados, categorias, separadores e tipos de canal (anúncios, regras, mídia, palco).
- **Cargos por servidor** com hierarquia e permissões, mais sobrescritas de permissão por canal (`app/cargos.py`).
- Mensagens com edição, exclusão, resposta, reações, fixadas, anexos, GIFs (Giphy) e emoji vetorial (Twemoji).
- Mensagens diretas (DM) com anexos, edição e exclusão, e DMs fixadas.
- Amizades com pedido, bloqueio e presença em tempo real.
- Convites por link com prévia, busca rápida (Ctrl+K), calendário de eventos e arrastar/reordenar servidores em pastas.
- **Explorar servidores:** vitrine pública ("o mar de barquinhos") com prévia segura e entrada sem convite.

**Voz e vídeo**
- Chamadas em canal e 1-a-1 por DM, via **PeerJS (WebRTC, malha P2P)**.
- Compartilhamento de tela com ajuste automático de qualidade, gravação e clipes da call.
- Atividades dentro da call (por exemplo, xadrez) e **Música** (pesquisa no YouTube, player e fila).

**Mapa social**
- Notas geolocalizadas com duração, respostas e reações; servidores "plantados" no mapa; lojas no mapa.
- Mapa por raio, localizar amigos, radar de estranhos (opt-in recíproco, desligado por padrão) e localização por IP ou pelo navegador.

**Perfil e conexões**
- Cartão de perfil com banner, tema, moldura, placa, estilo de nome, efeitos e títulos.
- **Conexões:** a pessoa cola um link (GitHub, YouTube, Spotify e outros) e o cartão é montado automaticamente. LinkedIn é lido a partir do PDF do perfil.
- Playlist de músicas no perfil.

**Economia e cosméticos**
- Nível, XP e patentes (12 patentes × 3 subníveis), insígnias e inventário.
- **Armazém:** loja em DRC com compra atômica e livro-razão.
- **Passe de Batalha de temporada** (100 níveis, trilhas Grátis e Premium), missões e títulos, configurados no Estúdio (`/admin`).
- **Cosméticos:** ~113 temas e ~1040 itens gerados por código (`tools/cosm/`), mais um Estúdio de efeitos sem código.
- **Olimpo:** a assinatura do app (o "nitro"), com a insígnia Ômega e a trilha Premium do passe.

**Bazar da comunidade**
- Lojas, produtos, pedidos, Pix copia e cola, avaliações, favoritos, frete, disputas, banimento e anúncios.
- Pagamento pelo app via gateway **Asaas** (Pix com split para a loja). O app **não guarda dinheiro de ninguém**.

**Segurança e moderação**
- **Guardião:** triagem de texto (regras locais, com IA Gemini só para o que for marcado) e de imagens enviadas. O conteúdo retido vai para análise humana no Estúdio.
- Termos de Uso e LGPD, denúncias, silenciar pessoas e notificações push (Web Push / VAPID).

**Plataforma**
- PWA instalável (manifesto e service worker que só cacheia estáticos) e app desktop para Windows.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Flask 3, Flask-SQLAlchemy, Flask-SocketIO (eventlet), Authlib (login com Google OAuth) |
| Servidor | gunicorn com worker `eventlet`, 1 worker (`Procfile`) |
| Banco | PostgreSQL (Neon serverless) em produção |
| Frontend | Sem build step e sem framework: `app/templates/chat.html` com CSS e JS inline, mais módulos em `app/static/js/` |
| Tempo real | Socket.IO (texto, presença, mapa) e PeerJS/WebRTC (voz e vídeo) |
| Mapa | Leaflet |
| Mídia | Cloudinary (avatares, ícones, anexos), Pillow (recorte de GIF) |
| APIs externas | Giphy, YouTube Data API, Spotify, GitHub, Gemini (Guardião e leitura de PDF), Asaas (pagamentos) |
| Desktop | Electron + electron-builder + electron-updater |
| Python | 3.11.9 (`runtime.txt`) |

---

## Estrutura do repositório

```
.
├── run.py                  # ponto de entrada (eventlet.monkey_patch + create_app)
├── seed.py                 # cria tabelas e popula cargos/canais padrão
├── Procfile                # web: gunicorn -k eventlet -w 1 run:app
├── requirements.txt
├── runtime.txt             # python-3.11.9
├── bazar_admin.py          # dá poder de moderação / define porte de loja
├── conceder_item.py        # dá ou retira item do inventário de alguém
├── CLAUDE.md               # documentação interna detalhada (histórico por rodada)
├── PLANO_COSMETICOS.md     # plano das patentes, insígnias e cosméticos
├── app/
│   ├── __init__.py         # create_app(), APP_NOME, moeda, origens do socket
│   ├── config.py           # Config (banco Neon, SECRET_KEY, cookies, pool)
│   ├── models.py           # todos os modelos SQLAlchemy (~40 tabelas)
│   ├── utils.py            # com_retry() e todas as checagens de permissão
│   ├── events.py           # handlers Socket.IO principais (canais, DM, mapa, amigos...)
│   ├── auth/               # login Google OAuth
│   ├── main/               # rotas REST (/chat, /api/..., /convite/<code>)
│   ├── cargos.py           # cargos, categorias, permissões por canal
│   ├── cosmeticos.py       # catálogo, posse, patentes e insígnias
│   ├── loja.py             # Armazém (loja em DRC)
│   ├── passe.py            # Passe de Batalha e títulos
│   ├── efeitos.py          # Estúdio de efeitos
│   ├── bazar.py            # Bazar da comunidade
│   ├── pagamentos.py       # gateway de Pix (Asaas ou simulado)
│   ├── olimpo.py           # assinatura Olimpo
│   ├── guardiao.py         # segurança com IA
│   ├── explorar.py         # Explorar servidores
│   ├── conexoes.py         # conexões do perfil (links e PDF do LinkedIn)
│   ├── musica.py           # pesquisa e player de música
│   ├── atividades.py       # atividades na call (xadrez)
│   ├── notas_mapa.py       # respostas e reações nas notas do mapa
│   ├── ordem.py            # ordem dos servidores e DMs fixadas
│   ├── push.py             # notificações push
│   ├── admin.py            # Estúdio (/admin, só administradores)
│   ├── novidades.py        # pop-up de novidades (entrada nova no topo)
│   ├── *_events.py         # eventos Socket.IO de cada módulo
│   ├── templates/          # chat.html (o app inteiro), entrar.html, admin.html...
│   └── static/             # css/, js/, img/, audio/, fonts/, emoji/
├── desktop/                # casca Electron (main.js, preload.js, login, seletor)
├── tools/cosm/             # gerador dos temas de cosméticos (Node)
├── testes/                 # scripts de fumaça (SQLite em memória)
└── instance/               # bancos SQLite locais
```

---

## Rodando localmente

**Pré-requisitos:** Python 3.11, e (para o desktop e o gerador de temas) Node.js.

```bash
# 1. Ambiente virtual e dependências
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Variáveis de ambiente: crie um arquivo .env na raiz (veja a seção abaixo)

# 3. Cria as tabelas e os dados iniciais (canais e cargos padrão)
python seed.py

# 4. Sobe o servidor
python run.py
```

O login é **somente via Google OAuth**, então é preciso criar credenciais no Google Cloud Console e informar `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET`.

> **Banco local:** `config.py` monta a URL pensando no Neon (adiciona `sslmode=require`). Para desenvolvimento, o caminho mais simples é apontar `DATABASE_URL` para um Postgres. Os testes automatizados usam SQLite em memória sobrescrevendo a configuração (veja `CLAUDE.md`, seção "Testando sem tocar no banco de produção").

---

## Variáveis de ambiente

Só `SECRET_KEY` e `DATABASE_URL` são essenciais para subir. O resto habilita recursos específicos, e sem ele o recurso fica indisponível ou degradado.

| Variável | Para quê |
|---|---|
| `SECRET_KEY` | **Obrigatória em produção.** Assina as sessões (o app recusa subir no Render sem ela). |
| `DATABASE_URL` | URL do Postgres (Neon). |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Login com Google. |
| `CLOUDINARY_URL` | Upload de avatar, ícone e anexos. |
| `GIPHY_API_KEY` | Busca de GIF (sem ela só `/api/gifs` responde 503). |
| `YOUTUBE_API_KEY`, `YOUTUBE_UNIDADES_DIA` | Pesquisa de música por nome (sem a chave só funciona colar link). |
| `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` | Integração com Spotify. |
| `GITHUB_TOKEN` | Mais fôlego na API do GitHub (conexões do perfil). |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | IA para o Guardião e para a leitura de PDF do LinkedIn. |
| `GUARDIAO`, `GUARDIAO_DMS`, `GUARDIAO_MODELO` | Controle do Guardião. |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | Notificações push. |
| `TURN_URLS`, `TURN_USERNAME`, `TURN_CREDENTIAL` | Servidor TURN para chamadas atrás de NAT restritivo. |
| `PAGAMENTOS` | `asaas`, `simulado` ou `desligado`. |
| `ASAAS_API_KEY`, `ASAAS_AMBIENTE`, `ASAAS_WEBHOOK_TOKEN` | Pix via Asaas (`ASAAS_AMBIENTE=producao` sai do sandbox). |
| `TAXA_PLATAFORMA_PCT` | Taxa da plataforma no split dos pedidos. |
| `OLIMPO_GRATIS`, `OLIMPO_PRECO_CENT` | O Olimpo é grátis por padrão. `OLIMPO_GRATIS=0` passa a cobrar. |
| `ORIGENS_PERMITIDAS` | Origens extras aceitas pelo WebSocket (domínio próprio). |
| `EXIGIR_TERMOS`, `CONTATO_PRIVACIDADE` | Termos de Uso/LGPD. |
| `BAZINGA_SERVER_ID` | Servidor "oficial" usado por insígnias e regras específicas. |

No Render também são lidas `RENDER`, `RENDER_EXTERNAL_URL` e `RENDER_GIT_COMMIT` (esta última vira a versão do app, usada para avisar abas desatualizadas).

---

## Banco de dados e migrações

**Não há Flask-Migrate/Alembic.** `db.create_all()` só cria tabelas que ainda não existem e **nunca adiciona colunas** a tabelas existentes.

- Toda coluna nova em `models.py` precisa também de um `ALTER TABLE` no script de migração manual `atualizar_banco.py`, rodado depois de qualquer mudança nos modelos:
  ```bash
  python atualizar_banco.py
  ```
- Há uma rede de segurança no boot (`adicionar_colunas_que_faltam()`) que adiciona colunas ausentes sozinha, mas ela **não** cobre dados nem índices. O código deve tratar `None` nas colunas novas.
- Todo handler que toca o banco usa `com_retry()` / `comitar_com_retry()` (`app/utils.py`) por causa do *cold start* do Neon.
- Cada query é uma ida de rede. Antes de aceitar um handler novo, conte as queries com `testes/contar_queries.py`.

> `atualizar_banco.py` é citado na documentação interna, mas **não veio no zip analisado**. Confirme se ele está no repositório.

---

## Testes

Não há framework de testes. O padrão são **scripts de fumaça** em `testes/`, com SQLite em memória e `socketio.test_client()`. Rode da raiz do projeto:

```bash
python testes/fumaca_social.py
python testes/fumaca_servidor.py
python testes/fumaca_seguranca.py
python testes/contar_queries.py
```

Há ~50 scripts, quase um por subsistema: `fumaca_cargos`, `fumaca_permissoes_canal`, `fumaca_bazar`, `fumaca_pagamentos`, `fumaca_guardiao`, `fumaca_passe`, `fumaca_loja`, `fumaca_call`, `fumaca_notas_mapa`, `fumaca_musica`, entre outros. A lista completa, com o que cada um cobre, está em `CLAUDE.md`, seção "Testes". Rode **todos** antes de commitar e confira o resultado de cada um.

Para testar a interface de verdade e os bugs de tempo real, use **duas pessoas/abas**: com um usuário só, um broadcast que não chega aos outros passa despercebido.

---

## Deploy (Render)

`Procfile`:

```
web: gunicorn -k eventlet -w 1 run:app
```

- **`-k eventlet` é obrigatório.** Sem ele o WebSocket não sobe e o Socket.IO cai para long-polling.
- **Mantenha `-w 1`.** A presença (`usuarios_conectados`) vive na memória do processo. Com mais de um worker seria preciso um message queue (Redis).
- Configure as variáveis de ambiente no painel do Render (veja a seção acima).
- Depois de cada deploy que mexa em `models.py`, rode `python atualizar_banco.py`.
- Para anunciar uma atualização aos usuários, adicione uma entrada **no topo** de `app/novidades.py`.

O plano gratuito do Render pode "dormir", e o Neon pode ter *cold start*. Os dois são tratados com retry, mas a primeira requisição pode ser lenta.

---

## App desktop (Electron)

A pasta `desktop/` contém uma casca Electron que carrega o site e cuida de login, bandeja do sistema e atualização automática.

```bash
cd desktop
npm install
npm start          # roda em modo de desenvolvimento
npm run dist       # gera o instalador Windows (NSIS) em dist/
```

- `desktop/config.json` aponta para o endereço do servidor.
- As atualizações são publicadas no GitHub Releases (repositório `panteao-releases`) via `electron-updater`.
- Mudanças só no site **não** exigem um instalador novo. Mudanças em `desktop/` só chegam aos usuários depois de `npm run dist` e de uma nova release.

---

## Regras e convenções do projeto

Seis regras surgiram de bugs reais e valem para qualquer contribuição (detalhes em `CLAUDE.md`):

1. **Migração é manual.** Coluna nova em `models.py` exige `ALTER TABLE` em `atualizar_banco.py`.
2. **Use `com_retry()` / `comitar_com_retry()`** em todo acesso ao banco. Em escritas, a função de preparo refaz as alterações a cada tentativa.
3. **Erro de banco não falha em silêncio.** Faça rollback, registre no log e emita `erro_bazinga` com a mensagem real.
4. **Permissão se checa sempre no servidor** (`app/utils.py`). Nunca confie num id vindo do cliente.
5. **XSS:** nunca jogue dado de usuário cru em `innerHTML`. Use `esc()`, `escUrl()` e `escJs()` no `chat.html`.
6. **Tempo real é para quem está olhando, não só para quem agiu.** Depois de aplicar uma mudança, emita também para as salas dos outros interessados.

Outras convenções:
- Use `br_now()` para datas, **sem fuso**.
- Prefira `transform`/`opacity` nas animações e respeite `body.rolando`, para não travar a rolagem.
- Temas de cosméticos são desenhados **por código**, sem sprite, logo ou áudio de terceiros. Mudanças no gerador: `node tools/cosm/gerar.js`.

---

## Segurança

- **Nunca commite o `.env`.** Ele está no `.gitignore`, mas a documentação interna registra que credenciais (Neon, Google e `SECRET_KEY`) já foram parar no histórico do git (commit `e7e2a27`). **Troque essas credenciais** e, se o repositório for público, considere limpar o histórico.
- Os arquivos em `instance/*.db` são bancos SQLite locais. Não versione bancos com dados reais.
- `SECRET_KEY` é obrigatória em produção, e o app recusa subir sem ela.
- O WebSocket só aceita as origens do próprio app (`ORIGENS_PERMITIDAS` para domínios extras).
- CDNs externos são carregados com SRI. O cookie de sessão é `HttpOnly`, `SameSite=Lax` e `Secure` no Render.
- O webhook do Asaas confere o token em tempo constante e reconfirma status e valor na API antes de dar o pedido como pago.
- O Guardião trata o texto do usuário como **dado**, não como instrução (proteção contra prompt injection), e a resposta da IA é um JSON fechado.

---

## Documentação interna

| Arquivo | Conteúdo |
|---|---|
| `CLAUDE.md` | Documento principal: stack, regras, mapa do `chat.html`, eventos, rotas e o histórico de cada rodada (1 a 34). |
| `PLANO_COSMETICOS.md` | Plano das patentes, insígnias e do laboratório de cosméticos. |

`CLAUDE.md` cita também uma pasta `docs/` (`HISTORICO.md`, `ESTUDIO_EFEITOS.md`, `PLANO_TEMAS.md`, `ARTE_TEMAS.md`, `PLANO_IA.md`), `BACKLOG.md` e os scripts `atualizar_banco.py` e `conceder_drc.py`, que **não estavam no zip analisado**.
