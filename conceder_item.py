"""Concede ou retira itens do inventário de uma pessoa (cosméticos exclusivos do laboratório).

    python conceder_item.py aquele.sales tudo               # tudo do laboratório dessa pessoa
    python conceder_item.py filippo.chiarion moldura:sasuke  # um item
    python conceder_item.py filippo.chiarion tema:fusao      # todos os itens de um tema
    python conceder_item.py filippo.chiarion badge:coder --revogar
    python conceder_item.py --lista                          # mostra o catálogo

A identidade é resolvida UMA vez (@username -> id): depois disso a posse é por id, então
trocar o @ não muda nada. Roda contra o banco do .env (Neon) - confira antes de usar.
"""
import sys

from app import create_app, db
from app.cosmeticos import CATALOGO, LABORATORIO, conceder_item, revogar_item
from app.models import Person


def main(args):
    if '--lista' in args or not args:
        for item_id, d in CATALOGO.items():
            print(f"{item_id:28} {d['tema'] or '-':8} {d['nome']}")
        print(__doc__)
        return

    revogar = '--revogar' in args
    args = [a for a in args if not a.startswith('--')]
    if len(args) != 2:
        print('Uso: python conceder_item.py <@usuario> <item|tema:<tema>|tudo> [--revogar]')
        return
    username, alvo = args[0].lstrip('@').lower(), args[1]

    app = create_app()
    with app.app_context():
        pessoa = Person.query.filter_by(username=username).first()
        if not pessoa:
            print(f'Não achei @{username}.')
            return
        if alvo == 'tudo':
            itens = LABORATORIO.get(username) or list(CATALOGO)
        elif alvo.startswith('tema:'):
            itens = [i for i, d in CATALOGO.items() if d['tema'] == alvo[5:]]
        else:
            itens = [alvo]
        for item_id in itens:
            if item_id not in CATALOGO:
                print(f'Item desconhecido: {item_id}')
                continue
            if revogar:
                print(f'- {item_id}: {"retirado" if revogar_item(pessoa.id, item_id) else "não tinha"}')
            else:
                print(f'+ {item_id}: {"concedido" if conceder_item(pessoa.id, item_id, "manual") else "já tinha"}')
        db.session.commit()


if __name__ == '__main__':
    main(sys.argv[1:])
