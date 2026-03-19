#!/usr/bin/env python3
import subprocess, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date

# ── Configuration ────────────────────────────────────────────────────────────
SMTP_HOST  = "smtp-relay.brevo.com"
SMTP_PORT  = 587
SMTP_USER  = "a54a73001@smtp-brevo.com"  # Adresse trouvée dans le profil Brevo
SMTP_PASS  = "bskkiQ0959D4Owy"           # Mot de passe SMTP créé sur Brevo
MAIL_FROM  = "timothe.maammar@gmail.com" # Important pour le filtre
MAIL_TO    = "timothe.maammar@gmail.com"

SCRIPTS = [
    ("HuggingFace daily papers", "Hugging.py"),
    ("arXiv papers",          "arXiv.py"),
    ("JMLR papers",              "JMLR.py")
]
# ─────────────────────────────────────────────────────────────────────────────

def run_script(label, path):
    try:
        result = subprocess.run(
            ["python3", path],
            capture_output=True, text=True, timeout=60
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            output += f"\n[ERREUR]\n{result.stderr.strip()}"
        return output or f"[{label}] — aucun résultat"
    except subprocess.TimeoutExpired:
        return f"[{label}] — timeout dépassé"
    except Exception as e:
        return f"[{label}] — erreur : {e}"

def build_body(sections):
    parts = []
    for label, content in sections:
        parts.append(f"{'='*80}")
        parts.append(f"  {label.upper()}")
        parts.append(f"{'='*80}")
        parts.append(content)
        parts.append("")
    return "\n".join(parts)

def send_mail(subject, body):
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"]    = MAIL_FROM
    msg["To"]      = MAIL_TO
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)

def main():
    today   = date.today().strftime("%d/%m/%Y")
    subject = f"Veille IA — {today}"

    sections = [(label, run_script(label, path)) for label, path in SCRIPTS]
    body     = build_body(sections)

    send_mail(subject, body)

if __name__ == "__main__":
    main()
