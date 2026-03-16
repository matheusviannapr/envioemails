import io
import random
import time
from datetime import datetime
from typing import List

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
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

if "df_result" not in st.session_state:
    st.session_state.df_result = None
if "log_rows" not in st.session_state:
    st.session_state.log_rows = []
if "manual_df" not in st.session_state:
    st.session_state.manual_df = pd.DataFrame(
        [
            {
                "email": "contato1@empresa.com",
                "campo_1": "João",
                "campo_2": "Empresa A",
                "campo_3": "Diagnóstico energético",
                "status": "",
                "erro": "",
                "enviado_em": "",
            },
            {
                "email": "contato2@empresa.com",
                "campo_1": "Maria",
                "campo_2": "Empresa B",
                "campo_3": "Eficiência operacional",
                "status": "pendente",
                "erro": "",
                "enviado_em": "",
            },
        ]
    )


def _read_secret(key: str) -> str:
    try:
        value = st.secrets[key]
    except StreamlitSecretNotFoundError:
        return ""
    except KeyError:
        return ""
    return str(value).strip()


with st.sidebar:
    st.header("Configurações SMTP")
    smtp_host = st.text_input("Host", value="smtp.titan.email", disabled=True)
    smtp_port = st.number_input("Porta", min_value=1, max_value=65535, value=587, disabled=True)

    email_user = _read_secret("email_user")
    email_password = _read_secret("email_password")

    smtp_sender = st.text_input("E-mail remetente (email_user)", value=email_user, disabled=True)
    smtp_password = st.text_input(
        "Senha (email_password)",
        type="password",
        value=("********" if email_password else ""),
        disabled=True,
    )

    if not email_user:
        st.error("Defina 'email_user' em st.secrets.")
    elif "@" not in email_user or email_user.count("@") != 1:
        st.error("'email_user' deve ser um endereço de e-mail completo.")

    if not email_password:
        st.error("Defina 'email_password' em st.secrets.")

    st.header("Parâmetros da campanha")
    max_per_run = st.number_input("Máximo por execução", min_value=1, max_value=30, value=30)
    min_interval = st.number_input("Intervalo mínimo (s)", min_value=0.0, value=1.0, step=0.5)
    max_interval = st.number_input("Intervalo máximo (s)", min_value=0.0, value=2.0, step=0.5)
    persist_sqlite = st.checkbox("Persistir histórico em SQLite", value=True)
    sqlite_path = st.text_input("Arquivo SQLite", value="campaign_history.db")

    st.markdown("---")
    st.caption("Credenciais lidas de st.secrets. Campos acima são apenas exibição.")


