import functools
import http.server
import socketserver

import os
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PORT = 8766

Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DIRECTORY)

with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
    print("serving on", PORT)
    httpd.serve_forever()
