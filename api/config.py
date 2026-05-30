"""
Injects Supabase public config into the frontend.
GET /api/config → returns { supabaseUrl, supabaseAnon }
These are public keys — safe to expose to the browser.
"""

import os
import json
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        config = {
            "supabaseUrl":  os.environ.get("SUPABASE_URL", ""),
            "supabaseAnon": os.environ.get("SUPABASE_ANON_KEY", ""),
        }
        body = json.dumps(config).encode()
        self.send_response(200)
        self.send_header("Content-Type",  "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass
