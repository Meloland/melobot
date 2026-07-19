from argparse import Namespace

import pytest

from melobot._cli import dev, run
from melobot._cli.main import parse_args, parser
from melobot._run import CLI_RUN_ALIVE_FLAG, CLI_RUN_FLAG
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
