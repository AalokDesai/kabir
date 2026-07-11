"""
Dynamic email sending for Kabir.

The sender reads a locally saved profile instead of using one hard-coded SMTP
account. Gmail works out of the box with an app password; Zimbra/custom mail
servers can use auto-guessed hosts or explicit SMTP settings from the profile.
"""

import datetime
import base64
import json
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
try:
    import win32crypt
except ImportError:
    win32crypt = None


TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "template.html")
PROFILE_PATH = os.path.join(os.path.dirname(__file__), "mail_profile.json")
PASSWORD_FIELD = "password_protected"

DEFAULT_PROFILE = {
    "name": "",
    "age": "",
    "email": "",
    "smtp_user": "",
    "password": "",
    "provider": "auto",
    "smtp_host": "",
    "smtp_port": 587,
    "use_tls": True,
}

PROVIDER_SETTINGS = {
    "gmail": {"host": "smtp.gmail.com", "port": 587, "use_tls": True},
    "googlemail": {"host": "smtp.gmail.com", "port": 587, "use_tls": True},
    "outlook": {"host": "smtp.office365.com", "port": 587, "use_tls": True},
    "hotmail": {"host": "smtp.office365.com", "port": 587, "use_tls": True},
    "live": {"host": "smtp.office365.com", "port": 587, "use_tls": True},
    "yahoo": {"host": "smtp.mail.yahoo.com", "port": 587, "use_tls": True},
    "icloud": {"host": "smtp.mail.me.com", "port": 587, "use_tls": True},
}


def _clean_profile(profile):
    clean = DEFAULT_PROFILE.copy()
    if isinstance(profile, dict):
        clean.update(profile)

    clean["email"] = str(clean.get("email", "")).strip().lower()
    clean["smtp_user"] = str(clean.get("smtp_user", "") or "").strip()
    clean["provider"] = str(clean.get("provider", "auto") or "auto").strip().lower()
    clean["password"] = str(clean.get("password", "") or "").strip()
    clean["smtp_host"] = str(clean.get("smtp_host", "") or "").strip()
    try:
        clean["smtp_port"] = int(clean.get("smtp_port") or 587)
    except (TypeError, ValueError):
        clean["smtp_port"] = 587
    clean["use_tls"] = bool(clean.get("use_tls", True))
    domain = _email_domain(clean["email"])
    if clean["provider"] in {"auto", "gmail", "googlemail"} and domain in {"gmail.com", "googlemail.com"}:
        clean["password"] = "".join(clean["password"].split())
    return clean


def _protect_secret(value):
    if not value:
        return ""
    if win32crypt is None:
        raise RuntimeError("pywin32 is required to encrypt mail passwords on Windows.")
    protected = win32crypt.CryptProtectData(value.encode("utf-8"), None, None, None, None, 0)
    return base64.b64encode(protected).decode("ascii")


def _unprotect_secret(value):
    if not value:
        return ""
    if win32crypt is None:
        return ""
    protected = base64.b64decode(str(value).encode("ascii"))
    _, data = win32crypt.CryptUnprotectData(protected, None, None, None, 0)
    return data.decode("utf-8")


def _read_profile_file():
    if not os.path.exists(PROFILE_PATH):
        return DEFAULT_PROFILE.copy(), False
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            profile = json.load(f)
        if not isinstance(profile, dict):
            return DEFAULT_PROFILE.copy(), False
        return profile, False
    except (OSError, json.JSONDecodeError):
        return DEFAULT_PROFILE.copy(), False


def _write_profile_file(clean):
    stored = clean.copy()
    password = stored.pop("password", "")
    stored[PASSWORD_FIELD] = _protect_secret(password) if password else stored.get(PASSWORD_FIELD, "")
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(stored, f, indent=2)


def load_mail_profile(include_password=True):
    profile, _ = _read_profile_file()
    protected_password = profile.get(PASSWORD_FIELD, "")
    plaintext_password = str(profile.get("password", "") or "")

    if protected_password:
        try:
            profile["password"] = _unprotect_secret(protected_password)
        except Exception:
            profile["password"] = ""
    elif plaintext_password:
        # One-time migration from the old plaintext profile format.
        profile["password"] = plaintext_password
        _write_profile_file(_clean_profile(profile))

    profile = _clean_profile(profile)
    if not include_password:
        profile["password"] = ""
    profile.pop(PASSWORD_FIELD, None)
    return profile


def save_mail_profile(profile):
    clean = _clean_profile(profile)
    if not clean["password"]:
        existing = load_mail_profile(include_password=True)
        clean["password"] = existing.get("password", "")
    _write_profile_file(clean)
    public_profile = clean.copy()
    public_profile["password"] = ""
    return public_profile


def get_profile_status():
    profile = load_mail_profile(include_password=True)
    missing = []
    if not profile["email"]:
        missing.append("email")
    login_user = profile["smtp_user"] or profile["email"]
    if not login_user:
        missing.append("SMTP username")
    if not profile["password"]:
        missing.append("password/app password")

    smtp = resolve_smtp_settings(profile)
    if not smtp["host"]:
        missing.append("SMTP host")

    return {
        "configured": not missing,
        "missing": missing,
        "email": profile["email"],
        "smtp_user": profile["smtp_user"],
        "name": profile["name"],
        "provider": smtp["provider"],
        "smtp_host": smtp["host"],
        "smtp_port": smtp["port"],
    }


