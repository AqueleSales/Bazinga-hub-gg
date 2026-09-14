from app import create_app, db
from sqlalchemy import text

app = create_app()


def atualizar_banco():
    with app.app_context():
        try:
            print("Conectando ao banco Neon...")

            # 1. FAXINA: Removendo as tabelas plurais antigas (lixo do banco)
            db.session.execute(text("DROP TABLE IF EXISTS channels CASCADE"))
            db.session.execute(text("DROP TABLE IF EXISTS messages CASCADE"))
            db.session.execute(text("DROP TABLE IF EXISTS roles CASCADE"))

            # 2. Dropando as tabelas do mapa (caso tenham sobrado com estruturas velhas)
            db.session.execute(text("DROP TABLE IF EXISTS geo_note CASCADE"))
            db.session.execute(text("DROP TABLE IF EXISTS map_server CASCADE"))
            db.session.commit()
            print("✅ Faxina de tabelas antigas concluída.")

            # 3. Cria todas as tabelas novas (Server, server_members, GeoNote, MapServer)
            db.create_all()
            print("✅ Novas tabelas criadas com sucesso (Servidores e Mapa)!")

            # 4. Adiciona a coluna server_id na tabela channel existente (se não existir)
            # Como a tabela 'channel' já existe, o create_all() ignora ela. Injetamos na mão:
            try:
                db.session.execute(text("ALTER TABLE channel ADD COLUMN server_id INTEGER REFERENCES server(id)"))
                db.session.commit()
                print("✅ Coluna 'server_id' injetada na tabela 'channel'.")
            except Exception as e:
                db.session.rollback()
                print("ℹ️ A coluna 'server_id' já existe na tabela 'channel' (ou ocorreu um aviso ignorável).")

            print("\n🚀 Banco de Dados 100% atualizado e pronto!")
        except Exception as e:
            print("❌ Erro fatal ao atualizar o banco:", e)


if __name__ == "__main__":
    atualizar_banco()