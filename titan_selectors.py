COMPOSE_BUTTON_SELECTORS = [
    '[data-testid="compose-btn"]',
    'button.btn.btn-primary.item-compose',
    'button:has(span:has-text("Novo e-mail"))',
    'span:has-text("Novo e-mail")',
    'button:has-text("Novo e-mail")',
    'button:has-text("Compose")',
]

TO_FIELD_SELECTOR = 'input[data-testid*="draft-to"]'
SUBJECT_FIELD_SELECTOR = 'input[data-testid="subject-input"]'
BODY_EDITOR_SELECTOR = 'div.fr-element'
SEND_BUTTON_SELECTOR = 'span:has-text("Enviar")'

# Fallback selectors para login, pois podem variar por tenant/idioma.
LOGIN_EMAIL_SELECTORS = ['input#username', 'input[name="username"]', 'input[type="email"]', 'input[name="email"]', 'input.ux-text-entry-field[type="text"]']
LOGIN_PASSWORD_SELECTORS = ['input#password', 'input[autocomplete="current-password"]', 'input[type="password"]', 'input[name="password"]']
LOGIN_SUBMIT_SELECTORS = ['button#submitBtn', 'button[id="submitBtn"]', 'button[type="submit"]', 'button:has-text("Entrar")', 'button:has-text("Sign In")', 'button:has-text("Sign in")']
