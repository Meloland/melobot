from core.Executor import EXEC, AuthRole
from common import *


@EXEC.template(
    aliases=['print', '复读'], 
    userLevel=AuthRole.USER, 
    comment='复读',
    prompt='无参数',
)
async def echo(session: BotSession, text: str) -> None:
    await session.send(text)