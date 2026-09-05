# -*- coding: utf-8 -*-
import threading
import time

import webview

w = webview.create_window("geoconvert-test", "data:text/html,<h1>hello</h1>",
                          width=300, height=200)


def closer():
    time.sleep(6)
    try:
        w.destroy()
    except Exception as e:
        print("destroy fail:", e)


threading.Thread(target=closer, daemon=True).start()
t0 = time.time()
webview.start()
print("webview ran for %.1fs OK" % (time.time() - t0))
