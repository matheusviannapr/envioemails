"""Utilitários de validação e processamento de campanha."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from storage import save_log_sqlite
from templates import render_template

STATUS_PENDING_VALUES = {"", "pendente", "pending", None}


class ValidationError(Exception):
    """Erro de validação de entradas da campanha."""


def load_csv(file_obj) -> pd.DataFrame:
    """Carrega CSV e normaliza colunas para string simples."""
    df = pd.read_csv(file_obj)
    df.columns = [str(c).strip() for c in df.columns]

    for col in ["status", "erro", "enviado_em"]:
        if col not in df.columns:
            df[col] = ""

    return df


def get_available_placeholders(df: pd.DataFrame) -> List[str]:
    """Retorna placeholders no padrão {{coluna}} com base no CSV."""
    return [f"{{{{{col}}}}}" for col in df.columns]


def build_template_preview(subject_template: str, body_template: str, row_data: Dict) -> Tuple[str, str]:
    """Renderiza assunto e corpo para pré-visualização."""
    return render_template(subject_template, row_data), render_template(body_template, row_data)


def validate_campaign_inputs(
    df: pd.DataFrame,
    email_col: str,
    subject_template: str,
    body_template: str,
    smtp_user: str,
    smtp_password: str,
    max_per_run: int,
    min_interval: float,
    max_interval: float,
) -> Tuple[bool, List[str]]:
    """Valida entradas críticas antes de enviar campanha."""
    errors = []

    if df is None or df.empty:
        errors.append("CSV vazio ou inválido.")

    if not email_col or email_col not in df.columns:
        errors.append("Coluna de e-mail inválida.")

    if not subject_template or not subject_template.strip():
        errors.append("Assunto não pode estar vazio.")

    if not body_template or not body_template.strip():
        errors.append("Corpo do e-mail não pode estar vazio.")

    if not smtp_user or not smtp_password:
        errors.append("Credenciais SMTP obrigatórias.")

    if max_per_run < 1 or max_per_run > 30:
        errors.append("Máximo por execução deve estar entre 1 e 30.")

    if min_interval < 0 or max_interval < 0 or min_interval > max_interval:
        errors.append("Intervalo inválido: mínimo deve ser <= máximo e ambos >= 0.")

    return len(errors) == 0, errors


def _is_pending_status(value) -> bool:
    if value is None:
        return True
    text = str(value).strip().lower()
    return text in STATUS_PENDING_VALUES


def process_campaign(
    df: pd.DataFrame,
    email_col: str,
    subject_template: str,
    body_template: str,
    sender_email: str,
    smtp_send_callable: Callable,
    smtp_client_factory: Optional[Callable],
    max_per_run: int,
    min_interval: float,
    max_interval: float,
    simulate: bool,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    sleep_callable: Optional[Callable[[float], None]] = None,
    random_callable: Optional[Callable[[float, float], float]] = None,
    sqlite_path: Optional[str] = None,
):
    """Processa campanha com controle de limite, status e logging."""
    working_df = df.copy()
    log_rows = []

    pending_indices = [
        idx for idx, row in working_df.iterrows() if _is_pending_status(row.get("status", ""))
    ]
    pending_indices = pending_indices[:max_per_run]

    total = len(pending_indices)
    done = 0

    smtp_client = None
    if not simulate and smtp_client_factory:
        smtp_client = smtp_client_factory()

    try:
        for idx in pending_indices:
            row = working_df.loc[idx].to_dict()
            recipient = str(row.get(email_col, "")).strip()
            subject = render_template(subject_template, row)
            body = render_template(body_template, row)
            processed_at = datetime.utcnow().isoformat()

            if not recipient or "@" not in recipient:
                status = "erro"
                error_message = "E-mail do destinatário inválido."
            else:
                try:
                    if simulate:
                        status = "ignorado"
                        error_message = "Simulação: envio não realizado."
                    else:
                        smtp_send_callable(
                            host="",
                            port=0,
                            username="",
                            password="",
                            sender=sender_email,
                            recipient=recipient,
                            subject=subject,
                            body=body,
                            smtp_client=smtp_client,
                        )
                        status = "enviado"
                        error_message = ""
                except Exception as exc:  # noqa: BLE001 - robustez operacional
                    status = "erro"
                    error_message = str(exc)

            working_df.at[idx, "status"] = status
            working_df.at[idx, "erro"] = error_message
            working_df.at[idx, "enviado_em"] = processed_at

            log_row = {
                "processed_at": processed_at,
                "row_index": int(idx),
                "recipient": recipient,
                "subject": subject,
                "status": status,
                "error_message": error_message,
                "simulated": simulate,
            }
            log_rows.append(log_row)

            if sqlite_path:
                save_log_sqlite(sqlite_path, log_row)

            done += 1
            if progress_callback:
                progress_callback(done, total)

            # Espera apenas entre itens quando não for o último.
            if done < total and sleep_callable and random_callable:
                interval = random_callable(min_interval, max_interval)
                sleep_callable(interval)

        # Registra como ignorados linhas fora do limite que também estavam pendentes.
        skipped_pending = [
            idx
            for idx in [
                i for i, row in working_df.iterrows() if _is_pending_status(row.get("status", ""))
            ]
            if idx not in pending_indices
        ]
        for idx in skipped_pending:
            if _is_pending_status(working_df.at[idx, "status"]):
                working_df.at[idx, "status"] = "ignorado"
                working_df.at[idx, "erro"] = "Fora do limite da execução atual."
    finally:
        if smtp_client is not None:
            try:
                smtp_client.quit()
            except Exception:
                pass

    return working_df, log_rows
