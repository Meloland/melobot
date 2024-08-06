from os import listdir as _melobot_runtime_listdir
from pathlib import Path as _MeloBotRuntimePathClass

from melobot.bot import get_bot as _melobot_runtime_get_bot
from melobot.plugin.load import plugin_get_attr as _melobot_runtime_get_attr

__PLUGIN_PATH__ = _MeloBotRuntimePathClass(__file__).parent
__PLUGIN_RELATIVES__ = set(
    fname.split(".")[0] for fname in _melobot_runtime_listdir(__PLUGIN_PATH__)
)


def __getattr__(name):
    if name in __PLUGIN_RELATIVES__:
        raise AttributeError
    else:
        return _melobot_runtime_get_attr(
            _melobot_runtime_get_bot, __PLUGIN_PATH__.parts[-1], name
        )
