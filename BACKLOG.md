# Backlog (atualizado em 08/10/2026 — Armazém e Bazar nas Rodadas 10 a 13, no fim deste arquivo)

Mercado, loja, bazar, economia e Battle Pass/nível ficam de fora por decisão do dono —
vão ser refeitos depois com conteúdo novo. O resto da lista da rodada de teste foi feito
(detalhes em `CLAUDE.md`, seção "Rodada de 01/10/2026"). Marque aqui o que ainda falta.

## Feito nesta rodada
- [x] Faixa não salvava GIF do Giphy; agora salva + GIF enquadrável (arrastar/zoom/espelhar) na
      faixa e no fundo do cartão; novo editor `painel`.
- [x] Mensagens: 50 mais recentes (não mais antigas) + paginação; reconexão do socket;
      foto aparece na hora; agrupamento por id; menu ⋯.
- [x] Amizade: tela própria (Disponível/Todos/Pendente/Bloqueados/Adicionar), pedido de 24h,
      Aceitar/Recusar/Bloquear, "aguardando" pra quem enviou, remover/bloquear/desbloquear.
- [x] Anotações com ícone próprio.
- [x] DM: compositor completo (emoji, GIF, foto/vídeo, enviar), não lidas, som, toast, título da aba.
- [x] Caixa de entrada funcionando (DM, pedido de amizade, menção).
- [x] Presença consistente (lista, cabeçalho da DM, tela de Amigos).
- [x] Emoji: catálogo completo (Emoji 17, português) em chat, DM, status, nota, evento, reações.
- [x] Nota: emoji vira o ícone do balão; **a duração agora vale** (notas somem no prazo).
- [x] Mapa: raio de privacidade + ondas, rolagem presa, servidor com alcance maior, notas abrem
      sozinhas 5s com X vermelho, copiar nota, denunciar nota/servidor, painel do servidor refeito,
      sem ícones de ligar no Radar.
- [x] Perfil: X fixo, barra de rolagem, "+" no hover, cartão mais redondo.
- [x] Velocidade: queries por carga cortadas (22→9, 46→11, 20→8) + libs pesadas fora do caminho crítico.

## Rodada 2 (feedback do teste) - feito
- [x] Nota só abre por clique ou sozinha ao chegar perto (sem hover), card retangular com o tempo inteiro.
- [x] Copiar nota: você escolhe o ponto no mapa (dentro do alcance).
- [x] Notas antigas sem prazo somem (servidor ignora + `atualizar_banco.py` apaga).
- [x] Amigos simples (Todos | Online, busca, pedidos em cima, bloqueados no fim).
- [x] Nome de exibição repetido não escolhe pessoa errada (pede o @).
- [x] Conversa rápida: mensagem pra desconhecido = pedido temporário de 24h; cada lado fecha só do seu
      lado; mensagens somem em 24h; quem puxou não bloqueia, quem recebeu decide.
- [x] Botões de ligar/vídeo/⋮ da DM funcionando (menu: silenciar, convidar, denunciar, copiar, bloquear...).
- [x] Anotações sem botão de ligar (e cabeçalho certo).
- [x] Texto grande rola (marquee) em listas, cabeçalho e cartão.
- [x] Cartão: menu ⋯ não corta, balão grafite, mais legível sobre imagem clara, moldura quadrada some.
- [x] GIF editável em avatar/ícone/faixa/fundo (servidor recorta, mantém animação); sem arrastar-fantasma.
- [x] Caixa de entrada também no cabeçalho do servidor.
- [x] Efeitos sonoros: XP, nível, missão, entrar/sair da call, toque de chamada e "chamando".
- [x] Prévia de foto/vídeo antes de enviar (canal e DM) e clique pra ver grande.

