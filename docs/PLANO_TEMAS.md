# Plano mestre dos temas de cosméticos: fazer TODOS (escrito em 13/10/2026)

> **Este arquivo é só CONTEXTO e PLANO.** Nada daqui foi produzido ainda, exceto o tema Simbionte (Rodada 26). Quem abrir uma conversa nova: leia este arquivo inteiro, depois `docs/ARTE_TEMAS.md`
> (técnica) e a seção "Rodada 26" do `CLAUDE.md`, e comece pelo **Passo 0** (seção 4). O resumo e o checklist vivo também estão no topo do `CLAUDE.md` ("TAREFA PERMANENTE").

## 1. O pedido do dono (nas palavras dele)

- "É para fazer **TODOS MESMO TODOS**." (13/10/2026, antes de abrir uma conversa nova; o plano tinha que ficar salvo no CLAUDE.md.)
- Os **10 temas de jogo e anime**, "com arte original que só evoca": **Brawlhalla, LoL, SNK, JoJo-like, Umamusume, Rematch, Roblox-like, Marvel Rivals-like, Blue Lock-like e TF2-like**.
- Os **adiados** ("primeiro as features novas", que agora já foram feitas): **chama azul do JJK**; **Homem-Aranha, Venom e DC/Marvel**; **todos os genéricos: fofos, básicos, emo, assustadores, temas banais**.
- Antes disso, na mesma conversa, ele deu a direção da arte (ver seção 2): fiel ao que se reconhece, alta qualidade, ampla variedade, itens vendidos separados, efeito de avatar por cima da foto.
- "Os genéricos vão dar mais 20 ou mais temas." (mínimos por família na seção 5, grupo C.) Ele também citou **futevôlei** (entra nos banais/esporte).

## 2. Regras do dono (valem pra TUDO que vier)

1. **Arte de ALTA QUALIDADE e FIEL ao que se reconhece.** "Um símbolo tem que ser o símbolo daquele tema; uma mão tem que ser uma mão e não só traços; a animação conhecida do anime/jogo tem que ser reproduzida igual."
   Ele já disse (13/10) que o risco de direitos é dele ("o projeto não vai ficar tão grande"). Ao listar os 10 de jogo/anime ele repetiu "arte original que só evoca". **Como reconciliar (decisão desta sessão):**
   fiel = forma, cor, composição e MOVIMENTO identificáveis, **desenhados por código** (SVG/CSS/canvas, som sintetizado); nunca copiar arquivo de terceiros (sprite, logo oficial, áudio, screenshot). Nomes de loja genéricos e evocativos, não a marca
   ("Simbionte", não "Venom"; "Hextech" é termo do jogo mas serve; "Valhalla", "Derby", "Zona"...). Se ele preferir o nome da marca, é trocar uma constante (`TEMAS[...]['nome']`).
2. **Ampla variedade**: "não pega só os mais conhecidos, pega uma ampla variedade". Cada franquia ganha várias facetas (sub-temas), não só o personagem/símbolo óbvio.
3. **Itens vendidos SEPARADOS**: "não precisa fazer pacotes, pode fazer coisas separadas; nem todos os pacotes precisam ter todos os cosméticos". Pacote é opcional (`_pacote_loja`), tema pode ter só alguns tipos.
   Pode haver itens **amplos** (genéricos, ex.: as letras "ゴゴゴ") e **específicos** (ex.: Za Warudo, Giorno, Iggy, Star Platinum) dentro da mesma família.
4. **Efeito de avatar pode passar POR CIMA da foto** (ex.: o simbionte que come a foto e depois recua em tentáculos). Já existe a peça `.ef-av-sobre` (ver `docs/ARTE_TEMAS.md`).
5. **Moldura e efeito de avatar são coisas separadas e ficam as duas** (decisão dele): moldura = anel; efeito de avatar = animação em volta/por cima da foto; efeito de perfil = animação no cartão inteiro.
6. **Mão, rosto, personagem e criatura**: só com **imagem de referência** salva em arquivo (decalcar). Sem referência, faça símbolo, padrão, tipografia, partícula, luz, cor e movimento. **Não desenhe mão em SVG** (duas tentativas ruins no JJK).
7. Ele ri quando fica feio ("q porra de símbolo é esse kkkk"). Prefira entregar menos e certo a entregar muito e torto: mostre o resultado, confira de perto com a ferramenta de QA e só então siga.

## 3. Como trabalhar (processo)

- **Não pare no meio da lista pra perguntar** o que este plano já responde. Peça as referências UMA vez, no começo (seção 6), e siga com o que dá sem elas.
- Trabalhe em **lotes de 3 a 5 temas**. Fim de cada lote: suíte verde (`.venv\Scripts\python.exe testes\fumaca_*.py`, todos devem sair com código 0 e "FALHAS: nenhuma"), checklist atualizado (aqui e no `CLAUDE.md`), uma **entrada nova no topo de `app/novidades.py`** (pop-up de atualização) e uma nota curta na seção da rodada no `CLAUDE.md`.
- **Commit só se o dono pedir.** Nunca deploy.
- Se o contexto acabar no meio de um lote, deixe o checklist (seção 5) e a lista "o que não ficou 100%" (seção 7) atualizados: a próxima conversa recomeça do primeiro tema desmarcado.
- O dono olha as coisas no monitor dele e responde rápido (às vezes no meio do trabalho). Responda curto e diga o que está fazendo. Mensagem dele no meio do turno é prioridade.
- Subagentes só se o dono autorizar. Se autorizar, NÃO deixe dois agentes editando o mesmo arquivo de arte ao mesmo tempo (ver o passo 0.2: um arquivo por categoria evita conflito).

