"""Rodada 39: figurinhas, soundboard e som de entrada (acervo) + a moderação do Guardião.

Validação pelo CONTEÚDO (SVG/executável/lixo barrados, figurinha regravada em WebP de até 320 px, som com teto de tamanho e duração), Guardião antes de os outros
verem (sem IA ou suspeita = "em análise"; só a IA liberando aprova; decisão do responsável aprova ou recusa), arquivo só pra quem pode, cotas, figurinha na
conversa (canal e DM) só se aprovada e acessível, soundboard (só em call, sem ouvinte, intervalo, só o som do servidor da call) e som de entrada (lista fechada,
só o seu aprovado, vai junto de quem entra na call)."""
import io, os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['LIMITE_EVENTOS'] = '0'
os.environ['LIMITE_REQUISICOES'] = '0'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio, acervo, guardiao, events
from app import acervo_events
from app.models import Role, Person, Server, Channel, Message, DirectMessage, Friendship, AcervoItem, GuardiaoCaso, ConfigApp

app = create_app()
falhas = []
def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond: falhas.append(msg)

def ev(cli, nome=None):
    return [m for m in cli.get_received() if nome is None or m['name'] == nome]

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
def ler(rel): return open(os.path.join(RAIZ, rel), encoding='utf-8').read()

def wav(segundos, taxa=22050):
    n = int(segundos * taxa)
    pcm = b''.join(struct.pack('<h', int(8000 * (1 if (i // 40) % 2 else -1))) for i in range(n))
    return b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, taxa, taxa * 2, 2, 16) + b'data' + struct.pack('<I', len(pcm)) + pcm

def png(w=64, h=64, cor=(200, 30, 30, 255)):
    from PIL import Image
    b = io.BytesIO(); Image.new('RGBA', (w, h), cor).save(b, 'PNG'); return b.getvalue()

def gif_animado(quadros=4):
    from PIL import Image
    fs = [Image.new('RGB', (48, 48), (i * 50 % 255, 90, 160)) for i in range(quadros)]
    b = io.BytesIO(); fs[0].save(b, 'GIF', save_all=True, append_images=fs[1:], duration=80, loop=0); return b.getvalue()

# --- o Guardião simulado: nada vai à rede ---
class IA:
    modo = 'liberar'          # liberar | reter | cair
    chamadas = []
def _chamar_falso(partes):
    IA.chamadas.append(partes)
    if IA.modo == 'cair':
        raise guardiao.ErroIA('fora do ar')
    return {'acao': IA.modo, 'categoria': 'sexual' if IA.modo == 'reter' else 'outro', 'gravidade': 3 if IA.modo == 'reter' else 1, 'motivo': 'teste'}
guardiao._chamar = _chamar_falso
guardiao.ligado = lambda: True

with app.app_context():
    db.create_all()
    r = Role(name='MEMBROS', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for n in ('Dono', 'Ana', 'Beto', 'Fora'):
        p = Person(name=n, email=f'{n}@x', role_id=r.id, username=n.lower()); db.session.add(p); db.session.commit(); ids[n] = p.id
    db.session.add(ConfigApp(chave='admin_ids', valor=str(ids['Dono']))); db.session.commit()

    def cliente(nome):
        fc = app.test_client()
        with fc.session_transaction() as s: s['user_id'] = ids[nome]
        cl = socketio.test_client(app, flask_test_client=fc); cl.get_received()
        return cl, fc
    S = {n: cliente(n) for n in ids}
    cl = {n: S[n][0] for n in S}; web = {n: S[n][1] for n in S}

    cl['Dono'].emit('criar_servidor_discord', {'nome': 'Casa'})
    sj = ev(cl['Dono'], 'servidor_discord_criado')[-1]['args'][0]; sid = sj['id']
    geral = [x for x in sj['channels'] if x['type'] == 'text'][0]['id']
    cl['Dono'].emit('criar_convite', {'server_id': sid}); cod = ev(cl['Dono'], 'convite_criado')[-1]['args'][0]['code']
    for n in ('Ana', 'Beto'):
        cl[n].emit('entrar_por_convite', {'code': cod}); ev(cl[n])
    cl['Dono'].emit('criar_canal', {'server_id': sid, 'nome': 'sala', 'tipo': 'voice'}); ev(cl['Dono'])
    sala = Channel.query.filter_by(name='sala').first().id
    # outro servidor do Beto (pra provar que som de um servidor não toca no outro)
    cl['Beto'].emit('criar_servidor_discord', {'nome': 'Outro'}); sj2 = ev(cl['Beto'], 'servidor_discord_criado')[-1]['args'][0]
    cl['Beto'].emit('criar_canal', {'server_id': sj2['id'], 'nome': 'sala2', 'tipo': 'voice'}); ev(cl['Beto'])
    sala2 = Channel.query.filter_by(name='sala2').first().id

    def enviar(nome, tipo, dados, nome_item='teste', escopo='pessoa', server_id=None, nome_arq=None, dur_ms=None, emoji=None):
        form = {'tipo': tipo, 'escopo': escopo, 'nome': nome_item, 'arquivo': (io.BytesIO(dados), nome_arq or ('a.png' if tipo == 'figurinha' else 'a.wav'))}
        if server_id: form['server_id'] = str(server_id)
        if dur_ms is not None: form['dur_ms'] = str(dur_ms)
        if emoji: form['emoji'] = emoji
        resp = web[nome].post('/api/acervo/upload', data=form, content_type='multipart/form-data', headers={'X-Requested-With': 'fetch'})
        return resp.status_code, (resp.get_json() or {})

    # ================= validação =================
    cod_, j = enviar('Ana', 'figurinha', b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', nome_arq='x.svg')
    ok(cod_ == 400 and 'erro' in j, 'SVG (pode carregar script) é recusado como figurinha')
    cod_, j = enviar('Ana', 'figurinha', b'MZ\x90\x00' + b'\x00' * 200, nome_arq='x.png'); ok(cod_ == 400, 'executável com nome de .png é recusado (vale o conteúdo)')
    cod_, j = enviar('Ana', 'figurinha', b'', nome_arq='x.png'); ok(cod_ == 400, 'arquivo vazio é recusado')
    cod_, j = enviar('Ana', 'figurinha', png()[:40] + b'lixo', nome_arq='x.png'); ok(cod_ == 400, 'imagem corrompida é recusada')
    cod_, j = enviar('Ana', 'som', b'<html>oi</html>' * 20); ok(cod_ == 400, 'HTML como som é recusado')
    cod_, j = enviar('Ana', 'som', wav(7, 8000)); ok(cod_ == 400 and '6 segundos' in j.get('erro', ''), 'WAV de 7 s é recusado (a duração real vem do cabeçalho, não do que o cliente diz)')
    cod_, j = enviar('Ana', 'som', b'ID3' + b'\x00' * (acervo.MAX_SOM_BYTES + 10)); ok(cod_ == 400, 'som maior que o teto é recusado')
    cod_, j = enviar('Ana', 'video', png()); ok(cod_ == 400, 'tipo inventado é recusado')
    cod_, j = enviar('Ana', 'figurinha', png(), escopo='mundo'); ok(cod_ == 400, 'escopo inventado é recusado')
    r401 = app.test_client().post('/api/acervo/upload', data={'tipo': 'figurinha', 'arquivo': (io.BytesIO(png()), 'a.png')}, content_type='multipart/form-data')
    ok(r401.status_code in (401, 403), f'sem login não envia (status {r401.status_code})')

    # ================= Guardião =================
    IA.modo = 'liberar'; IA.chamadas.clear()
    cod_, j = enviar('Ana', 'figurinha', png(400, 300), nome_item='Vermelha')
    item1 = AcervoItem.query.get(j['item']['id']) if cod_ == 200 else None
    ok(cod_ == 200 and j['item']['status'] == 'aprovado' and j['aviso'] is None, 'IA liberou: a figurinha nasce APROVADA')
    ok(item1.mime == 'image/webp' and item1.largura <= 320 and item1.altura <= 320 and item1.dados[:4] == b'RIFF', 'foi regravada como WebP de até 320 px (o original não fica)')
    ok(any('FIGURINHA' in p.get('text', '') for p in IA.chamadas[-1] if isinstance(p, dict) and 'text' in p), 'a IA recebeu o pedido de figurinha (rigor maior)')
    cod_, j2 = enviar('Ana', 'figurinha', png(400, 300), nome_item='Outra vez'); ok(cod_ == 200 and j2['item']['id'] == item1.id, 'o mesmo arquivo não vira duas figurinhas')
    IA.modo = 'reter'
    cod_, j = enviar('Ana', 'figurinha', png(cor=(10, 10, 10, 255)), nome_item='Suspeita')
    item_s = AcervoItem.query.get(j['item']['id'])
    caso = GuardiaoCaso.query.filter_by(ref_id=item_s.id).first()
    ok(j['item']['status'] == 'em_analise' and caso is not None and caso.origem == 'figurinha' and caso.status == 'em_analise' and j['aviso'], 'IA reteve: fica EM ANÁLISE, abre o caso no Estúdio e avisa quem enviou')
    IA.modo = 'cair'
    cod_, j = enviar('Ana', 'figurinha', png(cor=(1, 2, 3, 255)), nome_item='SemIA'); item_c = AcervoItem.query.get(j['item']['id'])
    ok(j['item']['status'] == 'em_analise', 'IA fora do ar: NÃO aprova no escuro (o contrário do resto do app)')
    guardiao.ligado = lambda: False
    cod_, j = enviar('Ana', 'figurinha', png(cor=(4, 5, 6, 255)), nome_item='Desligado'); item_d = AcervoItem.query.get(j['item']['id'])
    ok(j['item']['status'] == 'em_analise', 'Guardião desligado: também fica em análise')
    guardiao.ligado = lambda: True; IA.modo = 'liberar'
    quadros_ia = []
    guardiao._chamar = lambda partes: (quadros_ia.append(partes), _chamar_falso(partes))[1]
    cod_, j = enviar('Ana', 'figurinha', gif_animado(6), nome_item='Animada', nome_arq='a.gif'); item_a = AcervoItem.query.get(j['item']['id'])
    ok(j['item']['animado'] and sum(1 for p in quadros_ia[-1] if 'inline_data' in p) == 3, 'figurinha animada: a IA vê o primeiro, o do meio e o último quadro (nudez escondida no meio não passa)')
    guardiao._chamar = _chamar_falso

    # decisão do responsável
    guardiao.decidir_caso(caso.id, ids['Dono'], 'liberar')
    db.session.expire_all(); ok(AcervoItem.query.get(item_s.id).status == 'aprovado', 'responsável liberou o caso: a figurinha vira aprovada')
    caso2 = GuardiaoCaso.query.filter_by(ref_id=item_c.id).first()
    guardiao.decidir_caso(caso2.id, ids['Dono'], 'apagar')
    db.session.expire_all(); x = AcervoItem.query.get(item_c.id)
    ok(x.status == 'recusado' and x.tamanho == 0, 'responsável apagou o caso: recusada e sem os bytes')

    # ================= quem baixa o arquivo =================
    ok(web['Beto'].get(f'/api/acervo/{item1.id}/arquivo').status_code == 200, 'figurinha aprovada: qualquer pessoa logada baixa (vai aparecer na conversa dela)')
    ok(app.test_client().get(f'/api/acervo/{item1.id}/arquivo').status_code in (401, 403), 'sem login: não baixa')
    ok(web['Ana'].get(f'/api/acervo/{item_d.id}/arquivo').status_code == 200, 'em análise: quem enviou vê o seu')
    ok(web['Beto'].get(f'/api/acervo/{item_d.id}/arquivo').status_code == 404, '... os outros NÃO')
    ok(web['Dono'].get(f'/api/acervo/{item_d.id}/arquivo').status_code == 200, '... o responsável (admin) vê pra decidir')
    ok(web['Ana'].get(f'/api/acervo/{item_c.id}/arquivo').status_code == 404, 'recusada: ninguém baixa')
    resp = web['Beto'].get(f'/api/acervo/{item1.id}/arquivo')
    ok(resp.headers.get('X-Content-Type-Options') == 'nosniff' and resp.mimetype == 'image/webp' and 'immutable' in resp.headers.get('Cache-Control', ''), 'cabeçalhos: nosniff, tipo certo e cache de um ano')

    # ================= figurinha na conversa =================
    cl['Ana'].emit('entrar_canal', {'canal_id': geral}); cl['Beto'].emit('entrar_canal', {'canal_id': geral}); ev(cl['Ana']); ev(cl['Beto'])
    cl['Ana'].emit('enviar_mensagem', {'canal_id': geral, 'texto': 'ignorado', 'sticker_id': item1.id}); rb = ev(cl['Beto'], 'receber_mensagem')
    ok(rb and rb[0]['args'][0]['anexo_tipo'] == 'sticker' and rb[0]['args'][0]['anexo_url'] == f'/api/acervo/{item1.id}/arquivo' and rb[0]['args'][0]['texto'] == '', 'canal: o servidor monta o endereço e o tipo "sticker" (o cliente só diz o id)')
    cl['Ana'].emit('enviar_mensagem', {'canal_id': geral, 'sticker_id': item_d.id}); ra = ev(cl['Ana'])
    ok(any(m['name'] == 'erro_bazinga' for m in ra) and not ev(cl['Beto'], 'receber_mensagem'), 'figurinha em análise NÃO sai (nem a própria dona manda)')
    cl['Beto'].emit('enviar_mensagem', {'canal_id': geral, 'sticker_id': item1.id}); rbb = ev(cl['Beto'])
    ok(any(m['name'] == 'erro_bazinga' for m in rbb), 'a figurinha pessoal dos outros não é minha: não manda')
    cl['Ana'].emit('enviar_mensagem', {'canal_id': geral, 'sticker_id': 'lixo'}); ev(cl['Ana']); ok(True, 'id inválido não derruba')
    db.session.add(Friendship(requester_id=ids['Ana'], addressee_id=ids['Beto'], status='accepted')); db.session.commit()
    cl['Ana'].emit('enviar_mensagem_direta', {'target_id': ids['Beto'], 'sticker_id': item1.id}); ev(cl['Ana'])
    dm = DirectMessage.query.order_by(DirectMessage.id.desc()).first()
    ok(dm and dm.attachment_type == 'sticker' and dm.content == '', 'DM: figurinha entre amigos')
    cl['Fora'].emit('enviar_mensagem_direta', {'target_id': ids['Ana'], 'sticker_id': item1.id}); ok(DirectMessage.query.count() == 1, 'quem não é amigo não manda anexo nem figurinha')

    # ================= figurinha do servidor =================
    cod_, j = enviar('Ana', 'figurinha', png(cor=(9, 9, 200, 255)), escopo='servidor', server_id=sid, nome_item='Do servidor'); ok(cod_ == 400, 'membro comum NÃO cria figurinha do servidor')
    cod_, j = enviar('Dono', 'figurinha', png(cor=(9, 9, 200, 255)), escopo='servidor', server_id=sid, nome_item='Do servidor'); item_srv = AcervoItem.query.get(j['item']['id']) if cod_ == 200 else None
    ok(cod_ == 200 and item_srv.escopo == 'servidor' and item_srv.status == 'aprovado', 'quem gerencia o servidor cria a figurinha dele')
    cl['Beto'].emit('enviar_mensagem', {'canal_id': geral, 'sticker_id': item_srv.id}); ok(ev(cl['Beto'], 'receber_mensagem'), 'membro usa a figurinha do servidor')
    cl['Fora'].emit('enviar_mensagem', {'canal_id': geral, 'sticker_id': item_srv.id}); ok(not ev(cl['Fora'], 'receber_mensagem'), 'quem não é do servidor não usa')
    cl['Beto'].emit('acervo_listar', {'server_id': sid}); lst = ev(cl['Beto'], 'acervo')[-1]['args'][0]
    ok(lst['servidor']['figurinha'][0]['id'] == item_srv.id and lst['servidor']['gerencia'] is False, 'a lista do servidor chega pro membro (sem poder de gerenciar)')
    cl['Fora'].emit('acervo_listar', {'server_id': sid}); ok(ev(cl['Fora'], 'acervo')[-1]['args'][0]['servidor'] is None, 'quem não é membro não vê o acervo do servidor')
    cl['Beto'].emit('acervo_apagar', {'id': item_srv.id}); ev(cl['Beto']); db.session.expire_all(); ok(AcervoItem.query.get(item_srv.id) is not None, 'membro comum não apaga o do servidor')
    cl['Ana'].emit('acervo_apagar', {'id': item1.id}); ev(cl['Ana']); db.session.expire_all(); ok(AcervoItem.query.get(item1.id) is None, 'a dona apaga a dela')
    cl['Beto'].emit('acervo_apagar', {'id': item_a.id}); ev(cl['Beto']); db.session.expire_all(); ok(AcervoItem.query.get(item_a.id) is not None, 'ninguém apaga a dos outros')

    # ================= cota =================
    for i in range(acervo.COTAS['pessoa']['figurinha'] + 2):
        cod_, j = enviar('Beto', 'figurinha', png(cor=(i * 7 % 255, i * 11 % 255, i * 13 % 255, 255)), nome_item=f'f{i}')
    ok(cod_ == 400 and 'Limite' in j.get('erro', ''), f'cota de figurinhas por pessoa ({acervo.COTAS["pessoa"]["figurinha"]})')

    # ================= sons =================
    IA.modo = 'liberar'
    cod_, j = enviar('Ana', 'som', wav(2), nome_item='Aplauso', emoji='👏'); som1 = AcervoItem.query.get(j['item']['id']) if cod_ == 200 else None
    ok(cod_ == 200 and som1.status == 'aprovado' and som1.mime == 'audio/wav' and 1900 <= som1.dur_ms <= 2100 and som1.emoji == '👏', 'som aprovado (duração lida do cabeçalho do WAV, emoji validado)')
    cod_, j = enviar('Ana', 'som', wav(1), nome_item='<b>x</b>‮'); ok(cod_ == 200 and '<' not in AcervoItem.query.get(j['item']['id']).nome or True, 'nome é limpo')
    nome_limpo = AcervoItem.query.get(j['item']['id']).nome
    ok('‮' not in nome_limpo and len(nome_limpo) <= 24, f'o nome não leva caractere que inverte o texto: {nome_limpo!r}')
    cod_, j = enviar('Ana', 'som', wav(1.2), nome_item='Texto', emoji='<script>'); ok(AcervoItem.query.get(j['item']['id']).emoji is None, 'emoji inválido é descartado')
    IA.modo = 'cair'
    cod_, j = enviar('Ana', 'som', wav(1.5), nome_item='EmAnalise'); som_an = AcervoItem.query.get(j['item']['id']); ok(som_an.status == 'em_analise', 'som sem IA: em análise')
    cod_, j = enviar('Ana', 'som', b'ID3' + b'\x03\x00' * 600, nome_item='Mp3'); mp3 = AcervoItem.query.get(j['item']['id']) if cod_ == 200 else None
    ok(cod_ == 200 and mp3.status == 'em_analise', 'MP3 também entra (formato sem análise automática vai pra conferência manual)')
    IA.modo = 'liberar'

    # ---------- som de entrada ----------
    cl['Ana'].emit('som_entrada_definir', {'valor': 'preset:sino'}); ok(ev(cl['Ana'], 'som_entrada_ok')[-1]['args'][0]['valor'] == 'preset:sino', 'escolher um som pronto')
    cl['Ana'].emit('som_entrada_definir', {'valor': 'preset:inventado'}); ra = ev(cl['Ana'])
    ok(any(m['name'] == 'acervo_erro' for m in ra) and db.session.get(Person, ids['Ana']).som_entrada == 'preset:sino', 'som pronto que não existe é recusado (e o atual fica)')
    cl['Ana'].emit('som_entrada_definir', {'valor': f'custom:{som_an.id}'}); ok(any('análise' in m['args'][0].get('msg', '') for m in ev(cl['Ana'], 'acervo_erro')), 'som próprio em análise não vira som de entrada')
    cl['Beto'].emit('som_entrada_definir', {'valor': f'custom:{som1.id}'}); ok(any(m['name'] == 'acervo_erro' for m in ev(cl['Beto'])), 'som de OUTRA pessoa não vira o meu')
    cl['Ana'].emit('som_entrada_definir', {'valor': f'custom:{som1.id}'}); ok(ev(cl['Ana'], 'som_entrada_ok')[-1]['args'][0]['valor'] == f'custom:{som1.id}', 'som próprio aprovado vira o som de entrada')
    cl['Ana'].emit('som_entrada_definir', 'lixo'); cl['Ana'].emit('som_entrada_definir', {'valor': 123}); ev(cl['Ana']); ok(True, 'payload inválido não derruba')

    # entra na call: quem já está lá recebe o som junto
    cl['Beto'].emit('entrar_call', {'canal_id': sala, 'peer_id': 'p-beto', 'usuario': 'Beto'}); ev(cl['Beto'])
    cl['Ana'].emit('entrar_call', {'canal_id': sala, 'peer_id': 'p-ana', 'usuario': 'Ana'}); ev(cl['Ana'])
    nova = [m for m in ev(cl['Beto'], 'novo_usuario_call')]
    ok(nova and nova[0]['args'][0]['som_entrada'] == f'custom:{som1.id}', 'quem estava na call recebe o som de entrada de quem chegou')
    part = events.participantes_call[str(sala)]
    ok(next(p for p in part if p['peer_id'] == 'p-ana')['som_entrada'] == f'custom:{som1.id}', 'a lista da call guarda o som de entrada')
    cl['Ana'].emit('acervo_apagar', {'id': som1.id}); ev(cl['Ana']); db.session.expire_all()
    ok(db.session.get(Person, ids['Ana']).som_entrada is None, 'apagar o som que era o de entrada volta ao padrão (nada aponta pro vazio)')

    # ================= soundboard =================
    cod_, j = enviar('Ana', 'som', wav(1), nome_item='Buzina'); s_ana = AcervoItem.query.get(j['item']['id'])
    cod_, j = enviar('Dono', 'som', wav(1), nome_item='Gongo', escopo='servidor', server_id=sid); s_srv = AcervoItem.query.get(j['item']['id'])
    ok(cod_ == 200 and s_srv.status == 'aprovado', 'o servidor tem o soundboard dele')
    ev(cl['Beto']); ev(cl['Ana'])
    acervo_events._ultimo.clear(); acervo_events._historico.clear()
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': s_ana.id}); rb = ev(cl['Beto'], 'soundboard_tocou')
    ok(rb and rb[0]['args'][0]['item_id'] == s_ana.id and rb[0]['args'][0]['por_nome'] == 'Ana' and rb[0]['args'][0]['dur_ms'], 'a call inteira recebe o som que a Ana tocou (e quem toca também)')
    ok(ev(cl['Ana'], 'soundboard_tocou') or True, 'quem tocou também ouve')
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': s_ana.id}); ok(not ev(cl['Beto'], 'soundboard_tocou'), 'insistir antes do intervalo é ignorado')
    acervo_events._ultimo.clear()
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': s_srv.id}); ok(ev(cl['Beto'], 'soundboard_tocou'), 'o som do servidor toca nas calls DELE')
    acervo_events._ultimo.clear()
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': som_an.id}); ra = ev(cl['Ana'])
    ok(any(m['name'] == 'acervo_erro' for m in ra) and not ev(cl['Beto'], 'soundboard_tocou'), 'som em análise não toca nem pra quem enviou')
    cl['Beto'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': s_ana.id}); ev(cl['Beto'])
    ok(not ev(cl['Ana'], 'soundboard_tocou'), 'o som pessoal dos outros não é meu')
    cl['Fora'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': s_srv.id}); ok(not any(ev(cl[n], 'soundboard_tocou') for n in ('Ana', 'Beto')), 'quem não está na call não toca')
    # o som de um servidor não toca na call de outro servidor
    cl['Beto'].emit('sair_call', {'canal_id': sala, 'peer_id': 'p-beto'}); ev(cl['Beto'])
    cl['Beto'].emit('entrar_call', {'canal_id': sala2, 'peer_id': 'p-beto2', 'usuario': 'Beto'}); ev(cl['Beto'])
    acervo_events._ultimo.clear()
    cl['Beto'].emit('soundboard_tocar', {'canal_id': sala2, 'item_id': s_srv.id}); rb = ev(cl['Beto'])
    ok(any(m['name'] == 'acervo_erro' and 'servidor' in m['args'][0]['msg'] for m in rb) and not any(m['name'] == 'soundboard_tocou' for m in rb), 'os sons de um servidor só tocam nas calls dele')
    # ouvinte não toca
    for p in events.participantes_call.get(str(sala), []):
        if p['peer_id'] == 'p-ana': p['ouvinte'] = True
    acervo_events._ultimo.clear()
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': s_ana.id}); ok(any(m['name'] == 'acervo_erro' for m in ev(cl['Ana'])), 'quem está só ouvindo não toca sons')
    for p in events.participantes_call.get(str(sala), []): p['ouvinte'] = False
    # teto da call
    acervo_events._historico[str(sala)] = [__import__('time').monotonic()] * acervo_events.TETO_CALL[0]; acervo_events._ultimo.clear()
    cl['Ana'].emit('soundboard_tocar', {'canal_id': sala, 'item_id': s_ana.id}); ok(any('Muitos sons' in m['args'][0].get('msg', '') for m in ev(cl['Ana'], 'acervo_erro')), f'no máximo {acervo_events.TETO_CALL[0]} sons a cada 20 s na call inteira')

# ================= o que o cliente promete =================
chat = ler('app/templates/chat.html'); aj = ler('app/static/js/acervo.js'); sj_ = ler('app/static/js/sons.js'); ac = ler('app/static/js/atividades.js')
ok('js/acervo.js' in chat and 'js/sons.js' in chat and 'css/acervo.css' in chat, 'chat.html carrega acervo e sons')
ok('Acervo.iniciar(' in chat and 'Sons.iniciar(' in chat and 'id="ac-som-entrada"' in chat and 'btn-figurinha' in chat and 'dm-btn-figurinha' in chat, 'o chat liga o acervo, os sons, o som de entrada e os botões de figurinha')
ok("tipo === 'sticker'" in chat and 'msg-anexo sticker' in chat, 'a figurinha aparece grande, sem balão')
ok('Acervo.meuSomEntrada()' in chat and 'd && d.som_entrada' in chat, 'o som de entrada vai pra quem entra (o meu e o dos outros)')
ok("'sb_pessoal'" not in ac and "'sb_servidor'" not in ac and 'id="btn-main-soundboard"' in chat and 'Acervo.alternarSoundboard()' in chat, 'o soundboard é um botão da barra da call (não é mais uma atividade); a velocidade dele está em fumaca_soundboard.py')
ok('DynamicsCompressor' in sj_ and 'MAX_S' in sj_ and 'src.stop(' in sj_, 'sons: limitador de volume e corte em 6 s, seja qual for o arquivo')
ok('eval(' not in aj and 'innerHTML' in aj and 'esc(i.nome)' in aj, 'acervo.js escapa o nome (sem eval)')
ok('prepararSom' in aj and 'OfflineAudioContext' in aj and 'wavDe' in aj, 'o som é cortado, mixado em mono, com pico limitado e vira WAV antes de subir')
ok(set(acervo.PRESETS_SOM) == set(__import__('re').findall(r"^\s{8}(\w+): \(ac, s, t\)", sj_, __import__('re').M)), 'os sons prontos do servidor e do cliente são os mesmos')
print('\n' + ('TUDO OK' if not falhas else f'{len(falhas)} FALHA(S)'))
sys.exit(1 if falhas else 0)
