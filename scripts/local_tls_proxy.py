"""Loopback-only TLS harness for isolated deployment verification. Not a production edge server."""

import argparse
import http.client
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--certificate", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--listen", type=int, default=13443)
    parser.add_argument("--target", type=int, default=13000)
    args = parser.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def forward(self):
            connection = http.client.HTTPConnection("127.0.0.1", args.target, timeout=60)
            try:
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                headers = {
                    k: v
                    for k, v in self.headers.items()
                    if k.lower() not in {"connection", "transfer-encoding", "content-length"}
                }
                connection.request(self.command, self.path, body=body, headers=headers)
                upstream = connection.getresponse()
                content = upstream.read()
                self.send_response(upstream.status)
                for key, value in upstream.getheaders():
                    if key.lower() not in {"connection", "transfer-encoding", "content-length"}:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            finally:
                connection.close()

        do_GET = forward
        do_POST = forward
        do_PUT = forward
        do_PATCH = forward
        do_DELETE = forward

    server = ThreadingHTTPServer(("127.0.0.1", args.listen), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(args.certificate, args.key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print("Local verification TLS listener ready", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