### Critério de "tema COMPLETO"
- Os **4 visuais**: moldura + nome + placa + faixa (obrigatório nos temas de franquia e nos de grupo B; nos genéricos, pelo menos 3 dos 4).
- **Efeitos**: efeito de avatar E efeito de perfil nos temas de franquia (grupos A e B); nos genéricos, pelo menos um dos dois. Pelo menos **6 itens** por tema.
- **Extras baratos e bonitos** (faça nos temas de franquia, 2 ou mais): efeito de chat, pin de nota, efeito de fala, efeito do radar, som de entrada (sintetizado), efeito de servidor. Os 12 slots completos só nos temas "carro-chefe".
- Cada item: id `[a-z_]` com no máximo 24 caracteres (as colunas `moldura/placa/nome_estilo` são `String(24)`; faixa vira `anim:<id>` em `String(50)`; posse `<tipo>:<id>` em `String(60)`), CSS em todos os contextos (cartão, tile do perfil, mensagem, call), registro no JS quando precisa.
- Conferido de perto com `testes/qa_itens.py` em vários tamanhos e **em momentos diferentes do ciclo** (as animações longas começam "vazias": congele em 4, 8, 12 s).
- Preço pelo `PRECOS` (raridade x tipo); `calibrar_precos.py` e a suíte continuam passando. Pacote só se ajudar (4+ itens).
- Hero do Armazém (`ARTES` em `loja.js` + `DESTAQUES` em `loja.py`) é **opcional** (`sem_hero: True` é o padrão); só nos carro-chefe.

## 4. PASSO 0: infraestrutura pra aguentar 60+ temas (fazer ANTES dos temas)

Hoje o Armazém tem 15 temas e ~150 itens. Com 60+ temas e 400+ itens vários pontos quebram. Ordem sugerida:

1. **Categoria temática** (o dono já tinha pedido "categorizar"): campo `categoria` em cada `TEMAS[...]` (`anime`, `jogos`, `quadrinhos`, `esporte`, `fofo`, `sombrio`, `cotidiano`, `fantasia`, `mitologia`, `basico`, `sazonal`),
   mandado no payload da vitrine, e no Armazém um filtro de categoria (chips ou lista) **mais busca por tema**. A lista suspensa "Tema" com 60 nomes não presta. Atualizar o teste de loja pra exigir `categoria` válida.
2. **Um arquivo de arte por categoria** em vez de um `cosm_temas.js/css` gigante: `static/js/cosm_<categoria>.js` e `static/css/cosm_<categoria>.css` (o `cosm_temas.*` atual fica como núcleo: tentáculos, filtro de gosma, helpers e o **kit de ícones**).
   Carregar por uma lista só (`COSM_ARQUIVOS` em `app/__init__.py`, versão por arquivo, `{% for %}` no `chat.html`) e fazer os testes lerem `cosm_*.css` / `cosm_*.js` por padrão de nome (hoje leem os nomes fixos).
3. **Kit de ícones SVG** (`cosm_temas.js`): ~60 formas simples e limpas (coração, estrela, morcego, caveira, pata, flor, nuvem, lua, sol, raio, gota, folha, floco, chama, nota musical, controle, bola, coroa, espada, escudo, fantasma,
   abóbora, doce, peixe, osso, aranha, olho, dente, chave, cadeado, diamante, laço, orelha...) + **geradores**: anel de ícones em volta da foto, ícones orbitando, chuva/subida de ícones no cartão, padrão repetido pra placa/faixa (data-URI),
   nome com contorno/sombra, moldura de ícones. Com isso os genéricos viram quase só dados (paleta + ícone + movimento). Reaproveite a ideia do Estúdio de efeitos (`efeitos.js`: partículas, brilho, raios, anel, órbita).
4. **Prévia que não nasce vazia**: efeitos de ciclo longo (domínios, Invasão Negra) aparecem em branco no começo nas prévias (carrossel do perfil, Armazém, Inventário). Faça as prévias começarem numa fase representativa
   (`animation-delay` negativo por variável `--ef-inicio`, ou `currentTime` ao montar). Hoje o cartão "Invasão Negra" do Armazém mostra uma faixa escura vazia.
5. **Hero automático** do Armazém para tema sem `ARTES` (cartão com a foto da pessoa usando a moldura/nome/placa do tema), pra não precisar de 60 heróis feitos à mão.
6. **Desempenho do Armazém** com 400+ cartões (`content-visibility`, renderização por prateleira, ou paginar) e do `vitrine_para_json` (todos os itens vão a cada abertura). Medir antes de mexer.
7. Reler `calibrar_precos.py` com os temas novos (as "regras de ouro" dos preços) e a conta da **Coleção** (4/12/24 itens avulsos: com tanto item ela vai ser alcançada rápido; talvez subir as metas).
8. (Opcional, se o dono topar) Moldura em série, ex.: **Elos do LoL** (10 molduras de rank) e **Cores** dos básicos como itens soltos.

