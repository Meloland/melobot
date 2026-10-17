import os
import signal
import subprocess
import sys
import textwrap
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from melobot._cli import _signal, dev, run
from melobot._cli.main import parse_args, parser
from melobot._run import CLI_LAST_EXIT_CODE, CLI_RUN_ALIVE_FLAG, CLI_RUN_FLAG
from melobot.typ import ExitCode


def test_run_passes_arguments_after_separator_to_bot() -> None:
    args = parser.parse_args(["run", "bot.py", "--", "--debug", "--config", "config.toml"])

    assert args.entry_file == "bot.py"
    assert args.bot_args == ["--debug", "--config", "config.toml"]


def test_run_help_is_still_handled_by_mb() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["run", "bot.py", "--help"])

    assert exc_info.value.code == 0


def test_run_parser_has_a_list_of_bot_arguments() -> None:
    args = parser.parse_args(["run", "bot.py"])

    assert isinstance(args.bot_args, list)
    assert args.bot_args == []


def test_run_launches_bot_with_forwarded_arguments(tmp_path, monkeypatch) -> None:
    entry_file = tmp_path.joinpath("bot.py")
    entry_file.touch()
    commands: list[list[str]] = []

    class FakeProcess:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def wait(self):
            return ExitCode.NORMAL.value

    def fake_popen(command, **_):
        commands.append(command)
        return FakeProcess()

    monkeypatch.delenv(CLI_RUN_FLAG, raising=False)
    monkeypatch.delenv(CLI_RUN_ALIVE_FLAG, raising=False)
    monkeypatch.setattr(run.subprocess, "Popen", fake_popen)

    run.main(Namespace(entry_file=str(entry_file), bot_args=["--debug"]))

    assert commands == [[run.sys.executable, entry_file.resolve().as_posix(), "--debug"]]


def test_dev_passes_arguments_after_separator_to_bot() -> None:
    args = parse_args(["dev", "bot.py", "--watch", "src", "plugins", "--", "--debug"])

    assert args.entry_file == "bot.py"
    assert args.watch == ["src", "plugins"]
    assert args.bot_args == ["--debug"]


def test_dev_launches_bot_with_forwarded_arguments(tmp_path, monkeypatch) -> None:
    entry_file = tmp_path.joinpath("bot.py")
    entry_file.touch()
    commands: list[list[str]] = []

    class FakeObserver:
        def schedule(self, *_args, **_kwargs):
            return None

        def start(self):
            return None

        def stop(self):
            return None

        def join(self):
            return None

    class FakeHandler:
        def __init__(self, *_args):
            pass

    class FakeProcess:
        returncode = ExitCode.NORMAL.value

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def wait(self):
            return self.returncode

    def fake_popen(command, **_):
        commands.append(command)
        return FakeProcess()

    monkeypatch.delenv(CLI_RUN_FLAG, raising=False)
    monkeypatch.delenv(CLI_RUN_ALIVE_FLAG, raising=False)
    monkeypatch.setattr(dev, "get_requires", lambda: (FakeObserver, FakeHandler))
    monkeypatch.setattr(dev.subprocess, "Popen", fake_popen)

    dev.main(Namespace(entry_file=str(entry_file), watch=[str(tmp_path)], bot_args=["--debug"]))

    assert commands == [[dev.sys.executable, entry_file.resolve().as_posix(), "--debug"]]


def _request_shutdown():
    handler = signal.getsignal(signal.SIGTERM)
    assert callable(handler)
    handler(signal.SIGTERM, None)


def _cli_harness(module, tmp_path, monkeypatch, codes=(0,), on_spawn=None):
    entry = tmp_path / "bot.py"
    entry.touch()
    for key in (CLI_RUN_FLAG, CLI_RUN_ALIVE_FLAG, CLI_LAST_EXIT_CODE):
        monkeypatch.delenv(key, raising=False)
    harness = SimpleNamespace(
        args=Namespace(entry_file=str(entry), bot_args=["--debug"], watch=[str(tmp_path)]),
        launches=[],
        observer_events=[],
        reload_signal=None,
        wait_error=None,
        start_error=None,
    )

    class Observer:
        def schedule(self, handler, *_args, **_kwargs):
            harness.reload_signal = handler.reload_signal

        def start(self):
            harness.observer_events.append("start")
            if harness.start_error is not None:
                raise harness.start_error

        def stop(self):
            harness.observer_events.append("stop")

        def join(self):
            harness.observer_events.append("join")

    class Handler:
        def __init__(self, _path, reload_signal):
            self.reload_signal = reload_signal

    class Process:
        def __init__(self, command, **_kwargs):
            self.returncode = codes[len(harness.launches)]
            harness.launches.append(
                (
                    command.copy(),
                    os.environ.get(CLI_LAST_EXIT_CODE),
                    signal.getsignal(signal.SIGTERM),
                )
            )
            if on_spawn is not None:
                on_spawn()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            if harness.wait_error is not None:
                assert not Path(os.environ[CLI_RUN_ALIVE_FLAG]).exists()

        def wait(self):
            if harness.wait_error is not None:
                raise harness.wait_error
            return self.returncode

    if module is dev:
        monkeypatch.setattr(dev, "get_requires", lambda: (Observer, Handler))
    monkeypatch.setattr(module.subprocess, "Popen", Process)
    return harness


