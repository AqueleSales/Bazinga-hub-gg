# Plano: o "Guardião" (IA de segurança das calls, do chat e das denúncias) e a IA de clipes

**Estado: só plano, nada construído.** Reescrito em 13/10/2026 com o que o dono pediu: **o mais gratuito possível (Gemini)**, ficar **inativa** na call e só **acordar com palavra-chave**, analisar o **contexto** dos últimos segundos
(quantas pessoas, se tem tela compartilhada, o que está sendo dito e mostrado), distinguir ofensa de apelido, servir de **intermediária** das denúncias e, no futuro, apoiar o encaminhamento a autoridades.
Abaixo: o que dá pra fazer, **o que eu mudaria e por quê** (são três coisas importantes), e o passo a passo.

## Três pontos em que eu discordo do pedido (leia primeiro)

### 1. "Escondida" não: tem que ser **visível**
Ouvir e analisar a fala de pessoas **sem avisar** é o tipo de coisa que dá problema de verdade: LGPD (transparência, finalidade e consentimento), sigilo das comunicações (Marco Civil), e confiança dos usuários
(foi a falta de transparência que fez as pessoas se revoltarem contra outras plataformas). A versão segura é igual em eficácia e muito mais defensável:
- Um **ícone "Guardião ativo"** na call, aviso ao entrar ("esta call tem moderação automática: só ouve palavras de risco e analisa o trecho em volta quando uma é dita") e texto claro na política de uso.
- Quem decide ligar é o **dono do servidor** (e vem **ligado por padrão em servidor público/Explorar**). **Chamada 1-a-1 por DM e DM nunca são analisadas** (só se alguém denunciar).
- Isso não atrapalha a proteção: quem faz algo grave não vai deixar de fazer porque viu o ícone, e o ícone deixa o resto da comunidade mais segura.

### 2. "Gratuito" tem um custo escondido: privacidade
A API do Gemini tem camada gratuita, **mas os limites são baixos, mudam, e (confira os termos atuais em ai.google.dev) no plano gratuito o Google pode usar o conteúdo enviado pra melhorar os produtos dele**.
Mandar áudio/imagem de uma call (com menores, inclusive) pra lá não é uma boa ideia. Então o desenho é:
- **O gatilho roda no aparelho** (grátis, sem enviar nada). Só quando ele dispara, sobe **texto curto** (a transcrição dos últimos ~30 s) + metadados (nº de pessoas, tela sim/não). **Nunca áudio, nunca vídeo.**
- Imagem da tela compartilhada: um **detector local de conteúdo adulto** (existem modelos que rodam no navegador, como o NSFWJS; precisam de teste de erros) olha o quadro; **só se der alto** o app sobe um aviso/quadro desfocado.
- Quando o app crescer (ou antes de mandar imagem pra nuvem): **plano pago** do Gemini (não usa os dados pra treino e o modelo "Flash-Lite" custa centavos nesse volume).
- O código fica atrás de uma interface (`moderar(provedor, ...)`): trocar Gemini por outro modelo não muda o resto.

### 3. Não automatizar denúncia à polícia
Uma IA que erra (e vai errar, principalmente com gíria, ironia e apelido) acusando alguém **diretamente** a uma autoridade é risco jurídico pra você e injustiça pra quem for inocente. O desenho certo:
**a IA monta o dossiê, uma pessoa revisa, e o responsável envia ao canal oficial.** No Brasil: SaferNet (denúncia e orientação), Disque 100, delegacias de crimes cibernéticos e a Polícia Federal nos casos graves.
Conteúdo de **exploração sexual de crianças e adolescentes** tem regra própria (remoção e comunicação obrigatórias): **fale com um advogado** antes de lançar e deixe esse caso como prioridade máxima no fluxo.
O app já guarda os registros que ajudam uma investigação (mensagens, horários, IDs); **entrega de dados à polícia só por ordem judicial** (ou nos casos que a lei obrigar), nunca "por iniciativa da IA".

## Como funciona, em camadas (cada uma só liga se a anterior disparar)

| Camada | Onde roda | Custo | O que faz |
|---|---|---|---|
| **0. Palavras de risco** | No aparelho (texto do chat) e no gatilho de voz | zero | Lista de termos por categoria (xingamento, racismo, homofobia, golpe, sexual, ameaça). Só detecta, não decide. |
| **1. Contexto** | Gemini (texto) | grátis a poucos centavos | Recebe a janela de ~30 s de transcrição + metadados e responde em JSON se é ofensa real, apelido entre amigos, citação, brincadeira ou nada. |
| **2. Imagem** | Local (NSFWJS) e, se preciso, Gemini | grátis | Só com tela compartilhada **e** gatilho ativo. |
| **3. Ação** | Servidor | zero | Gradual e **reversível** (ver abaixo). |
| **4. Dossiê** | Servidor | zero | Pacote pra revisão humana e eventual encaminhamento. |

### O "contexto" (o caso do apelido)
O prompt manda o modelo considerar: se as pessoas se tratam com intimidade (histórico curto da conversa), se o termo é apelido combinado, se há risada/tom brincalhão no texto, se é citação ("ele me chamou de X"), e se o alvo reagiu mal. Resposta obrigatória em JSON:
`{"categoria": "...", "gravidade": 0-3, "confianca": 0-1, "contexto": "apelido|brincadeira|citacao|ofensa|ameaca|nenhum", "motivo": "frase curta"}`.
**Gravidade 0/1 não faz nada além de registrar.** Só gravidade 2+ com confiança alta chega a uma pessoa. Mesmo assim vai errar às vezes: por isso a IA é uma **medida protetora, não absoluta** (como você mesmo disse), e toda decisão passa por revisão.

