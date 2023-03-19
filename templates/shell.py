from core.Executor import EXEC, AuthRole
from common import *
import asyncio as aio


@EXEC.template(
    aliases=['命令', 'command', 'cmd'], 
    userLevel=AuthRole.OWNER, 
    comment='执行一条 shell 命令',
    prompt='(命令字符串)'
)
async def shell(session: BotSession, cmd_str: str) -> None:
    proc = await aio.create_subprocess_shell(
        cmd_str,
        stderr=aio.subprocess.PIPE,
        stdout=aio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()
    if stderr == b'':
        ret_str = stdout.decode(encoding='gbk').strip('\r\n')
    else:
        ret_str = stderr.decode(encoding='gbk').strip('\r\n')

    await session.send(ret_str)
