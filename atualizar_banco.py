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

            # 12b. Responder mensagem (canal e DM)
            add_column_se_nao_existir("message", "reply_to_id INTEGER")
            add_column_se_nao_existir("direct_message", "reply_to_id INTEGER")

            # 13. Amizades de verdade (tabela nova - o db.create_all() acima já
            # cria; isso aqui só avisa se faltar).
            try:
                db.session.execute(text("SELECT 1 FROM friendship LIMIT 1"))
                db.session.commit()
                print("✅ Tabela 'friendship' (pedidos de amizade) presente.")
            except Exception:
                db.session.rollback()
                print("⚠️ Tabela 'friendship' não encontrada - sistema de amigos não vai funcionar.")

            # 14. "Membro desde" de verdade no card de perfil - antes era um
            # texto fixo ("Set. 2026") igual pra todo mundo. Conta antiga
            # fica NULL (não dá pra saber a data real dela).
            add_column_se_nao_existir("person", "created_at TIMESTAMP")

            # 15. Battle Pass (nível/XP pessoal)
            add_column_se_nao_existir("person", "xp INTEGER DEFAULT 0")
            add_column_se_nao_existir("person", "xp_ganho_em TIMESTAMP")

            # 16. Modo Fantasma salvo no servidor + sequência diária do Battle Pass
            add_column_se_nao_existir("person", "ghost_mode BOOLEAN DEFAULT FALSE NOT NULL")
            # 25. Localização na conta (NULL = ligada; sem NOT NULL de propósito)
            add_column_se_nao_existir("person", "localizacao_ativa BOOLEAN")
            add_column_se_nao_existir("person", "localizacao_ip BOOLEAN")
            add_column_se_nao_existir("person", "streak_dias INTEGER DEFAULT 0 NOT NULL")
            add_column_se_nao_existir("person", "streak_em DATE")
            add_column_se_nao_existir("person", "tema VARCHAR(20) DEFAULT 'dark' NOT NULL")

            # 18. Cartão de perfil: faixa em imagem e pronomes
            add_column_se_nao_existir("person", "banner_url VARCHAR(255)")
            add_column_se_nao_existir("person", "pronomes VARCHAR(40)")

            # 19. Perfil completo: nome da conta (@), emoji de status, tema, estilo de
            # nome, placa e moldura
            add_column_se_nao_existir("person", "username VARCHAR(32)")
            add_column_se_nao_existir("person", "status_emoji VARCHAR(16)")
            add_column_se_nao_existir("person", "perfil_tema VARCHAR(300)")
            add_column_se_nao_existir("person", "nome_estilo VARCHAR(24)")
            add_column_se_nao_existir("person", "placa VARCHAR(24)")
            add_column_se_nao_existir("person", "moldura VARCHAR(24)")
            try:
                db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_person_username ON person (username)"))
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"\u2139\ufe0f Indice unico de username: {e}")

            # 20. "Pensando agora" (balão) separado do status. Quem já tinha um texto no
            # balão (antes era custom_status) mantém esse texto no balão: copia UMA vez,
            # só quando a coluna acabou de ser criada (senão reviveria balão apagado).
            try:
                db.session.execute(text("SELECT pensando FROM person LIMIT 1"))
                db.session.commit()
                print("\u2139\ufe0f Coluna 'pensando' ja existe - nada a copiar.")
            except Exception:
                db.session.rollback()
                add_column_se_nao_existir("person", "pensando VARCHAR(128)")
                try:
                    db.session.execute(text("UPDATE person SET pensando = custom_status WHERE custom_status IS NOT NULL AND custom_status <> ''"))
                    db.session.commit()
                    print("\u2705 Balao antigo copiado para 'pensando'.")
                except Exception as e:
                    db.session.rollback()
                    print(f"\u26a0\ufe0f Nao consegui copiar o balao antigo: {e}")

            # 21. Faixa em GIF com enquadramento, DMs com anexo/leitura, notas com ícone,
            # denúncias (tabela nova -> db.create_all) e itens ocultos por denúncia.
            add_column_se_nao_existir("person", "banner_ajuste VARCHAR(60)")
            add_column_se_nao_existir("direct_message", "attachment_url VARCHAR(500)")
            add_column_se_nao_existir("direct_message", "attachment_type VARCHAR(20)")
            add_column_se_nao_existir("direct_message", "attachment_name VARCHAR(255)")
            add_column_se_nao_existir("direct_message", "lida BOOLEAN")   # sem DEFAULT: o que já existe fica NULL e vira lido abaixo
            try:
                # DM só de anexo vem sem texto: a coluna deixa de ser obrigatória (Postgres).
                db.session.execute(text("ALTER TABLE direct_message ALTER COLUMN content DROP NOT NULL"))
                db.session.commit()
            except Exception:
                db.session.rollback()   # SQLite não tem esse comando - lá a coluna já é tolerante
            try:
                # Tudo que já existia antes dessa coluna é considerado lido (senão
                # todo mundo ganha um badge enorme de "não lidas" no primeiro login).
                db.session.execute(text("UPDATE direct_message SET lida = TRUE WHERE lida IS NULL"))
                db.session.commit()
            except Exception:
                db.session.rollback()
            add_column_se_nao_existir("geo_note", "icone VARCHAR(16)")
            add_column_se_nao_existir("geo_note", "oculta BOOLEAN DEFAULT FALSE")
            add_column_se_nao_existir("map_server", "oculta BOOLEAN DEFAULT FALSE")
            # 22. Conversa rápida (mensagem pra desconhecido) e silenciar contato (tabela nova -> create_all)
            add_column_se_nao_existir("friendship", "rapida BOOLEAN DEFAULT FALSE")
            add_column_se_nao_existir("friendship", "oculta_req BOOLEAN DEFAULT FALSE")
            add_column_se_nao_existir("friendship", "oculta_dest BOOLEAN DEFAULT FALSE")
            # 23. Notas antigas sem prazo (criadas antes da duração valer) ficavam eternas no mapa: apaga as
            # com mais de 1 dia. (O servidor também ignora essas notas na hora de mostrar.)
            try:
                from datetime import timedelta
                from app.models import br_now
                db.session.execute(text("DELETE FROM geo_note WHERE expires_at IS NULL AND timestamp < :corte"),
                                   {"corte": br_now() - timedelta(days=1)})
                db.session.commit()
                print("✅ Notas antigas sem prazo limpas.")
            except Exception as e:
                db.session.rollback()
                print(f"ℹ️ Limpeza de notas antigas: {e}")
            for tabela in ("denuncia", "notificacao"):
                try:
                    db.session.execute(text(f"SELECT 1 FROM {tabela} LIMIT 1"))
                    db.session.commit()
                    print(f"✅ Tabela '{tabela}' presente.")
                except Exception:
                    db.session.rollback()
                    print(f"⚠️ Tabela '{tabela}' não encontrada - o db.create_all() do boot cria.")

            # 24. Cosméticos: coluna dos slots extras (efeitos) + tabela `posse` (nova -> create_all) e a
            # concessão do laboratório (insígnias e itens dos temas Gogeta/Sasuke/Fusão) aos dois testers.
            # Idempotente: rodar de novo só dá o que faltar. Quem não for achado (por @) vira um aviso;
            # use `python conceder_item.py <@usuario> tudo` quando a conta existir.
            add_column_se_nao_existir("person", "equipados TEXT")
            add_column_se_nao_existir("server", "efeito VARCHAR(24)")
            try:
                from app.cosmeticos import conceder_laboratorio
                conceder_laboratorio(print)
            except Exception as e:
                db.session.rollback()
                print(f"⚠️ Não consegui conceder o laboratório: {e}")

            # 26. Insígnias: Beta pra todo mundo, BAZINGA pros membros do servidor Bazinga (define o id em config_app)
            # e Alpha Tester pra lista de nomes. Idempotente; confira os avisos no fim (nome repetido, servidor não achado).
            try:
                from app.cosmeticos import conceder_insignias_iniciais
                conceder_insignias_iniciais(print)
            except Exception as e:
                db.session.rollback()
                print(f"⚠️ Não consegui conceder as insígnias: {e}")

            print("\n🚀 Banco de Dados 100% atualizado e pronto!")
        except Exception as e:
            print("❌ Erro fatal ao atualizar o banco:", e)


if __name__ == "__main__":
    atualizar_banco()
