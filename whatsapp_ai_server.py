# ====================================================================
# 👑 MOPOLEE CINEMA & EXCHANGE — CINEMATIC APP DASHBOARD
# Features: Branded login mockup, selectable themes, profile and settings screens
# Updated: October 5, 2026 WAT | Target Platform: Windows VS Code Server
# Bypasses all browser API link restrictions for 100% platform uptime!
# ====================================================================

import os
import re
import secrets
import sqlite3
import time
from html import escape
from contextlib import contextmanager
from uuid import uuid4
from flask import Flask, abort, flash, get_flashed_messages, jsonify, redirect, request, send_from_directory, session
from botocore.exceptions import BotoCoreError, ClientError
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

print("\nInitializing Mopolee Cinema & Exchange...")
load_dotenv()

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_VERIFY_SERVICE_SID = os.environ.get("TWILIO_VERIFY_SERVICE_SID", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
PRIVATE_PREVIEW = os.environ.get("PRIVATE_PREVIEW", "false").lower() == "true"
PREVIEW_INVITE_CODE = os.environ.get("PREVIEW_INVITE_CODE", "")
CATALOG_ADMIN_EMAIL = os.environ.get("CATALOG_ADMIN_EMAIL", "").strip().lower()
CLOUDFLARE_R2_ACCOUNT_ID = os.environ.get("CLOUDFLARE_R2_ACCOUNT_ID", "").strip()
CLOUDFLARE_R2_BUCKET = os.environ.get("CLOUDFLARE_R2_BUCKET", "").strip()
CLOUDFLARE_R2_ACCESS_KEY_ID = os.environ.get("CLOUDFLARE_R2_ACCESS_KEY_ID", "").strip()
CLOUDFLARE_R2_SECRET_ACCESS_KEY = os.environ.get("CLOUDFLARE_R2_SECRET_ACCESS_KEY", "").strip()
MAX_CINEMA_VIDEO_BYTES = 4_500_000_000
MAX_CINEMA_POSTER_BYTES = 10_000_000
CINEMA_LOCAL_FILMS = {
    "cinema-preview.mp4",
    "DEMO THE MAN NOBODY KNOWS.mp4",
}

APP_THEMES = [
    {"name": "Midnight Gold", "class": "theme-gold", "bg": "linear-gradient(135deg, #0b1020 0%, #1d2940 48%, #ffb703 100%)"},
    {"name": "Neon Blue", "class": "theme-blue", "bg": "linear-gradient(135deg, #011627 0%, #0d47a1 52%, #00b4d8 100%)"},
    {"name": "Rose Night", "class": "theme-rose", "bg": "linear-gradient(135deg, #1a0f1f 0%, #5d2a42 48%, #ff7b7b 100%)"},
    {"name": "Emerald Luxe", "class": "theme-emerald", "bg": "linear-gradient(135deg, #061b14 0%, #0b4f3b 48%, #2ad4ac 100%)"},
]

app = Flask(__name__, static_folder="static")
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
)
DATABASE_PATH = os.path.join(app.instance_path, "mopolee_users.sqlite3")
PROJECT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
os.makedirs(app.instance_path, exist_ok=True)


class DatabaseConnection:
    def __init__(self, connection, is_postgres):
        self.connection = connection
        self.is_postgres = is_postgres

    def execute(self, statement, parameters=()):
        if self.is_postgres:
            cursor = self.connection.cursor()
            try:
                cursor.execute(statement.replace("?", "%s"), parameters)
            except Exception as error:
                if getattr(error, "sqlstate", None) == "23505":
                    raise sqlite3.IntegrityError("A unique value already exists.") from error
                raise
            return cursor
        return self.connection.execute(statement, parameters)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


