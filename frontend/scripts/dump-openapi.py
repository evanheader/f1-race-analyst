"""Write the API's OpenAPI document to the file named on the command line, without a server."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.main import app

Path(sys.argv[1]).write_text(json.dumps(app.openapi()), encoding="utf-8")
