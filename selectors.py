COMPOSE_BUTTON_SELECTORS = [
    '[data-testid="compose-btn"]',
    'button.btn.btn-primary.item-compose',
]

TO_FIELD_SELECTOR = 'input[data-testid*="draft-to"]'
SUBJECT_FIELD_SELECTOR = 'input[data-testid="subject-input"]'
BODY_EDITOR_SELECTOR = 'div.fr-element'
SEND_BUTTON_SELECTOR = 'span:has-text("Enviar")'

# Fallback selectors para login, pois podem variar por tenant/idioma.
LOGIN_EMAIL_SELECTORS = ['input[type="email"]', 'input[name="email"]']
LOGIN_PASSWORD_SELECTORS = ['input[type="password"]', 'input[name="password"]']
LOGIN_SUBMIT_SELECTORS = ['button[type="submit"]', 'button:has-text("Entrar")', 'button:has-text("Sign in")']
