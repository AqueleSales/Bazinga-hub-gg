from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Person(db.Model):
    """MESMA tabela 'person' do bazingawards — aponta pro mesmo DATABASE_URL,
    então é o mesmo usuário/id em ambos os sites (login separado por enquanto,
    mas identidade compartilhada)."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    photo_url = db.Column(db.String(500))

    auth_provider = db.Column(db.String(20))
    provider_user_id = db.Column(db.String(120))
    email = db.Column(db.String(255))

    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_manual = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("auth_provider", "provider_user_id", name="uq_person_provider"),
    )

    def __repr__(self):
        return f"<Person {self.id} {self.name!r}>"