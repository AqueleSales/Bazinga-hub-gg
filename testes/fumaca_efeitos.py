"""Estúdio de efeitos: receita validada (só valores de listas fechadas), efeito vira item do catálogo, equipar com posse, apagar limpa tudo,
API do /admin (só admin) e o motor do navegador sem eval. Banco SQLite em memória."""
import os, sys, re, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import app.config as c
c.Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
c.Config.SQLALCHEMY_ENGINE_OPTIONS = {}
from app import create_app, db, socketio, efeitos
from app import cosmeticos as cos
from app.bazar import definir_admin
from app.models import Role, Person, Posse, EfeitoCustom

app = create_app()
falhas = []
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')


def ok(cond, msg):
    print(('OK   ' if cond else 'FALHA'), msg)
    if not cond:
        falhas.append(msg)


def levanta(fn):
    try:
        fn()
    except efeitos.ErroEfeito:
        db.session.rollback()
        return True
    return False


H = {'X-Requested-With': 'fetch'}
with app.app_context():
    db.create_all()
    r = Role(name='M', color='#fff'); db.session.add(r); db.session.commit()
    ids = {}
    for nome in ('adm', 'ana'):
        p = Person(name=nome, email=f'{nome}@x', role_id=r.id, username=nome, bazinga_coins=500); db.session.add(p); db.session.commit(); ids[nome] = p.id
    definir_admin(ids['adm'])

    def cli(nome):
        fc = app.test_client()
        with fc.session_transaction() as s:
            s['user_id'] = ids[nome]
        sc = socketio.test_client(app, flask_test_client=fc); sc.get_received()
        return fc, sc

    fadm, _ = cli('adm'); fana, sana = cli('ana')

    # ---------- receita ----------
    rec = efeitos.normalizar_receita('efeito_perfil', {'pausa': 99, 'camadas': [
        {'tipo': 'particulas', 'cor': 'javascript:alert(1)', 'cor2': '#ABCDEF', 'qtd': 9999, 'tam': -4, 'dur': 'abc', 'dir': 'diagonal', 'forma': '<script>', 'brilho': 500, 'extra': '<img onerror=x>'},
        {'tipo': 'camada_inventada', 'x': 1}, {'tipo': 'raios', 'qtd': 3}]})
    p0 = rec['camadas'][0]
    ok(len(rec['camadas']) == 2, 'Camada que não existe no esquema é descartada')
    ok(rec['pausa'] == 15, 'Pausa limitada ao máximo (15 s)')
    ok(p0['cor'] == '#f2c14e' and p0['cor2'] == '#abcdef', 'Cor inválida volta ao padrão; cor boa é normalizada (minúscula)')
    ok(p0['qtd'] == 40 and p0['tam'] == 2 and p0['dur'] == 6 and p0['brilho'] == 100, 'Números limitados (máximo, mínimo, texto vira padrão)')
    ok(p0['dir'] == 'cima' and p0['forma'] == 'circulo' and 'extra' not in p0, 'Opção fora da lista volta ao padrão; campo desconhecido some')
    ok(set(p0) == {'tipo', 'cor', 'cor2', 'qtd', 'tam', 'dur', 'dir', 'forma', 'brilho'}, 'A camada sai só com os parâmetros do esquema')
    ok(levanta(lambda: efeitos.normalizar_receita('efeito_perfil', {'camadas': []})), 'Sem camada: recusado')
    ok(levanta(lambda: efeitos.normalizar_receita('efeito_perfil', {'camadas': [{'tipo': 'anel'}]})), 'Camada de avatar num efeito de cartão: recusado')
    ok(levanta(lambda: efeitos.normalizar_receita('efeito_avatar', {'camadas': [{'tipo': 'raios'}]})), 'Camada de cartão num efeito de avatar: recusado')
    ok(levanta(lambda: efeitos.normalizar_receita('moldura', {'camadas': [{'tipo': 'brilho'}]})), 'Tipo de efeito inválido: recusado')
    ok(levanta(lambda: efeitos.normalizar_receita('efeito_perfil', 'texto')), 'Receita que não é objeto: recusada')
    ok(len(efeitos.normalizar_receita('efeito_perfil', {'camadas': [{'tipo': 'brilho'}] * 20})['camadas']) == efeitos.MAX_CAMADAS, 'No máximo 6 camadas')

    # ---------- API: só admin ----------
    corpo = {'id': 'poeira_azul', 'nome': 'Poeira Azul', 'tipo': 'efeito_perfil', 'raridade': 'epico', 'descricao': 'Teste',
             'receita': {'pausa': 2, 'camadas': [{'tipo': 'particulas', 'cor': '#7cc4ff'}, {'tipo': 'brilho', 'cor': '#7cc4ff'}]}}
    ok(fana.get('/admin/api/efeitos').status_code == 403 and fana.post('/admin/api/efeitos', json=corpo, headers=H).status_code == 403, 'Não-admin não vê nem cria efeito')
    ok(fadm.post('/admin/api/efeitos', json=corpo).status_code == 400, 'Sem o cabeçalho anti-forja: recusado')
    sana.get_received()
    rr = fadm.post('/admin/api/efeitos', json=corpo, headers=H)
    ok(rr.status_code == 200 and rr.get_json()['id'] == 'poeira_azul', 'Admin cria o efeito')
    ok('efeito_perfil:poeira_azul' in cos.CATALOGO and cos.CATALOGO['efeito_perfil:poeira_azul'].get('custom') and not cos.CATALOGO['efeito_perfil:poeira_azul'].get('preco'),
       'O efeito entra no catálogo (sem preço, marcado como custom)')
    ok(cos.item_exclusivo('efeito_perfil', 'poeira_azul'), 'item_exclusivo reconhece (é o que o equipar confere)')
    ok(EfeitoCustom.query.get('poeira_azul') is not None, 'Guardado na tabela efeito_custom')
    ev = [m for m in sana.get_received() if m['name'] == 'efeitos_custom']
    ok(ev and 'poeira_azul' in ev[0]['args'][0], 'Quem está conectado recebe o efeito novo na hora (efeitos_custom)')
    lista = fadm.get('/admin/api/efeitos').get_json()
    ok(lista['efeitos'][0]['id'] == 'poeira_azul' and set(lista['esquema']) == set(efeitos.ESQUEMA), 'Admin lista os efeitos e recebe o esquema das camadas')
    ok(any(i['id'] == 'efeito_perfil:poeira_azul' for i in fadm.get('/admin/api/catalogo').get_json()['itens']), 'O efeito aparece no seletor de recompensas do passe')
    ok(fadm.post('/admin/api/efeitos', json={**corpo, 'id': 'gogeta', 'nome': 'Copia'}, headers=H).status_code == 400, 'Id que já é de um item feito à mão no mesmo tipo (efeito_perfil:gogeta): recusado')
    ok(fadm.post('/admin/api/efeitos', json={**corpo, 'id': 'com espaco1'}, headers=H).status_code == 400, 'Id com espaço/número: recusado')
    ok(fadm.post('/admin/api/efeitos', json={**corpo, 'nome': 'x'}, headers=H).status_code == 400, 'Nome curto: recusado')
    ok(fadm.post('/admin/api/efeitos', json={**corpo, 'tipo': 'efeito_avatar'}, headers=H).status_code == 400, 'Mudar o tipo de um efeito criado: recusado')

    # editar mantém o id e atualiza o catálogo
    corpo2 = {**corpo, 'nome': 'Poeira Azul 2', 'receita': {'pausa': 0, 'camadas': [{'tipo': 'brilho', 'cor': '#ff0000'}]}}
    ok(fadm.post('/admin/api/efeitos', json=corpo2, headers=H).status_code == 200 and cos.CATALOGO['efeito_perfil:poeira_azul']['nome'] == 'Poeira Azul 2', 'Editar atualiza o nome no catálogo')
    ok(json.loads(EfeitoCustom.query.get('poeira_azul').receita)['camadas'][0]['cor'] == '#ff0000', 'Editar atualiza a receita')

    # ---------- dar, equipar (posse), apagar ----------
    sana.get_received()
    sana.emit('equipar_item', {'item_id': 'efeito_perfil:poeira_azul'})
    ok(db.session.get(Person, ids['ana']).equipados is None, 'Sem ter ganhado, não equipa (posse conferida no servidor)')
    ok(fadm.post('/admin/api/itens/conceder', json={'item_id': 'efeito_perfil:poeira_azul', 'person_id': ids['ana']}, headers=H).status_code == 200, 'Admin dá o item')
    ok(fadm.post('/admin/api/itens/conceder', json={'item_id': 'pacote:gojo', 'person_id': ids['ana']}, headers=H).status_code == 400, 'Dar pacote: recusado')
    ok(fadm.post('/admin/api/itens/conceder', json={'item_id': 'efeito_perfil:nao_existe', 'person_id': ids['ana']}, headers=H).status_code == 400, 'Dar item que não existe: recusado')
    sana.emit('equipar_item', {'item_id': 'efeito_perfil:poeira_azul'}); sana.get_received()
    db.session.expire_all()
    ok(json.loads(db.session.get(Person, ids['ana']).equipados).get('efeito_perfil') == 'poeira_azul', 'Com a posse, equipa')
    sana.emit('listar_inventario', {})
    inv = [m for m in sana.get_received() if m['name'] == 'inventario'][0]['args'][0]
    ok(any(i['id'] == 'efeito_perfil:poeira_azul' for i in inv['catalogo']) and inv['equipados'].get('efeito_perfil') == 'poeira_azul', 'Aparece no inventário e como equipado')
    cl_pf = fana.get('/chat')
    ok(b'poeira_azul' in cl_pf.data and b'Efeitos.registrar' in cl_pf.data, 'O /chat já nasce com o mapa de efeitos (o cartão desenha na primeira vez)')

    # avatar
    av = {'id': 'onda_azul', 'nome': 'Onda Azul', 'tipo': 'efeito_avatar', 'receita': {'camadas': [{'tipo': 'anel', 'cor': '#7cc4ff'}, {'tipo': 'orbita'}]}}
    ok(fadm.post('/admin/api/efeitos', json=av, headers=H).status_code == 200 and 'efeito_avatar:onda_azul' in cos.CATALOGO, 'Efeito de avatar (anel + órbita) criado')

    sana.get_received()
    ok(fadm.delete('/admin/api/efeitos/poeira_azul', headers=H).status_code == 200, 'Admin apaga o efeito')
    db.session.expire_all()
    ok('efeito_perfil:poeira_azul' not in cos.CATALOGO and EfeitoCustom.query.get('poeira_azul') is None, 'Sai do catálogo e da tabela')
    ok(not Posse.query.filter_by(item_id='efeito_perfil:poeira_azul').count(), 'Sai da posse de todo mundo')
    ok(db.session.get(Person, ids['ana']).equipados is None, 'Sai do que estava equipado (o JSON da pessoa não fica com id morto)')
    ok(fadm.delete('/admin/api/efeitos/poeira_azul', headers=H).status_code == 400, 'Apagar de novo: erro de regra')

    # sobrevive ao reinício: o boot recarrega do banco
    cos.CATALOGO.pop('efeito_avatar:onda_azul', None)
    efeitos.carregar()
    ok('efeito_avatar:onda_azul' in cos.CATALOGO, 'Depois de um reinício o efeito volta ao catálogo (carregar())')

    # ---------- front-end ----------
    js = open(os.path.join(RAIZ, 'static', 'js', 'efeitos.js'), encoding='utf-8').read()
    cosm = open(os.path.join(RAIZ, 'static', 'js', 'cosmeticos.js'), encoding='utf-8').read()
    html = open(os.path.join(RAIZ, 'templates', 'chat.html'), encoding='utf-8').read()
    ok(re.search(r'(?<!\w)eval\(|new Function|document\.write', js) is None, 'O motor não usa eval/new Function')
    ok(all(f'{t}(raiz' in js for t in efeitos.ESQUEMA), 'Toda camada do esquema tem o desenho no motor')
    ok('Efeitos.tem(id, \'efeito_perfil\')' in cosm and 'Efeitos.tem(id, \'efeito_avatar\')' in cosm, 'cosmeticos.js delega os efeitos do Estúdio ao motor')
    ok("socket.on('efeitos_custom'" in html and 'js/efeitos.js' in html, 'O chat escuta efeitos_custom e carrega o motor')
    ok('lim(' in js and 'idOk' in js, 'O motor limita os números e confere o id')

print()
print('FALHAS:', 'nenhuma' if not falhas else falhas)
sys.exit(1 if falhas else 0)
