from melobot import PluginPlanner, send_text
from melobot.handle import on_text
from melobot.utils.parse import CmdParser

VAR_PLUGIN_NAME_S = PluginPlanner("0.0.1")


@VAR_PLUGIN_NAME_S.use
@on_text(parser=CmdParser(".", " ", "VAR_PLUGIN_NAME_S"))
async def VAR_PLUGIN_NAME_S_main() -> None:
    await send_text("Hello, VAR_PLUGIN_NAME_S!\nVAR_PLUGIN_NAME_S 插件已就绪！")
