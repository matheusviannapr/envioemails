import csv
import html
import imaplib
import json
import queue
import random
import re
import smtplib
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from string import Formatter
from tkinter import messagebox
from typing import Any

import customtkinter as ctk


APP_TITLE = "Email Campaign Desktop"
CONFIG_PATH = Path("desktop_config.json")
CHECKPOINT_PATH = Path("desktop_checkpoint.json")
TEXT_LOG_PATH = Path("desktop_campaign.log")
MAX_ALLOWED_PER_CAMPAIGN = 100
GRID_EXAMPLE = "email\tnome\tempresa\nana@empresa.com\tAna\tEmpresa A\nbruno@empresa.com\tBruno\tEmpresa B"


@dataclass
class CampaignConfig:
    smtp_host: str = "smtpout.secureserver.net"
    smtp_port: int = 465
    email: str = ""
    password: str = ""
    imap_host: str = "imap.secureserver.net"
    imap_port: int = 993
    subject: str = "Olá {nome}, proposta para {empresa}"
    body_html: str = "<p>Olá <strong>{nome}</strong>,</p><p>Tudo bem?</p>"
    delay_min: float = 6.0
    delay_max: float = 9.0
    long_pause_seconds: int = 90
    long_pause_every: int = 25
    max_per_campaign: int = 100


class SmtpImapClient:
    def __init__(self, cfg: CampaignConfig):
        self.cfg = cfg
        self.server: smtplib.SMTP | smtplib.SMTP_SSL | None = None

    def start(self):
        if self.cfg.smtp_port == 465:
            self.server = smtplib.SMTP_SSL(self.cfg.smtp_host, self.cfg.smtp_port, timeout=30)
        else:
            self.server = smtplib.SMTP(self.cfg.smtp_host, self.cfg.smtp_port, timeout=30)
            self.server.starttls()

    def login(self):
        if not self.server:
            raise RuntimeError("Servidor SMTP não inicializado")
        self.server.login(self.cfg.email, self.cfg.password)

    def stop(self):
        if self.server:
            try:
                self.server.quit()
            except Exception:
                pass
            self.server = None

    def test_imap(self):
        with imaplib.IMAP4_SSL(self.cfg.imap_host, self.cfg.imap_port) as imap:
            imap.login(self.cfg.email, self.cfg.password)
            status, _ = imap.list()
            if status != "OK":
                raise RuntimeError("Não foi possível listar pastas IMAP")

    def _resolve_sent_folder(self, imap: imaplib.IMAP4_SSL) -> str | None:
        candidates = ["Sent", "Sent Items", "Enviados", "Itens Enviados"]
        status, folders = imap.list()
        if status != "OK" or not folders:
            return None
        for line in folders:
            decoded = line.decode("utf-8", errors="ignore")
            for candidate in candidates:
                if candidate.lower() in decoded.lower():
                    if '"' in decoded:
                        parts = decoded.split('"')
                        if len(parts) >= 3 and parts[-2].strip():
                            return parts[-2].strip()
                    return decoded.rsplit(" ", 1)[-1].strip().strip('"')
        return None

    def _save_to_sent(self, msg_bytes: bytes):
        try:
            with imaplib.IMAP4_SSL(self.cfg.imap_host, self.cfg.imap_port) as imap:
                imap.login(self.cfg.email, self.cfg.password)
                sent_folder = self._resolve_sent_folder(imap)
                if sent_folder:
                    imap.append(sent_folder, r"\\Seen", imaplib.Time2Internaldate(time.time()), msg_bytes)
        except Exception:
            pass

    def send_email(self, recipient: str, subject: str, body_html: str):
        if not self.server:
            raise RuntimeError("Servidor SMTP não inicializado")

        msg = MIMEMultipart("alternative")
        msg["From"] = self.cfg.email
        msg["To"] = recipient
        msg["Subject"] = Header(subject, "utf-8")

        plain = html_to_text(body_html)
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        self.server.sendmail(self.cfg.email, recipient, msg.as_string())
        self._save_to_sent(msg.as_bytes())


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def extract_placeholders(template: str) -> set[str]:
    return {f for _, f, _, _ in Formatter().parse(template) if f}


class SafeDict(dict):
    def __missing__(self, key):
        return ""


