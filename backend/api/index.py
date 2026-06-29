from pathlib import Path
import sys

# Ensure backend root is importable when Vercel runs this file from /api.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from main import app
