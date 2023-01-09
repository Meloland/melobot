import asyncio as aio
from utils.Interface import ExeI, AuthRole
from utils.Event import *
from utils.Action import msg_action, BotAction
from utils.Definition import BotCmdExecFailed
from utils.Store import BOT_STORE
from utils.Logger import BOT_LOGGER


@ExeI.template(
    aliases=['life', 'lc'], 
    userLevel=AuthRole.SU, 
    isLocked=True,
    comment='生命周期控制',
    prompt='[on / off / close]'
)
async def lifecycle(event: BotEvent, subCmd: str) -> BotAction:
    if subCmd == 'on': 
        return lifecycle_on(event)
    elif subCmd == 'off': 
        return lifecycle_off(event)
    elif subCmd == 'close': 
        return await lifecycle_close(event)
    else:
        raise BotCmdExecFailed("无效的子指令")


def lifecycle_on(event: BotEvent) -> BotAction:
    """
    开启响应功能
    """
    bot_name = BOT_STORE['custom']['BOT_NAME']
    if BOT_STORE['kernel']['WORKING_STATUS'] == True:
        action = text_action(event, f'{bot_name}已经在工作啦 >w<')
    else:
        BOT_STORE['kernel']['WORKING_STATUS'] = True
        BOT_LOGGER.info('bot 工作状态变更为：on')
        action = text_action(event, f'{bot_name}回来啦 owo')
    return action


def lifecycle_off(event: BotEvent) -> BotAction:
    """
    关闭响应功能
    """
    bot_name = BOT_STORE['custom']['BOT_NAME']
    if BOT_STORE['kernel']['WORKING_STATUS'] == False:
        return
    else:
        BOT_STORE['kernel']['WORKING_STATUS'] = False
        BOT_LOGGER.info('bot 工作状态变更为：off')
        action = text_action(event, f'{bot_name}去休息了~')
        return action


async def lifecycle_close(event: BotEvent) -> None:
    """
    关闭 bot
    """
    bot_name = BOT_STORE['custom']['BOT_NAME']
    monitor = BOT_STORE['kernel']['MONITOR']
    pre_action = text_action(event, f'{bot_name}下班了捏')
    # 变相让 monitor 做代理，直接向 handler 发送 action
    # 因为关闭 bot 后，再无法发送任何 action
    await monitor.place_prior_action(pre_action)
    # 现在线程是加锁的状态，因此需要 IO 来切换线程，顺便给时间让 action 被发出去
    await aio.sleep(3)
    await monitor.stop_bot()
    return


def text_action(event: BotEvent, text: str) -> BotAction:
    return msg_action(
        text,
        event.msg.is_private(),
        event.msg.sender.id,
        event.msg.group_id,
        True
    )