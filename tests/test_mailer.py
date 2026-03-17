import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

import mailer


class FakeTitanClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    def start(self):
        return None

    def login(self):
        return None

    def send_email(self, recipient, subject, body):
        self.calls.append((recipient, subject, body))

    def save_error_screenshot(self, directory):
        return f"{directory}/error.png"

    def stop(self):
        return None


def test_run_campaign_respects_max_per_run_and_marks_sent(monkeypatch, tmp_path):
    fake_module = SimpleNamespace(TitanClient=FakeTitanClient)
    monkeypatch.setitem(sys.modules, "titan_client", fake_module)
    monkeypatch.setattr(mailer.time, "sleep", lambda *_: None)

    cfg = SimpleNamespace(
        log_path=str(tmp_path / "log.csv"),
        max_per_run=2,
        titan_url="https://webmail.titan.email",
        titan_email="x@y.com",
        titan_password="123",
        headless=True,
        chromium_args=("--no-sandbox", "--disable-dev-shm-usage"),
        max_consecutive_errors=3,
        delay_min_seconds=0,
        delay_max_seconds=0,
        screenshot_dir=str(tmp_path),
    )

    df = pd.DataFrame([
        {"nome": "A", "email": "a@a.com", "status": ""},
        {"nome": "B", "email": "b@b.com", "status": ""},
        {"nome": "C", "email": "c@c.com", "status": ""},
    ])

    out = mailer.run_campaign(df, "email", "Oi {nome}", "Corpo", cfg)
    assert (out["status"] == "enviado").sum() == 2
