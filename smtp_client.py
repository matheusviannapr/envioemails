import imaplib
import time
import smtplib
import re
from email.header import Header
from html import unescape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class SmtpClient:
    def __init__(self, host: str, port: int, email: str, password: str, imap_host: str = "imap.secureserver.net", imap_port: int = 993):
        self.host = host
        self.port = port
        self.email = email
        self.password = password
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.server = None

    def start(self):
        try:
            if self.port == 465:
                self.server = smtplib.SMTP_SSL(self.host, self.port)
            else:
                self.server = smtplib.SMTP(self.host, self.port)
                self.server.starttls()
        except Exception as exc:
            raise RuntimeError(
                f"Falha ao conectar ao servidor SMTP {self.host}:{self.port}. Erro: {exc}"
            ) from exc

    def login(self):
        if not self.server:
            raise RuntimeError("Servidor SMTP não inicializado. Chame start() primeiro.")
        try:
            self.server.login(self.email, self.password)
        except smtplib.SMTPAuthenticationError as exc:
            raise RuntimeError(
                f"Falha de autenticação. Verifique seu e-mail e senha. Erro: {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Erro inesperado durante o login SMTP: {exc}") from exc


    def _decode_folder_line(self, raw_line) -> str:
        if isinstance(raw_line, bytes):
            return raw_line.decode("utf-8", errors="ignore")
        return str(raw_line)

    def _resolve_sent_folder(self, imap) -> str | None:
        candidates = ["Sent", "Sent Items", "Enviados", "Itens Enviados"]

        result, folders = imap.list()
        if result != "OK" or not folders:
            return None

        parsed = [self._decode_folder_line(line) for line in folders]

        for candidate in candidates:
            for line in parsed:
                if candidate.lower() in line.lower():
                    # Nome da pasta é o trecho final entre aspas ou após último espaço.
                    if '"' in line:
                        parts = line.split('"')
                        if len(parts) >= 3 and parts[-2].strip():
                            return parts[-2].strip()
                    fallback = line.rsplit(" ", 1)[-1].strip()
                    return fallback.strip('"')

        return None

    def _save_to_sent(self, message_bytes: bytes):
        with imaplib.IMAP4_SSL(self.imap_host, self.imap_port) as imap:
            imap.login(self.email, self.password)
            sent_folder = self._resolve_sent_folder(imap)
            if not sent_folder:
                return
            imap.append(
                sent_folder,
                r"\Seen",
                imaplib.Time2Internaldate(time.time()),
                message_bytes,
            )


    def _html_to_text(self, html_content: str) -> str:
        text = re.sub(r"<\s*br\s*/?>", "\n", html_content, flags=re.IGNORECASE)
        text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</li\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        return unescape(text).strip()

    def send_email(self, recipient: str, subject: str, body: str):
        if not self.server:
            raise RuntimeError("Servidor SMTP não inicializado. Chame start() primeiro.")

        msg = MIMEMultipart("alternative")
        msg["From"] = self.email
        msg["To"] = recipient
        msg["Subject"] = Header(subject, "utf-8")

        looks_like_html = bool(re.search(r"<[^>]+>", body or ""))
        if looks_like_html:
            plain_fallback = self._html_to_text(body) or "Mensagem em HTML"
            msg.attach(MIMEText(plain_fallback, "plain", "utf-8"))
            msg.attach(MIMEText(body, "html", "utf-8"))
        else:
            msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            self.server.sendmail(self.email, recipient, msg.as_string())
            # Não impede o envio principal caso haja falha apenas ao salvar em Enviados.
            try:
                self._save_to_sent(msg.as_bytes())
            except Exception:
                pass
        except Exception as exc:
            raise RuntimeError(f"Falha ao enviar e-mail para {recipient}. Erro: {exc}") from exc

    def stop(self):
        if self.server:
            try:
                self.server.quit()
            except Exception:
                pass
            finally:
                self.server = None