## 5. Lista completa e checklist (marque [x] só quando COMPLETO, ver seção 3)
> **Estado em 14/10/2026 (Rodada 27, NÃO commitada até a sessão pedir): todos os temas da lista foram produzidos pelo gerador (`tools/cosm/`, ver `CLAUDE.md` > Rodada 27), 113 temas e ~1040 itens.**
> Marcados `[x]` = feitos com os 4 visuais, efeitos de avatar e de perfil e extras (pin, som...), conferidos nas galerias (`testes/qa_itens.py`). **Ressalvas** (o que NÃO ficou 100%) na seção 7. `[~]` = parcial (Simbionte: o símbolo da aranha ainda é aproximação).

Os ids de tema abaixo são **sugestões** (`[a-z_]`, máx. 24). Cada "sub-tema" é um tema à parte na loja (variedade). Os conceitos são de partida: refine com referências.

### Grupo A: os 10 de jogo e anime
- [x] **A1. Brawlhalla** (`valhalla`): luta de plataforma viking. Paleta: laranja-brasa `#f08a24`, azul-aço `#3a6ea5`, pedra `#5b5f6b`, ouro `#e0b23a`. Evocar: runas nórdicas girando e acendendo uma a uma (o Unicode tem o bloco rúnico, ou desenhe),
  armas (martelo, machado, espada, lança, arco) como silhuetas simples, escudo redondo, ponte Bifrost em arco-íris, **arma caindo** com brilho dourado, **contador de dano "%"** que sobe e muda de cor (branco, amarelo, vermelho), **estrela de KO** estourando pra fora.
  Itens: moldura Círculo de Runas; nome Valhalla (pedra talhada + brilho laranja); placa Laje de Runas; faixa Arena Flutuante; efeito de avatar **Dano %** (número sobe por cima da foto e a foto "voa" num KO e volta) e Armas Orbitando;
  efeito de perfil Zona de KO (estrela e linhas radiais cruzam o cartão); efeito de chat Golpe (faíscas de impacto); pin Runa; som Impacto (sintetizado).
- [x] **A2. LoL** (`hextech`): Runeterra. Paleta do cliente: dourado `#c8aa6e`, turquesa `#0ac8b9`, azul-fundo `#010a13`/`#091428`. Evocar: hexágonos e cristais Hextech, runas, **subir de nível** (feixe de luz + estrelas), minimapa com pings ("?" e "!"),
  **PENTAKILL**, banners VICTORY/DEFEAT, e a **moldura de elo com asas e gema** (Ferro, Bronze, Prata, Ouro, Platina, Esmeralda, Diamante, Mestre, Grão-Mestre, Desafiante: série de 10 molduras soltas).
  Itens: moldura Hextech (anel hexagonal com segmentos girando); nome Invocador (serifa dourada com brilho turquesa); placa Mapa da Fenda; faixa Cristal Hextech; efeito de avatar Nível! ; efeito de perfil **Pentakill** (cinco raios + texto) e Arcano (runas flutuando);
  efeito de chat Ping; som Subiu de Nível.
  - [x] sub-temas de variedade (cada um com cara própria): **Zaun** (quimitecnologia: verde-tóxico `#7cff3a` + roxo, tubos, bolhas, engrenagens), **Ilhas das Sombras** (verde-fantasma `#40e0a0`, névoa, correntes), **Noxus** (vermelho/preto, machados), **Demacia** (azul/dourado, asas), **Ionia** (flores, rosa), **Freljord** (gelo), **Shurima** (areia e sol).
- [x] **A3. SNK** (`neoarena`): KOF, Fatal Fury, Samurai Shodown, Metal Slug. Paleta: vermelho `#e4002b`, amarelo `#ffd400`, azul Neo Geo. Evocar: **barra de vida** amarela que esvazia e vira vermelha com "K.O." no meio, **"ROUND 1: FIGHT!"**, "K.O.!", "PERFECT",
  **contador "N HITS!"**, pixel 16-bit, chama **carmesim** e chama **púrpura** (duas facções), tinta de sabre preto-e-branco com respingo vermelho (Samurai Shodown), explosão estilo Metal Slug, onda de energia.
  Itens: moldura Chama Carmesim e moldura Chama Púrpura (soltas); nome K.O. (letras grossas vermelho/amarelo com bisel); placa Barra de Vida (esvazia e pisca); faixa Arena Neo; efeito de avatar Chamas Rivais (as duas chamas em duelo);
  efeito de perfil **ROUND 1: FIGHT!** (letras entram, cartão treme, K.O. corta); efeito de chat **Combo** (o contador de hits sobe a cada mensagem enviada); pin Bola de Fogo; som Round.
