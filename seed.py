from app import create_app
from app.models import db, Role, Channel

app = create_app()

with app.app_context():
    # Cria todas as tabelas lá no Neon
    db.create_all()

    # Verifica se os canais já existem para não duplicar
    if not Channel.query.first():
        print("Criando canais da Bazinga...")
        c1 = Channel(name="geral", channel_type="text")
        c2 = Channel(name="bazingawards", channel_type="text")
        c3 = Channel(name="torneio-ubc", channel_type="text")
        c4 = Channel(name="LOBBY", channel_type="voice")
        db.session.add_all([c1, c2, c3, c4])

    # Cria os cargos com as cores em Hexadecimal.
    # Checa cargo por cargo (e não `if not Role.query.first()`): se só um deles
    # existisse, o outro nunca era criado - e o login procura MEMBROS pelo nome.
    cargos = [
        ("MODERADORES", "#F1C40F"),  # Amarelo ouro
        ("MEMBROS", "#23a559"),      # Verde clássico
    ]
    for nome, cor in cargos:
        if not Role.query.filter_by(name=nome).first():
            print(f"Criando cargo {nome}...")
            db.session.add(Role(name=nome, color=cor))

    db.session.commit()
    print("Banco de dados Neon populado com sucesso!")