## Rodada 3 - feito
- [x] Marquee do "Conversa rápida": sobra de 1-2 px agora rola (medida fracionária em `mqAvaliar`).
- [x] Vídeo (mp4/webm/mov) como foto, ícone, faixa e fundo: navegador extrai quadros + Pillow monta WebP animado (sem ffmpeg).
- [x] GIF de 5-10 MB não era barrado antes de chegar na rota (teto de upload por rota).

## Rodada 4 (feedback 02/10) - feito, AINDA SEM TESTE COM 2 PESSOAS REAIS
- [x] Emoji gigante no cabeçalho da DM; Enter/Shift+Enter (textarea); limites de caracteres (nome, servidor, canal, nota, status).
- [x] Call virou janela flutuante (mini arrasta/redimensiona, cheia, volta ao navegar); DM chama com cartão no canto.
- [x] Câmera não chegava aos outros (faixa reserva + `estado_camera`); tela própria sem espelho infinito; zoom na tela alheia.
- [x] Barra do usuário limpa; submenus do mic/fone não fecham; toggles de ruído/eco/ganho funcionam; teste de mic; um jeito só de mudar status.
- [x] Convite por qualquer membro + e-mail (Gmail/mailto). Moldura e estilo do nome nas mensagens; moldura na call.
- [x] Mapa: amigos aparecem (mesmo sem servidor em comum), notas de amigos no alcance grande, GPS sem fallback silencioso.
- [x] Missões em cartões estilo Quests; barras laterais redimensionáveis.

## Rodada 5 (02/10) - patentes, insígnias, inventário e laboratório - feito, AINDA SEM TESTE COM 2 PESSOAS REAIS NO NAVEGADOR
- [x] Nível 1–1000+ (curva antiga até o 100, depois +25 XP/nível; 1000+ com passo fixo) e 12 patentes com ícone SVG animado + popover "orb".
- [x] Insígnias Criador, Beta Tester, Coder e "Só nós" (duas chamas que se fundem no hover).
- [x] Catálogo + posse (`Posse`), `equipar_item`/`desequipar_item`/`listar_inventario`, checagem no servidor, `conceder_item.py`.
- [x] Inventário (Configurações e atalho embaixo do Mercado Elite), galeria de patentes, pacotes de tema.
- [x] Laboratório Gogeta/Sasuke/Fusão: moldura, placa, nome, faixa, aura de avatar, efeito de perfil, efeito de fala, radar, chat, som de entrada, pin de nota, efeito de servidor.
- [ ] **Testar com 2 pessoas no navegador**: equipar o pacote e ver (um no outro) cartão, mensagens, call (efeito de fala/aura), mapa (pin), som de entrada.
- [ ] Rodar `python atualizar_banco.py` no deploy (colunas `person.equipados` e `server.efeito` + concede o laboratório).
- [ ] Patente/insígnia ao lado do nome em mensagens e lista de membros (precisa do nível do autor no payload).
- [x] Efeito de servidor (ícone na barra, cabeçalho e pino no mapa), aplicado pelo dono.
- [x] Montanha das Patentes (botão "!" ao lado da patente).
- [ ] Títulos comemorativos de temporada (o usuário escolhe no perfil) e Battle Pass 1–100 próprio (separado do nível da conta).
- [ ] Gadget do mapa (música tipo Spotify): confirmar com o dono o que ele imagina.
- [ ] Loja/economia/Battle Pass temático (Dracmas, raridade) em cima da `Posse`.

