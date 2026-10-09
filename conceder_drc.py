"""Dá (ou tira) DRC de uma pessoa e registra no livro-razão (movimento_drc, motivo 'ajuste').

    python conceder_drc.py aquele.sales 40000             # dá 40.000 DRC (também vale 40k ou 40.000)
    python conceder_drc.py aquele.sales -500              # tira 500 (nunca deixa o saldo negativo)
    python conceder_drc.py aquele.sales 40000 --simular   # só mostra o que faria, sem gravar

A pessoa é achada pelo @username. A soma é um UPDATE atômico (nada de "ler, somar, gravar") e o movimento
guarda o saldo que ficou, então o extrato mostra "Ajuste" certinho. Roda contra o banco do .env (Neon):
confira o @ antes. É um atalho do DONO do app: DRC não é vendido nem transferido entre pessoas.
"""
import sys

from sqlalchemy import func, update

from app import create_app, db
from app.models import MovimentoDrc, Person
from app.utils import comitar_com_retry

LIMITE = 1_000_000          # trava de segurança contra zero a mais (mude aqui se precisar de mais)


def ajustar(pessoa_id, quantidade):
    """Soma `quantidade` ao saldo (pode ser negativa) e escreve o movimento. Devolve o saldo novo, ou None se tiraria além do saldo."""
    def preparar():
        saldo = func.coalesce(Person.bazinga_coins, 0)
        r = db.session.execute(update(Person).where(Person.id == pessoa_id, saldo + quantidade >= 0)
                               .values(bazinga_coins=saldo + quantidade))
        if r.rowcount != 1:
            return None
        pessoa = db.session.get(Person, pessoa_id)
        db.session.refresh(pessoa, ['bazinga_coins'])
        db.session.add(MovimentoDrc(person_id=pessoa_id, delta=quantidade, saldo_apos=pessoa.bazinga_coins, motivo='ajuste', ref='manual'))
        return pessoa.bazinga_coins

    return comitar_com_retry(preparar)


def main(args):
    simular = '--simular' in args
    args = [a for a in args if a != '--simular']
    if len(args) != 2:
        print(__doc__)
        return
    username = args[0].lstrip('@').lower()
    try:
        txt = args[1].lower().replace('.', '').replace('_', '')
        quantidade = int(txt[:-1]) * 1000 if txt.endswith('k') else int(txt)      # aceita "40000", "40.000" e "40k"
    except ValueError:
        print(f'"{args[1]}" não é um número inteiro.')
        return
    if quantidade == 0 or abs(quantidade) > LIMITE:
        print(f'A quantidade tem que ser diferente de 0 e ter no máximo {LIMITE:,} DRC (trava de segurança).'.replace(',', '.'))
        return

    app = create_app()
    with app.app_context():
        pessoa = Person.query.filter_by(username=username).first()
        if not pessoa:
            print(f'Não achei @{username}.')
            return
        antes = pessoa.bazinga_coins or 0
        if simular:
            print(f'[simulação] @{username} ({pessoa.name}): {antes} DRC -> {antes + quantidade} DRC. Nada foi gravado.')
            return
        novo = ajustar(pessoa.id, quantidade)
        if novo is None:
            print(f'@{username} tem só {antes} DRC: não dá pra tirar {-quantidade}. Nada foi gravado.')
            return
        print(f'@{username} ({pessoa.name}): {antes} DRC -> {novo} DRC ({quantidade:+d}). Registrado no extrato como "Ajuste".')


if __name__ == '__main__':
    main(sys.argv[1:])
