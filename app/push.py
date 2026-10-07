"""Notificações push (Web Push): avisos no celular/PC mesmo com o app fechado.

- As chaves VAPID (identificam o servidor perante o navegador) vêm das variáveis VAPID_PRIVATE_KEY/VAPID_PUBLIC_KEY ou,
  se não existirem, são geradas uma vez e guardadas na tabela `config_app`. Assim não depende de configurar nada no Render.
- Só se envia push pra quem NÃO está com o app aberto e visível (o aviso dentro do app já cobre esse caso).
- Inscrição que o navegador recusa (404/410) é apagada na hora.
"""
import base64
import json
import os
import threading

from flask import current_app

from . import socketio
from .models import db, PushSub, ConfigApp

_trava = threading.Lock()
_cache = {}


def _b64url(dados):
    return base64.urlsafe_b64encode(dados).rstrip(b'=').decode()


def _gerar_chaves():
    from py_vapid import Vapid
    from cryptography.hazmat.primitives import serialization
    v = Vapid()
    v.generate_keys()
    privada = v.private_pem().decode()
    publica = _b64url(v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    return privada, publica


def chaves_vapid():
    """(privada_pem, publica_b64url). Gera e guarda na primeira vez."""
    with _trava:
        if _cache.get('chaves'):
            return _cache['chaves']
        priv = (os.environ.get('VAPID_PRIVATE_KEY') or '').replace('\\n', '\n').strip()
        pub = (os.environ.get('VAPID_PUBLIC_KEY') or '').strip()
        if not (priv and pub):
            linhas = {c.chave: c.valor for c in ConfigApp.query.filter(ConfigApp.chave.in_(['vapid_privada', 'vapid_publica'])).all()}
            priv, pub = linhas.get('vapid_privada'), linhas.get('vapid_publica')
            if not (priv and pub):
                priv, pub = _gerar_chaves()
                for chave, valor in (('vapid_privada', priv), ('vapid_publica', pub)):
                    item = ConfigApp.query.get(chave) or ConfigApp(chave=chave)
                    item.valor = valor
                    db.session.add(item)
                db.session.commit()
        _cache['chaves'] = (priv, pub)
        return _cache['chaves']


def chave_publica():
    return chaves_vapid()[1]


def vapid_instancia():
    """Objeto Vapid pronto pro pywebpush (ele não aceita o PEM em texto direto)."""
    if 'vapid' not in _cache:
        from py_vapid import Vapid
        _cache['vapid'] = Vapid.from_pem(chaves_vapid()[0].encode())
    return _cache['vapid']


def assunto():
    return os.environ.get('VAPID_SUBJECT') or 'mailto:contato@panteao.app'


def _enviar_um(sub, texto, priv):
    from pywebpush import webpush, WebPushException
    try:
        webpush(subscription_info={'endpoint': sub['endpoint'], 'keys': {'p256dh': sub['p256dh'], 'auth': sub['auth']}},
                data=texto, vapid_private_key=priv, vapid_claims={'sub': assunto()}, ttl=3600, timeout=8)
        return True
    except WebPushException as e:
        codigo = getattr(getattr(e, 'response', None), 'status_code', None)
        print(f"[PUSH] falha {codigo}: {e}")
        return False if codigo in (404, 410) else True   # False = inscrição morta
    except Exception as e:
        print(f"[PUSH] erro: {type(e).__name__}: {e}")
        return True


def enviar_push(pessoa_id, titulo, corpo='', url='/chat', tag=None, extra=None):
    """Agenda o envio em segundo plano (nunca atrasa nem quebra quem chamou). Devolve True se havia alguma inscrição."""
    try:
        subs = [{'id': s.id, 'endpoint': s.endpoint, 'p256dh': s.p256dh, 'auth': s.auth}
                for s in PushSub.query.filter_by(person_id=pessoa_id).all()]
        if not subs:
            return False
        priv = vapid_instancia()
        texto = json.dumps({'titulo': (titulo or '')[:100], 'corpo': (corpo or '')[:160], 'url': url, 'tag': tag, **(extra or {})})
        app = current_app._get_current_object()

        def tarefa():
            mortas = []
            for sub in subs:
                if not _enviar_um(sub, texto, priv):
                    mortas.append(sub['id'])
            if mortas:
                with app.app_context():
                    try:
                        PushSub.query.filter(PushSub.id.in_(mortas)).delete(synchronize_session=False)
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        print(f"[PUSH] limpar mortas: {e}")

        socketio.start_background_task(tarefa)
        return True
    except Exception as e:
        db.session.rollback()
        print(f"[PUSH] enviar_push: {e}")
        return False
