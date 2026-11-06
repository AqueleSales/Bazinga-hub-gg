// Lógica do texto formatado (static/js/texto_rico.js) rodando no Node, sem navegador. Chamado por testes/fumaca_texto_rico.py.
const fs = require('fs'), path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'app', 'static', 'js', 'texto_rico.js'), 'utf8');
const TextoRico = new Function(src + '\nreturn TextoRico;')();
let falhas = 0;
const ok = (c, m) => { console.log((c ? 'OK   ' : 'FALHA') + ' ' + m); if (!c) falhas++; };
const ctx = {
    membros: () => [{ id: 12, nome: 'Ana <b>', username: 'ana', online: true }, { id: 7, nome: 'Beto', username: 'beto' }],
    cargos: () => [{ id: 3, nome: 'Mestres de RPG', cor: '#e91e63', icone: '🎲' }, { id: 4, nome: 'Ruim', cor: 'red; background:url(x)' }],
    meuId: 7, meusCargos: [3], souDono: false, podeGerir: false, previas: true
};
const R = (t, c) => TextoRico.render(t, c || ctx);

// ---- formatação básica ----
ok(R('**oi**') === '<strong>oi</strong>', 'negrito');
ok(R('*oi*') === '<em>oi</em>' && R('_oi_') === '<em>oi</em>', 'itálico com * e _');
ok(R('__oi__') === '<u>oi</u>', 'sublinhado');
ok(R('~~oi~~') === '<s>oi</s>', 'riscado');
ok(R('***oi***') === '<strong><em>oi</em></strong>', 'negrito e itálico');
ok(/class="spoiler"[^>]*>segredo<\/span>/.test(R('||segredo||')), 'spoiler');
ok(R('==oi==') === '<mark class="rt-mark">oi</mark>', 'destaque');
ok(R('snake_case_nome e 2*3*4') === 'snake_case_nome e 2*3*4', 'underline no meio da palavra e conta de multiplicar não viram itálico');
ok(R('\\*nada\\*') === '*nada*', 'barra invertida mostra o símbolo');
ok(R('a\nb') === 'a<br>b', 'quebra de linha vira <br>');
ok(R('a  b').includes('a  b'), 'o texto fica como foi digitado');

// ---- código ----
ok(R('`x < y`') === '<code class="cod-i">x &lt; y</code>', 'código em linha escapa');
ok(R('`**não**`') === '<code class="cod-i">**não**</code>', 'dentro do código nada é formatado');
const bloco = R('```js\nconst a = "x"; // oi\n```');
ok(bloco.includes('class="cod"') && bloco.includes('tk-k">const') && bloco.includes('tk-s">&quot;x&quot;') && bloco.includes('tk-c">// oi'), 'bloco de código com linguagem: palavra-chave, texto e comentário coloridos');
ok(bloco.includes('cod-copiar') && bloco.includes('>js</span>'), 'bloco tem botão de copiar e o nome da linguagem');
ok(R('```\nsem linguagem\n```').includes('>código</span>'), 'sem linguagem diz "código"');
ok(R('```<img src=x onerror=1>```').includes('&lt;img src=x onerror=1&gt;') && !R('```<img src=x onerror=1>```').includes('<img'), 'HTML dentro do bloco de código é escapado');
const py = R('```python\ndef f(x):\n    return x  # ok\n```');
ok(py.includes('tk-k">def') && py.includes('tk-f">f') && py.includes('tk-c"># ok'), 'python colorido');
ok(R('```sql\nSELECT * FROM t WHERE id = 1\n```').includes('tk-k">SELECT'), 'sql (sem diferenciar maiúscula)');
ok(R('```json\n{"a": true, "b": 12}\n```').includes('tk-n">12') && R('```json\n{"a": true}\n```').includes('tk-k">true'), 'json');
ok(R('```html\n<a href="x">oi</a>\n```').includes('tk-k">&lt;a'), 'html: a tag é colorida e escapada');
const gigante = R('```js\n' + 'a'.repeat(9000) + '\n```');
ok(!gigante.includes('tk-'), 'código enorme não é colorido (custo)');

