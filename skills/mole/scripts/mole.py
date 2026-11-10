#!/usr/bin/env python3
"""Run the engine bundled beside this entrypoint, from any working directory."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from molekit.cli import main
except ImportError:
    print(json.dumps({"protocolVersion": "1.0", "ok": False, "status": "FAILED",
                      "nextAction": "Copy the complete skill directory.",
                      "error": {"code": "PAYLOAD_INCOMPLETE", "message": "Bundled engine could not be imported.",
                                "recoverable": True, "suggestedAction": "Copy the complete skill directory and retry."}}))
    raise SystemExit(3)

if __name__ == "__main__":
    raise SystemExit(main())
