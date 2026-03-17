import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class SmtpClient:
    def __init__(self, host: str, port: int, email: str, password: str):
        self.host = host
        self.port = port
        self.email = email
        self.password = password
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

    def send_email(self, recipient: str, subject: str, body: str):
        if not self.server:
            raise RuntimeError("Servidor SMTP não inicializado. Chame start() primeiro.")

        msg = MIMEMultipart()
        msg["From"] = self.email
        msg["To"] = recipient
        msg["Subject"] = Header(subject, "utf-8")
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            self.server.sendmail(self.email, recipient, msg.as_string())
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
