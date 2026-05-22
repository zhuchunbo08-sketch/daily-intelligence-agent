from email.message import EmailMessage
import logging
import smtplib

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return all(
            [
                self.settings.smtp_host,
                self.settings.smtp_username,
                self.settings.smtp_password,
                self.settings.smtp_from,
                self.settings.smtp_to,
            ]
        )

    def send(self, subject: str, content: str) -> None:
        if not self.enabled:
            raise RuntimeError("SMTP settings are not configured")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.smtp_from
        message["To"] = self.settings.smtp_to
        message.set_content(content)

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(message)
        logger.info("Email sent: %s", subject)
