"""Setup condiviso da tutti i test.

Aggiunge streamlit/app a sys.path cosi' i test possono importare i suoi
moduli (services/components/utils) esattamente come fa Streamlit stesso a
runtime (vedi streamlit/app/main.py) — quella cartella non e' un pacchetto
installato, solo landini_etl lo e' (vedi pyproject.toml).
"""

import sys
from pathlib import Path

_STREAMLIT_APP_DIR = Path(__file__).resolve().parent.parent / "streamlit" / "app"
if str(_STREAMLIT_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_STREAMLIT_APP_DIR))
