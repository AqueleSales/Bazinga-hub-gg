# Pantheon: história do projeto

Linha do tempo de tudo que foi feito, em ordem, escrita pra qualquer pessoa (ou conversa nova) entender **como o app chegou até aqui e por quê**.
Os detalhes técnicos de cada rodada (arquivos, regras, bugs) ficam no `CLAUDE.md`; a lista do que falta fica no `BACKLOG.md`.
Datas vêm do git (`git log`) e das rodadas registradas no `CLAUDE.md`. Todas de 2026.

## Visão de uma linha
Um clone de Discord (Flask + Socket.IO + Postgres no Neon, Render free) com um diferencial: **um mapa** onde as pessoas plantam servidores e deixam notas; depois ganhou
**nível/patentes, loja de cosméticos em moeda do app, Bazar de comunidade com Pix, passe de temporada e um painel de criador**.
Nome: nasceu como "BazingaCord/Bazinga Hub", virou **Panteão** (30/09) e depois **Pantheon** (09/10).

## Fase 1: o chat nasce (28/08 a 24/09)
- 28/08 **hub inicial**; 01/09 chamadas por WebRTC (PeerJS), telas múltiplas, UI de hardware e popups.
- 09 a 20/09 **mapa** (Leaflet) com servidores e notas, persistência real de mapa/perfil/servidores no Neon, e o **primeiro CLAUDE.md**.
- 20/09 **primeira limpeza de segurança**: XSS, permissões de canal/mensagem, worker do Socket.IO; convites com QR, reações, anexos, calendário, mensagens fixadas.
- 21/09 página de entrada própria (`/entrar`) com login Google; **canal privado de verdade** (antes só escondia na tela); editor de imagem (cortar/girar/zoom).
- 24/09 login obrigatório, configurações em popup, **gravar e clipar a call**, amigos de verdade, chamada 1-a-1 por DM, deploy no Render (gunicorn + eventlet), uploads no Cloudinary,
  atualização em tempo real (a "regra 6": mudança chega a quem está olhando), busca de GIF (Giphy).
- 28/09 correções de call, Neon sem `NullPool` (lentidão), primeiro **Battle Pass** (nível/XP).

## Fase 2: identidade e polimento (30/09 a 02/10)
- 30/09 **perfil v2** (nome da conta @, status com emoji, "pensando", faixas animadas, molduras, placas, estilos de nome), cartão de perfil, menções (@), tema salvo na conta,
  visual "vidro", renome pra Panteão, Battle Pass de 100 níveis com missões diárias/semanais e XP por tempo ativo.
- 01 e 02/10 **rodadas 1 a 3**: amizade refeita (pedido de 24h, bloqueio), DM com anexo e não lidas, caixa de entrada com som, **mapa por raio** (privacidade) com denúncia,
  GIF e vídeo viram foto/faixa (recorte no servidor com Pillow), conversa rápida, call em janela flutuante, mapa de amigos, convites por qualquer membro.
- 02/10 **Rodada 5**: nível 1 a 1000+, **12 patentes** com ícones animados, **insígnias** (Criador, Alpha, Beta, BAZINGA, Coder, Só nós), inventário com posse, o **laboratório**
  (Gogeta, Sasuke, Fusão) com todos os slots de efeito; Montanha das Patentes. **Rodada 6**: estabilidade de call (quem está na call é decidido pelo servidor).

## Fase 3: app instalável, celular e notificações (05 a 07/10)
- 05/10 **PWA com cache** e **app desktop em Electron** (login pelo navegador com PKCE, atualizador próprio, bandeja). Localização na conta, reserva por IP.
- 06/10 confiança da posição (GPS x IP x teletransporte suspeito), modo **Explorar** no mapa, convites em cartão animado, **layout de celular** (barra inferior, botão multi-uso), responder mensagem,
  **notificações push**. 07/10 insígnias finais e localização pelo navegador no desktop.