- [x] **A4. JoJo-like** (`bizarro` e sub-temas): paleta psicodélica: roxo `#7a2bbf`, magenta `#e0409a`, petróleo `#1aa6b7`, laranja `#ff8a1f`; contorno preto grosso; linhas de impacto; sombreado dramático; **tipografia de efeito sonoro japonês** (ゴ ド ズ ギュ ン オ ラ ム ダ).
  - [x] **Bizarro (genérico)**: efeito de avatar **Menacing** (os "ゴゴゴゴ" flutuando EM CIMA da foto, tremendo, em degradê; desenhe as letras como caminhos SVG: ゴ é "コ" com dois tracinhos) e "ドドド" (batimento);
    moldura **Flecha** (a ponta de flecha do Stand) e **Estrela Joestar** (a marca de nascença em forma de estrela); nome Bizarro (letras com contorno e sombra); placa Joestar; faixa Aventura (céu em degradê psicodélico com linhas); efeito de perfil Pose (linhas de impacto e ゴ cruzando o cartão).
  - [x] **Parar o Tempo** (Za Warudo): relógio com algarismos romanos, **pulso que inverte as cores** (`mix-blend-mode: difference`), ザ・ワールド, tom verde-amarelo; efeito de avatar por cima da foto (a foto fica em negativo e o relógio para no XII); rolo compressor opcional (silhueta simples).
  - [x] **Vento Dourado** (Giorno): **joaninha** (o broche), **borboletas douradas**, vida brotando (folhas, flores), ouro + verde.
  - [x] **Areia** (Iggy): tempestade de areia em canvas, patinhas, tons de areia. (O cachorro em si é desenho de personagem: só com referência.)
  - [x] **Platina** (Star Platinum): rajada **"ORA ORA ORA"** (オラ) em letras grossas e linhas de impacto; estrela; roxo/azul. Punhos e rosto só com referência.
  - [x] extras de variedade: **Hamon** (anéis dourados de ondulação), **Diamante** (cacos voltando ao lugar: "reparar"), Stone Ocean etc. se o dono quiser.
- [x] **A5. Umamusume** (`derby`): pastel: rosa `#ff8fc7`, menta `#7fe0b4`, céu `#7ec8ff`, ouro `#ffd166`. Evocar: **ferradura**, **orelhas de cavalo** (efeito de avatar por cima da foto, balançando), laços/fitas, pista de corrida com raias, **linha de chegada quadriculada**,
  cenoura, troféu/coroa, palco de show ("Live": holofotes, bastões luminosos, confete). Itens: moldura Ferradura (cravos dourados); nome Idol (rosa/azul pastel com contorno branco e brilho); placa Raia (um ponto corre até a chegada);
  faixa Derby (arquibancada, bandeirolas, confete); efeito de avatar **Orelhinhas** e Trilha de Cascos; efeito de perfil **Linha de Chegada** (faixa cruza o cartão, confete, holofotes); efeito de chat Galope; pin Ferradura; som Largada (sino + galope).
  - [x] sub-tema **Live** (palco idol) e **Cenouras** (fofo).
- [x] **A6. Rematch** (`gol`): futebol. Verde-gramado `#2e9e4f`/`#3aa95a`, branco, amarelo/vermelho dos cartões, laranja da bola. Evocar: **bola** (pentágonos), gol e **rede** (malha), linhas do campo (círculo central), apito, **cartões**, **placar**, holofotes, papel picado, "GOL!".
  Itens: moldura Bola (orbita com rastro); nome Camisa 10 (numerais de camisa com contorno e listras); placa Placar (dígitos que mudam "2 - 1"); faixa Gramado (campo visto de cima com listras de corte); efeito de avatar Chute (a bola passa, onda de gol);
  efeito de perfil **Gol!** (rede balança, papel picado, holofotes); efeito de chat **Cartão** (amarelo e vermelho piscam ao enviar); efeito do radar Círculo Central; pin Bola; som Apito/Torcida.
- [x] **A7. Roblox-like** (`tijolos`): blocos. Vermelho `#d9362b`, amarelo `#f5c518`, azul `#2f6fd6`, verde `#2e9e4f`, cinza-baseplate `#8b8f99`. Evocar: **tijolos com pinos (studs)**, baseplate quadriculada, **obby** (plataformas coloridas sobre lava), personagem de blocos
  (cabeça amarela, tronco azul, pernas verdes: formas simples), moeda hexagonal, peças neon, spawn pad, "oof". Itens: moldura Anel de Tijolos; nome Blocão (letras de tijolo); placa Baseplate; faixa Obby; efeito de avatar **Tijolos Empilhando**;
  efeito de perfil **Chuva de Tijolos** (caem e formam um muro embaixo); efeito de chat Encaixa (o tijolo encaixa ao enviar); pin Tijolo; som Oof (sintetizado).
- [x] **A8. Marvel Rivals-like** (`hq`): hero shooter em quadrinho. Vermelho `#e23636`, azul `#1e5eff`, amarelo `#ffd23f`, preto, **meio-tom (Ben-Day)**. Evocar: **painéis de HQ**, pontos de meio-tom, linhas de velocidade, onomatopeias ocidentais (POW, BAM, KRAK),
  balão de fala, **barra de Ultimate** que enche e explode, elo de "Team-Up" entre dois ícones, barra de progresso do payload. Itens: moldura Quadro de HQ; nome Impacto (amarelo, contorno preto, sombra deslocada); placa Halftone; faixa Capa de HQ;
  efeito de avatar **Ultimate** (anel de barra enche e estoura em linhas); efeito de perfil **Painéis** (painéis entram em sequência com POW!); efeito de chat BAM; pin Balão. (Diferente do Mangá, que é preto-e-branco japonês.)
