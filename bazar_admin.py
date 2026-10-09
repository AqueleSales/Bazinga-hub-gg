"""Administração do Bazar (roda contra o banco do .env: confira antes de usar).

    python bazar_admin.py admin aquele.sales            # dá poder de moderar (a tela "Moderação" do Bazar)
    python bazar_admin.py admin aquele.sales --remover
    python bazar_admin.py porte aquele.sales grande     # loja parceira (grande), media ou micro
    python bazar_admin.py verificada aquele.sales       # dá o selo "verificada" à loja (--remover tira)
    python bazar_admin.py lista                         # admins e lojas

A pessoa é resolvida UMA vez (@username -> id): o poder é por id, então trocar o @ não passa o poder pra quem pegar o @ antigo.
"""
import sys

from app import create_app, db
from app import bazar
from app.models import Person, BazarLoja


def main(args):
    flags = [a for a in args if a.startswith('--')]
    args = [a for a in args if not a.startswith('--')]
    app = create_app()
    with app.app_context():
        if args[:1] == ['lista']:
            ids = bazar._ids_admin()
            print('Admins:', ', '.join(f'@{p.username} (id {p.id})' for p in Person.query.filter(Person.id.in_(ids))) or '(nenhum)')
            for l in BazarLoja.query.order_by(BazarLoja.id):
                print(f'loja #{l.id} "{l.nome}" dono id {l.owner_id} porte={l.porte} aberta={l.aberta} oculta={l.oculta} verificada={bool(l.verificada)}')
            return
        if len(args) >= 2 and args[0] in ('admin', 'porte', 'verificada'):
            pessoa = Person.query.filter_by(username=args[1].lstrip('@').lower()).first()
            if not pessoa:
                print(f'Não achei @{args[1]}.')
                return
            if args[0] == 'admin':
                bazar.definir_admin(pessoa.id, ativo='--remover' not in flags)
                print(f'@{pessoa.username} (id {pessoa.id}): admin = {pessoa.id in bazar._ids_admin()}')
                return
            if args[0] == 'verificada':
                loja = BazarLoja.query.filter_by(owner_id=pessoa.id).first()
                if not loja:
                    print(f'@{pessoa.username} ainda não abriu loja.')
                    return
                loja.verificada = '--remover' not in flags
                db.session.commit()
                print(f'Loja "{loja.nome}": verificada = {loja.verificada}.')
                return
            if len(args) == 3 and args[2] in ('micro', 'media', 'grande'):
                loja = BazarLoja.query.filter_by(owner_id=pessoa.id).first()
                if not loja:
                    print(f'@{pessoa.username} ainda não abriu loja.')
                    return
                loja.porte = args[2]
                db.session.commit()
                print(f'Loja "{loja.nome}" agora é {loja.porte}.')
                return
        print(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