## Rodada 6 (02/10) - estabilidade de call, mapa, versão do app - feito, AINDA SEM TESTE COM 2 PESSOAS REAIS (só servidor + navegador solo)
- [x] Call: reentrada com o mesmo peer depois de queda do socket (graça de 12 s), uma call por pessoa, aba velha sai sozinha, limpeza de card fantasma, `pedir_ligacao`.
- [x] Ligação por DM: aceitar volta só pra aba que ligou; toque fecha nas outras abas; offline avisa; toque expira; chamada de vídeo abre com câmera.
- [x] Sem chat da call; janela da call atrás de cartão/menus/modais (z-index 1500); Sharingan no card da call corrigido.
- [x] Versão do app (`APP_VERSAO`, faixa "Atualizar agora"), `/chat` sem cache, `garantir_salas`.
- [x] Mapa: reanuncia posição a cada 45 s e ao reconectar, filtro de fix ruim do GPS, ponto corrigido fica salvo 6 h, círculo de precisão some em 10 s.
- [x] Reação instantânea (otimista + servidor responde antes do XP); configurações sem blur aninhado e com fundo pausado.
- [x] Sons de entrada de arquivo: Gogeta = Teleporte (`static/audio/teleporte.mp3`), Sasuke = Sharingan (`sharingan.mp3`); o sintetizado fica de reserva.
- [x] Amaterasu refeita (canvas, discreta, estilo anime) e Punição de Alma do Gogeta (espiral → bolha arco-íris → estoura). Falta o dono aprovar o visual no uso real.
- [ ] **Testar com 2 pessoas**: queda de rede no meio da call (desligar o Wi-Fi 5 s), entrar em duas calls seguidas, ligar por DM com 2 abas, chamada de vídeo.
- [ ] Se continuar sem conectar por rede: TURN próprio no Render (`TURN_URLS`, `TURN_USERNAME`, `TURN_CREDENTIAL`).
- [ ] Sons de DBZ/Naruto são material de terceiro: trocar por áudio próprio antes de abrir o laboratório pra loja pública.
- [ ] Rodada 6 NÃO mexeu em models: não precisa de `atualizar_banco.py`.

## Falta da rodada 4 / dúvidas
- [ ] **Testar com 2 pessoas**: câmera (liga/desliga/entrada tardia), compartilhar tela + zoom, call mini ao trocar de servidor/DM.
- [ ] "Mudar a fonte do status na conversa" (lista de DMs): o pedido não ficou claro; os kaomojis do "pensando" caem em outra fonte do sistema.
- [ ] Redimensionar o chat da call e a área de mensagens (hoje: barras laterais, janela mini e o painel de chat fixo em 350px).
- [ ] Placa (barrinha) ainda não aparece nas mensagens; estilo do nome não vai pro label do card da call.
- [ ] Remover o HTML morto `#status-picker-menu` (agora nunca abre).

## Próxima frente (planejada)
- [ ] Patentes/badges/cosméticos Gogeta e Sasuke: ver `PLANO_COSMETICOS.md`.

## Falta
- [ ] Vídeo como foto/faixa: escolher o trecho (hoje só os 6 s iniciais) e, se quiser, áudio não se aplica.
- [ ] Tela de revisão de denúncias (hoje só pelo banco).
- [ ] Mercado / loja / bazar / economia / Battle Pass (dono vai refazer).
- [ ] Menção (@) em DM; Denunciar mensagem de chat.
- [ ] Rodar `python atualizar_banco.py` no Neon depois do deploy e conferir o log
      `[MIGRACAO]` do boot (cria sozinho o que faltar).

