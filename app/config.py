import os
from dotenv import load_dict


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'bazinga-secret-key-123')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Isso aqui faz o Flask "testar" a conexão antes de mandar a requisição.
    # Se o Neon tiver derrubado a conexão, ele reconecta automaticamente.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }