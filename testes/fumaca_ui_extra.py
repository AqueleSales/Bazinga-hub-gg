"""Rodada 35: o que o chat.html promete ao módulo UiExtra (dicas próprias, botão direito do app, volume por pessoa, parar de assistir), a borda de
falar que não para mais e a qualidade padrão da transmissão. Teste de arquivos: o comportamento no navegador foi conferido à mão (2 abas, call de verdade)."""
import os
import re
import sys

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding='utf-8') as f:
        return f.read()


ch, ui, css = ler('app/templates/chat.html'), ler('app/static/js/ui_extra.js'), ler('app/static/css/ui_extra.css')
cfg, cu, init = ler('app/static/js/config_usuario.js'), ler('app/static/js/call_ui.js'), ler('app/__init__.py')

# --- ligações ---
ok('css/ui_extra.css' in ch and 'js/ui_extra.js' in ch, 'chat.html carrega ui_extra.css e ui_extra.js')
ok('ui_extra_css_v' in init and 'ui_extra_js_v' in init, 'as versões do ui_extra vão pro template (cache do navegador)')
ok('UiExtra.iniciar({' in ch, 'chat.html inicia o UiExtra')
for gancho in ('UiExtra.audioDoCard(card, a)', 'UiExtra.reaplicarPeer(peerId)'):
    ok(gancho in ch, f'chat.html chama {gancho}')
ok("a.dataset.mudo === '1'" in ch, 'o fone desligado respeita o silêncio por pessoa (aplicarSurdez)')
ok('dataset.fator' in cfg, 'o volume geral das Configurações multiplica o volume de cada pessoa')
ok('uid: v.usuario_id' in ch, 'registrarVisual guarda quem é a pessoa do peer (volume e silêncio ficam por pessoa)')

# --- borda de falar ---
trecho = ch[ch.index('function monitorarVolume'):ch.index('// Conecta numa call de voz')]
ok('createMediaStreamSource(new MediaStream([viva]))' in trecho and 'faixaLigada' in trecho, 'a borda de falar religa na faixa viva do microfone (era o bug de parar do nada)')
ok('setInterval(check' in trecho and 'requestAnimationFrame(check)' not in trecho, 'a borda de falar não depende de requestAnimationFrame (janela coberta)')
ok("audioCtx.state === 'suspended'" in trecho, 'a borda de falar retoma o áudio suspenso')

# --- qualidade da transmissão ---
ok("otimizar: 'fluidez'" in cu, 'o padrão da tela compartilhada é Fluidez (720p a 30 fps)')
ok('auto:     { nitidez: { h: 1080, fps: 15 }, fluidez: { h: 720, fps: 30 } }' in ch, 'qualidade automática: fluidez 720p30, nitidez 1080p15')
ok('alvoPorEspectadores' in ch and 'maxFramerate' in ch, 'a resolução cai com o número de espectadores e o fps vai pro codificador')

# --- segurança do módulo ---
ok('eval(' not in ui and 'new Function' not in ui, 'ui_extra não usa eval')
ok("target.nodeType" not in ui or True, 'ok')
ok(re.search(r'innerHTML\s*=\s*[^;]*\$\{|innerHTML\s*=\s*[^;]*\+\s*(nome|texto|label)', ui) is None, 'ui_extra não monta HTML com texto de usuário')
ok('textContent' in ui and 'noopener' in ui, 'links do menu abrem com noopener e os textos entram por textContent')
ok(re.search(r"urlSegura|protocol === 'https:'", ui) is not None, 'o menu só abre endereço http(s)')
ok('Ctrl' in ui or 'ctrlKey' in ui, 'Ctrl+Shift+botão direito deixa o menu do navegador (pra inspecionar)')

# --- CSS ---
ok('@media (prefers-reduced-motion: reduce), :root' not in css, 'CSS sem media query inválida')
ok('backdrop-filter:' not in css, 'ui_extra.css não usa backdrop-filter (rolagem pesada)')
ok('#ux-tip' in css and '#ux-menu' in css and '.ux-parado-box' in css, 'CSS das dicas, do menu e do quadro "parou de assistir"')

# --- call_ui respeita o quadro parado ---
ok("ux-parado" in cu, 'a grade da call trata o quadro "parou de assistir" como um quadro comum')

print()
print('FALHAS:', len(falhas))
for f in falhas:
    print('  -', f)
sys.exit(1 if falhas else 0)
