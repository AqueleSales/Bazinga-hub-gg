# Estúdio de efeitos: como criar um efeito sem código

Entre em `/admin` (só admin) e abra **Efeitos**. Você monta o efeito por camadas, vê a prévia ao vivo e salva. Não precisa pedir pra ninguém escrever CSS/JS.

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

## Por que é seguro
A receita é **só números, cores e opções de uma lista**. O servidor (`app/efeitos.py`, `normalizar_receita`) descarta qualquer camada ou campo que não esteja no esquema e limita todos os números; o navegador limita de novo ao desenhar. Nada vira CSS ou JavaScript livre, então nem um admin com a conta invadida consegue injetar script por aqui.

## Como adicionar um TIPO de camada novo (pra quem mexe no código)
1. Em `app/efeitos.py`, uma entrada em `ESQUEMA` (nome, slots onde vale, dica, parâmetros com mínimo/máximo/padrão). O editor do admin e o validador leem daqui, então os controles aparecem sozinhos.
2. Em `app/static/js/efeitos.js`, uma função com o mesmo nome em `CAMADAS` (recebe `raiz`, os parâmetros, a pausa e um sorteador com semente). Use só `transform`/`opacity` (vão pra GPU) e `ciclo(dur, pausa)` pra respeitar a pausa.
3. Rode `python testes/fumaca_efeitos.py` (confere que toda camada do esquema tem desenho no motor).

## Limites honestos
- Não cobre efeitos de canvas complexos (a Amaterasu, a Punição de Alma): esses continuam feitos à mão. Peça "peças" novas (um vórtice, um fogo orgânico) e viram camada.
- Hoje só **efeito de cartão** e **efeito de avatar**. Molduras, nomes, placas, faixas, efeitos de fala/radar/pin/servidor e sons seguem à mão; entram no Estúdio nas próximas etapas (a mesma ideia: receita + motor).
- Tabela `efeito_custom` (nasce sozinha). Efeitos ficam no catálogo em memória, recarregados do banco a cada boot.
