import sys

sys.path.append("../../../src")
from melobot.bot import get_bot
from melobot.plugin.auto import get_plugin_attr


def __getattr__(name):
    return get_plugin_attr(get_bot(), "__PLUGIN_NAME__", name)
