from flask import Blueprint, current_app, render_template, session

from ..models import Person

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    user = Person.query.get(session.get("person_id")) if "person_id" in session else None
    return render_template(
        "index.html",
        user=user,
        bazinga_awards_url=current_app.config["BAZINGA_AWARDS_URL"],
    )