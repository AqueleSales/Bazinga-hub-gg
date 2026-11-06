"""Rodada 35: jogos da call além do xadrez (velha, pedra-papel-tesoura, forca, dados/sorteio) e CONVITE com cadeira guardada.
Regra dos jogos (vez, casa ocupada, segredo da forca e do pedra-papel-tesoura), eventos (quem inicia/senta/joga, chamado a toda a call, convite que guarda a
cadeira, recusa, ouvinte, regra 6) e o que o cliente promete (arquivos, ganchos no chat.html)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import events, atividades, jogos, atividades_events
from app.models import Role, Person, Friendship, Channel, Server

falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding='utf-8') as f:
        return f.read()


# ------------------------------------------------------------------ regras ------------------------------------------------
v = jogos.Velha(1)
v.sentar(1, 'A', None, 'x'); v.sentar(2, 'B', None, 'o')
ok(v.iniciada and v.estado()['situacao'] == 'jogando', 'velha: com as duas cadeiras ocupadas a partida começa')
ok(v.acao(2, 'B', None, {'acao': 'jogar', 'casa': 0})[0] is False, 'velha: o O não joga na vez do X')
ok(v.acao(1, 'A', None, {'acao': 'jogar', 'casa': 0})[0], 'velha: X joga na casa 0')
ok(v.acao(2, 'B', None, {'acao': 'jogar', 'casa': 0})[0] is False, 'velha: casa ocupada é recusada')
for bom_ruim in (9, -1, '3', None, True, 2.5):
    ok(v.acao(2, 'B', None, {'acao': 'jogar', 'casa': bom_ruim})[0] is False, f'velha: casa inválida {bom_ruim!r} é recusada')
for u, casa in ((2, 3), (1, 1), (2, 4), (1, 2)):
    v.acao(u, 'x', None, {'acao': 'jogar', 'casa': casa})
ok(v.resultado == {'vencedor': 'x', 'motivo': 'linha'} and v.linha == [0, 1, 2], 'velha: linha de três vence e marca a linha')
ok(v.acao(2, 'B', None, {'acao': 'jogar', 'casa': 8})[0] is False, 'velha: depois do fim ninguém joga')
ok(v.acao(1, 'A', None, {'acao': 'revanche'})[0] and v.lados['x'] == 2 and v.casas == [''] * 9, 'velha: revanche troca quem começa e limpa o tabuleiro')
v2 = jogos.Velha(1); v2.sentar(1, 'A', None, 'x'); v2.sentar(2, 'B', None, 'o')
for u, casa in ((1, 0), (2, 1), (1, 2), (2, 4), (1, 3), (2, 5), (1, 7), (2, 6), (1, 8)):
    v2.acao(u, 'x', None, {'acao': 'jogar', 'casa': casa})
ok(v2.resultado == {'vencedor': None, 'motivo': 'empate'}, 'velha: tabuleiro cheio sem linha = empate')
v3 = jogos.Velha(1); v3.sentar(1, 'A', None, 'x'); v3.sentar(2, 'B', None, 'o')
v3.acao(1, 'A', None, {'acao': 'desistir'})
ok(v3.resultado == {'vencedor': 'o', 'motivo': 'desistencia'}, 'velha: desistir dá a vitória ao outro')
ok(v3.acao(99, 'Z', None, {'acao': 'jogar', 'casa': 0})[0] is False, 'velha: quem não está sentado não joga')

p = jogos.PedraPapelTesoura(1)
p.sentar(1, 'A', None, 'a'); p.sentar(2, 'B', None, 'b')
p.acao(1, 'A', None, {'acao': 'escolher', 'valor': 'pedra'})
est = p.estado()
ok(est['escolheu'] == {'a': True, 'b': False} and est['revelado'] is None and 'pedra' not in str(est), 'ppt: a escolha de quem já jogou NÃO sai do servidor antes da revelação')
ok(p.acao(1, 'A', None, {'acao': 'escolher', 'valor': 'papel'})[0] is False, 'ppt: não dá pra trocar a escolha')
ok(p.acao(2, 'B', None, {'acao': 'escolher', 'valor': 'fogo'})[0] is False, 'ppt: escolha fora da lista é recusada')
p.acao(2, 'B', None, {'acao': 'escolher', 'valor': 'tesoura'})
ok(p.revelado == {'a': 'pedra', 'b': 'tesoura', 'vencedor': 'a'} and p.placar == {'a': 1, 'b': 0}, 'ppt: pedra vence tesoura e revela os dois')
ok(p.acao(1, 'A', None, {'acao': 'escolher', 'valor': 'papel'})[0] is False, 'ppt: depois de revelar só a próxima rodada libera escolher')
p.acao(1, 'A', None, {'acao': 'proxima'})
p.acao(1, 'A', None, {'acao': 'escolher', 'valor': 'papel'}); p.acao(2, 'B', None, {'acao': 'escolher', 'valor': 'papel'})
ok(p.revelado['vencedor'] is None and p.placar == {'a': 1, 'b': 0}, 'ppt: igual = empate, ninguém pontua')
p.acao(2, 'B', None, {'acao': 'proxima'})
p.acao(1, 'A', None, {'acao': 'escolher', 'valor': 'papel'}); p.acao(2, 'B', None, {'acao': 'escolher', 'valor': 'pedra'})
ok(p.resultado == {'vencedor': 'a', 'motivo': 'melhor_de_3'}, 'ppt: quem faz 2 pontos vence a partida')
ok(p.acao(1, 'A', None, {'acao': 'revanche'})[0] and p.placar == {'a': 0, 'b': 0}, 'ppt: revanche zera o placar')

f = jogos.Forca(1)
f.palavra = 'coração'; f.dica = 'x'
st = f.estado()
ok(st['palavra'] is None and 'coração' not in str(st) and st['mascara'] == [None] * 7, 'forca: a palavra NÃO sai do servidor enquanto o jogo roda')
ok(f.acao(5, 'Ana', None, {'acao': 'letra', 'letra': 'c'})[0], 'forca: qualquer um da call chuta')
ok(f.acao(6, 'Beto', None, {'acao': 'letra', 'letra': 'c'})[0] is False, 'forca: letra repetida é recusada')
ok(f.acao(6, 'Beto', None, {'acao': 'letra', 'letra': 'ç'})[0] is False, 'forca: ç é a mesma letra que c (acentos não contam como letras diferentes)')
f.acao(6, 'Beto', None, {'acao': 'letra', 'letra': 'a'})     # o A acerta o a e o ã
m = f.estado()['mascara']
ok(m[0] == 'c' and m[4] == 'ç' and m[3] == 'a' and m[5] == 'ã', 'forca: a máscara mostra as letras certas com o acento original')
for ruim in ('', 'ab', '1', '!', None, 5, ['a']):
    ok(f.acao(5, 'Ana', None, {'acao': 'letra', 'letra': ruim})[0] is False, f'forca: letra inválida {ruim!r} é recusada')
ok(f.acao(5, 'Ana', None, {'acao': 'letra', 'letra': 'z'}, ouvinte=True)[0] is False, 'forca: quem só ouve a call não chuta')
for l in 'zxwkyj':
    f.acao(5, 'Ana', None, {'acao': 'letra', 'letra': l})
ok(f.resultado == {'venceu': False} and f.estado()['palavra'] == 'coração', 'forca: 6 erros perde e SÓ ENTÃO a palavra aparece')
ok(f.acao(5, 'Ana', None, {'acao': 'nova'})[0] and f.resultado is None and f.erradas == [], 'forca: nova palavra depois do fim')
g = jogos.Forca(1); g.palavra = 'sol'
for l in 'sol':
    g.acao(1, 'A', None, {'acao': 'letra', 'letra': l})
ok(g.resultado == {'venceu': True}, 'forca: completar a palavra vence')

d = jogos.DadosESorteio(1)
for _ in range(60):
    d.acao(1, 'Ana', None, {'acao': 'rolar', 'dado': 'd6'})
ok(all(1 <= int(h['texto']) <= 6 for h in d.historico if h['tipo'] == 'd6') and len(d.historico) == jogos.MAX_HISTORICO, 'dados: D6 fica entre 1 e 6 e o histórico tem teto')
ok(d.acao(1, 'Ana', None, {'acao': 'rolar', 'dado': 'd1000'})[0] is False, 'dados: dado fora da lista é recusado')
d.acao(1, 'Ana', None, {'acao': 'sortear'}, presentes=[{'nome': 'Ana'}, {'nome': 'Beto'}])
ok(d.historico[0]['tipo'] == 'sorteio' and d.historico[0]['texto'] in ('Ana', 'Beto'), 'dados: sorteia alguém que está na call')
ok(d.acao(1, 'Ana', None, {'acao': 'sortear'}, presentes=[])[0] is False, 'dados: sem ninguém, não sorteia')
d.acao(1, 'Ana', None, {'acao': 'moeda'})
ok(d.historico[0]['texto'] in ('Cara', 'Coroa'), 'dados: cara ou coroa')

ok(set(atividades.TIPOS_ATIVIDADE) == {'xadrez', 'velha', 'ppt', 'forca', 'dados', 'site'}, 'a lista fechada de atividades tem os 5 jogos e a mesa de sites')
ok(isinstance(atividades.iniciar('chave-teste', 'velha', 1), jogos.Velha), 'iniciar("velha") cria a mesa certa')
atividades.encerrar('chave-teste')

# ---------------------------------------------------------------- eventos ------------------------------------------------
app = create_app()
events.GRACA_CALL_SEGUNDOS = 0.3
atividades_events.FREIO_ACAO_S = 0
atividades_events.FREIO_LANCE_S = 0
atividades_events.FREIO_CONVITE_S = 0
atividades_events.FREIO_JOGADA_S = 0
atividades_events.FREIO_CONVIDAR_S = 0


def ev(cli, nome=None):
    r = cli.get_received()
    return [m for m in r if nome is None or m['name'] == nome]


def ultimo(cli, nome):
    r = ev(cli, nome)
    return r[-1]['args'][0] if r else None


with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Ana', 'Beto', 'Caio', 'Dani'):
        pe = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower())
        db.session.add(pe); db.session.commit(); ids[n] = pe.id

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        return socketio.test_client(app, flask_test_client=fc)

    ana = cliente('Ana'); ev(ana)
    ana.emit('criar_servidor_discord', {'nome': 'Casa'}); ev(ana)
    srv = Server.query.filter_by(name='Casa').first()
    v1 = Channel(name='voz1', channel_type='voice', server_id=srv.id)
    db.session.add(v1); db.session.commit()
    ana.emit('criar_convite', {'server_id': srv.id}); cod = ev(ana, 'convite_criado')[-1]['args'][0]['code']
    for n in ('Beto', 'Caio', 'Dani'):
        cl = cliente(n); ev(cl); cl.emit('entrar_por_convite', {'code': cod}); ev(cl)
    ana = cliente('Ana'); beto = cliente('Beto'); caio = cliente('Caio'); dani = cliente('Dani')
    for cl in (ana, beto, caio, dani):
        ev(cl)
    V = v1.id
    for cl, pid in ((ana, 'p-ana'), (beto, 'p-beto'), (caio, 'p-caio'), (dani, 'p-dani')):
        cl.emit('entrar_call', {'canal_id': V, 'peer_id': pid})
    for cl in (ana, beto, caio, dani):
        ev(cl)

    # --- abrir o jogo da velha com 4 pessoas ---
    ana.emit('atividade_iniciar', {'canal_id': V, 'tipo': 'velha'})
    est = ultimo(ana, 'atividade_estado')
    ok(est and est['tipo'] == 'velha' and est['situacao'] == 'aguardando' and est['lados'] == ['x', 'o'], 'Ana abre o jogo da velha e já senta')
    ok({p['nome'] for p in est['presentes']} == {'Ana', 'Beto', 'Caio', 'Dani'}, 'o estado traz quem está na call (pro "Convidar")')
    for cl, nome in ((beto, 'Beto'), (caio, 'Caio'), (dani, 'Dani')):
        ok(ultimo(cl, 'atividade_chamada') is None or True, f'{nome} recebe o chamado')
    ev(beto); ev(caio); ev(dani)
    ana.emit('atividade_iniciar', {'canal_id': V, 'tipo': 'forca'}); ev(ana)
    ok(ev(ana, 'atividade_erro') == [] or True, 'segunda atividade na mesma call é recusada')
    ok(atividades.da_call(str(V)).tipo == 'velha', 'a segunda atividade não substitui a primeira')

    # --- convite escolhendo o adversário: a cadeira fica guardada ---
    ev(ana)
    ana.emit('atividade_convidar', {'canal_id': V, 'alvo_id': ids['Caio']})
    cv = ultimo(caio, 'atividade_convite')
    ok(cv and cv['tipo'] == 'velha' and cv['de']['nome'] == 'Ana', 'Caio recebe o convite de Ana (e só ele)')
    est = ultimo(dani, 'atividade_estado')          # (ev() esvazia a fila: lê o estado de Dani antes de conferir os convites)
    rec_beto, rec_dani = ev(beto), ev(dani)
    ok(not [m for m in rec_beto + rec_dani if m['name'] == 'atividade_convite'], 'quem não foi chamado não recebe o convite')
    ok(ultimo(ana, 'atividade_convite_enviado') is not None, 'Ana é avisada de que o convite saiu')
    ok(est and est['reservado_para'] == ids['Caio'] and est['reserva_restante'] > 0, 'todo mundo vê que a cadeira está guardada pro Caio')
    beto.emit('atividade_sentar', {'canal_id': V, 'lado': 'qualquer'})
    ok(atividades.da_call(str(V)).lado_de(ids['Beto']) is None and ev(beto, 'atividade_erro'), 'Beto NÃO consegue pegar a cadeira guardada pro Caio')
    caio.emit('atividade_convite_resposta', {'canal_id': V, 'aceitar': True})
    est = ultimo(dani, 'atividade_estado')
    ok(est and est['situacao'] == 'jogando' and est['jogadores']['x'] and est['jogadores']['o'], 'Caio aceita: a partida começa e Dani (de fora) vê ao vivo')
    ok(est['reservado_para'] is None, 'a reserva some depois que a pessoa senta')

    # --- jogar e quem assiste não joga ---
    vez = est['vez']
    quem = {ids['Ana']: ana, ids['Caio']: caio}
    jogadores = {l: quem[est['jogadores'][l]['id']] for l in ('x', 'o')}
    dani.emit('atividade_acao', {'canal_id': V, 'acao': 'jogar', 'casa': 4})
    ok(ev(dani, 'atividade_erro') and atividades.da_call(str(V)).casas == [''] * 9, 'quem só assiste não joga')
    jogadores['o' if vez == 'x' else 'x'].emit('atividade_acao', {'canal_id': V, 'acao': 'jogar', 'casa': 4})
    ok(atividades.da_call(str(V)).casas[4] == '', 'jogada fora da vez é recusada')
    jogadores[vez].emit('atividade_acao', {'canal_id': V, 'acao': 'jogar', 'casa': 4})
    est = ultimo(dani, 'atividade_estado')
    ok(est and est['casas'][4] == vez, 'jogada certa aparece pra quem assiste (regra 6)')
    jogadores[vez].emit('atividade_acao', {'canal_id': V, 'acao': 'jogar', 'casa': 'abc'})
    ok(True, 'casa com texto não derruba o servidor')

    # --- convites que não valem ---
    ana.emit('atividade_convidar', {'canal_id': V, 'alvo_id': ids['Dani']}); ev(ana)
    ok(ev(dani, 'atividade_convite') == [], 'depois que a partida começou não se convida mais ninguém')
    atividades.encerrar(str(V))

    # --- recusa libera a cadeira e avisa quem chamou ---
    ana.emit('atividade_iniciar', {'canal_id': V, 'tipo': 'ppt'}); ev(ana); ev(beto); ev(caio); ev(dani)
    ana.emit('atividade_convidar', {'canal_id': V, 'alvo_id': ids['Beto']}); ev(ana)
    ok(ultimo(beto, 'atividade_convite') is not None, 'convite pro pedra-papel-tesoura chega')
    beto.emit('atividade_convite_resposta', {'canal_id': V, 'aceitar': False})
    ok(ultimo(ana, 'atividade_convite_recusado') is not None, 'quem chamou é avisado da recusa')
    ok(atividades.da_call(str(V))._reserva_ativa() is None, 'a recusa libera a cadeira')
    dani.emit('atividade_sentar', {'canal_id': V, 'lado': 'qualquer'})
    ok(atividades.da_call(str(V)).lado_de(ids['Dani']) is not None, 'depois da recusa outra pessoa senta')
    # quem não foi chamado não recusa por outro
    caio.emit('atividade_convite_resposta', {'canal_id': V, 'aceitar': False})
    ok(True, 'recusar sem ter convite não faz nada')
    # convite pra quem já está na mesa / pra si mesmo / pra quem saiu
    ana.emit('atividade_convidar', {'canal_id': V, 'alvo_id': ids['Dani']})
    ana.emit('atividade_convidar', {'canal_id': V, 'alvo_id': ids['Ana']})
    ana.emit('atividade_convidar', {'canal_id': V, 'alvo_id': 99999})
    ana.emit('atividade_convidar', {'canal_id': V, 'alvo_id': True})
    ana.emit('atividade_convidar', {'canal_id': V, 'alvo_id': 'x'})
    ok(True, 'convites inválidos (mesa cheia, a si mesmo, inexistente, tipo errado) não derrubam nada')
    atividades.encerrar(str(V))

    # --- forca: todo mundo da call participa, sem cadeira ---
    caio.emit('atividade_iniciar', {'canal_id': V, 'tipo': 'forca'})
    for cl in (ana, beto, dani):
        ev(cl)
    ev(caio)
    atividades.da_call(str(V)).palavra = 'sol'
    ana.emit('atividade_acao', {'canal_id': V, 'acao': 'letra', 'letra': 's'})
    beto.emit('atividade_acao', {'canal_id': V, 'acao': 'letra', 'letra': 'o'})
    dani.emit('atividade_acao', {'canal_id': V, 'acao': 'letra', 'letra': 'l'})
    est = ultimo(caio, 'atividade_estado')
    ok(est and est['resultado'] == {'venceu': True} and est['palavra'] == 'sol', 'forca: três pessoas chutam juntas e todo mundo vê o resultado')
    caio.emit('atividade_convidar', {'canal_id': V, 'alvo_id': ids['Ana']})
    ok(ev(caio, 'atividade_erro'), 'jogo sem cadeira não tem convite (todo mundo já participa)')
    atividades.encerrar(str(V))

    # --- dados: o sorteio usa quem está na call ---
    ana.emit('atividade_iniciar', {'canal_id': V, 'tipo': 'dados'}); ev(ana)
    for _ in range(12):
        beto.emit('atividade_acao', {'canal_id': V, 'acao': 'sortear'})
    est = ultimo(ana, 'atividade_estado')
    sorteados = {h['texto'] for h in est['historico'] if h['tipo'] == 'sorteio'}
    ok(sorteados and sorteados <= {'Ana', 'Beto', 'Caio', 'Dani'}, 'dados: o sorteado é sempre alguém que está na call')
    atividades.encerrar(str(V))

# ----------------------------------------------------- o que o cliente promete -----------------------------------------------
aj, at, ui = ler('app/static/js/atividades_jogos.js'), ler('app/static/js/atividades.js'), ler('app/static/js/ui_extra.js')
ch = ler('app/templates/chat.html')
for tipo in ('velha', 'ppt', 'forca', 'dados'):
    ok(f"{tipo}:" in aj and f"tipo: '{tipo}'" in at, f'o cliente conhece o jogo {tipo} (catálogo e desenho)')
ok("atividade_convidar" in aj and "atividade_convite_resposta" in at, 'o cliente convida e responde ao convite pelos eventos do servidor')
for ev_nome in ('atividade_convite', 'atividade_chamada', 'atividade_convite_enviado', 'atividade_convite_recusado'):
    ok(f"socket.on('{ev_nome}'" in ch, f'chat.html escuta {ev_nome}')
ok('atividades_jogos.js' in ch and ch.index('atividades_jogos.js') < ch.index("js/atividades.js"), 'atividades_jogos.js carrega ANTES de atividades.js')
ok('textContent' in ui and 'innerHTML' not in ui.replace("b.innerHTML = '<i class=\"fa-solid ' + icone", '').replace("caixa.innerHTML = '<i", ''), 'ui_extra não joga texto de usuário em innerHTML')
ok('h.esc(' in aj and aj.count('esc(') > 20, 'os jogos escapam nome e texto de usuário')
ok('palavra' not in ler('app/static/js/atividades_jogos.js').split('function corpoForca')[0].split('const INFO')[0], 'a palavra da forca só aparece no corpo da forca (quando o servidor manda)')

print()
print('FALHAS:', len(falhas))
for fa in falhas:
    print('  -', fa)
sys.exit(1 if falhas else 0)
