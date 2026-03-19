import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils import validate_campaign_inputs


def test_validate_campaign_inputs_requires_full_email_user():
    df = pd.DataFrame([{"email": "dest@example.com"}])
    ok, errors = validate_campaign_inputs(
        df=df,
        email_col="email",
        subject_template="Assunto",
        body_template="Corpo",
        smtp_user="usuario-sem-arroba",
        smtp_password="secret",
        max_per_run=1,
        min_interval=0,
        max_interval=1,
    )

    assert not ok
    assert "'email_user' deve ser um endereço de e-mail completo." in errors
