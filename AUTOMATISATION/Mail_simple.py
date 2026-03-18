import smtplib
from email.mime.text import MIMEText

LOGIN="XXXXXXXXXX@smtp-brevo.com"
MDP="Ma clé SMTP"

msg = MIMEText("Test")
msg["Subject"] = "Test"
msg["From"] = "Adresse@gmail.com"
msg["To"]   = "Adresse@gmail.com"

with smtplib.SMTP("smtp-relay.brevo.com", 587) as smtp:
    smtp.set_debuglevel(1)
    smtp.starttls()
    smtp.login(LOGIN,MDP)
    smtp.send_message(msg)
    print("OK")
