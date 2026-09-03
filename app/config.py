import os
from dotenv import load_dotenv
from sqlalchemy.pool import NullPool

load_dotenv()


def get_neon_url():
    """Formata a URL exatamente como a Neon exige para o plano Serverless"""
    url = os.getenv('DATABASE_URL', '')
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    # Garante que o -pooler está na URL (Recomendação oficial da Neon)
    if ".sa-east-1.aws.neon.tech" in url and "-pooler" not in url:
        url = url.replace(".sa-east-1.aws.neon.tech", "-pooler.sa-east-1.aws.neon.tech")

    if "sslmode=require" not in url:
        url += "&sslmode=require" if "?" in url else "?sslmode=require"
    return url


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'bazinga-secret-key-123')
    SQLALCHEMY_DATABASE_URI = get_neon_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Desativa o pool do Flask. O Neon assume o controle 100%.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": NullPool
    }