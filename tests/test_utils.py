import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils import extract_placeholders


def test_extract_placeholders_detects_subject_and_body_tokens():
    tokens = extract_placeholders("Olá {nome} da {empresa}")
    assert tokens == {"nome", "empresa"}
