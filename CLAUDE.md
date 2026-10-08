# Panteão (repositório: Bazinga Hub)

Clone do Discord em Flask + Socket.IO, com um diferencial: um mapa (Leaflet)
onde os usuários "plantam" servidores e deixam notas geolocalizadas.

## Stack

- **Backend**: Flask, Flask-SQLAlchemy, Flask-SocketIO (eventlet), Authlib (login Google OAuth)
- **Banco**: Neon (Postgres serverless) em produção. `config.py` usa pool com
  `pool_pre_ping` (o `NullPool` antigo foi trocado). Cold start do Neon ("acordando")
  ainda pode falhar qualquer query: veja `com_retry()` abaixo. **Cada query é uma ida
  de rede** — conte-as (`testes/contar_queries.py`) antes de aceitar um handler novo.
- **Frontend**: um único arquivo `app/templates/chat.html` (~8100 linhas) com
  CSS e JS inline — sem build step, sem framework. PeerJS para voz/vídeo
  (WebRTC, malha P2P — ver Pendências), Leaflet para o mapa, qrcodejs para o
  QR do convite, Twemoji pra desenhar emoji igual em qualquer SO.
- **APIs externas**: Cloudinary (upload de mídia) e Giphy (busca de GIF no
  chat — `GIPHY_API_KEY`). O Tenor (concorrente do Giphy) parou de aceitar
  registro novo em jan/2026 e desliga de vez em 30/06/2026 — não vale a pena
  integrar com ele nem pra teste.
- **Deploy**: Render, free tier (pode dormir). Veja a seção Deploy.

## Arquivos principais

| Arquivo | O quê |
|---|---|
| `app/models.py` | Todos os modelos SQLAlchemy |
| `app/utils.py` | `com_retry()`, `comitar_com_retry()` e **todas** as checagens de permissão |
| `app/events.py` | ~55 handlers de Socket.IO (`@socketio.on(...)`) |
| `app/cosmeticos.py` | Catálogo de itens exclusivos, **posse**, patentes (nível → ícone), insígnias e slots equipados (ver "Rodada 5") |
| `app/static/js/cosmeticos.js` | Ícones SVG das patentes/insígnias, popover "orb", inventário e efeitos (objeto global `Cosm`) |
| `app/static/css/cosmeticos.css` | Animações das patentes, inventário e o laboratório (Gogeta/Sasuke/Fusão) |
| `app/loja.py` | **Armazém** (loja do app em DRC): preço, compra atômica, vitrine (ver Rodada 10) |
| `app/bazar.py` / `app/bazar_events.py` | **Bazar da comunidade** (modelo A, Pix direto): lojas, produtos, pedidos, Pix copia e cola, moderação (ver Rodada 11) |
| `app/static/js/bazar.js` / `css/bazar.css` | Interface do Bazar (objeto global `Bazar`): vitrine por porte, loja, produto, pedido, editor, moderação |
| `bazar_admin.py` | Dá poder de moderar (`admin <@usuario>`) e define loja parceira (`porte <@usuario> grande`) |
| `app/static/js/loja.js` / `css/loja.css` | Vitrine do Armazém (objeto global `Loja`): hero em carrossel, prateleiras, modal do item |
| `conceder_item.py` | Dá/retira item do inventário de alguém (`python conceder_item.py <@usuario> tudo`) |
| `app/main/routes.py` | Rotas REST (`/chat`, `/api/...`, `/convite/<code>`) |
| `app/auth/routes.py` | Login Google OAuth |
| `app/templates/chat.html` | O app inteiro (HTML+CSS+JS) — ~8100 linhas |
| `app/templates/entrar.html` | Página de bloqueio/login (ver seção) |
| `desktop/` | Casca Electron do app desktop (`main.js`, `preload.js`, `login.html`, `seletor.html`; ver Rodada 7) |
| `app/templates/abrir.html` | Tela pós-login "continuar/instalar" — hoje órfã (ver seção) |
| `atualizar_banco.py` | Migração manual — **rodar sempre que mexer em `models.py`** |
| `seed.py` / `seed_loja.py` | Popula cargos/canais/produtos padrão |

---

# As 6 regras que já causaram bug real

Cada uma destas seções existe porque o problema **aconteceu** neste projeto.
Não são preferências de estilo.

## 1. ⚠️ Sem Flask-Migrate/Alembic — migração é na mão

`db.create_all()` (chamado no boot) só cria tabelas que **não existem** —
nunca adiciona colunas em tabela já existente. Toda coluna nova em
`models.py` precisa também de um `ALTER TABLE` em `atualizar_banco.py`
(`add_column_se_nao_existir(...)`), senão a coluna existe no modelo Python
mas não no banco real, e a query falha em produção (Postgres) mesmo
funcionando no teste local com SQLite, que é mais tolerante.

**Desde 01/10/2026 há uma rede de segurança**: `adicionar_colunas_que_faltam()` roda no
boot e adiciona sozinha a coluna que o modelo tem e o banco não (sem NOT NULL/DEFAULT).
Isso evita o bug, mas **não** dispensa o `atualizar_banco.py` (dados, índices) — e o
código precisa tratar `None` nas colunas novas. Ver "Rodada de 01/10/2026".

**O bug**: `geo_note.duration_hours`/`expires_at` e colunas de `map_server`
existiam no modelo havia tempo mas nunca tinham sido migradas no Neon —
toda criação de nota/servidor no mapa falhava em silêncio (o toast dizia
"sucesso" e nada era salvo). Aconteceu de novo, menor, com `message.is_pinned`
durante o desenvolvimento local — banco de teste antigo, coluna nova no
modelo, `/chat` quebrando com "Erro de conexão com o banco" até rodar a
migração.

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
contra o usuário da sessão. A chamada 1-a-1 por DM segue a mesma lógica: quem
liga (`chamar_amigo`) e quem entra na sala (`entrar_call` com `canal_id`
`"dm_<a>_<b>"`) são checados contra `Friendship.status == 'accepted'`, nunca
contra o que o cliente afirma ser.

## 5. XSS — nunca jogue dado de usuário cru em `innerHTML`

Três helpers em `chat.html`, definidos logo antes de `showToast()`:

- `esc(valor)` — texto (mensagem, nome, nota, descrição de produto)
- `escUrl(url)` — para `src`/`href`; só deixa passar `http(s)` e caminhos do
  próprio site, barrando `javascript:` e `data:`
- `escJs(valor)` — para valores dentro de um `onclick="..."` (faz
  `JSON.stringify` e depois `esc`, então lida direito com aspas/acentos —
  usado, por exemplo, nos botões de ligar da DM, que embutem nome e avatar
  do amigo no `onclick`)

**O bug**: `appendMessageGrouped()` interpolava `texto`/`autor`/`avatar`
direto no `innerHTML`, então `<img src=x onerror=...>` executava script no
navegador de todo mundo que abrisse o canal. Valia também para nota do mapa,
nome de servidor, participante de call e produtos do bazar.

**Pegadinha do `escUrl`**: ele bloqueia `blob:` de propósito. Para preview
local de arquivo escolhido, defina `img.src` **por propriedade**, fora do
`innerHTML` — já quebrou o preview do ícone na criação de servidor.

## 6. Mudança em tempo real é pra quem tá olhando, não só pra quem agiu

Um `emit()` sem `room`/`to=` (ou com `to=` mas mirando só quem fez a ação)
volta **só pro socket de quem disparou o evento**. É fácil escrever o
handler, testar sozinho, ver funcionar, e nunca perceber que ninguém mais
recebe nada — porque com um usuário só o bug não aparece.

**O bug (achado com dois usuários testando junto)**: aconteceu três vezes
na mesma sessão, em lugares diferentes:
- Alguém entrava num servidor pelo link de convite (`entrar_por_link`,
  rota HTTP pura) e ninguém mais via a lista de membros atualizar — só
  quem entrou tinha os dados, o resto precisava de F5.
- `atualizar_perfil` só respondia pra quem editou o próprio nome/avatar
  (`emit('perfil_atualizado', ...)` sem `to=`) — os outros membros do
  servidor continuavam vendo o avatar/nome antigo na lista até recarregar.
- Quem tinha o servidor aberto mas não tinha entrado numa call de voz não
  tinha como saber que um amigo já estava lá — só descobria entrando ele
  mesmo (aí sim recebia `novo_usuario_call`, que também só avisa quem já
  está na sala).

A correção nos três casos foi a mesma ideia: depois de aplicar a mudança,
perguntar "quem mais, além de quem agiu, precisa saber disso **agora**?" e
emitir pra `sala_servidor(...)`/`sala_pessoal(...)` deles também (`entrar_
por_link` e `entrar_por_convite` emitem `membro_entrou_servidor`;
`atualizar_perfil` emite `perfil_membro_mudou`; `entrar_call`/`sair_call`
mantêm `participantes_call` em memória e emitem `participantes_call_mudou`
pra sala do servidor, não só pra sala da call). Teste sempre com **dois
usuários reais** (duas abas/sessões) antes de considerar uma feature
"ao vivo" pronta — testando sozinho, esse tipo de bug é invisível.

---

# Onde as coisas moram

## `chat.html` — mapa do arquivo

Ele é grande; estes são os marcos (a linha muda, o nome não):

| Seção | O que tem |
|---|---|
| Injeção de variáveis do Flask | `currentUserId`, `currentUserName` (agora `let`, muda ao editar o nome), `currentChannelId` |
| Segurança | `esc()`, `escUrl()`, `escJs()` |
| Toasts e modais genéricos | `showToast()`, `openConfirmModal()`, `openInputModal()` — `.modal-overlay` é sempre `z-index: 10500`, mais alto que qualquer popup de configurações |
| Envio de mídia | `comprimirImagem()`, `uploadMidiaCompleto()`, `uploadMidia()` |
| Servidor: sidebar | `entrarNoServidor()`, `htmlDoCanal()`, `souDonoDoServidor()` |
| Modais de servidor/canal/convite | `abrirModalCanal()`, `abrirConfigServidor()`, `abrirModalConvite()` |
| Configurações completas do servidor | `abrirConfigCompleta()` (popup, não mais tela cheia), `trocarSecaoConfig()`, `desenharMembrosDaConfig()` |
| Configurações de usuário | `.settings-overlay`/`.settings-modal` (popup), `aplicarPerfilEntrada()`, `constraintsDoMic()` |
| Presença e lista de membros | `desenharMembrosSidebar()`, `atualizarStatusAmigo()` |
| Amigos | `abrirModalAdicionarAmigo()`, `linhaAmigoHtml()`, listeners de `pedido_amizade_*` |
| Mensagens fixadas | `ctx-pin` no menu de mensagem, `#painel-fixadas`, listener de `fixadas_do_canal` |
| Busca rápida (Ctrl+K) | `abrirQuickSwitcher()`, `coletarItensQuickSwitcher()` |
| Calendário | `abrirCalendario()`, `desenharCalendario()`, `abrirModalEvento()` |
| Mapa | `renderizarGeoNote()`, `renderizarServidorMapa()`, `carregarDadosDoMapa()` |
| DMs | `setupDMClickListeners()`, `iniciarDMTemporaria()` |
| Ações da mensagem | `appendMessageGrouped()`, `abrirMenuMensagem()`, `iniciarEdicao()` |
| Anexos | `adicionarAnexos()`, `desenharAnexosPendentes()` |
| Editor de imagem | `abrirEditorImagem()`, `desenharEditor()` |
| Voz/vídeo | `conectarNaCall()` (compartilhada por canal e DM), `initVoiceChannel()`, `disconnectCall()` |
| Qualidade automática da call | `monitorarEAjustarBitrate()`, `criarCompositor(altura, fpsDesenho)` |
| Chamada 1-a-1 por DM | `iniciarChamadaDM()`, listeners de `chamada_recebida`/`chamada_aceita`/`chamada_recusada`/`chamada_cancelada` |
| Gravar/clipar a call | `criarCompositor()`, `iniciarGravacao()`, `montarClipeDoBuffer()`, `iniciarDeteccaoAutomatica()` |
| Emoji vetorial | `emojificar(el)` (Twemoji) |
| Busca de GIF | `abrirGifPicker()`, `carregarGifs()` |
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
`Invite` · `Event` · `DirectMessage` · `Friendship` · `Product` · `Purchase` ·
`GeoNote` · `MapServer`

Tabelas de associação: `server_members` (quem está no servidor) e
`channel_members` (quem entra num canal **privado**).

`Friendship` é uma linha por par (`requester_id` → `addressee_id`,
`status` `pending`/`accepted`) — quem aceitou vira amigo nos dois sentidos;
consultar sempre com `OR` nas duas colunas (ver `amigos_de()`/`sao_amigos()`
em `events.py`).

`Person.created_at` (default `br_now`, aplicado só em linha nova) alimenta
o "Membro desde" real do cartão de perfil — conta criada antes dessa
coluna existir fica `NULL` de propósito (não dá pra inventar a data real),
e o template só mostra a linha quando tem valor.

## Eventos de Socket.IO

~55 handlers em `events.py`. Agrupados:

- **Canal/mensagem**: `entrar_canal`, `sair_canal`, `enviar_mensagem`,
  `editar_mensagem`, `apagar_mensagem`, `reagir_mensagem`
- **Mensagens fixadas**: `fixar_mensagem` (alterna), `listar_fixadas`
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
- **Voz (canal e DM)**: `entrar_call`, `sair_call` — genéricos, servem tanto
  pra canal de voz quanto pra call de DM (ver Chamada 1-a-1 abaixo);
  `listar_participantes_call` dá a prévia de quem já está numa call sem
  precisar entrar (ver "Prévia de call" abaixo)
- **Toque da chamada de DM**: `chamar_amigo`, `aceitar_chamada`,
  `recusar_chamada`, `cancelar_chamada`
- **Gravação**: `iniciar_gravacao`, `parar_gravacao` (só avisam quem mais
  está na call — a gravação em si é 100% no navegador de quem clicou)
- **DM/perfil**: `entrar_dm`, `enviar_mensagem_direta`, `atualizar_perfil`
  (aceita `name`/`avatar`/`custom_status`/`bio`/`banner_color` — string vazia
  em `banner_color` limpa e volta pro gradiente animado padrão), `mudar_status`
- **Amigos**: `enviar_pedido_amizade`, `listar_pedidos_pendentes`,
  `responder_pedido_amizade`, `remover_amigo`
- **Presença**: `connect`/`disconnect` (built-in do Socket.IO) alimentam
  `usuarios_conectados` em memória e emitem `usuario_ficou_online`/`offline`

### Salas

- `sala_pessoal(user_id)` → `user_<id>` — DMs, notificações diretas e o
  toque da chamada de DM (`chamada_recebida`/`aceita`/`recusada`/`cancelada`)
- `sala_servidor(server_id)` → `srv_<id>` — o que interessa só aos membros
  (inclui `usuario_ficou_online`/`offline`)
- o id do canal (string) — mensagens do canal, inclusive `mensagem_fixada`
- `voz_<canal_id>` — participantes da call de um canal de servidor
- `voz_dm_<menorId>_<maiorId>` — participantes de uma call 1-a-1 (mesmo
  prefixo `voz_`, só que o "canal_id" é a string `dm_<menorId>_<maiorId>`
  montada por `sala_dm()`; `entrar_call`/`sair_call` não precisaram de
  eventos novos, só de checar `startswith('dm_')` e validar amizade em vez
  de `canal_permitido`)

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
`/api/upload` · `/api/gifs?q=<busca>` · `/api/localizacao/ip` · `/api/convite/<code>/previa`

---

# Subsistemas

## Porta de entrada / página de bloqueio (`/entrar`)

Virou o portão único do app, não só o link pra gente de fora. Fluxo atual:

- `/chat` sem sessão → redireciona pra `/entrar` (antes voltava pra `/` sem
  explicação nenhuma).
- `/entrar` com sessão já ativa → pula direto pro `/chat` (não passa mais
  por `/abrir`).
- `/entrar` sem sessão → marca `session['veio_do_entrar']` e mostra a página
  (split-screen: Google de um lado, "baixar app" do outro, seta pra voltar
  pra home).
- Callback do Google, se veio de `/entrar` → cai direto no `/chat` (antes
  caía em `/abrir`).
- `/auth/logout` → sempre volta pra `/entrar`, nunca pra `/`.

**`/abrir` ficou órfã** de propósito: a rota e o template continuam no
código (`main.abrir`, `abrir.html`), mas nada mais linka pra ela — é
infraestrutura que pode voltar a ser útil (oferecer instalar o app de
dentro do chat, por exemplo) sem precisar recriar nada.

O que é honesto em cada botão de `/entrar` e `/abrir`:

- **Instalar app** nasce escondido e só aparece quando o navegador dispara
  `beforeinstallprompt`, ou seja, quando o site é mesmo instalável. Para
  isso existem `/manifest.webmanifest` e `/sw.js`. O service worker só cacheia
  **estático** (`/static/*` versionado por `APP_VERSAO` + CDN com versão fixa na URL) e
  nunca `/chat`, `/api`, `/socket.io`, `/auth` nem POST (ver Rodada 7).
- **Abrir no Chrome** usa `intent://` no Android. No desktop **não existe**
  forma de uma página abrir outro navegador; lá ele copia o link e explica,
  em vez de fingir que abriu.

## Mídia (foto, GIF, vídeo)

A compressão é **no navegador, antes do upload** (`comprimirImagem()`):
redimensiona para no máximo 1600px no maior lado e exporta em WebP (JPEG se
o navegador não suportar). Uma foto de 7 MB vira ~180 KB.

Duas exceções que não são óbvias:

- **GIF passa direto**, sem canvas — o canvas só captura o primeiro quadro e
  mataria a animação. O upload de avatar tinha um segundo botão "Escolher
  GIF" travado atrás de "Apenas usuários Nitro" — removido porque o botão
  normal de "Enviar imagem" já aceitava GIF o tempo todo (`accept="image/*"`
  cobre `image/gif`), então a trava não escondia nada de verdade.
- **Vídeo não é recomprimido** — o navegador não faz isso de forma
  confiável. É só validado (25 MB no `/api/upload`, com checagem da
  assinatura real do arquivo, não da extensão) e renderizado com
  `preload="metadata"`, senão abrir o canal baixaria todos os vídeos de uma
  vez.

**O bug (GIF de avatar sem preview)**: a primeira versão do editor de GIF
pra avatar perguntava "estática ou usar assim" com dois botões — e escolher
"usar assim" mandava direto, sem mostrar nem uma prévia do que ia virar
avatar. Hoje é um botão só: o editor detecta GIF e troca o `<canvas>` do
recorte por uma `<img>` de verdade tocando a animação dentro do círculo
(mesmo arquivo que vai ser enviado), sem controles de girar/zoom (não tem
efeito nenhum, já que GIF vai inteiro). Recortar um GIF *mantendo* a
animação continua fora de alcance — precisaria decodificar e reexportar
quadro a quadro (lib tipo `gif.js`), não só trocar a UI.

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
- GIF troca o `<canvas>` por uma `<img>` tocando a animação de verdade (sem
  controles de corte/zoom, que não têm efeito nenhum nele) e manda o
  arquivo original — ver "O bug (GIF de avatar sem preview)" na seção Mídia.
- `editarIconeAtual()` busca a foto que o servidor já tem (mesma origem) e
  devolve para o editor, para não precisar reescolher o arquivo só para
  cortar.

## Busca de GIF (Giphy)

O botão "GIF" da barra de mensagem só abria o seletor de arquivo do PC
filtrado por `.gif` — redundante com o "+" de anexo geral, que já aceita
`image/*` (GIF incluso). Virou busca de verdade:

- `/api/gifs?q=<busca>` (`app/main/routes.py`) chama a API do Giphy **no
  servidor** — a `GIPHY_API_KEY` nunca chega ao navegador. Sem `q`, devolve
  os "em alta" (trending). Devolve só `{id, preview, url, nome}` por GIF —
  o resto da resposta do Giphy (dezenas de variações de tamanho, embed,
  estatística) não interessa pro cliente.
- `abrirGifPicker()`/`carregarGifs()` no `chat.html` mostram um grid
  (`fixed_width_small`, ~100px) num painel flutuante igual ao de emoji;
  busca com debounce de 400ms. Clicar num GIF manda `enviar_mensagem` com
  `anexo_url` = a variação `fixed_height` (~200px, leve) direto do CDN do
  Giphy — **não** passa pelo `/api/upload`/Cloudinary.
- `enviar_mensagem` (`events.py`) precisou aceitar o domínio
  `media*.giphy.com` na validação de `anexo_url` (antes só aceitava
  caminho do próprio site ou `res.cloudinary.com`).
- **Sem `GIPHY_API_KEY` configurada**, a rota devolve 503 com uma mensagem
  clara em vez de quebrar — configurar no Render (`Environment` do
  serviço) e localmente no `.env` (gitignored).

**Por que Giphy e não Tenor** (o que o Discord usa): o Tenor parou de
aceitar registro de API novo em jan/2026 e desliga de vez em 30/06/2026 —
não dava pra montar nada em cima dele que sobrevivesse.

## Configurações — sempre popup, nunca mais tela cheia

Servidor e usuário têm cada um dois níveis, e os quatro seguem o mesmo
molde visual (`.modal-overlay` escurecido + cartão central com sidebar +
conteúdo, X e ESC fecham, clique fora fecha):

- **Servidor, popup rápido** (`abrirConfigServidor`): nome, foto, descrição,
  cor.
- **Servidor, completo** (`abrirConfigCompleta`): Perfil, Canais, Membros,
  Convites, Eventos e excluir o servidor. Era tela cheia (`#server-full-settings`
  com `position:fixed;inset:0`) — virou um cartão de `920px` dentro do
  mesmo padrão de overlay dos outros modais.
- **Usuário** (`#settings-modal`, ícone de engrenagem): Minha Conta, Perfis
  (nome de exibição — editável de verdade agora —, avatar, cor da faixa,
  status personalizado, bio), Voz e Vídeo, Aparência. Também era tela cheia
  (`100vw`/`100vh`) e virou popup do mesmo jeito.

**Removido por ser cópia sem sentido do Discord**: badge "NITRO" na aba
Perfis, o bloco "Assinar Nitro", e o texto "Krisp Virtual" na supressão de
ruído (renomeado pra só "Supressão de ruído" — o que existe de verdade por
trás são as constraints nativas do `getUserMedia`, não o SDK da Krisp).

**Voz e Vídeo ganhou função de verdade**: "Perfil de entrada"
(Isolamento/Estúdio/Personalizado) e os toggles de supressão de
ruído/eco/ganho automático só trocavam classe CSS — hoje alimentam
`constraintsDoMic()`, que monta o objeto de constraints aplicado sempre que
o microfone é pego (entrar numa call, trocar de dispositivo, testar o mic).
Isolamento força `noiseSuppression`/`echoCancellation`/`autoGainControl`
ligados; Estúdio força todos desligados (áudio cru); Personalizado usa os
três toggles manuais.

**Pegadinha de z-index**: um modal genérico (`openInputModal`, por exemplo)
aberto **de dentro** de um popup de configurações ficava escondido atrás
dele — `.modal-overlay` tinha `z-index: 5000` e o popup de configurações
`9999`. Corrigido subindo `.modal-overlay` pra `10500` (mais alto que
qualquer outro popup do app). Se um modal novo nascer atrás de outro, é
essa a primeira coisa a checar.

**Cartão de perfil tinha dois dados 100% inventados**: "Jogando no
momento: Marvel Rivals" era HTML fixo, igual pra todo mundo, sem nenhuma
feature de Rich Presence por trás (precisaria de um app nativo rodando no
PC, tipo o Discord de verdade — fora de escopo aqui) — removido de vez, não
só escondido. "Membro desde" também era um texto fixo ("Set. 2026"/"Hoje")
— virou `Person.created_at` de verdade (ver seção Modelos); conta antiga
sem essa data simplesmente não mostra a linha, em vez de inventar uma.

**Faixa de perfil animada era só um acidente**: o CSS já tinha
`background-size: 400% 400%` no fallback (quando `banner_color` tá vazio),
preparado pra uma animação de gradiente — só que sem `animation` nenhuma
aplicada, então ficava parado. Tinha até um `@keyframes bg-spin` pronto no
arquivo, usado só num efeito de loading em outro canto (linha ~7859).
Hoje isso é uma **opção explícita** (botão ao lado da cor, `.banner-
animado`), não só o que sobra quando ninguém escolhe cor nenhuma.

**Status/bio/cor só atualizavam dentro do próprio popup de
configurações**: o preview ao vivo (enquanto digitava) dava a impressão de
que salvou, mas o `perfil_atualizado` (a confirmação de verdade do
servidor) só tratava `name`/`avatar` — a barra inferior e o cartão de
perfil ficavam com o valor antigo até um F5. Corrigido aplicando os três
campos também na confirmação.

**Emoji virou vetor (Twemoji)**, em vez de depender da fonte de emoji de
cada sistema operacional — `emojificar(el)` roda depois de qualquer render
de conteúdo de usuário (mensagem, status, bio); não é aplicado no
`emoji-picker-panel` em si porque o Twemoji troca o emoji por uma `<img>` e
isso quebraria `el.textContent` (usado pra pegar qual emoji foi clicado).