- [x] **A9. Blue Lock-like** (`ego`): futebol de ego. Azul-elétrico `#2d6bff`/`#1d4ed8`, preto, branco, ciano, amarelo. Evocar: **chama azul "Zona"**, **metavisão** (linhas de campo em arame e setas de trajetória), **trajetória do chute**, tipografia "EGO",
  gaiola/cadeado, camisa 11, coração pulsando, faíscas de **reação química**. Itens: moldura Zona (anel de chama azul); nome Ego (azul com chamas e contorno branco); placa Metavisão; faixa Gaiola Azul;
  efeito de avatar **Aura da Zona**; efeito de perfil **Reação Química** (dois feixes colidem em faíscas); efeito de chat Chute Direto; pin Cadeado; som Zona. (A criatura/monstro de personagem: só com referência.)
- [x] **A10. TF2-like** (`fortaleza`): RED vs BLU, estética de pôster dos anos 60, cores dessaturadas: RED `#b8383b`, BLU `#5b7a8c`, creme `#e8dcc0`, laranja `#cf7336`. Evocar: **efeitos "Inusitados"** (partículas orbitando: chama, nuvem, plasma, parafusos, planetas),
  **caixa de suprimentos** de madeira com estêncil, **Crítico!** (estrelas e brilho), **ÜberCarga** (brilho vermelho/azul pulsando), Austrálio (ouro brilhante), cartaz de propaganda. Itens: moldura Efeito Inusitado (chamas orbitando) e Austrálio (anel dourado);
  nome Estêncil (letras de caixa); placa Caixa de Suprimentos; faixa Cartaz (RED vs BLU); efeito de avatar **ÜberCarga** e Planetas Orbitando; efeito de perfil **Crítico!**; efeito de chat Crítico; pin Caixa; som Crit (sintetizado).

### Grupo B: os adiados
- [x] **B1. Chama Azul (JJK)** (`chamaazul`). **Ambíguo**: a nota original diz só "chama azul do JJK" (não existe um personagem óbvio com chama azul). Pergunte UMA vez qual técnica ele quis; padrão se não souber:
  a **energia amaldiçoada em chama azul-branca** envolvendo a foto (efeito de avatar, chamas que sobem), moldura Chama Azul, nome em azul/branco, placa Aura, faixa Céu Maldito, efeito de perfil Fogo Azul (cartão em chamas azuis com bordas escurecendo). Já existem Gojo (branco/azul/roxo), Sukuna (vermelho) e Mahoraga (dourado): não repetir o "Azul" do Gojo.
- [x] **B2. Homem-Aranha** (`teia`): vermelho `#d4161e`, azul `#1a3a8c`, preto, branco. **Teia** (mandala: raios + anéis curvados entre os raios; gere por código), **sentido de aranha** (riscos tremendo ao redor da cabeça), **emblema** (o dono mandou o gráfico "Spider-Man Symbol Evolution": ele escolhe qual(is) usar e salva o arquivo pra decalcar),
  lentes brancas da máscara, skyline, fio de teia balançando. Itens: moldura Teia (anel de teia); nome Aranha (vermelho/azul com fios); placa Máscara (vermelha com teia preta, lentes que piscam); faixa Cidade (skyline ao entardecer com fios de teia);
  efeito de avatar **Sentido de Aranha** e Teia (fios disparam das bordas e grudam); efeito de perfil **Teia Gigante** (a teia se forma no cartão e uma aranha desce pelo fio); pin Aranha; som Thwip (sintetizado).
  - [x] sub-tema **Aranhaverso** (meio-tom, glitch com aberração cromática, grafite, painéis) e variações de emblema (Escarlate, 2099...).
- [~] **B3. Venom / Simbionte** (`simbionte`): **já tem 6 itens** (Rodada 26). Terminar: trocar o **símbolo** pelo decalque da imagem de referência (SIM_SIMBOLO em `cosm_temas.js`); extras de efeito de fala/radar/chat/som/pin/servidor; hero do Armazém; variação **Carnificina** (vermelho) e sub-tema "Garras" opcional.
- [x] **B4. DC** (cada um é um mini-tema de 4 a 8 itens; ampla variedade):
  - [x] **Batman / Gotham** (`gotham`): preto, cinza-azulado, amarelo; oval com morcego, **Bat-Sinal** (feixe nas nuvens), chuva, skyline gótica, morcegos voando (silhueta); efeito de perfil "Noite em Gotham" (chuva, relâmpago, morcegos cruzando).
  - [x] **Superman / Krypton** (`krypton`): escudo "S" (pentágono), capa vermelha ondulando (tecido animado), visão de calor (feixes vermelhos), rastro de voo, sol amarelo.
  - [x] **Mulher-Maravilha / Temiscira** (`temiscira`): estrela dourada, tiara, **laço dourado** (corda), braceletes que faíscam, águia.
  - [x] **Flash / Força da Velocidade** (`velocista`): raio amarelo, rastro, **imagens residuais**, faíscas de velocidade.
  - [x] **Lanterna Verde / Força de Vontade** (`vontade`): símbolo, anel verde, construtos de luz (o símbolo já existe no desenho da insígnia BAZINGA em `cosmeticos.js`).
  - [x] **Aquaman / Atlântida** (`atlantida`): tridente, ondas, bolhas, dourado + verde-água.
  - [x] **Coringa / Caos** (`caos`): cartas, sorriso (arco de dentes), roxo + verde, confete e risada (som).
  - [x] extras: Arlequina (losangos vermelho/preto), Ciborgue/Jovens Titãs (circuitos), Liga da Justiça.
