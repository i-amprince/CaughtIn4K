import re

from extensions import db
from models import User

GOOGLE_OAUTH_PASSWORD_PLACEHOLDER = "GOOGLE_OAUTH_ONLY"

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def is_valid_email(email: str | None) -> bool:
    return bool(_EMAIL_PATTERN.match(normalize_email(email)))


def get_user_by_email(email: str | None) -> User | None:
    normalized_email = normalize_email(email)
    if not normalized_email:
        return None
    return User.query.filter_by(username=normalized_email).first()


def upsert_google_user(email: str, role: str) -> tuple[User, bool]:
    normalized_email = normalize_email(email)
    existing_user = get_user_by_email(normalized_email)

    if existing_user:
        existing_user.role = role
        existing_user.password = GOOGLE_OAUTH_PASSWORD_PLACEHOLDER
        return existing_user, False

    user = User(
        username=normalized_email,
        password=GOOGLE_OAUTH_PASSWORD_PLACEHOLDER,
        role=role,
    )
    db.session.add(user)
    return user, True


def sync_bootstrap_admins(admin_emails: list[str]) -> None:
    has_admin_emails = False
    for admin_email in admin_emails:
        normalized_email = normalize_email(admin_email)
        if not normalized_email:
            continue
        has_admin_emails = True
        upsert_google_user(normalized_email, "System Administrator")

    if has_admin_emails:
        db.session.commit()
