"""Rodada 39: texto formatado e menções especiais.

Servidor: @todos/@aqui/@cargo exigem a permissão "Mencionar todos e cargos" (sem ela o token vira texto e ninguém é chamado); @staff, @dono,
@amigos e @alguem qualquer um usa, com intervalo; só chama quem é MEMBRO e enxerga o canal (canal privado não vaza); @alguem vira uma menção comum
de quem foi sorteado; editar uma mensagem não chama ninguém; aviso em lote (uma gravação) pra muita gente. Cliente: a lógica do formatador roda no
Node (testes/texto_rico_logica.js), e o chat.html/CSS/JS prometem o que o formatador precisa."""
import os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['LIMITE_EVENTOS'] = '0'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio, cargos, mencoes
from app.models import Role, Person, Server, Channel, Message, Notificacao, ServerRole, MemberRole, Friendship

app = create_app()
falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

def ev(cli, nome=None):
    r = cli.get_received()
    return [m for m in r if nome is None or m['name'] == nome]

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
def ler(rel): return open(os.path.join(RAIZ, rel), encoding='utf-8').read()

with app.app_context():
    db.create_all()
    r = Role(name="MEMBROS", color="#fff"); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Dono', 'Mod', 'Ana', 'Beto', 'Caio', 'Duda', 'Fora'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); ids[n] = p.id

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s: s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl

    cl = {n: cliente(n) for n in ids}
    cl['Dono'].emit('criar_servidor_discord', {'nome': 'Casa'})
    srv_json = ev(cl['Dono'], 'servidor_discord_criado')[-1]['args'][0]; sid = srv_json['id']
    geral = [x for x in srv_json['channels'] if x['type'] == 'text'][0]['id']
    cl['Dono'].emit('criar_convite', {'server_id': sid}); cod = ev(cl['Dono'], 'convite_criado')[-1]['args'][0]['code']
    for n in ('Mod', 'Ana', 'Beto', 'Caio', 'Duda'):
        cl[n].emit('entrar_por_convite', {'code': cod}); ev(cl[n])
    srv = db.session.get(Server, sid)

    # cargos: "Mestres" (sem permissão especial, com a cor) e "Mods" (com a permissão de mencionar + gerenciar o servidor)
    cl['Dono'].emit('cargo_criar', {'server_id': sid, 'nome': 'Mestres', 'cor': '#e91e63', 'permissoes': []}); ev(cl['Dono'])
    cl['Dono'].emit('cargo_criar', {'server_id': sid, 'nome': 'Mods', 'cor': '#3498db', 'permissoes': ['mencionar_todos', 'gerenciar_servidor']}); ev(cl['Dono'])
    mestres = ServerRole.query.filter_by(server_id=sid, nome='Mestres').first(); mods = ServerRole.query.filter_by(server_id=sid, nome='Mods').first()
    ok(mestres is not None and mods is not None, 'cargos criados')
    for n, rid in (('Mod', mods.id), ('Ana', mestres.id), ('Beto', mestres.id)):
        cl['Dono'].emit('cargo_membro', {'server_id': sid, 'person_id': ids[n], 'cargo_id': rid, 'ativo': True}); ev(cl['Dono'])
    ok(MemberRole.query.filter_by(role_id=mestres.id).count() == 2 and MemberRole.query.filter_by(role_id=mods.id).count() == 1, 'cargos dados')
    cl['Dono'].emit('criar_canal', {'server_id': sid, 'nome': 'secreto', 'privado': True, 'membros': [ids['Ana']]}); ev(cl['Dono'])
    secreto = Channel.query.filter_by(name='secreto').first().id
    db.session.add(Friendship(requester_id=ids['Caio'], addressee_id=ids['Duda'], status='accepted')); db.session.commit()
    # Fora: não é do servidor
    for n in ids: cl[n].emit('entrar_canal', {'canal_id': geral});
    for n in ids: ev(cl[n])

    def falar(quem, texto, canal=None):
        mencoes._ultimo.clear()                       # os intervalos têm teste próprio mais abaixo
        cl[quem].emit('enviar_mensagem', {'canal_id': canal or geral, 'texto': texto})
        saida = {n: ev(cl[n]) for n in ids}
        m = Message.query.order_by(Message.id.desc()).first()
        return m, saida
    def avisos(saida, n):
        return [x for x in saida[n] if x['name'] == 'mencao_recebida']

    # ---------- @todos / @aqui / @cargo: precisam da permissão ----------
    m, s = falar('Ana', 'oi <@todos>')
    ok(m.text == 'oi @todos', 'sem a permissão, <@todos> vira texto e a mensagem sai mesmo assim')
    ok(not any(avisos(s, n) for n in ids), 'sem a permissão ninguém é chamado')
    ok(any(x['name'] == 'erro_bazinga' and 'permissão' in x['args'][0]['msg'] for x in s['Ana']), '...e quem escreveu recebe o motivo')
    m, s = falar('Ana', 'chamando <@&%d>' % mestres.id)
    ok(m.text == 'chamando @Mestres' and not any(avisos(s, n) for n in ids), 'cargo também precisa da permissão')

    m, s = falar('Mod', 'atenção <@todos>')
    ok(m.text == 'atenção <@todos>', 'com a permissão o token fica no texto')
    esperados = {'Dono', 'Ana', 'Beto', 'Caio', 'Duda'}
    chamados = {n for n in ids if avisos(s, n)}
    ok(chamados == esperados | {'Mod'} - {'Mod'}, f'@todos chama os membros que enxergam o canal (menos quem escreveu e quem é de fora): {sorted(chamados)}')
    ok('Fora' not in chamados, 'quem não é do servidor NUNCA é chamado')
    ok(avisos(s, 'Ana')[0]['args'][0]['motivo'] == 'todos' and 'chamou todo mundo' in Notificacao.query.filter_by(person_id=ids['Ana'], tipo='mencao').order_by(Notificacao.id.desc()).first().titulo,
       'o aviso diz que foi @todos (na hora e na caixa de entrada)')
    ok(Notificacao.query.filter_by(person_id=ids['Mod'], tipo='mencao').count() == 0, 'quem escreveu não se chama')
    ok(all(n.ref == f'{sid}:{geral}' for n in Notificacao.query.filter_by(tipo='mencao').all()), 'o aviso abre o canal certo (ref servidor:canal)')

    m, s = falar('Mod', 'olha <@&%d>' % mestres.id)
    ok({n for n in ids if avisos(s, n)} == {'Ana', 'Beto'}, '@cargo chama só quem tem o cargo')
    ok('chamou o cargo' in Notificacao.query.filter_by(person_id=ids['Ana'], tipo='mencao').order_by(Notificacao.id.desc()).first().titulo, 'aviso de cargo')
    m, s = falar('Mod', 'cargo de outro lugar <@&999999>')
    ok(m.text == 'cargo de outro lugar @cargo' and not any(avisos(s, n) for n in ids), 'cargo que não existe neste servidor vira texto')

    # online (o "aqui" só chama quem está conectado)
    from app import events
    events.usuarios_conectados[ids['Duda']] = 0; events.usuarios_conectados.pop(ids['Duda'], None)
    m, s = falar('Mod', 'quem está aí <@aqui>')
    online = {n for n in ids if avisos(s, n)}
    ok('Duda' not in online or events.esta_online(ids['Duda']), '@aqui só chama quem está online')
    ok({'Ana', 'Beto', 'Caio'} <= online and 'Fora' not in online, '@aqui chama os que estão conectados')

    # ---------- canal privado: só quem enxerga ----------
    for n in ids: cl[n].emit('entrar_canal', {'canal_id': secreto}); ev(cl[n])
    m, s = falar('Mod', 'segredo <@todos>', canal=secreto)
    ok({n for n in ids if avisos(s, n)} <= {'Ana', 'Dono'}, 'em canal privado @todos só chama quem enxerga o canal (sem vazar)')
    ok(not avisos(s, 'Caio') and not avisos(s, 'Beto'), 'membro sem acesso ao canal privado não é chamado')

    # ---------- @staff, @dono, @amigos, @alguem: qualquer um, com intervalo ----------
    m, s = falar('Ana', 'socorro <@staff>')
    ok(m.text == 'socorro <@staff>' and {n for n in ids if avisos(s, n)} == {'Dono', 'Mod'}, '@staff chama o dono e quem gerencia o servidor')
    m, s = falar('Ana', 'chefe <@dono>')
    ok({n for n in ids if avisos(s, n)} == {'Dono'}, '@dono chama o dono')
    m, s = falar('Caio', 'galera <@amigos>')
    ok({n for n in ids if avisos(s, n)} == {'Duda'}, '@amigos chama só os AMIGOS de quem escreveu que estão no servidor')
    m, s = falar('Beto', 'sorteando <@alguem>')
    sorteado = [n for n in ids if avisos(s, n)]
    ok(len(sorteado) == 1 and sorteado[0] != 'Beto' and sorteado[0] != 'Fora' and m.text == f'sorteando <@{ids[sorteado[0]]}>', f'@alguem sorteia UMA pessoa do servidor e vira menção comum: {sorteado}')
    ok(avisos(s, sorteado[0])[0]['args'][0]['motivo'] in ('alguem', 'pessoa'), '...e o sorteado recebe o aviso')

    # ---------- intervalo e limites ----------
    mencoes._ultimo.clear()
    cl['Mod'].emit('enviar_mensagem', {'canal_id': geral, 'texto': 'a <@todos>'}); ev(cl['Mod'])
    cl['Mod'].emit('enviar_mensagem', {'canal_id': geral, 'texto': 'b <@todos>'}); rr = ev(cl['Mod'])
    ult = Message.query.order_by(Message.id.desc()).first()
    ok(ult.text == 'b @todos' and any('Calma' in x['args'][0].get('msg', '') for x in rr if x['name'] == 'erro_bazinga'), 'segundo @todos seguido (cedo demais) vira texto e avisa "Calma"')
    mencoes._ultimo.clear()
    cl['Mod'].emit('enviar_mensagem', {'canal_id': geral, 'texto': '<@todos> <@aqui> <@staff> <@dono> <@amigos>'}); ev(cl['Mod'])
    ult = Message.query.order_by(Message.id.desc()).first()
    ok(ult.text.count('<@') == 3 and '@dono' in ult.text and '@amigos' in ult.text and '<@dono>' not in ult.text, 'no máximo 3 menções especiais por mensagem (o resto vira texto)')
    ok(ult.text.startswith('<@todos> <@aqui> <@staff>'), '...as primeiras valem')

    # ---------- editar não chama ninguém ----------
    mencoes._ultimo.clear()
    cl['Ana'].emit('enviar_mensagem', {'canal_id': geral, 'texto': 'normal'}); ev(cl['Ana'])
    base = Message.query.order_by(Message.id.desc()).first()
    cl['Ana'].emit('editar_mensagem', {'msg_id': base.id, 'texto': 'agora <@todos> e <@&%d>' % mestres.id}); ev(cl['Ana'])
    db.session.expire_all()
    ok(db.session.get(Message, base.id).text == 'agora @todos e @cargo', f'editar uma mensagem pra pôr @todos/@cargo só deixa texto (nunca chama, nunca dá pílula amarela): {db.session.get(Message, base.id).text!r}')
    ok(mencoes.sem_especiais_novos('oi <@todos>', 'oi <@todos> de novo') == 'oi <@todos> de novo', 'o token que já estava na mensagem continua ao editar')

    # ---------- texto sem token não custa nada ----------
    ok(not mencoes.tem_especial('oi <@12> tudo bem') and mencoes.tem_especial('<@todos>') and mencoes.tem_especial('<@&5>'), 'só os tokens especiais disparam o caminho novo')
    antes = len(mencoes._ultimo)
    mencoes.preparar(db.session.get(Person, ids['Ana']), srv, db.session.get(Channel, geral), 'texto normal', lambda p: True, lambda p, c: True)
    ok(len(mencoes._ultimo) == antes, 'texto normal não toca no servidor nem nos intervalos')
    ok(mencoes.RE_TOKEN.sub('x', '<@todos><@aqui><@&3><@staff><@dono><@amigos><@alguem>') == 'x' * 7, 'o formato dos tokens é o que o cliente gera')

    # ---------- permissão nova nas listas ----------
    ok(cargos.IDS_PERMISSAO[-1] == 'mencionar_todos' and cargos.BIT['mencionar_todos'] < (1 << 20), 'mencionar_todos é a permissão nova (no fim, sem encostar nos bits do canal)')
    ok(not (cargos.PERMS_MEMBRO_PADRAO & cargos.BIT['mencionar_todos']), 'membro comum NÃO nasce com ela (servidor antigo não vira bagunça)')

    # ---------- aviso em lote: muita gente = pouca consulta ----------
    import sqlalchemy
    consultas, detalhe = [], []
    @sqlalchemy.event.listens_for(db.engine, 'before_cursor_execute')
    def _conta(conn, cur, stmt, params, ctx, many): consultas.append(stmt.split()[0]); detalhe.append(stmt[:70])
    mencoes._ultimo.clear(); consultas.clear(); detalhe.clear()
    cl['Mod'].emit('enviar_mensagem', {'canal_id': geral, 'texto': 'lote <@todos>'}); ev(cl['Mod'])
    ins_notif = [d for d in detalhe if d.startswith('INSERT INTO notificacao')]
    n_destino = 5
    # (no SQLite cada linha vira um INSERT; no Postgres o SQLAlchemy junta num só. O que importa é não crescer com várias idas POR PESSOA.)
    ok(len(consultas) <= 16 + len(ins_notif), f'@todos pra {n_destino} pessoas custa {len(consultas)} instruções no total (sem consulta por destinatário)')
    ok(not [d for d in detalhe if d.startswith('SELECT') and 'FROM push_sub' in d], 'o push sai em segundo plano (nada de consulta de push dentro do envio da mensagem)')

