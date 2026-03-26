from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional

from .config import EnvConfig
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class EmailConfig:
    server: str
    port: int
    use_tls: bool
    username: str
    password: str
    sender: str
    recipient: str


class EmailNotifier:
    def __init__(self, config: Optional[EmailConfig]) -> None:
        self.config = config

    @classmethod
    def from_config(cls, env: EnvConfig) -> "EmailNotifier":
        if not (
            env.mail_server
            and env.mail_port
            and env.mail_username
            and env.mail_password
            and env.mail_default_sender
            and env.notify_email_to
        ):
            logger.warning("Email config incomplete; notifications disabled.")
            return cls(None)
        return cls(
            EmailConfig(
                server=env.mail_server,
                port=env.mail_port,
                use_tls=env.mail_use_tls if env.mail_use_tls is not None else True,
                username=env.mail_username,
                password=env.mail_password,
                sender=env.mail_default_sender,
                recipient=env.notify_email_to,
            )
        )

    def send(self, subject: str, body: str) -> None:
        if not self.config:
            return
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.config.sender
        message["To"] = self.config.recipient
        message.set_content(body)

        try:
            with smtplib.SMTP(self.config.server, self.config.port) as smtp:
                if self.config.use_tls:
                    smtp.starttls()
                smtp.login(self.config.username, self.config.password)
                smtp.send_message(message)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to send email: %s", exc)