## Rodada 10 (08/10/2026) - Armazém (loja do app em DRC) + livro-razão - feito e testado só no navegador solo
- [x] Armazém: hero em carrossel, filtro por tema, prateleiras, modal do item/pacote, compra atômica em DRC, livro-razão `movimento_drc`.
- [x] Temas à venda com arte original: Relojoaria e Dualidade (moldura, nome, placa, faixa e pacote).
- [x] ~~Calibrar preços~~ → feito na **Rodada 13** com uma CONTA (`testes/calibrar_precos.py`), **não** com jogo real: refazer quando houver dado de uso de verdade.
- [ ] **Testar com 2 pessoas**: comprar numa aba e ver saldo/inventário na outra (regra 6), duas abas clicando em comprar juntas.
- [~] Outros temas do grupo, **sempre com arte original que evoca** (nada de símbolo/sprite de terceiro): a Rodada 13 fez Cubos (Minecraft-like), Batida (música), Quadra (haikyuu/kuroko-like), Mira (valorant/cs-like) e Mangá (anime genérico). **Faltam**: Brawlhalla, LoL, SNK, JoJo-like, Umamusume, Rematch, Roblox-like, Marvel Rivals-like, Blue Lock-like, TF2-like (a Relojoaria já evoca o relógio de bolso).
- [x] ~~Tela de histórico de DRC~~ → Rodada 13 (botão "Extrato" no Armazém).
- [x] ~~Busca na loja~~ → Rodada 13. [ ] "relíquia da semana"; estoque/tempo limitado; mecânica "colete N itens e ganhe uma placa".
- [ ] Item avulso de tipos que ainda não têm tema à venda (efeito de avatar/perfil/fala/radar/pin/servidor, som de call).
- [ ] Apagar os produtos-placebo de `seed_loja.py` (`is_official`): nada mais os mostra.
- [ ] Desconto de grandes lojas parceiras (futuro, só se houver parceria).
- [ ] Carteira virtual com dinheiro real: **decidido NÃO fazer** (guardar dinheiro de terceiros é atividade regulada). Pix só por split de gateway (modelo B).
- [ ] Não afetados nem testados nesta rodada: Electron e PWA. Visual só visto no navegador da pane (desktop e 375 px).
- [ ] A paleta geral do app ainda não foi decidida; a loja segue as variáveis do app e o tema dá o acento.

## Rodada 11 (08/10/2026) - Bazar da comunidade, modelo A (classificados, Pix direto) - feito; testado com 2 origens no navegador local (Ana e Beto) + servidor
- [x] Loja por pessoa com 3 portes (micro/feira, média/fachada, grande/parceira), toldo e cor personalizáveis, propaganda, logo e banner, produto com foto/vídeo/combo/estoque/entrega privada.
- [x] Pedido com estados (aguardando, aceito, pago, confirmado, concluído, recusado, cancelado), estoque reservado ao aceitar, Pix copia e cola + QR, conversa do pedido, avaliação, notificação e badge de pendências.
- [x] Denúncia de loja/produto + tela de moderação (só admin) que também cobre nota/servidor do mapa (fecha a pendência antiga de "tela de revisão de denúncias").
- [ ] **No Neon, depois do deploy**: `python bazar_admin.py admin aquele.sales` (sem isso o dono não vê o botão Moderação). As tabelas `bazar_*` nascem sozinhas no boot.
- [ ] **Colar o "Pix copia e cola" no app de um banco de verdade** e conferir nome do recebedor/valor (segue a especificação e o vetor de CRC, mas só um banco confirma).
- [ ] **Testar com 2 pessoas reais** (celular + PC): pedido, aceite, "já paguei", confirmação, entrega, avaliação, e a notificação/push de cada passo.
- [ ] Modelo B (checkout com gateway: split, retenção até a entrega, KYC do vendedor, webhook assinado, CNPJ/nota, direito de arrependimento, menores de idade).
- [ ] Disputa: hoje não há tela; o admin não lê a conversa do pedido (de propósito, por privacidade) e não existe estorno (o app não toca no dinheiro).
- [ ] Banimento de pessoa (a moderação só registra a denúncia de pessoa).
- [ ] Conversa do pedido sem anexo/comprovante e sem link (só texto). Avaliação só do comprador (o vendedor não avalia o comprador).
- [ ] Frete/endereço de entrega: não existe (combinar na conversa do pedido).
- [ ] Moderação de imagem/vídeo enviados (não há checagem de conteúdo no upload).
- [ ] Loja no mapa ("lojas perto de mim") e filtro por região; favoritos/seguir loja; ordenação (mais vendidos, mais baratos).
- [ ] Reputação mais forte (selo "verificada", tempo de conta mínimo pra vender, limite de valor pra conta nova).
- [ ] Personalização premium da loja (toldos/molduras extras) como produto do Armazém, em DRC.
- [ ] Parceiros grandes (iFood, Mercado Livre...): hoje só o porte "grande" definido à mão; links curtos/afiliados e desconto em DRC são futuro.
- [ ] Remover o legado: `Product`/`Purchase`, `/api/produtos`, `/api/inventario` antigo, `seed_loja.py` (cuidado: `Purchase` é histórico de compras da loja antiga).
- [ ] Visual do Bazar só visto no navegador da pane (desktop e 375 px). Teclado virtual em modal, Electron e PWA não foram testados.
- [ ] Bazar não aparece na barra de baixo do celular com badge próprio (só na aba e no item Mercado Elite).

