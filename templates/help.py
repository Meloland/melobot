from utils.Interface import ExeI, AuthRole
from utils.Event import *
from utils.Action import msg_action, BotAction
from utils.Definition import *


@ExeI.template(
    aliases=['帮助', 'h'], 
    userLevel=AuthRole.USER, 
    comment='获取帮助',
    prompt='[命令名]'
)
def help(event: BotEvent, queryCmdName: str=None) -> BotAction:
    if not queryCmdName:
        u_lvl = ExeI.msg_checker.get_event_lvl(event)

        # 只显示权限内可用的命令
        help_str = '\n'.join([
            f' ● {name}  {"（" + " / ".join(ExeI.get_cmd_aliases(name)) + "）" if ExeI.get_cmd_aliases(name) != [] else ""}'
            for name in ExeI.cmd_map.keys()
            if u_lvl >= ExeI.get_cmd_auth(name)
        ])
        if help_str != '':
            help_str = '可用指令如下，括号内为别名：（命令可以使用别名）\n\n' \
                + help_str \
                + '\n\n此命令后跟命令名或别名获取详细帮助'
    else:
        help_str = help_detail(event, queryCmdName)

    return msg_action(
        help_str,
        event.msg.is_private(),
        event.msg.sender.id,
        event.msg.group_id,
        True
    )


def help_detail(event: BotEvent, queryName: str) -> str:
    u_lvl = ExeI.msg_checker.get_event_lvl(event)

    try:
        cmdName = ExeI.get_cmd_name(queryName)
    except BotUnknownCmdName:
        return '命令不存在'
    if u_lvl < ExeI.get_cmd_auth(cmdName):
        return '无权访问的命令'

    aliases = ExeI.get_cmd_aliases(cmdName)
    return "命令名：{}\n别称：{}\n说明：{}\n参数：{}\n注：方框参数为可选，括号参数为必选".format(
        cmdName,
        " / ".join(aliases) if aliases != [] else '无',
        ExeI.get_cmd_comment(cmdName),
        ExeI.get_cmd_paramsTip(cmdName)
    )

