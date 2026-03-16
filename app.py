import io
import os
import random
import time
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from mailer import build_smtp_client, send_email
from storage import append_log_rows, download_log_csv, init_db
from templates import render_template
from utils import (
    STATUS_PENDING_VALUES,
    build_template_preview,
    get_available_placeholders,
    load_csv,
    process_campaign,
    validate_campaign_inputs,
)

load_dotenv()

st.set_page_config(page_title="Titan Mail Merge", layout="wide")
st.title("📧 Titan Mail Merge (Uso autorizado)")
st.caption(
    "Envio SMTP com controle operacional, sem automação de navegador e sem técnicas de evasão."
)

# Estado para armazenar dataframe processado e logs
if "df_result" not in st.session_state:
    st.session_state.df_result = None
if "log_rows" not in st.session_state:
    st.session_state.log_rows = []

with st.sidebar:
    st.header("Configurações SMTP")
    smtp_host = st.text_input("Host", value=os.getenv("SMTP_HOST", "smtp.titan.email"))
    smtp_port = st.number_input("Porta", min_value=1, max_value=65535, value=int(os.getenv("SMTP_PORT", "465")))
    smtp_sender = st.text_input("E-mail remetente (SMTP_USER)", value=os.getenv("SMTP_USER", ""))
    smtp_password = st.text_input("Senha (SMTP_PASSWORD)", type="password", value=os.getenv("SMTP_PASSWORD", ""))

    st.header("Parâmetros da campanha")
    max_per_run = st.number_input("Máximo por execução", min_value=1, max_value=30, value=30)
    min_interval = st.number_input("Intervalo mínimo (s)", min_value=0.0, value=1.0, step=0.5)
    max_interval = st.number_input("Intervalo máximo (s)", min_value=0.0, value=2.0, step=0.5)
    persist_sqlite = st.checkbox("Persistir histórico em SQLite", value=True)
    sqlite_path = st.text_input("Arquivo SQLite", value="campaign_history.db")

    st.markdown("---")
    st.caption(
        "Use variáveis de ambiente em produção. Os campos acima são para execução local controlada."
    )

uploaded_file = st.file_uploader("Upload do CSV", type=["csv"])

if uploaded_file:
    try:
        df = load_csv(uploaded_file)
    except Exception as exc:
        st.error(f"Erro ao carregar CSV: {exc}")
        st.stop()

    st.subheader("Prévia do CSV")
    st.dataframe(df.head(20), use_container_width=True)

    if df.empty:
        st.warning("O CSV está vazio.")
        st.stop()

    email_col = st.selectbox("Coluna de e-mail", options=list(df.columns))

    st.subheader("Template")
    placeholders = get_available_placeholders(df)
    st.caption(f"Placeholders disponíveis: {', '.join(placeholders) if placeholders else 'Nenhum'}")

    subject_template = st.text_input("Assunto", value="Pergunta rápida para {{empresa}}")
    body_template = st.text_area(
        "Corpo",
        value=(
            "Olá {{nome}},\n\n"
            "Sou Matheus Vianna, da PACE Inteligência Energética.\n\n"
            "Gostaria de entender se o custo de energia é um tema relevante hoje para a {{empresa}}.\n\n"
            "Abraço,\n"
            "Matheus Vianna"
        ),
        height=220,
    )

    preview_idx = st.number_input(
        "Linha para prévia (índice)", min_value=0, max_value=len(df) - 1, value=0
    )
    preview_data = df.iloc[int(preview_idx)].to_dict()
    rendered_subject, rendered_body = build_template_preview(
        subject_template, body_template, preview_data
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Prévia do assunto**")
        st.code(rendered_subject)
    with c2:
        st.markdown("**Prévia do corpo**")
        st.code(rendered_body)

    st.markdown("---")
    st.subheader("Validação / Teste")

    test_email = st.text_input("E-mail para envio de teste")
    simulate_mode = st.checkbox("Simular campanha (não envia)", value=False)

    if st.button("Enviar teste", type="secondary"):
        is_valid, errors = validate_campaign_inputs(
            df=df,
            email_col=email_col,
            subject_template=subject_template,
            body_template=body_template,
            smtp_user=smtp_sender,
            smtp_password=smtp_password,
            max_per_run=int(max_per_run),
            min_interval=float(min_interval),
            max_interval=float(max_interval),
        )
        if not test_email:
            errors.append("Informe o e-mail de teste.")

        if not is_valid or errors:
            for err in errors:
                st.error(err)
        else:
            try:
                subject = render_template(subject_template, preview_data)
                body = render_template(body_template, preview_data)
                send_email(
                    host=smtp_host,
                    port=int(smtp_port),
                    username=smtp_sender,
                    password=smtp_password,
                    sender=smtp_sender,
                    recipient=test_email,
                    subject=subject,
                    body=body,
                )
                st.success(f"Teste enviado para {test_email}.")
            except Exception as exc:
                st.error(f"Falha no envio de teste: {exc}")

    if st.button("Executar campanha", type="primary"):
        is_valid, errors = validate_campaign_inputs(
            df=df,
            email_col=email_col,
            subject_template=subject_template,
            body_template=body_template,
            smtp_user=smtp_sender,
            smtp_password=smtp_password,
            max_per_run=int(max_per_run),
            min_interval=float(min_interval),
            max_interval=float(max_interval),
        )

        if not is_valid:
            for err in errors:
                st.error(err)
            st.stop()

        if persist_sqlite:
            init_db(sqlite_path)

        progress = st.progress(0)
        status_text = st.empty()

        smtp_client_factory = None
        if not simulate_mode:
            smtp_client_factory = lambda: build_smtp_client(
                host=smtp_host,
                port=int(smtp_port),
                username=smtp_sender,
                password=smtp_password,
            )

        def on_progress(done: int, total: int):
            pct = int((done / total) * 100) if total else 100
            progress.progress(min(pct, 100))
            status_text.info(f"Processando: {done}/{total}")

        result_df, log_rows = process_campaign(
            df=df,
            email_col=email_col,
            subject_template=subject_template,
            body_template=body_template,
            sender_email=smtp_sender,
            smtp_send_callable=send_email,
            smtp_client_factory=smtp_client_factory,
            max_per_run=int(max_per_run),
            min_interval=float(min_interval),
            max_interval=float(max_interval),
            simulate=simulate_mode,
            progress_callback=on_progress,
            sleep_callable=time.sleep,
            random_callable=random.uniform,
            sqlite_path=sqlite_path if persist_sqlite else None,
        )

        st.session_state.df_result = result_df
        st.session_state.log_rows = log_rows
        append_log_rows(log_rows)

        progress.progress(100)
        status_text.success("Campanha finalizada.")

if st.session_state.df_result is not None:
    st.subheader("Resultado da execução")
    st.dataframe(st.session_state.df_result, use_container_width=True)

    csv_buffer = io.StringIO()
    st.session_state.df_result.to_csv(csv_buffer, index=False)

    st.download_button(
        label="Baixar CSV atualizado",
        data=csv_buffer.getvalue(),
        file_name=f"campanha_resultado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )

if st.session_state.log_rows:
    st.subheader("Logs")
    st.dataframe(pd.DataFrame(st.session_state.log_rows), use_container_width=True)

    st.download_button(
        label="Baixar log CSV",
        data=download_log_csv(st.session_state.log_rows),
        file_name=f"log_envio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )

st.caption(
    f"Status considerados pendentes para envio: {', '.join(sorted(STATUS_PENDING_VALUES))}"
)
