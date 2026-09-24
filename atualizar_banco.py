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

            # 7. Compras da loja (tabela nova - o db.create_all() acima já cria,
            # isso aqui é só a rede de segurança se a tabela tiver vindo
            # incompleta de uma versão anterior)
            add_column_se_nao_existir("purchase", "price_paid_bzc INTEGER")

            # 8. Configurações de servidor e canal (editáveis depois da criação)
            add_column_se_nao_existir("server", "description TEXT")
            add_column_se_nao_existir("server", "banner_color VARCHAR(50)")
            add_column_se_nao_existir("channel", "topic VARCHAR(255)")
            add_column_se_nao_existir("channel", "is_private BOOLEAN DEFAULT FALSE")
            add_column_se_nao_existir("channel", "position INTEGER DEFAULT 0")

            # 9. Anexos e edição de mensagem
            add_column_se_nao_existir("message", "attachment_url VARCHAR(500)")
            add_column_se_nao_existir("message", "attachment_type VARCHAR(20)")
            add_column_se_nao_existir("message", "attachment_name VARCHAR(255)")
            add_column_se_nao_existir("message", "edited_at TIMESTAMP")

            # Mensagem só de anexo não tem texto, então a coluna precisa aceitar NULL
            try:
                db.session.execute(text("ALTER TABLE message ALTER COLUMN text DROP NOT NULL"))
                db.session.commit()
                print("✅ Coluna 'text' de 'message' liberada para aceitar NULL (mensagem só com anexo).")
            except Exception:
                db.session.rollback()
                print("ℹ️ 'text' já aceitava NULL (ou aviso ignorável).")

            # 10. Tabelas novas (reaction, invite, event) - o db.create_all() acima
            # já cria; isso aqui é a rede de segurança se vierem incompletas.
            add_column_se_nao_existir("invite", "uses INTEGER DEFAULT 0")
            add_column_se_nao_existir("event", "emoji VARCHAR(16)")
            add_column_se_nao_existir("event", "color VARCHAR(20)")

            # 11. Canal privado de verdade: tabela de quem tem acesso.
            # O db.create_all() acima cria; isso aqui só avisa se faltar.
            try:
                db.session.execute(text("SELECT 1 FROM channel_members LIMIT 1"))
                db.session.commit()
                print("✅ Tabela 'channel_members' (acesso a canal privado) presente.")
            except Exception:
                db.session.rollback()
                print("⚠️ Tabela 'channel_members' não encontrada - canal privado não vai funcionar.")

            # 12. Mensagens fixadas
            add_column_se_nao_existir("message", "is_pinned BOOLEAN DEFAULT FALSE")

            # 13. Amizades de verdade (tabela nova - o db.create_all() acima já
            # cria; isso aqui só avisa se faltar).
            try:
                db.session.execute(text("SELECT 1 FROM friendship LIMIT 1"))
                db.session.commit()
                print("✅ Tabela 'friendship' (pedidos de amizade) presente.")
            except Exception:
                db.session.rollback()
                print("⚠️ Tabela 'friendship' não encontrada - sistema de amigos não vai funcionar.")

            print("\n🚀 Banco de Dados 100% atualizado e pronto!")
        except Exception as e:
            print("❌ Erro fatal ao atualizar o banco:", e)


if __name__ == "__main__":
    atualizar_banco()
