# Campanhas de E-mail Titan com Streamlit + Playwright

Refatoração do fluxo para usar **automação do Titan Webmail** (Playwright) como caminho principal, sem SMTP.

## Estrutura

- `app.py` → interface Streamlit
- `mailer.py` → rotina principal de campanha
- `titan_client.py` → automação de navegador no Titan
- `utils.py` → CSV, placeholders e logs
- `config.py` → configuração via `.env`
- `titan_selectors.py` → seletores da interface Titan (evita conflito com módulo padrão `selectors`)
- `.env.example` → modelo de variáveis

## Funcionalidades atendidas

- Criação de campanha direto no app com planilha editável (quantidade variável de campos)
- Upload de CSV com colunas como `nome,email,empresa`
- Placeholders em assunto/corpo no formato `{nome}` e `{empresa}`
- Exemplo pronto de assunto/corpo ao abrir o app para facilitar uso
- Login no Titan via `.env` e/ou campos de credenciais na barra lateral (incluindo Titan URL editável)
- Suporte a fluxo de login em duas etapas (Titan → GoDaddy SSO)
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


## Troubleshooting

- Erro `Executable doesn't exist` no Playwright:
  - **Streamlit Cloud**: mantenha `PLAYWRIGHT_AUTO_INSTALL=true`. O app tenta automaticamente `playwright install` + `playwright install chromium` e `playwright install-deps` (best effort).
  - Se aparecer erro de `shared libraries` (ex.: `libglib-2.0.so.0`), adicione `packages.txt` com libs do sistema e faça reboot/redeploy.
  - **VPS/servidor**: execute `playwright install chromium` e instale libs de sistema necessárias.


## packages.txt (Streamlit Cloud)

Crie `packages.txt` na raiz com dependências de SO para Playwright/Chromium.
Incluímos uma lista ampliada baseada em erros comuns no Streamlit Cloud (ex.: `libglib`, `libnspr4`, `libcups2`, `libatspi2.0-0`, `libwayland-client0`).

- Erro `ERR_NAME_NOT_RESOLVED`: revise a Titan URL no sidebar e a conectividade/DNS do ambiente Streamlit Cloud.

- Se seu domínio usa GoDaddy SSO, o app tenta o fluxo com etapa inicial de e-mail + redirecionamento para senha/Sign In.