## Rodada 12 (08/10/2026) - Bazar reorganizado (propagandas em carrossel, feed misturado, Minha lojinha em página) - feito; testado em 2 origens no navegador local + servidor
- [x] Carrossel de propagandas (lojas parceiras + as do Panteão), "Bem avaliadas", filtros (categoria, tipo, busca), feed misturado e embaralhado por seed com rolagem infinita, página da loja, atalho "Minha lojinha" ao lado das moedas e painel completo.
- [ ] **Olhar no tamanho de tela real do dono** (as capturas foram numa janela de ~800 px e no preset de celular): espaçamentos do carrossel, do feed de 3 colunas e do painel em desktop largo.
- [ ] Propagandas das empresas grandes hoje = a "propaganda" da loja parceira (porte "grande"). Se quiser anúncio com **arte própria, datas de início/fim e contagem de cliques**, criar uma tabela de anúncios + tela de admin.
- [ ] As propagandas do Panteão estão fixas no `bazar.js` (`PROPAGANDAS_CASA`): trocar texto = editar o arquivo.
- [ ] "Bem avaliadas" pede só 1 avaliação (`MIN_AVALIACOES_DESTAQUE`): subir quando houver volume, senão uma nota 5 sozinha vira destaque.
- [ ] Feed lê até 300 lojas / 600 itens por pedido e embaralha em Python: com muitas lojas, sortear no SQL ou cachear por seed.
- [ ] Barra de baixo do celular não mostra o selo de pendências do Bazar (só o atalho do cabeçalho, a aba e o item Mercado Elite).
- [ ] Atalho "Minha lojinha" só mostra logo/nome depois que o Bazar é aberto uma vez (evita query extra no connect).
- [ ] O preview do Claude não consegue o banco real: tudo foi testado com SQLite descartável (`run_local_loja.py` no scratchpad, fora do repo). Falta testar no Neon e com 2 pessoas reais.

## Rodada 13 (08/10/2026) - Armazém: preços calibrados, +5 temas, extrato e busca - feito; testado com SQLite descartável + navegador solo (nada no Neon, nada com 2 pessoas reais)
- [x] **Tabela central de preços** `PRECOS` (raridade x tipo) em `cosmeticos.py` + `DESCONTO_PACOTE` (30%); o pacote é calculado sozinho (soma dos 4 itens −30%, arredondado a 50 → **1200 DRC**; avulsos 350/350/450/550).
- [x] **Calibragem** (`python testes/calibrar_precos.py`, sai com 1 se alguma "regra de ouro" quebrar): 1 item barato no 1º dia pra todo mundo; 1º pacote no dia 5 (regular), 4 (intenso), 43 (casual); premium só no dia 41 (regular).
- [x] **7 temas à venda**: Relojoaria, Dualidade, **Cubos, Batida, Quadra, Mira, Mangá** (cada um: moldura, nome, placa, faixa, pacote, arte do carrossel e slide próprio).
- [x] **Extrato de DRC** (botão no Armazém, lê o `movimento_drc` só da própria pessoa) e **busca** por item/tema.
- [x] Teste: `fumaca_loja` 164 verificações (inclui "todo tema da loja tem CSS, arte do hero e slide"), `fumaca_bazar` 169; suíte inteira passou em 08/10.