## Fase 4: economia (08/10)
- **Rodada 10** Armazém (loja do app em **DRC**), compra atômica, livro-razão de moeda. **Rodadas 11 e 12** Bazar da comunidade (modelo A: Pix direto, sem escrow), carrossel de propagandas,
  feed misturado, "Minha lojinha". **Rodada 13** preços calibrados por simulação (`calibrar_precos.py`), 5 temas novos, extrato. **Rodada 14** DRC por missão, relíquia da semana,
  edições limitadas, coleção. **Rodada 15** filtros, raridades, temas Cyber Neon/Eldoria/Arcade. **Rodadas 16 e 17** JJK (Gojo, Sukuna, Mahoraga) refeito a pedido do dono.
  "Rolagem pesada": animações pausam ao rolar.
- Decisões que valem até hoje: **DRC só se ganha no app** (nunca se compra com dinheiro); Bazar é **Pix direto** (o app não guarda dinheiro); cosmético não se revende.

## Fase 5: Bazar completo e acabamento (09 a 10/10)
- **Rodada 18** domínios calmos com pausa; Bazar completo: favoritos, ordenação, "perto de mim", reputação, frete/endereço, **disputa**, **banimento**, anúncios com datas e cliques.
- **Rodada 19** (feedback de teste com amigos) som da call (causa reproduzida), menus cortados, **login que dura**, notificações sem duplicar, nome **Pantheon**.
- **Rodada 20** setinha de "atualização disponível" + pop-up de novidades, 10 temas novos e **tema personalizado** (imagem por arquivo/link/GIF), "Colar link" no seletor de imagem (anti-SSRF),
  editor na lojinha, atualizador do Windows que instala sozinho (desktop 0.3.1 testado de verdade), tema separado por aparelho.

## Fase 6: criador e passe de temporada (12/10)
- **Rodada 21** Estúdio `/admin` (só admin), **passe de temporada** (100 níveis x Grátis/Premium, datas opcionais, catch-up), títulos, temas exclusivos de temporada, Temporada 1 "Deuses",
  5 diárias + semanais escolhidas, anti-spam de missão, gradientes decorativos fora, logo preta e dourada.
- **Rodada 22** Estúdio de efeitos sem código, Explorar servidores (o mar de barquinhos), conserto do `/admin` (bloqueador de anúncio) e o primeiro plano da IA (ver `docs/`).
- **Rodada 23** (13/10) passe da **Odisseia** (10 cantos, mitologia grega, efeitos feitos no Estúdio) e plano do **Guardião** reescrito: visível, gatilho local, texto ao Gemini, revisão humana.

## Lições que custaram caro (resumo)
1. Sem Alembic: coluna nova precisa de `ALTER` (`atualizar_banco.py`) além do boot que cria sozinho.
2. Escrita no banco sempre em `comitar_com_retry` (Neon acorda e falha a 1ª query).
3. Permissão se confere no servidor; esconder botão não protege.
4. Mudança em tempo real precisa chegar a **todos** que olham, não só a quem agiu (teste com 2 pessoas).
5. Dado de usuário nunca cru em `innerHTML` (XSS); só ids conhecidos viram `class=""`.
6. Muita animação que repinta (gradiente/`background-position`) trava a rolagem; prefira `transform`/`opacity`.
7. Não desenhe mão em SVG. Heredoc com aspas quebra a ferramenta de shell: escreva scripts de patch por arquivo.
8. Bloqueador de anúncio esconde tudo que começa com `ad-` (o painel usa `es-`).

## Pendências de sempre (ações do dono)
Trocar as credenciais do `.env` que foram pro histórico (commit `e7e2a27`); `python atualizar_banco.py` depois de cada deploy; testar no Neon e com 2 pessoas reais;
colar o Pix num banco de verdade; trocar nomes/sons de JJK, DBZ e Naruto antes de qualquer loja comercial (dinheiro real); assinatura de código do instalador.
