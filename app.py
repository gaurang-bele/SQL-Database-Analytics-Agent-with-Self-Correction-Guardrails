#!/usr/bin/env python3
"""
SQL & Database Analytics Agent - Streamlit Application Entrypoint
Run using:
    streamlit run app.py
"""
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.ui.dashboard import run_dashboard

if __name__ == "__main__":
    run_dashboard()
