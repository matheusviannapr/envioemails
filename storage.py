"""Persistência de logs (CSV em memória e SQLite opcional)."""

import csv
import io
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

DEFAULT_LOG_FILE = "campaign_logs.csv"


def init_db(db_path: str) -> None:
    """Inicializa tabela de histórico de campanha."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS campaign_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                processed_at TEXT NOT NULL,
                row_index INTEGER,
                recipient TEXT,
                subject TEXT,
                status TEXT,
                error_message TEXT,
                simulated INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()


def save_log_sqlite(db_path: str, log_row: Dict) -> None:
    """Salva um registro de log no SQLite."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO campaign_logs (
                processed_at, row_index, recipient, subject, status, error_message, simulated
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_row.get("processed_at", datetime.utcnow().isoformat()),
                log_row.get("row_index"),
                log_row.get("recipient"),
                log_row.get("subject"),
                log_row.get("status"),
                log_row.get("error_message"),
                1 if log_row.get("simulated") else 0,
            ),
        )
        conn.commit()


def append_log_rows(log_rows: List[Dict], log_file: str = DEFAULT_LOG_FILE) -> None:
    """Anexa logs em CSV local para trilha simples de execução."""
    if not log_rows:
        return

    fieldnames = [
        "processed_at",
        "row_index",
        "recipient",
        "subject",
        "status",
        "error_message",
        "simulated",
    ]

    try:
        with open(log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if f.tell() == 0:
                writer.writeheader()
            for row in log_rows:
                writer.writerow({k: row.get(k, "") for k in fieldnames})
    except Exception:
        # Não quebrar execução principal por falha de escrita de log local
        return


def download_log_csv(log_rows: List[Dict]) -> str:
    """Gera CSV em memória para download no Streamlit."""
    output = io.StringIO()
    if not log_rows:
        return ""

    fieldnames = list(log_rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(log_rows)
    return output.getvalue()
