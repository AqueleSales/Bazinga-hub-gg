import os
from dotenv import load_dotenv

# Carrega as variáveis do .env ANTES do app ligar
load_dotenv()

def clean_neon_url(url):
    """Limpa a URL para garantir a conexão direta perfeita"""
    if not url:
        return url
    # SQLAlchemy exige postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    # Removemos o ?sslmode da string para passá-lo de forma mais segura abaixo
    if "?" in url:
        url = url.split("?")[0]
    # Garante que NÃO estamos usando o pooler
    url = url.replace("-pooler", "")
    return url

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'bazinga-secret-key-123')
    SQLALCHEMY_DATABASE_URI = clean_neon_url(os.getenv('DATABASE_URL'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Escudo Máximo para Neon Serverless na AWS
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "connect_args": {
            "sslmode": "require",
            "keepalives": 1,           # Ativa o sinal de vida
            "keepalives_idle": 30,     # Manda sinal a cada 30 segundos
            "keepalives_interval": 10,
            "keepalives_count": 5
        }
    }