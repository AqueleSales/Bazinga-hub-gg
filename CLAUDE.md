# Bazinga Hub

Clone do Discord em Flask + Socket.IO, com um diferencial: um mapa (Leaflet)
onde os usuários "plantam" servidores e deixam notas geolocalizadas.

## Stack

- **Backend**: Flask, Flask-SQLAlchemy, Flask-SocketIO (eventlet), Authlib (login Google OAuth)
- **Banco**: Neon (Postgres serverless) em produção. `config.py` usa `NullPool` —
  **toda query abre uma conexão nova**. Isso causa falhas intermitentes de
  "cold start" (Neon "acordando"). Veja `com_retry()` abaixo.
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
| `app/events.py` | ~52 handlers de Socket.IO (`@socketio.on(...)`) |
| `app/main/routes.py` | Rotas REST (`/chat`, `/api/...`, `/convite/<code>`) |
| `app/auth/routes.py` | Login Google OAuth |
| `app/templates/chat.html` | O app inteiro (HTML+CSS+JS) — ~8100 linhas |
| `app/templates/entrar.html` | Página de bloqueio/login (ver seção) |
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

~52 handlers em `events.py`. Agrupados:

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
`/api/upload` · `/api/gifs?q=<busca>`

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

**Rodar `python atualizar_banco.py` depois do deploy** — essa rodada criou
a tabela `friendship`, a coluna `message.is_pinned` e, na mais recente,
`person.created_at` ("Membro desde"). Configurar `GIPHY_API_KEY` no
Environment do Render (ver seção Deploy) pra busca de GIF funcionar em
produção.

## Pendências conhecidas

- **Call é malha P2P (PeerJS), não SFU**: cada participante manda a
  própria mídia direto pra cada outro — upload de cada um escala com
  `N-1` participantes, então call grande ou alguém com banda ruim pesa
  pra todo mundo. O ajuste automático de bitrate (ver "Qualidade de
  câmera/tela automática") alivia mas não resolve de raiz; migrar pra um
  servidor de mídia (LiveKit/mediasoup) é projeto à parte, não um bug pra
  corrigir — precisa de infra nova (servidor, TURN, reescrever a lógica de
  call do zero no frontend).
- **Recortar GIF perdendo a animação**: o editor de avatar mostra o GIF
  animado de verdade antes de confirmar, mas não deixa cortar/girar
  mantendo a animação (canvas só captura um quadro). Precisaria de uma lib
  de decode+reencode de GIF (tipo `gif.js`) - ver seção Editor de imagem.
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
- **Modo Fantasma** salva só no `localStorage`, não no banco (troca de
  aparelho e volta ligado); o duplo clique no mapa ("teletransporte") ainda
  emite a posição sem checar o modo; e ativar o fantasma não remove seu
  marcador de quem já te via — só para de atualizar.
- **Canais globais** (`server_id=NULL`) continuam liberados para qualquer
  logado em `pode_ver_canal()`, por compatibilidade. Não há UI que leve até
  eles. Se forem removidos de vez, dá para apertar essa checagem.
- **Remover amigo sem UI dedicada**: o evento `remover_amigo` existe e
  funciona, mas não tem botão/menu que chame ele ainda.
- **Clipe automático é heurística, não IA**: dispara por volume simultâneo
  de 2+ pessoas, não por análise de conteúdo. Documentado como decisão
  consciente (ver seção "Gravar e clipar a call"), não como bug.
- **Trim do clipe não recodifica**: a tela de edição só ajusta a prévia
  (in/out points); o arquivo enviado/baixado é o clipe inteiro. Cortar de
  verdade precisaria de algo como ffmpeg.wasm.
- **Decorações de perfil (efeitos, molduras, badges)** ficaram de fora
  desta rodada por decisão — a Bazinga não tem produto tipo Nitro pra
  vender, e o card de "Apenas usuários Nitro" foi removido em vez de virar
  outra trava. Se um dia existir alguma forma de desbloquear isso (badge de
  conquista, por exemplo), o lugar certo é `.decoration-grid` em `set-perfis`.
