from core.Executor import EXEC, AuthRole
from common import *
from common.Exceptions import BotCmdExecFailed


@EXEC.template(
    aliases=['life', 'lc'], 
    userLevel=AuthRole.SU, 
    isLocked=True,
    comment='生命周期控制',
    prompt='[on / off / close]'
)
async def lifecycle(session: BotSession, subCmd: str) -> None:
    if subCmd == 'on': 
        await lifecycle_on(session)
    elif subCmd == 'off': 
        await lifecycle_off(session)
    elif subCmd == 'close': 
        await lifecycle_close(session)
    else:
        raise BotCmdExecFailed("无效的控制参数")


async def lifecycle_on(session: BotSession) -> None:
    """
    开启响应功能
    """
    bot_name = BOT_STORE.config.bot_name 
    if BOT_STORE.meta.working_status == True:
        await session.send(f'{bot_name}已经在工作啦 >w<')
    else:
        BOT_STORE.meta.working_status = True
        BOT_STORE.logger.info('bot 工作状态变更为：on')
        await session.send(f'{bot_name}回来啦 owo')


async def lifecycle_off(session: BotSession) -> None:
    """
    关闭响应功能
    """
    bot_name = BOT_STORE.config.bot_name 
    if BOT_STORE.meta.working_status == False:
        return
    else:
        BOT_STORE.meta.working_status = False
        BOT_STORE.logger.info('bot 工作状态变更为：off')
        await session.send(f'{bot_name}去休息了~')


async def lifecycle_close(session: BotSession) -> None:
    """
    关闭 bot
    """
    bot_name = BOT_STORE.config.bot_name 
    monitor = BOT_STORE.monitor
    await session.send(f'{bot_name}下班了捏', waitResp=True)
    await monitor.stop_kernel()
