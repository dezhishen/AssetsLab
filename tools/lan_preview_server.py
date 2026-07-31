from __future__ import annotations

import argparse
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class PreviewHandler(SimpleHTTPRequestHandler):
    server_version = "AssetsLabPreview/1.0"

    def log_message(self, format: str, *args: object) -> None:
        # The server is intentionally silent when launched by the hidden
        # preview helper. HTTP errors are still returned to the client.
        return

    def do_POST(self) -> None:
        if self.path != "/api/save-calibration":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            schema = payload.get("schema")
            output_name = {
                "component_anchor_calibration_v1": "latest.json",
                "body_anchor_calibration_v1": "body_latest.json",
                "walk_body_component_anchor_calibration_v1": "body_components_latest.json",
            }.get(schema)
            if output_name is None:
                raise ValueError("unsupported calibration schema")
            output = Path.cwd() / "calibration" / "latest.json"
            output = output.with_name(output_name)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            body = b'{"saved":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as error:
            body = json.dumps({"saved": False, "error": str(error)}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only AssetsLab LAN preview server")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    root = args.directory.resolve()
    os.chdir(root)
    server = ThreadingHTTPServer(("0.0.0.0", args.port), PreviewHandler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
