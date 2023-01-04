from utils.cmdInterface import ExeI, AuthRole
from utils.botEvent import *
from utils.botAction import Builder, Encoder, msg_send_packer
from utils.globalData import BOT_STORE


@ExeI.template(
    aliases=['信息'], 
    userLevel=AuthRole.USER, 
    comment='获取 bot 信息', 
    prompt='无参数'
)
def info(event: BotEvent) -> dict:
    info_list = [
        BOT_STORE['custom']['BOT_NAME'],
        BOT_STORE['kernel']['PROJ_NAME'],
        BOT_STORE['kernel']['VERSION'],
        BOT_STORE['kernel']['DEVELOPER'],
        BOT_STORE['kernel']['PROJ_URL'],
    ]
    info_str = "bot 名称：{}\n项目名称：{}\n版本：v{}\n开发者：{}\n项目地址：{} ".format(*info_list)
    
    action = Builder.build(
        msg_send_packer.pack(
            event,
            [Encoder.text(info_str, fromEvent=False)],
        )
    )
    return action