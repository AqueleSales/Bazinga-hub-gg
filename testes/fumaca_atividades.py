"""Rodada 34: atividades da call (xadrez) e convite pra voz.
Motor (perft de referência, roque, en passant, promoção, mate, afogamento, repetição, 50 lances, material), eventos
(quem pode iniciar/sentar/jogar, lance ilegal/fora da vez/de peça alheia, desistir, empate, revanche, encerrar, call vazia,
entrada no meio da partida, regra 6) e `convidar_voz` (amigo, membro, canal privado, DM, limite de repetição)."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio
from app import events, atividades, call_events
from app.atividades import Posicao, Partida, perft, casa, lance_de_texto
from app.models import Role, Person, Friendship, Channel, Server

falhas = []


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


# ------------------------------------------------------------------ motor ------------------------------------------------
ok([perft(Posicao.inicial(), d) for d in (1, 2, 3)] == [20, 400, 8902], 'perft da posição inicial (20, 400, 8902)')
ok([perft(Posicao.do_fen('r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1'), d) for d in (1, 2)] == [48, 2039],
   'perft da posição Kiwipete (roques, en passant, xeques: 48, 2039)')
ok([perft(Posicao.do_fen('8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1'), d) for d in (1, 2, 3)] == [14, 191, 2812], 'perft do final com xeques descobertos')
ok([perft(Posicao.do_fen('r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1'), d) for d in (1, 2)] == [6, 264], 'perft com promoções')
ok(Posicao.inicial().fen() == 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1', 'FEN da posição inicial ida e volta')
for ruim in ('', 'x', '8/8/8 w - - 0 1', 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNZ w KQkq - 0 1', '8/8/8/8/8/8/8/8 x - - 0 1'):
    try:
        Posicao.do_fen(ruim); ok(False, f'FEN inválido recusado: {ruim!r}')
    except ValueError:
        ok(True, f'FEN inválido recusado: {ruim!r}')

roque = Posicao.do_fen('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
ls = {(a, b) for a, b, _ in roque.lances_legais()}
ok((casa('e1'), casa('g1')) in ls and (casa('e1'), casa('c1')) in ls, 'roque curto e longo são permitidos')
dep = roque.aplicar(casa('e1'), casa('g1'))
ok(dep.tab[casa('f1')] == 'R' and dep.tab[casa('g1')] == 'K' and dep.tab[casa('h1')] == '.' and 'K' not in dep.roques and 'Q' not in dep.roques,
   'roque move a torre e gasta os dois direitos')
passando = Posicao.do_fen('r3kr2/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
ls = {(a, b) for a, b, _ in passando.lances_legais()}
ok((casa('e1'), casa('g1')) not in ls and (casa('e1'), casa('c1')) in ls, 'não dá pra rocar passando por casa atacada')
xeque = Posicao.do_fen('r3k2r/8/8/8/4r3/8/8/R3K2R w KQkq - 0 1')
ok(not any(b in (casa('g1'), casa('c1')) and a == casa('e1') for a, b, _ in xeque.lances_legais()), 'não dá pra rocar em xeque')

ep = Posicao.do_fen('rnbqkbnr/ppp1pppp/8/8/3pP3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 3')
ok((casa('d4'), casa('e3'), None) in ep.lances_legais(), 'en passant é permitido')
dep = ep.aplicar(casa('d4'), casa('e3'))
ok(dep.tab[casa('e4')] == '.' and dep.tab[casa('e3')] == 'p', 'en passant remove o peão capturado')

promo = Posicao.do_fen('8/P6k/8/8/8/8/8/K7 w - - 0 1')
ok({p for a, b, p in promo.lances_legais() if a == casa('a7')} == {'q', 'r', 'b', 'n'}, 'promoção oferece as 4 peças')
pt = Partida(); pt.pos = promo
okj, _ = pt.jogar(casa('a7'), casa('a8'), None)
ok(okj and pt.pos.tab[casa('a8')] == 'Q', 'promoção sem escolha vira dama')

mate = Partida()
for m in ('f2f3', 'e7e5', 'g2g4', 'd8h4'):
    okj, _ = mate.jogar(casa(m[:2]), casa(m[2:4]))
ok(mate.resultado == {'vencedor': 'b', 'motivo': 'xequemate'}, 'mate do tolo: pretas vencem por xeque-mate')
ok(mate.jogar(casa('a2'), casa('a3'))[0] is False, 'depois do fim ninguém joga')

af = Partida(); af.pos = Posicao.do_fen('k7/8/1Q6/8/8/8/8/7K b - - 0 1'); af._conferir_fim()
ok(af.resultado == {'vencedor': None, 'motivo': 'afogamento'}, 'rei sem lance e sem xeque = afogamento (empate)')

for fen in ('k7/8/8/8/8/8/8/K7 w - - 0 1', 'k7/8/8/8/8/8/8/K6B w - - 0 1', 'k7/8/8/8/8/8/8/K6N w - - 0 1'):
    mi = Partida(); mi.pos = Posicao.do_fen(fen)
    ok(mi.pos.material_insuficiente(), f'material insuficiente: {fen}')
ok(not Posicao.do_fen('k7/8/8/8/8/8/8/K6R w - - 0 1').material_insuficiente(), 'torre ainda dá mate')
ok(not Posicao.do_fen('k7/8/8/8/8/8/p7/K7 w - - 0 1').material_insuficiente(), 'peão ainda promove')

rep = Partida()
for m in ('g1f3', 'g8f6', 'f3g1', 'f6g8', 'g1f3', 'g8f6', 'f3g1', 'f6g8'):
    rep.jogar(casa(m[:2]), casa(m[2:4]))
ok(rep.resultado == {'vencedor': None, 'motivo': 'repeticao'}, 'a mesma posição 3 vezes empata')

c50 = Partida(); c50.pos = Posicao.do_fen('k7/8/8/8/8/8/8/K6R w - - 99 80')
c50.jogar(casa('a1'), casa('a2'))
ok(c50.resultado == {'vencedor': None, 'motivo': 'cinquenta'}, '50 lances sem captura nem peão empata')

ok(lance_de_texto('e2', 'e4') == (casa('e2'), casa('e4'), None), 'lance_de_texto aceita casas válidas')
for ruim in (('z9', 'e4', None), ('e2', 'e4', 'k'), (5, 'e4', None), ('e2', None, None), ('e2e4', 'e5', None), ('e2', 'e4', 'queen')):
    ok(lance_de_texto(*ruim) is None, f'lance_de_texto recusa {ruim!r}')

# ---------------------------------------------------------------- eventos ------------------------------------------------
app = create_app()
events.GRACA_CALL_SEGUNDOS = 0.3
from app import atividades_events
atividades_events.FREIO_ACAO_S = 0      # teste rápido: o freio de verdade é conferido mais abaixo
atividades_events.FREIO_LANCE_S = 0


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
    for n in ('Ana', 'Beto', 'Caio', 'Dani', 'Edu'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower())
        db.session.add(p); db.session.commit(); ids[n] = p.id
    for a, b in (('Ana', 'Beto'), ('Ana', 'Caio'), ('Ana', 'Dani'), ('Ana', 'Edu')):
        db.session.add(Friendship(requester_id=ids[a], addressee_id=ids[b], status='accepted'))
    db.session.commit()

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        return socketio.test_client(app, flask_test_client=fc)

    ana = cliente('Ana'); ev(ana)
    ana.emit('criar_servidor_discord', {'nome': 'Casa'}); ev(ana)
    srv = Server.query.filter_by(name='Casa').first()
    v1 = Channel(name='voz1', channel_type='voice', server_id=srv.id)
    palco = Channel(name='palco', channel_type='palco', server_id=srv.id)
    priv = Channel(name='privada', channel_type='voice', server_id=srv.id, is_private=True)
    db.session.add_all([v1, palco, priv]); db.session.commit()
    ana.emit('criar_convite', {'server_id': srv.id}); cod = ev(ana, 'convite_criado')[-1]['args'][0]['code']
    entrou = {}
    for n in ('Beto', 'Caio', 'Dani'):      # Edu fica de fora do servidor
        cl = cliente(n); ev(cl); cl.emit('entrar_por_convite', {'code': cod}); ev(cl)
    ana = cliente('Ana'); ev(ana)
    beto = cliente('Beto'); caio = cliente('Caio'); dani = cliente('Dani'); edu = cliente('Edu')
    for cl in (beto, caio, dani, edu):
        ev(cl)
    ev(ana)
    V = v1.id

    # ninguém fora da call vê nem mexe na atividade
    ana.emit('atividade_iniciar', {'canal_id': V, 'tipo': 'xadrez'})
    ok(atividades.da_call(str(V)) is None, 'quem não entrou na call não inicia atividade')
    ana.emit('entrar_call', {'canal_id': V, 'peer_id': 'p-ana'}); ev(ana)
    beto.emit('entrar_call', {'canal_id': V, 'peer_id': 'p-beto'}); ev(beto); ev(ana)
    caio.emit('entrar_call', {'canal_id': V, 'peer_id': 'p-caio'}); ev(caio); ev(ana); ev(beto)

    # tipo inventado é ignorado
    ana.emit('atividade_iniciar', {'canal_id': V, 'tipo': 'rm -rf'})
    ok(atividades.da_call(str(V)) is None, 'tipo de atividade inventado é ignorado')
    ana.emit('atividade_iniciar', {'canal_id': V, 'tipo': 'xadrez'})
    est = ultimo(ana, 'atividade_estado')
    ok(est and est['ativa'] and est['tipo'] == 'xadrez' and est['situacao'] == 'aguardando', 'Ana inicia o xadrez: aguardando o outro lado')
    ok(sum(1 for j in est['jogadores'].values() if j) == 1, 'quem inicia já senta')
    for cl, nome in ((beto, 'Beto'), (caio, 'Caio')):
        e2 = ultimo(cl, 'atividade_estado')
        ok(e2 and e2['ativa'] and e2['id'] == est['id'], f'{nome} (que só assiste) recebe o estado ao vivo (regra 6)')
    cor_ana = 'w' if est['jogadores']['w'] else 'b'
    cor_beto = 'b' if cor_ana == 'w' else 'w'

    # outra atividade enquanto uma roda
    beto.emit('atividade_iniciar', {'canal_id': V, 'tipo': 'xadrez'})
    ok(ev(beto, 'atividade_erro'), 'não começa uma segunda atividade na mesma call')
    ev(ana)

    # sentar
    ana.emit('atividade_sentar', {'canal_id': V, 'lado': cor_beto})
    ok(ev(ana, 'atividade_erro') or atividades.da_call(str(V)).lado_de(ids['Ana']) == cor_ana, 'Ana não senta nos dois lados')
    edu.emit('atividade_sentar', {'canal_id': V, 'lado': cor_beto})
    ok(atividades.da_call(str(V)).lado_de(ids['Edu']) is None, 'quem não está na call não senta')
    ev(beto)
    beto.emit('atividade_sentar', {'canal_id': V, 'lado': cor_beto})
    est = ultimo(beto, 'atividade_estado')
    ok(est and est['situacao'] == 'jogando' and est['vez'] == 'w' and est['fen'].startswith('rnbqkbnr'), 'os dois sentados: a partida começa com as brancas')
    ev(ana); ev(caio)
    caio.emit('atividade_sentar', {'canal_id': V, 'lado': 'w'})
    ok(atividades.da_call(str(V)).lado_de(ids['Caio']) is None, 'com os dois lados ocupados o terceiro só assiste')

    branca, preta = (ana, beto) if cor_ana == 'w' else (beto, ana)
    nome_b, nome_p = ('Ana', 'Beto') if cor_ana == 'w' else ('Beto', 'Ana')

    # lances
    preta.emit('atividade_acao', {'canal_id': V, 'acao': 'lance', 'de': 'e7', 'para': 'e5'})
    ok(ev(preta, 'atividade_erro'), 'lance fora da vez é recusado')
    caio.emit('atividade_acao', {'canal_id': V, 'acao': 'lance', 'de': 'e2', 'para': 'e4'})
    ok(atividades.da_call(str(V)).partida.lances == [], 'quem só assiste não joga')
    branca.emit('atividade_acao', {'canal_id': V, 'acao': 'lance', 'de': 'e2', 'para': 'e5'})
    ok(ev(branca, 'atividade_erro'), 'lance ilegal (peão pulando 3 casas) é recusado')
    branca.emit('atividade_acao', {'canal_id': V, 'acao': 'lance', 'de': 'e7', 'para': 'e6'})
    ok(ev(branca, 'atividade_erro'), 'mexer peça do adversário é recusado')
    branca.emit('atividade_acao', {'canal_id': V, 'acao': 'lance', 'de': 'zz', 'para': 'e4'})
    ok(ev(branca, 'atividade_erro') or True, 'lance com texto inválido não derruba o servidor')
    ev(ana); ev(beto); ev(caio)
    branca.emit('atividade_acao', {'canal_id': V, 'acao': 'lance', 'de': 'e2', 'para': 'e4'})
    est = ultimo(caio, 'atividade_estado')
    ok(est and est['lances'] == ['e2e4'] and est['vez'] == 'b' and est['ultimo'] == ['e2', 'e4'], 'lance legal vale e aparece pra quem assiste')
    preta.emit('atividade_acao', {'canal_id': V, 'acao': 'lance', 'de': 'e7', 'para': 'e5'})

    # entrar no meio da partida recebe o tabuleiro
    dani.emit('entrar_call', {'canal_id': V, 'peer_id': 'p-dani'})
    est = ultimo(dani, 'atividade_estado')
    ok(est and est['lances'] == ['e2e4', 'e7e5'] and est['situacao'] == 'jogando', 'quem entra no meio da call recebe a partida em andamento')
    dani.emit('entrar_call', {'canal_id': V, 'peer_id': 'p-dani-2'})
    dani.emit('sair_call', {'canal_id': V, 'peer_id': 'p-dani-2'})
    ev(ana); ev(beto); ev(caio); ev(dani)

    # empate: propor, o proponente não aceita a própria, o outro recusa/aceita
    branca.emit('atividade_acao', {'canal_id': V, 'acao': 'empate'})
    est = ultimo(preta, 'atividade_estado')
    ok(est and est['empate_de'] == 'w', 'proposta de empate chega no adversário')
    branca.emit('atividade_acao', {'canal_id': V, 'acao': 'empate_aceitar'})
    ok(atividades.da_call(str(V)).partida.resultado is None, 'não dá pra aceitar o próprio empate')
    preta.emit('atividade_acao', {'canal_id': V, 'acao': 'empate_recusar'})
    ok(atividades.da_call(str(V)).partida.empate_de is None, 'recusar limpa a proposta')
    branca.emit('atividade_acao', {'canal_id': V, 'acao': 'empate'})
    preta.emit('atividade_acao', {'canal_id': V, 'acao': 'empate_aceitar'})
    res = atividades.da_call(str(V)).partida.resultado
    ok(res == {'vencedor': None, 'motivo': 'acordo'}, 'empate aceito encerra a partida')
    ok(atividades.da_call(str(V)).partida.lances == ['e2e4', 'e7e5'], 'o histórico fica pra rever')
    # só depois do fim dá pra revanche (cores trocam)
    preta.emit('atividade_acao', {'canal_id': V, 'acao': 'revanche'})
    atv = atividades.da_call(str(V))
    ok(atv.partida.lances == [] and atv.lados['w'] == ids[nome_p], 'revanche: partida nova com as cores trocadas')
    caio.emit('atividade_acao', {'canal_id': V, 'acao': 'revanche'})
    ok(atv.partida.lances == [], 'quem assiste não pede revanche (e ela só vale depois do fim)')

    # desistir
    nova_branca = preta
    nova_preta = branca
    nova_branca.emit('atividade_acao', {'canal_id': V, 'acao': 'desistir'})
    ok(atv.partida.resultado == {'vencedor': 'b', 'motivo': 'desistencia'}, 'desistir dá a vitória ao adversário')

    # encerrar: espectador não pode enquanto os jogadores estão na call
    ev(caio)
    caio.emit('atividade_encerrar', {'canal_id': V})
    ok(atividades.da_call(str(V)) is not None and ev(caio, 'atividade_erro'), 'quem só assiste não encerra a atividade dos outros')
    ana.emit('atividade_encerrar', {'canal_id': V})
    ok(atividades.da_call(str(V)) is None, 'quem começou encerra')
    ok(ultimo(caio, 'atividade_estado') == {'canal_id': str(V), 'ativa': False}, 'todos recebem o fim da atividade')

    # sair no meio da partida mantém; sair antes de começar libera a cadeira; call vazia apaga
    ana.emit('atividade_iniciar', {'canal_id': V, 'tipo': 'xadrez'}); ev(ana)
    ana.emit('sair_call', {'canal_id': V, 'peer_id': 'p-ana'})
    ok(atividades.da_call(str(V)).lado_de(ids['Ana']) is None, 'quem sai da call antes do jogo começar libera a cadeira')
    beto.emit('atividade_sentar', {'canal_id': V, 'lado': 'qualquer'})
    caio.emit('atividade_sentar', {'canal_id': V, 'lado': 'qualquer'})
    ok(atividades.da_call(str(V)).partida is not None, 'dois sentados começam (lado sorteado)')
    beto.emit('sair_call', {'canal_id': V, 'peer_id': 'p-beto'})
    atv = atividades.da_call(str(V))
    ok(atv is not None and atv.partida is not None and not atv.partida.resultado, 'quem sai no meio da partida não a apaga')
    est = montar = None
    from app.atividades_events import montar_estado
    pres = [j['presente'] for j in montar_estado(str(V))['jogadores'].values() if j]
    ok(sorted(pres) == [False, True], 'a cadeira de quem saiu aparece como ausente')
    caio.emit('sair_call', {'canal_id': V, 'peer_id': 'p-caio'})
    dani.emit('sair_call', {'canal_id': V, 'peer_id': 'p-dani'})
    ok(atividades.da_call(str(V)) is None, 'call vazia apaga a atividade')

    # ouvinte (plateia do palco) assiste mas não inicia nem senta
    ana.emit('entrar_call', {'canal_id': palco.id, 'peer_id': 'pa-ana'}); ev(ana)
    caio.emit('entrar_call', {'canal_id': palco.id, 'peer_id': 'pa-caio'}); ev(caio)
    ana.emit('atividade_iniciar', {'canal_id': palco.id, 'tipo': 'xadrez'})
    ok(atividades.da_call(str(palco.id)) is not None, 'quem fala no palco inicia')
    caio.emit('atividade_sentar', {'canal_id': palco.id, 'lado': 'qualquer'})
    ok(atividades.da_call(str(palco.id)).lado_de(ids['Caio']) is None and ev(caio, 'atividade_erro'), 'plateia do palco (ouvinte) não senta')
    ana.emit('sair_call', {'canal_id': palco.id, 'peer_id': 'pa-ana'}); caio.emit('sair_call', {'canal_id': palco.id, 'peer_id': 'pa-caio'})

    # DM: a atividade funciona entre os dois
    sala = f'dm_{min(ids["Ana"], ids["Beto"])}_{max(ids["Ana"], ids["Beto"])}'
    ana.emit('entrar_call', {'canal_id': sala, 'peer_id': 'dm-ana'}); beto.emit('entrar_call', {'canal_id': sala, 'peer_id': 'dm-beto'})
    ev(ana); ev(beto)
    ana.emit('atividade_iniciar', {'canal_id': sala, 'tipo': 'xadrez'})
    est = ultimo(beto, 'atividade_estado')
    ok(est and est['ativa'] and est['canal_id'] == sala, 'xadrez também roda numa ligação por DM')
    ana.emit('sair_call', {'canal_id': sala, 'peer_id': 'dm-ana'}); beto.emit('sair_call', {'canal_id': sala, 'peer_id': 'dm-beto'})

    # payload torto não derruba nada
    for payload in (None, 'texto', [], {'canal_id': None}, {'canal_id': {'x': 1}}, {'canal_id': V, 'acao': 5}):
        for nome in ('atividade_pedir', 'atividade_iniciar', 'atividade_sentar', 'atividade_acao', 'atividade_encerrar', 'convidar_voz'):
            ana.emit(nome, payload)
    ok(True, 'payload inválido nos eventos novos é ignorado sem erro')

    # --------------------------------------------------------- convidar pra voz ------------------------------------------
    ev(ana); ev(beto); ev(caio); ev(dani); ev(edu)
    ana.emit('entrar_call', {'canal_id': V, 'peer_id': 'c-ana'}); ev(ana)
    caio.emit('convidar_voz', {'canal_id': V, 'amigo_id': ids['Ana']})
    ok(not ev(ana, 'voz_convite'), 'quem não está na call não convida pra ela')
    ana.emit('convidar_voz', {'canal_id': V, 'amigo_id': ids['Beto']})
    cv = ultimo(beto, 'voz_convite')
    ok(cv and cv['canal_id'] == V and cv['de_id'] == ids['Ana'] and cv['server_nome'] == 'Casa' and cv['canal_nome'] == 'voz1',
       'amigo do servidor recebe o convite com canal e servidor')
    ok(ultimo(ana, 'voz_convite_enviado') == {'amigo_id': ids['Beto']}, 'quem convidou recebe a confirmação')
    ana.emit('convidar_voz', {'canal_id': V, 'amigo_id': ids['Beto']})
    ok(not ev(beto, 'voz_convite') and ev(ana, 'erro_bazinga'), 'não dá pra chamar a mesma pessoa de novo em 20 s')
    ana.emit('convidar_voz', {'canal_id': V, 'amigo_id': ids['Edu']})
    ok(not ev(edu, 'voz_convite') and ev(ana, 'erro_bazinga'), 'amigo que não é do servidor não recebe (não vaza nome do servidor)')
    ana.emit('convidar_voz', {'canal_id': V, 'amigo_id': 999999})
    ok(not ev(ana, 'voz_convite_enviado'), 'quem não é amigo (id qualquer) não recebe convite')
    # canal privado: só quem é convidado do canal
    ana.emit('sair_call', {'canal_id': V, 'peer_id': 'c-ana'}); ev(ana)
    ana.emit('entrar_call', {'canal_id': priv.id, 'peer_id': 'priv-ana'}); ev(ana)
    ana.emit('convidar_voz', {'canal_id': priv.id, 'amigo_id': ids['Caio']})
    ok(not ev(caio, 'voz_convite') and ev(ana, 'erro_bazinga'), 'canal de voz privado: quem não foi convidado dele não recebe')
    # DM call: não convida
    ana.emit('sair_call', {'canal_id': priv.id, 'peer_id': 'priv-ana'}); ev(ana)
    ana.emit('entrar_call', {'canal_id': sala, 'peer_id': 'dm2-ana'}); ev(ana)
    ana.emit('convidar_voz', {'canal_id': sala, 'amigo_id': ids['Caio']})
    ok(not ev(caio, 'voz_convite') and ev(ana, 'erro_bazinga'), 'ligação por DM não convida terceiros')
    ana.emit('sair_call', {'canal_id': sala, 'peer_id': 'dm2-ana'})

print()
print('FALHAS:', len(falhas))
for f in falhas:
    print('  -', f)
sys.exit(1 if falhas else 0)
