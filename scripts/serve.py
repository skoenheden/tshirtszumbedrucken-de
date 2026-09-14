#!/usr/bin/env python3
"""Lokale Vorschau von docs/ wie auf GitHub Pages: /slug liefert slug.html aus."""
import http.server, os, sys
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=DOCS, **k)
    def send_head(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if path != "/" and "." not in os.path.basename(path) and os.path.exists(os.path.join(DOCS, path.lstrip("/") + ".html")):
            self.path = path + ".html"
        elif not os.path.exists(os.path.join(DOCS, path.lstrip("/"))) and path != "/":
            self.path = "/404.html"
        return super().send_head()

http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
