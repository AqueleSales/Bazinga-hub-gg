# Estúdio de efeitos: como criar um efeito sem código

Entre em **`/estudio`** (o Pantheon Estúdio, só admin; também tem atalho no `/admin`) e abra **Efeitos**. Você monta o efeito por camadas, ou **arrasta um arquivo feito fora do site** (Lottie, GIF, WebP, APNG, MP4, WebM), vê a prévia ao vivo e salva. Não precisa pedir pra ninguém escrever CSS/JS.

## Passo a passo
1. **Novo efeito**, ou **"Começar de um modelo"** (Poeira dourada, Neve, Brasas, Tempestade, Código verde, Estrelas; no avatar: Onda dourada, Satélites, Aura azul, Brasa viva).
2. Escolha **onde aparece**: *Cartão de perfil* (cobre o cartão) ou *Avatar* (em volta da foto). Não dá pra trocar depois de criado.
3. Dê **nome**, **raridade** e uma **descrição** (aparece pra quem ganhar). O id sai do nome (letras minúsculas e `_`).
4. **Adicione camadas** (até 6) e mexa nos controles: cor, quantidade, tamanho, velocidade, direção, forma...
5. **Pausa**: tempo parado entre uma passada e outra (0 = nunca para). Com pausa o efeito "respira" e fica menos poluído.
6. **Criar efeito**. Ele vira um item do catálogo na hora (`efeito_perfil:<id>` ou `efeito_avatar:<id>`).
7. Use: **Dar a mim** (teste: equipe no Inventário), **Dar a alguém**, ou ponha como **recompensa do Passe de Batalha** (escolha "Item" e procure pelo id). Quem está conectado vê a mudança na hora quando você edita.
8. **Editar** muda o efeito pra todo mundo que o tem. **Apagar** tira de todos (inventário e perfil).

## Camadas disponíveis
| Camada | Onde | O que faz | Controles |
|---|---|---|---|
| Partículas | cartão | pontinhos que sobem/descem/cruzam | cor, 2ª cor, quantidade, tamanho, duração, direção, forma (círculo/quadrado/losango/estrela), brilho |
| Brilho | cartão e avatar | luz suave que pulsa | cor, onde (topo/centro/base), força, duração |
| Raios | cartão | relâmpagos que caem | cor, quantidade, intervalo |
| Anel | avatar | onda que se expande da foto | cor, espessura, duração |
| Órbita | avatar | pontinhos girando em volta da foto | cor, quantidade, tamanho, volta |
| **Arquivo** | cartão e avatar | uma animação/imagem/vídeo feita fora do site (da biblioteca) | encaixe, tamanho, posição x/y, giro, espelho, opacidade, velocidade, aparar começo/fim, atrás ou por cima da foto (avatar) |

## Camada Arquivo (arte feita fora do site)
1. Produza a arte onde quiser (After Effects/LottieFiles, um editor de vídeo, uma IA). **Fundo transparente: exporte WebP animado, APNG ou Lottie.** GIF e vídeo MP4 não têm transparência boa: no MP4 use fundo preto e a **mistura "tela"** (o preto some, só a luz fica).
2. No Estúdio, **arraste o arquivo** na camada Arquivo (ou em *Biblioteca de arquivos*). Limites: Lottie 400 KB, imagem 3 MB (lado até 2048 px, até 240 quadros), vídeo 6 MB, até 20 s por passada, biblioteca de 120 MB.
3. Ajuste tamanho, posição, giro, espelho, opacidade; em Lottie e vídeo também velocidade e o trecho (aparar). **Pausa** e **mistura** valem pro efeito inteiro.
4. Em avatar, escolha se fica **atrás** ou **por cima da foto**.
5. Onde o efeito é pequeno (foto de mensagem/lista) ou a página está rolando, o app mostra a imagem parada; com "reduzir movimento" ligado, não desenha. No máximo 6 animações pesadas tocam juntas na tela.
6. Segurança: o Lottie não pode ter expressões (código), imagem, texto nem áudio; SVG e executáveis são recusados; o tipo vem do conteúdo, não da extensão. A receita guarda só o id do arquivo.

## Vender o efeito e juntar em pacotes (Rodada 37)
- **Vender avulso**: na caixa "Vender avulso no Armazém", o efeito ganha o preço da tabela (raridade × tipo; você não digita preço) e aparece na vitrine no tema **Estúdio**. Desmarcado, ele só se dá, entra em pacote ou vira recompensa do passe.
- **Pacotes**: em `/estudio#pacotes` você escolhe até um item por slot (moldura, nome, placa, faixa, os efeitos, som, pin), de **qualquer tema**, inclusive efeitos do Estúdio. Publique como **à venda** (preço automático -30% ou fixo até a soma, com fim de venda opcional), **só dar** ou deixe em **rascunho**. Quem recebe ou compra leva todos os itens, mesmo os que não são vendidos avulsos.
- Um efeito que está num pacote não pode ser apagado: tire-o do pacote antes.

## Por que é seguro
A receita é **só números, cores e opções de uma lista**. O servidor (`app/efeitos.py`, `normalizar_receita`) descarta qualquer camada ou campo que não esteja no esquema e limita todos os números; o navegador limita de novo ao desenhar. Nada vira CSS ou JavaScript livre, então nem um admin com a conta invadida consegue injetar script por aqui.

## Como adicionar um TIPO de camada novo (pra quem mexe no código)
1. Em `app/efeitos.py`, uma entrada em `ESQUEMA` (nome, slots onde vale, dica, parâmetros com mínimo/máximo/padrão). O editor do admin e o validador leem daqui, então os controles aparecem sozinhos.
2. Em `app/static/js/efeitos.js`, uma função com o mesmo nome em `CAMADAS` (recebe `raiz`, os parâmetros, a pausa e um sorteador com semente). Use só `transform`/`opacity` (vão pra GPU) e `ciclo(dur, pausa)` pra respeitar a pausa.
3. Rode `python testes/fumaca_efeitos.py` (confere que toda camada do esquema tem desenho no motor).

## Limites honestos
- Não cobre efeitos de canvas complexos (a Amaterasu, a Punição de Alma): esses continuam feitos à mão. Peça "peças" novas (um vórtice, um fogo orgânico) e viram camada.
- Hoje só **efeito de cartão** e **efeito de avatar**. Molduras, nomes, placas, faixas, efeitos de fala/radar/pin/servidor e sons seguem à mão; entram no Estúdio nas próximas etapas (receita + motor, e arquivo onde fizer sentido). Roadmap: ver "Rodada 36b" no `CLAUDE.md`.
- Tabelas `efeito_custom`, `estudio_arquivo` e `pacote_custom` (nascem sozinhas; a coluna `efeito_custom.vender` entra pelo boot ou pelo `atualizar_banco.py`). Efeitos ficam no catálogo em memória, recarregados do banco a cada boot.
