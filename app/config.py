import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-troque-isso-em-producao")

    # MESMO DATABASE_URL do bazingawards (Neon) -> mesma tabela "person"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///hub.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

    DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
    DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")

    ADMIN_EMAILS = [
        e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()
    ]
    ADMIN_DISCORD_IDS = [
        d.strip() for d in os.environ.get("ADMIN_DISCORD_IDS", "").split(",") if d.strip()
    ]

    # links pros outros sites do ecossistema (facilita trocar depois sem mexer no template)
    BAZINGA_AWARDS_URL = os.environ.get("BAZINGA_AWARDS_URL", "https://bazingawards.onrender.com")