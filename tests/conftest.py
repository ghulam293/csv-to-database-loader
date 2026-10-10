"""Makes the project folder importable, so tests can do: import transform"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))