"""Envio de e-mails via SMTP com STARTTLS (Titan ou compatível)."""

import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional


class SMTPSendError(Exception):
    """Erro específico de envio SMTP."""


def build_smtp_client(host: str, port: int, username: str, password: str):
    """Cria cliente SMTP autenticado com STARTTLS."""
    context = ssl.create_default_context()
    client = smtplib.SMTP(host=host, port=port, timeout=30)
    client.ehlo()
    client.starttls(context=context)
    client.ehlo()
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
    smtp_client: Optional[smtplib.SMTP] = None,
) -> None:
    """Envia e-mail de texto simples. Reutiliza cliente se fornecido."""
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    owns_client = smtp_client is None

    try:
        client.start()
        client.login()

        for idx in pending:
            row = df.loc[idx].to_dict()
            recipient = str(row.get(email_col, "")).strip()
            subject = render_template(subject_template, row)
            body = render_template(body_template, row)
            timestamp = now_iso()

            try:
                client.send_email(recipient=recipient, subject=subject, body=body)
                df.at[idx, "status"] = "enviado"
                df.at[idx, "erro"] = ""
                consecutive_errors = 0
                status = "enviado"
                error = ""
            except Exception as exc:
                df.at[idx, "status"] = "erro"
                df.at[idx, "erro"] = str(exc)
                status = "erro"
                error = str(df.at[idx, "erro"])
                consecutive_errors += 1

            df.at[idx, "enviado_em"] = timestamp
            append_log(
                cfg.log_path,
                {
                    "destinatario": recipient,
                    "horario": timestamp,
                    "status": status,
                    "erro": error,
                },
            )

            done += 1
            if progress_callback:
                progress_callback(done, total)
            if status_callback:
                status_callback(f"{done}/{total} -> {recipient}: {status}")

            if consecutive_errors >= cfg.max_consecutive_errors:
                if status_callback:
                    status_callback("Campanha interrompida por muitos erros consecutivos.")
                break

            if done < total:
                delay = random.uniform(cfg.delay_min_seconds, cfg.delay_max_seconds)
                if status_callback:
                    status_callback(f"Aguardando {delay:.1f}s antes do próximo envio...")
                time.sleep(delay)
    finally:
        client.stop()

    return df
