# Plano: patentes, badges e cosméticos (temas Gogeta e Sasuke)

Escrito em 02/10/2026 para abrir uma conversa nova. Leia junto com `CLAUDE.md` (regras 1–6, a seção
"Perfil v2" e a **"Rodada 5"**, que descreve como tudo isto foi feito) e `BACKLOG.md`. É um laboratório: tudo é
**só para o dono e o amigo beta tester**, com os temas pessoais de cada um, antes de virar loja.

## STATUS (fim da Rodada 5, 02/10/2026) — a maior parte já está feita

Decisões tomadas (as "perguntas abertas" da seção 1): **sem teto** (1–1000 em tabela e 1000+ com passo fixo; nível ≠ Battle Pass),
**12 patentes × 3 subníveis** (nomes mitológicos, combinam com Panteão/Dracmas), nível + patente aparecem no **cartão de perfil**,
Meu Perfil, Battle Pass e tela de "subiu de nível" (mensagens/lista de membros ficaram para depois).

| Item do plano | Estado |
|---|---|
| Nível 1–1000+, patentes em ícone SVG animado (mais animação quanto maior), popover "orb" | ✅ feito (galeria na aba Patentes do Inventário) |
| Insígnias Criador / Beta Tester / Coder / **Só nós** (duas chamas que se fundem no hover) | ✅ feito |
| Catálogo único + **posse** por pessoa (`Posse`), servidor confere ao equipar | ✅ feito (`app/cosmeticos.py`, `equipar_item`, `atualizar_perfil` com checagem) |
| Inventário nas Configurações **e** embaixo do Mercado Elite | ✅ feito (mesmo componente) |
| Laboratório Gogeta / Sasuke / **Fusão (só nós)**: moldura, placa, nome, faixa, efeito de avatar, efeito de perfil, efeito de fala, radar, efeito do chat (digitar/enviar), som de entrada na call, pin de nota, pacotes de tema | ✅ feito |
| Efeitos para servidores e pin de servidor no mapa | ✅ feito (um item só: o dono aplica ao servidor; ícone na barra, cabeçalho e pino) |
| Gadget do mapa (música tipo Spotify) | ⏳ não feito (pedido ambíguo: confirmar com o dono o que é) |
| Patente/insígnia ao lado do nome em mensagens e lista de membros | ⏳ não feito (precisa do nível do autor em cada payload) |
| Loja/economia/Battle Pass temático (comprar com Dracmas, raridade, bazar) | ⏳ o dono vai refazer; a posse (`origem`) já está pronta pra isso |
| Arte/áudio próprios para a loja pública | ⏳ o laboratório usa só forma/cor/som sintetizado; **não** usar sprite/áudio de Dragon Ball/Naruto na loja |

O texto abaixo é o plano original (mantido como referência das ideias por tipo de item).

## Os dois usuários de teste e os temas

- **Dono (filippo / "Aquele Sales")** — tema **Gogeta**: fogo, aura dourada/laranja, Super Saiyajin,
  Fusão, "Punição de Alma" (Soul Punisher), Dragon Ball. Cores: laranja, vermelho, dourado, preto, com toques de azul/branco.
- **Amigo beta tester** — tema **Sasuke**: roxo (Susanoo, Chidori), preto, Sharingan/Rinnegan, relâmpago, Amaterasu (chama negra).
  Cores: roxo, preto, vermelho-sangue, azul-elétrico.
- Hoje o app quase não tem nada com esses temas (a moldura/placa/faixa existentes são genéricas).
- Os itens "só nossos" devem ficar **travados por id de usuário** (lista no servidor), nunca por regra do cliente.
  Sugestão: tabela `Cosmetico`/`Posse` (ver "Fundação") com `exclusivo_para` = lista de `person_id`.

## 1. Níveis e patentes (substitui "Explorador", "Novato"...)

Ideia do dono, resumida:

- **Nível** = experiência TOTAL acumulada (horas de uso, mensagens, missões...). Vai de **1 a 1000+** e nunca zera.
- **Battle Pass** = outra coisa: trilhas por **tema/temporada** (cada uma de 1 a 100), com recompensas próprias.
  O nível geral e o nível do passe são independentes.
- Ao lado do nível aparece uma **patente em forma de ícone animado**, que melhora a cada faixa de níveis; **quanto maior
  a patente, mais animação ela ganha** (brilho parado → pulsar → partículas → aura/raios).
