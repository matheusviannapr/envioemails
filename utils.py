import csv
import io
import os
from datetime import datetime
from string import Formatter
from typing import Dict

import pandas as pd


LOG_COLUMNS = ["destinatario", "horario", "status", "erro"]
PENDING_VALUES = {"", "pendente", "pending", None}


def load_csv(file_obj) -> pd.DataFrame:
    df = pd.read_csv(file_obj)
    df.columns = [str(c).strip() for c in df.columns]
    for col in ["status", "erro", "enviado_em"]:
        if col not in df.columns:
            df[col] = ""
    return df


def extract_placeholders(template: str) -> set[str]:
    formatter = Formatter()
    return {field_name for _, field_name, _, _ in formatter.parse(template) if field_name}


def render_template(template: str, context: Dict) -> str:
    values = {k: "" if pd.isna(v) else str(v) for k, v in context.items()}
    return template.format_map(_SafeDict(values))


class _SafeDict(dict):
    def __missing__(self, key):
        return ""


def append_log(log_path: str, row: Dict):
    exists = os.path.exists(log_path)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in LOG_COLUMNS})


def read_log(log_path: str) -> pd.DataFrame:
    if not os.path.exists(log_path):
        return pd.DataFrame(columns=LOG_COLUMNS)
    return pd.read_csv(log_path)


def sent_recipients(log_path: str) -> set[str]:
    log_df = read_log(log_path)
    if log_df.empty:
        return set()
    ok_df = log_df[log_df["status"] == "enviado"]
    return {str(r).strip().lower() for r in ok_df["destinatario"].tolist()}


def is_pending(value) -> bool:
    return str(value).strip().lower() in PENDING_VALUES


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def to_csv_download(df: pd.DataFrame) -> str:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue()
