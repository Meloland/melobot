from core.Executor import EXEC, AuthRole
from common import *
from common.Exceptions import BotUnknownCmd


@EXEC.template(
    aliases=['帮助', 'h'], 
    userLevel=AuthRole.USER, 
    comment='获取帮助',
    prompt='[命令名]'
)
async def help(session: BotSession, queryCmdName: str=None) -> None:
    event = session.event

    if not queryCmdName:
        u_lvl = EXEC.msg_checker.get_event_lvl(event)

        # 只显示权限内可用的命令
        help_str = '\n'.join([
            f'{name}  {"(" + " / ".join(EXEC.get_cmd_aliases(name)) + ")" if EXEC.get_cmd_aliases(name) != [] else ""}'
            for name in EXEC.cmd_map.keys()
            if u_lvl >= EXEC.get_cmd_auth(name)
        ])
        if help_str != '':
            help_str = '可用指令如下。括号内为别名，~help#命令名 获取详细帮助。\n\n' \
                + help_str
    else:
        help_str = help_detail(event, queryCmdName)

    await session.send(help_str)


def help_detail(event: BotEvent, queryName: str) -> str:
    u_lvl = EXEC.msg_checker.get_event_lvl(event)

    try:
        cmdName = EXEC.get_cmd_name(queryName)
    except BotUnknownCmd:
        return '命令不存在'
    if u_lvl < EXEC.get_cmd_auth(cmdName):
        return '无权访问的命令'

    aliases = EXEC.get_cmd_aliases(cmdName)
    return "命令名：{}\n别称：{}\n说明：{}\n参数：{}\n注：方框参数为可选，括号参数为必选".format(
        cmdName,
        " / ".join(aliases) if aliases != [] else '无',
        EXEC.get_cmd_comment(cmdName),
        EXEC.get_cmd_prompt(cmdName)
    )

