import os
from dotenv import load_dotenv

# Carrega as variáveis do .env ANTES do app ligar
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'bazinga-secret-key-123')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # O escudo anti-queda do Neon: faz o Flask testar a conexão antes de mandar a requisição.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }