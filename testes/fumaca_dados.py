"""Rodada 39: dados de RPG (d4 a d100, vários dados, modificador, vantagem/desvantagem, "manter os maiores"), moedas e os dados 3D.

Servidor: a expressão é lida por uma lista FECHADA (nada de eval), os limites valem (30 dados, +-999, 10 moedas), o resultado sai do SystemRandom e o
histórico leva o detalhe de cada dado (quais ficaram). Cliente: a matemática do 3D e da bandeja roda no Node (testes/dados3d_logica.js)."""
import os, subprocess, sys, statistics
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['LIMITE_EVENTOS'] = '0'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import jogos

falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
def ler(rel): return open(os.path.join(RAIZ, rel), encoding='utf-8').read()

def mesa(): return jogos.DadosESorteio(1)
def rolar(m, **kw): return m.acao(1, 'Ana', None, {'acao': 'rolar', **kw})

# ---------- a leitura da expressão ----------
g, mod = jogos.ler_expressao('2d20kh1+1d6+5')
ok(len(g) == 2 and g[0] == {'dado': 'd20', 'qtd': 2, 'sinal': 1, 'manter': ('kh', 1)} and g[1]['dado'] == 'd6' and mod == 5, 'lê 2d20kh1+1d6+5')
g, mod = jogos.ler_expressao(' D8 - 1d4 - 2 ')
ok([x['sinal'] for x in g] == [1, -1] and mod == -2, 'espaços, maiúsculas e sinais de menos')
ok(jogos.ler_expressao('d100')[0][0]['qtd'] == 1, 'sem número = 1 dado')
for ruim, motivo in [('', 'vazia'), ('2d7', 'dado que não existe'), ('d20+', 'sinal sobrando'), ('abc', 'lixo'), ('31d6', 'dados demais'), ('2d6kh3', 'ficar com mais do que rolou'),
                     ('2d6kh0', 'ficar com zero'), ('d20+5000', 'modificador gigante'), ('__import__("os")', 'tentativa de código'), ('1d20+' * 30 + '1d20', 'comprida demais'),
                     ('2d6**2', 'potência'), ('d20/2', 'divisão'), ('0d6', 'zero dados'), ('2d20kx1', 'sufixo inventado')]:
    try:
        jogos.ler_expressao(ruim); ok(False, f'expressão {motivo} ({ruim[:20]!r}) deveria ser recusada')
    except jogos.ErroRolagem:
        ok(True, f'recusa expressão {motivo}')
ok(jogos.expressao_de({'dado': 'd20', 'modo': 'vantagem', 'mod': 3}) == '2d20kh1+3' and jogos.expressao_de({'dado': 'd20', 'modo': 'desvantagem'}) == '2d20kl1', 'vantagem e desvantagem viram 2d20kh1/kl1')
ok(jogos.expressao_de({'dado': 'd6', 'qtd': 3, 'mod': -2}) == '3d6-2', 'pedido estruturado vira expressão')

# ---------- rolando ----------
m = mesa()
ok(rolar(m, expr='2d20kh1+5') == (True, ''), 'rola uma expressão')
e = m.historico[0]
v = e['grupos'][0]['valores']
ok(e['tipo'] == 'rolagem' and e['id'] == 1 and e['total'] == max(v) + 5 and e['texto'] == str(max(v) + 5) and e['grupos'][0]['mantidos'] == [v.index(max(v))], 'vantagem fica com o MAIOR e o total soma o modificador')
for _ in range(60):
    rolar(m, expr='2d20kl1')
    x = m.historico[0]; vv = x['grupos'][0]['valores']
    assert x['total'] == min(vv)
ok(True, 'desvantagem fica com o MENOR (60 rolagens)')
for _ in range(60):
    rolar(m, expr='4d6kh3')
    x = m.historico[0]; vv = x['grupos'][0]['valores']
    assert x['total'] == sum(sorted(vv)[1:]) and len(x['grupos'][0]['mantidos']) == 3
