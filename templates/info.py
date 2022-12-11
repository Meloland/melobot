from utils.cmdInterface import ExeI
from utils.actInterface import Builder, Encoder, msg_send_packer
from utils.globalData import BOT_STORE


comment = 'bot 信息'
@ExeI.sync_method(alias=['信息'], userLevel=ExeI.role.USER, comment=comment, 
                    paramsTip='无参数')
def info(event: dict) -> dict:
    info_list = [
        BOT_STORE['kernel']['BOT_NAME_INFO'],
        BOT_STORE['kernel']['VERSION'],
        BOT_STORE['kernel']['DEVELOPER'],
        BOT_STORE['kernel']['PROJ_URL'],        
    ]
    info_str = "bot 信息：\n名称：{}\n版本：v{}\n开发者：{}\n项目地址：{} ".format(*info_list)
    
    action = Builder.build(
        msg_send_packer.pack(
            event,
            [Encoder.text(info_str, fromEvent=False)],
        )
    )
    return action