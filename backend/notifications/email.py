import os
import smtplib
from email.mime.text import MIMEText


def is_email_configured() -> bool:
    """Return True if all required SMTP env vars are set."""
    required = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM")
    return all(os.environ.get(k) for k in required)


def send_trade_email(to_address: str, subject: str, body: str) -> None:
    """Send a plain-text email. No-op if SMTP not configured."""
    if not is_email_configured():
        return

    host = os.environ["SMTP_HOST"]
    port = int(os.environ["SMTP_PORT"])
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    from_addr = os.environ["SMTP_FROM"]

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_address

    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.sendmail(from_addr, [to_address], msg.as_string())
