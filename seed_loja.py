from app import create_app
from app.models import db, Product

app = create_app()

def semear_loja():
    with app.app_context():
        # Verifica se já tem produtos para não duplicar
        if Product.query.first():
            print("🛑 Os produtos já existem no banco! Não vou duplicar.")
            return

        produtos = [
            # ----- LOJA BAZINGA (OFICIAL) -----
            Product(
                name='Pacote Cyberpunk',
                description='Domine o radar com um pino de nave neon e uma borda de avatar hacker. Exclusivo por tempo limitado.',
                price_bzc=800,
                image_url='https://images.unsplash.com/photo-1542831371-29b0f74f9713?q=80&w=500&auto=format&fit=crop',
                is_official=True
            ),
            Product(
                name='Anel de Ouro Fundido',
                description='Cosmético Global de Borda de Avatar.',
                price_bzc=300,
                image_url='',
                is_official=True
            ),
            Product(
                name='Radar Hacker',
                description='Cosmético Global de Cores.',
                price_bzc=450,
                image_url='',
                is_official=True
            ),
            # ----- BAZAR DA COMUNIDADE (PIX) -----
            Product(
                name='Pack de Overlays "Neon Stream"',
                description='Pacote completo para OBS Studio, inclui tela de espera, chat box e webcam border animada em WebM.',
                price_pix=25.00,
                image_url='https://images.unsplash.com/photo-1550745165-9bc0b252726f?q=80&w=500&auto=format&fit=crop',
                is_official=False
            ),
            Product(
                name='Guia Definitivo: Python Flask',
                description='E-book com 50 páginas ensinando a criar um backend com Flask, Sockets e integração com PostgreSQL.',
                price_pix=19.90,
                image_url='https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?q=80&w=500&auto=format&fit=crop',
                is_official=False
            ),
            Product(
                name='Ilustração Customizada (Icon)',
                description='Faço seu ícone de perfil no estilo Anime/Lo-Fi. Prazo de entrega de 3 dias úteis. (3 Vagas restando)',
                price_pix=40.00,
                image_url='https://images.unsplash.com/photo-1611162617474-5b21e879e113?q=80&w=500&auto=format&fit=crop',
                is_official=False
            )
        ]

        db.session.bulk_save_objects(produtos)
        db.session.commit()
        print("✅ Loja reabastecida com sucesso! 6 produtos adicionados.")

if __name__ == '__main__':
    semear_loja()