- [x] **B5. Marvel** (mini-temas):
  - [x] **Homem de Ferro / Stark** (`stark`): **reator arc** (anéis azuis concêntricos girando), **HUD** (círculos e linhas), repulsor (onda/feixe), vermelho e dourado.
  - [x] **Capitão América / Escudo** (`escudo`): escudo (anéis vermelho/branco/azul + estrela) orbitando, listras.
  - [x] **Thor / Trovão** (`trovao`): martelo + raios azul-brancos (o passe já tem "Tempestade de Zeus": fazer visual diferente).
  - [x] **Hulk / Gama** (`gama`): verde, rachaduras no cartão, onda de choque.
  - [x] **Pantera Negra / Wakanda** (`wakanda`): vibranium roxo, arranhões de garra, padrões geométricos africanos.
  - [x] **Doutor Estranho / Mística** (`mistica`): **mandalas de faíscas laranja** girando, portais, símbolo do Olho de Agamotto.
  - [x] **Joias do Infinito / Thanos** (`joias`): **seis gemas** (roxa, azul, vermelha, laranja, verde, amarela) orbitando; efeito de avatar **Estalo** por cima da foto (a foto vira pó e volta). A manopla em si é mão: só com referência.
  - [x] **Deadpool / Mercenário** (`mercenario`): vermelho/preto, katanas cruzadas (armas), balões de fala, máscara com olhos brancos.
  - [x] **Wolverine / Garras** (`garras`): três arranhões, brilho metálico.
  - [x] **Feiticeira Escarlate / Caos** (`feitico`): fiapos vermelhos de magia. **Loki / Truque** (`truque`): verde/dourado, chifres em silhueta, ilusões que "falham" (glitch).

### Grupo C: genéricos (mínimos: 6 fofos, 1 grande de básicos, 5 emo, 7 assustadores, 8 banais + sazonais; cada um 6 a 10 itens; faça mais se sobrar fôlego)
- [x] **C1. Fofos (kawaii)**, pastel, formas redondas, brilhinhos: **Gatinhos** (orelhas, patinhas, bigodes, "miau"), **Docinhos** (cupcake, sorvete, bala, granulado), **Nuvens e Arco-íris**, **Coelhinhos e Ursinhos** (orelhas por cima da foto, pelúcia),
  **Frutinhas** (morango, cereja, pêssego), **Estrelinhas e Luas** (céu pastel), **Jardim** (flores, abelhinhas, borboletas), **Bolhas de Sabão**, **Chá e Bolinhos** (cottagecore), **Fadinhas** (pó de brilho), **Pinguim e Gelo**, **Cachorrinhos** (patas, ossinhos).
- [x] **C2. Básicos**: **completar o tema Básicos** com TODAS as cores (vermelho, laranja, amarelo, verde, ciano, azul, roxo, rosa, branco, preto, cinza + versões pastel e escura) em moldura/nome/placa/faixa lisos e comuns (baratos);
  mais padrões simples: **Listras, Xadrez, Bolinhas, Degradês, Quadriculado, Zigue-zague**. Tudo `comum` e sem animação (ou animação mínima), como o tema Básicos atual.
- [x] **C3. Emo / Gótico / Punk**: **Emo Noite** (preto, rosa-choque, roxo; listras, xadrez, estrelas, **corações costurados**, alfinetes, correntes), **Coração Partido** (rachadura que pulsa, estilhaços), **Chuva e Melancolia** (chuva numa janela escura, gotas, azul-cinza),
  **Gótico** (velas, rosas, vitral, morcegos), **Scene 2008** (neon, estrelas, listras de zebra, arco-íris, glitter), **Grunge / Punk** (papel rasgado, rabisco, rebites, alfinete de segurança, cartaz colado), **Vampiro** (presas, gotas de sangue, lua).
- [x] **C4. Assustadores (horror)**: **Sangue** (escorrendo: moldura e placa pingando), **Fantasmas** (lençol flutuando, olhos vazados), **Abóboras / Halloween**, **Olhos na Escuridão** (vários olhos que abrem no escuro: dá pra desenhar), **Teias e Aranhas** (teia de aranha de canto, aranhas descendo),
  **Fita VHS / Found Footage** (ruído, linhas de rastreio, **"REC" piscando e data-hora**), **Garras / Slasher** (arranhões que cortam o cartão), **Ocultismo** (círculo e pentagrama, runas, velas), **Cemitério e Névoa** (lápides, névoa à deriva),
  **Glitch / Creepypasta** (texto corrompido "zalgo", estática), **Mansão Assombrada** (janelas acesas piscando), **Esqueletos e Catacumbas** (caveiras: moldura de caveiras), **Palhaço** (balões, riso: sutil), **Lua de Sangue**, **Monstro do Armário** (garras vindo das bordas, parente do simbionte).