# ---------- cliente ----------
chat = ler('app/templates/chat.html'); js = ler('app/static/js/texto_rico.js'); css = ler('app/static/css/texto_rico.css'); cj = ler('app/static/js/cargos.js')
ok('js/texto_rico.js' in chat and 'css/texto_rico.css' in chat, 'chat.html carrega o texto_rico')
ok('<div class="message-text">${htmlTexto(textoMostrado)}' in chat and '<p class="message-text">${htmlTexto' not in chat, 'o texto da mensagem é um <div> (bloco de código e lista não cabem num <p>)')
ok("p = document.createElement('div')" in chat, 'a edição também recria o texto como <div>')
ok('TextoRico.render(texto, ctxTexto())' in chat and 'TextoRico.sugestoes(' in chat and 'TextoRico.digitadoParaTokens(' in chat, 'chat.html usa o formatador, as sugestões do @ e a conversão de menções')
ok("'mencionar_todos'" in cj, 'cargos.js conhece a permissão nova')
ok('--link' in css and 'data-claro' in css, 'link com cor própria (legível no tema claro e no escuro)')
ok('.message .message-text { white-space: normal; }' in css, 'o texto deixa de ser pre-wrap (a quebra de linha vem do <br>)')
ok("sandbox" in js and 'youtube-nocookie.com' in js and 'preload="none"' in js, 'prévias: iframe em sandbox, YouTube sem cookie, áudio sem baixar antes do play')
ok('eval(' not in js and 'new Function' not in js and 'document.write' not in js, 'o formatador não usa eval nem document.write')
ok('(?<' not in js.replace('(?<![', '').replace('(?<!', ''), 'sem lookbehind no regex (iPhone mais velho quebraria o arquivo inteiro)')

# a lógica pura do formatador, no Node
saida = subprocess.run(['node', os.path.join(RAIZ, 'testes', 'texto_rico_logica.js')], capture_output=True, text=True, encoding='utf-8')
linhas = [l for l in saida.stdout.splitlines() if l.startswith('FALHA')]
ok(saida.returncode == 0 and not linhas, 'a lógica do formatador passa nos testes do Node (%d verificações)' % sum(1 for l in saida.stdout.splitlines() if l.startswith(('OK', 'FALHA'))))
for l in linhas: print('     ', l)

print('\n' + ('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S)'))
sys.exit(1 if falhas else 0)
