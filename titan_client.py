import os
import time
from datetime import datetime
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from titan_selectors import (
    BODY_EDITOR_SELECTOR,
    COMPOSE_BUTTON_SELECTORS,
    LOGIN_EMAIL_SELECTORS,
    LOGIN_PASSWORD_SELECTORS,
    LOGIN_SUBMIT_SELECTORS,
    SEND_BUTTON_SELECTOR,
    SUBJECT_FIELD_SELECTOR,
    TO_FIELD_SELECTOR,
)


class TitanClient:
    def __init__(self, base_url: str, email: str, password: str, headless: bool, chromium_args: tuple[str, ...]):
        self.base_url = base_url
        self.email = email
        self.password = password
        self.headless = headless
        self.chromium_args = list(chromium_args)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def start(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless, args=self.chromium_args)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def stop(self):
        for obj in [self.context, self.browser, self.playwright]:
            try:
                if obj:
                    obj.close() if hasattr(obj, "close") else obj.stop()
            except Exception:
                pass

    def _first_visible(self, selectors: list[str], timeout_ms: int = 15000):
        for selector in selectors:
            locator = self.page.locator(selector).first
            try:
                locator.wait_for(state="visible", timeout=timeout_ms)
                return locator
            except Exception:
                continue
        raise PlaywrightTimeoutError(f"Nenhum seletor ficou visível: {selectors}")

    def _retry_click(self, selector: str, retries: int = 3, delay_s: float = 0.7):
        last_exc = None
        for _ in range(retries):
            try:
                self.page.locator(selector).first.click(timeout=10000)
                return
            except Exception as exc:
                last_exc = exc
                time.sleep(delay_s)
        raise RuntimeError(f"Falha ao clicar em '{selector}': {last_exc}")

    def login(self):
        self.page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)

        email_field = self._first_visible(LOGIN_EMAIL_SELECTORS)
        email_field.fill(self.email)
        password_field = self._first_visible(LOGIN_PASSWORD_SELECTORS)
        password_field.fill(self.password)
        submit_btn = self._first_visible(LOGIN_SUBMIT_SELECTORS)
        submit_btn.click()

        compose_button = self._first_visible(COMPOSE_BUTTON_SELECTORS, timeout_ms=45000)
        compose_button.wait_for(state="visible")

    def send_email(self, recipient: str, subject: str, body: str):
        compose_clicked = False
        for selector in COMPOSE_BUTTON_SELECTORS:
            try:
                self._retry_click(selector)
                compose_clicked = True
                break
            except Exception:
                continue
        if not compose_clicked:
            raise RuntimeError("Não foi possível abrir janela de composição.")

        self.page.locator(TO_FIELD_SELECTOR).first.wait_for(state="visible", timeout=15000)
        self.page.locator(TO_FIELD_SELECTOR).first.fill(recipient)
        self.page.locator(SUBJECT_FIELD_SELECTOR).first.wait_for(state="visible", timeout=15000)
        self.page.locator(SUBJECT_FIELD_SELECTOR).first.fill(subject)

        body_locator = self.page.locator(BODY_EDITOR_SELECTOR).first
        body_locator.wait_for(state="visible", timeout=15000)
        body_locator.click()
        self.page.keyboard.press("Control+A")
        self.page.keyboard.type(body)

        self._retry_click(SEND_BUTTON_SELECTOR)

    def save_error_screenshot(self, directory: str) -> str:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"error_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png")
        self.page.screenshot(path=path, full_page=True)
        return path