### O QUE FALTA (lista única, não esquecer)
**Decisão do dono**
- [ ] **A renda de DRC cai depois do 1º mês** (só níveis pagam DRC e o nível custa cada vez mais XP): o regular ganha 3400 DRC em 90 dias, mas ~2200 já no dia 30. Proposta **NÃO aplicada**: missão pagar DRC. Contas: 10 DRC/diária + 40/semanal → regular 3400→**6910**; 20/80 → **10420**. Se aprovar: `MISSOES`/`_somar_xp` pagam + escrevem `MovimentoDrc` (`motivo='missao'`, **e `ROTULO_MOTIVO` em `loja.py`**), e rodar `calibrar_precos.py` de novo.
- [ ] Paleta geral do app (a loja segue as variáveis do app).
- [ ] Trocar os sons de DBZ/Naruto (`static/audio/`) por áudio próprio antes da loja pública; arte do laboratório (Gogeta/Sasuke) também é só pro beta fechado.
**Temas e itens**
- [ ] Temas ainda não feitos (arte original que evoca): Brawlhalla, LoL, SNK, JoJo-like, Umamusume, Rematch, Roblox-like, Marvel Rivals-like, Blue Lock-like, TF2-like (o relógio de bolso da Relojoaria já evoca).
- [ ] Item **avulso** de efeito (avatar/perfil/fala/radar/pin/servidor) e **som de call** à venda: hoje só existem no laboratório, sem preço.
- [ ] "Relíquia da semana", estoque/tempo limitado, "colete N itens e ganhe uma placa".
- [ ] Desconto de grandes lojas parceiras (só se houver parceria).
**Limpeza**
- [ ] Remover o legado: `Product`/`Purchase`, `/api/produtos`, `/api/inventario` antigo, `seed_loja.py` (`Purchase` é histórico: decidir antes).
**Teste e deploy** (nada abaixo foi feito)
- [ ] **Testar no Neon** (o preview do Claude só roda SQLite) e **com 2 pessoas reais** (celular + PC): comprar numa aba e ver saldo/inventário na outra; duas abas clicando em comprar juntas; pedido do Bazar de ponta a ponta.
- [ ] Depois do deploy: `python atualizar_banco.py` e `python bazar_admin.py admin aquele.sales`.
- [ ] Colar o Pix copia e cola num app de banco de verdade (nome do recebedor, valor).
- [ ] **Dados reais de uso** pra recalibrar `PRECOS` (os perfis casual/regular/intenso do `calibrar_precos.py` são suposição).
- [ ] Electron e PWA não foram tocados nem testados; visual só visto na pane (desktop ~800 px e 375 px), nunca no monitor do dono.
**Bazar (modelo A) em aberto**: ver as Rodadas 11 e 12 acima (modelo B com gateway/split/escrow/KYC/CNPJ/CDC/LGPD/menores, tela de disputa, banimento de pessoa, moderação de imagem/vídeo, frete/endereço, loja no mapa, favoritos/ordenação, reputação mais forte, anúncios com arte/datas/cliques, `PROPAGANDAS_CASA` editável, mínimo de avaliações em "Bem avaliadas", feed em escala, selo do Bazar na barra do celular).
**Já pendente do app antes disso**: patente ao lado do nome nas mensagens/listas; menção (@) em DM; "Denunciar mensagem"; vídeo como foto escolher o trecho; trocar credenciais do `.env` que foram pro histórico do git (commit `e7e2a27`); assinatura de código do instalador desktop.

