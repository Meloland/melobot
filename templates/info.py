from core.Interface import ExeI, AuthRole
from common import *
from common.Action import msg_action


@ExeI.template(
    aliases=['信息'], 
    userLevel=AuthRole.USER, 
    comment='获取 bot 信息', 
    prompt='无参数'
)
def info(event: BotEvent) -> BotAction:
    info_list = [
        BOT_STORE.config.bot_name,
        BOT_STORE.meta.proj_name,
        BOT_STORE.meta.version,
        BOT_STORE.meta.developer,
        BOT_STORE.meta.proj_url,
    ]
    info_str = "bot 名称：{}\n基于项目：{}\n版本：v{}\n开发信息：\n©{} \n{}".format(*info_list)
    thanks_str = "\n特别致谢：\n@Vescrity 的创意点子\nhttps://github.com/Vescrity"
    info_str += thanks_str
    
    return msg_action(
        info_str,
        event.msg.is_private(),
        event.msg.sender.id,
        event.msg.group_id,
        True
    )