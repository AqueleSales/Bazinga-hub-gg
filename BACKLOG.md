# Backlog (atualizado em 01/10/2026)

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