def _ensure_campaign_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Garante as colunas de controle no dataframe."""
    local = df.copy()
    for col in ["status", "erro", "enviado_em"]:
        if col not in local.columns:
            local[col] = ""
    return local


def _build_manual_dataframe(
    email_col_name: str,
    field_names: List[str],
    row_count: int,
    current_df: pd.DataFrame,
) -> pd.DataFrame:
    """Cria/ajusta dataframe manual preservando valores possíveis."""
    base_columns = [email_col_name] + field_names + ["status", "erro", "enviado_em"]

    if current_df is None or current_df.empty:
        return pd.DataFrame([{col: "" for col in base_columns} for _ in range(row_count)])

    adjusted_rows = []
    for i in range(row_count):
        source = current_df.iloc[i].to_dict() if i < len(current_df) else {}
        adjusted_rows.append({col: source.get(col, "") for col in base_columns})

    return pd.DataFrame(adjusted_rows)


source_mode = st.radio(
    "Origem dos dados",
    options=["Upload CSV", "Planilha editável no app"],
    horizontal=True,
)

working_df = None
email_col = None

if source_mode == "Upload CSV":
    uploaded_file = st.file_uploader("Upload do CSV", type=["csv"])
    if uploaded_file:
        try:
            working_df = load_csv(uploaded_file)
        except Exception as exc:
            st.error(f"Erro ao carregar CSV: {exc}")
            st.stop()

        st.subheader("Prévia do CSV")
        st.dataframe(working_df.head(20), use_container_width=True)

        if not working_df.empty:
            email_col = st.selectbox("Coluna de e-mail", options=list(working_df.columns))

else:
    st.subheader("Planilha editável")
    st.caption(
        "Defina os campos variáveis (campo_1, campo_2, ...) e edite os dados diretamente abaixo."
    )

    col_a, col_b = st.columns(2)
    with col_a:
        email_col = st.text_input("Nome da coluna de e-mail", value="email")
        num_fields = st.number_input("Quantidade de campos variáveis", min_value=1, value=3, step=1)
    with col_b:
        row_count = st.number_input("Quantidade de linhas", min_value=1, value=5, step=1)

    st.markdown("**Nomes dos campos variáveis**")
    field_names = []
    for i in range(int(num_fields)):
        field_name = st.text_input(f"Campo {i + 1}", value=f"campo_{i + 1}", key=f"field_name_{i}")
        field_names.append(field_name.strip() or f"campo_{i + 1}")

    if st.button("Gerar/Atualizar planilha editável"):
        st.session_state.manual_df = _build_manual_dataframe(
            email_col_name=email_col,
            field_names=field_names,
            row_count=int(row_count),
            current_df=st.session_state.manual_df,
        )

    if st.button("Carregar exemplo preenchido"):
        # Exemplo simples solicitado pelo usuário
        example_rows = []
        for i in range(int(row_count)):
            row = {
                email_col: f"contato{i + 1}@empresa.com",
                "status": "" if i % 2 == 0 else "pendente",
                "erro": "",
                "enviado_em": "",
            }
            for n, field in enumerate(field_names, start=1):
                row[field] = f"Valor {n} - Linha {i + 1}"
            example_rows.append(row)
        st.session_state.manual_df = pd.DataFrame(example_rows)

    st.session_state.manual_df = _build_manual_dataframe(
        email_col_name=email_col,
        field_names=field_names,
        row_count=int(row_count),
        current_df=st.session_state.manual_df,
    )

    edited_df = st.data_editor(
        st.session_state.manual_df,
        num_rows="dynamic",
        use_container_width=True,
        key="manual_editor",
    )
    working_df = _ensure_campaign_columns(pd.DataFrame(edited_df))

if working_df is None:
    st.info("Selecione uma origem de dados para começar.")
    st.stop()

if working_df.empty:
    st.warning("A tabela está vazia.")
    st.stop()

working_df = _ensure_campaign_columns(working_df)
if not email_col or email_col not in working_df.columns:
    st.error("Defina corretamente a coluna de e-mail.")
    st.stop()

st.subheader("Template")
placeholders = get_available_placeholders(working_df)
st.caption(f"Placeholders disponíveis: {', '.join(placeholders) if placeholders else 'Nenhum'}")

subject_template = st.text_input("Assunto (editável)", value="Pergunta rápida para {{campo_2}}")
body_template = st.text_area(
    "Corpo padrão do e-mail (editável)",
    value=(
        "Olá {{campo_1}},\n\n"
        "Sou Matheus Vianna, da PACE Inteligência Energética.\n\n"
        "Gostaria de entender se o custo de energia é um tema relevante hoje para a {{campo_2}}.\n"
        "Tema de interesse: {{campo_3}}.\n\n"
        "Abraço,\n"
        "Matheus Vianna"
    ),
    height=220,
)

preview_idx = st.number_input(
    "Linha para prévia (índice)", min_value=0, max_value=max(len(working_df) - 1, 0), value=0
)
preview_data = working_df.iloc[int(preview_idx)].to_dict()
rendered_subject, rendered_body = build_template_preview(subject_template, body_template, preview_data)

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
        df=working_df,
        email_col=email_col,
        subject_template=subject_template,
        body_template=body_template,
        smtp_user=email_user,
        smtp_password=email_password,
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
                username=email_user,
                password=email_password,
                sender=email_user,
                recipient=test_email,
                subject=subject,
                body=body,
            )
            st.success(f"Teste enviado para {test_email}.")
        except Exception as exc:
            st.error(f"Falha no envio de teste: {exc}")

if st.button("Executar campanha", type="primary"):
    is_valid, errors = validate_campaign_inputs(
        df=working_df,
        email_col=email_col,
        subject_template=subject_template,
        body_template=body_template,
        smtp_user=email_user,
        smtp_password=email_password,
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
            username=email_user,
            password=email_password,
        )

    def on_progress(done: int, total: int):
        pct = int((done / total) * 100) if total else 100
        progress.progress(min(pct, 100))
        status_text.info(f"Processando: {done}/{total}")

    try:
        result_df, log_rows = process_campaign(
            df=working_df,
            email_col=email_col,
            subject_template=subject_template,
            body_template=body_template,
            sender_email=email_user,
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
    except Exception as exc:
        progress.empty()
        status_text.empty()
        st.error(f"Falha ao iniciar a campanha: {exc}")
        st.stop()

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

pending_labels = sorted(str(v) for v in STATUS_PENDING_VALUES if v is not None)
st.caption(
    f"Status considerados pendentes para envio: {', '.join(['(vazio)'] + pending_labels)}"
)
