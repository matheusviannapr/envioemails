from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class CampaignConfig:
    titan_url: str = os.getenv("TITAN_WEBMAIL_URL", "https://webmail.titan.email")
    titan_email: str = os.getenv("TITAN_EMAIL", "")
    titan_password: str = os.getenv("TITAN_PASSWORD", "")
    headless: bool = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    max_per_run: int = min(int(os.getenv("MAX_PER_RUN", "30")), 30)
    delay_min_seconds: int = int(os.getenv("DELAY_MIN_SECONDS", "45"))
    delay_max_seconds: int = int(os.getenv("DELAY_MAX_SECONDS", "90"))
    max_consecutive_errors: int = int(os.getenv("MAX_CONSECUTIVE_ERRORS", "5"))
    log_path: str = os.getenv("LOG_CSV_PATH", "log.csv")
    screenshot_dir: str = os.getenv("SCREENSHOT_DIR", "screenshots")
    chromium_args: tuple[str, ...] = ("--no-sandbox", "--disable-dev-shm-usage")
