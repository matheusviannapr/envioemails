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
- **Carregamento de CSV em formato de planilha editável** (duplo clique na célula para editar)
- Botão para adicionar linha vazia manualmente
- Assunto com placeholders (`{nome}`, `{empresa}`, etc.)
- **Editor do corpo em texto normal** (estilo e-mail) com atalhos:
  - `Negrito` => `**texto**`
  - `Itálico` => `*texto*`
  - `Bullet` => `- item`
- O app converte automaticamente o texto para HTML e envia como `text/html` (com fallback `text/plain`)
- Preview do HTML antes do envio
- Delay aleatório entre envios
- Pausa longa automática por bloco
- Controles de iniciar / pausar / parar
- Progresso + contadores (enviados/falhas/restantes)
- Persistência local:
  - `desktop_config.json`
  - `desktop_checkpoint.json`
  - `desktop_campaign.log`

## Build `.exe`

```bash
pyinstaller --onefile --windowed email_campaign_desktop.py
```
