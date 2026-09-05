# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\WEB\zicaiduck\geo-convert")
from http.server import ThreadingHTTPServer
from geoconvert.webui import Handler
srv = ThreadingHTTPServer(("127.0.0.1", 8898), Handler)
print("READY http://127.0.0.1:8898", flush=True)
srv.serve_forever()