- [x] **C5. Banais / cotidiano**: **Café** (xícara, vapor, arte de latte), **Chuva na Janela**, **Comida** (pizza, hambúrguer, sushi, ramen, tacos: um tema cada ou um só), **Plantinhas** (suculentas, hera crescendo),
  **Livros e Estudo** (papel de caderno, marca-texto, post-it), **TV Antiga (CRT)** (estática, barras de teste), **Pôr do Sol**, **Praia / Futevôlei** (areia, rede, onda, sol: o futevôlei que o dono citou), **Acampamento / Fogueira**,
  **Academia** (halteres, suor, contador de repetições), **Escritório / Planilha** (grade de células, fórmulas), **Torcida** (verde-amarelo, bandeirinhas, confete), **Festa Junina** (bandeirinhas, fogueira, balão), **Retrô 80s / Synthwave** (sol listrado, grade de neon),
  **Vaporwave** (estátua, grade, pôr do sol rosa/ciano), **Y2K**, **Minimalista**, **Aquarela**, **Giz / Quadro-negro**, **Rabisco (doodle)**, **Sabonete e Espuma**... Pegue o que render item bonito.
- [x] **C6. Sazonais** (saem e entram por época; podem virar edição limitada): **Natal / Ano Novo** (neve, luzes, fogos), **Aniversário** (balões, confete), **Dia dos Namorados** (corações), **Carnaval**, **Páscoa**, **Dia das Bruxas** (junta com Assustadores).

## 6. Referências que o dono precisa salvar (pedir UMA vez, no começo da conversa)

A imagem colada no chat **não vira arquivo no disco** (o painel só guarda as do início da conversa em `...\scratchpad\..\images`; as que chegam no meio do turno não). Peça pra ele **salvar em `docs/refs/<tema>/`** (ver `docs/refs/LEIA-ME.md`),
com nomes claros (`simbolo.png`, `emblema.png`, `letras.png`...). Fundo liso e contraste alto decalcam melhor. Antes de pedir, veja o que já existe: `ls docs/refs/*` (o Glob pode ignorar a pasta se ela estiver no `.gitignore`).
Sugestão do que pedir (nada é obrigatório; sem a referência, faça a versão por símbolo/padrão/efeito):
- **Simbionte**: o símbolo da aranha branco no preto (ele já colou uma no chat; precisa salvar o arquivo). Esse é o que mais importa: a versão atual é aproximação.
- **Homem-Aranha**: o gráfico "Spider-Man Symbol Evolution" (ele colou) e qual emblema usar.
- **JoJo**: um print do estilo das letras "ゴゴゴ", do relógio do Za Warudo, do broche de joaninha do Giorno (o que ele quiser de fiel); personagens/Stands só se ele mandar.
- **LoL**: padrão hextech e uma moldura de elo com asas. **SNK**: barra de vida e o "FIGHT!". **TF2**: uma caixa de suprimentos e um pôster. **Brawlhalla, Umamusume, Rematch, Roblox, Rivals, Blue Lock**: o que ele achar que define a cara.
- **DC/Marvel**: os símbolos (S, morcego, escudo, reator, mandala do Doutor Estranho...) em preto e branco, se quiser fidelidade total.

## 7. O que já existe e o que NÃO ficou 100% (atualizado em 14/10/2026, Rodada 27)

**Existe** (detalhes na "Rodada 27" do `CLAUDE.md`): o **gerador** `tools/cosm/` (kit de ícones, anéis, ladrilhos, cenas, camadas de efeito e a fábrica `G()` de temas genéricos); **113 temas e ~1040 itens** em 10 categorias
(anime 11, jogos 12, quadrinhos 25, esporte 2, fofo 14, sombrio 21, dia a dia 20, datas especiais 7, básico 1 com 138 itens, fantasia só os antigos); Armazém reestruturado por categorias; os Básicos completos (22 cores x 4 slots, 22 placas
de padrão, 16 degradês e 12 faixas de padrão); novidade 27 em `app/novidades.py`.
O Passo 0 (seção 4) está feito, exceto: desempenho medido (item 6), a Coleção (resolvido de outro jeito: os itens **comuns não contam**) e as molduras de elo do LoL (item 8, opcional).

**Não ficou 100%** (corrigir ou refazer quando o dono pedir):
1. **O símbolo da aranha do Simbionte é aproximação** (precisa decalcar de um arquivo; ver seção 6) e o Simbionte não tem hero no Armazém.
2. **Nenhuma mão, rosto ou personagem foi desenhado** (não há referência em `docs/refs/`). Os temas de franquia evocam por símbolo, cor, padrão, tipografia, partícula, luz e movimento, como o dono combinou ("arte original que só evoca").
3. **Prévias de ciclo longo**: os efeitos gerados usam `--ef-prev` (começam no auge nas prévias do Armazém/Inventário/editor), mas os feitos à mão antes (Invasão Negra do Simbionte, domínios do JJK) ainda nascem vazios nelas.
4. **Desempenho não medido num computador de verdade**: o `chat.html` carrega TODOS os `cosm_*.css/js` (~2,5 MB de CSS, ~350 KB com gzip, que o `after_request` já liga) e a vitrine manda os ~1040 itens a cada abertura.
   Se pesar: carregar por categoria sob demanda (só o equipado + o que o Armazém abrir) e paginar a vitrine. A rolagem continua protegida por `body.rolando`.
