from app import create_app, db
from sqlalchemy import text

app = create_app()


def add_column_se_nao_existir(tabela, coluna_sql):
    """Roda um ALTER TABLE ADD COLUMN e ignora o erro se a coluna já existir."""
    try:
        db.session.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna_sql}"))
        db.session.commit()
        print(f"✅ Coluna adicionada em '{tabela}': {coluna_sql}")
    except Exception:
        db.session.rollback()
        print(f"ℹ️ Coluna já existe em '{tabela}' (ou aviso ignorável): {coluna_sql}")


def atualizar_banco():
    with app.app_context():
        try:
            print("Conectando ao banco Neon...")

            # 1. Cria as tabelas que ainda não existem
            db.create_all()
            print("✅ Tabelas verificadas/criadas com sucesso!")

            # 2. Perfil do usuário (bio, status personalizado, cor do banner, status online)
            add_column_se_nao_existir("person", "bio TEXT")
            add_column_se_nao_existir("person", "custom_status VARCHAR(128)")
            add_column_se_nao_existir("person", "banner_color VARCHAR(50)")
            add_column_se_nao_existir("person", "status VARCHAR(20) DEFAULT 'online'")

            # 3. Ícone dos Servidores criados pelos usuários
            add_column_se_nao_existir("server", "icon_url VARCHAR(255)")

            # 4. Canal agora pode pertencer a um Servidor (ou ser um canal padrão global)
            add_column_se_nao_existir("channel", "server_id INTEGER REFERENCES server(id)")
            try:
                db.session.execute(text("ALTER TABLE channel ALTER COLUMN server_id DROP NOT NULL"))
                db.session.commit()
                print("✅ Coluna 'server_id' de 'channel' liberada para aceitar NULL.")
            except Exception:
                db.session.rollback()
                print("ℹ️ 'server_id' já aceitava NULL (ou aviso ignorável).")

            # 5. Notas HQ do mapa (geo_note) - tabela antiga, faltavam colunas novas
            add_column_se_nao_existir("geo_note", "duration_hours INTEGER DEFAULT 24")
            add_column_se_nao_existir("geo_note", "expires_at TIMESTAMP")

            # 6. Servidores plantados no mapa (map_server) - idem
            add_column_se_nao_existir("map_server", "max_tickets INTEGER")
            add_column_se_nao_existir("map_server", "duration_hours INTEGER")
            add_column_se_nao_existir("map_server", "expires_at TIMESTAMP")
            add_column_se_nao_existir("map_server", "server_id INTEGER REFERENCES server(id)")

            print("\n🚀 Banco de Dados 100% atualizado e pronto!")
        except Exception as e:
            print("❌ Erro fatal ao atualizar o banco:", e)


if __name__ == "__main__":
    atualizar_banco()
