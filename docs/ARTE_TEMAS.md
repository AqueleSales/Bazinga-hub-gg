# Arte dos temas: como fazer cosmético bonito de verdade (Rodada 26)

Este guia é pra quem for criar tema novo. Ele junta o que deu certo (e o que deu errado) nos temas de cultura pop (Simbionte, e os que vierem).

> **Desde a Rodada 27 (14/10/2026) os temas novos NÃO são escritos à mão nos arquivos de arte: saem do gerador `tools/cosm/`** (`node tools/cosm/gerar.js`; receita e armadilhas no `CLAUDE.md` > Rodada 27 e em `docs/PLANO_TEMAS.md` §8).
> Tudo abaixo continua valendo como técnica (caixa padrão do efeito, peça por cima da foto, SVG como fundo, QA), mas o jeito de CRIAR é: um arquivo em `tools/cosm/temas/`, e para arte única uma camada `{k:'raw', html, css}`.
> O `cosm_temas.js/css` guarda só o que foi feito à mão antes (Simbionte).

## Regra de ouro: arte fiel vem de REFERÊNCIA, não de memória
- **Símbolos, logos e formas geométricas** (aranha, roda, olho, teia, runas): dá pra desenhar por código com qualidade, MAS só se houver uma imagem de referência na mão.
  Quando eu desenhei o símbolo do Simbionte "de memória" ficou uma aranha de inseto, nada a ver (o dono riu: "q porra de símbolo é esse"). A referência certa (branco no preto) resolveu o formato.
- **Mãos, rostos, personagens e criaturas**: NÃO desenhe à mão em SVG (duas tentativas ruins no JJK). Peça a imagem de referência ao dono e **decalque** (contornar a imagem, simplificar e espelhar;
  foi assim com as marcas do Sukuna: `MARCAS_SUKUNA` em `cosmeticos.js`). Sem referência, não invente: faça só o que é símbolo, padrão, tipografia e efeito.
- A imagem que o dono manda **no chat** nem sempre vira arquivo no disco. Peça pra ele salvar a imagem numa pasta do projeto (ex.: `docs/refs/`) e decalque de lá.

## A caixa padrão do efeito de avatar
- O `.ef-av` é um quadrado de **160% da foto** (`inset: -30%`; nas mensagens `-24%`, e o Gogeta no cartão chega a `-40%`). **Efeito novo tem que caber ali.**
  Num SVG de `viewBox="0 0 160 160"` a foto é o círculo de raio 50 no centro (80, 80).
- As prévias (quadradinho do perfil, catálogo, inventário, Armazém) reservam essa caixa num "palco" (`.cat-palco`, 96 px com foto de 52 px) e o quadradinho do perfil usa foto de 40 px (40 x 1,6 = 64 px)
  dentro de 72 px. Assim nada passa nem é cortado. Brilho (glow) pode passar um pouco, forma dura não.
- `testes/fumaca_economia.py` confere que nenhuma regra `.ef-av-*` usa `inset` fora de -40%..0.

## Efeito POR CIMA da foto (`.ef-av-sobre`)
O `.ef-av` fica atrás da foto (`z-index: -1`). Pra um efeito cobrir a foto (a gosma "comendo" o rosto) o efeito devolve **dois elementos irmãos**:
`<i class="ef-av ef-av-X">` (atrás, na caixa de 160%) e `<i class="ef-av-sobre ef-sobre-X">` (por cima, presa ao círculo da foto, `viewBox` 100 = a foto inteira).
Quem insere/remove o efeito ao vivo (`chat.html`) já remove os dois (`.ef-av, .ef-av-sobre`). No CSS, `.message .ef-sobre-X { display: none }`: nas mensagens (dezenas de fotos) só a parte de trás, parada.

## Como registrar o efeito que precisa de HTML gerado por código
`static/js/cosm_temas.js` (global `CosmTemas`) chama `Cosm.registrarTema({ avatar: { id: fn }, perfil: { id: fn }, ids: { fala: [...], ... } })`.
O CSS do tema mora em `static/css/cosm_temas.css` (carregado depois do `cosmeticos.css`). Moldura/nome/placa/faixa são CSS puro nesse arquivo.
O teste de economia lê os ids dos dois arquivos. Id de item só `[a-z_]` (número faz o preview sumir).

## Peças prontas
- **Tentáculo** (`CosmTemas.tentaculo`): cadeia de segmentos aninhados; cada segmento gira em volta da própria junta (`transform-origin: 0 0` num `<g>` aninhado) com atraso crescente, então a onda anda do pé à ponta.
  Só `transform`. Serve pra cipó, rabo, língua, qualquer coisa que se mexe como bicho.
- **Gosma** (filtro `#sim-goo` em `Cosm.injetarDefs`): `feGaussianBlur` + `feColorMatrix` com o alfa multiplicado: bolhas pretas se fundem como líquido. Aplique o filtro DENTRO do SVG (`<g filter="url(#sim-goo)">`), não em HTML (Safari).
- **SVG como imagem de fundo** (anel da moldura, olhos da placa, faixa): gerado em JS, entregue ao CSS por variável (`--sim-anel`, `--sim-olhos`, `--sim-faixa`). SVG usado como imagem **roda as animações CSS que estão dentro dele**
  (mas não enxerga o CSS da página: leva o próprio `<style>`). Bom pra faixa e placa, que não aceitam HTML.
- **Moldura com máscara própria**: o `chat.html` tem regras de contexto MAIS específicas (`.pf-tile-av[class*="moldura-"]::before`, `.message .chat-avatar[class*="moldura-"]::before`) com a máscara padrão do anel.
  Se a sua moldura usa `mask`, repita a máscara nesses dois contextos (ver `.pf-tile-av.moldura-gosma::before`).

## Custo e rolagem
Só `transform`/`opacity` (vão pra GPU). `body.rolando` já pausa tudo ao rolar. Nas mensagens o efeito fica parado. Dezenas de grupos animados num cartão só são aceitáveis; centenas na tela, não.
Um `filter: drop-shadow` no conjunto dá um contorno contínuo e barato (um filtro por avatar), melhor que desenhar o contorno em cada segmento (aparece uma "vértebra" em cada junta).

## Como olhar a arte de perto (QA)
A pane do navegador é pequena. `python testes/qa_itens.py <pasta>` gera `qa_itens.html` (usa o CSS REAL do `chat.html`) com moldura em 4 tamanhos, nome, placa (lista e barra do usuário), faixa em 3 tamanhos, efeito de avatar em 4 tamanhos
e um cartão inteiro. Sirva a pasta numa rota `/debug-pag/` do servidor de teste (fora do repo) e abra `?m=<moldura>&n=<nome>&p=<placa>&f=<faixa>&a=<efeito de avatar>&e=<efeito de perfil>&t=<segundos>`;
os botões congelam todas as animações em N segundos. **O service worker guarda `/static` pela URL**: a página do QA já põe `?v=<hora>` em todo arquivo, senão você enxerga arquivo velho.
Pra testar no app de verdade, reinicie o servidor de teste quando mudar o catálogo (Python não recarrega sozinho).

## Nomes
Os nomes de loja são genéricos e evocativos ("Simbionte", "Gosma Negra", "Invasão"), não a marca. A arte é fiel ao que se reconhece (símbolo, olhos, cores, movimento). Se a loja virar comercial de verdade, rever.
