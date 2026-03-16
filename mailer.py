"""Envio de e-mails via SMTP SSL (Titan ou compatível)."""

import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional


class SMTPSendError(Exception):
    """Erro específico de envio SMTP."""


def build_smtp_client(host: str, port: int, username: str, password: str):
    """Cria cliente SMTP SSL autenticado."""
    context = ssl.create_default_context()
    client = smtplib.SMTP_SSL(host=host, port=port, context=context, timeout=30)
    client.login(username, password)
    return client


def send_email(
    host: str,
    port: int,
    username: str,
    password: str,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    smtp_client: Optional[smtplib.SMTP_SSL] = None,
) -> None:
    """Envia e-mail de texto simples. Reutiliza cliente se fornecido."""
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    owns_client = smtp_client is None

    try:
        client = smtp_client or build_smtp_client(host, port, username, password)
        client.send_message(msg)
    except Exception as exc:  # noqa: BLE001 - queremos capturar falhas SMTP de forma robusta
        raise SMTPSendError(str(exc)) from exc
    finally:
        if owns_client and smtp_client is None:
            try:
                client.quit()
            except Exception:
                # Falha ao encerrar não impede fluxo.
                pass