@pytest.mark.parametrize("missing", [False, True, "parent"])
def test_clear_alive_sig_is_idempotent(tmp_path, monkeypatch, missing):
    marker = tmp_path / "alive.signal"
    if missing == "parent":
        marker = tmp_path / "absent" / "alive.signal"
    elif not missing:
        marker.touch()
    monkeypatch.setenv(CLI_RUN_ALIVE_FLAG, str(marker))

    _signal.clear_alive_sig()
    _signal.clear_alive_sig()

    assert not marker.exists()


def test_clear_alive_sig_preserves_permission_errors(tmp_path, monkeypatch):
    marker = tmp_path / "alive.signal"
    marker.touch()
    monkeypatch.setenv(CLI_RUN_ALIVE_FLAG, str(marker))

    def denied(_path):
        raise PermissionError("cannot delete marker")

    monkeypatch.setattr(_signal.os, "remove", denied)
    with pytest.raises(PermissionError, match="cannot delete marker"):
        _signal.clear_alive_sig()
    assert marker.exists()


@pytest.mark.parametrize("fail", [False, True])
def test_shutdown_signals_handle_nested_callbacks_and_restore(tmp_path, monkeypatch, fail):
    marker = tmp_path / "alive.signal"
    marker.touch()
    monkeypatch.setenv(CLI_RUN_ALIVE_FLAG, str(marker))
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    remove = os.remove
    calls = []

    def nested_remove(path):
        calls.append(path)
        if len(calls) == 1:
            _request_shutdown()
        remove(path)

    monkeypatch.setattr(_signal.os, "remove", nested_remove)
    state = _signal.ShutdownState()
    try:
        with _signal.shutdown_signals(state):
            _request_shutdown()
            assert state.requested
            assert not marker.exists()
            if fail:
                raise RuntimeError("body failed")
    except RuntimeError as exc:
        assert fail
        assert str(exc) == "body failed"

    assert len(calls) == 2
    assert {sig: signal.getsignal(sig) for sig in previous} == previous


def test_shutdown_signals_register_and_restore_sigbreak(monkeypatch):
    fake_break = 999
    original = {signal.SIGINT: object(), signal.SIGTERM: object(), fake_break: object()}
    installed = original.copy()

    def install(signum, handler):
        previous = installed[signum]
        installed[signum] = handler
        return previous

    with monkeypatch.context() as patch:
        patch.setattr(_signal.sys, "platform", "win32")
        patch.setattr(signal, "SIGBREAK", fake_break, raising=False)
        patch.setattr(signal, "signal", install)
        patch.setattr(_signal, "clear_alive_sig", lambda: None)
        state = _signal.ShutdownState()
        with _signal.shutdown_signals(state):
            installed[fake_break](fake_break, None)
            assert state.requested
        assert installed == original


@pytest.mark.parametrize("module", [run, dev], ids=["run", "dev"])
def test_cli_restart_preserves_arguments_and_signal_handler(tmp_path, monkeypatch, module):
    harness = _cli_harness(module, tmp_path, monkeypatch, codes=(2, 0))
    previous = signal.getsignal(signal.SIGTERM)

    module.main(harness.args)

    assert len(harness.launches) == 2
    assert harness.launches[0][0] == harness.launches[1][0]
    assert harness.launches[1][0][-1] == "--debug"
    assert [launch[1] for launch in harness.launches] == [None, "2"]
    assert harness.launches[0][2] is harness.launches[1][2]
    assert signal.getsignal(signal.SIGTERM) is previous
    assert not Path(os.environ[CLI_RUN_ALIVE_FLAG]).parent.exists()
    if module is dev:
        assert harness.observer_events == ["start", "stop", "join"]


@pytest.mark.parametrize("module", [run, dev], ids=["run", "dev"])
def test_cli_shutdown_during_spawn_overrides_restart(tmp_path, monkeypatch, module):
    def stop_twice():
        _request_shutdown()
        _request_shutdown()
        assert not Path(os.environ[CLI_RUN_ALIVE_FLAG]).exists()

    harness = _cli_harness(module, tmp_path, monkeypatch, codes=(2,), on_spawn=stop_twice)
    module.main(harness.args)

    assert len(harness.launches) == 1
    assert not Path(os.environ[CLI_RUN_ALIVE_FLAG]).parent.exists()


@pytest.mark.parametrize("module", [run, dev], ids=["run", "dev"])
@pytest.mark.parametrize("stop_before_creation", [False, True])
def test_cli_shutdown_during_marker_creation_prevents_spawn(
    tmp_path, monkeypatch, module, stop_before_creation
):
    harness = _cli_harness(module, tmp_path, monkeypatch)
    create = module.create_alive_sig

    def interrupted_create():
        if stop_before_creation:
            _request_shutdown()
        create()
        if not stop_before_creation:
            _request_shutdown()

    monkeypatch.setattr(module, "create_alive_sig", interrupted_create)
    module.main(harness.args)

    assert not harness.launches
    assert not Path(os.environ[CLI_RUN_ALIVE_FLAG]).parent.exists()