## Presença e lista de membros

Não existia rastreio nenhum de quem está com o app aberto. Agora:

- `usuarios_conectados` (dicionário em memória, `app/events.py`) conta
  **sockets por pessoa**, não um booleano — assim abrir/fechar uma aba
  extra não faz a pessoa "piscar" offline enquanto outra aba dela continua
  conectada.
- `handle_connect`/`handle_disconnect` (o segundo não existia) emitem
  `usuario_ficou_online`/`offline` pras salas de servidor **e** pros amigos
  (`sala_pessoal` de cada um), só na transição real online↔offline.
- A sidebar de membros do servidor (`#server-members-sidebar`) era HTML
  fixo mostrando só "você mesmo" — nunca tinha sido ligada a dado nenhum.
  Hoje `desenharMembrosSidebar()` desenha Online/Offline de verdade a partir
  de `listar_membros_servidor` (que ganhou `status`/`online` na resposta) e
  atualiza ao vivo com os eventos de presença.
- O ícone de "Ocultar Lista de Membros" no header do canal também nunca
  tinha handler — agora recolhe (`width` pra `0`, transição CSS) e lembra a
  preferência no `localStorage`.
- Quando alguém entra num servidor (link ou código), os outros membros
  conectados recebem `membro_entrou_servidor` e re-pedem a lista — antes só
  quem entrou via o modal de código recebia algo (`servidor_discord_criado`
  sem `to=`), e quem entrava pelo link (`entrar_por_link`, rota HTTP pura,
  sem contexto de socket) não avisava ninguém. Ver regra 6.
- Crachá de dono na sidebar (`👑`) usava o emoji do sistema em tamanho
  normal, chamativo demais — virou um ícone Font Awesome pequeno e opaco.

## Amigos

Não existia sistema de amizade nenhum: `/chat` montava a lista de "amigos"
com `Person.query.filter(Person.id != usuario_atual.id).all()` — **todo
mundo que existe no banco** virava amigo na tela (o comentário no código
antigo admitia "simula sua lista de amigos"). O botão "Enviar pedido de
amizade" só disparava um toast de sucesso, sem `emit` nenhum.

Hoje é `Friendship` (`pending`/`accepted`) de verdade:

- `enviar_pedido_amizade` busca por nome ou e-mail exato, recusa se já
  existir pedido/amizade, notifica `sala_pessoal` do destinatário.
- `responder_pedido_amizade` aceita (linha vira `accepted`) ou recusa
  (linha é apagada).
- `remover_amigo` desfaz uma amizade aceita (sem UI dedicada ainda — dá pra
  chamar via console/uma ação futura no menu do usuário).
- `/chat` e a lista de DMs usam `amigos_de()`/a mesma query com `OR` nas
  duas colunas — só amizade `accepted` conta.

## Mensagens: latência percebida

A mensagem só aparecia na tela depois do round-trip completo (emit →
`comitar_com_retry` → `receber_mensagem` de volta) — em qualquer cold
start do Neon (regra 2) isso virava alguns segundos de "cadê minha
mensagem". `enviarMensagemOtimista()` desenha a bolha na hora (classe
`.pendente`, opacidade reduzida) com um `temp_id` gerado no cliente; a
resposta do servidor (`receber_mensagem`, que ecoa esse `temp_id` de
volta) troca a bolha otimista pela confirmada. Se não confirmar em 8s
(erro/queda), a bolha vira `.falha-envio` em vez de ficar "pendente" pra
sempre.

**Nunca ecoe o `temp_id` cru do cliente pro canal inteiro** —
`temp_id_seguro()` em `events.py` valida contra `^[A-Za-z0-9_-]{1,64}$`
antes de reemitir; sem isso, um `temp_id` malicioso (aspas/colchetes)
quebraria o `querySelector` de `receber_mensagem` em **todo mundo** que
está no canal, não só em quem mandou.

## Perfil e preferências moram na conta, não no navegador

**O bug**: o avatar (e o GIF escolhido) "resetava" ao trocar de dispositivo ou
rede. Causa: o callback do Google (`auth/routes.py`) sobrescrevia
`Person.avatar` com a foto do Google **a cada login**, e sessão nova (outro
aparelho, cookie limpo) = login novo. Hoje só sincroniza se a pessoa ainda
usa foto do Google ou nenhuma (`_avatar_e_do_google()`); avatar próprio
(Cloudinary) nunca é tocado. Quem já teve o avatar sobrescrito no passado
precisa escolher de novo — não há de onde recuperar.

**Regra**: preferência de usuário que precisa acompanhar a pessoa vai pro
banco, não pro `localStorage` (que é por navegador). `localStorage` fica só
pra conveniência de UI (ex.: lista de membros recolhida).

- **Modo Fantasma** = `Person.ghost_mode`. O cliente emite
  `alternar_fantasma {ativo}` (valor explícito, não "inverter" — duas abas
  clicando juntas não se anulam) e só muda a tela quando o servidor devolve
  `preferencias_carregadas` (que também é enviado ao conectar, então vale em
  qualquer aparelho; o valor inicial já vem no HTML pra não piscar OFF→ON).
  `atualizar_localizacao` **descarta** a posição no servidor se o fantasma
  estiver ligado (antes só o navegador se continha — o teletransporte por
  duplo clique vazava). Ao ligar, emite `posicao_amigo_removida` pra
  `sala_servidor` (o pino some do mapa de quem já via — regra 6).

## Battle Pass (nível/XP) e missões

Tudo calculado no servidor (`app/utils.py`); o cliente só desenha o que chega em
`xp_atualizado` e `missoes_atualizadas` (nunca recalcula nível nem progresso).

- **Nível 1–1000+ (desde a Rodada 5)**: subir do nível N pro N+1 custa
  `100 + 204·(N-1)` até o 100 (1→2 = 100, 99→100 = 20.092; total até o 100 =
  **999.504 XP**) e, do 100 em diante, `+25 XP` a mais por nível (até ~42,6 mil
  por nível; do 1000+ um passo fixo, sem teto). `Person.xp` guarda o TOTAL, então
  mexer na curva não precisa de migração (só muda o nível calculado). O servidor
  manda o **bloco de 100 níveis** onde a pessoa está (`marcos`, `marcos_da_pagina`);
  o cliente rola até o nível atual. Detalhes e as **patentes** em "Rodada 5".
- **Recompensas** (`recompensa_do_nivel`): +50 DRC por nível, +150 a cada 5,
  +300 a cada 10; o 1º nível de cada **patente** nova carrega o nome dela
  (`titulo`; as patentes substituíram `TITULOS_POR_NIVEL`). As moedas
  dos níveis cruzados são pagas na MESMA transação que soma o XP (regra 2).
- **Fontes de XP**: mensagem (+10, cooldown 30s), **tempo ativo** (+3 XP/min,
  teto 60 min/dia), **bônus diário** (+50, +10 por dia seguido até 7; pular um
  dia zera) e **missões**.
- **Missões** (`MISSOES` em utils.py): cada pessoa tem 3 diárias + 3 semanais
  sorteadas de um pool. O sorteio é **determinístico** (semente = pessoa +
  período), então a escolha não é guardada — só o progresso
  (`MissaoProgresso`, `chave` = dia ou segunda-feira). Virou o período, a chave
  muda e as missões novas nascem zeradas sem apagar nada. Cada missão tem um
  `evento` ligado a algo que o app já faz: `mensagem`, `dm`, `reacao` (só ao
  ADICIONAR — ligar/desligar não vira XP), `nota`, `plantar`, `minutos`,
  `call_minutos`, `login`. Concluiu = o XP cai na hora (sem "resgatar").
  Para criar missão nova: uma linha em `MISSOES` (entra no pool sozinha).
- **Todo progresso passa por `_emitir_progresso()`** (events.py), que engole
  erro de propósito: falha de banco na missão nunca pode quebrar a mensagem/
  reação/nota que a originou.
- **Tempo ativo**: o cliente manda `batimento_atividade` 1x/min só se houve
  mouse/teclado com a aba visível (ou se está em call). **O servidor não
  confia**: limita a 1 batimento a cada 50s e a 60 min de XP/dia, e decide
  `call_minutos` por `_call_por_sid` (estar na call de verdade).
- Linhas de `MissaoProgresso` com `codigo` começando em `_` são contadores
  internos (ex.: `_tempo_ativo`), nunca aparecem pra pessoa.
- O texto "Como ganhar XP" em `chat.html` é fixo e **espelha** as constantes —
  mudou uma, mude a outra. A tabela `missao_progresso` nasce pelo
  `db.create_all()` (não precisa de ALTER).
- UI: anel de progresso + barra com brilho, missões em abas Diárias/Semanais
  (cartão com canto cortado, barra fina, contagem de reset), trilha de 100
  níveis com rolagem horizontal (**sem** `backdrop-filter` nos cartões: 100
  blurs pesam), "+N XP" flutuando na barra lateral e comemoração com confete.

## Visual: "vidro" sobre o Discord clássico

Direção: estrutura e paleta do Discord antigo (cinza-azulado
`#36393f/#2f3136/#202225`, blurple suave `#7289da`, cantos arredondados), com
camadas de **vidro fosco** (blur + borda de luz) flutuando sobre um fundo vivo
(`body::before/::after`: duas manchas de cor à deriva, só `transform`) **só no
tema Claro**. No Escuro/AMOLED as manchas foram removidas de propósito: ficavam
estranhas e o azul atrapalhava a leitura do texto — lá os painéis são quase
sólidos e o vidro fica nos cartões/modais/popups. Fonte: Nunito Sans.

- O bloco **"TEMA VIDRO" fica no FIM do `<style>`** de propósito: sobrescreve
  por ordem de declaração. Não mova pro meio nem quebre em vários.
- Superfícies de vidro usam `color-mix(in srgb, var(--bg-X) N%, transparent)`,
  então **seguem as variáveis** e os temas Claro/AMOLED continuam funcionando.
  Se um elemento novo precisa parecer vidro, repita esse padrão (não use
  `rgba` fixo).
- `.bazinga-toast` **não** entra na regra de borda `!important` dos modais:
  a borda colorida da esquerda é o que diferencia sucesso/erro/aviso.
- `position:relative` dos botões/cartões é via `:where()` (especificidade zero)
  pra não brigar com quem já define `position`. O ripple (`.ripple`) e o brilho
  que segue o mouse (`--mx/--my`, `::after`) são delegados no `document` — não
  precisa ligar nada em elemento novo, basta ter uma das classes da lista
  `SPOT`/`RIPPLE` no JS.
- Transição de aba (`vistaEntra`), `modalPop`, microinterações e
  `prefers-reduced-motion` (desliga tudo) estão no bloco "POLIMENTO GERAL".
  A entrada das abas é puro CSS e só usa opacity/translate com `backwards` —
  **não** deixe `transform` fixo num wrapper de aba, senão os `position:fixed`
  de dentro passam a se ancorar nele. O mapa (`#bazinga-map`) fica de fora de
  propósito (Leaflet usa transform).
- **Tema (Escuro/Claro/AMOLED) mora na conta** (`Person.tema`, evento
  `mudar_tema`), igual ao Modo Fantasma. O valor vem em `<html data-tema>` e as
  paletas Claro/AMOLED existem também em CSS puro (primeiro paint sem piscar);
  `TEMAS`/`aplicarTema()` no JS cuidam da troca ao vivo. Mudou uma paleta,
  mude nos dois lugares.

## Nome, logo e moeda ("Panteão")

O app foi renomeado (Bazinga tem cara de marca de terceiro). **Uma constante só**:
`APP_NOME`, `MOEDA_NOME` (Dracmas) e `MOEDA_SIGLA` (DRC) em `app/__init__.py`,
injetadas em todo template como `{{ app_nome }}`/`{{ moeda_nome }}`/
`{{ moeda_sigla }}` (context processor) e usadas no manifesto do PWA. Trocar o
nome de novo = mudar ali (e, se o artigo importar, "no/do" nos textos).

- **Só o texto exibido mudou.** Identificadores internos ficam como estavam
  (`bazinga_coins`, `price_bzc`, `erro_bazinga`, `bazingaMap`, `bazinga-map`):
  renomear coluna de banco exigiria migração sem ganho nenhum.
- "Bazinga Awards" e "Ultimate Bazinga" (`base.html`/`index.html`) são outros
  produtos do dono e **não** foram renomeados.
- Logo: `app/static/img/logo.svg` (templo com um ponto de mapa no frontão).
  `icone-192.png`/`icone-512.png` são a mesma arte rasterizada (o manifesto do
  PWA precisa de PNG); se mexer no SVG, refaça os PNGs.

## Sistema de cartões (mesma linguagem do Battle Pass em todas as telas)

Bloco "SISTEMA DE CARTÕES" no fim do `<style>`: anel de gradiente girando
(`.cartao-anel`), títulos de seção com filete, sidebar/DMs/Mercado/Radar/
Configurações com entrada escalonada, hover com brilho que segue o mouse e
estados ativos com barra de acento.

- **`.cartao-anel` usa pseudo-elemento com máscara**, não fundo em camadas: com
  fundo em camadas o arco-íris vazava por dentro do cartão translúcido.
- **`animation-fill-mode: both` em entrada de cartão é bug**: segura o último
  keyframe (`opacity: 1`) e anula qualquer `opacity` de estado (`.bloqueado`).
  Use `backwards`.
- O `#radar-header` tem `style` inline; a versão de vidro usa `!important`.
- Listas injetadas por JS (`.market-grid`, `#dm-list-container`) ganham o
  escalonamento por `nth-child` (até 12); a partir daí todos entram juntos.

## Servidores da barra lateral vêm no HTML

`carregar_meus_servidores` só chegava pelo socket, então com Render/Neon
"acordando" a barra ficava vazia por segundos e parecia que os servidores
tinham sumido. Agora `/chat` já manda `servidores_iniciais` e o cliente desenha
na hora (`aplicarMeusServidores` em `setTimeout 0`, porque várias variáveis
`let` usadas por `entrarNoServidor()` só existem depois do script inteiro ser
avaliado); o socket reenvia e reconcilia.

## Cartão de perfil, "Meu Perfil" e status de presença

**Um renderizador só** (`htmlCartao(pf, modo)` em `chat.html`) desenha o cartão do
popup (quem você clica) e a pré-visualização do editor — o que você vê editando é
o que os outros veem. Popup: `abrirCartao(id, ancora)` / `fecharCartao()`; o
clique é **delegado** (`[data-perfil-id]` em qualquer elemento + avatar/nome de
mensagem via `data-autor-id`), então vale pro que for desenhado depois.

- **Meu cartão** vem do estado local `perfilMeu` (abre na hora, sem rede). **O de
  outra pessoa** vem de `obter_perfil`: o servidor só entrega bio/status/faixa
  pra quem **convive** (servidor em comum ou amizade); senão devolve só nome e
  foto com `restrito: true`. Nunca exponha e-mail no cartão dos outros.
- Ações do cartão alheio: Mensagem (amigo → DM; senão DM temporária), loja
  (só se a pessoa vende no Bazar → abre Mercado > Bazar), ⋯ (copiar ID,
  adicionar/desfazer amizade). Adicionar amigo manda `usuario_id` (exato — o
  pedido por nome/e-mail ambíguo não serve aqui).
