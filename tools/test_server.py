# -*- coding: utf-8 -*-
"""浏览器实测用：只起 HTTP 服务，不开浏览器。用法: python tools/test_server.py [port]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from http.server import ThreadingHTTPServer

from geoconvert.webui import Handler

port = int(sys.argv[1]) if len(sys.argv) > 1 else 18765
srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
print('listening on http://127.0.0.1:%d' % port, flush=True)
srv.serve_forever()
