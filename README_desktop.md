# Email Campaign Desktop (Local)

Aplicação **nova e independente** do Streamlit para executar campanhas de e-mail localmente no Windows usando interface `customtkinter`.

## Arquivos gerados

- `email_campaign_desktop.py` (aplicação principal)
- `requirements_desktop.txt` (dependências da versão desktop)

## Execução local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements_desktop.txt
python email_campaign_desktop.py
```

## Funcionalidades

- Configuração SMTP e IMAP pela UI
- Teste de conexão SMTP/IMAP
- **Planilha colada direto na interface** (copiar do Excel/Sheets e colar)
- Assunto com placeholders (`{nome}`, `{empresa}`, etc.)
- **Mini editor HTML** com atalhos para negrito, itálico, parágrafo, lista e quebra de linha
- Envio do corpo como HTML (com versão texto simples de fallback)
- Delay aleatório entre envios
- Pausa longa automática por bloco
- Controles de iniciar / pausar / parar
- Progresso + contadores (enviados/falhas/restantes)
- Persistência local:
  - `desktop_config.json`
  - `desktop_checkpoint.json`
  - `desktop_campaign.log`

## Formato da planilha colada

- A primeira linha deve ser o cabeçalho.
- É obrigatório existir a coluna `email`.
- Pode ser separado por TAB (padrão ao colar do Excel) e também aceita `;` ou `,`.

Exemplo:

```text
email	nome	empresa
ana@empresa.com	Ana	Empresa A
bruno@empresa.com	Bruno	Empresa B
```

## Build `.exe`

```bash
pyinstaller --onefile --windowed email_campaign_desktop.py
```