def render_template(template: str, row: dict[str, Any]) -> str:
    clean = {k: "" if v is None else str(v) for k, v in row.items()}
    return template.format_map(SafeDict(clean))


def html_to_text(body_html: str) -> str:
    text = re.sub(r"<\s*br\s*/?>", "\n", body_html, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip() or "Mensagem HTML"


def parse_pasted_grid(raw_text: str) -> list[dict[str, str]]:
    lines = [line for line in raw_text.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("Cole uma planilha com cabeçalho e linhas.")

    sniff = csv.Sniffer()
    delimiter = "\t"
    try:
        dialect = sniff.sniff("\n".join(lines[:3]), delimiters="\t;,")
        delimiter = dialect.delimiter
    except Exception:
        pass

    reader = csv.DictReader(lines, delimiter=delimiter)
    if not reader.fieldnames:
        raise RuntimeError("Planilha sem cabeçalho.")

    rows = []
    for row in reader:
        cleaned = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        rows.append(cleaned)

    if not rows:
        raise RuntimeError("Planilha sem linhas de dados.")

    email_key = None
    for key in rows[0].keys():
        if key.lower() == "email":
            email_key = key
            break
    if not email_key:
        raise RuntimeError("A planilha precisa ter uma coluna chamada 'email'.")

    normalized = []
    for row in rows:
        row["__email"] = row.get(email_key, "").strip()
        row["status"] = row.get("status", "")
        row["erro"] = row.get("erro", "")
        row["enviado_em"] = row.get("enviado_em", "")
        normalized.append(row)

    return normalized


class DesktopApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        self.title(APP_TITLE)
        self.geometry("1280x900")

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()
        self.worker_thread: threading.Thread | None = None

        self.sent_count = 0
        self.fail_count = 0
        self.remaining_count = 0

        self.cfg = self.load_config()
        self.vars: dict[str, ctk.StringVar] = {}
        self._build_ui()
        self._load_cfg_to_ui()
        self.after(200, self._drain_log_queue)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        container = ctk.CTkScrollableFrame(self)
        container.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        container.grid_columnconfigure((0, 1), weight=1)

        left = ctk.CTkFrame(container)
        right = ctk.CTkFrame(container)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=6)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=6)
        left.grid_columnconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self._section_title(left, "Configuração SMTP/IMAP", 0)
        self._entry(left, "SMTP host", "smtp_host", 1)
        self._entry(left, "SMTP porta", "smtp_port", 2)
        self._entry(left, "E-mail", "email", 3)
        self._entry(left, "Senha", "password", 4, show="*")
        self._entry(left, "IMAP host", "imap_host", 5)
        self._entry(left, "IMAP porta", "imap_port", 6)

        ctk.CTkButton(left, text="Testar SMTP", command=self.test_smtp).grid(row=7, column=0, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(left, text="Testar IMAP", command=self.test_imap).grid(row=7, column=1, padx=8, pady=8, sticky="ew")

        self._section_title(left, "Regras da campanha", 8)
        self._entry(left, "Delay mínimo (s)", "delay_min", 9)
        self._entry(left, "Delay máximo (s)", "delay_max", 10)
        self._entry(left, "Pausa longa (s)", "long_pause_seconds", 11)
        self._entry(left, "A cada X envios", "long_pause_every", 12)
        self._entry(left, "Máx. e-mails na campanha", "max_per_campaign", 13)

        self._section_title(left, "Planilha (colar dados)", 14)
        ctk.CTkLabel(left, text="Cole aqui uma tabela (Excel/Sheets) com coluna 'email':").grid(row=15, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 2))
        self.grid_text = ctk.CTkTextbox(left, height=220)
        self.grid_text.grid(row=16, column=0, columnspan=2, sticky="nsew", padx=8, pady=4)
        self.grid_text.insert("1.0", GRID_EXAMPLE)

        ctk.CTkButton(left, text="Validar planilha colada", command=self.validate_grid).grid(row=17, column=0, columnspan=2, padx=8, pady=(6, 8), sticky="ew")

        self._section_title(right, "Mensagem", 0)
        subject_line = ctk.CTkFrame(right)
        subject_line.grid(row=1, column=0, sticky="ew", padx=8, pady=(8, 2))
        subject_line.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(subject_line, text="Assunto").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.subject_entry = ctk.CTkEntry(subject_line)
        self.subject_entry.grid(row=0, column=1, sticky="ew")

        toolbar = ctk.CTkFrame(right)
        toolbar.grid(row=2, column=0, sticky="ew", padx=8, pady=(8, 4))
        toolbar.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        ctk.CTkButton(toolbar, text="Negrito", command=lambda: self.wrap_selection("<strong>", "</strong>")).grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        ctk.CTkButton(toolbar, text="Itálico", command=lambda: self.wrap_selection("<em>", "</em>")).grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        ctk.CTkButton(toolbar, text="Parágrafo", command=lambda: self.wrap_selection("<p>", "</p>\n")).grid(row=0, column=2, padx=4, pady=4, sticky="ew")
        ctk.CTkButton(toolbar, text="Lista", command=self.insert_list_block).grid(row=0, column=3, padx=4, pady=4, sticky="ew")
        ctk.CTkButton(toolbar, text="Quebra linha", command=lambda: self.insert_at_cursor("<br>\n")).grid(row=0, column=4, padx=4, pady=4, sticky="ew")

        ctk.CTkLabel(right, text="Editor HTML do corpo").grid(row=3, column=0, sticky="w", padx=8, pady=(4, 2))
        self.body_text = ctk.CTkTextbox(right, height=210)
        self.body_text.grid(row=4, column=0, sticky="ew", padx=8, pady=2)

        self.placeholder_label = ctk.CTkLabel(right, text="Placeholders: -")
        self.placeholder_label.grid(row=5, column=0, sticky="w", padx=8, pady=(4, 8))

        button_frame = ctk.CTkFrame(right)
        button_frame.grid(row=6, column=0, sticky="ew", padx=8, pady=8)
        button_frame.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkButton(button_frame, text="Iniciar campanha", command=self.start_campaign).grid(row=0, column=0, padx=4, pady=6, sticky="ew")
        ctk.CTkButton(button_frame, text="Pausar/Retomar", command=self.toggle_pause).grid(row=0, column=1, padx=4, pady=6, sticky="ew")
        ctk.CTkButton(button_frame, text="Parar", command=self.stop_campaign).grid(row=0, column=2, padx=4, pady=6, sticky="ew")

        self.progress = ctk.CTkProgressBar(right)
        self.progress.grid(row=7, column=0, sticky="ew", padx=8, pady=(4, 8))
        self.progress.set(0)

        self.counters_label = ctk.CTkLabel(right, text="Enviados: 0 | Falhas: 0 | Restantes: 0")
        self.counters_label.grid(row=8, column=0, sticky="w", padx=8, pady=(0, 8))

        ctk.CTkLabel(right, text="Log em tempo real").grid(row=9, column=0, sticky="w", padx=8, pady=(8, 2))
        self.log_box = ctk.CTkTextbox(right, height=280)
        self.log_box.grid(row=10, column=0, sticky="nsew", padx=8, pady=(0, 8))

        self.subject_entry.bind("<KeyRelease>", lambda _e: self.update_placeholders())
        self.body_text.bind("<KeyRelease>", lambda _e: self.update_placeholders())

    def _section_title(self, parent, text, row):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(10, 4)
        )

    def _entry(self, parent, label, key, row, show=None):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        self.vars[key] = ctk.StringVar()
        entry = ctk.CTkEntry(parent, textvariable=self.vars[key], show=show)
        entry.grid(row=row, column=1, sticky="ew", padx=8, pady=4)

    def _load_cfg_to_ui(self):
        for key, value in asdict(self.cfg).items():
            if key in {"subject", "body_html"}:
                continue
            self.vars[key].set(str(value))
        self.subject_entry.delete(0, "end")
        self.subject_entry.insert(0, self.cfg.subject)
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", self.cfg.body_html)
        self.update_placeholders()

    def _read_ui_cfg(self) -> CampaignConfig:
        cfg = CampaignConfig(
            smtp_host=self.vars["smtp_host"].get().strip(),
            smtp_port=int(self.vars["smtp_port"].get().strip() or 465),
            email=self.vars["email"].get().strip(),
            password=self.vars["password"].get(),
            imap_host=self.vars["imap_host"].get().strip(),
            imap_port=int(self.vars["imap_port"].get().strip() or 993),
            subject=self.subject_entry.get().strip(),
            body_html=self.body_text.get("1.0", "end").rstrip(),
            delay_min=float(self.vars["delay_min"].get().strip() or 0),
            delay_max=float(self.vars["delay_max"].get().strip() or 0),
            long_pause_seconds=int(self.vars["long_pause_seconds"].get().strip() or 0),
            long_pause_every=max(1, int(self.vars["long_pause_every"].get().strip() or 25)),
            max_per_campaign=min(MAX_ALLOWED_PER_CAMPAIGN, max(1, int(self.vars["max_per_campaign"].get().strip() or 100))),
        )
        if cfg.delay_max < cfg.delay_min:
            raise RuntimeError("Delay máximo precisa ser maior ou igual ao mínimo.")
        if not cfg.subject:
            raise RuntimeError("Informe um assunto.")
        if not cfg.body_html:
            raise RuntimeError("Informe o corpo HTML do e-mail.")
        return cfg

    def update_placeholders(self):
        placeholders = sorted(extract_placeholders(self.subject_entry.get()) | extract_placeholders(self.body_text.get("1.0", "end")))
        text = ", ".join("{" + p + "}" for p in placeholders) if placeholders else "-"
        self.placeholder_label.configure(text=f"Placeholders: {text}")

    def wrap_selection(self, open_tag: str, close_tag: str):
        try:
            start = self.body_text.index("sel.first")
            end = self.body_text.index("sel.last")
            selected = self.body_text.get(start, end)
            self.body_text.delete(start, end)
            self.body_text.insert(start, f"{open_tag}{selected}{close_tag}")
        except Exception:
            self.insert_at_cursor(f"{open_tag}{close_tag}")

    def insert_list_block(self):
        block = "<ul>\n  <li>Item 1</li>\n  <li>Item 2</li>\n</ul>\n"
        self.insert_at_cursor(block)

    def insert_at_cursor(self, text: str):
        self.body_text.insert("insert", text)

    def validate_grid(self):
        try:
            leads = parse_pasted_grid(self.grid_text.get("1.0", "end"))
            self.log(f"Planilha válida com {len(leads)} linha(s).")
        except Exception as exc:
            messagebox.showerror("Planilha inválida", str(exc))

    def save_config(self):
        cfg = self._read_ui_cfg()
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(asdict(cfg), f, indent=2, ensure_ascii=False)

    def load_config(self) -> CampaignConfig:
        if CONFIG_PATH.exists():
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            defaults = asdict(CampaignConfig())
            defaults.update(data)
            return CampaignConfig(**defaults)
        return CampaignConfig()

    def save_checkpoint(self, payload: dict[str, Any]):
        with CHECKPOINT_PATH.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def write_log_file(self, text: str):
        with TEXT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(text + "\n")

    def log(self, text: str):
        stamped = f"[{now_iso()}] {text}"
        self.log_queue.put(stamped)
        self.write_log_file(stamped)

    def _drain_log_queue(self):
        while not self.log_queue.empty():
            line = self.log_queue.get_nowait()
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")
        self.after(200, self._drain_log_queue)

    def _validate_before_actions(self) -> CampaignConfig | None:
        try:
            cfg = self._read_ui_cfg()
            self.save_config()
            return cfg
        except Exception as exc:
            messagebox.showerror("Erro de validação", str(exc))
            return None

    def test_smtp(self):
        cfg = self._validate_before_actions()
        if not cfg:
            return

        def _run():
            try:
                client = SmtpImapClient(cfg)
                client.start()
                client.login()
                client.stop()
                self.log("Teste SMTP: sucesso")
            except Exception as exc:
                self.log(f"Teste SMTP: falha -> {exc}")

        threading.Thread(target=_run, daemon=True).start()

    def test_imap(self):
        cfg = self._validate_before_actions()
        if not cfg:
            return

        def _run():
            try:
                client = SmtpImapClient(cfg)
                client.test_imap()
                self.log("Teste IMAP: sucesso")
            except Exception as exc:
                self.log(f"Teste IMAP: falha -> {exc}")

        threading.Thread(target=_run, daemon=True).start()

    def _set_counters(self, sent: int, fail: int, remaining: int):
        self.sent_count = sent
        self.fail_count = fail
        self.remaining_count = remaining
        self.counters_label.configure(text=f"Enviados: {sent} | Falhas: {fail} | Restantes: {remaining}")

    def start_campaign(self):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Campanha em execução", "Já existe uma campanha em andamento.")
            return

        cfg = self._validate_before_actions()
        if not cfg:
            return

        try:
            leads = parse_pasted_grid(self.grid_text.get("1.0", "end"))
        except Exception as exc:
            messagebox.showerror("Planilha inválida", str(exc))
            return

        self.stop_event.clear()
        self.pause_event.clear()
        self.progress.set(0)
        self._set_counters(0, 0, 0)
        self.worker_thread = threading.Thread(target=self._campaign_worker, args=(cfg, leads), daemon=True)
        self.worker_thread.start()

    def toggle_pause(self):
        if not self.worker_thread or not self.worker_thread.is_alive():
            self.log("Nenhuma campanha ativa para pausar/retomar.")
            return
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.log("Campanha retomada.")
        else:
            self.pause_event.set()
            self.log("Campanha pausada.")

    def stop_campaign(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_event.set()
            self.log("Solicitação de parada recebida. Finalizando envio atual...")
        else:
            self.log("Nenhuma campanha ativa para parar.")

    def _sleep_with_controls(self, seconds: float):
        start = time.time()
        while (time.time() - start) < seconds:
            if self.stop_event.is_set():
                return
            while self.pause_event.is_set() and not self.stop_event.is_set():
                time.sleep(0.2)
            time.sleep(0.2)

    def _campaign_worker(self, cfg: CampaignConfig, leads: list[dict[str, str]]):
        try:
            pending = [r for r in leads if r.get("__email")]
            pending = pending[: cfg.max_per_campaign]
            total = len(pending)
            if total == 0:
                self.log("Nenhum destinatário válido na planilha colada.")
                return

            self._set_counters(0, 0, total)
            self.log(f"Campanha iniciada com {total} destinatário(s).")

            sent = 0
            fail = 0
            client = SmtpImapClient(cfg)
            client.start()
            client.login()

            for idx, row in enumerate(pending, start=1):
                if self.stop_event.is_set():
                    self.log("Campanha interrompida pelo usuário.")
                    break

                while self.pause_event.is_set() and not self.stop_event.is_set():
                    time.sleep(0.2)

                recipient = row.get("__email", "").strip()
                subject = render_template(cfg.subject, row)
                body_html = render_template(cfg.body_html, row)
                ts = now_iso()

                try:
                    client.send_email(recipient, subject, body_html)
                    row["status"] = "enviado"
                    row["erro"] = ""
                    row["enviado_em"] = ts
                    sent += 1
                    self.log(f"{idx}/{total} enviado para {recipient}")
                except Exception as exc:
                    row["status"] = "erro"
                    row["erro"] = str(exc)
                    row["enviado_em"] = ts
                    fail += 1
                    self.log(f"{idx}/{total} falha para {recipient}: {exc}")

                remaining = max(0, total - (sent + fail))
                self._set_counters(sent, fail, remaining)
                self.progress.set((sent + fail) / total)
                self.save_checkpoint(
                    {
                        "timestamp": now_iso(),
                        "sent": sent,
                        "fail": fail,
                        "processed": sent + fail,
                        "total": total,
                        "stopped": self.stop_event.is_set(),
                    }
                )

                if self.stop_event.is_set() or (sent + fail) >= total:
                    continue

                if (sent + fail) % cfg.long_pause_every == 0:
                    self.log(
                        f"Pausa longa automática iniciada por {cfg.long_pause_seconds}s "
                        f"(bloco de {cfg.long_pause_every} e-mails)."
                    )
                    self._sleep_with_controls(cfg.long_pause_seconds)
                else:
                    delay = random.uniform(cfg.delay_min, cfg.delay_max)
                    self.log(f"Aguardando {delay:.1f}s antes do próximo envio.")
                    self._sleep_with_controls(delay)

            client.stop()
            self.log(f"Campanha finalizada. Enviados={sent}, falhas={fail}.")
        except Exception as exc:
            self.log(f"Erro fatal na campanha: {exc}")


def main():
    app = DesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