def _email_domain(email):
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[1].lower()


def resolve_smtp_settings(profile):
    profile = _clean_profile(profile)
    provider = profile["provider"]
    domain = _email_domain(profile["email"])
    domain_key = domain.split(".", 1)[0] if domain else ""

    if profile["smtp_host"]:
        return {
            "provider": provider if provider != "auto" else "custom",
            "host": profile["smtp_host"],
            "port": profile["smtp_port"],
            "use_tls": profile["use_tls"],
        }

    if provider in PROVIDER_SETTINGS:
        settings = PROVIDER_SETTINGS[provider].copy()
        settings["provider"] = provider
        return settings

    if provider == "auto" and domain_key in PROVIDER_SETTINGS:
        settings = PROVIDER_SETTINGS[domain_key].copy()
        settings["provider"] = domain_key
        return settings

    if domain:
        return {
            "provider": "custom",
            "host": f"mail.{domain}",
            "port": profile["smtp_port"],
            "use_tls": profile["use_tls"],
        }

    return {"provider": provider, "host": "", "port": profile["smtp_port"], "use_tls": True}


def _load_html_template():
    """Load template.html and substitute {{marchYear}}."""
    if not os.path.exists(TEMPLATE_PATH):
        return None
    march_year = datetime.datetime.now().year
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    return html.replace("{{marchYear}}", str(march_year))


def _collect_attachments(folder_path):
    if not folder_path or not os.path.isdir(folder_path):
        return []
    attachments = []
    for fname in os.listdir(folder_path):
        full = os.path.join(folder_path, fname)
        if os.path.isfile(full):
            attachments.append(full)
    return attachments


def _build_message(profile, to_email, subject, body_text, folder_path, use_template):
    msg = MIMEMultipart("alternative" if use_template else "mixed")
    from_name = profile.get("name", "").strip()
    from_addr = profile["email"]
    msg["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
    msg["To"] = to_email
    msg["Subject"] = subject

    if use_template:
        html_body = _load_html_template()
        msg.attach(MIMEText(body_text, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))
    else:
        msg.attach(MIMEText(body_text, "plain"))

    attachment_files = _collect_attachments(folder_path)
    for file_path in attachment_files:
        fname = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
        msg.attach(part)

    return msg, attachment_files


def _auth_help(profile, smtp, error=None):
    provider = smtp.get("provider", profile.get("provider", "auto"))
    login_user = profile.get("smtp_user") or profile.get("email")
    error_text = ""
    if error is not None:
        raw_error = getattr(error, "smtp_error", b"")
        if isinstance(raw_error, bytes):
            error_text = raw_error.decode("utf-8", "ignore")
        else:
            error_text = str(raw_error)

    if provider in {"gmail", "googlemail"}:
        if "Application-specific password required" in error_text or "InvalidSecondFactor" in error_text:
            return (
                "Gmail rejected the login because an app password is required. In Profile, "
                "replace the Gmail password with a new 16-character Google app password."
            )
        return (
            "Authentication failed for Gmail. Use a Google app password, not your normal "
            "Gmail password, and make sure the SMTP username is your full Gmail address."
        )
    if provider == "zimbra" or smtp.get("host", "").startswith("mail."):
        return (
            f"Authentication failed on {smtp['host']} as {login_user}. For Zimbra, try your "
            "full email as SMTP username, or the mailbox username your organization gave you."
        )
    return (
        f"Authentication failed on {smtp['host']} as {login_user}. Check the SMTP username "
        "and password/app password in Profile."
    )


def send_email(to_email, subject, body_text, folder_path=None, use_template=False, profile=None):
    """
    Send an email via the saved profile or a supplied profile dictionary.

    Returns (True, message) or (False, message).
    """
    profile = _clean_profile(profile or load_mail_profile(include_password=True))
    smtp = resolve_smtp_settings(profile)

    login_user = profile["smtp_user"] or profile["email"]

    if not profile["email"] or not login_user or not profile["password"]:
        return False, "Mail profile is incomplete. Open Profile and add email, SMTP username, and password."
    if not smtp["host"]:
        return False, "SMTP host is missing. Open Profile and add SMTP settings."

    try:
        msg, attachment_files = _build_message(
            profile, to_email, subject, body_text, folder_path, use_template
        )

        with smtplib.SMTP(smtp["host"], smtp["port"], timeout=20) as server:
            server.ehlo()
            if smtp["use_tls"]:
                server.starttls()
                server.ehlo()
            server.login(login_user, profile["password"])
            server.sendmail(profile["email"], to_email, msg.as_string())

        n = len(attachment_files)
        att_msg = f" with {n} attachment{'s' if n != 1 else ''}" if n else ""
        return True, f"Email sent to {to_email}{att_msg} from {profile['email']}."

    except smtplib.SMTPAuthenticationError as e:
        return False, _auth_help(profile, smtp, e)
    except smtplib.SMTPConnectError:
        return False, f"Cannot connect to {smtp['host']}:{smtp['port']}. Check SMTP settings."
    except FileNotFoundError as e:
        return False, f"Attachment file not found: {e}"
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"


def build_qsb_subject():
    year = datetime.datetime.now().year
    return f"Fwd: QSB SUBMISSION FOR PERIOD ENDED 31 MARCH {year}"
