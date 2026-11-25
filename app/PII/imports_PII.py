
import sys
from pathlib import Path

MODEL_DIR = (
    Path(__file__).resolve().parents[2]
    / "models"
    / "cbx-indic-pii-extractor-17M"
)

sys.path.insert(0, str(MODEL_DIR))

from pii import PIIExtractor  # type: ignore[reportMissingImports]
pii = PIIExtractor()
 

def extract_pii(text: str):
    return pii.extract(text)


def redact_pii(text: str):
    return pii.redact(text)