- **Configurações**: "Minha Conta" e "Perfis" viraram **uma aba só, "Meu Perfil"**
  (nome de exibição, pronomes, avatar, faixa em cor/animada/**imagem**, status de
  presença, status personalizado, bio, e o bloco Conta: e-mail, ID, membro desde,
  nível, sair). Edição usa **rascunho + barra "alterações não salvas"**; avatar e
  presença aplicam na hora (não entram no rascunho). `perfil_atualizado` **não
  atropela** campo que a pessoa está editando.
- Campos novos em `Person`: `pronomes`, `banner_url` (migração em
  `atualizar_banco.py`, passo 18). `banner_url` só aceita caminho do site ou
  Cloudinary; `banner_color` só `#rrggbb` (a string vai parar num `style=""` no
  navegador de todo mundo).

**Status de presença (online/ausente/não perturbar/invisível) vale em todo lugar**
(regra 6). `mudar_status` antes só salvava no banco. Agora:
`meu_status_mudou` → minhas outras abas (status real); `status_visivel_mudou` →
servidores e amigos (**Invisível chega como `offline`**, por `status_visivel()`).
`connect` não anuncia "ficou online" quem está invisível; `listar_membros_servidor`
e o snapshot de amigos também mascaram. `aplicarMeuStatus()` atualiza barra
inferior, cartão, editor, lista de membros e o item da sidebar numa função só.

### Perfil v2: dois nomes, enfeites, mídia e status personalizado

- **Dois nomes.** `Person.name` = nome de **exibição** (enfeitável, pode repetir).
  `Person.username` = nome da **conta** (@, único, `[a-z0-9_.]{3,32}`): é o que se
  digita pra adicionar alguém (`enviar_pedido_amizade` aceita `@username`, nome ou
  e-mail). Conta antiga ganha `@` automático em `garantir_username()` (chamado no
  `/chat`). `@` inválido/repetido só gera toast de erro — o resto do perfil salva.
- **"Pensando agora" e Status são coisas separadas.**
  `Person.pensando` = o **balão** ao lado da foto (texto livre). O **status** é a
  presença (`online/idle/dnd/invisible/custom`); no modo `custom` valem
  `status_emoji` (o emoji **substitui a bolinha**: `htmlBolinha()`/`aplicarBolinha()`;
  sem emoji cai no verde) e `custom_status` (o **texto** do status, ex.: "Jogando
  Valorant", que ocupa o lugar de "Disponível"). `custom` conta como "disponível" no
  filtro de amigos. Emoji e texto vão junto em todo payload de presença
  (`emoji`/`texto`), não só o status. Na migração, quem tinha texto no balão
  (antes `custom_status`) teve o texto **copiado** pra `pensando` (uma vez só).
- **Subtítulo nas listas** (DMs e membros): `subPresenca()` = `pensando` se houver;
  senão o rótulo do status (texto do Personalizado ou Disponível/Ausente/...);
  offline sem pensando não mostra nada. Nos cartões de DM vive em `data-pensando` /
  `data-status-texto` + `atualizarSubDM()`.
- **Enfeites** (ids validados em `utils.ESTILOS_NOME/PLACAS/MOLDURAS`, **têm que bater
  com o catálogo do JS e o CSS `.ne-*`/`.placa-*`/`.moldura-*`** — o servidor nunca
  guarda texto livre que vire `class=""`):
  estilo de nome (`nome_estilo`), **placa** (barrinha atrás do nome na lista de
  membros, DMs e barra inferior), **moldura** (anel animado no avatar, via `::before`
  com máscara + `bpGira`) e **tema do cartão** (`perfil_tema`: `grad:#a,#b` |
  `solid:#a` | `img:<url>`, validado por `tema_perfil_valido`). "Efeitos de perfil"
  são cartões **Em breve** (vão ser desbloqueados por Battle Pass/loja).
  "Surpreenda-me" sorteia estilo/placa/moldura/tema **no rascunho** (dá pra descartar).
- **URLs de imagem** (avatar, faixa, tema): só caminho do site, Cloudinary ou Giphy
  (`url_de_imagem_ok`). Antes o avatar só barrava `blob:` e aceitava qualquer host.
- **Seletor de mídia** (`abrirSeletorMidia`): avatar, faixa e tema usam o mesmo modal —
  enviar arquivo/arrastar + sugestões de GIF (`/api/gifs`, Giphy). Escolher uma
  sugestão abre o editor **como se tivesse sido enviada** (`urlRemota`; GIF não corta,
  vai inteiro e fica hospedado no Giphy). Pinterest e similares **não** têm busca
  liberada pra apps de terceiros — a saída é salvar a imagem e enviar.
- **Editor de imagem** ganhou formato `faixa` (340×108 de preview, 1360×432 de saída):
  a área de corte agora é largura×altura (`PW/PH/SW/SH`), não mais um quadrado fixo.
  A proporção do preview e da saída tem que ser a mesma ("o que vejo é o que sai").
- A foto do avatar **é o botão** (sem botão extra); a faixa é um retângulo só que abre
  cor sólida / **faixas animadas** / imagem / sugestões. A moldura é só o quadradinho
  ao lado da foto (sem texto — "quebrava a vibe").
- **Faixas animadas** = `banner_color` com `anim:<id>` (ids em `utils.FAIXAS_ANIMADAS`,
  11 opções incluindo o arco-íris padrão, que é o valor **vazio**). O CSS é
  `.banner-anim-<id>` (mesmo padrão `bg-spin` da faixa antiga). **Criar faixa nova =**
  id em `FAIXAS_ANIMADAS` + `.banner-anim-<id>` no CSS + item em `FAIXAS_ANIM` no JS.
  O servidor só aceita `#rrggbb` ou `anim:<id conhecido>`. **A faixa animada do modal
  ficava invisível** porque a classe só tinha CSS em `.pc-banner`/`.npc-banner` — todo
  lugar novo que use `banner-animado`/`banner-anim-*` precisa de tamanho e fundo próprios.
- **z-index do avatar do cartão**: o anel da moldura (`::before`) fica em `0`, a foto em
  `1` e a bolinha/emoji de presença em `3`. Antes o anel cobria a bolinha.
- Dead code: o modal antigo `#avatar-upload-modal` e seu input continuam no HTML (um
  listener ainda referencia o input) mas nada o abre mais.

### Menções (@) no chat

- No texto enviado a menção é **`<@id>`** (estável: o nome de exibição muda e a
  mensagem continua certa). Na tela vira o **nome de exibição** em destaque,
  clicável (abre o cartão) — `htmlTexto()` faz a troca sobre o texto **já escapado**
  (`&lt;@id&gt;`). `atualizarMencoes()` corrige o nome quando a lista de membros
  chega depois da mensagem.
- `data-texto` no `.message` guarda o texto **bruto**: editar/copiar usam ele (senão a
  menção viraria texto solto). Edição mostra `@Nome` e reconverte ao salvar.
- Autocomplete no `#message-input`: `@` + parte do nome de exibição ou do `@conta`
  (só membros do servidor ativo, online primeiro). O `@Nome` escolhido fica em
  `mencoesPendentes` e vira `<@id>` no envio (`converterMencoes`); `@usuario`
  digitado à mão também resolve. **Só canais** (DM não tem menção ainda).
- Servidor: `_notificar_mencoes()` avisa (`mencao_recebida`) só quem é **membro do
  servidor E enxerga o canal** — citar não vaza canal privado. Falha aqui nunca
  quebra o envio. Mensagem que cita você ganha `.mencionando-me` (faixa amarela).

**Emoji do Twemoji precisa de `img.emoji`** (1.2em): sem essa regra o `<img>` vinha
em ~109px e estourava qualquer linha (barra do usuário, status, mensagens).

Pendência: o CSS antigo do popup (`.popout-*`, `.nitro-preview-card`, `.npc-*`,
`.account-*`) ficou sem uso — pode ser removido numa limpeza.

## Mensagens fixadas

`Message.is_pinned` (coluna nova, precisa de `atualizar_banco.py`). Fixar é
um alternar (`fixar_mensagem` inverte o valor atual) disparado pelo item
"Fixar mensagem" no menu de contexto da mensagem; qualquer um que veja o
canal pode fixar (mesma checagem de `pode_ver_canal`, não é exclusivo do
dono). O ícone de pin no header do canal abre `#painel-fixadas`, que pede
`listar_fixadas` e mostra a lista com botão de desfixar cada uma. A
mensagem fixada ganha um destaque visual (`.message.fixada`, borda amarela)
direto na conversa, sem precisar abrir o painel pra saber que ela existe.

## Busca rápida (Ctrl+K)

Existia só o badge visual "Ctrl K" do lado da busca — sem atalho de teclado
e sem busca nenhuma por trás. Hoje `Ctrl/Cmd+K` (ou clicar na barra) abre
`#quick-switcher`, que filtra ao digitar por cima de três fontes já
carregadas no cliente (sem round-trip novo ao servidor): `meUserServers`,
os canais do servidor ativo, e os `.user-dm-item` da sidebar de DMs.
Clicar num resultado navega direto pra lá.

## Gravar e clipar a call

Botão único (`btn-main-clip`, ícone de claquete) virou um popup com duas
ações: **Gravar** (roxo, grava a call inteira) e **Clipar** (laranja,
últimos ~30s). O ícone muda de cor conforme o que está ativo — metade roxo,
metade laranja quando os dois ao mesmo tempo.

- `criarCompositor(altura)` desenha num `<canvas>` (via `requestAnimationFrame`)
  a grade de todo mundo na call e mistura o áudio de todo mundo (local +
  remoto) num único `AudioContext`/`MediaStreamDestination` — é esse
  `MediaStream` combinado que o `MediaRecorder` grava, não os `<video>`
  separados.
- **Gravar**: pede pasta via `window.showDirectoryPicker()` (Chrome/Edge;
  sem suporte, cai pra gravar em memória e baixar no final) e escreve os
  chunks incrementalmente (`FileSystemWritableFileStream`), pra não estourar
  memória em calls longas.
- **Clipar**: um segmento de ~30s roda sempre em background durante a call
  (`iniciarBufferClipe`/`abrirNovoSegmentoBuffer`) — quando fecha, vira "o
  último clipe pronto" e um novo começa. Automático liga por um switch e usa
  uma **heurística** (não IA de verdade — o projeto não tem infra pra isso):
  dispara quando 2+ pessoas ficam com `.is-speaking` ao mesmo tempo por
  alguns segundos seguidos.
- `criarCompositor(altura, fpsDesenho)` ganhou um segundo parâmetro: o
  buffer de clipe (sempre rodando, ninguém assiste em tempo real) desenha a
  só 15fps; "Gravar" manual continua em 30fps. Antes desenhava no ritmo do
  `requestAnimationFrame` da tela (60fps, às vezes mais) o tempo todo só
  pra manter esse buffer "quente" — o maior custo de CPU/GPU de uma call
  com tela compartilhada.

**O bug (descoberto testando)**: a primeira versão tentava simular um
buffer circular real concatenando os `Blob`s de várias sessões curtas do
`MediaRecorder` (`new Blob([...blobs])`). Isso **não funciona** — cada
`start()`/`stop()` gera seu próprio cabeçalho Matroska, e colar vários um
atrás do outro produz um arquivo onde só o **primeiro pedaço** toca. A
correção foi trocar por um único segmento contínuo de ~30s por vez (com
`timeslice` só quando precisa dos chunks parciais antes do `stop()`); ao
fechar, vira o clipe pronto, e um novo começa. Qualquer ideia futura de
"buffer circular" de vídeo no navegador esbarra nesse mesmo limite.

A tela de edição do clipe só ajusta a prévia (não recodifica o arquivo —
cortar de verdade um webm no navegador sem servidor precisaria de algo como
ffmpeg.wasm, fora de escopo por ora).

## Prévia de quem já está numa call

Antes, só descobria quem estava numa call **entrando nela** — quem tinha o
servidor aberto mas não tinha entrado não via nada, e o próprio `entrar_
call` só avisa quem **já está na sala** (`novo_usuario_call`, `to=sala_
call`), então quem chega não sabe quem tem lá até cada peer chamar de volta.

- `participantes_call` (dicionário em memória, `events.py`, igual em
  espírito ao `usuarios_conectados`) guarda quem está em cada call, com
  `peer_id`/`usuario_id`/`nome`/`avatar`.
- `entrar_call`/`sair_call` emitem `participantes_call_mudou` pra
  `sala_servidor` inteira (não só pra `sala_call`) — é isso que dá a prévia
  tipo Discord (avatares embaixo do canal de voz) pra quem não entrou ainda.
- `listar_participantes_call` é a versão "sob demanda", chamada ao abrir um
  servidor (`entrarNoServidor` pede pra cada canal de voz).
- `handle_disconnect` limpa a entrada mesmo se a conexão cair sem passar
  por `sair_call` (queda de rede não dispara o `beforeunload` do
  navegador) — usa `_call_por_sid` (sid → canal/peer) pra saber o que
  limpar.
- No frontend, o listener de `participantes_call_mudou` **não mexe** na UI
  de quem já está na call ativa (`inCall && currentVoiceChannelId ===
  dados.canal_id`) — só serve pra quem está de fora olhando. A UI de quem
  está dentro continua 100% no fluxo antigo (`novo_usuario_call`/
  `usuario_saiu_call`), pra não arriscar duplicar/piscar a lista ao vivo.

## Qualidade de câmera/tela automática (sem escolha manual)

Existia um modal pra escolher resolução/fps antes de compartilhar a tela —
virou automático: teto fixo (720p/30fps, com `max` no `getDisplayMedia`,
não só `ideal` — sem isso o navegador podia negociar bem mais que o
pedido) e ajuste de bitrate ao vivo.

- `monitorarEAjustarBitrate(call, tipo)` mede a perda de pacote reportada
  pelo outro lado (RTCP, via `getStats()`) a cada 5s e sobe/desce um degrau
  de `maxBitrate` (`RTCRtpSender.setParameters`) — sem isso, uma conexão
  ruim de qualquer participante travava/engasgava a call pra ele **e** pra
  quem via ele do outro lado.
- Câmera (`getUserMedia`) ganhou teto também (640x480@24fps, antes era sem
  nenhum limite — o navegador podia pedir a resolução nativa da webcam).
- Isso reduz a dor de rede ruim, mas a call continua sendo **malha P2P**
  (cada participante manda a própria mídia pra cada outro direto, sem
  servidor de mídia no meio) — ver Pendências sobre migrar pra um SFU
  (LiveKit/mediasoup).

**O bug (CSS, achado testando foco + fala ao mesmo tempo)**: `.video-card.
focused` (`order: -10`) e `.video-card.is-speaking` (`order: -1`) têm a
mesma especificidade CSS; como `is-speaking` vem depois no arquivo, ele
ganhava sempre que os dois coexistiam — o card em foco saía/voltava do
topo toda vez que a pessoa focada falava (fala tem pausas naturais).
Corrigido com uma regra mais específica, `.video-card.focused.is-speaking
{ order: -10; }`, que não depende de ordem de declaração.

**Trocar de call parecia fechar uma feature e abrir outra**: `disconnect
Call()` escondia a tela de vídeo e mostrava o chat de texto por ~350ms
(esperando o peer antigo fechar de verdade antes de abrir o novo — isso
**não** é enfeite, sem essa espera o servidor de sinalização do PeerJS
recusa a conexão nova) antes de reconectar. Hoje um overlay
(`#call-switch-overlay`) fica por cima da própria tela de vídeo durante
essa espera, em vez de trocar de tela e voltar.

## Chamada de voz/vídeo 1-a-1 por DM

Os ícones de "Iniciar Chamada de Voz/Vídeo" existiam no header do canal de
**texto** do servidor e não tinham handler nenhum (nem fazia sentido ali —
servidor já tem canal de voz próprio). Removidos de lá e adicionados no
header da DM (`#dm-header-actions`, ícones de telefone/vídeo, só quando a
conversa é com um amigo de verdade, não uma DM temporária de 24h).

Fluxo, igual Discord (toca e espera, não entra direto):

1. `chamar_amigo` (checa `sao_amigos` antes de tocar) → `chamada_recebida`
   só pra sala pessoal do destinatário.
2. Quem recebe vê um modal com avatar, nome e Aceitar/Recusar — não é toast
   (não pode sumir sozinho enquanto a pessoa não responde).
3. `aceitar_chamada` → `chamada_aceita` pros dois lados, cada um com a
   mesma `sala` (`sala_dm()`, ver seção de Salas acima).
4. Os dois chamam `conectarNaCall(sala, nome)` — a **mesma** função que o
   clique num canal de voz usa. Foi extraída do antigo listener de clique
   de `initVoiceChannel()` justamente pra isso: reaproveitar 100% do PeerJS,
   compositor, mic/câmera e `disconnectCall()` sem duplicar nada.

`cancelar_chamada` (quem ligou desiste antes da resposta) e
`recusar_chamada` fecham os modais dos dois lados. Se a pessoa já está em
outra call/ligação quando o toque chega, o cliente recusa sozinho em vez de
tocar por cima.

## Mapa

O pino do servidor usa a foto real do servidor, e o nome/ícone vêm do
`Server` ligado — **não** da cópia feita na hora de plantar, senão renomear
o servidor não mudava nada no mapa.

O pino cai nas iniciais quando não há ícone **ou quando a imagem não
carrega** (`onerror`). Isso não é firula: a pasta de uploads é efêmera, então
uma foto enviada antes pode ter sumido do disco — sem o fallback sobrava só
o quadrado colorido do fundo, que era o "a imagem não aparece no mapa".

**Dois bugs de identidade/corrida no radar de amigos**
(`posicao_amigo_atualizada`):
- Logado na mesma conta em duas abas/dispositivos, a própria posição
  ecoava de volta e virava um pino de "amigo" fantasma sobre o próprio
  usuário — `include_self=False` só exclui o socket que emitiu, não os
  outros sockets da mesma pessoa. Corrigido no cliente: ignora o evento
  quando `usuario_id === currentUserId`.
- O mapa (`bazingaMap`) inicializa ~200ms depois do resto da página
  (`setTimeout(initMap, 200)`); um ping de posição chegando antes disso
  fazia `L.marker(...).addTo(null)` estourar — o marcador do amigo nunca
  era criado, e o próximo ping também não corrigia porque a exceção
  acontecia antes de guardar em `mapMarkers[id]`. Guarda simples
  (`if (!bazingaMap) return`) resolve — o próximo ping (real, a cada
  movimento) recria o marcador normalmente.

## Reações e densidade do chat

A linha de reações nasce **vazia** quando não há reação nenhuma e some via
`.msg-reacoes:empty { display: none }`.

**O bug**: quando ela sempre trazia o botão de "+", toda mensagem ganhava
~20px invisíveis de altura, e o chat ficava com aquele espaçamento estranho
(46px entre linhas agrupadas, contra 24px hoje). O "+" continua acessível
pela barra de hover.

---


# Rodada de 01/10/2026 — social, mapa por raio e velocidade

Saiu do teste com duas pessoas (filippo + aquele sales). **Mercado e Battle Pass/nível
ficaram de fora de propósito** (o dono vai refazer economia, loja e bazar depois).
Scripts de fumaça desta rodada: `testes/` (ver seção "Testes").

## Velocidade: o que pesava e foi cortado

Cada query é uma ida ao Neon. Medido com `testes/contar_queries.py` (banco realista, 5
servidores x 20 membros): `/chat` 22→9, conexão do socket 46→11 (reconexão; 24 na 1ª do
dia, que cria as missões), `enviar_mensagem` 20→8, `entrar_canal` 5→3.

- `db = SQLAlchemy(session_options={'expire_on_commit': False})` (`models.py`). Por padrão
  o SQLAlchemy esquece tudo a cada commit e relê a pessoa a cada acesso. **Cuidado**: depois
  de um `commit()` os objetos *não* são recarregados sozinhos — se precisar do valor que o
  banco calculou, use `db.session.refresh(obj)`.
- `Server.members` e `Channel.allowed_members` eram `lazy='subquery'`: **toda** vez que um
  `Server` carregava, vinham junto todas as linhas de todos os membros. Agora `lazy='select'`.
  Para "essa pessoa é membro?" use `eh_membro(usuario, server_id)` (EXISTS), não
  `usuario in srv.members`.
- `servidores_para_json(lista, usuario)` monta todos os servidores com 3 queries (canais,
  quem vê canal privado, contagem de membros). `servidor_para_json` virou atalho dele.
  `avisar_servidor` calcula os canais uma vez e filtra por membro.
- `/api/mensagens/<id>` e `/api/dms/<id>` devolviam as **50 mais antigas** (`asc` + `limit`),
  então canal com mais de 50 mensagens "perdia" as novas ao sair e voltar. Agora são as 50
  mais recentes e aceitam `?antes=<id>` (o cliente pagina ao rolar pro topo).
- PeerJS e qrcodejs não bloqueiam mais o `<head>`: `carregarLib(url)` baixa sob demanda e
  pré-aquece quando o navegador está ocioso. `preconnect` nos CDNs.
- Cloudinary: `urlOtimizada()` pede `f_auto,q_auto,w_900` pra foto (GIF e links de fora
  ficam como estão); mensagem que acabou de chegar carrega na hora (sem `lazy`) com
  esqueleto, e a rolagem acompanha a foto que termina de carregar.
- **Reconexão** (`connect` no cliente): o socket que cai perde a sala do canal e as mensagens
  paravam de chegar até F5. Agora reentra no canal/DM, busca o que faltou e mostra a pílula
  "Reconectando...". O servidor também manda `receber_mensagem` direto pro autor (o cliente
  ignora a repetição pelo id).

## Migração automática de coluna (rede de segurança da regra 1)

`adicionar_colunas_que_faltam()` (`app/__init__.py`) roda no boot e faz `ADD COLUMN` pra
toda coluna do modelo que o banco ainda não tem. Só adiciona, **sem NOT NULL/DEFAULT** —
por isso o código trata `None` como falso/vazio nas colunas novas (`lida`, `oculta`).
`atualizar_banco.py` continua valendo pra dados e índices. Coluna nova ainda deve ir nos
dois (modelo + `atualizar_banco.py`).

Colunas/tabelas novas: `person.banner_ajuste`, `direct_message.attachment_url/type/name/lida`,
`geo_note.icone/oculta`, `map_server.oculta`, tabelas `denuncia` e `notificacao`.
`direct_message.content` grava `''` (não `None`) quando é só anexo — o Neon pode ter a
coluna `NOT NULL`.

## Amizade (refeita)

- `Friendship.status`: `pending` (vale 24h a partir de `created_at`), `accepted`, `blocked`
  (**quem bloqueou é o `requester_id`**). `relacao_entre(a, b)`, `pedido_expirou()`,
  `limpar_pedidos_expirados()` em `events.py`.
- Quem **envia** vê a pessoa na lista de DMs como "Aguardando resposta" e só pode
  **cancelar**; quem **recebe** vê "Aceitar?" e, na DM, os botões Aceitar / Recusar /
  Bloquear. Pedir de volta pra quem já pediu = aceita. Bloqueado não revela que foi bloqueado.
- **Uma fonte da verdade**: `emitir_amizades(pessoa_id)` manda o evento `amizades`
  (`amigos`, `pedidos`, `bloqueados`) pras abas da pessoa — nas duas pontas, a cada mudança, e
  no `connect`. O cliente (`reconciliarAmizades()`) acerta lista de DMs, selos, contadores e a
  tela de Amigos a partir dele.
- Eventos: `listar_amizades`, `enviar_pedido_amizade`, `responder_pedido_amizade`
  (`acao`: aceitar/recusar/bloquear), `cancelar_pedido_amizade`, `remover_amigo`,
  `bloquear_usuario`, `desbloquear_usuario`.
- **Tela de Amigos** (`#amigos-view`, item "Amigos" na sidebar com badge): abas Disponível ·
  Todos · Pendente · Bloqueados e o botão verde "Adicionar amigo". Substitui os filtros
  "Disponível/Todos" da sidebar (que só filtravam a lista de DMs).
- `pode_trocar_dm()`: DM só entre amigos, pedido pendente, quem divide servidor, ou a si
  mesmo. Antes qualquer pessoa mandava DM pra qualquer id.
- **Presença**: `presencaPorId` (cliente) é a única fonte; `atualizarStatusAmigo()` e o
  retrato `amizades` a alimentam, e `presencaMudou()` repinta lista, cabeçalho da DM e tela
  de Amigos. O ponto do cabeçalho da DM antes era calculado só ao abrir a conversa.
- **Anotações** (`#dm-me`): ícone de marcador próprio e "Só você vê" (antes usava a foto da
  pessoa e parecia outro contato). Continua sendo uma DM para si mesma.

## DM

- Compositor novo: enviar (aparece ao digitar), emoji, GIF (mesmo painel do canal, via
  `gifDestino`), foto/vídeo por "+", colar e arrastar. Bolha otimista com `temp_id`.
- `DirectMessage.lida` + `dms_nao_lidas` (ao conectar) + `marcar_dm_lida` + `dm_lidas`
  (sincroniza as outras abas). `lida IS NULL` = mensagem antiga = já lida.
- Conversa rápida (alguém do mesmo servidor, sem amizade): cartão tracejado "Conversa
  rápida" com botão Adicionar amigo no cabeçalho.
- O cabeçalho do Radar voltava com os ícones de ligar da última DM (`switchMainView('home')`
  não resetava). Agora reseta pra caixa de entrada.

## Caixa de entrada + som

- `Notificacao` (`dm` agregada por remetente com contador, `amizade`, `mencao`).
  Eventos: `notificacoes`, `notificacao_nova`, `listar/marcar_notificacoes_lidas`,
  `limpar_notificacoes`. `criar_notificacao()` nunca derruba quem chamou.
- `notificacao_nova` só atualiza a caixa; **toast e som saem dos eventos específicos**
  (`receber_mensagem_direta`, `pedido_amizade_recebido`, `mencao_recebida`) pra não tocar duas
  vezes. Som sintetizado com Web Audio (`tocarSom('msg'|'amizade'|'mencao')`), calado em "Não
  perturbar" e desligável no sino (guarda em `localStorage`, é conveniência de UI). Número
  nas abas do navegador "(3) Panteão" e aviso nativo com a aba em segundo plano.

## Mapa por raio (privacidade)

- Constantes em `utils.py`: `RAIO_NOTAS_M = 2000`, `RAIO_SERVIDORES_M = 15000`,
  `MAX_NOTAS_ATIVAS_POR_PESSOA = 20`, `DENUNCIAS_PARA_OCULTAR = 3`. O servidor manda esses
  valores ao cliente (mexeu aqui, vale lá).
- Só chega ao navegador o que está no raio de quem olha: `mapa_pedir_arredores` →
  `mapa_arredores`; `dados_do_mapa_perto()` filtra por caixa + haversine, ignora expiradas
  (`expires_at`) e ocultas. `/api/mapa/dados?lat=&lng=` usa a mesma função (sem posição, vazio).
- `centros_mapa` (sid → posição, em memória) decide quem recebe cada aviso ao vivo
  (`_emitir_perto`). Nunca é repassado e vale no Modo Fantasma também (só filtra). Criar
  nota/servidor fora do alcance é recusado no servidor.
- **Bug das notas que nunca sumiam**: o cliente nunca mandava `duracao` em `criar_geonote`,
  então `expires_at` ficava `None`. Agora manda (1h / 1 dia / 7 dias) e a nota some do mapa
  no prazo (`restante_s` no payload; o cliente remove sozinho).
- Cliente: ondas saindo de você (`.raio-onda`, CSS puro, tamanho recalculado por zoom),
  círculo do raio das notas e dos servidores, rolagem presa (`setMaxBounds` + `minZoom 12`).
- Nota: o emoji do modal é o **ícone do balão** (`GeoNote.icone`), não entra no texto. Abre
  sozinha 5s ao chegar no alcance ou quando você chega a <100 m, tem X vermelho pra
  minimizar, abre no hover e fecha ao tirar o mouse; clique no balão fixa aberto.
- **Copiar nota** (`copiar_geonote`) cria uma nota nova sua no seu alcance, com a mesma
  duração — não copia link nem texto (a seleção do texto fica bloqueada).
- **Denunciar** nota/servidor (`denunciar` → `Denuncia`, motivos em `MOTIVOS_DENUNCIA`).
  3 denúncias de pessoas diferentes marcam `oculta=True` e tiram do mapa de todo mundo; quem
  denuncia deixa de ver na hora. Ainda **não existe tela de revisão** (ver Pendências).
- Painel do pino de servidor refeito (`.bsv-*`): capa na cor do servidor, foto sobreposta,
  membros/vagas, Entrar, Editar/Tirar do mapa (dono) ou Denunciar.

## Perfil

- Salvar faixa: o servidor só aceitava URL do site/Cloudinary, então **GIF escolhido nas
  sugestões (Giphy) era descartado em silêncio** e a faixa "não salvava". Agora usa
  `url_de_imagem_ok` (site, Cloudinary ou Giphy).
- **GIF com enquadramento**: *(superado na Rodada 2 - ver "GIF/animação: o servidor recorta")*.
  Na rodada 1 o GIF era enquadrado por CSS (`Person.banner_ajuste`, `img:<url>|<ajuste>`); esses dados
  antigos ainda são lidos e desenhados (`camadaGif()`/`temaCamadaHtml()`), mas o editor agora manda o
  GIF pro servidor recortar. Novo formato de editor `painel` (retrato) pro fundo do cartão.
- X de fechar e ESC ficam fora da área que rola; barra de rolagem estilizada; "+" ao passar o
  mouse na foto e na faixa; cartão mais redondo.

## Emoji completo

`emoji-picker-element` (CDN) com os dados **em português e Emoji 17** servidos por
`/static/emoji/pt.json`, gerado por `gerar_emoji.py` (baixa `emojibase-data@latest/pt` e
converte `label`→`annotation`; `emoticon` tem que ser texto, não lista). Rode de novo
quando sair Unicode novo. `abrirEmojiPicker(botão, input|callback)` mantém a assinatura de
sempre (chat, DM, status, nota, evento, reações com "+"); sem a biblioteca, cai no painel
pequeno antigo. Shift+clique mantém aberto.

## Mensagens: pequenos acertos

- Agrupamento por **id do autor** (antes por nome: dois "Filippo" ou nome trocado no meio se
  juntavam sob o mesmo cabeçalho).
- Os 3 pontinhos da mensagem abriam e fechavam no mesmo clique (dois `click` no `document`;
  `stopPropagation` não impede o irmão).
- `receber_mensagem` leva `canal_id`; o cliente ignora o que é de outro canal.

## Testes (`testes/`)

Sem framework; rodar da raiz com o venv. Banco SQLite em memória, `socketio.test_client`.

```bash
python testes/fumaca_social.py     # amizade, bloqueio, 24h, DM/anexo, mapa por raio, denúncia, perfil
python testes/fumaca_servidor.py   # servidor, convite, canal privado, paginação, expulsão
python testes/fumaca_conversa_rapida.py  # conversa rápida, nome repetido, silenciar, denunciar pessoa, notas antigas, recorte de GIF
python testes/fumaca_rodada3.py    # convite por membro, posição/notas de amigos, câmera, ornamentos, limites
python testes/contar_queries.py    # quantas queries cada carga faz (use antes/depois de mexer em performance)
python testes/fumaca_call.py       # uma call por pessoa, graça no disconnect, reentrada, ligação por DM (aba certa), versão do app
python testes/fumaca_cosmeticos.py # curva de nível, patentes, catálogo, posse, equipar, efeito de servidor
python testes/fumaca_localizacao.py  # localização na conta, travas do mapa, IP
python testes/fumaca_resposta.py   # responder mensagem (canal e DM)
python testes/fumaca_push.py       # notificações push (chaves, inscrição, quem recebe)
python testes/fumaca_insignias.py  # Beta pra todos, BAZINGA por servidor, Alpha por nome
python testes/fumaca_bazar.py      # Bazar: Pix copia e cola, loja/produto, pedido (estados), privacidade da chave Pix, estoque, avaliação, denúncia+moderação, corrida
python testes/fumaca_loja.py       # Armazém: compra atômica, livro-razão, pacote com abatimento, saldo velho, clique duplo, regra 6, extrato, todo tema tem CSS/arte/slide
python testes/fumaca_economia.py   # missão paga DRC, relíquia da semana, edições limitadas, coleção, id/CSS/JS de todo item do catálogo
python testes/calibrar_precos.py   # NÃO é teste de banco: conta quanto DRC cada perfil junta e checa as "regras de ouro" dos preços (sai com 1 se quebrar)
```
Rode **todos** antes de commitar (um comando encadeado com `;`/`&&` não para na falha: confira a última linha de cada).

---


## Rodada 2 de 01/10/2026 — feedback do teste da rodada 1

### Conversa rápida (mensagem pra desconhecido) — o modelo
- 1ª mensagem pra quem **não é amigo** (e divide servidor) cria um `Friendship` `pending` com
  `rapida=True`. Mesma máquina do pedido de amizade (24h, Aceitar/Recusar/Bloquear), só que com
  mensagens **temporárias**: quando o pedido expira, `limpar_pedidos_expirados()` apaga a linha
  **e as `DirectMessage` entre os dois**.
- **Cada ponta fecha só do seu lado**: `Friendship.oculta_req` (quem puxou) / `oculta_dest` (quem
  recebeu). Fechar/recusar uma conversa rápida só esconde pra você — a outra pessoa continua
  vendo e lendo (sem saber que foi recusada) até as 24h. Quem recusou **não recebe mais nada**
  (nem aviso) e quem escreve pra uma conversa que fechou a faz reaparecer pra si.
- Quem **puxou** a conversa nunca "bloqueia" (o botão era Bloquear, estranho): tem
  **Adicionar amigo** (vira pedido de verdade) e **Fechar conversa**. Quem **recebeu** tem
  Adicionar amigo / Recusar / Bloquear.
- Se quem puxou já tinha **fechado** e o outro clica em Adicionar amigo, o pedido **volta** pra
  quem fechou (`requester`/`addressee` trocam, `created_at` reinicia, histórico fica) e é ele quem
  decide aceitar, recusar ou bloquear (`_aceitar_pedido`).
- Cliente: o cartão da DM e o cabeçalho têm estados `recebido`, `enviado`, `recebido-rapida`,
  `enviado-rapida`, `rapida` (ainda sem mensagem, sem linha no banco), `amigo`, `notas`
  (`nomeEstadoDoCartao`/`pintarCabecalhoDM`). O mesmo vale pra conversa iniciada no mapa.
- **Nome de exibição repetido**: `enviar_pedido_amizade` resolve por `@conta` ou e-mail (únicos).
  Por nome, se houver mais de uma pessoa, **recusa e lista os `@`** em vez de escolher uma.

### Tela de Amigos v2 (simples)
Sem abas ao estilo Discord: **Todos | Online** + busca + botão "+ Adicionar". Pedidos e
conversas rápidas aparecem **em cima** só quando existem; amigos em cartões (online primeiro,
offline esmaecido, ações no hover); **Bloqueados** num `<details>` discreto no fim.
O filtro escolhido fica no `localStorage` (conveniência de UI).

### Menu do contato (clique-direito na DM, ⋮ do cabeçalho e dos cartões)
Ver perfil · Enviar mensagem · Copiar ID · Copiar @usuário · **Silenciar** (`Silenciado`, mora na
conta; mensagem chega mas sem som/toast/badge/caixa de entrada) · **Convidar para um servidor
meu** (cria convite de 1 uso/24h e manda o link na DM) · **Denunciar** pessoa (`Denuncia` com
`tipo='usuario'`: só registra, não esconde) · Desfazer amizade · Bloquear.
O ⋮ do cabeçalho "não funcionava": o clique subia até o `document`, cujo listener fecha o menu
no mesmo instante. Ligar quando já está numa call agora pergunta antes de sair
(`ligarPara()`), em vez de só mostrar um toast.
**Anotações** moram em `#dm-me` (não `#dm-<meu id>`): `cartaoDaDM(id)` resolve isso. Antes o
cabeçalho não repintava e mostrava a conversa anterior (com botões de ligar).

### GIF/animação: o servidor recorta (Pillow)
O canvas do navegador só pega 1 quadro, então **todo GIF** (foto, ícone de servidor, faixa, fundo
do cartão) passa por `POST /api/gif/recortar`: o editor mostra a animação num `<img>` (arrastar,
zoom, espelhar; **girar só em foto parada**) e, ao confirmar, manda arquivo (ou link do Giphy —
só esse CDN, anti-SSRF) + `formato`/`escala`/`ox`/`oy`/`fh`/`fv`. `recortar_animacao()` (utils)
faz a mesma conta do editor de foto parada e devolve **WebP animado** (25 KB de GIF → ~2 KB), que
segue pelo upload normal (`File.animado = true` pula a compressão por canvas). Formatos em
`FORMATOS_ANIMADOS`. Máx. ~90 quadros, 10 MB, 1 recorte a cada 1,5 s por pessoa.
**Pillow entrou no `requirements.txt`.** `Person.banner_ajuste` e `img:<url>|<ajuste>` (CSS)
continuam sendo **lidos** (dados antigos), mas o editor não os gera mais.
**Vídeo como foto/faixa não existe** (cortar vídeo exigiria ffmpeg no servidor).

### Mapa: ajustes
- Nota **não abre mais no hover** (virava um quadrado quebrado): abre por **clique** ou **sozinha
  5 s** ao entrar no alcance/chegar perto; o X vermelho fecha. Card em retângulo (232–320 px) com
  o "expira em..." inteiro.
- **Copiar nota** agora é "escolha o ponto": entra em `plantingMode = 'copia'`, clique **dentro do
  círculo azul** (Esc cancela); o servidor revalida o alcance.
- Nota antiga **sem prazo** (criada antes da duração valer) só vale 24h desde que nasceu
  (`dados_do_mapa_perto` + `nota_para_json`), e `atualizar_banco.py` apaga as com mais de 1 dia.

### Vídeo (mp4/webm/mov) como foto, ícone, faixa e fundo — sem ffmpeg
O navegador decodifica o vídeo (`videoParaAnimacao()` em `chat.html`, logo antes de `abrirEditorImagem`):
tira ~12 quadros/s num `<canvas>` (só os **primeiros 6 s**, lado máx. 480px, 640px em faixa/fundo) e manda os
JPEGs pra `POST /api/video/animar`; o servidor só junta com o Pillow (`animar_quadros()` em utils.py) e
devolve um **WebP animado**. Esse arquivo (`File.animado = true`) entra no **mesmo editor de GIF**
(arrastar/zoom/espelhar) e no mesmo `/api/gif/recortar`. Não existe ffmpeg em lugar nenhum: o Render free
só gasta CPU montando ~70 quadros pequenos (1 conversão a cada 3 s por pessoa).
- `abrirEditorImagem()` aceita `video/*` direto, então avatar, ícone de servidor (criar/editar), faixa e fundo
  funcionam sem mudar quem chama — bastou liberar `video/*` no `accept` dos inputs.
- Limites: vídeo de até 80 MB (lido no navegador, não sobe), formato que o **navegador** decodifica (mp4 H.264,
  webm, mov em geral); HEVC/MOV exótico pode falhar com toast claro. Sem áudio, sem escolher trecho (só o começo).
- **Teto de upload por rota**: o `MAX_CONTENT_LENGTH` global (5 MB) barrava GIF de 6–10 MB **antes** da rota
  rodar (o aviso dizia "5 MB" mesmo a rota aceitando 10). `teto_de_upload_por_rota()` (routes.py) sobe o teto só
  em `/api/gif/recortar` (12 MB) e `/api/video/animar` (16 MB); `/api/upload` continua em 5 MB.

### Cartão de perfil
- Menu ⋯ cortado: o `.pc` tinha `overflow:hidden` (adicionado na rodada 1) e o wrapper
  `.pc-popout` desenhava uma moldura quadrada atrás. Agora o wrapper é transparente e o menu abre
  pra cima se faltar espaço.
- Legibilidade sobre foto/GIF claro: balão do "pensando" em **grafite sólido**, véu escuro
  gradiente no corpo do cartão com tema (`.pc.com-tema .pc-corpo`), seções escurecidas e
  `text-shadow`. (Inverter a cor do texto pela luminosidade da imagem ficou de fora: exigiria
  amostrar a imagem em canvas e CORS nos GIFs.)

### Marquee (texto grande que rola)
`MQ_SELETOR`/`MQ_RAIZES` (fim do `chat.html`): nome/subtítulo que não cabem ficam 3 s parados no
início, rolam até o fim, esperam 3 s e voltam (Web Animations API). Um `MutationObserver` +
`ResizeObserver` reavaliam quando o texto ou a largura mudam; `mqProcessar()` desliga o
observer enquanto mexe no DOM. Elemento novo que precise disso: ponha a classe/seletor em
`MQ_SELETOR` (e garanta `white-space: nowrap; overflow: hidden` + pai com `min-width: 0`).

**Bug do marquee que ficava só com "..." (Conversa rápida)**: `mqAvaliar()` media com `scrollWidth`/`clientWidth`
(inteiros) e ignorava sobra < 4 px. Só que 1–2 px a mais já fazem o `text-overflow` mostrar "…" — o subtítulo
"Conversa rápida" estourava por 2 px (caixa 83, texto 85), nem rolava nem cabia. Agora mede por
`getBoundingClientRect()` (fracionário) e rola qualquer sobra (`dist >= 1`).

### Sons novos
`tocarSom('xp'|'nivel'|'missao'|'call_entrar'|'call_sair'|'toque'|'ligando')`; `iniciarToque()`/
`pararToque()` fazem o loop do toque de chamada (até atender/recusar/cancelar) e do "chamando".
Cada tom aceita volume como 4º item (o do XP é bem baixo).

### Outras correções
- Prévia de anexo (canal e DM) saía em branco: `escUrl()` barra `blob:`; o `src` agora é definido
  por propriedade (`ligarPreviasDeAnexo`). Clicar na miniatura abre grande (foto ou vídeo).
- Caixa de entrada também no cabeçalho do servidor.

## Rodada 3 de 02/10/2026 — feedback do teste com 2 pessoas (call, mapa, barra do usuário)

Testes: `python testes/fumaca_rodada3.py` (convite por membro, posição/notas de amigos, câmera, ornamentos, limites).

### Call: janela flutuante (mini <-> cheia) — NÃO é mais uma "aba"
O `#video-view` é movido no JS para `#call-janela` (fixa, no `<body>`), então a call sobrevive a trocar de aba,
servidor e DM. `callMostrar('mini'|'cheia')`, `callMinimizar()`, `callOcultar()`, `posicionarCall()`.
- **mini**: arrasta pelo topo, redimensiona (CSS `resize: both`), controles sempre visíveis; **cheia**: cobre a área
  central (`.chat-area-main` do servidor, ou `.chat-area` numa call de DM). Duplo clique no topo alterna.
- Entrar num **canal de voz** abre cheia; **chamada de DM** abre mini (você segue no chat). `switchMainView()` e o
  clique num canal de texto chamam `callMinimizar()`. Clicar em "Voz conectada" na barra lateral volta pra cheia.
- O chat da call (botão de balão) só existe em call de canal: `isCallChatOpen` encolhe a janela cheia em 350px e o
  `#text-view` (`.sidebar-mode`, `margin-left:auto`) aparece ao lado. O `text-view` nunca mais é escondido (`hidden`).
- Mover o `<video>` de pai pausa a mídia: `callMostrar` chama `play()` em todos de novo.
- `currentVoiceChannelId` agora é `let` declarada (antes só existia depois da 1ª atribuição → ReferenceError).
- A chamada de DM (tocando/chamando) virou **cartão no canto**, sem escurecer a tela (`#chamada-recebida-modal`/`#chamando-modal`).

### Câmera nunca chegava aos outros (bug)
A call nascia só com áudio e o PeerJS **não renegocia**: `replaceTrack` não achava sender de vídeo. Hoje toda call
nasce com uma faixa de vídeo "reserva" (`videoReserva()`, canvas 2x2) trocada por `null` logo depois
(`prepararVideoDaCall`); ligar a câmera = `replaceTrack` na vaga (`senderDeVideo()`, que acha o sender **mesmo com
`track === null`** — o `s.track && ...` antigo não achava depois de desligar). Quem mostra vídeo vs avatar é o
evento `estado_camera` (socket, validado contra `participantes_call`), **não** o `mute` do WebRTC (demora/não vem).
Erro de câmera agora vira toast. `disconnectCall` zera `myCamStream` (a faixa morta ia pra próxima call).

### Tela compartilhada
- **Sem prévia da própria tela** (`.tela-propria`): compartilhar a tela onde o app roda gerava túnel infinito.
  Aparece um aviso com "Parar de compartilhar". `getDisplayMedia` usa `selfBrowserSurface: 'exclude'`.
- **Zoom na tela dos outros** (`tornarZoomavel`): roda do mouse, arrastar, duplo clique reseta.

### Barra do usuário, microfone e fone
- Barra limpa (bloco no fim do último `<style>`): sem gradiente de placa (só um filete), menus ancorados à esquerda.
- **Submenu do mic/fone fechava "rápido demais"**: tinha 4px de vão entre item e submenu (o mouse perdia o hover).
  Agora encosta, tem ponte invisível (`::before`) e fecha 350ms depois (`visibility` com atraso).
- **Toggles de ruído/eco/ganho nunca mudavam**: um listener genérico (`.toggle-switch`) e o específico alternavam
  juntos. Hoje o genérico exclui `#toggle-noise/echo/gain`, e mudar perfil/toggle chama `reaplicarMic()` (vale ao vivo).
- Teste de microfone do menu (`iniciarTesteMic`/`pararTesteMic`) agora funciona; `enumerarDispositivos` solta o mic
  depois de listar (antes ficava aberto); saída de áudio escolhida é aplicada de verdade (`aplicarSaida`, `setSinkId`);
  clique direito em mic/fone abre as opções.
- **Status: um jeito só** (o cartão de perfil). Clicar no avatar da barra abre o cartão (antes abria um menuzinho por
  cima dele). A lista de status do cartão reposiciona o cartão ao abrir (`posicionarCartao()`), senão estourava a tela.

### Mensagens e campos
- `#message-input`/`#dm-message-input` são `<textarea>`: **Enter envia, Shift+Enter quebra linha** (`autoCrescer`).
- **Limites** (`LIM_*` em `events.py`, mesmos números nos `maxlength` do HTML): nome de exibição 32, servidor 40,
  canal 32, nota 140, status/"pensando" 60.
- Estilo do nome (`nome_estilo`) e moldura vão junto de cada mensagem (histórico de canal/DM e ao vivo) e a moldura
  aparece no card da call (`novo_usuario_call`/metadata do peer). Estilo de nome **não** vai pro label da call (o label tem
  fundo e o `background-clip:text` do estilo o apagaria).
- Emoji do cabeçalho da DM saía gigante (`.dm-head-dot.custom` com largura `auto` + `img` a 100%): tamanho fixo.

### Convites
Qualquer **membro** gera convite (`criar_convite` usa `eh_membro`); quem não é dono tem teto de 7 dias / 25 usos
(o servidor força, mesmo pedindo ilimitado). O modal tem "Gmail"/"Outro" (compõe o e-mail com o link; quem envia é a
pessoa — não enviamos e-mail do servidor).

### Mapa
- **Posição de amigo só ia pras salas de servidor**: amigo sem servidor em comum nunca aparecia. Agora também vai pra
  `sala_pessoal` de cada amigo (`_salas_da_posicao`, cache de 60 s em `contatos_do_mapa`). `ultimas_posicoes` (em memória,
  só de quem NÃO está em Fantasma) é entregue em `mapa_pedir_arredores` — antes você só via quem se mexesse depois de abrir o
  mapa. Fantasma/desconectar emitem `posicao_amigo_removida` pros mesmos destinos.
- **Nota de amigo** vale no alcance grande (`RAIO_SERVIDORES_M`); de desconhecido, só no pequeno (`dados_do_mapa_perto(...,
  amigos_ids)`, `_avisar_amigos`). O cliente re-filtra por distância em `nova_geonote`.
- **GPS**: o timeout de 5 s com alta precisão estourava no PC e caía num fallback **silencioso em São Paulo**; o GPS também
  sobrescrevia o teletransporte. Agora: timeout 20 s, 2ª tentativa sem alta precisão, toast honesto, círculo de precisão,
  e o teletransporte (`posicaoManual`) vale até clicar em "Centralizar em mim" *(removido em 06/10/2026: virou Explorar, ver Rodada 7)*.

### Outros
- **Missões em cartões estilo Quests** (`.qs-card`: capa colorida pelo ícone, XP em destaque, barra, estado). Dados e
  regras iguais; só o renderer (`desenharMissoes`) e o CSS mudaram.
- **Barras laterais redimensionáveis** (`.redimensionador`, `--w-canais`/`--w-membros`, guarda em `localStorage`, duplo
  clique reseta). A janela mini da call também redimensiona.
- DM: `relacao_entre` era consultada 2x por mensagem (permissão + conversa rápida); agora 1x (`pode_trocar_dm(..., rel)`).

## Rodada 5 de 02/10/2026 — patentes, insígnias, inventário e laboratório (Gogeta / Sasuke / Fusão)

Saiu do `PLANO_COSMETICOS.md` (que agora só guarda o histórico e o que falta). **Os dois usuários de teste**: o dono
(`@aquele.sales`, tema **Gogeta**) e o amigo beta tester (`@filippo.chiarion`, tema **Sasuke**). Tudo que é "só nosso" fica
travado **por id de pessoa no servidor** (tabela `Posse`), nunca por regra do cliente. Se algum dos dois trocar o `@`,
a posse continua (é por id); para conceder de novo: `python conceder_item.py <@usuario> tudo`.

### Nível 1–1000+ e patentes (substituem Novato/Explorador/...)
- **Nível = XP total** e nunca zera. Os 100 primeiros níveis seguem a curva antiga (quem já tinha nível não mudou: 1→2 = 100 XP,
  99→100 = 20.092, total até o 100 = 999.504). Do 100 em diante o passo cresce só **+25 XP por nível** (`XP_CRESCIMENTO_ALEM`):
  100→101 = 20.117, 999→1000 = 42.592, e do **1000+** é um passo fixo de 42.617 XP por nível (sem teto). Tabela pré-calculada
  (`_LIMIARES`) + `bisect` — `nivel_da_pessoa()` é O(log n). `NIVEL_MAXIMO` deixou de existir (`nivel_maximo` do payload é sempre `False`).
- **Battle Pass é outra coisa** (trilhas temáticas de 1–100, o dono vai refazer). Por enquanto a trilha de marcos mostra o **bloco
  de 100 níveis** onde a pessoa está (`marcos_da_pagina()`: nível 150 → "níveis 101 a 200"). As moedas por nível seguem iguais.
- **12 patentes** em `cosmeticos.PATENTES` (Iniciado 1–9, Aprendiz 10–24, Explorador 25–49, Desbravador 50–89, Veterano 90–149,
  Herói 150–229, Lenda 230–329, Campeão 330–449, Semideus 450–599, Titã 600–749, Olimpiano 750–899, Panteão 900+), cada uma com
  **3 subníveis** (I/II/III em terços da faixa; Panteão = 900/950/1000) e `anim` 0–4: **quanto maior a patente, mais animação**
  (0–1 brilho que varre → 2 pulsa → 3 faíscas → 4 raios girando; Panteão roda as cores, Titã respira como brasa).
- `patente_do_nivel(n)` devolve tudo que a tela precisa (id, subnível, nome completo, `proximo`); o servidor manda em
  `xp_atualizado`, `perfil_publico` e no HTML do `/chat` — **o cliente só desenha**. `titulo`/`titulo_do_nivel()` agora são
  "Aprendiz II"; a `recompensa_do_nivel()` leva o nome da patente nova no 1º nível dela.
- **Ícones** (`Cosm.svgPatente(id, sub, {anim})` em `static/js/cosmeticos.js`): SVG 64×64 por patente, gradientes **globais**
  num `<svg id="cosm-defs">` injetado por `Cosm.iniciar()` (cada ícone só referencia por id) e um `clipPath` por instância
  (`ptc-<n>`) para o brilho que varre. Patente nova = entrada em `PATENTES` (py) **e** em `PAL`/`EMBLEMAS` (js), mesmo id.
- **Popover "orb"** (ícone grande em cima, nome embaixo, próxima evolução): qualquer elemento com `data-orb="patente|badge|texto"`
  abre; um só popover, delegado no `document`. `Cosm.htmlPatente()`/`htmlBadge()` já saem com o atributo.
- Onde aparece: cartão de perfil (chip "Nv. N" + ícone + insígnias), Meu Perfil > Conta, Battle Pass (ícone grande ao lado do nome),
  tela de "subiu de nível" e a **galeria da aba Patentes do Inventário** (as não alcançadas ficam cinza). Ainda **não** aparece ao lado
  do nome nas mensagens/lista de membros (precisaria do nível do autor em cada payload).

### Insígnias (não equipáveis: aparecem sempre)
*(Atualizado em 07/10/2026: hoje são 6, com desenhos novos e regras de quem recebe — ver "Insígnias" na Rodada 8.)* Eram `criador`, `beta_tester`, `coder` e `so_nos`
só dos dois testers; o "Só nós" das duas chamas virou a sarça ardente. Desenho em `DESENHO_BADGE`; nomes/descrições espelham `cosmeticos.CATALOGO`.

### Catálogo, posse e inventário (regra 4 em ação)
- `app/cosmeticos.py` é a fonte da verdade dos itens **exclusivos**: `CATALOGO["<tipo>:<id>"]`. Os itens **livres** (neon, ouro,
  lava...) continuam nas tuplas de `utils.py` e nos catálogos do `chat.html`; os ids exclusivos entram nas mesmas tuplas
  (`ESTILOS_NOME`, `PLACAS`, `MOLDURAS`, `FAIXAS_ANIMADAS`) só pra validar.
- Tipos: colunas já existentes (`moldura`, `placa`, `nome` = `nome_estilo`, `faixa` = `banner_color 'anim:<id>'`) e **slots em JSON**
  `Person.equipados` (`efeito_avatar`, `efeito_perfil`, `efeito_fala`, `efeito_radar`, `efeito_chat`, `som_call`, `pin_nota`).
  `equipados_da_pessoa()` **só devolve ids que o catálogo conhece** (JSON adulterado/quebrado vira vazio, nunca vira `class=""`).
- Tabela nova **`Posse`** (`person_id`, `item_id`, `origem`; única por par). `atualizar_perfil` confere a posse (`pode_usar()`): exclusivo
  sem posse **não muda o slot** (não apaga o que já estava equipado) e avisa com `erro_bazinga`. Eventos novos: `listar_inventario`
  → `inventario`, `equipar_item {item_id}` (inclusive `pacote:<tema>`), `desequipar_item {tipo}`; os dois últimos mandam
  `perfil_atualizado` + `inventario` pras abas da pessoa e `perfil_membro_mudou` pra quem convive.
- **Conceder** é um ato explícito: `atualizar_banco.py` (passo 24, idempotente) ou `conceder_item.py` — a identidade (@ → id) é resolvida **uma
  vez**. Não roda sozinho no boot de propósito: se alguém trocasse o @ e outra pessoa pegasse o antigo, herdaria o item.
- **Inventário** = aba "Inventário" nas Configurações (embaixo de Meu Perfil) **e** botão "Inventário" na barra lateral embaixo do
  Mercado Elite (os dois abrem o mesmo `#inv-raiz`; `Cosm.renderInventario`). Abas Tudo/Insígnias/Molduras/Placas/Nomes/Faixas/Efeitos/Pacotes/
  Patentes; cada item tem prévia animada; "Ouvir" nos sons; clicar equipa (só muda quando o servidor confirma). Os catálogos do editor de
  perfil também listam os exclusivos que a pessoa possui (`exclusivosDe()`).
- O `/chat` já embute o inventário (`inventario_inicial`): +1 query (`/chat` foi de 9 pra **10**).

### Laboratório: o que existe (CSS/SVG puro, nada de imagem)
| Tipo | Gogeta | Sasuke | Fusão |
|---|---|---|---|
| Moldura (`::before` do `.moldura-*`) | Aura Dourada | **Sharingan** (anel vermelho + 3 tomoe em `::after`, sem cor girando) | Fusão |
| Placa (várias camadas de `background` animadas) | Em Chamas (brasas) | Cinzas Roxas | Duas Chamas |
| Nome (`background-clip:text`) | Super Saiyajin | Mangekyō (tremor vermelho) | Fusão |
| Faixa (`.banner-anim-*` + `::before` de faíscas/raios) | Aura Saiyajin | Tempestade Roxa | Fusão |
| Efeito de avatar (`.ef-av`) | aura de chamas | **Olho Brilhante** (o anel do Sharingan acende em vermelho e volta ao normal, ciclo de 7 s) | — |
| Efeito de perfil (`.ef-pf` por cima do cartão) | poeira cósmica (CSS) + **Punição de Alma** (canvas) | raios caindo + chama negra de Amaterasu que sobe de baixo, cresce e volta | — |
| Efeito de fala (`.video-card.fala-X.is-speaking`) | ki explode | Chidori | — |
| Efeito do radar (classe na `.raio-onda`) | ondas douradas | ondas roxas | — |
| Efeito do chat (digitando = brilho; Enter = faíscas/raio) | Ki no Teclado | Raio no Teclado | — |
| Som de entrada na call (Web Audio sintetizado) | Power Up | Chidori | — |
| Pin de nota no mapa (`.pin-X.minimized`) | Esfera de Estrelas | Kunai Roxa | — |
| **Efeito de servidor** (ícone na barra + nome no cabeçalho + pino no mapa) | Chamas do Servidor | Tempestade do Servidor | Fusão do Servidor |
| Pacote (equipa o tema inteiro) | ✓ | ✓ | ✓ (só os 4 visuais) |

**Montanha das Patentes** (botão "!" ao lado da patente no cartão, no Battle Pass e na aba Patentes do inventário; `Cosm.abrirMontanha`): tela cheia que começa no
pé da montanha e rola pra cima; as patentes ficam "cravadas" em placas de pedra com o nível que pedem, **caem com estrondo** quando entram na tela
(`IntersectionObserver`; a montanha treme com `--f` que cresce até ~6 px nas altas, e `Cosm.somImpacto` sintetiza o estrondo), nuvens e aves passam, e a luz/sol
aparecem conforme se sobe (`--luz` = progresso da rolagem). Uma bandeira marca onde a pessoa está e a trilha dourada vai até ela. Topo fixo com o X e o ESC (o ESC
fecha só a montanha: listener em captura + `stopImmediatePropagation`). Tabela de patentes vem do servidor (`inventario.patentes`), então mudar faixa em `cosmeticos.PATENTES` muda a montanha.
Perfil/mensagem: molduras e auras na foto pequena das mensagens ficam **sem `filter` difuso** (era o "fade" em volta da imagem).

**Efeito de servidor** é diferente dos outros: não é um slot da pessoa, é do **servidor** (`Server.efeito`, coluna nova). O inventário tem o botão
"Aplicar a um servidor" (lista só os servidores onde a pessoa é dono). Evento `aplicar_efeito_servidor {server_id, valor}`: o servidor confere que a pessoa
administra o servidor (`servidor_gerenciavel`) **e** possui o item, grava, reenvia o servidor a todos os membros (`avisar_servidor`) e atualiza o pino do mapa
(`servidor_mapa_editado`). O cliente aplica `sv-ef-<id>` no ícone da barra e no `.pino-foto`, e `ne-<id>` no nome do cabeçalho. `efeito_servidor_valido()`
filtra o valor em todo payload (`_json_de_servidor`, `servidor_mapa_para_json`).

**Como o Sasuke v2 funciona** (feedback do 1º teste; asas de Susanoo, fogo em partículas e Punição de Alma foram testados e **descartados**): os **raios**
desenham o traço de cima pra baixo (`stroke-dashoffset` 100→0 em ~0,1 s, `pathLength=100`); ao fim de cada ciclo (invisíveis) o evento `animationiteration`
chama `sortearPosicao()` (`iniciar()` liga um listener só), que sorteia o `left` da próxima queda (elementos com `data-aleatorio="<nome da animação>"`). A **Amaterasu**
foi **refeita em canvas na Rodada 6** (ver "Efeitos em canvas"): a faixa de SVG parecia grama/espetos e o dono pediu algo discreto, tipo anime. Os **tomoe**
do Sharingan são 6 `radial-gradient` no `::after` da moldura (o `inset` dele acompanha o do `::before` em cada contexto). O **Olho Brilhante** é só `box-shadow` animado no `.ef-av`.
O pacote de cada tema pega o **1º item de cada tipo** (`_pacote`), então extras opcionais futuros não entram sozinhos.

Pegadinhas que apareceram (já resolvidas — não desfaça):
- **Aura de Gogeta cobria a foto** de quem não tem imagem: `z-index:-1` ainda pinta *por cima* do `background` do próprio avatar. Hoje a aura tem
  um **furo no meio** (`mask: radial-gradient(closest-side, transparent 60%, #000 65%)`); `.com-ef` (+ `isolation:isolate`) é a classe do avatar que carrega aura.
- **`.user-profile-bar[class*="placa-"]` força `animation` e `background-size` com `!important`** (chat.html, bloco da barra do usuário). Placa nova com
  várias camadas precisa também do seletor `.user-profile-bar.placa-X { ... !important }` (já feito pras três).
- Efeito no **nome** usa `filter: drop-shadow`, não `text-shadow`: com `color: transparent` + `background-clip:text` o text-shadow pinta por cima do degradê.
- A **call mostra o visual que o SERVIDOR mandou** (`novo_usuario_call`/`participantes_call_mudou` → `visualPorPeer`), não o `metadata` do peer
  (cliente adulterado afirmaria ter item que não tem). `adicionarVideoCard` só usa o metadata para moldura **livre**, e só se o aviso do servidor
  ainda não chegou. Equipar no meio da call reemite `participantes_call_mudou` (`_atualizar_visual_na_call`, regra 6).
- Em teste, `socketio.test_client()` criado **antes** do servidor existir não está na `sala_servidor` (o `join_room` é no `connect`): reconecte o cliente.

**Criar item novo do laboratório**: (1) `_item(...)` em `cosmeticos.py` (acima de `recalcular_pacotes()`); (2) CSS com o id (`.moldura-<id>`, `.placa-<id>`
+ `.user-profile-bar.placa-<id>`, `.ne-<id>`, `.banner-anim-<id>`, `.ef-av-<id>`, `.ef-pf-<id>`, `.fala-<id>`, `.radar-<id>`, `.chat-ef-<id>`, `.pin-<id>`);
(3) pros efeitos com HTML/JS, o id na lista de `cosmeticos.js` (`EFEITOS_AVATAR`, `EFEITOS_PERFIL`, `IDS_EFEITO`) e, se for som, o ramo em `somEntrada`;
(4) `LABORATORIO` já pega o tema sozinho (`_itens_do_tema`); rode `conceder_item.py` ou `atualizar_banco.py`.
Para a loja pública, **refazer com arte/áudio próprios** (nada de sprite/som de Dragon Ball ou Naruto): o laboratório só usa formas, cores e sons sintetizados.

Teste: `python testes/fumaca_cosmeticos.py` (curva 1–1000+, patentes, catálogo, posse, equipar/recusar, JSON adulterado, insígnias, call, pin, efeito de servidor, regra 6).
**Rodar `python atualizar_banco.py` depois do deploy**: cria `person.equipados` e `server.efeito`, a tabela `posse` nasce no `create_all()` e os itens do laboratório são concedidos.

**O que ficou de fora** (ver `PLANO_COSMETICOS.md`): gadget do mapa (música tipo Spotify — o pedido ficou ambíguo), patente ao lado do nome
em mensagens/listas, loja/economia (Mercado e Battle Pass temático seguem para refazer).

## Rodada 6 de 02/10/2026 — estabilidade de call, mapa, versão do app e peso das configurações

Saiu do teste com o amigo (Gabriel): ele "caía da call", aparecia em 3-4 calls ao mesmo tempo, a ligação por DM não tocava
pra ele, a pessoa aparecia duplicada na chamada e o mapa/radar ficava estranho. Teste novo: `python testes/fumaca_call.py`.

### Call: o servidor é a fonte da verdade de "quem está na call"
- **Causa do "cai da call"**: o `disconnect` do socket tirava a pessoa da call, e o cliente **nunca reentrava** quando o socket
  reconectava (Render/Neon/troca de rede piscam o socket o tempo todo; a mídia WebRTC nem caía). A pessoa virava fantasma: os outros
  não a viam, `estado_camera` era recusado (não estava mais na lista) e quem entrava depois nunca ligava pra ela.
  Agora: (a) o `disconnect` só agenda a saída (`GRACA_CALL_SEGUNDOS = 12`, `_graca_call`), (b) o cliente reemite `entrar_call` com o
  **mesmo `peer_id`** no `connect` e isso cancela a saída, (c) a reentrada manda `novo_usuario_call` com `reentrada: true` e o cliente
  só refaz a ligação se a antiga morreu (`connectionState`).
- **Uma pessoa, uma call**: `_meta_call[(chave, peer_id)] = {sid, usuario_id, server_id}` e `_call_por_sid`. Entrar numa call tira a
  pessoa de qualquer outra (outro canal, outra aba, peer velho de F5) e avisa a aba velha com `call_substituida` (o cliente sai sozinho).
  Era o "fantasma em 3 calls": cada socket só lembrava UMA call, a anterior ficava na lista de todo mundo pra sempre.
  `sair_call` só vale pra entrada que é da própria pessoa; `_tirar_da_call()` é o único jeito de remover (não depende de request, então
  roda no fim da graça).
- **Autocura no cliente**: `participantes_call_mudou` da MINHA call agora limpa card de gente que não está mais na lista
  (`reconciliarCall`) e, a cada 6s, quem está na lista sem ligação viva vira `pedir_ligacao` (o servidor repassa pra essa pessoa discar
  de novo, `refazer`). O PeerJS não renegocia e só quem JÁ estava dentro disca, então o pedido passa pelo servidor.
- **Ligação por DM**: `_chamadas_pendentes[(quem_liga, quem_recebe)]` guarda de qual ABA saiu a ligação; `chamada_aceita` volta só pra essa
  aba (antes ia pra todas as abas de quem ligou e cada uma entrava na call = a pessoa duplicada) e as outras abas de quem recebia fecham o
  toque (`chamada_resolvida`). Aceitar chamada que já acabou não entra em call. Pessoa offline recusa na hora (`offline: true`), toque some
  sozinho em 45-50s, quem liga e cai cancela o toque de quem recebe. `conectarNaCall` tem trava (`conectandoCall`) contra dois peers.
- **Vídeo × voz**: `chamar_amigo` já mandava `tipo`; agora `chamada_aceita` o devolve e `conectarNaCall(sala, nome, {video: true})` liga
  a câmera quando o peer abre. A de voz segue só áudio.
- **Sem "chat da call"**: o botão de balão foi removido. Abrir canal de texto/DM/outra aba já minimiza a call numa janelinha
  (`callMinimizar`). A `.call-janela` caiu de `z-index: 9000` pra **1500**: fica na frente do app mas ATRÁS de cartão de perfil (2001),
  menus, modais, pickers e configurações. Era a call cobrindo tudo (o cartão de perfil aparecia cortado por ela).
- **ICE**: `ICE_SERVERS` vem do servidor (`_servidores_ice()` em `app/__init__.py`). Para TURN próprio defina no Render `TURN_URLS`
  (vírgula), `TURN_USERNAME` e `TURN_CREDENTIAL` — vai na frente do relay público (openrelay, instável). Sem relay, rede de faculdade/4G
  não conecta e parece "sumiu da call".
- **Sharingan esticado no card da call**: o anel da moldura é `::before` absoluto e o `.video-avatar` não era posicionado (só com
  `.com-ef`), então o anel se ancorava no card INTEIRO. `.video-avatar { position: relative }` no fim do `cosmeticos.css`.

### Efeitos em canvas (Amaterasu do Sasuke, Punição de Alma do Gogeta)
CSS não faz fogo orgânico nem vórtice, então esses dois efeitos de perfil são `<canvas class="ef-cv" data-ef="amaterasu|punicao">` dentro do `.ef-pf`.
Um **motor único** em `cosmeticos.js` (`MOTORES`, `passoCanvas`, `ligarCanvas`; 30 fps) desenha todo canvas visível e **dorme** quando não há nenhum, a aba está
escondida ou `prefers-reduced-motion`; um `MutationObserver` o acorda quando um canvas aparece (cartão, prévia do perfil, inventário). Efeito novo em canvas = objeto
`{ novo(), desenhar(ctx, estado, t, dt, w, h, esc) }` em `MOTORES` + `<canvas data-ef>` no `htmlEfeitoPerfil`. `Cosm._passo(ts)` desenha um quadro na mão (usado pra testar
no navegador com a aba em segundo plano, onde `requestAnimationFrame` não dispara).
- **Amaterasu**: línguas de fogo pretas (gota com ponta curvada, balançam e "respiram") com halo lilás só na borda, mais fagulhas pretas. Um "nível" por ciclo de 14 s
  controla quantas nascem e até onde sobem (no máximo ~15% do cartão, nunca espeto reto): sobe de leve e some.
- **Punição de Alma** (ciclo de 17 s, a poeira dourada em CSS continua por baixo): partículas brancas entram em **espiral** em volta do CENTRO do cartão (rastro curvo, giram mais rápido perto do centro)
  → núcleo de luz branca cresce e vira a **bolha arco-íris** (borda laranja, rosa, miolo ciano/azul com braços do redemoinho e meia-lua verde, reflexo de bolha de sabão,
  cintilar em volta) → **estoura** (flash, aro iridescente que expande, cacos coloridos). O item se chama "Poeira Cósmica e Punição de Alma".

### Sons de entrada de arquivo
`ARQ_SOM` em `cosmeticos.js` mapeia o id do item pro arquivo em `app/static/audio/` (gogeta → `teleporte.mp3`, sasuke → `sharingan.mp3`; os itens
agora se chamam "Teleporte" e "Sharingan", os ids `gogeta`/`sasuke` não mudaram). `somEntrada()` toca o arquivo e só cai no som sintetizado
(Power Up/Chidori, ainda no código) se o arquivo falhar. Os dois mp3 vieram de efeitos de DBZ/Naruto: ok pro beta fechado, **trocar por áudio
próprio antes da loja pública**. Som novo = arquivo em `static/audio/` + linha em `ARQ_SOM` (o id já precisa estar em `IDS_EFEITO.som`).

### Versão do app (aba velha falando com servidor novo)
`APP_VERSAO` (`app/__init__.py`: `RENDER_GIT_COMMIT` ou hora do boot) vai no HTML (`VERSAO_PAGINA`) e o servidor manda `versao_app` a cada
`connect`. Se divergir, `mostrarAvisoNovaVersao()` mostra a faixa "Atualizar agora" e recarrega sozinho quando não há call nem texto sendo
escrito. `/chat` sai com `Cache-Control: no-store`. É o mesmo mecanismo que serviria de "versão mínima" se o app virar empacotado (se o app
só carregar o site, a versão é sempre a do servidor). `versao_app` também é o sinal de que o `connect` terminou: sem ele em 5s o cliente
pede `garantir_salas` (o `connect` agora tenta de novo se o banco estava acordando, mas isso cobre o resto).

### Mapa
- **Posição sumia**: PC parado quase nunca dispara o `watchPosition`, e o servidor esquece a posição no `disconnect`: depois de qualquer
  piscada do socket a pessoa sumia do mapa dos outros até o GPS "andar" (nunca, no desktop). Agora o cliente reanuncia a posição a cada 45s
  e ao reconectar (`anunciarMinhaPosicao`), e o servidor só repete pra quem chega a posição de quem mandou sinal nos últimos 180s
  (`POSICAO_VALE_SEGUNDOS`); o cliente tira pino de amigo sem sinal há 4 min. `_cache_contatos` é invalidado quando a amizade muda.
- **"Mapa louco" (Samambaia → Taguatinga)**: o PC sem GPS chuta a região pelo Wi-Fi/IP. `aoReceberGps` descarta fix PIOR que o atual que
  joga a posição longe (`ultimoFixGps`), avisa quando a precisão é ruim (> 1,5 km) e o **teletransporte (duplo clique) fica salvo no
  aparelho por 6h** (`localStorage pnt_pos_manual`, só conveniência de UI); "Centralizar em mim" esquece. O "mini radar verde" era o círculo
  de precisão (`mostrarPrecisao`) — agora some sozinho em 10s.

### Peso (reações e configurações)
- `reagir_mensagem` emitia `reacoes_atualizadas` DEPOIS de pagar XP/missão (~8 queries no Neon): a reação demorava. Agora emite antes e o
  cliente já muda o chip no clique (`reagirOtimista`, o evento do servidor sobrescreve e corrige).
- Configurações/modais travavam por **blur aninhado** (overlay `blur(6px)` + cartão `blur(22px)`) sobre um fundo cheio de animação
  (placas, molduras, nomes). Agora overlay e cartão são sólidos, `body.painel-aberto` pausa a animação do fundo e as prévias do
  catálogo/inventário só animam sob o mouse (ou equipadas).

---

## Rodada 7 de 05/10/2026 — PWA com cache + app desktop (Electron)

### O que foi feito (testado em 05/10/2026; commit/deploy ainda não)
- **Código em `desktop/`** (casca Electron 44; `npm install` e `npm start` lá dentro; `npm run dist` gera
  `dist/Panteão Setup 0.1.0.exe`, ~107 MB, **sem assinatura**). Servidor vem de `desktop/config.json` (`servidor`) ou da
  env `PANTEAO_URL`. **O `config.json` ainda aponta pra `http://localhost:5000`: trocar pela URL do Render antes de distribuir.**
- **Fluxo de login do desktop** (testado de ponta a ponta com servidor SQLite descartável): `login.html` local (animado,
  pinga `/manifest.webmanifest` e avisa "acordando o servidor") → botão abre o navegador em `/entrar?desktop=1&desafio=<sha256>`
  → Google → `auth.callback` vê `session['desktop_desafio']` e gera código de uso único (60s, em memória) → página
  `desktop_ok.html` abre `panteao://auth?codigo=...` → o app navega em `/auth/desktop/trocar?codigo&verificador` e recebe o cookie.
  **PKCE**: só o hash (`desafio`) sai do app; o `verificador` fica na memória do processo principal. O código morre na
  1ª tentativa (certa ou errada). Teste: `python testes/fumaca_desktop.py`.
- **Service worker** (`service_worker()` em `main/routes.py`): cache de `/static/*` versionado (`estatico-<APP_VERSAO>`,
  o texto do SW muda a cada deploy → navegador instala o novo e `activate` apaga o velho), cache `cdn-v1` só pra CDN com versão
  fixa (nada de `@latest`/`@1`), página "Sem conexão" em navegação offline. Em `debug=True` o estático **não** é cacheado.
  Registrado em `chat.html`, `entrar.html`, `abrir.html`.
- **Pegadinhas que apareceram**: (1) **o Cache Storage do SW derruba o renderer do Electron 44** ("bad Mojo message ...
  CacheStorageCache") e, com `render-process-gone` recarregando, virava loop — por isso o SW **não é registrado** quando o UA tem
  `PanteaoDesktop` (o app limpa SW/cache antigos ao iniciar). O PWA em Chrome real **não foi testado** com o SW novo.
  (2) CSP `default-src 'self'` das telas locais bloqueia `<script>` inline: o JS fica em `desktop/assets/*.js`.
  (3) O cookie `session` continua existindo depois do logout (o `/entrar` grava `veio_do_entrar`), então **cookie não prova
  sessão**: o app tenta `/chat` e, se o servidor redirecionar pra `/entrar`, volta ao login local com `?sem=1` (sem isso: loop).
  (4) Renderer que cai 3x em 30s mostra erro em vez de recarregar de novo.
- Já pronto na casca: instância única, `panteao://` (second-instance no Windows), bandeja (fechar = esconder; "Sair" encerra;
  "Iniciar com o Windows"), tamanho/posição lembrados, links externos no navegador do sistema, permissões só pro domínio do app,
  seletor próprio de tela/janela (`seletor.html`, áudio `loopback`), auto-update via `electron-updater` (só empacotado).
- **Repo é PRIVADO desde 05/10/2026** (o `.env` com senha do Neon/Google/SECRET_KEY foi commitado no passado, commit `e7e2a27`, quando
  o repo era público: **trocar essas credenciais** — pendente, e `instance/*.db` também está no histórico). Produção:
  `https://bazinga-hub-gg.onrender.com` (já no `desktop/config.json`).
- **Auto-update** (`iniciarAtualizador()` em `main.js`; só no app empacotado): baixa em segundo plano, avisa "Reiniciar agora / Depois",
  confere de novo a cada 4h e tem "Procurar atualizações" na bandeja. Como o código é privado, os instaladores vão num repo **público só
  de binários**: `AqueleSales/panteao-releases` (campo `publish` do `desktop/package.json`). **Publicar uma versão nova**: (1) subir `version` em `desktop/package.json`; (2) `cd desktop && npm run dist` (o nome é fixo, só ASCII:
  `Panteao-Setup-<v>.exe`, porque o GitHub troca espaço/acento no upload e quebraria o `latest.yml`); (3) `cd dist` e
  `gh release create v<v> Panteao-Setup-<v>.exe Panteao-Setup-<v>.exe.blockmap latest.yml --repo AqueleSales/panteao-releases --title "Panteão Desktop <v>" --notes "..."`
  (os **3 arquivos**: sem o `latest.yml` o app não enxerga a versão nova; o `gh` precisa de `gh auth login` feito uma vez). A v0.2.0 já está
  publicada (06/10/2026). O repo de releases é público: **nada de chave dentro do instalador** além do que já é público (a `googleApiKey` do
  `config.json` só entra se for restrita à Geolocation API). Mudança só no site (Flask/chat.html) **não** exige novo instalador. Não testado de
  ponta a ponta ainda (precisa de uma 2ª versão publicada pra ver o app se atualizar).
- **Duas camadas de atualização, dois avisos** (não confundir): (1) mudança no **SITE** (deploy no Render) chega sozinha: o servidor manda
  `versao_app` a cada `connect`, e se diferente da `VERSAO_PAGINA` aparece a faixa "Saiu uma versão nova... Atualizar agora" (recarrega sozinha em
  ~20 s se não há call nem texto sendo escrito); o app desktop só carrega o site, então não baixa nada. (2) mudança no **PRÓPRIO APP**
  (instalador, `desktop/`): `electron-updater` baixa em segundo plano e o estado vai pra dentro do app (`mudarEstadoAtualizacao` em `main.js` →
  IPC `atualizacao:estado` → `pintarAtualizacao()` em `chat.html`): **pílula no canto inferior esquerdo** ("Baixando a atualização X · 42%" com barra;
  depois "Atualização X pronta [Reiniciar e atualizar]"), status e "Procurar atualizações" em Configurações > Geral, rodapé da tela de login e dica
  da bandeja. A janelinha do Windows só aparece se a janela estiver escondida na bandeja. Fases: `nenhuma|procurando|atualizado|baixando|pronta|erro|dev`.
  Erro de rede ao procurar é silencioso (só vira aviso se estava baixando). A pílula só existe com `window.panteao` (app desktop). **Pegadinha**:
  `Set-Content -Encoding utf8` do PowerShell 5.1 grava BOM e, com `Get-Content -Raw`, estraga acento (`Panteão` virou `PanteÃ£o` no build): editar
  `package.json` por Python/Edit, nunca por Get/Set-Content.
- **Falta**: assinatura de código (SmartScreen); badge de não lidas; geolocalização no Electron (usa o Windows; se falhar, vale o
  teletransporte do mapa); testar com o Render dormindo e com duas contas (regra 6).

### Localização na conta + aba "Geral" (Configurações do app)
- **Interruptor na CONTA** (igual ao Modo Fantasma): `Person.localizacao_ativa` e `Person.localizacao_ip` (colunas **anuláveis**:
  `NULL` = nunca mexeu = **ligada**; `atualizar_banco.py` passo 25). Evento `alternar_localizacao {ativa?, ip?}` → `preferencias_carregadas`
  pra todas as abas; o valor inicial já vem no HTML (sem piscar).
- **Desligada, o SERVIDOR recusa** (`localizacao_ligada()` em `utils.py`; regra 4): comprar (`/api/produtos/<id>/comprar` → 403;
  **não existe rota de vender ainda**, o Bazar vai ser refeito: ligar a mesma checagem lá), `criar_geonote`, `copiar_geonote`,
  `plantar_servidor`, `entrar_servidor_pin`, e o radar nos dois sentidos (`atualizar_localizacao` descarta a posição e
  `mapa_pedir_arredores` não devolve nada). **XP/missões NÃO são bloqueados** (decisão do dono). Desligar emite `posicao_amigo_removida`
  (regra 6). **É trava leve**: cliente adulterado ainda manda coordenada falsa; ela barra uso casual, não é prova de presença.
- **Alcance e pino (corrigido em 06/10/2026)**: `_dentro_do_alcance()` **não deixa mais passar sem posição conhecida** (antes plantava servidor/nota de
  qualquer lugar) e `entrar_servidor_pin` só aceita servidor **plantado**, vivo (não vencido/oculto) e **dentro de `RAIO_SERVIDORES_M`** do pino
  (antes qualquer pessoa entrava em QUALQUER servidor só chutando o id: sem pino a checagem era pulada). O mapa nasce com `minZoom 3`,
  `maxBounds` do mundo e `noWrap` (antes só havia limite depois da 1ª posição e dava pra ver/clicar o mundo repetido).
- **Confiança da posição + Explorar (06/10/2026)**: o cliente manda `fonte` em `atualizar_localizacao` e o servidor guarda por socket em
  `fontes_mapa`: `'aparelho'` (GPS/Wi-Fi: **pode agir**), `'ip'` (só aproximada: **só olha o mapa**, não vira pino pros amigos) ou `'suspeita'`
  (dois fixes seguidos com salto > 50 km e > 1000 km/h = teletransporte: 30 min sem agir, sem pino; `VELOCIDADE_MAX_KMH`, `SALTO_MIN_M`,
  `SUSPEITA_SEGUNDOS` em `events.py`). **Agir** = `plantar_servidor`, `criar_geonote`, `copiar_geonote`, `entrar_servidor_pin`
  (`_exigir_presenca()`); comprar só exige a localização ligada. O **teletransporte (duplo clique) acabou**: virou **Explorar**
  (`mapa_explorar` → `mapa_arredores` com `explorando: true`): olhar notas e servidores plantados em outro lugar (ex.: evento em outra
  cidade), **sem radar de pessoas** (senão dava pra espiar quem está na casa de alguém), **sem mexer em onde o servidor acha que você está**
  (então não dá pra agir de lá) e com limite de ritmo (0,8 s). O cliente mostra a faixa "Explorando: só olhando / Voltar pra mim"
  (`explorarPonto`/`sairDoExplorar`, `modoExplorar`) e `exigirLocalizacao(true)` barra a ação com o motivo. Ponto salvo do teletransporte
  antigo (`pnt_pos_manual`) é apagado no boot. **Modo Fantasma**: o cliente passou a mandar a posição mesmo com ele ligado (o servidor é quem
  esconde o pino); sem isso o servidor "não sabia onde a pessoa estava" e barrava plantar/nota. **Consequência assumida**: PC sem sensor
  (só IP) vê e explora, mas não age; o celular (PWA, com GPS) tem tudo. Continua sendo trava leve: cliente adulterado manda `fonte: 'aparelho'`
  com qualquer coordenada; não existe API que prove presença.
- **DM: link e anexo só entre amigos**: em `enviar_mensagem_direta`, quem não é amigo (conversa rápida, pedido pendente, só divide servidor)
  tem link (`texto_tem_link()` em `utils.py`, propositalmente largo: prefere barrar a mais) e anexo recusados com o motivo. Anotações (a si
  mesmo) e amigos seguem normais. Vira amigo e libera.
- **Convites (06/10/2026)**: (1) link `/convite/<código>` do próprio site, em qualquer mensagem (DM ou canal), vira **cartão animado** (borda em
  gradiente, ícone flutuando, botão com brilho) desenhado por `htmlCartoesDeConvite`/`hidratarConvites`/`pintarConvite` a partir de
  `GET /api/convite/<code>/previa` (login obrigatório; só nome, ícone, nº de membros, validade; inválido = esgotado = inexistente;
  `server_id` só pra quem já é membro, pro botão "Abrir"). O link sai do texto (e o texto antigo "Te convidei pro servidor X: ..." também).
  (2) **Convidar** (modal do servidor): lista de amigos com botão Convidar (manda só o link na DM, convite de 1 uso/24h) + "ou envie um link"
  (validade/usos, copiar, QR e e-mail dentro de "Mais opções"). Os pedidos `criar_convite` passam por uma fila (`pedidosConvite`, casa por
  `server_id`, expira em 8 s) porque modal e DM compartilham o evento `convite_criado`. (3) **Barra "Link ou código de convite + Entrar"**
  ao lado de "Plantar Servidor" (`entrarComConvite`). (4) **"+" da barra de servidores** abre `#add-opcoes-modal`: Criar o meu / Entrar com um
  convite / Explorar servidores (**em breve**: mapa vivo com barquinhos e estruturas; ainda só o cartão). O campo "Recebeu um convite?" saiu do modal de convidar.
- **Reserva por IP**: `GET /api/localizacao/ip` (`routes.py`) acha o 1º IP público de `X-Forwarded-For` e consulta `PROVEDOR_IP`
  (ipwho.is, sem chave; troque a constante pra mudar de provedor). Cache de 1h por IP, 1 pedido a cada 15s por pessoa; precisão fixa
  de 10 km. **Erra com VPN e dados móveis** (o IP é do provedor): o cliente avisa e o duplo clique no mapa (teletransporte) continua mandando.
  No cliente (`tentarPosicaoPorIP` dentro do `initMap`) entra quando o aparelho erra OU em 8 s sem nenhuma posição (Electron/PC sem provedor
  fica mudo ~35 s); uma leitura melhor do aparelho depois substitui o fix por IP.
- **Aba "Geral"** (`#set-geral`, em "Configurações do app"): localização (+ estado atual: aparelho/IP/ponto marcado), sons e avisos
  na área de trabalho (`localStorage`, por aparelho) e, **só no app desktop** (`window.panteao.prefsGet` existe): localização do Windows,
  localização do Google, iniciar com o Windows e "fechar deixa o app na bandeja". Os toggles usam `.toggle-switch.tg-app` (o listener
  genérico de toggle exclui essa classe: o estado vem do servidor/das prefs, nunca alterna sozinho).
- **Prefs do app desktop** moram em `userData/prefs.json` (`desktop/main.js`: `prefs`, IPC `prefs:get/set`, só aceitos da tela local ou do
  próprio servidor do app). Windows/Google são lidos **antes do ready** (flag `WinrtGeolocationImplementation` / `GOOGLE_API_KEY`), então
  mudar exige **reiniciar** (a aba mostra o botão). A chave do Google vem de `desktop/config.json` (`googleApiKey`) ou da env `GOOGLE_API_KEY`;
  fica dentro do instalador, então precisa ser **restrita à Geolocation API** no Google Cloud. "Iniciar com o Windows" não faz nada em
  `npm start` (registraria o electron.exe puro): só no app instalado. O serviço "Geolocalização" (`lfsvc`) do Windows está **desativado**
  no PC do dono; sem ele a flag do Windows não ajuda (por isso IP e Google).
- Teste: `python testes/fumaca_localizacao.py` (travas, regra 6, IP). A parte do Electron (prefs/IPC) **não foi testada ao vivo**.

### Plano original (histórico)

**DECISÃO FINAL (05/10/2026): fazer PWA instalável E Electron juntos, PWA primeiro.** Motivo: o Electron não deixa nada mais
rápido (+150–300 MB de RAM, instalador ~80–100 MB, mesma latência de Render/Neon), e parte do público tem internet ruim. Então:
(a) **PWA** é o caminho leve e universal (já existem `/manifest.webmanifest` e `/sw.js`): falta tela de login animada, **cache dos
estáticos no service worker** (hoje ele propositalmente não faz cache — mudar com cuidado: nunca cachear `/chat`, `/socket.io`, `/api/*`,
senão mostra tela velha; versionar o cache por `APP_VERSAO`) e o botão de instalar; (b) **Electron** reaproveita a mesma tela de login e
só entra pelo que o PWA não faz (auto-update com cara de Discord, iniciar com o Windows, seletor de captura de tela, tray). Ordem:
login animado → cache no SW → PWA polido → casca Electron. Perguntas em aberto pro dono: Node.js instalado? repo do GitHub é privado
(decide onde ficam os Releases)?

Objetivo: app instalável no Windows (estilo Discord), com tela de login própria e animada e **atualização
automática**. Plano do Electron: **Electron como casca** (`desktop/` na raiz do repo) que carrega o site do Render. Nada do
`chat.html` é reescrito; o app é só uma janela + login + atualizador.

- **Por que Electron e não "app nativo"**: o produto inteiro é HTML/JS/WebRTC/Leaflet. Electron = Chromium embutido,
  então call, mapa e emoji funcionam como no Chrome. Reescrever em Kotlin/Java (como o SamusChat do amigo) seria refazer tudo.
- **Duas camadas de atualização**: (1) o **site** atualiza sozinho a cada deploy no Render (já existe o aviso
  `versao_app`/`mostrarAvisoNovaVersao`, ver Rodada 6) — 95% das mudanças não exigem novo instalador; (2) a **casca**
  (`electron-updater` + GitHub Releases, instalador NSIS) baixa a versão nova em segundo plano e instala ao fechar/reabrir.
  Sem certificado de assinatura o Windows mostra o SmartScreen ("editor desconhecido") na 1ª instalação; o auto-update funciona igual.
- **Login (armadilha)**: o Google **bloqueia OAuth dentro de webview/Electron** (`disallowed_useragent`). Fluxo certo:
  tela de login local (`desktop/login.html`, animada, empacotada no app, funciona mesmo com o Render dormindo) → botão abre o
  **navegador do sistema** em `/entrar?desktop=1` → depois do Google o servidor redireciona pra `panteao://auth?codigo=<uso único, ~60s>`
  → o Electron troca o código por sessão (rota nova no Flask, guarda o cookie na janela). Exige: rota `/auth/desktop/trocar`, tabela/dict
  de códigos de uso único, e **nunca** colocar o cookie/sessão na URL do protocolo. Checar `Origin`/uso único no servidor (regra 4).
- **Splash/"acordando"**: o Render free dorme; a tela local faz ping em `/` e mostra animação + mensagem honesta enquanto o servidor sobe.
- **Casca**: `BrowserWindow` com `contextIsolation: true`, `nodeIntegration: false`, `webSecurity` ligado, navegação restrita ao domínio do
  app (links externos abrem no navegador do sistema), instância única, lembra tamanho/posição, bandeja (tray), iniciar com o Windows (opcional),
  notificação nativa (reaproveita as do site), badge de não lidas.
- **Compartilhar tela**: `getDisplayMedia` no Electron exige `session.setDisplayMediaRequestHandler` (escolher a tela/janela) — sem isso
  o botão falha em silêncio. Microfone/câmera: `setPermissionRequestHandler` liberando só o domínio do app.
- **Fora de escopo agora**: macOS/Linux (precisa assinatura/notarização pra atualizar no Mac), loja da Microsoft, mobile (PWA/Capacitor
  é outra rodada), Rich Presence.
- **Repo/Release**: se o repositório for privado, o `electron-updater` não baixa sem token — publicar os Releases num repo público só de
  binários ou tornar o de releases público.

Ordem de trabalho: (1) casca mínima abrindo o Render; (2) tela de login animada + splash; (3) deep link `panteao://` + rota de troca no Flask;
(4) electron-builder gerando o instalador; (5) auto-update via GitHub Releases; (6) tray/notificações/captura de tela.
Testar sempre com duas contas (regra 6) e com o Render dormindo.

## Rodada 8 de 06/10/2026 — mobile (só CSS/JS em `chat.html`, abaixo de 720px) + responder mensagem

Tudo mobile vive em 3 blocos no fim do `chat.html`: CSS "MOBILE" (fim do último `<style>`, dentro de `@media (max-width: 720px)`; fora do
media só a lista que **esconde** os elementos mobile no desktop) e 3 `<script>` no fim do `<body>` (navegação, botão de ação do mapa, toque longo/membros/
teclado/configurações, e responder). Não cria telas novas: chama o que o desktop já usa (`switchMainView`, `#btn-mercado`...).

- **Barra inferior de 5 slots**: 1 Servidores (painel: faixa de bolinhas + canais), 2 Chat do canal atual, 3 **multi-uso** (Radar/Loja/Passe: toque
  abre o triângulo, arrastar pra cima e soltar também seleciona; com call vira losango e a Call ocupa o vértice de baixo), 4 Amigos/DMs (painel),
  5 Você (folha: perfil, inventário, configurações, mic, fone, sair). Os painéis são as sidebars do desktop em `position: fixed`
  (`body[data-painel]`); clique **confiável** (`e.isTrusted`) num canal/DM fecha o painel — o app clica sozinho no 1º canal ao entrar no servidor.
- **Botão de ação do Radar** (`#mob-fab`): arrasta pros 4 cantos, abre fantasma/nota/plantar em leque; no canto de baixo-direita sobe acima dos
  controles do Leaflet (mede `.leaflet-bottom.leaflet-right .leaflet-control`). O cabeçalho do Radar no celular só tem título + caixa de entrada.
- **Armadilhas**: `.discord-app` tem `z-index:1` (contexto de empilhamento): tudo que fica dentro dele (sidebar de membros) fica **abaixo** da barra
  (`z-index:1300`), por isso a folha de membros usa `bottom: var(--nav-h)`. A barra de baixo **só some com teclado de verdade** (janela encolheu >150px);
  esconder por "campo focado" sumia a barra na DM, que abre com o cursor no texto. `interactive-widget=resizes-content` no viewport.
- **Mensagem**: toque longo abre o menu como folha (reações rápidas no topo); a barra de hover (`.msg-actions`) some no celular. Config: tela cheia com
  abas rolando de lado, alça no topo (puxar pra baixo fecha), botão "Pré-visualização" mostra só o cartão por cima. Cartão de perfil abre centralizado.
- **Responder (canal e DM, desktop e celular)**: `Message.reply_to_id` e `DirectMessage.reply_to_id` (inteiro **sem FK**: apagar a original não apaga a
  resposta; o cliente mostra "Mensagem apagada"). O cliente manda só `reply_to` (id); o **servidor** valida que é do mesmo canal/conversa e monta o
  resumo (`resumos_de_resposta_canal/_dm` em `utils.py`) — nunca confia no texto do navegador. Gatilhos: seta ao passar o mouse, item "Responder" do menu,
  Alt+clique, triplo clique (opção em Configurações > Geral > Mensagens, `localStorage pnt_resp_triplo`), arrastar pra direita (celular). Teste:
  `python testes/fumaca_resposta.py`. **Rodar `python atualizar_banco.py` depois do deploy** (a rede de segurança do boot também cria as colunas).
- **Instalar (`/entrar`) por plataforma**: Windows → botão que baixa o `.exe` mais novo (API do GitHub em `AqueleSales/panteao-releases`, cai no
  `/releases/latest` se a API falhar; o instalador **não é assinado**, a página avisa do SmartScreen); Android/Chrome → botão do `beforeinstallprompt`
  (ou passo a passo); iPhone → passo a passo do Safari; navegador embutido (Instagram...) → "Abrir no Chrome". `/entrar?instalar=1` mostra a página
  mesmo logado (a home usa isso no "Baixar o app"). A home (`index.html`) é standalone, sem `base.html`. `bazinga_awards_url` **não existe** em nenhum
  context processor (o link vinha vazio): sem ela o cartão vira um bloco sem link.
- **Login que falha não vira "Erro interno"**: `auth.callback` captura erro do OAuth (estado que não bate, sessão expirada, Google recusou) e volta pra
  `/entrar?erro=login` com aviso; existe um handler 500 próprio (HTML simples; `/api/*` devolve JSON).
- **Largura das barras laterais**: `.left-sidebar-wrapper` é `calc(72px + var(--w-canais))`. Era `312px` fixo: arrastar a barra de DMs pra mais larga
  vazava pra baixo do mapa e a alça (que fica na borda) sumia, sem como arrastar de volta.
- **O layout de celular não depende só da largura**: `@media (max-width: 720px), (pointer: coarse) and (max-device-width: 820px)` (e `MOBILE_Q` no JS, mesma regra). Assim vale também quando o navegador/PWA abre em "Versão para computador" (viewport 980, tudo "zoom out"); o chat ainda avisa uma vez por sessão nesse caso.
- **Escala do celular**: bloco "escala do celular" no CSS mobile (cabeçalhos 58px, fotos de DM 52px, campo de mensagem 58px, textos 16.5–17px). O "Amigos" do painel de conversas é um título com atalho "Abrir ›" (o `#btn-amigos::after` do desktop é um brilho absoluto: sobrescrito com `!important`).
- **Rumo no mapa (só celular)**: leque azul suave no avatar apontando pra onde o aparelho aponta (`deviceorientationabsolute` no Android, `webkitCompassHeading` no iPhone, que pede permissão num toque). Não testado em aparelho.
- X das notas do mapa: 28px no desktop, 40px no celular, com área de toque maior que o desenho.
- **Radar** é o alvo azul (`.ic-radar`), Loja rosa (`.ic-loja`), Passe dourado (`.ic-passe`) em todo lugar; Loja/Passe mexem no hover/ativo.
- **Notificações push (Web Push, 06/10/2026)**: `app/push.py` (pywebpush). Chaves VAPID: `VAPID_PRIVATE_KEY`/`VAPID_PUBLIC_KEY` do ambiente ou,
  sem elas, geradas no 1º uso e guardadas na tabela `config_app` (**não precisa configurar nada no Render**; `VAPID_SUBJECT` é opcional). Tabelas novas
  `push_sub` (um aparelho por linha, `endpoint` único: outra conta no mesmo aparelho assume a inscrição) e `config_app` nascem pelo `create_all`.
  O cliente avisa `visibilidade` (aba visível ou não) e o servidor **só manda push se nenhuma aba da pessoa está visível** e ela não está em "Não perturbar"
  (`push_se_ausente()` em `events.py`; `criar_notificacao()` e `chamar_amigo` chamam). DM, menção, amizade e "está te ligando" viram push; offline +
  tentou ligar vira "Ligação perdida". Inscrição que o navegador recusa (404/410) é apagada. Sair da conta solta o aparelho (`pushSairAntes`), senão os
  avisos da conta velha continuariam chegando. Toque na notificação abre `/chat?dm=<id>` (ou `postMessage` pra aba aberta). **iPhone**: só funciona com o
  app instalado na Tela de Início (iOS 16.4+). O app do Windows (Electron) não usa (sem service worker; tem aviso próprio). Teste: `python testes/fumaca_push.py`
  (envio real não é testado: `pywebpush.webpush` é trocado por um registrador).
- **Insígnias (07/10/2026)**: 6 em `cosmeticos.CATALOGO` (ordem do cartão): Criador (capacete de obra; no popover é uma pilha de 9 camadas em `translateZ` que gira
  em `rotateY` = objeto 3D, `svgBadge3D`), Alpha Tester (capacete romano; olhos vermelhos em flash), Beta Tester (Medusa dormindo; acorda e volta a dormir), BAZINGA
  (símbolo dos Lanternas Verdes, "on top!"; partículas -> explosão -> aura), Coder, Só nós (sarça ardente; raio -> fogo). **Desenhos finais (07/10)**: Alpha = capacete
  espartano de crista vermelha alta (crista balança sempre; brilho varre o ouro e olhos vermelhos em flash no zoom); Beta = Medusa magra e sombria (dormindo parece pedra;
  no zoom acorda num bote com olhos amarelos, boca com presas e 11 cobras com presas, depois volta a dormir); Só nós = arbusto verde envolto em fogo, raio no zoom.
  **Arte é vetor desenhado à mão no JS**: um PNG de 46 px (capacete) não serve (borrado, com halo branco) — se o dono mandar arte melhor (>= 400 px, fundo transparente, de
  fonte que ele possa usar), dá pra usar `<image>` no SVG com a animação por cima. O dono (`@aquele.sales`) e `@filippo.chiarion` também têm Alpha, via `LABORATORIO`. "No zoom" = popover `.orb-grande`
  (animação em loop) e, nas pequenas, `:hover`. **Quem recebe**: Beta = **todo mundo** (`posses_com_regras()` no `/chat`, 1 escrita só na 1ª vez);
  BAZINGA = membro do servidor cujo id está em `config_app.servidor_bazinga_id` (ou env `BAZINGA_SERVER_ID`) — **por ID, nunca por nome** (qualquer um cria um servidor
  "Bazinga"); Alpha = lista `ALPHA_NOMES` por nome de exibição, concedida só no `atualizar_banco.py` passo 26 (nome repetido ou não achado vira aviso; use
  `conceder_item.py <@usuario> badge:alpha_tester`). O passo 26 também define o servidor Bazinga (o mais antigo com esse nome: **confira o id impresso**) e dá beta/BAZINGA
  a quem já existe. A insígnia não é retirada se a pessoa sair do servidor. O "!" do cartão só aparece abaixo do nível 10. Teste: `python testes/fumaca_insignias.py`.
- **Não testado ao vivo**: toque longo, arrastar pro lado, teclado, call, rumo (bússola) e entrega real de push em celular; losango com call real.
- **Ideias combinadas e ainda não feitas**: APK/Play Store (TWA via PWABuilder/Bubblewrap: precisa conta de dev US$25 + `assetlinks.json` + ícones maiores; **não melhora
  desempenho nem layout**, só dá presença na loja); IPA na App Store (Mac + US$99/ano); chave Google Geolocation no `desktop/config.json` pra o app do Windows achar a posição
  por Wi-Fi (sem ela cai no IP, que erra); aumentar `RAIO_SERVIDORES_M` se o dono quiser; assinatura de código do instalador; seletor completo de emoji com fonte Twemoji
  hospedada (`app/static/fonts/twemoji.woff2` já está lá e entra na pilha de fontes).

## Rodada 9 de 07/10/2026 — localização no desktop pelo navegador + ajustes do celular (não testados em aparelho)

- **Desktop sem posição**: o Electron não tem o provedor de rede do Google (o Chrome tem, com a chave dele, que não dá pra usar). Além de Windows/Google
  (chave própria no `config.json`), há a **ponte pelo navegador**: `localizacao:navegador` (IPC) abre `/localizacao-desktop?n=<código de uso único>` no navegador do
  sistema, ele acha a posição e volta por `panteao://localizacao?n&lat&lng&acc` (`tratarLocalizacao` em `desktop/main.js`: confere o código, 5 min, uso único). O cliente
  guarda 3 h em `localStorage pnt_loc_navegador`. Aparece como confirmação quando só há posição por IP e em Configurações > Geral. **Exige instalador novo** (preload/main).
- Celular: botão de enviar no canal (`#btn-enviar-canal`), Enter quebra linha em teclado de toque (`tecladoDeToque()`), `autoCrescer` volta ao tamanho do CSS quando vazio,
  pedido de amizade com 3 botões só de ícone (`.rot` escondido) e **relógio HH:MM:SS** (`expiraEmTexto`, 1 s), busca de amigos em quadrado/tela expandida, `theme-color`
  (status bar) = `--bg-primary`, e botão voltar do aparelho (`popstate` no último `<script>`: fecha o que está aberto, volta ao Radar, só sai com 2 toques).
- Call: `vigiarConexaoDaCall` avisa quando a mídia não conecta (`failed`). Áudio mudo com todo mundo "na call" = quase sempre falta TURN próprio (`TURN_URLS` no Render).

---

## Rodada 10 de 08/10/2026 — Armazém (loja do app em DRC) + livro-razão

Decisões do dono (conversa de 08/10): **Armazém = só DRC** (cosméticos do app, pacotes por tema); **Bazar = 100% Pix, dinheiro real**,
começando pelo **modelo A** (classificados: o app mostra loja/produto, as pessoas combinam no chat e pagam Pix direto, sem escrow) — o
**modelo B** (checkout com gateway + split + retenção até a entrega) vem depois; **carteira virtual com dinheiro real: NÃO fazer** (guardar
dinheiro de terceiros é atividade regulada; o caminho seguro é split do gateway). **DRC só se ganha no app**: sem comprar com dinheiro, sem
transferir, sem sacar. Temas de jogos/animes de terceiros (TF2, JJK...) entram só como **arte original que evoca** (nada de símbolo/sprite deles).

### O que existe
- **`app/loja.py`** (sem socket; os handlers `listar_loja`/`comprar_item` moram em `events.py`). À venda = item do `CATALOGO` com campo `preco`
  (`_item(..., preco=350)` em `cosmeticos.py`); tema da loja = `TEMAS[x]['loja'] = True` (com `cores`, `icone`, `lema`). Laboratório e
  insígnias **não têm preço**, então nunca aparecem. `PRATELEIRAS` (ordem dos tipos) e `DESTAQUES` (slides do topo) ficam no próprio loja.py.
- **Compra = UMA transação** (`comprar()` dentro de `comitar_com_retry`): relê a posse, calcula o preço **no servidor**, debita com
  `UPDATE person SET bazinga_coins = coalesce(..) - :p WHERE id = :id AND coalesce(..) >= :p` (confere o saldo do **banco**, não o do objeto em memória:
  duas abas/clique duplo nunca gastam o mesmo DRC duas vezes), escreve a `Posse` (origem `loja`) e o `MovimentoDrc`. `Posse` é única por
  pessoa+item: se dois pedidos entregarem o mesmo item, o 2º dá `IntegrityError`, a transação inteira desfaz (inclusive o débito) e vira "você já tem".
  O cliente manda só `item_id` (+ `preco_esperado` opcional: se o preço mudou no meio, o servidor recusa e manda a vitrine corrigida). Freio de 0,6 s por pessoa.
- **Pacote**: `pacote:<tema>` entrega ele + os itens avulsos do tema que a pessoa ainda não tem. Preço = preço do pacote abatido **em proporção** do que
  ela já tem avulso (`preco_para()`); se já tem tudo, sai por 0 (só pra constar e poder "equipar tudo"; não escreve movimento de 0).
- **Livro-razão**: tabela `movimento_drc` (nasce pelo `create_all`, sem ALTER), uma linha imutável por movimento (`delta`, `saldo_apos`, `motivo`
  `compra|nivel|ajuste`, `ref`). Hoje grava compras e o ganho por nível (`_somar_xp`). `Person.bazinga_coins` continua sendo o saldo de leitura.
  **Todo novo jeito de ganhar/gastar DRC precisa escrever aqui** (e gastar passa pelo UPDATE condicional, nunca "ler, subtrair, gravar").
- **Regra 6**: `compra_ok`, `saldo_atualizado`, `loja` e `inventario` vão pra `sala_pessoal` (todas as abas de quem comprou). O cliente só marca "seu" quando o servidor confirma.
- **A rota antiga `/api/produtos/<id>/comprar` morreu (410)**: era "ler saldo, subtrair, gravar" (corrida) e só gravava um `Purchase` sem entregar nada.
  `/api/produtos` agora lista só o **Bazar** (`is_official` falso). A trava "comprar exige localização ligada" valia pra essa rota; **o Armazém não exige**
  (cosmético não tem nada a ver com onde a pessoa está) — quando o Bazar físico/Pix vier, a trava volta lá. `seed_loja.py` ainda cria os produtos-placebo
  antigos (`is_official`): não aparecem mais em lugar nenhum e podem ser removidos.

### Vitrine (`loja.js` + `loja.css`)
- Desenha tudo a partir do evento `loja`; nunca calcula preço/posse/saldo. Hero em carrossel (scroll-snap nativo, autoplay de 7 s que pausa com mouse/aba
  escondida/modal aberto, parallax por `transform`), filtro por tema (**a vitrine inteira troca `--a/--b/--c`** conforme o tema), prateleiras horizontais
  com setas, cartão de item com prévia **na foto/nome da própria pessoa** (reusa `Cosm.previaItem`), modal do item/pacote (conteúdo do pacote, "faz parte do pacote X",
  preço riscado + % de desconto, "faltam N DRC", comprar, equipar/tirar, confete tema-colorido ao comprar). Celular: modal vira folha, hero empilha.
- Visual combinado com o dono: **chapado e fosco** (borda grossa, sombra "dura" sem desfoque, um bloco de cor por tema), **sem vidro/blur/brilho que vaza/degradê de enfeite**.
  Só `transform`/`opacity` se mexem; prévias dos cartões só animam com o mouse em cima (mesma regra do inventário). A paleta geral do app **ainda não foi decidida**:
  a loja usa as variáveis do app (`--bg-*`, `--text-*`) e o tema dá o acento, então acompanha o que o dono escolher.
- `.arm-hero` usa **container query** (`@container (max-width: 880px)`): com as barras laterais abertas o mini-perfil some e a arte centraliza.
- ~~Pegadinha: tema novo entra em `TEMAS_COSM` e `NOME_TEMA`~~ — **resolvido na Rodada 13**: o servidor manda `temas` (nome e cor de todo `cosmeticos.TEMAS`) no payload do inventário e o cliente usa isso; as duas tabelas do cliente ficaram só como reserva dos temas antigos (não precisa mexer nelas pra tema novo).

### Temas à venda (arte original, tudo CSS, em `cosmeticos.css`, seção "LOJA")
- **Relojoaria** (latão): moldura "Relógio de Bolso" (a caixa de latão gira o brilho; de tempos em tempos o anel "abre" pra fora, some, aparecem as 12 marcas
  das horas e ele volta a fechar), nome "Tique-Taque" (avança aos tiques), placa "Engrenagens" (cremalheira aos tiques), faixa "Mecanismo" (ponteiro varrendo).
- **Dualidade** (azul e vermelho): moldura "Vazio Roxo" (dois arcos se aproximam, viram roxo e explodem; usa `@property --dz/--dz-m` animáveis), nome "Azul e
  Vermelho", placa "Convergência", faixa "Colapso". (Preços da 1ª versão eram 250–350 por item e 800 o pacote; **hoje vêm de `PRECOS`**, ver Rodada 13.)
- **Criar tema novo da loja**: (1) `TEMAS[id]` com `loja: True`, `cores`, `icone`, `lema`; (2) `_item(...)` com `preco=` por tipo + `_item('pacote', id, ..., preco=)`;
  (3) CSS `.moldura-<id>`, `.placa-<id>` **+ `.user-profile-bar.placa-<id>`**, `.ne-<id>`, `.banner-anim-<id>` (e `::after` da moldura com os `inset` por contexto, como no Sasuke);
  (4) arte do hero em `ARTES` no `loja.js` (senão o tema não ganha slide, mas aparece nas prateleiras); (5) `DESTAQUES` em `loja.py`. (Passos atualizados na **Rodada 13**; os preços agora vêm de `PRECOS`, não do `preco=` solto.)
  Temas pedidos pelo grupo e ainda **não feitos**: ver a lista "O que falta" da Rodada 13.

### Calibragem e pendências da economia (**superado pela Rodada 13**: preços calibrados por conta, extrato e busca prontos; os valores abaixo são os de ANTES)
- Preço x ganho: nível 1→2 = 100 XP; cada nível paga +50 DRC (+150 a cada 5, +300 a cada 10); todo mundo nasce com 500 DRC (1 item avulso na hora). Um pacote de 800
  fica em volta do nível 8–10. **Ainda não calibrado com jogo real**: ajustar `preco=` olhando quanto o pessoal ganha por semana.
- Falta: tela de histórico de DRC (o dado já está em `movimento_drc`), busca na loja, "relíquia da semana"/estoque limitado/coleção "colete N itens", item avulso de
  tipos que ainda não têm tema (efeitos de avatar/perfil/call/radar/pin/servidor à venda), conteúdo dos outros temas, e o **Bazar modelo A** (criar loja, cadastrar produto
  com foto/vídeo/combo, personalizar a loja — que também pode virar produto do Armazém —, avaliações, denúncia com tela de revisão).
- Para o **Bazar com Pix real (modelo B)**: gateway com **split** (Mercado Pago/Asaas/Efí), KYC do vendedor, retenção até a entrega, webhook com assinatura validada, CNPJ/nota,
  código do consumidor (arrependimento de 7 dias em produto físico), LGPD e **menores de idade**. Não começar sem decidir isso.

---

## Rodada 11 de 08/10/2026 — Bazar da comunidade, modelo A (classificados, Pix direto)

Decisão do dono (ver Rodada 10): o Bazar é **100% Pix com dinheiro real** e começa no **modelo A**: o app mostra loja/produto, organiza o pedido e monta o
"Pix copia e cola", mas **o dinheiro vai direto de uma pessoa pra outra** (sem saldo, sem escrow, sem gateway). O modelo B (gateway + split + retenção) fica pra depois.
O aviso "O Panteão não guarda nem devolve pagamento" está na tela, no produto e no pedido: não esconda isso.

### Arquivos
`app/models.py` (`BazarLoja`, `BazarProduto`, `BazarPedido`, `BazarMensagem`, `BazarAvaliacao`; nascem pelo `create_all`, **sem ALTER**; a organização da tela mudou na **Rodada 12**, abaixo) · `app/bazar.py` (toda a regra, sem socket) ·
`app/bazar_events.py` (handlers `bazar_*`; importado no **fim** do `events.py` porque usa `usuario_logado`/`sala_pessoal`/`criar_notificacao` de lá) ·
`static/js/bazar.js` + `static/css/bazar.css` (objeto global `Bazar`) · `bazar_admin.py` (admin e porte) · `testes/fumaca_bazar.py` (169 verificações).

### Modelo
- **Uma loja por pessoa** (`owner_id` único). O `porte` decide a aparência: `micro` = barraca de feira (itens aglomerados na "Feira dos aldeões"), `media` = fachada com toldo/placa/vitrine,
  `grande` = parceira (faixa larga + selo). **`grande` só um admin define** (`python bazar_admin.py porte <@usuario> grande`); o dono não consegue se promover nem perde o porte editando.
- Personalização = **ids validados** (`CORES`, `TOLDOS` em `bazar.py`): nunca texto livre num `class`/`style`. Logo/banner só imagem do próprio app (Cloudinary/site/Giphy) **e sem aspas, parênteses,
  espaço, `<`, `>` ou `\`** (`_RE_URL_SEGURA`): a URL do banner vai num `style="background-image:url('...')"` e sem isso dava injeção de CSS. O cliente ainda passa por `urlCss()`.
- Produto: preço em **centavos** (R$ 1,00 a R$ 50.000,00), `tipo` físico/digital/serviço, até 5 fotos + 1 vídeo, estoque (vazio = sem limite), **combo** (até 8 itens + preço avulso só pra mostrar o desconto),
  `entrega` **privada** (link/instrução: só o comprador de um pedido já confirmado vê). Até 40 produtos ativos por loja.
- **Texto público não aceita link** (nome, descrição, propaganda, combo, conversa do pedido, recado, avaliação): `texto_tem_link()`. Só `entrega` pode ter link.
- Vender/pedir/aceitar exigem a **localização ligada** (decisão do dono, trava leve; é a mesma `localizacao_ligada()` do mapa). Ver o Bazar não exige.

### Pedido (máquina de estados, `TRANSICOES` em `bazar.py`)
`aguardando → aceito → pago → confirmado → concluido`, mais `recusado`/`cancelado`. Cada ação é `(status atual, quem age, ação)`; qualquer outra combinação é recusada com "o pedido mudou de estado".
- A troca de status é um **`UPDATE ... WHERE status = <atual>`** (duas abas, ou os dois lados agindo juntos, nunca aplicam a mesma transição duas vezes).
- **Estoque**: reservado ao **aceitar** (`UPDATE ... WHERE estoque >= qtd`, então a corrida do último item falha com "Estoque insuficiente" e o rollback devolve o pedido a `aguardando`),
  devolvido ao cancelar/recusar depois de aceito; `concluido` soma `vendidos`/`vendas`. Preço e nome do pedido são **copiados** na hora (editar o produto depois não muda o pedido).
- Limites: 1 pedido aberto por produto por comprador, 10 abertos por comprador, quantidade 1–20. Bloqueado pelo vendedor (`Friendship` `blocked`) não abre pedido.
- **Quem vê o quê** (regra 4): a chave Pix (copia e cola) só vai pro **comprador** e só com o pedido **aceito** em diante (mascarada fora do código); o vendedor nunca recebe o bloco de Pix;
  `entrega` só pro comprador com Pix **confirmado**. Terceiro não abre o pedido nem recebe nada dele. A lista (`bazar_pedidos`) nunca carrega Pix nem conversa.
- Conversa do pedido (`BazarMensagem`): só texto, 300 caracteres, 80 por pedido, só as duas pessoas. **Não usa a DM**: a DM exige amizade/servidor em comum e viraria "conversa rápida"/pedido de amizade com desconhecido.
- Avaliação: só o comprador, só `concluido`, 1 por pedido (`UNIQUE`); a média é denormalizada na loja (`nota_soma`/`nota_qtd`, atualizada num UPDATE atômico).
- **Pix**: `pix_copia_cola()` monta o BR Code estático com valor (CRC16/CCITT-FALSE, verificado com o vetor `123456789 → 29B1`); `normalizar_chave_pix()` aceita CPF (com dígito verificador), CNPJ, telefone, e-mail e chave
  aleatória (11 números que não são CPF válido e parecem celular viram `+55`). **Nunca foi colado num banco de verdade**: segue a especificação e o vetor, mas só um banco confirma (está no BACKLOG).

### Tempo real e notificações (regra 6)
Pedido mudou → `bazar_pedido` pras **duas** salas pessoais (cada ponta no seu ponto de vista) + `bazar_pendencias` (contador de "precisa de você") + notificação `bazar` na caixa de entrada (clicar abre "Meus pedidos").
Loja/produto mudou → `bazar_mudou` em broadcast (quem está olhando pede a vitrine de novo). O contador de pendências também sai no `connect` (**+1 query: reconexão 12 → 13**; `/chat` não mudou).
Erro de regra volta como `bazar_erro {msg, ref}`; erro inesperado como `erro_bazinga` (regra 3).

### Moderação (resolve a antiga "tela de revisão de denúncias")
- **Admin = id em `config_app 'admin_ids'`**, definido por **id** uma vez: `python bazar_admin.py admin <@usuario>` (`--remover` tira). Trocar o @ não passa o poder. **Depois do deploy, dê admin ao dono.**
- `denunciar` agora aceita `loja` e `produto` (além de nota/servidor/pessoa) e **só conta denúncia ainda não revisada** (`resolvida` falso): depois que um admin restaura, o alvo recomeça do zero.
  3 pessoas diferentes escondem loja/produto (`oculta`), igual às notas do mapa.
- Botão **Moderação** (só aparece pra admin, e o servidor confere a cada chamada) lista as denúncias não revisadas de loja, produto, nota, servidor e pessoa, com quem denunciou e o motivo.
  **Restaurar/Dispensar** devolve o item e dispensa as denúncias; **Remover** derruba (loja: oculta+fechada; produto: apaga, ou desativa se já teve pedido; nota/servidor: apaga). **Pessoa não é banida** (só fica registrada).
- O botão "loja" do cartão de perfil agora abre a loja do Bazar (`obter_perfil` devolve `loja_id`).

### Interface
Vitrine por porte (parceiras, lojas da vila, feira), filtro por categoria + busca (servidor, com debounce), página da loja (capa, logo, nota, propaganda, produtos, avaliações, denunciar), modal do produto
(galeria com vídeo, combo, vendedor, quantidade, recado, "como funciona"), "Meus pedidos" (comprando/vendendo), pedido com linha do tempo, Pix + QR (qrcodejs) e conversa,
editor "Minha loja" (loja com **prévia ao vivo da fachada**, produtos, upload de foto/vídeo, combo, entrega privada). Visual igual ao do Armazém: chapado, borda grossa, sombra dura, sem vidro.
O toldo é CSS puro (listras + franjas com `mask`). Celular: modais viram folha.
- **Pegadinha de nome**: o `chat.html` já tinha `.bz-radio` e outras classes `bz-*` (criação de servidor). As minhas que colidiram viraram `.bz-opcao` e `.bz-contagem`. **Antes de criar classe `bz-` nova, confira com `grep -o "\.bz-[a-z-]*" app/templates/chat.html`.**

### Legado que ficou órfão
`Product`/`Purchase`, `/api/produtos`, `/api/inventario` (compras da loja antiga) e `seed_loja.py` não aparecem mais em lugar nenhum; `carregarMercado()` virou no-op. Podem ser removidos numa limpeza (cuidado: `Purchase` é histórico de compras antigas).

---

## Rodada 12 de 08/10/2026 — Bazar reorganizado: carrossel de propagandas, feed misturado e "Minha lojinha" em página

Pedido do dono (depois de ver o Bazar da Rodada 11): a **faixa azul** do mock é a área de **propagandas** (só retângulos, em carrossel, das empresas grandes **e** do próprio Panteão);
as caixinhas, o quadrado de 4 divisões e o retângulo ficam **misturados num feed único**, em ordem embaralhada, "pra ninguém ter motivo de dizer que aparece mais que o outro";
destaque e propaganda ficam separados e identificados; quem quiser algo específico usa **filtros**; e tudo da pessoa (minha loja, pedidos, personalização, moderação) vai pra uma
**página dentro do Mercado Elite** aberta por um atalho **"Minha lojinha" ao lado das moedas** (a barra lateral do app continua).

### Servidor (`app/bazar.py`, `app/bazar_events.py`)
- **`feed(busca, categoria, tipo, seed, pagina)`** substitui a vitrine por porte. Itens: `{'t':'loja','loja':...}` (média = caixa, grande = retângulo de 2 colunas) e `{'t':'quad','produtos':[até 4]}`
  (itens de barracas "micro" de vendedores DIFERENTES: cada passada tira 1 item de cada vendedor, em ordem embaralhada). Tudo é ordenado por `md5(seed:chave)` (`_sorteio`): a **ordem é estável com a mesma
  seed** (atualizar a tela não reorganiza o feed) e **muda com outra** (botão "Embaralhar"; seed nova a cada F5). Paginado (`PAGINA_FEED = 14`): página 0 = evento `bazar_vitrine` (com propagandas,
  destaques, catálogos e flags); páginas seguintes = `bazar_feed`. O servidor devolve o `tag` que o cliente mandou (seed|filtros|busca): resposta de um filtro que já não vale é ignorada.
  Filtros: categoria, tipo (físico/digital/serviço) e busca (nome da loja, descrição ou produto; `%` e `_` não viram curinga). Loja sem produto que bata não aparece.
- **`propagandas(seed)`** = lojas de porte **"grande"** (só admin define) com o texto/banner da PRÓPRIA propaganda da loja; rotaciona por seed. Não há tabela de anúncios: promover um parceiro = `python bazar_admin.py porte <@usuario> grande`.
  As propagandas do **próprio Panteão** (Monte a sua loja / Pix direto / Armazém) são constantes no `bazar.js` (`PROPAGANDAS_CASA`); entram intercaladas com as parceiras.
- **`destaques()`** = faixa "Bem avaliadas": o critério é só a nota (e nº de avaliações, vendas), à vista de todos (`MIN_AVALIACOES_DESTAQUE = 1`; suba quando houver volume).
- `minha_loja()` agora traz `stats` (pedidos aguardando/abertos/concluídos e quanto foi concluído) pro painel.
- **Escala**: o feed lê até 300 lojas e 600 itens de barraca a cada pedido e embaralha em Python. Serve pra comunidade pequena; com milhares de lojas, mover o sorteio pro SQL/cache (BACKLOG).

### Interface (`static/js/bazar.js`, `css/bazar.css`)
- **Vistas dentro do Mercado Elite** (`irPara`): `feed` | `loja` (página da loja, substitui o feed, com "Voltar ao Bazar" e rolagem restaurada) | `painel`. Produto e pedido continuam **modais** por cima da vista atual.
- **Feed**: carrossel de propagandas (scroll-snap, autoplay 6,5 s que pausa com mouse/aba escondida/modal aberto), aviso "Como o Bazar funciona", "Bem avaliadas", filtros + "Embaralhar",
  grid `auto-fill` com `grid-auto-flow: dense` (grande ocupa 2 colunas; em coluna estreita vira 1 via **container query** em `#bazar`), rolagem infinita (IntersectionObserver + botão "Ver mais lojas").
  Mudança no Bazar enquanto a pessoa olha **não reorganiza o feed**: aparece a pílula "Há novidades na vila: atualizar".
- **Atalho "Minha lojinha"** (`#bz-meu-chip`, ao lado das moedas, também na aba do Armazém): logo + nome da loja e o selo de pendências; clicar leva ao Bazar e abre o painel.
- **Painel** (`.bz-painel`): nav à esquerda (vira abas horizontais em coluna estreita) + corpo. Seções: **Visão geral** (status, atalhos, números, checklist "Pix/produto/logo/propaganda", fachada ao vivo),
  **Produtos**, **Pedidos recebidos** (os que precisam de você primeiro), **Minhas compras**, **Personalizar** (tamanho, cor, toldo, logo, banner, propaganda + prévia), **Dados e Pix**, **Moderação** (só admin).
  Sem loja: só "Visão geral" (convite), "Personalizar", "Dados e Pix" e "Minhas compras". Salvar a 1ª vez cria a loja e leva pros produtos. Clicar numa linha de pedido abre o modal do pedido (Pix, conversa...).
- O contador de pendências do `connect` continua sendo a única consulta nova de conexão; o atalho só mostra o **logo/nome** depois que o Bazar foi aberto pelo menos uma vez (carregamento preguiçoso, de propósito).
- Notificação do Bazar abre o painel em "Minhas compras" e o pedido; se a pessoa é o vendedor, o painel troca sozinho pra "Pedidos recebidos".

---

## Rodada 13 de 08/10/2026 — Armazém: preços calibrados, +5 temas, extrato e busca

Pedido do dono: seguir com o que a Rodada 10 deixou aberto (calibrar preço, mais temas), ir salvando no BACKLOG/CLAUDE.md e **manter a lista do que ainda falta**
(a lista única está no fim da Rodada 13 do `BACKLOG.md`: leia lá antes de começar outra frente).

### Preços: uma tabela só (`PRECOS` em `cosmeticos.py`)
- `PRECOS[raridade][tipo]` (hoje `raro`: nome 350, placa 350, faixa 450, moldura 550; `epico`: 600/600/750/900). `_item_loja(tipo, id, nome, desc, tema, raridade='raro')` lê daqui;
  `_pacote_loja(tema, nome, desc)` cria o pacote **sem preço** e `recalcular_pacotes()` calcula: soma dos 4 itens × (1 − `DESCONTO_PACOTE` = 30%), arredondado a múltiplo de 50 (**1200 DRC** pros temas "raro").
  **Nunca escreva `preco=` solto num item da loja.** O pacote abate em proporção do que a pessoa já tem avulso (ver Rodada 10).
- **`python testes/calibrar_precos.py`** = a conta por trás dos números (usa as constantes REAIS de `utils.py`: XP por mensagem/minuto/bônus/missão, curva de nível, DRC por nível, mais os 500 DRC iniciais).
  Os três perfis (casual 4 dias/semana, regular 6, intenso 7) são **suposição, não medição**. Rode de novo sempre que mudar `PRECOS`, o ganho de XP/DRC ou a curva. Regras de ouro que ele confere
  (sai com código 1 se quebrar): 1 item barato no **1º dia** pra qualquer um; 1º pacote **não** no 1º dia e em até 2 semanas pro regular, **não** antes do dia 3 pro intenso, em até ~2 meses pro casual;
  o premium (2500) não vira rotina (regular só no dia 30+). Resultado de 08/10: pacote no dia **5** (regular), **4** (intenso), **43** (casual); premium no dia **41** (regular).
- **O achado que a conta mostra e que o dono ainda não decidiu**: DRC só vem de **nível**, e o nível custa cada vez mais XP, então **a renda despenca depois do 1º mês** (regular: 2200 DRC no dia 30 e só 3400 no dia 90;
  a coleção de 7 pacotes custa 8400). Proposta **não aplicada**: missão pagar DRC (10/diária + 40/semanal → regular 6910 em 90 dias; 20/80 → 10420). Se for aplicada: pagar no mesmo `_somar_xp`/transação da missão,
  escrever `MovimentoDrc` com `motivo='missao'` **e** acrescentar o rótulo em `ROTULO_MOTIVO` (`loja.py`), e rodar o script de novo.
- Os testes **leem os preços do catálogo** (nada de 800/350 digitado em `fumaca_loja.py`): mudar `PRECOS` não quebra a suíte, e um teste confere que cada tema tem preço = `PRECOS[raridade][tipo]` e pacote = soma −30% arredondada.

### Cinco temas novos (arte original que evoca; tudo CSS/SVG em `cosmeticos.css`, seção "LOJA, rodada 2", e `loja.js`/`loja.css` pro carrossel)
| Tema | Evoca | Moldura | Nome | Placa | Faixa |
|---|---|---|---|---|---|
| **Cubos** (`#5fa83a`/`#8b5a2b`) | mundo de blocos | Bloco de Grama (anel em segmentos) | Pixelado (verde-claro com contorno, **legível sobre a própria placa**) | Terreno | Mundo de Blocos (céu, nuvens quadradas, grama) |
| **Batida** (`#d946ef`/`#22d3ee`) | música | Equalizador (barras ciano/magenta em volta) | Refrão (pulsa) | Pista de Dança | Vinil |
| **Quadra** (`#e8742c`/`#2a5db0`) | vôlei/basquete | Bola em Jogo (bola orbitando o anel) | Saque | Rede | Quadra Cheia (linhas brancas e bola) |
| **Mira** (`#e8483f`/`#4fd1c5`) | FPS tático | Mira Travada (retículo fecha no avatar) | Tático (mono, espaçado) | Mapa Tático (grade) | Radar (varredura) |
| **Mangá** (`#e63946`/`#f1faee`) | quadrinho P&B + 1 cor | Traço de Tinta | Onomatopeia | Retícula (pontos de trama) | Página de Mangá (linhas de velocidade e sol vermelho) |

- Cada tema tem moldura, nome, placa, faixa e pacote, **arte própria no carrossel do Armazém** (`ARTES` em `loja.js`: cubo flutuando, vinil + equalizador, bola quicando com sombra, mira travando, explosão de mangá) e **slide próprio** em `DESTAQUES`
  (`loja.py`). Verificados no cartão de perfil, na barra do usuário e na loja (navegador da pane).
- **Criar tema novo agora** (substitui a lista da Rodada 10): (1) `TEMAS[id]` com `loja: True`, `cores`, `icone`, `lema`; (2) 4× `_item_loja(...)` + `_pacote_loja(...)` (o preço é automático); (3) CSS `.moldura-<id>::before`,
  `.ne-<id>`, `.placa-<id>` **+ `.user-profile-bar.placa-<id>`**, `.banner-anim-<id>`; (4) `ARTES[<id>]` em `loja.js` (+ CSS da arte em `loja.css`); (5) slide em `DESTAQUES`. **Não** precisa mais mexer em `TEMAS_COSM`/`NOME_TEMA`
  (o servidor manda os temas no payload do inventário). O `fumaca_loja.py` falha se faltar CSS, `ARTES` ou slide de algum tema da loja.
- **Pegadinha de contraste (Cubos)**: o nome tinha quase a cor da própria placa e sumia. Nome e placa do **mesmo tema** vão aparecer juntos na lista de membros/barra do usuário: confira o par, não cada um sozinho
  (a correção foi paleta mais clara + `-webkit-text-stroke` escuro).
- Pegadinhas de CSS que se repetiram: `@property` pra animar variável (`--dz`, `--mg`, `--bp-angulo`); disco que não depende do tamanho do banner = `radial-gradient(circle closest-side ...)`; moldura e placa com
  `!important` na barra do usuário (já estava na Rodada 5).

### Extrato (histórico de DRC) e busca
- `loja.extrato(pessoa, limite=60)` lê o `MovimentoDrc` **só da própria pessoa** (nunca recebe id de outra) e devolve `saldo`, `ganho_total`, `gasto_total` e os últimos movimentos (título = nome do item comprado ou "Nível N" / "Níveis a a b").
  Evento `listar_movimentos` → `movimentos` (`events.py`; sem login não responde). Botão **Extrato** no Armazém abre o modal (`Loja.extrato`).
- Busca do Armazém (`#arm-busca`, 40 caracteres): filtra item/tema **no cliente** em cima do que a vitrine já mandou (sem ida ao servidor).

### Estado do teste (08/10/2026)
Toda a suíte passou: `fumaca_loja` (164 verificações), `fumaca_bazar` (169), `fumaca_cosmeticos`, `fumaca_social`, `fumaca_servidor`, `fumaca_conversa_rapida`, `fumaca_rodada3`, `fumaca_call`, `fumaca_localizacao`,
`fumaca_resposta`, `fumaca_push`, `fumaca_insignias`, `fumaca_desktop`; e `calibrar_precos.py` com as 5 regras OK. **Rode com o Python do venv (`.venv\Scripts\python.exe`)**: o `python` do PATH não tem o Flask.
**Não testado**: Neon, 2 pessoas reais, celular real, Electron/PWA, nada visto no monitor do dono (só na pane: ~800 px e 375 px).
**Nada desta rodada foi commitado** (nem as Rodadas 10–12): `git status` mostra tudo como modificado/novo.

### O que ainda falta (resumo; a lista completa e atualizada fica no `BACKLOG.md`)
Decisão do dono: DRC por missão (renda cai depois do mês 1) · paleta geral do app · trocar sons/arte de DBZ/Naruto antes da loja pública.
Conteúdo: temas Brawlhalla, LoL, SNK, JoJo-like, Umamusume, Rematch, Roblox-like, Marvel Rivals-like, Blue Lock-like, TF2-like · efeitos avulsos à venda (avatar/perfil/fala/radar/pin/servidor/som) · relíquia da semana, estoque limitado, "colete N".
Limpeza: legado `Product`/`Purchase`/`/api/produtos`/`seed_loja.py`.
Teste/deploy: Neon + 2 pessoas reais · `atualizar_banco.py` e `bazar_admin.py admin aquele.sales` depois do deploy · Pix copia e cola num banco de verdade · dados reais pra recalibrar · Electron/PWA.
Bazar: modelo B (gateway/split/escrow/KYC/CNPJ/CDC/LGPD/menores), disputa, banimento, moderação de mídia, frete, loja no mapa, favoritos, reputação, anúncios com arte/datas/cliques, feed em escala.

---

## Rodada 14 de 08/10/2026 — DRC por missão, relíquia da semana, edições limitadas, coleção e limpeza do legado

Testada com SQLite descartável + navegador da pane (solo); **nada no Neon, nada com 2 pessoas reais**. Teste novo: `python testes/fumaca_economia.py` (205 verificações).
- **Missão paga DRC** (`DRC_POR_MISSAO` em `utils.py`: 10 diária, 40 semanal; o dono não aprovou explicitamente, apliquei a proposta conservadora da Rodada 13: dá pra mudar a constante).
  Paga na MESMA transação do XP (`_somar_xp(..., drc_missoes, ref_missoes)`), um `MovimentoDrc` `motivo='missao'` por conclusão (ref = códigos separados por vírgula), `ROTULO_MOTIVO`/`extrato` já conhecem. O cartão da missão e o toast mostram o DRC; `xp_atualizado` também atualiza o saldo do Armazém. `calibrar_precos.py` agora usa o valor real (e compara com "só níveis" e "20/80"); a regra do "premium" passou a usar o pacote épico calculado de `PRECOS` (~2000), não um 2500 inventado.
- **Relíquia da semana** (`loja.reliquia_da_semana`): 1 item avulso de tema da loja com **-25%**, troca toda segunda (horário de Brasília), determinística (embaralhamento fixo + semana absoluta; nada guardado, não repete antes de passar todas). O preço é do servidor (`_preco_com_reliquia`); tela com preço velho recebe "o preço mudou".
- **Edições limitadas** (`tema 'edicao'`, campo `limitado={'estoque', 'ate'}` no catálogo): por prazo (`ate`, naive Brasília) e/ou estoque. Estoque = tabela `loja_estoque` (nasce pelo `create_all`), `UPDATE ... WHERE vendidos < estoque` dentro da transação da compra (sem DRC ou erro depois = rollback devolve a unidade). Hoje: Pioneiro (moldura, até 31/12/2026), Lote 001 (placa, 100 un., id `lote_um`), Eclipse (faixa, 150 un.). Encerrada/esgotada continua visível, não compra.
- **Coleção** (`cosmeticos.COLECOES`): 4/12/24 itens avulsos comprados (origem `loja`, pacote não conta, os 4 que ele entrega contam) dão Colecionador (placa), Curador (moldura), Acervo (nome). Prêmio sem preço, `origem='colecao'`, concedido dentro da compra e avisado em `compra_ok.premios`.
- **Pacote** agora soma só o que ele entrega (`PACOTES[tema]`), então `efeito_servidor` (que é do servidor, não um slot) não infla o preço. `PRECOS['epico']` já tem preço pros 8 slots de efeito (ainda sem item que use).
- **Legado removido**: rotas `/api/produtos*` e `/api/inventario`, modelos `Product`/`Purchase`, `seed_loja.py`, `carregarMercado`. **As tabelas `product` e `purchase` continuam no Neon** (histórico; só o código saiu; pode dar `DROP` à mão quando quiser).
- **Pegadinha**: o id de item precisa casar `^[a-z_]{1,24}$` (o cliente descarta o resto e o preview some em branco): por isso `lote_um` e não `lote001`. O `fumaca_economia.py` confere id, CSS e registro JS de **todo** item do catálogo (vai pegar tema/efeito novo esquecido).
- UI: `loja.js` ganhou faixa da relíquia, painel da coleção, prateleira "Edição limitada", selos, contagens que andam sozinhas (`.arm-tempo[data-fim]`), modal de prêmio e botão "Aplicar a um servidor" pro efeito de servidor comprado; `previa()` do som de entrada é um `<span>` no cartão (o cartão é um `<button>`) e o "Ouvir" de verdade fica no modal.

## Rodada 15 de 08/10/2026 — filtros do Armazém por tipo/raridade/animação, raridades e 3 temas premium com efeitos

Vem de um guia (feito com Gemini) que o dono trouxe. **O que do guia foi aceito e o que foi corrigido**: aceito = 4 raridades, pacote 30% mais barato, edição limitada, os 3 temas (cyberpunk, fantasia medieval, arcade 8-bit) e os itens de cada slot; **corrigido** = (1) cosmético **só em DRC**, nunca em R$/Pix (Pix é só do Bazar entre pessoas; "R$ 4,90 por moldura" não existe); (2) nada de "Cyberpunk 2077", "Zelda/Mario", "Jarvis" (marca de terceiro): o tema é **Cyber Neon** e o de vida é "Corações de Vida"; (3) **não existe revenda de cosmético na "Vila do Bazar (P2P)"**: item do Armazém não se troca nem se vende (DRC não transfere); (4) insígnia **não se vende** (se ganha); (5) "som de notificação" e "modificação de voz" **não são slots** hoje (futuro); (6) preços do guia (150 DRC por moldura) não batem com a economia calibrada (`PRECOS`).
- **Raridades** (`cosmeticos.RARIDADES`): comum (cor lisa, sem animação) · raro (temas de 4 itens) · épico (temas premium com efeitos) · lendário (efeito de perfil dos premium + edições limitadas). `PRECOS` tem as 4 colunas; o **pacote herda a raridade dos 4 visuais**. `animado=False` marca item estático (filtro "Sem animação").
- **Tema "Básicos"** (`sem_hero` + `sem_pacote`): 8 itens comuns e estáticos (moldura/nome/placa/faixa em 2 cores), 120–180 DRC. Fora da relíquia da semana (`_candidatas_reliquia` ignora comum).
- **3 temas premium** (`TEMAS[x]['premium']`): `cyber`, `eldoria`, `arcade`, cada um com **12 itens** (moldura, nome, placa, faixa, efeito de avatar, de perfil [lendário], de fala, de radar, de chat, som de entrada, pin de nota, efeito de servidor). Pacote = 11 itens (o efeito de servidor é avulso), **3850 DRC** (regular junta no dia ~39: é o prêmio de quem tem tempo de casa; `calibrar_precos.py` agora separa "pacote normal" de "premium"). Sons de entrada sintetizados em `somEntrada`. Ids novos entram em `EFEITOS_AVATAR`/`EFEITOS_PERFIL`/`IDS_EFEITO` (o `fumaca_economia.py` falha se faltar).
- **Armazém**: a barra de chips por **tema** virou chips por **tipo** (`GRUPOS` em `loja.py`: molduras, nomes, placas, faixas, efeitos, sons, pacotes) + listas suspensas **Tema / Raridade / Animação / Ordenar** + busca + "Limpar filtros" + Extrato (alinhadas numa grade; antes quebrava em duas linhas). Qualquer filtro troca a home (hero, relíquia, coleção, prateleiras) por uma grade de resultados; os filtros ficam no `localStorage` (`pnt_arm_filtros`). Cartão e modal ganharam o selo de raridade.

## Rodada 16 de 08/10/2026 — JJK à venda (Gojo, Sukuna, Mahoraga, Combo), cortes pretos e "Efeitos de perfil" liberados nas Configurações

Pedido do dono: o "pacote do Gojo" (que na verdade era a **Dualidade**, azul e vermelho, e "parecia policial") ficou fraco; ele quis o domínio e os Seis Olhos do Gojo, o Sukuna (cortes, flecha em chamas, aura vermelha, domínio com dentes) e o Mahoraga (menos detalhado), em **todos os slots**, e um combo. **É item pra COMPRAR no Armazém, não presente** (a 1ª versão foi pro laboratório por engano; foi corrigido).
- **Temas da loja** `gojo`, `sukuna`, `mahoraga` (`premium`, **lendários**, 12 itens cada: moldura, nome, placa, faixa, efeito de avatar/perfil/fala/radar/chat, som de entrada, pin de nota, efeito de servidor) + pacote por tema (11 slots, **5050 DRC**) + **`pacote:jjk` (Combo Gojo × Sukuna)**, uma mistura escolhida a dedo em `PACOTES_FIXOS` (`cosmeticos.py`; o pacote automático só pega UM tema; o fixo precisa existir ANTES do preço ser calculado em `recalcular_pacotes`). O combo não é tema da vitrine (`TEMAS['jjk']['combo']`): aparece só em "Pacotes". `PRECOS['lendario']` agora tem os 12 tipos. `calibrar_precos.py` ganhou o degrau lendário (regular junta o pacote no dia ~60). **Dualidade segue na loja** sem mudança.
- **Nomes/referências de JJK são de terceiro.** O dono autorizou ("pode copiar"), mas não é dono dos direitos; o DRC não compra-se com dinheiro (só se ganha no app), o que reduz o risco, e a arte é CSS/SVG original que só evoca (nenhuma imagem/áudio da obra foi copiado). Se a loja virar comercial de verdade (Pix), trocar nomes por criações originais.
- **MÃOS E DEDOS FORAM REMOVIDOS** (o dono achou feio e não-realista, duas tentativas): não desenhe mão em SVG de novo sem referência melhor. O domínio do **Sukuna** (ciclo de 14 s) é: aura vermelha se expande → **muitos cortes pretos com halo branco que some** (`CORTES_SUKUNA` em `cosmeticos.js`, 17 lentes afiladas; `.sk-corte` = wrapper com `drop-shadow` branco + `::before` preto com `clip-path`; posição/ângulo/instante vêm de CSS vars) → mandíbulas de cima e de baixo com **dentes de caveira** (`dentesSvg()`: 12 dentes arredondados em curva de sorriso, gengiva escura com costelas; a de baixo é a mesma figura com `scaleY(-1)`) mordem duas vezes com clarão branco → ~4 s parado → recomeça. O do **Gojo** (12 s): aura azul → vazio de estrelas e listras de luz expande → **os Seis Olhos acendem no centro e piscam** → colapsa com clarão → ~4 s. O do **Mahoraga** (10 s): a roda de 8 encaixes (aro, raios e discos escuros nas pontas) aparece no topo, gira 45° por vez com onda dourada e o cartão pulsa em ouro no fim.
- Só `transform`/`opacity` nos domínios. Para depurar uma fase: no console, `document.getAnimations()` e `a.pause(); a.currentTime = <ms>` nos elementos do `.ef-pf-<id>`.
- **Nome do Sukuna**: `::after` é a flecha (24 px, cai pela borda de cima, pra aparecer mesmo em caixa de nome com `overflow:hidden`) e o gradiente vertical do nome sobe pra "fogo" (7 s). **Corte do Sukuna ao enviar** (`efeitoEnvio`): linha diagonal SVG; Gojo/Mahoraga usam partículas (orbes azul/roxo; losangos dourados). Sons sintetizados: `gojo` (estalo + grave + brilho), `sukuna` (2 tambores + rosnado + corte de ar), `mahoraga` (sino + 8 cliques).
- **Carrossel**: 3 slides novos no topo (`ARTES` em `loja.js`: Gojo = vazio com o ∞, os olhos e um orbe roxo; Sukuna = lua vermelha com dentes em cima e embaixo e cortes pretos; Mahoraga = a roda girando por encaixes) e 3 entradas em `DESTAQUES`.
- **Configurações > Meu Perfil > Efeitos de perfil** deixou de ser "Em breve": lista os efeitos de **cartão** e de **foto** que a pessoa tem (`desenharEfeitosDoEditor`, ligado ao evento `inventario`); clicar equipa e clicar de novo tira (`equipar_item`/`desequipar_item`, posse conferida no servidor).
- Teste: `fumaca_economia.py` (JJK: 40 itens com preço, lendários, não concedido a ninguém, combo abatido/entregue/equipado, quem não comprou não equipa, sem mão/dedo no código, >= 10 cortes) + o guarda de id/CSS/registro JS cobre os itens. Sem coluna/tabela nova, **não precisa de `conceder_item.py`**: compra-se no Armazém.
- **Visto só em prévia no navegador do painel** (linha do tempo congelada em cada fase). Falta ver no monitor: fala na call, radar no mapa, som, pin e servidor dos 3.

### Rolagem pesada ("as coisas parecem soltas ao rolar", web e app, loja e Configurações > Perfil)
Visto num vídeo do dono: a barra de rolagem andava certa, mas a imagem não acompanhava (cada bloco da loja se deslocava um tanto diferente e a "Coleção" aparecia por cima da relíquia). **Causa**: ~240 animações decorativas rodando ao mesmo tempo (giro de anel com `--bp-angulo`, `background-position`/`background-size`, `conic-gradient` animado), que **não vão pra GPU**: são redesenhadas a cada quadro pela CPU. Medido na pane: p95 do quadro 13,9 ms com elas, 8,2 ms pausadas (o `backdrop-filter` quase não pesou). **Correção**: (1) `body.rolando` (CSS no fim do último `<style>` + script no fim do `<body>` do `chat.html`) **pausa toda animação enquanto qualquer área rola** e solta 150 ms depois; (2) o carrossel do Armazém só anima o slide à vista e nada quando o hero saiu da tela (`IntersectionObserver` em `ligarHero`, classe `.parado`); (3) `.arm-prat` usa `content-visibility: auto` (prateleira fora da tela nem é desenhada). Depois: p95 7,0 ms. **Regra pro futuro**: animação nova de tema deve preferir `transform`/`opacity` (vão pra GPU); `background-position`/`size`, `--bp-angulo` e `filter` animados custam repaint, e o `body.rolando` é o que segura o custo.

### O que NÃO foi feito (retomar daqui)
(Plano antigo dos temas premium: **feito na Rodada 15 com outros temas** — cyber/eldoria/arcade em vez de boreal/petala.) Para criar mais um tema premium: cada efeito exige id em `EFEITOS_AVATAR`/`EFEITOS_PERFIL`/`IDS_EFEITO` (`cosmeticos.js`), ramo em `htmlEfeitoPerfil` e `somEntrada` (antes do bloco do gogeta), CSS `.ef-av-X`, `.ef-pf-X`, `.fala-X`, `.radar-X`, `.chat-ef-X`, `.ef-envio-X`, `.pin-X`, `.sv-ef-X` (+ `.pino-foto.sv-ef-X`), e `PRATELEIRAS` em `loja.py` precisa das prateleiras de efeito. `TEMAS_COSM` e `MOLDURAS_EXCLUSIVAS` no `chat.html` só valem pro laboratório. Depois: os 10 temas de jogo/anime, mecânicas do Bazar (favoritos, ordenação, anúncios com arte/cliques, disputa, banimento, reputação, frete) e as pendências do app (patente ao lado do nome, menção em DM, denunciar mensagem). Ver `BACKLOG.md`.

---

# Convenções

- Nomes de eventos de socket, funções e variáveis em **português**
  (`criar_servidor_discord`, `plantar_servidor`, `apagar_geonote`...).
- Emoji/toast/mensagens de UI em português informal.
- Toasts: `showToast(msg, tipo)` com `info`/`success`/`warning`/`error`.
  Para ações que envolvem o banco: toast `info` otimista ("Salvando...") no
  emit, e `success` só quando a confirmação voltar do servidor — não assuma
  sucesso no emit. (O botão de salvar perfil fazia o contrário até essa
  rodada — mostrava "sucesso" no emit em vez de esperar `perfil_atualizado`.)
- Use `openConfirmModal()` / `openInputModal()` em vez de criar modal novo
  para pergunta simples (e nunca `confirm()`/`prompt()` nativos).
- Popup de configurações (servidor ou usuário) segue sempre o mesmo molde:
  `.modal-overlay` + cartão com sidebar/conteúdo, X e ESC fecham, clique
  fora fecha. Não recriar um padrão novo de "tela cheia" pra configuração
  nenhuma — foi exatamente isso que precisou ser desfeito duas vezes.
- Referência real de terceiro (nomes como "Discord", "Krisp", "Nitro") não
  entra em texto voltado pro usuário, só em comentário técnico quando ajuda
  a explicar uma decisão (ex.: "por que não usamos o SDK da Krisp").

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
repo. Pra testar presença/amigos/chamada de DM/entrada em servidor/prévia de
call/mudança de perfil, precisa de **dois** usuários (duas abas/perfis) —
um só não reproduz nenhum bug da regra 6 (broadcast que só volta pra quem
agiu passa despercebido com um usuário só).

Se o banco de teste for um arquivo SQLite reaproveitado entre sessões (em
vez de `:memory:`), ele passa a valer a regra 1 igualzinho ao Neon: uma
coluna nova em `models.py` (`is_pinned`, por exemplo) não aparece sozinha —
rode `atualizar_banco.py` apontando pra esse arquivo antes de testar.

Lembre que o Flask **cacheia templates** com `debug=False`: depois de editar
`chat.html`, reinicie o servidor de teste ou você vai depurar a página
antiga (já aconteceu).

---

# Deploy (Render)

`Procfile`: `gunicorn -k eventlet -w 1 run:app`

- **`-k eventlet` não é opcional** — com o worker sync padrão o WebSocket não
  sobe e o Socket.IO cai para long-polling degradado.
- **Mantenha `-w 1`** — com mais de um worker as salas do Socket.IO ficariam
  divididas entre processos, e seria preciso um message queue (Redis). Isso
  agora importa ainda mais: `usuarios_conectados` (presença) vive em memória
  do processo — com mais de um worker, cada um teria sua própria contagem e
  a presença ficaria errada.

`SECRET_KEY` é obrigatória em produção: `config.py` levanta erro no boot se
faltar, em vez de cair num valor fixo que tornaria as sessões forjáveis.

`GIPHY_API_KEY` **não** é obrigatória pro boot — sem ela o site sobe normal
e só a busca de GIF (`/api/gifs`) devolve 503 com aviso claro. Configurar
em Environment no Render (a chave é grátis, ver seção "Busca de GIF").

Avatar, ícone de servidor e anexo de mensagem sobem pro **Cloudinary**
(`cloudinary.uploader`, `CLOUDINARY_URL` no env) — não fica mais em
`app/static/uploads/`, que era efêmero no Render free (sumia a cada
restart do container). Isso já resolvido; se algum código antigo ainda
referenciar `static/uploads`, é resquício a limpar, não o caminho atual.

---

# Estado atual

**`main` e `feature/persistencia-mapa-perfil-servidores` estão em sincronia**
(merge feito e enviado ao remoto em 27/09/2026) — as duas branches têm:
login/página de bloqueio, popups de configuração (servidor e usuário) de
verdade, bugs de call corrigidos + gravar/clipar, presença e lista de
membros reais, sistema de amigos real, mensagens fixadas, Ctrl+K, chamada
1-a-1 por DM, upload em Cloudinary, e a rodada mais recente: atualização
em tempo real de verdade (regra 6), latência de mensagem percebida, prévia
de call, qualidade de call automática, correções de mapa/perfil, emoji
vetorial e busca de GIF (Giphy).

**Rodada de 01/10/2026 (ainda sem commit/deploy quando isto foi escrito)**: amizade refeita
(tela de Amigos, pedido de 24h, bloqueio), DM com anexo/não lidas, caixa de entrada + som, mapa
por raio com denúncia/cópia de nota, GIF enquadrável na faixa e no fundo do cartão, emoji
completo em português, reconexão do socket e uma queda grande no número de queries. Detalhes na
seção "Rodada de 01/10/2026" e "Rodada 2" (feedback do teste: conversa rápida, Amigos simples, GIF recortado no servidor com **Pillow** - instale com `pip install -r requirements.txt`). **Fora de escopo de propósito: Mercado e Battle Pass/nível.**

**Rodada 5 (patentes, insígnias, inventário, laboratório)**: ainda sem commit/deploy quando isto foi escrito. Depois do deploy, rodar
`python atualizar_banco.py` também cria `person.equipados` e `server.efeito` e concede os itens do laboratório aos dois testers.

**Rodar `python atualizar_banco.py` depois do deploy** (colunas novas de perfil: `pronomes`, `banner_url`, `username`, `status_emoji`, `pensando`, `perfil_tema`, `nome_estilo`, `placa`, `moldura`) — essa rodada criou
a tabela `friendship`, a coluna `message.is_pinned` e, na mais recente,
`person.created_at` ("Membro desde") e, agora, `person.ghost_mode`,
`person.streak_dias`, `person.streak_em`, `person.tema`, `person.pronomes`, `person.banner_url`, `person.username` (+ índice único), `person.status_emoji`, `person.perfil_tema`, `person.nome_estilo`, `person.placa` e `person.moldura` e `person.pensando`. Configurar `GIPHY_API_KEY` no
Environment do Render (ver seção Deploy) pra busca de GIF funcionar em
produção.

## Pendências conhecidas

- **Mais faixas animadas e molduras** (combinado com o dono): hoje são 11 faixas
  (`FAIXAS_ANIMADAS`) e 6 molduras (`MOLDURAS`). A ideia é ampliar e, depois, ligar
  parte delas ao Battle Pass/loja (hoje todas são livres; "Efeitos de perfil" já
  aparecem como "Em breve"). Passos pra criar cada tipo estão na seção de perfil.
- **Estilo de nome** já aparece nas mensagens (rodada 3); a **placa** ainda não (só cartão, listas e barra).
- **Menção (@) só em canais**; DM ainda não tem.
- **Emoji nos nomes de servidor/membro** ainda usa a fonte do sistema em alguns lugares
  (`emojificar()` só roda em mensagem, status e bio).

- **Call é malha P2P (PeerJS), não SFU**: cada participante manda a
  própria mídia direto pra cada outro — upload de cada um escala com
  `N-1` participantes, então call grande ou alguém com banda ruim pesa
  pra todo mundo. O ajuste automático de bitrate (ver "Qualidade de
  câmera/tela automática") alivia mas não resolve de raiz; migrar pra um
  servidor de mídia (LiveKit/mediasoup) é projeto à parte, não um bug pra
  corrigir — precisa de infra nova (servidor, TURN, reescrever a lógica de
  call do zero no frontend).
- **Recortar GIF**: resolvido na Rodada 2 (recorte no servidor com Pillow, ver acima).
- **Twemoji não cobre o app inteiro**: `emojificar()` roda em mensagens,
  status e bio (os pontos de maior tráfego), mas não em todo lugar que
  mostra texto de usuário (ex.: nome de membro na sidebar, nota do mapa).
  Extensível — só chamar `emojificar(el)` depois de renderizar.
- **Restos de UI decorativa não-funcional no cartão de perfil**: a aba
  "Mural"/"Atividade" (só troca o sublinhado, não existe conteúdo por trás)
  e o badge "Membro Elite" (gema fixa, sem sistema de "elite" nenhum por
  trás) continuam lá — mesma categoria do "Jogando no momento" que já foi
  removido, só não chegaram a ser mexidos ainda.
- **`quality-modal-overlay` (HTML morto)**: o modal antigo de escolher
  resolução/fps do compartilhamento de tela ficou no HTML sem nada que
  abra ele mais (a escolha virou automática) — inofensivo, mas pode ser
  removido numa limpeza.
- **Sem cargo por servidor**: `pode_gerenciar_servidor()` devolve `True` só
  para o dono. É o **ponto único** a mudar quando os cargos existirem — por
  isso todo handler passa por essa função em vez de comparar `owner_id` na
  mão. Enquanto não existir, uma tela de "Cargos" seria decorativa.
- **Inventário sem UI**: a compra grava um `Purchase` e existe
  `/api/inventario`, mas o usuário compra e não vê o que tem.
- **Canais globais** (`server_id=NULL`) continuam liberados para qualquer
  logado em `pode_ver_canal()`, por compatibilidade. Não há UI que leve até
  eles. Se forem removidos de vez, dá para apertar essa checagem.
- **Revisão de denúncias**: resolvida na Rodada 11 (botão Moderação do Bazar, só admin; ver `bazar_admin.py`). Falta banir pessoa e o admin ler a conversa de um pedido em disputa.
- **Mercado/loja/bazar e Battle Pass** (economia, inventário, itens): refazer — o dono
  deixou de lado nesta rodada. A compra continua com os problemas de antes (ver "Inventário").
- **Vídeo como foto/faixa**: resolvido sem ffmpeg (ver "Vídeo (mp4/webm/mov) como foto..."). Limites: só os 6 s iniciais, sem áudio, sem escolher o trecho.
- **Girar GIF 90°** não existe (só em foto parada) — o dono pediu pra tirar o botão.
- **Menu de contexto da mensagem** (⋯) não tem "Denunciar mensagem" — só nota/servidor do mapa.
- **Clipe automático é heurística, não IA**: dispara por volume simultâneo
  de 2+ pessoas, não por análise de conteúdo. Documentado como decisão
  consciente (ver seção "Gravar e clipar a call"), não como bug.
- **Trim do clipe não recodifica**: a tela de edição só ajusta a prévia
  (in/out points); o arquivo enviado/baixado é o clipe inteiro. Cortar de
  verdade precisaria de algo como ffmpeg.wasm.
- **Decorações de perfil**: viraram o laboratório da Rodada 5 (só os dois testers). Abrir para todo mundo (loja) fica para depois da economia;
  o texto abaixo é histórico: ficaram de fora
  desta rodada por decisão — a Bazinga não tem produto tipo Nitro pra
  vender, e o card de "Apenas usuários Nitro" foi removido em vez de virar
  outra trava. Se um dia existir alguma forma de desbloquear isso (badge de
  conquista, por exemplo), o lugar certo é `.decoration-grid` em `set-perfis`.
