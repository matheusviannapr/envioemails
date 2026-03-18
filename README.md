# Campanhas de E-mail Titan com Streamlit + SMTP

Fluxo principal de envio via **SMTP** (Professional Email/Titan via GoDaddy), sem automação de navegador.
Após enviar, o sistema tenta salvar cópia em **Enviados** via IMAP.

## Estrutura

- `app.py` → interface Streamlit
- `mailer.py` → rotina principal de campanha
- `smtp_client.py` → cliente SMTP + salvamento em Enviados via IMAP
- `utils.py` → CSV, placeholders e logs
- `config.py` → configuração via `.env`
- `.env.example` → modelo de variáveis

## Funcionalidades atendidas

- Criação de campanha direto no app com planilha editável (quantidade variável de campos)
- Upload de CSV com colunas como `nome,email,empresa`
- Placeholders em assunto/corpo no formato `{nome}` e `{empresa}`
- Exemplo pronto de assunto/corpo ao abrir o app para facilitar uso
- Login/autenticação SMTP via `.env` e/ou campos na barra lateral
- Salvamento automático na pasta Enviados via IMAP (quando pasta for localizada)
- Máximo de 30 envios por execução
- Delay aleatório entre 45 e 90 segundos
- Log em `log.csv` com `destinatario, horario, status, erro`
- Progresso exibido no Streamlit
- Interrupção por erros consecutivos
- Evita duplicidade (não reenvia destinatários já enviados com sucesso em `log.csv`)
- Retomada de campanha com base no status + log

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

## Executar

```bash
streamlit run app.py
```

## Troubleshooting SMTP

- Falha de autenticação: valide e-mail/senha e permissões da conta Professional Email/Titan.
- Falha de conexão: confira `SMTP_HOST`, `SMTP_PORT` (465/587), DNS e firewall.
- Se não aparecer em Enviados, valide `IMAP_HOST`, `IMAP_PORT` e permissões IMAP da conta.
