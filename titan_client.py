import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from titan_selectors import (
    BODY_EDITOR_SELECTORS,
    COMPOSE_BUTTON_SELECTORS,
    TITAN_LOGIN_EMAIL_SELECTORS,
    TITAN_LOGIN_NEXT_BUTTON_SELECTORS,
    GODADDY_LOGIN_EMAIL_SELECTORS,
    GODADDY_LOGIN_PASSWORD_SELECTORS,
    GODADDY_LOGIN_SUBMIT_SELECTORS,
    SEND_BUTTON_SELECTORS,
    SUBJECT_FIELD_SELECTORS,
    TO_FIELD_SELECTORS,
)


class TitanClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        headless: bool,
        chromium_args: tuple[str, ...],
        auto_install_browser: bool = True,
    ):
        self.base_url = base_url
        self.email = email
        self.password = password
        self.headless = headless
        self.chromium_args = list(chromium_args)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.auto_install_browser = auto_install_browser

    def _is_missing_browser_error(self, error: Exception) -> bool:
        message = str(error)
        return "Executable doesn't exist" in message or "Please run the following command" in message


    def _is_missing_system_lib_error(self, error: Exception) -> bool:
        message = str(error)
        return "error while loading shared libraries" in message or "libglib-2.0.so.0" in message

    def _run_install_command(self, command: list[str], allow_failure: bool = False) -> tuple[bool, str]:
        try:
            completed = subprocess.run(command, check=True, capture_output=True, text=True)
            output = (completed.stdout or "") + (completed.stderr or "")
            return True, output.strip()
        except Exception as exc:
            if allow_failure:
                return False, str(exc)
            raise

    def _install_chromium(self) -> tuple[bool, str]:
        logs = []
        playwright_bin = shutil.which("playwright")

        install_attempts = [
            [sys.executable, "-m", "playwright", "install"],
            [sys.executable, "-m", "playwright", "install", "chromium"],
        ]

        if playwright_bin:
            install_attempts.extend(
                [
                    ["playwright", "install"],
                    ["playwright", "install", "chromium"],
                ]
            )

        for cmd in install_attempts:
            ok, output = self._run_install_command(cmd, allow_failure=True)
            logs.append(f"$ {' '.join(cmd)}\n{output}")
            if ok:
                # install-deps pode falhar em ambientes sem sudo (ex.: Streamlit Cloud), então é best effort.
                if playwright_bin and cmd[0] == "playwright":
                    self._run_install_command(["playwright", "install-deps"], allow_failure=True)
                elif cmd[0] == sys.executable:
                    self._run_install_command([sys.executable, "-m", "playwright", "install-deps"], allow_failure=True)
                return True, "\n\n".join(logs)

        return False, "\n\n".join(logs)

    def start(self):
        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.launch(headless=self.headless, args=self.chromium_args)
        except Exception as exc:
            if self.auto_install_browser and self._is_missing_browser_error(exc):
                ok, install_logs = self._install_chromium()
                if ok:
                    try:
                        self.browser = self.playwright.chromium.launch(headless=self.headless, args=self.chromium_args)
                    except Exception as relaunch_exc:
                        if self._is_missing_system_lib_error(relaunch_exc):
                            raise RuntimeError(
                                "Chromium foi baixado, mas faltam bibliotecas do sistema (ex.: libglib). "
                                "No Streamlit Cloud, adicione um arquivo packages.txt com dependências do Playwright "
                                "e faça reboot/redeploy do app."
                            ) from relaunch_exc
                        raise RuntimeError(
                            "A instalação automática foi executada, mas o Chromium ainda não iniciou. "
                            "No Streamlit Cloud, verifique o runtime e reinicie o app. "
                            f"Detalhes: {relaunch_exc}"
                        ) from relaunch_exc
                else:
                    raise RuntimeError(
                        "Chromium do Playwright não está instalado e a instalação automática falhou. "
                        "Tentativas realizadas: playwright install / playwright install chromium / playwright install-deps (best effort). "
                        "No Streamlit Cloud, mantenha PLAYWRIGHT_AUTO_INSTALL=true e faça reboot do app. "
                        "Em VPS, execute manualmente: playwright install chromium. "
                        f"Logs: {install_logs[:1200]}"
                    ) from exc
            else:
                if self._is_missing_system_lib_error(exc):
                    raise RuntimeError(
                        "Faltam bibliotecas nativas do sistema para iniciar o Chromium (ex.: libglib). "
                        "No Streamlit Cloud, use packages.txt com dependências do Playwright e redeploy."
                    ) from exc
                if self._is_missing_browser_error(exc):
                    raise RuntimeError(
                        "Chromium do Playwright não está instalado. "
                        "No Streamlit Cloud, habilite PLAYWRIGHT_AUTO_INSTALL=true; "
                        "em VPS, execute: playwright install chromium"
                    ) from exc
                raise

        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        
        # Script stealth para mascarar o Playwright
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

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
        try:
            self.page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:
            message = str(exc)
            if "ERR_NAME_NOT_RESOLVED" in message:
                raise RuntimeError(
                    "Não foi possível resolver o domínio do Titan Webmail (ERR_NAME_NOT_RESOLVED). "
                    "Verifique a URL configurada, DNS/rede do ambiente e tente novamente."
                ) from exc
            if "ERR_CONNECTION" in message or "ERR_INTERNET_DISCONNECTED" in message:
                raise RuntimeError(
                    "Falha de conectividade ao acessar Titan Webmail. "
                    "Verifique acesso de rede/egress do ambiente Streamlit Cloud."
                ) from exc
            raise

        # Passo 1: Preencher email na página inicial do Titan
        try:
            email_field = self._first_visible(TITAN_LOGIN_EMAIL_SELECTORS, timeout_ms=15000)
            email_field.fill(self.email)
            next_btn = self._first_visible(TITAN_LOGIN_NEXT_BUTTON_SELECTORS, timeout_ms=5000)
            next_btn.click()
        except PlaywrightTimeoutError:
            # Pode já estar na página da GoDaddy ou já logado
            pass

        # Aguardar possível redirecionamento para GoDaddy
        time.sleep(3)

        # Passo 2: Preencher senha (e email se necessário) no SSO da GoDaddy
        if "sso.godaddy.com" in self.page.url:
            try:
                # Verifica se o email já está preenchido, se não, preenche
                godaddy_email = self._first_visible(GODADDY_LOGIN_EMAIL_SELECTORS, timeout_ms=5000)
                if not godaddy_email.input_value():
                    godaddy_email.fill(self.email)
            except PlaywrightTimeoutError:
                pass

            password_field = self._first_visible(GODADDY_LOGIN_PASSWORD_SELECTORS, timeout_ms=15000)
            password_field.fill(self.password)
            submit_btn = self._first_visible(GODADDY_LOGIN_SUBMIT_SELECTORS, timeout_ms=5000)
            submit_btn.click()

        # Passo 3: Aguardar redirecionamento de volta para a caixa de entrada do Titan
        try:
            compose_button = self._first_visible(COMPOSE_BUTTON_SELECTORS, timeout_ms=45000)
            compose_button.wait_for(state="visible")
        except PlaywrightTimeoutError as exc:
            # Verifica se a GoDaddy bloqueou o login
            if "sso.godaddy.com" in self.page.url and self.page.locator('text="unusual"').count() > 0:
                raise RuntimeError("A GoDaddy bloqueou o login por detectar um navegador automatizado (unusual browser). Considere usar SMTP.") from exc
            raise RuntimeError("Falha ao carregar a caixa de entrada do Titan após o login.") from exc

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

        to_field = self._first_visible(TO_FIELD_SELECTORS, timeout_ms=20000)
        to_field.fill(recipient)

        subject_field = self._first_visible(SUBJECT_FIELD_SELECTORS, timeout_ms=20000)
        subject_field.fill(subject)

        body_locator = self._first_visible(BODY_EDITOR_SELECTORS, timeout_ms=20000)
        body_locator.click()
        self.page.keyboard.press("Control+A")
        self.page.keyboard.type(body)

        sent_clicked = False
        for selector in SEND_BUTTON_SELECTORS:
            try:
                self._retry_click(selector)
                sent_clicked = True
                break
            except Exception:
                continue

        if not sent_clicked:
            raise RuntimeError("Não foi possível clicar no botão de envio (Send/Enviar).")

    def save_error_screenshot(self, directory: str) -> str:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"error_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png")
        self.page.screenshot(path=path, full_page=True)
        return path
