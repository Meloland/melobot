from core.Interface import ExeI, AuthRole
from common import *
from common.Action import msg_action
import asyncio as aio


@ExeI.template(
    aliases=['命令', 'command', 'cmd'], 
    userLevel=AuthRole.OWNER, 
    comment='执行一条 shell 命令',
    prompt='(命令字符串)'
)
async def shell(event: BotEvent, cmd_str: str) -> BotAction:
    proc = await aio.create_subprocess_shell(
        cmd_str,
        stderr=aio.subprocess.PIPE,
        stdout=aio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()
    if proc.returncode == 0:
        ret_str = stdout.decode(encoding='gbk').strip('\r\n')
    else:
        ret_str = stderr.decode(encoding='gbk').strip('\r\n')

    return msg_action(
        ret_str,
        event.msg.is_private(),
        event.msg.sender.id,
        event.msg.group_id,
        True
    )