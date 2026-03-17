import streamlit as st
from dotenv import load_dotenv

from config import CampaignConfig
from mailer import run_campaign
from utils import extract_placeholders, load_csv, render_template, to_csv_download

load_dotenv()

st.set_page_config(page_title="Campanhas Titan via Playwright", layout="wide")
st.title("📨 Campanhas Titan Webmail (Playwright)")

cfg = CampaignConfig()

with st.sidebar:
    st.header("Configuração")
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

cfg.titan_email = sidebar_titan_email
cfg.titan_password = sidebar_titan_password

uploaded_file = st.file_uploader("Upload CSV de leads", type=["csv"])
if not uploaded_file:
    st.info("Envie um CSV para iniciar.")
    st.stop()

df = load_csv(uploaded_file)
st.dataframe(df.head(20), use_container_width=True)

email_col = st.selectbox("Coluna de e-mail", options=list(df.columns), index=list(df.columns).index("email") if "email" in df.columns else 0)
subject_template = st.text_input("Assunto", value="Olá {nome}, proposta para {empresa}")
body_template = st.text_area("Mensagem", value="Oi {nome},\n\nGostaria de falar sobre a {empresa}.\n", height=180)

placeholders = sorted(extract_placeholders(subject_template) | extract_placeholders(body_template))
st.caption("Placeholders detectados: " + (", ".join(f"{{{p}}}" for p in placeholders) if placeholders else "nenhum"))

if not df.empty:
    preview_row = df.iloc[0].to_dict()
    st.subheader("Prévia")
    st.write("**Assunto:**", render_template(subject_template, preview_row))
    st.write("**Corpo:**")
    st.code(render_template(body_template, preview_row))

progress = st.progress(0)
log_text = st.empty()

if st.button("Iniciar campanha"):
    if not cfg.titan_email or not cfg.titan_password:
        st.error("Preencha e-mail e senha do Titan na barra lateral.")
        st.stop()

    def _progress(done: int, total: int):
        progress.progress(done / total if total else 1.0)

    def _status(msg: str):
        log_text.write(msg)

    out_df = run_campaign(
        df=df.copy(),
        email_col=email_col,
        subject_template=subject_template,
        body_template=body_template,
        cfg=cfg,
        progress_callback=_progress,
        status_callback=_status,
    )

    st.success("Execução finalizada.")
    st.dataframe(out_df, use_container_width=True)
    st.download_button("Baixar CSV atualizado", data=to_csv_download(out_df), file_name="campanha_atualizada.csv", mime="text/csv")
