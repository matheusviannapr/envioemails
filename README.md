# Campanhas de E-mail Titan com Streamlit + Playwright

Refatoração do fluxo para usar **automação do Titan Webmail** (Playwright) como caminho principal, sem SMTP.

## Estrutura

- `app.py` → interface Streamlit
- `mailer.py` → rotina principal de campanha
- `titan_client.py` → automação de navegador no Titan
- `utils.py` → CSV, placeholders e logs
- `config.py` → configuração via `.env`
- `selectors.py` → seletores da interface Titan
- `.env.example` → modelo de variáveis

## Funcionalidades atendidas

- Criação de campanha direto no app com planilha editável (quantidade variável de campos)
- Upload de CSV com colunas como `nome,email,empresa`
- Placeholders em assunto/corpo no formato `{nome}` e `{empresa}`
- Exemplo pronto de assunto/corpo ao abrir o app para facilitar uso
- Login no Titan via `.env` e/ou campos de credenciais na barra lateral
- Envio via Chromium headless com `--no-sandbox` e `--disable-dev-shm-usage`
- Máximo de 30 envios por execução
- Delay aleatório entre 45 e 90 segundos
- Log em `log.csv` com `destinatario, horario, status, erro`
- Screenshot em falhas
- Progresso exibido no Streamlit
- Interrupção por erros consecutivos
- Evita duplicidade (não reenvia destinatários já enviados com sucesso em `log.csv`)
- Retomada de campanha com base no status + log

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

## Executar

```bash
streamlit run app.py
```
