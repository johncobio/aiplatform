"""A standalone, stateless sample. Intended for a restricted demo network."""

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

EMAIL = re.compile(
    r"[a-z0-9_+%-]+(?:\.[a-z0-9_+%-]+)*@"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",
    re.IGNORECASE | re.ASCII,
)


class PreviewHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(5)
        super().setup()

    def log_message(self, *_args):
        # No request bodies or arbitrary URLs in the demo's system journal.
        pass

    def respond(self, content, media_type):
        self.send_response(200)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def page(self, result=""):
        version = self.server.preview_version
        html = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign-up form · Version {version}</title>
<h1>Sign-up form · Version {version}</h1>
<p>Temporary preview. Use a fake address; nothing is saved or sent.</p>
<form method="post" action="/">
  <label for="email">Sample email</label>
  <input id="email" name="email" maxlength="254" value="not-an-email">
  <button>Test sign-up</button>
</form>
<p role="status">{result}</p>
</html>"""
        self.respond(html.encode(), "text/html; charset=utf-8")

    def do_GET(self):
        if self.path == "/readyz":
            data = {"ready": True, "version": self.server.preview_version}
            self.respond(json.dumps(data).encode(), "application/json")
        elif self.path == "/":
            self.page()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 4096:
                raise ValueError("Invalid length")
            form = parse_qs(self.rfile.read(size).decode("utf-8"), max_num_fields=4)
            email = form.get("email", [""])[0].strip()
        except (ValueError, TimeoutError):
            self.send_error(400, "Invalid form")
            return
        accepted = len(email) <= 254 and (
            bool(email) if self.server.preview_version == 1 else EMAIL.fullmatch(email) is not None
        )
        self.page("Accepted the input." if accepted else "Rejected the input.")


def serve(version, host, port):
    if version not in (1, 2):
        raise ValueError("Unsupported version")
    with HTTPServer((host, port), PreviewHandler) as server:
        server.preview_version = version
        print(f"Ready: version {version} on port {server.server_port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    serve(int(sys.argv[1]), sys.argv[2], int(sys.argv[3]))
