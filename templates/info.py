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
        BOT_STORE['custom']['BOT_NAME'],
        BOT_STORE['kernel']['PROJ_NAME'],
        BOT_STORE['kernel']['VERSION'],
        BOT_STORE['kernel']['DEVELOPER'],
        BOT_STORE['kernel']['PROJ_URL'],
    ]
    info_str = "bot 名称：{}\n项目名称：{}\n版本：v{}\n开发者：{}\n项目地址：{} ".format(*info_list)
    
    return msg_action(
        info_str,
        event.msg.is_private(),
        event.msg.sender.id,
        event.msg.group_id,
        True
    )