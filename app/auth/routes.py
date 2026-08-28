import requests
from flask import current_app, redirect, session, url_for

from ..models import Person, db
from . import auth_bp, oauth


@auth_bp.route("/login/<provider>")
def login(provider):
    if provider not in ("google", "discord"):
        return redirect(url_for("main.index"))

    client = oauth.create_client(provider)
    if client is None:
        return (
            f"Provedor '{provider}' ainda não configurado "
            f"(faltam as credenciais no .env — veja o README).",
            400,
        )

    redirect_uri = url_for("auth.callback", provider=provider, _external=True)
    return client.authorize_redirect(redirect_uri)


@auth_bp.route("/callback/<provider>")
def callback(provider):
    client = oauth.create_client(provider)
    if client is None:
        return redirect(url_for("main.index"))

    try:
        token = client.authorize_access_token()
    except Exception as e:
        print(f"Erro ao autorizar token (possível F5 ou CSRF expirado): {e}")
        return redirect(url_for("main.index"))

    if not token:
        print("Token não recebido.")
        return redirect(url_for("main.index"))

    if provider == "google":
        userinfo = token.get("userinfo") or {}
        provider_id = str(userinfo.get("sub", ""))
        email = userinfo.get("email")
        name = userinfo.get("name") or email or "Sem nome"
        photo = userinfo.get("picture")

    else:  # discord
        access_token = token.get("access_token")

        if not access_token:
            print(f"ERRO CRÍTICO - Token veio sem access_token. Payload: {token}")
            return redirect(url_for("main.index"))

        resp = requests.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )

        if not resp.ok:
            print(f"Erro na API do Discord: {resp.status_code} - {resp.text}")
            return redirect(url_for("main.index"))

        profile = resp.json()

        provider_id = str(profile.get("id", ""))
        email = profile.get("email")
        name = profile.get("global_name") or profile.get("username") or "Sem nome"
        avatar = profile.get("avatar")
        photo = (
            f"https://cdn.discordapp.com/avatars/{provider_id}/{avatar}.png"
            if avatar
            else "https://cdn.discordapp.com/embed/avatars/0.png"
        )

    if not provider_id:
        print("Provedor não retornou um ID válido.")
        return redirect(url_for("main.index"))

    person = Person.query.filter_by(auth_provider=provider, provider_user_id=provider_id).first()

    if person is None:
        person = Person(
            auth_provider=provider,
            provider_user_id=provider_id,
            name=name,
            photo_url=photo,
            email=email,
        )
        db.session.add(person)
    else:
        person.email = email or person.email

    is_admin_email = bool(email) and email.lower() in current_app.config.get("ADMIN_EMAILS", [])
    is_admin_discord = provider == "discord" and provider_id in current_app.config.get("ADMIN_DISCORD_IDS", [])

    if is_admin_email or is_admin_discord:
        person.is_admin = True

    db.session.commit()
    session["person_id"] = person.id
    return redirect(url_for("main.index"))


@auth_bp.route("/logout")
def logout():
    session.pop("person_id", None)
    return redirect(url_for("main.index"))