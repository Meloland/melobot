import os
import signal
import sys
from contextlib import contextmanager
from dataclasses import dataclass

from typing_extensions import Any, Generator

from melobot._run import CLI_RUN_ALIVE_FLAG


@dataclass
class ShutdownState:
    requested: bool = False


def clear_alive_sig() -> None:
    try:
        os.remove(os.environ[CLI_RUN_ALIVE_FLAG])
    except FileNotFoundError:
        # 另一个信号处理函数或正常清理流程可能已经删除了标记。
        pass


@contextmanager
def shutdown_signals(state: ShutdownState) -> Generator[None, None, None]:
    def signal_handler(*_: Any) -> None:
        # Python 信号处理函数可能在同一线程中重入，不能在这里等待或获取锁。
        state.requested = True
        clear_alive_sig()

    signals: list[int] = [signal.SIGINT, signal.SIGTERM]
    if sys.platform == "win32":
        signals.append(signal.SIGBREAK)

    previous: dict[int, Any] = {}
    try:
        for signum in signals:
            previous[signum] = signal.signal(signum, signal_handler)
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
