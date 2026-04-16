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
from tkinter import filedialog, messagebox
from tkinter import ttk
import tkinter as tk
from typing import Any

import customtkinter as ctk


APP_TITLE = "Email Campaign Desktop"
CONFIG_PATH = Path("desktop_config.json")
CHECKPOINT_PATH = Path("desktop_checkpoint.json")
TEXT_LOG_PATH = Path("desktop_campaign.log")
MAX_ALLOWED_PER_CAMPAIGN = 100


@dataclass
class CampaignConfig:
    smtp_host: str = "smtpout.secureserver.net"
    smtp_port: int = 465
    email: str = ""
    password: str = ""
    imap_host: str = "imap.secureserver.net"
    imap_port: int = 993
    csv_path: str = ""
    subject: str = "Olá {nome}, proposta para {empresa}"
    body_text: str = "Olá {nome},\n\nTudo bem?"
    delay_min: float = 6.0
    delay_max: float = 9.0
    long_pause_seconds: int = 90
    long_pause_every: int = 25
    max_per_campaign: int = 100


class SmtpImapClient:
    def __init__(self, cfg: CampaignConfig, logger=None):
        self.cfg = cfg
        self.server: smtplib.SMTP | smtplib.SMTP_SSL | None = None
        self.logger = logger

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

    def _decode_folder_line(self, raw_line) -> str:
        if isinstance(raw_line, bytes):
            return raw_line.decode("utf-8", errors="ignore")
        return str(raw_line)

    def _resolve_sent_folder(self, imap: imaplib.IMAP4_SSL) -> str | None:
        candidates = ["Sent", "Sent Items", "Enviados", "Itens Enviados"]
        status, folders = imap.list()
        if status != "OK" or not folders:
            return None

        parsed = [self._decode_folder_line(line) for line in folders]

        for candidate in candidates:
            for line in parsed:
                if candidate.lower() in line.lower():
                    if '"' in line:
                        parts = line.split('"')
                        if len(parts) >= 3 and parts[-2].strip():
                            return parts[-2].strip()
                    fallback = line.rsplit(" ", 1)[-1].strip()
                    return fallback.strip('"')
        return None

    def _save_to_sent(self, msg_bytes: bytes) -> bool:
        # Alguns provedores falham no primeiro APPEND após autenticação.
        # Fazemos 2 tentativas para reduzir perda do primeiro envio na pasta Enviados.
        for _ in range(2):
            with imaplib.IMAP4_SSL(self.cfg.imap_host, self.cfg.imap_port) as imap:
                imap.login(self.cfg.email, self.cfg.password)
                sent_folder = self._resolve_sent_folder(imap)
                if not sent_folder:
                    return False
                status, _ = imap.append(
                    sent_folder,
                    r"\Seen",
                    imaplib.Time2Internaldate(time.time()),
                    msg_bytes,
                )
                if status == "OK":
                    return True
            time.sleep(0.5)
        return False

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
        try:
            self._save_to_sent(msg.as_bytes())
        except Exception:
            pass


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


def markdownish_text_to_html(text: str) -> str:
    """Converte editor de texto simples para HTML leve.

    Regras:
    - **texto** => <strong>
    - *texto* => <em>
    - linhas iniciando com '- ' => lista <ul><li>
    - demais linhas => <p>
    """
    escaped = html.escape(text.strip())

    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)

    lines = escaped.splitlines()
    chunks: list[str] = []
    in_list = False

    for line in lines:
        clean = line.strip()
        if not clean:
            if in_list:
                chunks.append("</ul>")
                in_list = False
            continue

        if clean.startswith("- "):
            if not in_list:
                chunks.append("<ul>")
                in_list = True
            chunks.append(f"<li>{clean[2:].strip()}</li>")
        else:
            if in_list:
                chunks.append("</ul>")
                in_list = False
            chunks.append(f"<p>{clean}</p>")

    if in_list:
        chunks.append("</ul>")

    if not chunks:
        return "<p>Mensagem vazia</p>"
    return "\n".join(chunks)


class DesktopApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        self.title(APP_TITLE)
        self.geometry("1360x920")

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()
        self.worker_thread: threading.Thread | None = None

        self.sent_count = 0
        self.fail_count = 0
        self.remaining_count = 0

        self.cfg = self.load_config()
        self.vars: dict[str, ctk.StringVar] = {}

        self.table_columns: list[str] = []
        self.table_rows: list[dict[str, str]] = []
        self._cell_editor = None

        self._build_ui()
        self._load_cfg_to_ui()
        self.after(200, self._drain_log_queue)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        container = ctk.CTkFrame(self)
        container.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        container.grid_columnconfigure((0, 1), weight=1)
        container.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(container)
        right = ctk.CTkFrame(container)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        left.grid_columnconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # SMTP/IMAP
        self._section_title(left, "Configuração SMTP/IMAP", 0)
        self._entry(left, "SMTP host", "smtp_host", 1)
        self._entry(left, "SMTP porta", "smtp_port", 2)
        self._entry(left, "E-mail", "email", 3)
        self._entry(left, "Senha", "password", 4, show="*")
        self._entry(left, "IMAP host", "imap_host", 5)
        self._entry(left, "IMAP porta", "imap_port", 6)

        ctk.CTkButton(left, text="Testar SMTP", command=self.test_smtp).grid(row=7, column=0, padx=8, pady=6, sticky="ew")
        ctk.CTkButton(left, text="Testar IMAP", command=self.test_imap).grid(row=7, column=1, padx=8, pady=6, sticky="ew")

        # regras campanha
        self._section_title(left, "Regras da campanha", 8)
        self._entry(left, "Delay mínimo (s)", "delay_min", 9)
        self._entry(left, "Delay máximo (s)", "delay_max", 10)
        self._entry(left, "Pausa longa (s)", "long_pause_seconds", 11)
        self._entry(left, "A cada X envios", "long_pause_every", 12)
        self._entry(left, "Máx. e-mails na campanha", "max_per_campaign", 13)

        # CSV editable spreadsheet
        self._section_title(left, "CSV como planilha editável", 14)
        self._entry(left, "Arquivo CSV", "csv_path", 15)
        ctk.CTkButton(left, text="Carregar CSV", command=self.load_csv_into_table).grid(row=16, column=0, padx=8, pady=6, sticky="ew")
        ctk.CTkButton(left, text="Adicionar linha vazia", command=self.add_empty_row).grid(row=16, column=1, padx=8, pady=6, sticky="ew")

        table_frame = ctk.CTkFrame(left)
        table_frame.grid(row=17, column=0, columnspan=2, sticky="nsew", padx=8, pady=(4, 8))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_frame, show="headings", height=14)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.bind("<Double-1>", self._start_cell_edit)
        self.tree.bind("<Button-1>", self._commit_cell_edit_if_open, add="+")
        self.tree.bind("<Control-v>", self._paste_from_clipboard_event)
        self.tree.bind("<Command-v>", self._paste_from_clipboard_event)

        ctk.CTkLabel(left, text="Dica: dê duplo clique em uma célula para editar.").grid(
            row=18, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8)
        )
        ctk.CTkButton(left, text="Colar planilha (Ctrl+V)", command=self.paste_from_clipboard).grid(
            row=19, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew"
        )

        # Editor de corpo (texto) + conversão HTML
        self._section_title(right, "Mensagem (editor texto => envio em HTML)", 0)
        subject_row = ctk.CTkFrame(right)
        subject_row.grid(row=1, column=0, sticky="ew", padx=8, pady=(8, 2))
        subject_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(subject_row, text="Assunto").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.subject_entry = ctk.CTkEntry(subject_row)
        self.subject_entry.grid(row=0, column=1, sticky="ew")

        toolbar = ctk.CTkFrame(right)
        toolbar.grid(row=2, column=0, sticky="ew", padx=8, pady=(6, 4))
        toolbar.grid_columnconfigure((0, 1, 2, 3), weight=1)
        ctk.CTkButton(toolbar, text="Negrito", command=lambda: self.wrap_with("**", "**")).grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        ctk.CTkButton(toolbar, text="Itálico", command=lambda: self.wrap_with("*", "*")).grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        ctk.CTkButton(toolbar, text="Bullet", command=lambda: self.insert_at_cursor("- ")).grid(row=0, column=2, padx=4, pady=4, sticky="ew")
        ctk.CTkButton(toolbar, text="Novo parágrafo", command=lambda: self.insert_at_cursor("\n\n")).grid(row=0, column=3, padx=4, pady=4, sticky="ew")

        ctk.CTkLabel(right, text="Corpo (texto normal):").grid(row=3, column=0, sticky="w", padx=8, pady=(4, 2))
        self.body_text = ctk.CTkTextbox(right, height=180)
        self.body_text.grid(row=4, column=0, sticky="ew", padx=8, pady=(0, 6))

        preview_buttons = ctk.CTkFrame(right)
        preview_buttons.grid(row=5, column=0, sticky="ew", padx=8, pady=(0, 6))
        preview_buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(preview_buttons, text="Atualizar preview HTML", command=self.refresh_html_preview).grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        ctk.CTkButton(preview_buttons, text="Validar placeholders", command=self.update_placeholders).grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        self.placeholder_label = ctk.CTkLabel(right, text="Placeholders: -")
        self.placeholder_label.grid(row=6, column=0, sticky="w", padx=8, pady=(0, 4))

        ctk.CTkLabel(right, text="Preview HTML que será enviado:").grid(row=7, column=0, sticky="w", padx=8)
        self.html_preview = ctk.CTkTextbox(right, height=150)
        self.html_preview.grid(row=8, column=0, sticky="ew", padx=8, pady=(2, 8))

        control = ctk.CTkFrame(right)
        control.grid(row=9, column=0, sticky="ew", padx=8, pady=6)
        control.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkButton(control, text="Iniciar campanha", command=self.start_campaign).grid(row=0, column=0, padx=4, pady=6, sticky="ew")
        ctk.CTkButton(control, text="Pausar/Retomar", command=self.toggle_pause).grid(row=0, column=1, padx=4, pady=6, sticky="ew")
        ctk.CTkButton(control, text="Parar", command=self.stop_campaign).grid(row=0, column=2, padx=4, pady=6, sticky="ew")

        self.progress = ctk.CTkProgressBar(right)
        self.progress.grid(row=10, column=0, sticky="ew", padx=8, pady=(2, 6))
        self.progress.set(0)

        self.counters_label = ctk.CTkLabel(right, text="Enviados: 0 | Falhas: 0 | Restantes: 0")
        self.counters_label.grid(row=11, column=0, sticky="w", padx=8, pady=(0, 6))

        ctk.CTkLabel(right, text="Log em tempo real").grid(row=12, column=0, sticky="w", padx=8)
        self.log_box = ctk.CTkTextbox(right, height=220)
        self.log_box.grid(row=13, column=0, sticky="nsew", padx=8, pady=(2, 8))

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
            if key in {"subject", "body_text"}:
                continue
            if key in self.vars:
                self.vars[key].set(str(value))
        self.subject_entry.delete(0, "end")
        self.subject_entry.insert(0, self.cfg.subject)
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", self.cfg.body_text)
        self.refresh_html_preview()
        self.update_placeholders()

    def _read_ui_cfg(self) -> CampaignConfig:
        cfg = CampaignConfig(
            smtp_host=self.vars["smtp_host"].get().strip(),
            smtp_port=int(self.vars["smtp_port"].get().strip() or 465),
            email=self.vars["email"].get().strip(),
            password=self.vars["password"].get(),
            imap_host=self.vars["imap_host"].get().strip(),
            imap_port=int(self.vars["imap_port"].get().strip() or 993),
            csv_path=self.vars["csv_path"].get().strip(),
            subject=self.subject_entry.get().strip(),
            body_text=self.body_text.get("1.0", "end").rstrip(),
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
        if not cfg.body_text:
            raise RuntimeError("Informe o corpo do e-mail.")
        return cfg

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

    def update_placeholders(self):
        placeholders = sorted(
            extract_placeholders(self.subject_entry.get())
            | extract_placeholders(self.body_text.get("1.0", "end"))
        )
        text = ", ".join("{" + p + "}" for p in placeholders) if placeholders else "-"
        self.placeholder_label.configure(text=f"Placeholders: {text}")

    def wrap_with(self, prefix: str, suffix: str):
        try:
            start = self.body_text.index("sel.first")
            end = self.body_text.index("sel.last")
            selected = self.body_text.get(start, end)
            self.body_text.delete(start, end)
            self.body_text.insert(start, f"{prefix}{selected}{suffix}")
        except Exception:
            self.body_text.insert("insert", f"{prefix}{suffix}")
        self.refresh_html_preview()

    def insert_at_cursor(self, text: str):
        self.body_text.insert("insert", text)
        self.refresh_html_preview()

    def refresh_html_preview(self):
        html_body = markdownish_text_to_html(self.body_text.get("1.0", "end"))
        self.html_preview.delete("1.0", "end")
        self.html_preview.insert("1.0", html_body)

    # ---- spreadsheet/csv ----
    def load_csv_into_table(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        self.vars["csv_path"].set(path)

        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise RuntimeError("CSV sem cabeçalho")
            self.table_columns = [c.strip() for c in reader.fieldnames if c]
            self.table_rows = []
            for row in reader:
                cleaned = {col: (row.get(col) or "").strip() for col in self.table_columns}
                self.table_rows.append(cleaned)

        if "email" not in [c.lower() for c in self.table_columns]:
            messagebox.showwarning("CSV", "A planilha não tem coluna 'email'.")

        self._render_table()
        self.log(f"CSV carregado com {len(self.table_rows)} linha(s).")

    def _render_table(self):
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = self.table_columns
        for col in self.table_columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=140, minwidth=100, stretch=True)

        for i, row in enumerate(self.table_rows):
            values = [row.get(col, "") for col in self.table_columns]
            self.tree.insert("", "end", iid=str(i), values=values)

    def _paste_from_clipboard_event(self, _event):
        self.paste_from_clipboard()
        return "break"

    def _parse_clipboard_grid(self) -> list[list[str]]:
        raw = self.clipboard_get()
        lines = [line for line in raw.splitlines() if line.strip() != ""]
        if not lines:
            raise RuntimeError("Área de transferência vazia.")
        return [line.split("\t") for line in lines]

    def paste_from_clipboard(self):
        try:
            grid = self._parse_clipboard_grid()
        except Exception as exc:
            messagebox.showerror("Colar planilha", f"Não foi possível colar: {exc}")
            return

        # Sem tabela carregada: assume primeira linha como cabeçalho.
        if not self.table_columns:
            headers = [cell.strip() or f"col_{i+1}" for i, cell in enumerate(grid[0])]
            self.table_columns = headers
            self.table_rows = []
            for row in grid[1:]:
                record = {col: "" for col in self.table_columns}
                for col_idx, col_name in enumerate(self.table_columns):
                    if col_idx < len(row):
                        record[col_name] = row[col_idx].strip()
                self.table_rows.append(record)
            self._render_table()
            self.log(f"Planilha colada com {len(self.table_rows)} linha(s).")
            return

        # Tabela existente: cola bloco a partir da célula selecionada.
        selected = self.tree.focus() or (self.tree.get_children()[0] if self.tree.get_children() else None)
        if selected is None:
            self.add_empty_row()
            selected = self.tree.get_children()[0]

        start_row = self.tree.index(selected)
        start_col = 0

        # tenta detectar coluna do clique atual se existir editor aberto
        if self._cell_editor and self._cell_editor.get("col_index") is not None:
            start_col = int(self._cell_editor["col_index"])

        needed_rows = start_row + len(grid)
        while len(self.table_rows) < needed_rows:
            self.table_rows.append({col: "" for col in self.table_columns})

        for r, row_vals in enumerate(grid):
            row_idx = start_row + r
            for c, value in enumerate(row_vals):
                col_idx = start_col + c
                if col_idx >= len(self.table_columns):
                    break
                col_name = self.table_columns[col_idx]
                self.table_rows[row_idx][col_name] = value.strip()

        self._render_table()
        self.log(f"Bloco colado na planilha: {len(grid)}x{max(len(r) for r in grid)} célula(s).")

    def _start_cell_edit(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or not col_id:
            return

        col_index = int(col_id.replace("#", "")) - 1
        if col_index < 0 or col_index >= len(self.table_columns):
            return

        bbox = self.tree.bbox(row_id, col_id)
        if not bbox:
            return
        x, y, width, height = bbox

        self._commit_cell_edit_if_open()

        value = self.tree.set(row_id, self.table_columns[col_index])
        editor = tk.Entry(self.tree)
        editor.insert(0, value)
        editor.select_range(0, "end")
        editor.focus_set()
        editor.place(in_=self.tree, x=x, y=y, width=width, height=height)

        self._cell_editor = {
            "widget": editor,
            "row_id": row_id,
            "col_index": col_index,
        }

        editor.bind("<Return>", lambda _e: self._commit_cell_edit_if_open())
        editor.bind("<Escape>", lambda _e: self._cancel_cell_edit())
        editor.bind("<FocusOut>", lambda _e: self._commit_cell_edit_if_open())

    def _cancel_cell_edit(self):
        if not self._cell_editor:
            return
        widget = self._cell_editor.get("widget")
        if widget:
            widget.destroy()
        self._cell_editor = None

    def _commit_cell_edit_if_open(self, _event=None):
        if not self._cell_editor:
            return

        widget = self._cell_editor.get("widget")
        row_id = self._cell_editor.get("row_id")
        col_index = self._cell_editor.get("col_index")

        if not widget or row_id is None or col_index is None:
            self._cell_editor = None
            return

        new_val = widget.get().strip()
        col_name = self.table_columns[col_index]
        self.tree.set(row_id, col_name, new_val)

        row_idx = self.tree.index(row_id)
        if 0 <= row_idx < len(self.table_rows):
            self.table_rows[row_idx][col_name] = new_val

        widget.destroy()
        self._cell_editor = None

    def add_empty_row(self):
        if not self.table_columns:
            # início rápido para quem ainda não carregou CSV
            self.table_columns = ["email", "nome", "empresa"]
        row = {col: "" for col in self.table_columns}
        self.table_rows.append(row)
        self._render_table()

    def get_table_rows(self) -> list[dict[str, str]]:
        if not self.table_columns:
            raise RuntimeError("Carregue um CSV ou adicione colunas/linhas na planilha.")

        email_col = None
        for col in self.table_columns:
            if col.lower() == "email":
                email_col = col
                break
        if not email_col:
            raise RuntimeError("A planilha deve ter uma coluna chamada 'email'.")

        rows: list[dict[str, str]] = []
        for row in self.table_rows:
            normalized = {k: (v or "").strip() for k, v in row.items()}
            normalized["__email"] = normalized.get(email_col, "").strip()
            rows.append(normalized)
        return rows

    # ---- smtp/imap tests ----
    def test_smtp(self):
        cfg = self._validate_before_actions()
        if not cfg:
            return

        def _run():
            try:
                client = SmtpImapClient(cfg, logger=self.log)
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
                client = SmtpImapClient(cfg, logger=self.log)
                client.test_imap()
                self.log("Teste IMAP: sucesso")
            except Exception as exc:
                self.log(f"Teste IMAP: falha -> {exc}")

        threading.Thread(target=_run, daemon=True).start()

    # ---- campaign ----
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
            leads = self.get_table_rows()
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
                self.log("Nenhum destinatário válido na planilha.")
                return

            self._set_counters(0, 0, total)
            self.log(f"Campanha iniciada com {total} destinatário(s).")

            sent = 0
            fail = 0
            client = SmtpImapClient(cfg, logger=self.log)
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
                body_text = render_template(cfg.body_text, row)
                body_html = markdownish_text_to_html(body_text)
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
