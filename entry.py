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


class _SafeStream:
    """包一层 stdout/stderr：句柄无效 / 已关闭导致写失败时不再抛异常，静默丢弃。

    frozen windowed exe（console=False）在无控制台上下文里，sys.stdout 可能是
    一个「非 None、但一写就 OSError」的坏对象，CLI 分支（如 --help）的 print
    会直接把程序打崩（实测：entry.py:48 → __main__.py:35 print(USAGE) →
    OSError [Errno 22] Invalid argument）。这里统一兜住，任何 print 都不会中断启动。
    """

    def __init__(self, raw):
        self._raw = raw

    def write(self, s):
        try:
            return self._raw.write(s)
        except (OSError, ValueError):
            return len(s) if s else 0

    def flush(self):
        try:
            self._raw.flush()
        except (OSError, ValueError):
            pass

    def __getattr__(self, name):  # isatty / reconfigure / encoding 等一律透传
        return getattr(object.__getattribute__(self, '_raw'), name)


def _guard_std_streams():
    """保证 sys.stdout/stderr 一定能写：None → devnull；坏句柄 → 吞异常的安全包装。"""
    for name in ('stdout', 'stderr'):
        s = getattr(sys, name)
        if s is None:
            try:
                s = open(os.devnull, 'w', encoding='utf-8')
            except OSError:
                s = None
        else:
            s = _SafeStream(s)
        setattr(sys, name, s)


if __name__ == '__main__':
    _attach_parent_console()  # 双击（GUI 无父终端）时是 no-op；终端启动时恢复输出
    _guard_std_streams()      # 兜底：无控制台/坏句柄下 print 不再抛 OSError 打崩启动
    _force_utf8_when_piped()
    sys.exit(main(sys.argv[1:]))
