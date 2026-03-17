import random
import time
from typing import Callable

from config import CampaignConfig
from utils import append_log, is_pending, now_iso, render_template, sent_recipients


def run_campaign(
    df,
    email_col: str,
    subject_template: str,
    body_template: str,
    cfg: CampaignConfig,
    progress_callback: Callable[[int, int], None] | None = None,
    status_callback: Callable[[str], None] | None = None,
):
    sent_before = sent_recipients(cfg.log_path)
    pending = []

    for idx, row in df.iterrows():
        recipient = str(row.get(email_col, "")).strip().lower()
        if not recipient:
            continue
        if recipient in sent_before:
            continue
        if is_pending(row.get("status", "")):
            pending.append(idx)

    pending = pending[: cfg.max_per_run]
    total = len(pending)
    done = 0
    consecutive_errors = 0

    from titan_client import TitanClient

    client = TitanClient(
        base_url=cfg.titan_url,
        email=cfg.titan_email,
        password=cfg.titan_password,
        headless=cfg.headless,
        chromium_args=cfg.chromium_args,
    )

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
                screenshot = client.save_error_screenshot(cfg.screenshot_dir)
                df.at[idx, "status"] = "erro"
                df.at[idx, "erro"] = f"{exc} | screenshot={screenshot}"
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
