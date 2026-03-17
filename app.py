import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from config import CampaignConfig
from mailer import run_campaign
from utils import extract_placeholders, load_csv, render_template, to_csv_download

load_dotenv()

st.set_page_config(page_title="Campanhas Titan via Playwright", layout="wide")
st.title("📨 Campanhas Titan Webmail (Playwright)")
st.caption("Crie campanhas no app com planilha editável, placeholders e envio automatizado via Playwright.")

cfg = CampaignConfig()

if "manual_df" not in st.session_state:
    st.session_state.manual_df = pd.DataFrame()


def _ensure_base_columns(df: pd.DataFrame) -> pd.DataFrame:
    local = df.copy()
    for col in ["status", "erro", "enviado_em"]:
        if col not in local.columns:
            local[col] = ""
    return local


def _build_manual_dataframe(
    email_col_name: str,
    custom_fields: list[str],
    row_count: int,
    current_df: pd.DataFrame,
) -> pd.DataFrame:
    campaign_columns = [email_col_name] + custom_fields
    base_columns = campaign_columns + ["status", "erro", "enviado_em"]

    if current_df is None or current_df.empty:
        rows = [{col: "" for col in base_columns} for _ in range(row_count)]
        return pd.DataFrame(rows)

    rows = []
    for i in range(row_count):
        source = current_df.iloc[i].to_dict() if i < len(current_df) else {}
        rows.append({col: source.get(col, "") for col in base_columns})

    return pd.DataFrame(rows)


with st.sidebar:
    st.header("Configuração Titan")
    st.write(f"Titan URL: `{cfg.titan_url}`")
    st.write(f"Headless: `{cfg.headless}`")
    st.caption("Você pode usar os valores do .env como padrão e sobrescrever abaixo.")

    sidebar_titan_email = st.text_input(
        "E-mail Titan",
        value=cfg.titan_email,
        placeholder="seu_email@dominio.com",
    ).strip()
    sidebar_titan_password = st.text_input(
        "Senha Titan",
        type="password",
        value=cfg.titan_password,
        placeholder="Sua senha",
    ).strip()

    st.markdown("---")
    st.subheader("Parâmetros da execução")
    st.caption(f"Máximo por execução: {cfg.max_per_run} e-mails")
    st.caption(f"Delay aleatório: {cfg.delay_min_seconds}s até {cfg.delay_max_seconds}s")

cfg.titan_email = sidebar_titan_email
cfg.titan_password = sidebar_titan_password

source_mode = st.radio(
    "Origem dos dados da campanha",
    options=["Planilha editável no app", "Upload CSV"],
    horizontal=True,
)

working_df = None
email_col = "email"

if source_mode == "Planilha editável no app":
    st.subheader("Montar campanha no app")
    st.caption("Defina os campos da campanha e preencha os leads diretamente na tabela abaixo.")

    col1, col2, col3 = st.columns(3)
    with col1:
        email_col = st.text_input("Nome da coluna de e-mail", value="email").strip() or "email"
    with col2:
        lead_count = int(st.number_input("Quantidade de leads", min_value=1, max_value=30, value=5, step=1))
    with col3:
        fields_count = int(st.number_input("Quantidade de campos variáveis", min_value=1, max_value=10, value=2, step=1))

    st.markdown("**Campos variáveis (para usar no corpo/assunto como placeholders)**")
    default_names = ["nome", "empresa", "cargo", "telefone", "cidade"]
    custom_fields = []
    for i in range(fields_count):
        default_name = default_names[i] if i < len(default_names) else f"campo_{i + 1}"
        field_name = st.text_input(f"Campo {i + 1}", value=default_name, key=f"field_name_{i}").strip()
        custom_fields.append(field_name or f"campo_{i + 1}")

    if st.button("Gerar/atualizar planilha") or st.session_state.manual_df.empty:
        st.session_state.manual_df = _build_manual_dataframe(
            email_col_name=email_col,
            custom_fields=custom_fields,
            row_count=lead_count,
            current_df=st.session_state.manual_df,
        )

        if not st.session_state.manual_df.empty:
            st.session_state.manual_df.at[0, email_col] = "joao@empresa.com"
            if "nome" in st.session_state.manual_df.columns:
                st.session_state.manual_df.at[0, "nome"] = "João"
            if "empresa" in st.session_state.manual_df.columns:
                st.session_state.manual_df.at[0, "empresa"] = "Empresa A"

    st.markdown("### Planilha da campanha")
    st.session_state.manual_df = st.data_editor(
        st.session_state.manual_df,
        use_container_width=True,
        num_rows="fixed",
        key="manual_editor",
    )
    working_df = _ensure_base_columns(st.session_state.manual_df)

