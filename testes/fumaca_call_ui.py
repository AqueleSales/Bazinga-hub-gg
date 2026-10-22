"""Rodada 34: tela da call (botão "+" em leque, menu dos 3 pontinhos, grade, zoom, ruído, Música por cima) e o que o chat.html promete.
Só confere arquivos e o algoritmo da grade (node, se existir); o servidor das atividades está em fumaca_atividades.py.
O que NÃO dá pra provar aqui (conferido à mão no navegador): arrastar, som, câmera/tela de verdade, celular de verdade."""
import os, re, subprocess, sys, json, shutil, tempfile
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, RAIZ)

falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding='utf-8') as f:
        return f.read()


chat = ler('app/templates/chat.html')
js = ler('app/static/js/call_ui.js')
css = ler('app/static/css/call_ui.css')
at_js = ler('app/static/js/atividades.js')
at_css = ler('app/static/css/atividades.css')
musica_css = ler('app/static/css/musica.css')
novidades = ler('app/novidades.py')

# ---- arquivos ligados no chat.html ----
for rel in ('css/call_ui.css', 'js/call_ui.js', 'css/atividades.css', 'js/atividades.js'):
    ok(f"filename='{rel}'" in chat, f'chat.html carrega {rel}')
ok(chat.index("filename='js/call_ui.js'") < chat.index('CallUI.iniciar({'), 'call_ui.js carrega antes de CallUI.iniciar()')

# ---- chess.js: versão fixa e SRI; PeerJS com o hash conferido ----
ok("URL_CHESS = 'https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js'" in chat, 'chess.js em versão fixa (0.10.3) no cdnjs')
ok(re.search(r"\[URL_CHESS\]: 'sha384-[A-Za-z0-9+/=]{64}'", chat) is not None, 'SRI (sha384) do chess.js')
ok("sha384-qOF1Ybxd53PR4BTaDzAk+eXLDARxOKQYQpXPqbJu/xkJWLIDDfP/ZusfTctQyNs+" in chat, 'SRI do PeerJS = o hash do arquivo que o unpkg e o jsdelivr entregam')
ok('OLBgp1GsljhM2TJ' not in chat, 'o hash antigo do PeerJS (que bloqueava toda call) saiu')
ok("carregarLib(URL_CHESS)" in chat, 'o xadrez baixa o chess.js sob demanda (carregarLib), não no <head>')

# ---- barra da call: ids que outros códigos usam continuam ----
for i in ('cf-main', 'btn-main-screen', 'btn-main-clip', 'media-popup', 'pop-btn-gravar', 'pop-btn-clipar', 'switch-clip-auto', 'clip-alerta', 'clip-gaveta',
          'btn-main-mic', 'btn-main-deafen', 'btn-main-camera', 'btn-main-disconnect', 'btn-side-ruido'):
    ok(f'id="{i}"' in chat, f'id {i} existe no chat.html')
ok('.media-btn-wrap, .cf-fan, #cf-camada' in chat, 'o clique fora que fecha o popup do clipe conhece o "+" e a camada do leque')
ok(re.search(r'#btn-main-screen,\s*\.media-btn-wrap', chat) is not None, 'no celular a tela compartilhada continua escondida (não existe no aparelho)')

# ---- cada ctx.X que os arquivos usam é entregue pelo chat.html ----
def bloco(inicio, fim):
    i = chat.index(inicio)
    return chat[i:chat.index(fim, i)]


def conferir_ctx(nome_arquivo, codigo, texto_bloco):
    usados = set(re.findall(r'\bctx\.(\w+)', codigo))
    faltando = sorted(u for u in usados if not re.search(r'\b' + u + r'\s*[:,(]', texto_bloco))
    ok(not faltando, f'{nome_arquivo}: tudo que usa de ctx é entregue pelo chat.html (faltando: {faltando})')


conferir_ctx('call_ui.js', js, bloco('CallUI.iniciar({', 'Atividades.iniciar({'))
conferir_ctx('atividades.js', at_js, bloco('Atividades.iniciar({', "socket.on('atividade_estado'"))

# ---- armadilha: `const X` de script clássico NÃO vira window.X (o botão de atividades ficou mudo por causa disso) ----
ok('window.Atividades' not in js and 'window.CallUI' not in at_js + js, 'ninguém procura CallUI/Atividades em window (const não vira propriedade de window)')

# ---- ganchos no chat.html ----
for gancho in ("CallUI.aoMostrar(modo)", "CallUI.aoSair(); Atividades.aoSairDaCall();", "CallUI.previaMensagem(", "CallUI.sonsLigados()", "CallUI.zoom(card)",
               "socket.on('atividade_estado'", "socket.on('atividade_erro'", "socket.on('voz_convite'", "socket.on('voz_convite_enviado'"):
    ok(gancho in chat, f'gancho no chat.html: {gancho}')
ok(chat.count('CallUI.previaMensagem(') >= 2, 'prévia de mensagem ligada no canal e na DM')
ok(re.search(r"tipo === 'call_entrar' \|\| tipo === 'call_sair'\) && !CallUI\.sonsLigados", chat) is not None, 'tocarSom respeita "Sons de entrada e saída"')

