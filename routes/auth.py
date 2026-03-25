import json
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from auth_helpers import get_user_by_email, normalize_email, upsert_google_user
from extensions import db

auth_bp = Blueprint("auth", __name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


@auth_bp.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))
    return redirect(url_for("auth.login"))


def _google_oauth_ready() -> bool:
    return bool(
        current_app.config.get("GOOGLE_CLIENT_ID")
        and current_app.config.get("GOOGLE_CLIENT_SECRET")
    )


def _google_redirect_uri() -> str:
    configured_uri = current_app.config.get("GOOGLE_OAUTH_REDIRECT_URI")
    if configured_uri:
        return configured_uri
    return url_for("auth.google_callback", _external=True)


def _is_verified_google_email(user_info: dict) -> bool:
    verified_value = user_info.get("email_verified")
    return verified_value is True or str(verified_value).lower() == "true"


def _exchange_google_code_for_tokens(code: str) -> dict:
    payload = urlencode(
        {
            "code": code,
            "client_id": current_app.config["GOOGLE_CLIENT_ID"],
            "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": _google_redirect_uri(),
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    request_obj = Request(
        GOOGLE_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request_obj, timeout=15) as response:
        return json.load(response)


def _fetch_google_user_info(access_token: str) -> dict:
    request_obj = Request(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urlopen(request_obj, timeout=15) as response:
        return json.load(response)


@auth_bp.route("/login", methods=["GET"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))

    return render_template(
        "login.html",
        google_oauth_ready=_google_oauth_ready(),
    )


@auth_bp.route("/auth/google")
def google_login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))

    if not _google_oauth_ready():
        flash("Google OAuth is not configured yet. Add the client ID and secret first.", "error")
        return redirect(url_for("auth.login"))

    state = secrets.token_urlsafe(32)
    session["google_oauth_state"] = state

    query_params = urlencode(
        {
            "client_id": current_app.config["GOOGLE_CLIENT_ID"],
            "redirect_uri": _google_redirect_uri(),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return redirect(f"{GOOGLE_AUTH_URL}?{query_params}")


@auth_bp.route("/auth/google/callback")
def google_callback():
    if request.args.get("error"):
        flash(f"Google sign-in was cancelled: {request.args['error']}", "error")
        return redirect(url_for("auth.login"))

    expected_state = session.pop("google_oauth_state", None)
    returned_state = request.args.get("state")
    if not expected_state or expected_state != returned_state:
        flash("Google sign-in could not be verified. Please try again.", "error")
        return redirect(url_for("auth.login"))

    code = request.args.get("code")
    if not code:
        flash("Google did not return an authorization code.", "error")
        return redirect(url_for("auth.login"))

    try:
        token_payload = _exchange_google_code_for_tokens(code)
        access_token = token_payload.get("access_token")
        if not access_token:
            flash("Google sign-in completed, but no access token was returned.", "error")
            return redirect(url_for("auth.login"))

        user_info = _fetch_google_user_info(access_token)
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        flash(f"Google OAuth request failed: {error_body or exc.reason}", "error")
        return redirect(url_for("auth.login"))
    except URLError as exc:
        flash(f"Could not reach Google OAuth services: {exc.reason}", "error")
        return redirect(url_for("auth.login"))
    except Exception as exc:
        flash(f"Google sign-in failed: {exc}", "error")
        return redirect(url_for("auth.login"))

    email = normalize_email(user_info.get("email"))
    if not email or not _is_verified_google_email(user_info):
        flash("Your Google account must have a verified email address.", "error")
        return redirect(url_for("auth.login"))

    user = get_user_by_email(email)
    if not user and email in current_app.config.get("GOOGLE_OAUTH_BOOTSTRAP_ADMIN_EMAILS", []):
        user, _ = upsert_google_user(email, "System Administrator")
        db.session.commit()

    if not user:
        flash("This Google account is not authorized yet. Ask an administrator to add your email.", "error")
        return redirect(url_for("auth.login"))

    login_user(user)
    flash(f"Signed in successfully as {email}.", "success")
    return redirect(url_for("dashboard.dashboard"))


@auth_bp.route("/logout")
@login_required
def logout():
    session.pop("google_oauth_state", None)
    logout_user()
    return redirect(url_for("auth.login"))