## Rodada 14 (08/10/2026) - DRC por missão, relíquia da semana, edições limitadas, coleção, limpeza do legado - feito; testado só com SQLite + navegador solo
- [x] Missão paga DRC (10 diária / 40 semanal, constante `DRC_POR_MISSAO`) com livro-razão e extrato. **Decisão do dono ainda vale**: se quiser outro valor (ou 20/80), é só mudar a constante e rodar `calibrar_precos.py`.
- [x] Relíquia da semana (-25%), edições limitadas por prazo/estoque (Pioneiro, Lote 001, Eclipse), coleção 4/12/24 (Colecionador, Curador, Acervo).
- [x] Legado removido (`Product`/`Purchase`/`/api/produtos`/`/api/inventario`/`seed_loja.py`); tabelas `product` e `purchase` seguem no Neon.
- [ ] **Falta (ver CLAUDE.md, "O que NÃO foi feito")**: temas premium com efeitos à venda (Boreal, Pétala) e efeitos avulsos + som de call; 10 temas (Brawlhalla, LoL, SNK, JoJo-like, Umamusume, Rematch, Roblox-like, Marvel Rivals-like, Blue Lock-like, TF2-like); Bazar (favoritos, ordenação, anúncios com arte/datas/cliques, `PROPAGANDAS_CASA` editável, disputa, banimento, reputação, frete, loja no mapa, selo na barra do celular, feed em escala); app (patente ao lado do nome, menção em DM, denunciar mensagem, escolher trecho do vídeo, HTML morto).
- [ ] **Ações suas (não dá pra eu fazer)**: trocar as credenciais do `.env` que foram pro histórico (commit `e7e2a27`: Neon, Google, SECRET_KEY); depois do deploy rodar `python atualizar_banco.py` e `python bazar_admin.py admin aquele.sales`; colar o Pix copia e cola num app de banco; testar com 2 pessoas reais (celular + PC), Neon, Electron e PWA; ver o visual no seu monitor; trocar sons/arte de Dragon Ball e Naruto antes da loja pública; decidir a paleta geral.

## Rodada 15 (08/10/2026) - filtros do Armazém, raridades e temas Cyber Neon / Eldoria / Arcade 8-bit - feito; testado só com SQLite + navegador solo
- [x] Armazém filtra por **tipo** (chips), tema, raridade, animação e ordem (listas), com "Limpar filtros"; barra alinhada.
- [x] Raridades comum/raro/épico/lendário; tema Básicos (comum, estático); 3 temas premium de 12 itens com efeitos (avatar, perfil, fala, radar, chat, som, pin, servidor).
- [ ] **Olhar no seu monitor** os efeitos novos (fala na call, radar no mapa, chat ao enviar, som de entrada, pin, efeito de servidor): só vi as prévias dos cartões na pane.
- [ ] Faltam os 10 temas de jogo/anime; Bazar (favoritos, ordenação, anúncios, disputa, banimento, reputação, frete); app (patente ao lado do nome, menção em DM, denunciar mensagem).
- [ ] Desktop **0.3.0** (traz a ponte de localização pelo navegador que o 0.2.1 não tem: por isso o mapa não achava a posição no 0.2.1).

## Rodada 16 (08/10/2026) - JJK à venda no Armazém e Efeitos de perfil nas Configurações - feito; só prévias vistas no navegador do painel
- [x] Gojo, Sukuna, Mahoraga (lendários, 12 itens cada, todos os slots, pacote 5050 DRC) + Combo JJK; domínios só com cortes pretos/dentes/vazio/roda (mãos e dedos removidos a pedido); "Efeitos de perfil" das Configurações liberado.
- [ ] **Ver no seu monitor**: domínios no cartão, fala na call, radar, som de entrada, pin de nota e efeito de servidor dos 3.
- [ ] Se a loja virar comercial (Pix): trocar nomes/referências de JJK, DBZ e Naruto por criações originais.

## Rodada 17 (08/10/2026) - JJK refeito, sons dos domínios, script de DRC e Bazar arejado - feito; só prévias vistas no navegador do painel
- [x] Sukuna: domínio sem boca (aura vermelha, marcas do rosto decalcadas da referência aparecendo e sumindo, 56 cortes pretos em rajadas); nome com a **flecha de fogo (Fuga)** caindo e o nome pegando fogo.
- [x] Gojo: Azul e Vermelho (avatar) sem corte, juntando no roxo; domínio que **enche o cartão**, com anel e **6 olhos humanos**. Mahoraga: **timão** que brilha, gira 45° e para duro, no cartão e na faixa (a faixa estava só um disco preto).
- [x] Sons de entrada dos 3 = os mp3 que o dono baixou (`static/audio/`). `conceder_drc.py` (40k de DRC: `python conceder_drc.py aquele.sales 40000`). Bazar: filtros em dois blocos rotulados e feed com espaço entre as partes.
- [ ] **Ver no seu monitor**: os 3 domínios no cartão, o nome do Sukuna pequeno (listas/barra), som de entrada numa call de verdade. O selo de **mãos do Sukuna** (imagem 2) ficou de fora: dá pra decalcar como as marcas se você pedir.
- [ ] Trocar os 3 mp3 (e os de DBZ/Naruto) por áudio próprio antes de qualquer loja comercial.

---

## O QUE FALTA (lista única e atualizada em 08/10/2026; as listas das rodadas acima são histórico)
**Decisões/ações do dono (eu não consigo fazer)**
- [ ] **Trocar as credenciais do `.env`** que foram pro histórico do git (commit `e7e2a27`: Neon, Google OAuth, `SECRET_KEY`). É a mais urgente.
- [ ] Depois de cada deploy: `python atualizar_banco.py` (e uma vez `python bazar_admin.py admin aquele.sales`). As tabelas `loja_estoque`, `bazar_*`, `movimento_drc` nascem sozinhas.
- [ ] Testar no Neon e **com 2 pessoas reais** (celular + PC): comprar numa aba e ver saldo/inventário na outra, duas abas comprando junto, pedido do Bazar de ponta a ponta, call, mapa.
- [ ] Colar o **Pix copia e cola** no app de um banco de verdade (nome do recebedor, valor).
- [ ] **Ver no monitor dele** tudo que só vi na pane (800 px e 375 px): efeitos de fala/radar/chat/som/pin/servidor dos temas premium e do JJK, e a rolagem depois do conserto.
- [ ] Decidir a **paleta geral** do app; trocar sons/arte de **DBZ, Naruto e JJK** por criações originais antes de qualquer loja comercial; assinatura de código do instalador; Electron e PWA sem teste ao vivo.
**Loja / conteúdo**
- [ ] 10 temas de jogo/anime (arte original que evoca): Brawlhalla, LoL, SNK, JoJo-like, Umamusume, Rematch, Roblox-like, Marvel Rivals-like, Blue Lock-like, TF2-like.
- [ ] Recalibrar `PRECOS` com **dados reais** de uso (`calibrar_precos.py` usa perfis supostos).
- [ ] Desconto de lojas parceiras (só se houver parceria); títulos de temporada e Battle Pass 1–100 próprio (separado do nível).
**Bazar (modelo A em aberto)**
- [ ] Favoritos/seguir loja, ordenação (mais vendidos/mais baratos), anúncios com arte/datas/cliques (hoje `PROPAGANDAS_CASA` fixas no `bazar.js`), disputa (tela), banimento de pessoa, reputação mais forte (conta nova com limite), frete/endereço, loja no mapa, moderação de imagem/vídeo, "Bem avaliadas" com mínimo maior, feed em escala, selo do Bazar na barra do celular, **modelo B** (gateway/split/escrow/KYC/CNPJ/CDC/LGPD/menores).
**App**
- [ ] Patente/insígnia ao lado do nome nas mensagens e listas; menção (@) em DM; denunciar mensagem; escolher o trecho do vídeo como foto; gadget do mapa (música; pedido ambíguo); remover HTML morto (`#status-picker-menu`, `quality-modal-overlay`, CSS `.popout-*`); redimensionar o chat da call; TURN próprio se a call não conectar (`TURN_URLS`...).
**Limpeza feita**: legado `Product`/`Purchase`/`/api/produtos`/`seed_loja.py` (as tabelas `product` e `purchase` seguem no Neon: dá pra `DROP` à mão).