ok(True, '4d6kh3 soma só os 3 maiores (60 rolagens)')
rolar(m, expr='1d20-1d4-3'); x = m.historico[0]
ok(x['total'] == x['grupos'][0]['valores'][0] - x['grupos'][1]['valores'][0] - 3, 'termo com sinal de menos subtrai')
ok(rolar(m, dado='d12', qtd=2, mod=1) == (True, '') and m.historico[0]['expr'] == '2d12+1', 'pedido estruturado também rola')
ok(rolar(m, dado='d1000') == (False, 'Dado inválido.'), 'dado fora da lista (formato antigo) continua recusado')
ok(rolar(m, expr='2d7')[0] is False and rolar(m, dado='d20', qtd='lixo')[0] is False and rolar(m, expr=['x'])[0] is False, 'pedidos quebrados voltam como erro, sem derrubar')
ids = [h['id'] for h in m.historico]
ok(len(set(ids)) == len(ids) <= jogos.MAX_HISTORICO and ids == sorted(ids, reverse=True), 'cada rolagem tem um id próprio (o mais novo primeiro) e o histórico tem teto')
m2 = mesa(); rolar(m2, dado='d6'); ok(m2.historico[0]['tipo'] == 'd6' and 1 <= int(m2.historico[0]['texto']) <= 6, 'o formato antigo (um dado só) segue igual')
ok(m.acao(1, 'Ana', None, {'acao': 'rolar', 'expr': '1d20'}, ouvinte=True)[0] is False, 'quem só ouve a call não rola')

# estatística básica: o d20 cobre de 1 a 20 e não é viciado de forma absurda
m3 = mesa(); amostra = []
for _ in range(2000):
    rolar(m3, expr='1d20'); amostra.append(m3.historico[0]['total'])
ok(min(amostra) == 1 and max(amostra) == 20 and 9.5 < statistics.mean(amostra) < 11.5, f'd20: de 1 a 20, média {statistics.mean(amostra):.2f}')
m4 = mesa(); soma10 = set()
for _ in range(400):
    rolar(m4, expr='1d10'); soma10.add(m4.historico[0]['total'])
ok(soma10 == set(range(1, 11)), 'd10 sai de 1 a 10 (e só isso)')
m5 = mesa(); r100 = []
for _ in range(500):
    rolar(m5, expr='1d100'); r100.append(m5.historico[0]['total'])
ok(min(r100) >= 1 and max(r100) <= 100 and max(r100) > 90, 'd100 vai de 1 a 100')

# ---------- moedas ----------
mm = mesa()
mm.acao(1, 'Ana', None, {'acao': 'moeda'}); ok(mm.historico[0]['texto'] in ('Cara', 'Coroa') and len(mm.historico[0]['moedas']) == 1, 'uma moeda: cara ou coroa')
mm.acao(1, 'Ana', None, {'acao': 'moeda', 'qtd': 5}); x = mm.historico[0]
ok(len(x['moedas']) == 5 and f"{x['moedas'].count('Cara')} cara" in x['texto'], f'cinco moedas: {x["texto"]}')
mm.acao(1, 'Ana', None, {'acao': 'moeda', 'qtd': 99}); ok(len(mm.historico[0]['moedas']) == jogos.MAX_MOEDAS, 'no máximo 10 moedas')
ok(mm.acao(1, 'Ana', None, {'acao': 'moeda', 'qtd': 'x'})[0] is False, 'quantidade de moedas inválida é recusada')

# ---------- o que o cliente promete ----------
chat = ler('app/templates/chat.html'); aj = ler('app/static/js/atividades_jogos.js'); d3 = ler('app/static/js/dados3d.js'); ati = ler('app/static/js/atividades.js'); css = ler('app/static/css/atividades.css')
ok('js/dados3d.js' in chat and chat.index('js/dados3d.js') < chat.index('js/atividades_jogos.js'), 'chat.html carrega o dados3d antes dos jogos')
ok('AtividadesJogos.depois(corpo, estado, ajudantes())' in ati, 'o painel chama o gancho que põe os dados 3D')
ok('eval(' not in d3 and 'innerHTML' not in d3 and 'new Function' not in d3, 'dados3d.js não usa eval nem innerHTML')
ok('prefers-reduced-motion' in d3 and 'cancelAnimationFrame' in d3, 'respeita "reduzir movimento" e para o laço')
ok('requestAnimationFrame(quadro)' in d3 and 'A.raf = 0; A.fim = true' in d3, 'o laço só roda enquanto anima')
ok('.aj-d3' in css and '.aj-dados7' in css and '.aj-passo' in css, 'CSS do palco 3D e da bandeja')
ok(all(f'data-d="{d}"' in aj or d in aj for d in ('d4', 'd6', 'd8', 'd10', 'd12', 'd20', 'd100')), 'os sete dados estão na interface')
saida = subprocess.run(['node', os.path.join(RAIZ, 'testes', 'dados3d_logica.js')], capture_output=True, text=True, encoding='utf-8')
falhas_node = [l for l in saida.stdout.splitlines() if l.startswith('FALHA')]
ok(saida.returncode == 0 and not falhas_node, 'a geometria 3D, a animação e a bandeja passam nos testes do Node (%d verificações)' % sum(1 for l in saida.stdout.splitlines() if l.startswith(('OK', 'FALHA'))))
for l in falhas_node: print('     ', l)

print('\n' + ('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S)'))
sys.exit(1 if falhas else 0)
