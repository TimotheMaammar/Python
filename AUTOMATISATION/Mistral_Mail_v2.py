#!/usr/bin/env python3
import subprocess, smtplib, os, glob
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

# ── Configuration ────────────────────────────────────────────────────────────
SMTP_HOST  = "smtp-relay.brevo.com"
SMTP_PORT  = 587
SMTP_USER  = "a54a73001@smtp-brevo.com"
SMTP_PASS  = "XXX"
MAIL_FROM  = "timothe.maammar@gmail.com"
MAIL_TO    = "timothe.maammar@gmail.com"

SCRIPTS = [
    ("arXiv", "/root/AUTOM_SCIENCE/Mistral_arXiv.py"),
    ("HuggingFace", "/root/AUTOM_SCIENCE/Mistral_HF.py"),
    ("Frontiers", "/root/AUTOM_SCIENCE/Mistral_Frontiers.py"),
]

MAX_EMAIL_SIZE = 25000  # 25KB max pour texte brut dans email

# ─────────────────────────────────────────────────────────────────────────────

def get_date_str():
    now = datetime.now()
    return now.strftime("%d-%m-%Y")

def run_script(label, script_name):
    try:
        print(f"[*] Exécution de {label}...")
        result = subprocess.run(
            ["python3", script_name],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            print(f"✅ {label} exécuté avec succès")
            return True, result.stdout.strip()
        else:
            error = result.stderr.strip() if result.stderr else "Code de retour non-zéro"
            print(f"❌ Erreur {label}: {error}")
            return False, error
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout {label}")
        return False, f"Timeout dépassé pour {label}"
    except Exception as e:
        print(f"❌ Exception {label}: {e}")
        return False, str(e)

def find_txt_file(date_str, prefix):
    pattern = f"{prefix}_{date_str}.txt"
    if os.path.exists(pattern):
        return pattern
    all_files = glob.glob(f"{prefix}_*.txt")
    if all_files:
        return sorted(all_files)[-1]
    return None

def verify_txt_files(date_str):
    files_status = {}
    prefixes = ["arXiv", "HuggingFace", "Frontiers"]

    for prefix in prefixes:
        txt_file = find_txt_file(date_str, prefix)
        if txt_file and os.path.exists(txt_file) and os.path.getsize(txt_file) > 0:
            files_status[prefix] = {"file": txt_file, "ok": True}
            print(f"✅ {txt_file} trouvé ({os.path.getsize(txt_file)} bytes)")
        else:
            files_status[prefix] = {"file": txt_file, "ok": False}
            print(f"❌ {prefix} : fichier manquant ou vide")

    return files_status

def read_txt_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[ERREUR LECTURE]: {e}"

def combine_txt_files(files_status):
    combined = ""

    for source in ["arXiv", "HuggingFace", "Frontiers"]:
        if source in files_status and files_status[source]["ok"]:
            combined += f"\n{'='*80}\n"
            combined += f"  {source}\n"
            combined += f"{'='*80}\n\n"

            content = read_txt_file(files_status[source]["file"])
            combined += content
            combined += "\n\n"
        else:
            combined += f"\n{'='*80}\n"
            combined += f"  {source} — [FICHIER MANQUANT OU VIDE]\n"
            combined += f"{'='*80}\n\n"

    return combined

def send_mail(subject, body, txt_content=None, date_str=None):
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"]    = MAIL_FROM
        msg["To"]      = MAIL_TO

        # Décision: texte brut ou pièce jointe
        if txt_content and len(txt_content) > MAX_EMAIL_SIZE:
            # Trop volumineux: envoyer en pièce jointe
            msg.attach(MIMEText(body, "plain", "utf-8"))

            txt_filename = f"Synthese_Veille_{date_str}.txt"
            with open(txt_filename, "w", encoding="utf-8") as f:
                f.write(txt_content)

            with open(txt_filename, "rb") as attachment:
                part = MIMEBase("text", "plain")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={txt_filename}")
            msg.attach(part)

            print(f"✅ Contenu > {MAX_EMAIL_SIZE} bytes: envoyé en pièce jointe TXT")
        else:
            # Assez petit: envoyer en texte brut
            full_body = body + "\n\n" + txt_content if txt_content else body
            msg.attach(MIMEText(full_body, "plain", "utf-8"))
            print(f"✅ Contenu en texte brut ({len(txt_content)} bytes)")

        # Envoi
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)

        print(f"✅ Email envoyé à {MAIL_TO}")
        return True
    except Exception as e:
        print(f"❌ Erreur envoi email: {e}")
        return False

def main():
    date_str = get_date_str()
    print(f"\n{'='*80}")
    print(f"  SYNTHÈSE VEILLE SCIENTIFIQUE — {date_str}")
    print(f"{'='*80}\n")

    # Étape 1: Exécuter les 3 scripts
    print("\n[ÉTAPE 1] Exécution des scripts de scraping...")
    print("-" * 80)

    for label, script_name in SCRIPTS:
        success, output = run_script(label, script_name)
        if not success:
            print(f"⚠️  {label} n'a pas généré de fichier TXT")

    # Étape 2: Vérifier les fichiers
    print("\n[ÉTAPE 2] Vérification des fichiers TXT...")
    print("-" * 80)

    files_status = verify_txt_files(date_str)

    # Vérifier qu'au moins un fichier est OK
    any_ok = any(f["ok"] for f in files_status.values())
    if not any_ok:
        print("❌ ERREUR: Aucun fichier valide trouvé!")
        return

    # Étape 3: Combiner les fichiers
    print("\n[ÉTAPE 3] Combinaison des fichiers...")
    print("-" * 80)

    txt_content = combine_txt_files(files_status)
    print(f"✅ Contenu généré ({len(txt_content)} bytes)")

    # Étape 4: Envoyer l'email
    print("\n[ÉTAPE 4] Envoi de l'email...")
    print("-" * 80)

    subject = f"Veille IA — Synthèse {date_str}"
    body = f"""Bonjour,

Veille scientifique du {date_str}.

Derniers papiers de recherche en IA depuis :
- arXiv
- HuggingFace
- Frontiers

--- CONTENU ---

"""

    send_mail(subject, body, txt_content, date_str)

    print(f"\n{'='*80}")
    print(f"  ✨ PIPELINE TERMINÉ AVEC SUCCÈS")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
