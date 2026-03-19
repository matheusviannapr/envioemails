from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class CampaignConfig:
    smtp_host: str = os.getenv("SMTP_HOST", "smtpout.secureserver.net")
    smtp_port: int = int(os.getenv("SMTP_PORT", "465"))
    imap_host: str = os.getenv("IMAP_HOST", "imap.secureserver.net")
    imap_port: int = int(os.getenv("IMAP_PORT", "993"))

    titan_email: str = os.getenv("TITAN_EMAIL", "")
    titan_password: str = os.getenv("TITAN_PASSWORD", "")

    max_per_run: int = min(int(os.getenv("MAX_PER_RUN", "30")), 30)
    delay_min_seconds: int = int(os.getenv("DELAY_MIN_SECONDS", "15"))
    delay_max_seconds: int = int(os.getenv("DELAY_MAX_SECONDS", "20"))
    max_consecutive_errors: int = int(os.getenv("MAX_CONSECUTIVE_ERRORS", "5"))
    log_path: str = os.getenv("LOG_CSV_PATH", "log.csv")
    screenshot_dir: str = os.getenv("SCREENSHOT_DIR", "screenshots")
