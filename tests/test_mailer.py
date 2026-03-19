import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from mailer import build_smtp_client


@patch("mailer.smtplib.SMTP")
def test_build_smtp_client_uses_starttls_before_login(mock_smtp):
    mock_client = MagicMock()
    mock_smtp.return_value = mock_client

    build_smtp_client(
        host="smtp.titan.email",
        port=587,
        username="user@example.com",
        password="secret",
    )

    method_calls = [call[0] for call in mock_client.method_calls]
    assert "starttls" in method_calls
    assert "login" in method_calls
    assert method_calls.index("starttls") < method_calls.index("login")
