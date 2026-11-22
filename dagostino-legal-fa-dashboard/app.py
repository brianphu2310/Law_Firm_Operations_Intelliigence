"""Entry point kept for the existing Streamlit Community Cloud deployment.

The app was first deployed with this file as its main file. The real app now lives
in the repository root (app.py); this file just runs it, so the public demo URL
keeps working without redeploying.
"""
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
runpy.run_path(os.path.join(ROOT, "app.py"), run_name="__main__")
