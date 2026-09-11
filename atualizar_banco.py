from app import create_app, db
from sqlalchemy import text

app = create_app()


def recriar_mapa():
    with app.app_context():
        try:
            # Apaga as tabelas antigas (que não tinham cor e vagas)
            db.session.execute(text("DROP TABLE IF EXISTS geo_note CASCADE"))
            db.session.execute(text("DROP TABLE IF EXISTS map_server CASCADE"))
            db.session.commit()

            # Recria com as colunas novas
            db.create_all()
            print("✅ Tabelas do Mapa (Notas e Servidores) recriadas com sucesso!")
        except Exception as e:
            print("Erro:", e)


if __name__ == "__main__":
    recriar_mapa()