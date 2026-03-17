COMPOSE_BUTTON_SELECTORS = [
    '[data-testid="compose-btn"]',
    'button.btn.btn-primary.item-compose',
    'button:has(span:has-text("Novo e-mail"))',
    'button:has(span:has-text("New email"))',
    'span:has-text("Novo e-mail")',
    'span:has-text("New email")',
    'button:has-text("Novo e-mail")',
    'button:has-text("New email")',
    'button:has-text("Compose")',
]

TO_FIELD_SELECTORS = [
    'input[data-testid*="draft-to"]',
    'input[data-testid*="participant-input"]',
    'div.tokenizing-field-input input[type="text"]',
]

SUBJECT_FIELD_SELECTORS = [
    'input[data-testid="subject-input"]',
    'input[name="subject"]',
    'input[placeholder="Subject"]',
]

BODY_EDITOR_SELECTORS = [
    'div.fr-element',
    'div[contenteditable="true"]',
]

SEND_BUTTON_SELECTORS = [
    'button[data-testid="send-action-btn"]',
    'button.btn.btn-primary.btn-send',
    'button:has-text("Send")',
    'span:has-text("Send")',
    'span:has-text("Enviar")',
]

# Seletores da página inicial do Titan
TITAN_LOGIN_EMAIL_SELECTORS = ['input[name="email"]', 'input[type="text"][placeholder*="Email"]']
TITAN_LOGIN_NEXT_BUTTON_SELECTORS = ['button.btn-login', 'button:has-text("Login")', 'button:has-text("Next")']

# Seletores do SSO da GoDaddy (redirecionamento)
GODADDY_LOGIN_EMAIL_SELECTORS = ['input#username', 'input[name="username"]', 'input.ux-text-entry-field[type="text"]']
GODADDY_LOGIN_PASSWORD_SELECTORS = ['input#password', 'input[autocomplete="current-password"]', 'input[type="password"]']
GODADDY_LOGIN_SUBMIT_SELECTORS = ['button#submitBtn', 'button[id="submitBtn"]', 'button:has-text("Sign In")']
