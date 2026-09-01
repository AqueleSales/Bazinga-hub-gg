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

    # Cria os cargos com as cores em Hexadecimal
    if not Role.query.first():
        print("Criando cargos...")
        r1 = Role(name="MODERADORES", color="#F1C40F") # Amarelo ouro
        r2 = Role(name="MEMBROS", color="#23a559")     # Verde clássico
        db.session.add_all([r1, r2])

    db.session.commit()
    print("Banco de dados Neon populado com sucesso!")