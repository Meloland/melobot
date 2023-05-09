from core.Executor import EXEC, AuthRole
from common import *


@EXEC.template(
    aliases=['信息'], 
    userLevel=AuthRole.USER, 
    comment='获取 bot 信息', 
    prompt='无参数'
)
async def info(session: BotSession) -> None:
    info_list = [
        BOT_STORE.config.bot_name,
        BOT_STORE.meta.proj_name,
        BOT_STORE.meta.version,
        BOT_STORE.meta.platform,
        'AiCorein',
        BOT_STORE.meta.proj_url,
    ]
    info_str = "bot 名称：{}\n内核版本：{} v{}\n系统环境：{}\n开发信息：\n@{} \n{}".format(*info_list)
    thanks_str = "\n特别致谢：\n@Vescrity 的创意点子\nhttps://github.com/Vescrity"
    info_str += thanks_str
    
    await session.send(info_str)