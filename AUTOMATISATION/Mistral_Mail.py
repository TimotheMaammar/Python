#!/usr/bin/env python3

# Tâche planifiée : 
# 0 8 * * 6 python3 /root/AUTOM_SCIENCE/Mistral_Mail.py

import subprocess, smtplib, os, glob
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER

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

# ─────────────────────────────────────────────────────────────────────────────

def get_date_str():
    now = datetime.now()
    return now.strftime("%d-%m-%Y")

def run_script(label, script_name):
    """Exécute un script et retourne le statut"""
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
        # Prendre le plus récent
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

def create_pdf_from_txts(files_status, date_str):
    pdf_filename = f"Synthese_Veille_{date_str}.pdf"

    doc = SimpleDocTemplate(pdf_filename, pagesize=letter,
                           topMargin=0.5*inch, bottomMargin=0.5*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)

    styles = getSampleStyleSheet()

    # Styles personnalisés
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor='#1a1a1a',
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    section_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor='#2c3e50',
        spaceAfter=10,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )

    content_style = ParagraphStyle(
        'Content',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        spaceAfter=6,
        alignment=TA_LEFT
    )

    story = []

    # En-tête
    title = Paragraph("Synthèse Veille Scientifique — Résumés IA", title_style)
    story.append(title)
    story.append(Paragraph(f"Généré le {date_str}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))

    # Ajouter chaque section
    for source in ["arXiv", "HuggingFace", "Frontiers"]:
        if source in files_status and files_status[source]["ok"]:
            # Titre de la section
            story.append(Paragraph(source, section_style))

            # Contenu du fichier TXT
            txt_file = files_status[source]["file"]
            content = read_txt_file(txt_file)

            # Parser et ajouter le contenu
            for line in content.split('\n'):
                if line.strip():
                    # Ignorer les lignes de séparation
                    if line.startswith('=') or line.startswith('-'):
                        continue
                    story.append(Paragraph(line, content_style))
                else:
                    story.append(Spacer(1, 0.05*inch))

            # Saut de page entre les sections
            story.append(PageBreak())
        else:
            story.append(Paragraph(f"{source} — [FICHIER MANQUANT OU VIDE]", section_style))

    # Build PDF
    try:
        doc.build(story)
        print(f"✅ PDF créé: {pdf_filename}")
        return pdf_filename
    except Exception as e:
        print(f"❌ Erreur création PDF: {e}")
        return None

def send_mail(subject, body, pdf_file):
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"]    = MAIL_FROM
        msg["To"]      = MAIL_TO

        # Corps du message
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Pièce jointe PDF
        if pdf_file and os.path.exists(pdf_file):
            with open(pdf_file, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {pdf_file}")
            msg.attach(part)
            print(f"✅ PDF attaché: {pdf_file}")

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

    # Étape 3: Créer le PDF
    print("\n[ÉTAPE 3] Création du PDF unifié...")
    print("-" * 80)

    pdf_file = create_pdf_from_txts(files_status, date_str)

    if not pdf_file:
        print("❌ ERREUR: Impossible de créer le PDF")
        return

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

Cordialement.
"""

    send_mail(subject, body, pdf_file)

    print(f"\n{'='*80}")
    print(f"  ✨ PIPELINE TERMINÉ AVEC SUCCÈS")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