### Ações (da mais leve à mais pesada; **sempre reversíveis e temporárias**)
1. Aviso privado ao moderador/dono da call ("o Guardião ouviu algo que pode ser grave; ver trecho").
2. Silenciar a call ou desligar a tela compartilhada por alguns minutos.
3. Fechar a call por 10 minutos e avisar o dono.
4. Tirar o servidor do Explorar (já existe no Estúdio) e abrir caso na fila.
5. **Derrubar servidor, banir pessoa, apagar conta: só um admin humano** (já existem banimento do Bazar e despublicar do Explorar).
Gravíssimo com confiança altíssima (ex.: imagem de abuso infantil): corta a tela na hora, guarda o dossiê e **avisa o admin pra agir em minutos**.

### Denúncias (o intermediário)
Denúncia de pessoa/servidor/mensagem/loja entra numa **fila única no Estúdio** (aba "Denúncias", hoje "em breve"). A IA lê **só o que foi denunciado** (mensagem + as 5 anteriores, ou o trecho da call) e devolve: categoria, gravidade, resumo e
"parece falso positivo?". O admin vê a sugestão e decide. Se for caso pra autoridade, o Estúdio gera o **dossiê** (PDF/JSON com trecho, horários, IDs, motivo) pra você encaminhar. Tudo fica num log (`moderacao`): quem viu, quando, o que decidiu.

## O gatilho de voz (a parte técnica difícil)
- **Web Speech API** do Chrome: grátis e simples, **mas manda o áudio pra nuvem do Google** (então precisa estar no aviso) e não funciona no app do Windows (Electron) sem chave.
- **Whisper pequeno rodando no aparelho** (WebAssembly, ~40 MB, baixa uma vez): privado e grátis, **pesa a CPU** (ok no PC, ruim em celular fraco). É o que eu recomendo.
- **Quem ouve quem:** cada aparelho transcreve **o que ele mesmo ouve** da call (o gravador já mistura todo o áudio num `AudioContext`; o gatilho usa o mesmo caminho). Distribui o peso e não depende de um servidor de mídia (a call é P2P).
- Limite honesto: um aparelho alterado (cliente modificado) pode simplesmente não rodar o Guardião. É por isso que é **proteção, não garantia**; a denúncia das outras pessoas da call continua sendo a rede de segurança.

## Passo a passo (nesta ordem)
1. **Decisões e política** (sem código): aviso visível, quem liga o Guardião, categorias (`docs/POLITICA_CONTEUDO.md`, eu rascunho pra você e um advogado revisarem), o que é "apelido".
2. **Fila de Denúncias no Estúdio + log `moderacao`** (sem IA). Já resolve a revisão e é a base de tudo. Teste: `testes/fumaca_moderacao.py`.
3. **Botão "Denunciar mensagem"** (hoje não existe) e denúncia de servidor do Explorar.
4. **Camada 0 no texto** (lista de palavras) só pra **pré-ordenar a fila** (quem é mais urgente), sem bloquear ninguém.
5. **Gemini no texto**, só nas denúncias (prompt de contexto + JSON). Chave `GEMINI_API_KEY` no Render; teto diário de chamadas; se falhar ou estourar a cota, **segue sem IA** (nunca derruba o app).
6. **Guardião de call, versão mínima:** ícone visível + gatilho local por palavra + janela de transcrição + metadados + Gemini + **aviso privado ao dono** (ação 1). Sem ação automática ainda.
7. **Imagem da tela:** detector local; se alto, desfoque/aviso.
8. **Ações graduais 2 e 3** (silenciar, fechar a call por 10 min), com botão "desfazer" pro dono.
9. **Dossiê e encaminhamento** (PDF/JSON) e o fluxo com advogado/SaferNet.
10. **Métricas:** quantas análises, quantas viraram ação, **falsos positivos** (liberados pelo admin depois de a IA marcar). Ajustar prompt, listas e limites com esses números. Revisar viés (gíria regional, AAVE/pt-BR, humor).

## IA de clipes (continua igual ao plano anterior, resumido)
Consentimento visível a todos na call, detecção barata de picos no navegador (volume, risada, vários falando, tela compartilhada), segmento de ~30 s (10 s antes, 20 s depois) e, opcionalmente, transcrição local + Gemini em **texto** pra
sugerir o título. Nunca subir áudio/vídeo bruto. Corte real do arquivo exige ffmpeg.wasm (fora de escopo). O gatilho de voz do Guardião e o dos clipes podem **compartilhar a mesma transcrição local**: um custo só.

## O que preciso de você pra começar
1. OK em tornar o Guardião **visível** (ícone + aviso) e **ligado por padrão só em servidor público**.
2. OK em **nunca** enviar áudio/vídeo pra nuvem (só texto curto) e em **não automatizar** denúncia à polícia.
3. Um **advogado** (ou orientação jurídica) antes do Passo 9, principalmente pro caso de abuso infantil.
4. Chave do Gemini (grátis no começo) e o teto diário de chamadas.
5. Quer que eu comece pelos Passos 2 e 3 (fila de denúncias, que não gasta nada e já protege)?