@contextmanager
def get_db_connection():
    is_postgres = bool(DATABASE_URL)
    if is_postgres:
        import psycopg
        from psycopg.rows import dict_row

        postgres_url = DATABASE_URL
        if postgres_url.startswith("postgres://"):
            postgres_url = "postgresql://" + postgres_url[len("postgres://"):]
        connection = psycopg.connect(postgres_url, row_factory=dict_row, connect_timeout=10)
    else:
        connection = sqlite3.connect(DATABASE_PATH)
        connection.row_factory = sqlite3.Row
    connection = DatabaseConnection(connection, is_postgres)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    user_id_column = "SERIAL PRIMARY KEY" if DATABASE_URL else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with get_db_connection() as connection:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS users (
                id {user_id_column},
                app_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL DEFAULT '',
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_limits (
                phone TEXT PRIMARY KEY,
                last_requested_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cinema_films (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                video_key TEXT NOT NULL,
                poster_key TEXT,
                uploaded_by INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def valid_csrf_token():
    submitted_token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    stored_token = session.get("csrf_token", "")
    return bool(stored_token) and secrets.compare_digest(submitted_token, stored_token)


def get_current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    with get_db_connection() as connection:
        user = connection.execute(
            "SELECT id, app_id, name, email, phone FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if user is None:
        session.clear()
    return user


def normalize_phone(phone):
    raw_phone = phone.strip()
    digits = "".join(character for character in raw_phone if character.isdigit())
    if raw_phone.startswith("00"):
        normalized = f"+{digits[2:]}"
    elif raw_phone.startswith("+"):
        normalized = f"+{digits}"
    else:
        return ""
    return normalized if re.fullmatch(r"\+[1-9]\d{7,14}", normalized) else ""


def twilio_verify_service():
    if (
        not TWILIO_ACCOUNT_SID.startswith("AC")
        or not TWILIO_AUTH_TOKEN
        or not TWILIO_VERIFY_SERVICE_SID.startswith("VA")
    ):
        raise RuntimeError("Twilio Verify credentials are not configured.")
    client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID)


def reserve_password_reset_send(phone, now):
    with get_db_connection() as connection:
        result = connection.execute(
            """
            INSERT INTO password_reset_limits (phone, last_requested_at)
            VALUES (?, ?)
            ON CONFLICT(phone) DO UPDATE SET last_requested_at = excluded.last_requested_at
            WHERE password_reset_limits.last_requested_at <= ?
            """,
            (phone, now, now - 60),
        )
        return result.rowcount == 1


if os.environ.get("REQUIRE_DATABASE_URL", "false").lower() == "true" and not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be configured for this deployment.")
initialize_database()

# --- 🖥️ 1. BASE ROOT STATUS ENDPOINT (THE LIVE INTERACTIVE MOVIE THEME UI) ---
@app.route("/", methods=["GET"])
def home():
    theme_cards = "\n".join(
        f'''<button class="theme-chip {theme['class']}" data-theme="{theme['name']}" title="{theme['name']}"><span>{theme['name']}</span></button>'''
        for theme in APP_THEMES
    )
    current_user = get_current_user()
    if current_user:
        with open(os.path.join(PROJECT_DIRECTORY, "index.html"), encoding="utf-8") as dashboard_file:
            dashboard_html = dashboard_file.read()
        logout_form = f"""
        <form class="dashboard-logout" action="/auth/logout" method="POST">
            <input type="hidden" name="csrf_token" value="{escape(csrf_token())}">
            <span>Signed in as {escape(current_user["name"])}</span>
            <button type="submit">Log out</button>
        </form>
        """
        dashboard_html = dashboard_html.replace("</aside>", f"{logout_form}</aside>", 1)
        dashboard_html = dashboard_html.replace(
            "Good evening, Ada",
            f"Welcome, {escape(current_user['name'])}",
            1,
        )
        profile_values = {
            "__MOPOLEE_PROFILE_NAME__": current_user["name"],
            "__MOPOLEE_PROFILE_EMAIL__": current_user["email"],
            "__MOPOLEE_PROFILE_PHONE__": current_user["phone"] or "Not added",
            "__MOPOLEE_PROFILE_APP_ID__": current_user["app_id"],
            "__MOPOLEE_PROFILE_INITIALS__": "".join(
                part[0].upper() for part in current_user["name"].split()[:2] if part
            ) or "M",
        }
        for placeholder, value in profile_values.items():
            dashboard_html = dashboard_html.replace(placeholder, escape(value))
        dashboard_html = dashboard_html.replace(
            '<meta name="csrf-token" content="" />',
            f'<meta name="csrf-token" content="{escape(csrf_token(), quote=True)}" />',
            1,
        )
        dashboard_html = dashboard_html.replace(
            '<div class="topbar overview-hero">',
            '<div class="demo-notice">Free films after sign-in. Dashboard figures are sample data; payments and rewards are not live.</div><div class="topbar overview-hero">',
            1,
        )
        return dashboard_html

    profile_name = escape(current_user["name"]) if current_user else ""
    profile_email = escape(current_user["email"]) if current_user else ""
    profile_phone = escape(current_user["phone"] or "Not added") if current_user else ""
    profile_app_id = escape(current_user["app_id"]) if current_user else ""
    reset_screen = request.args.get("reset") == "1"
    messages = "".join(
        f'<p class="form-message {escape(category)}">{escape(message)}</p>'
        for category, message in get_flashed_messages(with_categories=True)
    )
    token = escape(csrf_token())
    invite_field = (
        '<input type="text" name="invite_code" class="input-field" '
        'placeholder="Preview invite code" autocomplete="off" required>'
        if PRIVATE_PREVIEW
        else ""
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Discover Mopolee Cinema &amp; Exchange. Sign in to explore free films and your personal profile.">
    <meta name="theme-color" content="#07111f">
    <meta property="og:type" content="website">
    <meta property="og:title" content="Mopolee Cinema &amp; Exchange">
    <meta property="og:description" content="Discover Mopolee Cinema &amp; Exchange. Sign in to explore free films and your personal profile.">
    <meta property="og:url" content="{escape(request.url, quote=True)}">
    <meta property="og:image" content="{escape(request.url_root.rstrip('/'), quote=True)}/static/cinema-theme-background.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Mopolee Cinema &amp; Exchange">
    <meta name="twitter:description" content="Discover Mopolee Cinema &amp; Exchange. Sign in to explore free films and your personal profile.">
    <meta name="twitter:image" content="{escape(request.url_root.rstrip('/'), quote=True)}/static/cinema-theme-background.png">
    <title>Mopolee Cinema &amp; Exchange</title>
    <style>
        body, html {{ margin: 0; padding: 0; width: 100%; min-height: 100%; overflow-x: hidden; overflow-y: auto; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0c0f12; }}
        body {{ background: linear-gradient(135deg, #0b1020 0%, #111827 50%, #1d1b30 100%); }}
        .theme-backdrop {{ position: fixed; inset: 0; z-index: 0; overflow: hidden; background: linear-gradient(135deg, #0b1020 0%, #111827 42%, #1d1b30 100%); }}
        .theme-backdrop::before, .theme-backdrop::after {{ content: ''; position: absolute; width: 38vw; height: 38vw; border-radius: 50%; filter: blur(50px); opacity: 0.45; }}
        .theme-backdrop::before {{ background: rgba(255, 183, 3, 0.6); top: 8%; left: 5%; }}
        .theme-backdrop::after {{ background: rgba(0, 180, 216, 0.5); bottom: 10%; right: 10%; }}
        .theme-grid {{ position: absolute; inset: 0; display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 18px; align-items: center; justify-items: center; padding: 40px; opacity: 0.9; }}
        .theme-card {{ width: 100%; max-width: 180px; height: 120px; border-radius: 18px; border: 1px solid rgba(255,255,255,0.2); box-shadow: 0 12px 30px rgba(0,0,0,0.25); backdrop-filter: blur(10px); }}
        .theme-gold {{ background: linear-gradient(135deg, #0b1020 0%, #1d2940 48%, #ffb703 100%); }}
        .theme-blue {{ background: linear-gradient(135deg, #011627 0%, #0d47a1 52%, #00b4d8 100%); }}
        .theme-rose {{ background: linear-gradient(135deg, #1a0f1f 0%, #5d2a42 48%, #ff7b7b 100%); }}
        .theme-emerald {{ background: linear-gradient(135deg, #061b14 0%, #0b4f3b 48%, #2ad4ac 100%); }}
        .theme-background-poster {{ position: absolute; inset: 0; z-index: 0; width: 100%; height: 100%; object-fit: cover; opacity: 0.42; filter: brightness(0.65) saturate(1.08); }}
        .theme-poster-overlay {{ position: absolute; inset: 0; z-index: 1; background: linear-gradient(135deg, rgba(7, 12, 24, 0.64), rgba(5, 10, 20, 0.42) 52%, rgba(5, 10, 20, 0.72)); }}
        .theme-backdrop::before, .theme-backdrop::after {{ z-index: 1; }}
        .theme-grid {{ z-index: 2; }}
        .viewport-wrapper {{ display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; position: relative; z-index: 10; padding: 20px; box-sizing: border-box; }}
        .cockpit-card {{ position: relative; isolation: isolate; background: rgba(7, 15, 27, 0.84); border-radius: 24px; box-shadow: 0 26px 75px rgba(0,0,0,0.78), 0 0 0 1px rgba(255,255,255,0.12), 0 0 36px rgba(92,199,255,0.14); padding: 30px; width: 100%; max-width: 440px; border: 1px solid rgba(255, 183, 3, 0.78); text-align: center; box-sizing: border-box; backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px); }}
        .brand-title {{ margin: 0 0 10px; font-size: clamp(28px, 7vw, 40px); line-height: 1.08; text-transform: uppercase; letter-spacing: 1.5px; background: linear-gradient(90deg, #fff4cc 0%, #ffb703 48%, #8ecae6 100%); -webkit-background-clip: text; background-clip: text; color: transparent; text-shadow: 0 4px 24px rgba(255,183,3,0.2); }}
        .brand-title span {{ display: block; }}
        h1 {{ color: #ffb703; margin: 0 0 5px 0; font-size: 20px; text-transform: uppercase; letter-spacing: 1px; text-shadow: 0 2px 10px rgba(255,183,3,0.4); }}
        .sub-brand {{ color: #8ecae6; font-size: 12px; margin-bottom: 25px; font-weight: bold; letter-spacing: 2px; }}
        .avatar-frame {{ width: 95px; height: 95px; border-radius: 50%; border: 3px solid #ffb703; margin: 0 auto 20px auto; background: linear-gradient(45deg, #1f2833, #0077b6); display: flex; align-items: center; justify-content: center; font-size: 38px; box-shadow: 0 0 20px rgba(255, 183, 3, 0.4); overflow: hidden; }}
        .tab-container {{ display: flex; justify-content: space-around; margin-bottom: 20px; border-bottom: 1px solid #232d38; padding-bottom: 10px; }}
        .tab-btn {{ background: none; border: none; color: #d0d9e5; font-weight: bold; cursor: pointer; font-size: 13px; padding: 5px 10px; text-transform: uppercase; }}
        .tab-btn.active {{ color: #ffb703; border-bottom: 2px solid #ffb703; }}
        .auth-form {{ display: none; }}
        .auth-form.active {{ display: block; }}
        .input-field {{ background-color: rgba(3,8,16,0.96); border: 1px solid rgba(142,202,230,0.48); padding: 12px; border-radius: 8px; color: #fff; width: 100%; margin-bottom: 12px; box-sizing: border-box; font-size: 13px; padding-left: 15px; }}
        .input-field::placeholder {{ color: #b8c5d5; opacity: 1; }}
        .input-field:focus {{ border-color: #ffcf5c; outline: 2px solid rgba(255,207,92,0.26); outline-offset: 1px; box-shadow: 0 0 14px rgba(255,183,3,0.32); }}
        .btn-submit {{ background: linear-gradient(90deg, #ffb703, #fb8500); border: none; color: #0c0f12; font-weight: bold; cursor: pointer; width: 100%; padding: 14px; border-radius: 8px; text-transform: uppercase; font-size: 13px; margin-top: 5px; box-shadow: 0 4px 15px rgba(251, 133, 0, 0.4); }}
        .btn-submit:disabled {{ cursor: not-allowed; opacity: 0.55; box-shadow: none; }}
        .setup-notice {{ color: #ffe6a3; font-size: 12px; line-height: 1.5; margin: 0 0 14px; }}
        .form-message {{ padding: 10px; border-radius: 8px; font-size: 13px; }}
        .form-message.error {{ color: #ffd3d3; background: rgba(190, 35, 55, 0.2); }}
        .form-message.success {{ color: #c9ffe6; background: rgba(25, 145, 93, 0.2); }}
        .auth-links {{ color: #cbd5e1; font-size: 12px; margin-top: 14px; }}
        .auth-links button {{ border: 0; padding: 0; color: #ffb703; background: none; cursor: pointer; font: inherit; }}
        .reset-title {{ color: #ffb703; margin: 8px 0 16px; }}
        .metric-box {{ background-color: rgba(12,15,18,0.9); border-radius: 10px; padding: 15px; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.05); display: flex; justify-content: space-between; align-items: center; text-align: left; }}
        .metric-title {{ color: #a0aec0; font-size: 13px; text-transform: uppercase; }}
        .metric-value {{ color: #00b4d8; font-weight: bold; font-size: 18px; }}
        .btn-action {{ background: linear-gradient(90deg, #ffb703, #fb8500); border: none; border-radius: 8px; color: #0c0f12; display: block; font-weight: bold; padding: 14px; text-transform: uppercase; width: 100%; font-size: 13px; letter-spacing: 1px; text-decoration: none; margin-top: 10px; box-sizing: border-box; text-align: center; cursor: pointer; }}
        .user-profile-badge {{ border: 1px dashed rgba(255, 183, 3, 0.4); padding: 12px; border-radius: 8px; background-color: rgba(12,15,18,0.95); margin-bottom: 15px; text-align: left; font-size: 12px; }}
        .theme-selector {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 16px 0; justify-content: center; }}
        .theme-chip {{ border: 1px solid rgba(255,255,255,0.2); background: rgba(255,255,255,0.05); color: white; border-radius: 999px; padding: 8px 12px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.7px; cursor: pointer; }}
        .theme-chip span {{ display: block; }}
    </style>
</head>
<body>
    <div class="theme-backdrop" aria-hidden="true">
        <img class="theme-background-poster" src="/static/cinema-theme-background.png" alt="">
        <div class="theme-poster-overlay"></div>
        <div class="theme-grid">
            {theme_cards}
        </div>
    </div>
    <div class="viewport-wrapper">
        <div class="cockpit-card" id="loginScreen" style="display: {'none' if current_user else 'block'};">
            <div class="avatar-frame">👑</div>
            <h1 class="brand-title"><span>Mopolee Cinema</span><span>&amp; Exchange</span></h1>
            <div class="sub-brand">YOUR CINEMA. YOUR COMMUNITY.</div>
            <div class="tab-container" style="display: {'none' if reset_screen else 'flex'};">
                <button class="tab-btn active" onclick="switchTab('loginTab', this)">Sign In</button>
                <button class="tab-btn" onclick="switchTab('registerTab', this)">Create Account</button>
            </div>
            {messages}
            <div id="loginTab" class="auth-form active" style="display: {'none' if reset_screen else 'block'};">
                <form action="/auth/login" method="POST">
                    <input type="hidden" name="csrf_token" value="{token}">
                    <input type="email" name="email" class="input-field" placeholder="Email address" autocomplete="email" required>
                    <input type="password" name="password" class="input-field" placeholder="Password" autocomplete="current-password" required>
                    <button type="submit" class="btn-submit">Sign in</button>
                </form>
                <p class="auth-links"><button type="button" onclick="showPasswordReset()">Forgot password?</button></p>
            </div>
            <div id="registerTab" class="auth-form" style="display: none;">
                <form action="/auth/register" method="POST">
                    <input type="hidden" name="csrf_token" value="{token}">
                    <input type="text" name="name" class="input-field" placeholder="Your name" autocomplete="name" maxlength="80" required>
                    <input type="email" name="email" class="input-field" placeholder="Email address" autocomplete="email" maxlength="254" required>
                    <input type="tel" name="phone" class="input-field" placeholder="Phone number with country code (+...)" autocomplete="tel" maxlength="32" required>
                    {invite_field}
                    <input type="password" name="password" class="input-field" placeholder="Create a password (8+ characters)" autocomplete="new-password" minlength="8" required>
                    <input type="password" name="confirm_password" class="input-field" placeholder="Confirm password" autocomplete="new-password" minlength="8" required>
                    <button type="submit" class="btn-submit">Create Mopolee account</button>
                </form>
                <p class="auth-links"><button type="button" onclick="showPasswordReset()">Forgot password?</button></p>
            </div>
            <div id="passwordReset" style="display: {'block' if reset_screen else 'none'};">
                <h2 class="reset-title">Reset your password</h2>
                <p class="setup-notice">We’ll verify the phone number saved on your account using Twilio.</p>
                <form action="/auth/password-reset/request" method="POST">
                    <input type="hidden" name="csrf_token" value="{token}">
                    <input type="tel" name="phone" class="input-field" placeholder="Phone number with country code (+...)" autocomplete="tel" required>
                    <select name="channel" class="input-field" aria-label="Verification delivery method">
                        <option value="sms">Send code by SMS</option>
                        <option value="whatsapp">Send code by WhatsApp</option>
                    </select>
                    <button type="submit" class="btn-submit">Send verification code</button>
                </form>
                <form action="/auth/password-reset/confirm" method="POST">
                    <input type="hidden" name="csrf_token" value="{token}">
                    <input type="tel" name="phone" class="input-field" placeholder="Same phone number" autocomplete="tel" required>
                    <input type="text" name="code" class="input-field" placeholder="Verification code" inputmode="numeric" autocomplete="one-time-code" maxlength="10" required>
                    <input type="password" name="password" class="input-field" placeholder="New password (8+ characters)" autocomplete="new-password" minlength="8" required>
                    <input type="password" name="confirm_password" class="input-field" placeholder="Confirm new password" autocomplete="new-password" minlength="8" required>
                    <button type="submit" class="btn-submit">Verify code and reset password</button>
                </form>
                <p class="auth-links"><button type="button" onclick="hidePasswordReset()">Back to sign in</button></p>
            </div>
            <div class="theme-selector" aria-label="Theme selector">
                {theme_cards}
            </div>
        </div>
        <div class="cockpit-card" id="dashboardScreen" style="display: {'block' if current_user else 'none'};">
            <div class="avatar-frame">🤵‍♂️</div>
            <h1 class="brand-title"><span>Mopolee Cinema</span><span>&amp; Exchange</span></h1>
            <div class="sub-brand">WELCOME TO YOUR CINEMA</div>
            <div class="user-profile-badge">
                👤 PROFILE: {profile_name}<br>
                📧 EMAIL: {profile_email}<br>
                📱 PHONE: {profile_phone}<br>
                📦 APP ID: {profile_app_id}<br>
                📶 ACCOUNT: ACTIVE
            </div>
            <div>
                <div class="metric-box"><span class="metric-title">Membership</span><span class="metric-value" style="color:#ffb703;">MOPOLEE MEMBER</span></div>
            </div>
            <div class="theme-selector" aria-label="App themes">
                {theme_cards}
            </div>
            <button class="btn-action" style="background: linear-gradient(90deg, #ffb703, #fb8500); color: #0c0f12; margin-top:10px;" onclick="showSettings()">⚙️ SETTINGS</button>
            <a href="https://paystack.com" target="_blank" class="btn-action">💳 LIVE DEPOSIT CHECKOUT</a>
            <button class="btn-action" style="background: linear-gradient(90deg, #00b4d8, #0077b6); color: white; margin-top:10px;" onclick="alert('CINEMA ENGINE ONLINE!')">🍿 STREAM CINEMA VIDEOS</button>
        </div>
        <div class="cockpit-card" id="settingsScreen" style="display: none;">
            <div class="avatar-frame">⚙️</div>
            <h1>SETTINGS</h1>
            <div class="sub-brand">MOPOLEE CONTROL PANEL</div>
            <div class="user-profile-badge">
                👤 PROFILE: {profile_name}<br>
                📧 EMAIL: {profile_email}<br>
                📱 NUMBER: {profile_phone}<br>
                📦 APP ID: {profile_app_id}
            </div>
            <div class="theme-selector" aria-label="Settings themes">
                {theme_cards}
            </div>
            <button class="btn-action" style="background: linear-gradient(90deg, #00b4d8, #0077b6); color: white;" onclick="showDashboard()">⬅️ BACK TO DASHBOARD</button>
            <form action="/auth/logout" method="POST">
                <input type="hidden" name="csrf_token" value="{token}">
                <button class="btn-action" style="background: transparent; color: #e63946; border: 1px solid #e63946; margin-top: 20px; padding: 10px; font-size: 12px;">❌ LOGOUT</button>
            </form>
        </div>
    </div>
    <script>
        function switchTab(tabId, btn) {{
            document.querySelectorAll('.auth-form').forEach(form => form.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(form => form.style.display = form.id === tabId ? 'block' : 'none');
            document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            btn.classList.add('active');
        }}
        function showPasswordReset() {{
            document.querySelector('.tab-container').style.display = 'none';
            document.getElementById('loginTab').style.display = 'none';
            document.getElementById('registerTab').style.display = 'none';
            document.getElementById('passwordReset').style.display = 'block';
        }}
        function hidePasswordReset() {{
            document.getElementById('passwordReset').style.display = 'none';
            document.querySelector('.tab-container').style.display = 'flex';
            switchTab('loginTab', document.querySelector('.tab-btn'));
        }}
        function showSettings() {{
            document.getElementById('dashboardScreen').style.display = 'none';
            document.getElementById('settingsScreen').style.display = 'block';
        }}
        function showDashboard() {{
            document.getElementById('settingsScreen').style.display = 'none';
            document.getElementById('dashboardScreen').style.display = 'block';
        }}
        function applyTheme(themeName) {{
            document.querySelector('.theme-backdrop').style.background = 'linear-gradient(135deg, #0b1020 0%, #111827 50%, #1d1b30 100%)';
            const themes = {{
                'Midnight Gold': 'linear-gradient(135deg, #0b1020 0%, #1d2940 48%, #ffb703 100%)',
                'Neon Blue': 'linear-gradient(135deg, #011627 0%, #0d47a1 52%, #00b4d8 100%)',
                'Rose Night': 'linear-gradient(135deg, #1a0f1f 0%, #5d2a42 48%, #ff7b7b 100%)',
                'Emerald Luxe': 'linear-gradient(135deg, #061b14 0%, #0b4f3b 48%, #2ad4ac 100%)'
            }};
            if (themes[themeName]) {{
                document.querySelector('.theme-backdrop').style.background = themes[themeName];
            }}
        }}
        document.querySelectorAll('.theme-chip').forEach(button => {{
            button.addEventListener('click', () => applyTheme(button.dataset.theme));
        }});
    </script>
</body>
</html>
"""
    return html_content


@app.route("/styles.css", methods=["GET"])
def dashboard_styles():
    return send_from_directory(PROJECT_DIRECTORY, "styles.css")


@app.route("/script.js", methods=["GET"])
def dashboard_script():
    return send_from_directory(PROJECT_DIRECTORY, "script.js")


@app.route("/healthz", methods=["GET"])
def health_check():
    with get_db_connection() as connection:
        connection.execute("SELECT 1").fetchone()
    return "ok", 200, {"Content-Type": "text/plain"}


@app.route("/episodes/<path:filename>", methods=["GET"])
def protected_episode_file(filename):
    if not get_current_user():
        return redirect("/")
    episodes_directory = os.path.join(PROJECT_DIRECTORY, "episodes")
    return send_from_directory(episodes_directory, filename)


@app.route("/cinema-media/<path:filename>", methods=["GET", "HEAD"])
def protected_cinema_media(filename):
    if not get_current_user():
        return "Sign in to watch free films.", 401, {"Content-Type": "text/plain"}
    if filename not in CINEMA_LOCAL_FILMS:
        abort(404)
    cinema_media_directory = os.path.join(PROJECT_DIRECTORY, "cinema_media")
    return send_from_directory(
        cinema_media_directory,
        filename,
        conditional=True,
        max_age=0,
    )


def cinema_storage_ready():
    return all(
        (
            CLOUDFLARE_R2_ACCOUNT_ID,
            CLOUDFLARE_R2_BUCKET,
            CLOUDFLARE_R2_ACCESS_KEY_ID,
            CLOUDFLARE_R2_SECRET_ACCESS_KEY,
        )
    )


def cinema_storage_client():
    import boto3

    endpoint = f"https://{CLOUDFLARE_R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="auto",
        aws_access_key_id=CLOUDFLARE_R2_ACCESS_KEY_ID,
        aws_secret_access_key=CLOUDFLARE_R2_SECRET_ACCESS_KEY,
    )


def cinema_api_error(message, status):
    return jsonify(error=message), status


def cinema_current_user():
    user = get_current_user()
    if user is None:
        return None, cinema_api_error("Sign in to use the Cinema library.", 401)
    return user, None


def cinema_is_admin(user):
    return bool(CATALOG_ADMIN_EMAIL) and user["email"].strip().lower() == CATALOG_ADMIN_EMAIL


def cinema_admin_user():
    user, error = cinema_current_user()
    if error:
        return None, error
    if not cinema_is_admin(user):
        return None, cinema_api_error("Only the Cinema catalogue owner can manage films.", 403)
    return user, None


def cinema_json_admin_user():
    user, error = cinema_admin_user()
    if error:
        return None, error
    if not valid_csrf_token():
        return None, cinema_api_error("Your form session expired. Reload the page and try again.", 400)
    return user, None


def cinema_signed_url(client, operation, key, expires=3600, **parameters):
    return client.generate_presigned_url(
        operation,
        Params={"Bucket": CLOUDFLARE_R2_BUCKET, "Key": key, **parameters},
        ExpiresIn=expires,
    )


@app.route("/api/cinema/films", methods=["GET"])
def cinema_films():
    user, error = cinema_current_user()
    if error:
        return error

    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, description, video_key, poster_key, created_at
            FROM cinema_films
            WHERE status = 'published'
            ORDER BY created_at DESC
            LIMIT 100
            """
        ).fetchall()

    films = []
    if rows and not cinema_storage_ready():
        app.logger.error("Published Cinema films exist, but Cloudflare R2 is not configured.")
        return cinema_api_error("Cinema storage is not configured. Contact the app owner.", 503)

    try:
        client = cinema_storage_client() if rows else None
        for row in rows:
            poster_url = (
                cinema_signed_url(client, "get_object", row["poster_key"])
                if row["poster_key"]
                else None
            )
            films.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "description": row["description"],
                    "poster_url": poster_url,
                    "play_url": f"/api/cinema/films/{row['id']}/play",
                    "created_at": row["created_at"],
                }
            )
    except (BotoCoreError, ClientError):
        app.logger.exception("Could not create Cloudflare R2 links for Cinema films.")
        return cinema_api_error("The Cinema library could not load right now.", 502)

    return jsonify(
        films=films,
        is_admin=cinema_is_admin(user),
        storage_ready=cinema_storage_ready(),
    )


@app.route("/api/cinema/upload-intents", methods=["POST"])
def create_cinema_upload_intent():
    user, error = cinema_json_admin_user()
    if error:
        return error
    if not cinema_storage_ready():
        app.logger.error("Cinema upload is unavailable because Cloudflare R2 is not fully configured.")
        return cinema_api_error("Cloudflare R2 storage is not configured yet.", 503)

    data = request.get_json()
    if not isinstance(data, dict):
        return cinema_api_error("Upload details must be sent as a JSON object.", 400)
    title = data.get("title", "").strip() if isinstance(data.get("title"), str) else ""
    description = data.get("description", "").strip() if isinstance(data.get("description"), str) else ""
    video_name = data.get("video_name", "") if isinstance(data.get("video_name"), str) else ""
    video_type = data.get("video_type", "") if isinstance(data.get("video_type"), str) else ""
    poster_name = data.get("poster_name", "") if isinstance(data.get("poster_name"), str) else ""
    poster_type = data.get("poster_type", "") if isinstance(data.get("poster_type"), str) else ""
    video_size = data.get("video_size")
    poster_size = data.get("poster_size", 0)
    poster_media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    poster_extension = os.path.splitext(poster_name.lower())[1]

    if not title or len(title) > 120:
        return cinema_api_error("Enter a film title no longer than 120 characters.", 400)
    if len(description) > 1000:
        return cinema_api_error("Film descriptions must be 1,000 characters or fewer.", 400)
    if os.path.splitext(video_name.lower())[1] != ".mp4" or video_type != "video/mp4":
        return cinema_api_error("Choose an MP4 video file.", 400)
    if not isinstance(video_size, int) or isinstance(video_size, bool) or not 0 < video_size <= MAX_CINEMA_VIDEO_BYTES:
        return cinema_api_error("The MP4 must be smaller than 4.5 GB.", 400)
    if poster_name:
        if poster_type != poster_media_type.get(poster_extension):
            return cinema_api_error("Use a JPG, PNG, or WebP poster image.", 400)
        if not isinstance(poster_size, int) or isinstance(poster_size, bool) or not 0 < poster_size <= MAX_CINEMA_POSTER_BYTES:
            return cinema_api_error("The poster image must be smaller than 10 MB.", 400)

    film_id = uuid4().hex
    video_key = f"films/{film_id}/movie.mp4"
    poster_key = f"films/{film_id}/poster{poster_extension}" if poster_name else None
    try:
        client = cinema_storage_client()
        video_url = cinema_signed_url(
            client,
            "put_object",
            video_key,
            expires=900,
            ContentType="video/mp4",
        )
        poster_url = (
            cinema_signed_url(
                client,
                "put_object",
                poster_key,
                expires=900,
                ContentType=poster_type,
            )
            if poster_key
            else None
        )
        with get_db_connection() as connection:
            connection.execute(
                """
                INSERT INTO cinema_films
                    (id, title, description, video_key, poster_key, uploaded_by, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """,
                (film_id, title, description, video_key, poster_key, user["id"]),
            )
    except (BotoCoreError, ClientError):
        app.logger.exception("Could not create signed Cloudflare R2 upload links.")
        return cinema_api_error("Could not prepare this film upload. Try again later.", 502)

    return jsonify(
        film_id=film_id,
        video_upload_url=video_url,
        poster_upload_url=poster_url,
        poster_content_type=poster_type or None,
    ), 201


@app.route("/api/cinema/films/<film_id>/publish", methods=["POST"])
def publish_cinema_film(film_id):
    user, error = cinema_json_admin_user()
    if error:
        return error
    if not cinema_storage_ready():
        app.logger.error("Cinema publishing is unavailable because Cloudflare R2 is not fully configured.")
        return cinema_api_error("Cloudflare R2 storage is not configured yet.", 503)

    with get_db_connection() as connection:
        film = connection.execute(
            """
            SELECT id, video_key, poster_key
            FROM cinema_films
            WHERE id = ? AND uploaded_by = ? AND status = 'pending'
            """,
            (film_id, user["id"]),
        ).fetchone()
        if film is None:
            return cinema_api_error("This pending upload was not found.", 404)

    try:
        client = cinema_storage_client()
        video_metadata = client.head_object(Bucket=CLOUDFLARE_R2_BUCKET, Key=film["video_key"])
        video_length = video_metadata.get("ContentLength", 0)
        if not 0 < video_length <= MAX_CINEMA_VIDEO_BYTES or video_metadata.get("ContentType") != "video/mp4":
            return cinema_api_error("The uploaded MP4 is missing or failed its file checks.", 400)
        if film["poster_key"]:
            poster_metadata = client.head_object(Bucket=CLOUDFLARE_R2_BUCKET, Key=film["poster_key"])
            if (
                not 0 < poster_metadata.get("ContentLength", 0) <= MAX_CINEMA_POSTER_BYTES
                or poster_metadata.get("ContentType") not in {"image/jpeg", "image/png", "image/webp"}
            ):
                return cinema_api_error("The uploaded poster is missing or too large.", 400)
        with get_db_connection() as connection:
            connection.execute(
                "UPDATE cinema_films SET status = 'published' WHERE id = ? AND status = 'pending'",
                (film_id,),
            )
    except (BotoCoreError, ClientError):
        app.logger.exception("Could not verify or publish Cinema film %s.", film_id)
        return cinema_api_error("The uploaded film could not be verified. Try again later.", 502)

    return jsonify(message="Film added to the Cinema catalogue.", film_id=film_id)


@app.route("/api/cinema/films/<film_id>/play", methods=["GET"])
def play_cinema_film(film_id):
    _, error = cinema_current_user()
    if error:
        return error
    if not cinema_storage_ready():
        app.logger.error("Cinema playback is unavailable because Cloudflare R2 is not fully configured.")
        return cinema_api_error("Cloudflare R2 storage is not configured yet.", 503)

    with get_db_connection() as connection:
        film = connection.execute(
            "SELECT video_key FROM cinema_films WHERE id = ? AND status = 'published'",
            (film_id,),
        ).fetchone()
    if film is None:
        return cinema_api_error("That film is not available.", 404)

    try:
        video_url = cinema_signed_url(
            cinema_storage_client(),
            "get_object",
            film["video_key"],
            expires=3600,
            ResponseContentType="video/mp4",
        )
    except (BotoCoreError, ClientError):
        app.logger.exception("Could not create a playback link for Cinema film %s.", film_id)
        return cinema_api_error("The film could not be opened right now.", 502)
    return jsonify(video_url=video_url)


@app.route("/api/cinema/films/<film_id>/cancel", methods=["POST"])
def cancel_cinema_film_upload(film_id):
    user, error = cinema_json_admin_user()
    if error:
        return error
    if not cinema_storage_ready():
        app.logger.error("Cinema upload cancellation is unavailable because Cloudflare R2 is not fully configured.")
        return cinema_api_error("Cloudflare R2 storage is not configured yet.", 503)

    with get_db_connection() as connection:
        film = connection.execute(
            """
            SELECT video_key, poster_key
            FROM cinema_films
            WHERE id = ? AND uploaded_by = ? AND status = 'pending'
            """,
            (film_id, user["id"]),
        ).fetchone()
    if film is None:
        return cinema_api_error("This pending upload was not found.", 404)

    try:
        client = cinema_storage_client()
        for key in (film["video_key"], film["poster_key"]):
            if key:
                client.delete_object(Bucket=CLOUDFLARE_R2_BUCKET, Key=key)
        with get_db_connection() as connection:
            connection.execute(
                "DELETE FROM cinema_films WHERE id = ? AND status = 'pending'",
                (film_id,),
            )
    except (BotoCoreError, ClientError):
        app.logger.exception("Could not cancel pending Cinema film upload %s.", film_id)
        return cinema_api_error("The incomplete upload could not be cleaned up. Contact the app owner.", 502)
    return jsonify(message="Incomplete film upload removed.")


@app.route("/auth/register", methods=["POST"])
def register():
    if not valid_csrf_token():
        abort(400, description="Invalid form session. Reload the page and try again.")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = normalize_phone(request.form.get("phone", ""))
    invite_code = request.form.get("invite_code", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if PRIVATE_PREVIEW and not PREVIEW_INVITE_CODE:
        app.logger.error("Private-preview registration is closed: PREVIEW_INVITE_CODE is not configured.")
        flash("Preview registration is temporarily unavailable. Please contact the app owner.", "error")
    elif PRIVATE_PREVIEW and not secrets.compare_digest(invite_code, PREVIEW_INVITE_CODE):
        flash("That preview invite code is not valid.", "error")
    elif not name or len(name) > 80:
        flash("Enter a name no longer than 80 characters.", "error")
    elif len(email) > 254 or email.count("@") != 1 or any(char.isspace() for char in email):
        flash("Enter a valid email address.", "error")
    elif not phone:
        flash("Enter a valid phone number with country code, for example +2348012345678.", "error")
    elif len(password) < 8 or len(password) > 256:
        flash("Your password must be between 8 and 256 characters.", "error")
    elif password != confirm_password:
        flash("The passwords do not match.", "error")
    else:
        app_id = f"MPO-{uuid4().hex[:12].upper()}"
        user_id = None
        with get_db_connection() as connection:
            existing_phone = connection.execute(
                "SELECT id FROM users WHERE phone = ? LIMIT 1",
                (phone,),
            ).fetchone()
            if existing_phone:
                flash("That phone number is already linked to an account.", "error")
                return redirect("/")
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO users (app_id, name, email, phone, password_hash)
                    VALUES (?, ?, ?, ?, ?)
                    RETURNING id
                    """,
                    (app_id, name, email, phone, generate_password_hash(password)),
                )
                inserted_user = cursor.fetchone()
                user_id = inserted_user["id"] if inserted_user else None
            except sqlite3.IntegrityError:
                flash("An account with that email already exists. Sign in instead.", "error")
        if user_id:
            session.clear()
            session["user_id"] = user_id
            session["csrf_token"] = secrets.token_urlsafe(32)
            return redirect("/")

    return redirect("/")


@app.route("/auth/login", methods=["POST"])
def login():
    if not valid_csrf_token():
        abort(400, description="Invalid form session. Reload the page and try again.")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not email or not password or len(email) > 254 or len(password) > 256:
        flash("Email or password is incorrect.", "error")
        return redirect("/")

    with get_db_connection() as connection:
        user = connection.execute(
            "SELECT id, password_hash FROM users WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Email or password is incorrect.", "error")
        return redirect("/")

    session.clear()
    session["user_id"] = user["id"]
    session["csrf_token"] = secrets.token_urlsafe(32)
    return redirect("/")


@app.route("/auth/password-reset/request", methods=["POST"])
def request_password_reset():
    if not valid_csrf_token():
        abort(400, description="Invalid form session. Reload the page and try again.")

    session.pop("password_reset_user_id", None)
    session.pop("password_reset_channel", None)
    phone = normalize_phone(request.form.get("phone", ""))
    channel = request.form.get("channel", "").lower()
    if not phone or channel not in {"sms", "whatsapp"}:
        flash("Enter a valid phone number and choose SMS or WhatsApp.", "error")
        return redirect("/?reset=1")

    try:
        verify_service = twilio_verify_service()
    except RuntimeError:
        app.logger.error("Password reset is unavailable: Twilio Verify credentials are not configured.")
        flash("Password reset is not configured yet. Please contact the app administrator.", "error")
        return redirect("/?reset=1")

    with get_db_connection() as connection:
        matching_users = connection.execute(
            "SELECT id FROM users WHERE phone = ? LIMIT 2",
            (phone,),
        ).fetchall()

    if len(matching_users) == 1:
        now = int(time.time())
        if not reserve_password_reset_send(phone, now):
            flash("Please wait a minute before requesting another code.", "error")
            return redirect("/?reset=1")
        try:
            verification = verify_service.verifications.create(to=phone, channel=channel)
        except TwilioRestException as error:
            app.logger.error(
                "Twilio Verify request failed (status=%s, code=%s).",
                error.status,
                error.code,
            )
            flash("We could not send a verification code. Check the number and try again later.", "error")
            return redirect("/?reset=1")
        if verification.status != "pending":
            app.logger.error("Twilio Verify returned an unexpected request status.")
            flash("We could not start password reset. Please try again later.", "error")
            return redirect("/?reset=1")

        session["password_reset_user_id"] = matching_users[0]["id"]
        session["password_reset_channel"] = channel
        session["password_reset_started"] = int(time.time())

    flash(
        "If an account uses that phone number, a code has been sent. Enter the code below to continue.",
        "success",
    )
    return redirect("/?reset=1")


@app.route("/auth/password-reset/confirm", methods=["POST"])
def confirm_password_reset():
    if not valid_csrf_token():
        abort(400, description="Invalid form session. Reload the page and try again.")

    user_id = session.get("password_reset_user_id")
    channel = session.get("password_reset_channel")
    started_at = session.get("password_reset_started", 0)
    phone = normalize_phone(request.form.get("phone", ""))
    code = request.form.get("code", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if (
        not user_id
        or channel not in {"sms", "whatsapp"}
        or not phone
        or not code.isdigit()
        or not 4 <= len(code) <= 10
        or not isinstance(started_at, int)
        or time.time() - started_at > 600
    ):
        session.pop("password_reset_user_id", None)
        session.pop("password_reset_channel", None)
        session.pop("password_reset_started", None)
        flash("The code is invalid or expired. Request a new code and try again.", "error")
        return redirect("/?reset=1")
    if len(password) < 8 or len(password) > 256 or password != confirm_password:
        flash("Enter matching passwords between 8 and 256 characters.", "error")
        return redirect("/?reset=1")

    with get_db_connection() as connection:
        user = connection.execute(
            "SELECT id FROM users WHERE id = ? AND phone = ?",
            (user_id, phone),
        ).fetchone()
    if user is None:
        flash("The code is invalid or expired. Request a new code and try again.", "error")
        return redirect("/?reset=1")

    try:
        verify_service = twilio_verify_service()
    except RuntimeError:
        app.logger.error("Password reset is unavailable: Twilio Verify credentials are not configured.")
        flash("Password reset is not configured yet. Please contact the app administrator.", "error")
        return redirect("/?reset=1")

    try:
        verification_check = verify_service.verification_checks.create(to=phone, code=code)
    except TwilioRestException as error:
        app.logger.error(
            "Twilio Verify check failed (status=%s, code=%s).",
            error.status,
            error.code,
        )
        flash("The code could not be verified. Request a new code or try again later.", "error")
        return redirect("/?reset=1")

    if verification_check.status != "approved":
        flash("The code is incorrect or expired. Request a new code and try again.", "error")
        return redirect("/?reset=1")

    with get_db_connection() as connection:
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(password), user_id),
        )
    session.clear()
    flash("Your password was reset. Sign in with your new password.", "success")
    return redirect("/")


@app.route("/auth/logout", methods=["POST"])
def logout():
    if not valid_csrf_token():
        abort(400, description="Invalid form session. Reload the page and try again.")
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8082")),
        debug=False,
    )