@pytest.mark.parametrize("module", [run, dev], ids=["run", "dev"])
def test_cli_handles_signals_until_cleanup_completes(tmp_path, monkeypatch, module):
    harness = _cli_harness(module, tmp_path, monkeypatch)
    previous = signal.getsignal(signal.SIGTERM)
    rmtree = module.shutil.rmtree

    def interrupted_cleanup(path):
        _request_shutdown()
        rmtree(path)
        _request_shutdown()

    monkeypatch.setattr(module.shutil, "rmtree", interrupted_cleanup)
    module.main(harness.args)

    assert signal.getsignal(signal.SIGTERM) is previous
    assert not Path(os.environ[CLI_RUN_ALIVE_FLAG]).parent.exists()


@pytest.mark.parametrize("module", [run, dev], ids=["run", "dev"])
@pytest.mark.parametrize("failure", ["spawn", "wait", "cleanup"])
def test_cli_cleans_resources_and_restores_handlers_on_errors(
    tmp_path, monkeypatch, module, failure
):
    harness = _cli_harness(module, tmp_path, monkeypatch)
    previous = signal.getsignal(signal.SIGTERM)

    def failed_spawn(*_args, **_kwargs):
        raise RuntimeError("spawn failed")

    def failed_clear():
        raise PermissionError("cleanup failed")

    if failure == "spawn":
        monkeypatch.setattr(module.subprocess, "Popen", failed_spawn)
    elif failure == "wait":
        harness.wait_error = RuntimeError("wait failed")
    else:
        monkeypatch.setattr(module, "clear_alive_sig", failed_clear)

    with pytest.raises((RuntimeError, PermissionError), match=f"{failure} failed"):
        module.main(harness.args)

    assert signal.getsignal(signal.SIGTERM) is previous
    assert not Path(os.environ[CLI_RUN_ALIVE_FLAG]).parent.exists()
    if module is dev:
        assert harness.observer_events == ["start", "stop", "join"]
        if failure == "wait":
            assert harness.reload_signal.is_set()


def test_dev_does_not_join_observer_when_start_fails(tmp_path, monkeypatch):
    harness = _cli_harness(dev, tmp_path, monkeypatch)
    harness.start_error = RuntimeError("observer failed")
    previous = signal.getsignal(signal.SIGTERM)

    with pytest.raises(RuntimeError, match="observer failed"):
        dev.main(harness.args)

    assert harness.observer_events == ["start", "stop"]
    assert signal.getsignal(signal.SIGTERM) is previous
    assert not Path(os.environ[CLI_RUN_ALIVE_FLAG]).parent.exists()


@pytest.mark.parametrize("stop", [False, True])
def test_dev_reload_and_shutdown_priority(tmp_path, monkeypatch, stop):
    harness = _cli_harness(dev, tmp_path, monkeypatch, codes=(0, 0))
    wait = dev.concurrent.futures.wait

    def reload_or_stop(*args, **kwargs):
        if len(harness.launches) == 1:
            harness.reload_signal.set()
            if stop:
                _request_shutdown()
        return wait(*args, **kwargs)

    monkeypatch.setattr(dev.concurrent.futures, "wait", reload_or_stop)
    dev.main(harness.args)

    assert len(harness.launches) == (1 if stop else 2)
    assert not Path(os.environ[CLI_RUN_ALIVE_FLAG]).parent.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX waitpid and nested SIGTERM")
def test_nested_sigterm_during_wait_does_not_deadlock(tmp_path):
    probe = textwrap.dedent(
        """
        import os
        import signal
        import subprocess
        import sys
        from pathlib import Path
        from melobot._cli._signal import ShutdownState, shutdown_signals
        from melobot._run import CLI_RUN_ALIVE_FLAG

        marker = Path(sys.argv[1])
        marker.touch()
        os.environ[CLI_RUN_ALIVE_FLAG] = str(marker)
        state = ShutdownState()
        remove = os.remove
        nested = False

        def nested_remove(path):
            global nested
            if not nested:
                nested = True
                signal.raise_signal(signal.SIGTERM)
            remove(path)

        with subprocess.Popen([sys.executable, '-c', 'pass']) as proc:
            try_wait = proc._try_wait
            injected = False
            def interrupted_wait(flags):
                global injected
                if not injected:
                    injected = True
                    assert proc._waitpid_lock.locked()
                    signal.raise_signal(signal.SIGTERM)
                return try_wait(flags)

            proc._try_wait = interrupted_wait
            with shutdown_signals(state):
                os.remove = nested_remove
                try:
                    assert proc.wait() == 0
                finally:
                    os.remove = remove

        assert state.requested
        assert nested
        assert not marker.exists()
        """
    )
    env = os.environ.copy()
    source = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (source, env.get("PYTHONPATH"))))
    result = subprocess.run(
        [sys.executable, "-c", probe, str(tmp_path / "alive.signal")],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stdout + result.stderr
