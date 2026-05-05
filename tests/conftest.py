import sys
from pathlib import Path

# Add backend/ to sys.path so `from app.*` imports resolve correctly
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