# ---- ruído: honesto e ligado na mesma chave da aba Voz e Vídeo ----
ok('Krisp' not in js + at_js + css and 'Krisp' not in chat[chat.index('btn-side-ruido'):chat.index('btn-side-ruido') + 400], 'o botão de ruído não cita Krisp')
ok('filtro do navegador' in js.lower() or 'filtro do navegador' in chat.lower(), 'texto do ruído diz que é o filtro do navegador')
ok("aplicarPerfilEntrada('personalizado')" in chat and 'function alternarRuidoRapido' in chat, 'ruído rápido passa pelo perfil Personalizado (mesma chave da aba Voz e Vídeo)')

# ---- z-index: Música por cima da call; painel de atividades entre os dois; popovers do leque acima de todos ----
z_mu = int(re.search(r'\.musica-janela \{[^}]*z-index:\s*(\d+)', musica_css).group(1))
z_call = int(re.search(r'\.call-janela \{[^}]*z-index:\s*(\d+)', chat).group(1))
z_at = int(re.search(r'\.at-painel \{[^}]*z-index:\s*(\d+)', at_css).group(1))
z_leque = int(re.search(r'#cf-camada \{[^}]*z-index:\s*(\d+)', css).group(1))
ok(z_mu > z_at > z_call, f'z-index: Música ({z_mu}) > painel de atividades ({z_at}) > janela da call ({z_call})')
ok(z_leque > z_mu, f'z-index: leque/menus ({z_leque}) acima da Música ({z_mu})')
ok('evitarSobreposicao' in js and "'musica-janela'" in js, 'a call se afasta da Música quando as duas se cobrem')

# ---- animação só com transform/opacity; nada de gradiente de enfeite nos botões novos ----
for m in re.finditer(r'transition:\s*([^;}]*)', css + at_css):
    props = m.group(1)
    ok(not re.search(r'\b(width|height|left|top|margin|padding)\b', re.sub(r'(max|min)-(width|height)', '', props)), f'transição só de transform/opacity/cor: {props.strip()[:70]}')

# ---- XSS: dado de gente nunca cru no innerHTML ----
for nome, codigo in (('call_ui.js', js), ('atividades.js', at_js)):
    ok('${a.nome}' not in codigo and '${d.de_nome}' not in codigo and '${j.nome}' not in codigo, f'{nome}: nome de pessoa não entra cru no HTML')
ok(re.search(r'esc\(a\.nome\)', js) and re.search(r'esc\(d\.de_nome\)', js) and re.search(r'esc\(j\.nome\)', at_js), 'nomes passam por esc()')
ok('ctx.escUrl(a.avatar)' in js and 'ctx.escUrl(d.de_avatar)' in js and 'ctx.escUrl(j.avatar)' in at_js, 'avatares passam por escUrl()')

# ---- atividades: lista de "em breve" e o servidor é quem decide ----
ok("pronto: false" in at_js and 'Em breve' in at_js, 'música na call e bots aparecem como "em breve"')
ok('atividade_acao' in at_js and 'chess.moves' in at_js or 'chess.moves(' in at_js, 'o cliente mostra lances possíveis e manda o pedido pro servidor')

# ---- novidade anunciada ----
ok('Call' in novidades.split('"id"')[0] or "'id': 37" in novidades or '"id": 37' in novidades, 'novidade nova no topo do novidades.py')

# ---- grade: o tamanho calculado cabe na área (roda o algoritmo de verdade no node, se existir) ----
node = shutil.which('node')
if node:
    script = (
        "const vm=require('vm'),fs=require('fs');"
        "const cx={console,localStorage:{getItem(){return null},setItem(){}}};vm.createContext(cx);"
        "vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+';this.__C=CallUI;',cx);"
        "const out=[];for(const [W,H] of [[1000,600],[420,500],[360,640],[1400,800],[300,180]]){for(let n=1;n<=16;n++){"
        "const g=cx.__C._teste.melhorGrade(n,W,H,12);out.push([W,H,n,g.w,g.h]);}}"
        "console.log(JSON.stringify(out));"
    )
    r = subprocess.run([node, '-e', script, os.path.join(RAIZ, 'app/static/js/call_ui.js')], capture_output=True, text=True)
    if r.returncode != 0:
        ok(False, 'não consegui rodar o algoritmo da grade no node: ' + r.stderr[:200])
    else:
        linhas = json.loads(r.stdout)
        cabe = True
        for W, H, n, w, h in linhas:
            if w <= 0 or h <= 0:
                cabe = False; continue
            # existe um nº de colunas em que n quadros desse tamanho cabem em WxH
            if not any(c * w + (c - 1) * 12 <= W + 0.5 and -(-n // c) * h + (-(-n // c) - 1) * 12 <= H + 0.5 for c in range(1, n + 1)):
                cabe = False
                print('   não cabe:', W, H, n, round(w), round(h))
        ok(cabe, 'a grade calculada cabe na área para 1 a 16 pessoas em 5 tamanhos de janela')
        um = [(w, h) for W, H, n, w, h in linhas if (W, H, n) == (1000, 600, 1)][0]
        quatro = [(w, h) for W, H, n, w, h in linhas if (W, H, n) == (1000, 600, 4)][0]
        ok(um[0] > quatro[0], 'um só quadro é maior que quatro (a grade se ajusta ao nº de pessoas)')
else:
    print('(node não encontrado: algoritmo da grade não conferido)')

print()
print('FALHAS:', len(falhas))
for f in falhas:
    print('  -', f)
sys.exit(1 if falhas else 0)
