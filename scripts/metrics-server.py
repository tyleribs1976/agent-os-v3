#!/usr/bin/env python3
"""Simple metrics HTTP endpoint for Agent-OS v3."""

import sys
sys.path.insert(0, "/opt/agent-os-v3/src")

from http.server import HTTPServer, BaseHTTPRequestHandler
import json

from metrics import get_all_metrics, export_prometheus

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            # Prometheus format
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(export_prometheus().encode())
        elif self.path == "/metrics/json":
            # JSON format
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(get_all_metrics()).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logging

if __name__ == "__main__":
    port = 9090
    server = HTTPServer(("0.0.0.0", port), MetricsHandler)
    print(f"Metrics server running on port {port}")
    server.serve_forever()