- **Passar o mouse** no ícone abre uma caixinha estilo "orb" do Discord: o badge **grande** em cima e **embaixo o nome
  da patente** (e o nível). Referências que o dono mostrou: orbs do Discord (cristal que evolui: Aprendiz...), patentes
  do CS:GO (chevrons/estrelas/águia), Valorant (Ferro→Radiante, com 3 subníveis) e uma trilha militar de 40 patentes.
- Hoje: `Person.xp` guarda o TOTAL; nível e título são calculados em `app/utils.py` (`XP_BASE`/`XP_CRESCIMENTO`,
  100 níveis ≈ 999.504 XP, `TITULOS_POR_NIVEL`). Mexer na curva não precisa de migração.

Perguntas que o dono deixou abertas (decidir com ele no começo):

1. **Teto 1000?** Proposta: níveis 1–1000 com curva mais suave que a atual (a de 100 níveis custa 20k XP no último passo; em
   1000 níveis precisa de um crescimento menor ou por faixas), e "1000+" = prestígio (reinicia só a patente, não o XP).
2. Faixas de patente (rascunho): 10 patentes × 100 níveis cada, cada patente com 3 subníveis visuais (como Valorant).
   Nomes com a vibe dos dois temas ou neutros? (ex.: Aprendiz → ... → Panteão).
3. Mostrar o nível e a patente **onde**: cartão de perfil, lista de membros, mensagens, barra do usuário.

Implementação sugerida:

- Constante única `PATENTES = [{id, nome, de_nivel, ate_nivel, cor, anim}]` em `utils.py` + espelho em JS (mesmo padrão de
  `ESTILOS_NOME`/`MOLDURAS`: ids validados no servidor, CSS `.patente-<id>`).
- Ícones **SVG inline** (leves, sem imagem) com `<animate>`/CSS: o nível da animação sobe com a patente
  (`.anim-0` estático … `.anim-4` com partículas/brilho). Respeitar `prefers-reduced-motion`.
- Componente único `htmlPatente(nivel, tamanho)` + o popover do hover (um só, delegado no `document`).
- `estado_battlepass()` já devolve nível/título: acrescentar `patente`. Cuidado com o custo: calcular no servidor, o cliente só desenha.

## 2. Badges (insígnias) — separadas da patente

Insígnias colecionáveis no cartão de perfil (ícone pequeno ao lado do nome), com o mesmo popover de hover.

**Exclusivas do dono e do amigo (não vendáveis):**
- **Criador** (dono e amigo, decisão do dono) — ex.: coroa/cristal com chama Gogeta.
- **Beta Tester** (dono + amigo) — ex.: selo com engrenagem/estrela.
- **Coder** — ex.: `</>` luminoso (dono; amigo se ajudou a programar).
- **"Só nós"** — badge que só os dois têm (algo como duas chamas/fusão: Gogeta = fusão de dois!). Boa ideia visual: dois
  elementos que se unem, um laranja e um roxo.

**Para a loja no futuro:** badges comuns/raros/épicos comprados com Dracmas (DRC), com raridade na cor da borda.

Modelo sugerido: tabela `Badge` (catálogo) + `PessoaBadge` (posse) ou, no começo, coluna JSON `Person.badges` validada
contra um catálogo no servidor. **Lembrar a regra 1**: coluna nova = `ALTER` em `atualizar_banco.py`.

## 3. Laboratório de cosméticos (só para os dois)

Criar, **para cada tema**, uma versão experimental de cada tipo abaixo — como itens de teste travados por usuário.
A ordem sugerida é do que já tem infraestrutura para o que é novo:

| # | Tipo | Já existe? | Ideia Gogeta | Ideia Sasuke |
|---|---|---|---|---|
| 1 | **Moldura de avatar** | sim (6, `MOLDURAS` + `.moldura-*`) | anel de aura dourada com chamas | anel roxo com relâmpago Chidori |
| 2 | **Placa** (barra atrás do nome) | sim (`PLACAS`) | placa pegando **fogo** (partículas subindo) | placa com **poeira/cinza** e brilho roxo |
| 3 | **Estilo de nome** | sim (`ESTILOS_NOME`) | gradiente dourado→laranja pulsando | roxo→preto com glitch Sharingan |
| 4 | **Faixa animada** do perfil | sim (`FAIXAS_ANIMADAS`) | aura/energia subindo | tempestade roxa |
| 5 | **Efeito de avatar** (além da moldura) | não | aura "Super Saiyajin" atrás do avatar | olho Sharingan pulsando |
| 6 | **Efeito de perfil** (por cima do cartão) | só "Em breve" | faíscas douradas | relâmpagos |
| 7 | **Efeito de banner** | não | — | — |
| 8 | **Pin de nota** no mapa | parcial (`GeoNote.icone`) | esfera do dragão / Kamehameha | kunai/Amaterasu |
| 9 | **Pin de servidor** no mapa | foto do servidor | — | — |
| 10 | **Efeito do Radar** (ondas do raio) | sim (`.raio-onda`) | ondas de aura | ondas roxas |
| 11 | **Gadget do mapa** (ex.: música tocando) | não | — | — |
| 12 | **Efeitos sonoros** (entrar na call, mensagem, etc.) | `tocarSom()` | — | — |
| 13 | **Efeito de fala na call** | borda verde `.is-speaking` | aura ao falar | relâmpago ao falar |
| 14 | **Efeito de digitação / envio** | não | — | — |
| 15 | **Pacote de tema** (junta vários) | não | "Gogeta" completo | "Sasuke" completo |
| 16 | **Inventário** | `/api/inventario` sem UI | UI de equipar | — |

Notas técnicas por item (reaproveitar o molde de "Perfil v2" do CLAUDE.md):
- Cada cosmético tem **id validado no servidor** (nunca texto livre que vire `class=""`) + CSS + item no catálogo JS.
- Efeitos animados: preferir CSS/SVG (sem imagem), pausar durante rolagem (ver `.settings-content.rolando`) e respeitar
  `prefers-reduced-motion`. Anéis com `@property` rodam na thread principal — com muitos na tela pesam.
- Som: Web Audio sintetizado (`tocarSom`) cobre bipes; som "de verdade" (Kamehameha etc.) precisa de arquivo e **direitos
  autorais** — para o teste privado tudo bem, para a loja pública não usar áudio/imagem de Dragon Ball/Naruto sem licença
  (fazer inspiração própria: aura, relâmpago, fogo — sem ripar sprites).
- Pin/serv. no mapa: ver `renderizarGeoNote()` / `renderizarServidorMapa()`; ícone da nota é `GeoNote.icone`.

## 4. Fundação necessária antes da loja (resolver cedo)

1. **Catálogo único** de itens: `{id, tipo, nome, raridade, preco_drc, exclusivo_para?, tema?}` em um só lugar
   (hoje `ESTILOS_NOME`/`PLACAS`/`MOLDURAS`/`FAIXAS_ANIMADAS` vivem em listas separadas, espelhadas no JS).
2. **Posse/inventário** (`Posse`: person_id, item_id, origem) + tela de equipar; o servidor valida que a pessoa TEM o item
   antes de aceitar em `atualizar_perfil` (hoje aceita qualquer id válido — todo mundo tem tudo).
3. **Economia** (loja/bazar/Battle Pass de recompensas) — o dono deixou para refazer; combinar isto com ele.
4. Migração: `atualizar_banco.py` + o auto-add de colunas (`adicionar_colunas_que_faltam`); tabela nova nasce no `create_all()`.

## 5. Sugestão de ordem para a próxima conversa

1. Decidir as perguntas abertas da seção 1 (teto, faixas, onde mostrar) — 5 minutos com o dono.
2. **Patentes + hover "orb"** (SVG animado, 10 patentes) e trocar "Explorador/Novato" por elas.
3. **Badges exclusivos** (Criador, Beta Tester, Coder, "Só nós") com travamento por usuário.
4. **Laboratório Gogeta/Sasuke**: moldura, placa (fogo/poeira), nome, faixa, aura de avatar — um tipo por vez, testando com 2 pessoas.
5. Catálogo + posse (fundação) e só então efeitos de mapa/som/digitação.

Regras do projeto que valem aqui: testar com **2 usuários reais** (regra 6), toda mudança em `models.py` exige
`atualizar_banco.py` (regra 1), escapar dado de usuário em `innerHTML` (regra 5), e checar permissão no servidor (regra 4).