else:
    uploaded_file = st.file_uploader("Upload do CSV de leads", type=["csv"])
    if not uploaded_file:
        st.info("Envie um CSV para iniciar ou troque para 'Planilha editável no app'.")
        st.stop()

    working_df = _ensure_base_columns(load_csv(uploaded_file))
    st.subheader("Prévia do CSV")
    st.dataframe(working_df.head(20), use_container_width=True)

    if working_df.empty:
        st.warning("CSV sem linhas.")
        st.stop()

    email_col = st.selectbox(
        "Coluna de e-mail",
        options=list(working_df.columns),
        index=list(working_df.columns).index("email") if "email" in working_df.columns else 0,
    )

st.markdown("---")
st.subheader("Mensagem da campanha")

example_subject = "Olá {nome}, proposta para {empresa}"
example_body = (
    "Olá {nome},\n\n"
    "Vi que você está na {empresa} e gostaria de te mostrar uma proposta rápida.\n"
    "Se fizer sentido, me responde por aqui.\n\n"
    "Abraço!"
)

subject_template = st.text_input("Assunto", value=example_subject)
body_template = st.text_area(
    "Corpo do e-mail (use placeholders como {nome}, {empresa})",
    value=example_body,
    height=220,
)

placeholders = sorted(extract_placeholders(subject_template) | extract_placeholders(body_template))
st.caption("Placeholders detectados: " + (", ".join(f"{{{p}}}" for p in placeholders) if placeholders else "nenhum"))

if working_df is not None and not working_df.empty:
    preview_row = working_df.iloc[0].to_dict()
    st.markdown("### Prévia do primeiro lead")
    st.write("**Assunto renderizado:**", render_template(subject_template, preview_row))
    st.write("**Corpo renderizado:**")
    st.code(render_template(body_template, preview_row))

progress = st.progress(0)
log_text = st.empty()

if st.button("Iniciar campanha"):
    if working_df is None or working_df.empty:
        st.error("Inclua leads na planilha antes de iniciar a campanha.")
        st.stop()

    if email_col not in working_df.columns:
        st.error("A coluna de e-mail selecionada não existe na planilha.")
        st.stop()

    if not cfg.titan_email or not cfg.titan_password:
        st.error("Preencha e-mail e senha do Titan na barra lateral.")
        st.stop()

    def _progress(done: int, total: int):
        progress.progress(done / total if total else 1.0)

    def _status(msg: str):
        log_text.write(msg)

    try:
        out_df = run_campaign(
            df=working_df.copy(),
            email_col=email_col,
            subject_template=subject_template,
            body_template=body_template,
            cfg=cfg,
            progress_callback=_progress,
            status_callback=_status,
        )
    except Exception as exc:
        st.error(f"Falha ao executar campanha: {exc}")
        st.info("No Streamlit Cloud a app tenta instalar Chromium automaticamente (playwright install/install-deps). Se falhar, reinicie o app. Em VPS, rode playwright install chromium.")
        st.stop()

    st.success("Execução finalizada.")
    st.dataframe(out_df, use_container_width=True)
    st.download_button(
        "Baixar CSV atualizado",
        data=to_csv_download(out_df),
        file_name="campanha_atualizada.csv",
        mime="text/csv",
    )
