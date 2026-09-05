# -*- coding: utf-8 -*-
"""geoconvert.exe 入口：把 -m geoconvert 命令行语义原样转给包内 __main__。"""
import os
import sys

from geoconvert.__main__ import main


def _force_utf8_when_piped():
    # PyInstaller bootloader 不透传 PYTHONIOENCODING/PYTHONUTF8，重定向输出会退回 cp936。
    # 交互控制台（isatty）保持默认 WinConsoleIO（正确显示中文），管道/文件统一 UTF-8；
    # line_buffering 让 print 的端口提示即时可见。
    for s in (sys.stdout, sys.stderr):
        try:
            if s is not None and not s.isatty() and hasattr(s, 'reconfigure'):
                s.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
        except Exception:
            pass


def _attach_parent_console():
    """GUI 子系统（console=False）下恢复 CLI 可见性。

    双击启动：无控制台句柄 → 纯 GUI，无需输出。
    终端启动且无重定向：句柄无效 → AttachConsole 挂回父终端并重开 CONOUT$。
    管道/文件重定向：句柄有效 → 什么都不做（输出走管道/文件）。
    """
    try:
        os.write(1, b'')
        return  # stdout 句柄有效（控制台/管道/文件），无需处理
    except OSError:
        pass
    try:
        import ctypes
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        if k.AttachConsole(-1):  # ATTACH_PARENT_PROCESS
            sys.stdout = open('CONOUT$', 'w', encoding='utf-8',
                              errors='replace', buffering=1)
            sys.stderr = open('CONOUT$', 'w', encoding='utf-8',
                              errors='replace', buffering=1)
    except Exception:
        pass


if __name__ == '__main__':
    _attach_parent_console()  # 双击（GUI 无父终端）时是 no-op；终端启动时恢复输出
    _force_utf8_when_piped()
    sys.exit(main(sys.argv[1:]))
