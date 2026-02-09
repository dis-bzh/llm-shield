import sys
import urllib.request
import os

PORT = os.environ.get("PORT", "4000")
URL = f"http://127.0.0.1:{PORT}/health"

try:
    with urllib.request.urlopen(URL) as response:
        if response.status == 200:
            sys.exit(0)
        else:
            sys.exit(1)
except Exception as e:
    print(f"Healthcheck failed: {e}", file=sys.stderr)
    sys.exit(1)
