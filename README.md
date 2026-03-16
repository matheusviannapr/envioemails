# Titan Mail Merge com Streamlit

Aplicativo em Python para execução de campanhas de e-mail **autorizadas** via SMTP do Titan Email, com personalização por CSV, controle operacional e logs.

> ⚠️ Este projeto foi desenhado para uso legítimo e responsável. Não há automação de navegador, scraping, evasão de spam, rotação de identidade ou técnicas para burlar filtros.

## Funcionalidades

- Upload de CSV com colunas arbitrárias.
- Modo alternativo com planilha editável no app (sem CSV), com coluna de e-mail + campos variáveis dinâmicos.
- Prévia da tabela no app.
- Seleção/definição da coluna de e-mail.
- Templates com placeholders `{{nome_coluna}}` no assunto e corpo (assunto e corpo totalmente editáveis).
- Prévia da mensagem renderizada por linha.
- Envio apenas de registros com status vazio/pendente.
- Limite máximo de **30 e-mails por execução**.
- Intervalo aleatório configurável (rate limiting operacional).
- Status por linha: `enviado`, `erro`, `ignorado`.
- Registro de data/hora (`enviado_em`) e erro (`erro`).
- Botão de envio de teste.
- Modo de simulação sem envio real.
- Download do CSV atualizado e do log.
- Persistência opcional em SQLite para histórico de campanhas.

## Estrutura

```bash
.
├── app.py
├── mailer.py
├── templates.py
├── storage.py
├── utils.py
├── requirements.txt
├── .env.example
├── tests/
│   └── test_templates.py
└── README.md
```

## Requisitos

- Python 3.11+
- Conta Titan Email com SMTP habilitado

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

## Configuração de ambiente

1. Copie o arquivo de exemplo:

```bash
cp .env.example .env
```

2. Preencha no `.env`:

```env
SMTP_HOST=smtp.titan.email
SMTP_PORT=465
SMTP_USER=seu_email@dominio.com
SMTP_PASSWORD=sua_senha
```

> No app, você também pode preencher credenciais na barra lateral para testes locais.

## Executar o app

```bash
streamlit run app.py
```

## Formato esperado do CSV

Exemplo mínimo:

```csv
nome,email,empresa,status,erro,enviado_em
João,joao@empresa.com,Empresa A,,,
Maria,maria@empresa.com,Empresa B,,,
```

- Colunas podem variar livremente.
- Placeholders usam nomes das colunas (`{{nome}}`, `{{empresa}}`, etc.).

## Fluxo recomendado

1. Escolha a origem dos dados: upload de CSV ou planilha editável no app.
2. Se estiver no modo editável, defina coluna de e-mail, quantidade de campos (campo_1, campo_2, ...), gere a planilha e preencha/cole seus dados.
3. Defina assunto e corpo com placeholders.
4. Valide prévia em uma linha.
5. Envie um e-mail de teste.
6. Execute em modo simulação (opcional).
7. Execute campanha real.
8. Baixe CSV atualizado e logs.

## Testes

```bash
pytest
```

## Observações de segurança e conformidade

- Não implemente, nem utilize, técnicas de evasão de spam.
- Garanta que os destinatários tenham base legal para contato.
- Respeite limites e políticas do provedor Titan.
- Use credenciais via `.env` em ambiente local e segredo seguro em produção.

## Melhorias futuras (sugestões)

- Suporte a anexos controlados e validados.
- Múltiplos templates por segmento de público.
- Dashboard de métricas por campanha (taxa de erro, throughput, etc.).
- Fila de execução assíncrona (ex.: Celery/RQ) para volumes maiores.
- Auditoria com autenticação de usuário e trilha de ações.
- Validação avançada de e-mails e deduplicação automática.
- Export de histórico SQLite para relatórios.
