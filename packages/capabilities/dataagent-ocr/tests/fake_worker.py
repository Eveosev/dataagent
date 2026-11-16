"""Test worker speaking the dataagent-ocr worker protocol (stands in for a real engine)."""

import json
import sys

LINES = ["DATAAGENT OCR PROBE", "INVOICE NO. 2026-1106-0042", "TOTAL AMOUNT 12,345.67", "DATE 2026-11-06"]

for line in sys.stdin:
    request = json.loads(line)
    if request["op"] == "hello":
        print("engine banner on stdout that is not protocol")  # must be tolerated
        reply = {"id": request["id"], "engine": "fake", "engine_version": "9.9"}
    else:
        reply = {
            "id": request["id"],
            "blocks": [{"text": t, "bbox": [0, i * 10, 100, i * 10 + 9], "confidence": 0.95} for i, t in enumerate(LINES)],
        }
    sys.stdout.write(json.dumps(reply) + "\n")
    sys.stdout.flush()
