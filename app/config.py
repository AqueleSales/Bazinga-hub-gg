import os
from dotenv import load_dotenv

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


def get_secret_key():
    """A SECRET_KEY assina os cookies de sessão. Se ela vazar (ou for um valor
    fixo no código), qualquer um forja a sessão de qualquer usuário - por isso
    em produção a app se recusa a subir sem a env var."""
    chave = os.getenv('SECRET_KEY')
    if chave:
        return chave
    if os.getenv('RENDER') or os.getenv('FLASK_ENV') == 'production':
        raise RuntimeError(
            "SECRET_KEY não definida! Configure a variável de ambiente no Render "
            "antes de subir - sem ela as sessões dos usuários são forjáveis."
        )
    # Só em desenvolvimento local.
    return 'bazinga-dev-only-nao-use-em-producao'


class Config:
    SECRET_KEY = get_secret_key()
    SQLALCHEMY_DATABASE_URI = get_neon_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload: 5 MB por arquivo. Sem isso dava pra mandar um arquivo gigante e
    # estourar o disco/memória do Render free.
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    # Cookie de sessão mais seguro (o cookie do Flask não precisa ser lido por JS)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = bool(os.getenv('RENDER'))

    # Era NullPool (conexão nova a cada query) - a ideia era deixar o Neon
    # controlar tudo e nunca reaproveitar uma conexão que ele já tivesse
    # fechado por trás (daí o com_retry() em app/utils.py). Só que isso fazia
    # TODA query pagar handshake TCP+TLS+Postgres do zero contra o pooler do
    # Neon - com página trocando de canal disparando dezenas de queries em
    # sequência, isso sozinho já era boa parte do "tudo demora".
    # `pool_pre_ping` resolve o mesmo problema que o NullPool evitava (testa
    # a conexão com um SELECT 1 antes de reusar e reconecta sozinho se ela
    # morreu) só que sem descartar uma conexão viva - `pool_recycle` também
    # descarta proativamente conexões mais velhas que isso, antes que o Neon
    # feche por inatividade. com_retry()/comitar_com_retry() continuam
    # necessários: cold start de verdade (Neon com o compute desligado)
    # ainda estoura na primeira query, pool nenhum evita isso.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": 5,
        "max_overflow": 10,
    }
    