// ---- blocos ----
ok(R('# Título').includes('rt-h1') && R('## Sub').includes('rt-h2') && R('### Mini').includes('rt-h3'), 'títulos');
ok(!R('#semespaco').includes('rt-h'), '"#" colado no texto não vira título');
ok(R('> citação').includes('<blockquote class="rt-q">citação</blockquote>'), 'citação');
ok(R('>>> a\nb\nc').includes('a<br>b<br>c</blockquote>'), 'citação até o fim');
ok(R('- a\n- b').includes('<ul class="rt-l"><li>a</li><li>b</li></ul>'), 'lista');
ok(R('1. um\n2. dois').includes('<ol class="rt-l"><li>um</li><li>dois</li></ol>'), 'lista numerada');
ok(R('-# miúdo').includes('rt-sub'), 'texto miúdo');
ok(R('# **negrito no título**').includes('<strong>negrito no título</strong>'), 'formatação dentro do título');

// ---- segurança: nada que a pessoa digita vira tag ----
const veneno = ['<script>alert(1)</script>', '<img src=x onerror=alert(1)>', '"><svg onload=alert(1)>', "'-alert(1)-'", '<a href="javascript:alert(1)">x</a>', '&lt;b&gt;'];
veneno.forEach(v => {
    const h = R(v);
    ok(!/<script|<img|<svg|<a href=|onerror=|onload=/i.test(h.replace(/<(?:\/?(?:strong|em|u|s|br|span|div|code|pre|mark|a)\b)[^>]*>/g, '')) || !/<(script|img|svg)/i.test(h), 'XSS: ' + v.slice(0, 28));
});
ok(!R('<script>alert(1)</script>').includes('<script'), 'tag <script> sai escapada');
ok(!R('[x](javascript:alert(1))').includes('<a'), 'javascript: nunca vira link');
ok(!R('[x](data:text/html;base64,AAAA)').includes('<a'), 'data: nunca vira link');
ok(!/<[^>]*\sonclick=/i.test(R('[x](https://a.com" onclick="alert(1))')), 'aspa no link não abre atributo');
ok(!R('https://a.com/"onmouseover="alert(1)').includes('onmouseover="'), 'aspa em link solto não abre atributo');
ok(!R('https://user:senha@a.com/x').includes('<a'), 'link com usuário:senha não vira link');
ok(!R('ftp://a.com/x').includes('<a') && !R('file:///etc/passwd').includes('<a'), 'só http e https');
ok(R('\u0001 0 \u0002') === ' 0 ' && !R('`a` \u00010\u0002').includes('\u0001'), 'marcador interno digitado é descartado');
ok(!R('\u00010\u0002 <img src=x onerror=1>').includes('<img'), 'marcador interno forjado não escapa o filtro');
const nomeMau = R('<@12>', { ...ctx, membros: () => [{ id: 12, nome: '<img src=x onerror=alert(1)>' }] });
ok(!nomeMau.includes('<img') && nomeMau.includes('&lt;img'), 'nome de pessoa na menção é escapado');
const cargoMau = R('<@&4>');
ok(!cargoMau.includes('background:url') && cargoMau.includes('--c:#99aab5'), 'cor de cargo inválida cai no cinza (nada vai pro style)');

// ---- links ----
const l1 = R('veja https://exemplo.com/a?b=1.');
ok(l1.includes('href="https://exemplo.com/a?b=1"') && l1.includes('rel="noopener noreferrer nofollow ugc"') && l1.includes('target="_blank"') && l1.endsWith('</a>.'), 'link solto: abre fora, rel seguro e o ponto final fica de fora');
ok(R('(https://a.com/x)').includes('href="https://a.com/x"') && R('(https://a.com/x)').endsWith('</a>)'), 'parêntese que fecha a frase não entra no link');
ok(R('https://pt.wikipedia.org/wiki/Foo_(bar)').includes('Foo_(bar)"'), 'parêntese que faz parte do link continua nele');
const m1 = R('[clique aqui](https://exemplo.com)');
ok(m1.includes('>clique aqui</a>') && m1.includes('data-aviso="1"'), 'link com texto: mostra o texto e marca como "mascarado" (pergunta antes de abrir)');
const m2 = R('[https://banco.com](https://golpe.com/x)');
ok(m2.includes('golpe.com') && !m2.includes('>https://banco.com<'), 'texto que parece endereço mas leva a outro lugar mostra o destino de verdade');
ok(!R('[https://a.com](https://a.com)').includes('data-aviso'), 'texto igual ao destino não precisa de aviso');
ok(R('http://exemplo.com').includes('data-aviso="1"') && R('https://192.168.0.1/x').includes('data-aviso="1"'), 'http puro e endereço IP pedem confirmação');
ok(R('https://' + 'a'.repeat(30) + '.com/' + 'b'.repeat(80)).includes('…'), 'link enorme é encurtado na tela');

// ---- prévias ----
const yt = R('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1m30s');
ok(yt.includes('data-emb="yt"') && yt.includes('data-id="dQw4w9WgXcQ"') && yt.includes('data-t="90"') && yt.includes('i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg'), 'YouTube: capa + tempo inicial, sem carregar o player');
ok(!yt.includes('<iframe'), 'o player do YouTube só carrega no clique');
ok(R('https://youtu.be/dQw4w9WgXcQ').includes('data-id="dQw4w9WgXcQ"') && R('https://youtube.com/shorts/dQw4w9WgXcQ').includes('data-id="dQw4w9WgXcQ"') && R('https://music.youtube.com/watch?v=dQw4w9WgXcQ').includes('data-emb="yt"'), 'youtu.be, shorts e YouTube Music');
ok(!R('https://youtube.com/watch?v=curto').includes('data-emb'), 'id de vídeo inválido não vira prévia');
ok(!R('https://youtube.com.golpe.com/watch?v=dQw4w9WgXcQ').includes('data-emb') && !R('https://notyoutube.com/watch?v=dQw4w9WgXcQ').includes('data-emb'), 'domínio parecido com o do YouTube não vira prévia');
ok(R('https://www.youtube.com/playlist?list=PLabcdefghijkl').includes('data-lista="PLabcdefghijkl"'), 'playlist do YouTube');
ok(R('https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC?si=x').includes('data-emb="sp"') && R('https://open.spotify.com/intl-pt/album/4uLU6hMCjMI75M1A2tKUQC').includes('data-tipo="album"'), 'Spotify (música e álbum)');
ok(R('https://soundcloud.com/artista/faixa').includes('data-emb="sc"'), 'SoundCloud');
const au = R('https://exemplo.com/som/musica%20boa.mp3');
ok(au.includes('<audio controls preload="none"') && au.includes('musica boa.mp3'), 'áudio direto: player com preload=none (nada baixa até apertar play)');
ok(R('https://exemplo.com/v.mp4').includes('<video controls preload="none"'), 'vídeo direto: preload=none');
ok(!R('http://exemplo.com/som.mp3').includes('<audio'), 'áudio por http puro não carrega');
ok((R('https://youtu.be/dQw4w9WgXcQ https://youtu.be/aaaaaaaaaaa https://youtu.be/bbbbbbbbbbb').match(/data-emb="yt"/g) || []).length === 2, 'no máximo 2 prévias por mensagem');
ok((R('https://youtu.be/dQw4w9WgXcQ https://youtu.be/dQw4w9WgXcQ').match(/data-emb="yt"/g) || []).length === 1, 'o mesmo vídeo não repete');
ok(!R('https://youtu.be/dQw4w9WgXcQ', { ...ctx, previas: false }).includes('data-emb'), 'com "prévias" desligadas só sobra o link');
ok(R('https://youtu.be/dQw4w9WgXcQ', { ...ctx, previas: false }).includes('<a class="lnk"'), '...e o link continua clicável');
ok(R('`https://youtu.be/dQw4w9WgXcQ`') === '<code class="cod-i">https://youtu.be/dQw4w9WgXcQ</code>', 'link dentro de código não vira link nem prévia');

// ---- menções ----
const mp = R('oi <@12>');
ok(mp.includes('data-perfil-id="12"') && mp.includes('@Ana &lt;b&gt;'), 'menção de pessoa com o nome escapado');
ok(R('<@7>').includes('mencao-eu'), 'quando é comigo, destaca');
ok(R('<@todos>').includes('esp-todos') && R('<@todos>').includes('mencao-eu'), '@todos (e é comigo)');
ok(R('<@aqui>').includes('esp-aqui') && R('<@staff>').includes('esp-staff') && R('<@dono>').includes('esp-dono') && R('<@amigos>').includes('esp-amigos'), '@aqui, @staff, @dono, @amigos');
ok(!R('<@staff>').includes('mencao-eu') && R('<@staff>', { ...ctx, podeGerir: true }).includes('mencao-eu'), '@staff só destaca pra quem modera');
const mc = R('<@&3>');
ok(mc.includes('--c:#e91e63') && mc.includes('@Mestres de RPG') && mc.includes('mencao-eu') && mc.includes('🎲'), 'cargo com a cor, o ícone e destaque pra quem tem o cargo');
ok(R('<@&99>').includes('@cargo'), 'cargo que não existe (mais) vira "@cargo"');
ok(R('<@abc>') === '&lt;@abc&gt;' || !R('<@abc>').includes('<@abc>'), 'token inventado não vira nada especial');

// ---- autocompletar ----
const sug = (t, extra) => TextoRico.sugestoes(t, { ...ctx, podeMencionarTodos: false, emServidor: true, ...extra });
ok(!sug('').some(i => i.id === 'todos' || i.id === 'aqui') && sug('').some(i => i.id === 'staff') && sug('').some(i => i.id === 'amigos'), 'sem a permissão não sugere @todos/@aqui; @staff e @amigos qualquer um');
ok(sug('', { podeMencionarTodos: true }).some(i => i.id === 'todos') && sug('', { podeMencionarTodos: true }).some(i => i.tipo === 'cargo' && i.token === '<@&3>'), 'com a permissão sugere @todos e os cargos');
ok(sug('every', { podeMencionarTodos: true })[0].token === '<@todos>' && sug('here', { podeMencionarTodos: true })[0].token === '<@aqui>', 'apelidos em inglês (@everyone, @here)');
ok(sug('mod')[0].token === '<@staff>' && sug('mod')[0].tipo === 'esp', 'apelido @mods');
ok(sug('an').some(i => i.tipo === 'pessoa' && i.id === 12), 'acha pessoa pelo nome');
ok(!sug('', { emServidor: false }).some(i => i.tipo !== 'pessoa'), 'na DM só aparecem pessoas');
ok(TextoRico.digitadoParaTokens('oi @todos e @Everyone', ctx) === 'oi <@todos> e <@todos>', '@todos e @Everyone viram token');
ok(TextoRico.digitadoParaTokens('chamando @Mestres de RPG já', ctx) === 'chamando <@&3> já', 'cargo com espaço no nome');
ok(TextoRico.digitadoParaTokens('email a@todos.com', ctx) === 'email a@todos.com', '"@" no meio de palavra não vira menção');
ok(TextoRico.tokensParaDigitado('<@todos> <@&3> <@12>', ctx) === '@todos @Mestres de RPG <@12>', 'editar: tokens voltam a ser @palavra (pessoa o chat resolve)');

// ---- desempenho ----
const t0 = Date.now();
R(('texto *com* **formatação** `x` https://exemplo.com/a ').repeat(1500));
ok(Date.now() - t0 < 1500, 'mensagem de 75 mil caracteres formata em menos de 1,5 s (' + (Date.now() - t0) + ' ms)');
const t1 = Date.now();
R('*'.repeat(20000) + '_'.repeat(20000) + '|'.repeat(20000));
ok(Date.now() - t1 < 1500, 'símbolos repetidos não travam (sem regex catastrófica): ' + (Date.now() - t1) + ' ms');

console.log(falhas ? `\n${falhas} FALHA(S)` : '\nTUDO OK');
process.exit(falhas ? 1 : 0);