5. **Não visto**: celular, call e tema claro para a maioria dos temas novos (vistos em tiras de 800 px e algumas prévias); contraste de nome sobre fundo claro; o **som** dos temas (sintetizado, nunca ouvido: a pane não toca áudio).
6. **Elos do LoL** (molduras de rank) e a Liga da Justiça como tema à parte não foram feitos.
7. Os temas feitos pela fábrica `G()` (fofos, emo, terror, dia a dia, datas) seguem o mesmo molde (anel de ícones, nome em degradê, placa de ícones, cena na faixa, efeito de avatar e de perfil); os assinaturas de cada um (VHS com contador, Ocultismo com círculo mágico,
   Sangue escorrendo, Fogos do Ano Novo, Hera da Plantinhas, Giz desenhando...) são camadas `raw` à mão. Se o dono achar algum igual aos outros, vale refazer só as camadas dele.
8. Tudo commitado e enviado em 14/10/2026 a pedido do dono (sem coluna/tabela nova: não precisa de `atualizar_banco.py`).

## 8. Receitas rápidas

- Técnica de arte, caixa padrão, efeito por cima da foto, tentáculos, gosma, SVG como fundo, QA: **`docs/ARTE_TEMAS.md`**. Registro de efeito novo: `Cosm.registrarTema({ avatar, perfil, ids })` (`cosmeticos.js` + `cosm_temas.js`).
- **Criar tema (desde a Rodada 27)**: um arquivo em `tools/cosm/temas/<nome>.js` que exporta uma lista de `tema({...})` (ou `G({...})` de `temas/_generico.js` para os genéricos); `node tools/cosm/gerar.js` escreve `app/static/css/cosm_<categoria>.css`, `js/cosm_<categoria>.js` e `app/cosm_gen.json`. **Os arquivos gerados são commitados.** Receita completa e armadilhas: `CLAUDE.md` > Rodada 27.
- **Criar item**: `_item_loja(tipo, id, nome, desc, tema, raridade)` em `app/cosmeticos.py` (o preço sai de `PRECOS`); tema novo = entrada em `TEMAS` (`loja: True`, `cores`, `icone` Font Awesome, `lema`, `desc`, `sem_hero: True`); `_pacote_loja(tema, ...)` só se quiser pacote.
  Depois o CSS (`.moldura-<id>::before`, `.ne-<id>`, `.placa-<id>` **e** `.user-profile-bar.placa-<id>`, `.banner-anim-<id>`, `.ef-av-<id>`, `.ef-pf-<id>`, `.fala-<id>`, `.radar-<id>`, `.chat-ef-<id>`, `.pin-<id>`, `.sv-ef-<id>`) e o registro JS. O `fumaca_economia.py` e o `fumaca_loja.py` falham se faltar algo.
- **Servidor de teste** (fora do repo; a pasta temporária some entre conversas): crie um `run_local.py` com SQLite descartável (`DATABASE_URL=sqlite:///.../ui.db`, `config_mod.Config.SQLALCHEMY_ENGINE_OPTIONS = {}`), `create_app()`, três pessoas (Ana com TODOS os itens do catálogo via `cos.conceder_item`, Beto sem nada, Cris com saldo),
  um servidor com canal "geral", e rotas só do script: `/debug-login/<nome>` (`session['user_id']`), `/debug-equipar/<nome>/<tipo:id>` (`cos.definir_slot`) e `/debug-pag/<arquivo>` (serve a pasta do script, pro `qa_itens.html`). Porta **5064** (a 5060 o Chromium bloqueia).
  Registre em `.claude/launch.json` (`runtimeExecutable` = o python do `.venv`, `runtimeArgs` = o script, `port`). **Mudou o catálogo (Python)? Reinicie o servidor.** Rode: `python testes/qa_itens.py <pasta do script>` pra gerar a galeria.
- **Ver de perto**: emule a janela do navegador em 800 x 465 (a captura sai 1:1); congele as animações com `document.getAnimations().forEach(a => { a.pause(); a.currentTime = N * 1000 })`; o service worker guarda `/static` pela URL (use `?v=<hora>` nas páginas de teste).
- Python do projeto: `.venv\Scripts\python.exe` (o `python` do PATH não tem o Flask). Patch de arquivo grande: use a ferramenta de escrita de arquivo (heredoc de shell com `\U` ou aspas triplas quebra).

## 9. Armadilhas conhecidas (já custaram caro)
- ~240 animações que repintam travam a rolagem: só `transform`/`opacity`; `body.rolando` pausa ao rolar.
- Id de item só `[a-z_]` (número faz o preview sumir) e até 24 caracteres.
- Nunca classe/id começando com `ad-`/`ads-` (bloqueador de anúncio esconde).
- Moldura que usa `mask`: repetir a máscara nos contextos `.pf-tile-av` e `.message .chat-avatar` (têm regra própria mais específica).
- Placa nova precisa também do seletor `.user-profile-bar.placa-<id>` com `!important`.
- Contorno claro por segmento de tentáculo deixa "vértebra" em cada junta: use `drop-shadow` no conjunto.
- Nada de mão/rosto/personagem sem referência. Nada de áudio/sprite de terceiros.
- Testes que olham `chat.html`/CSS/JS por texto: criar arquivo novo de arte exige ensinar o teste a lê-lo (hoje `fumaca_economia.py` e `fumaca_loja.py` leem `cosmeticos.css`+`cosm_temas.css` e `cosmeticos.js`+`cosm_temas.js`).
