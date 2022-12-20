from utils.cmdInterface import ExeI
from utils.actInterface import Builder, Encoder, msg_send_packer
from utils.globalData import BOT_STORE


comment = '帮助'
@ExeI.sync_method(alias=['帮助', 'h'], userLevel=ExeI.role.USER, comment=comment,
                    paramsTip='[命令名]')
def help(event: dict, queryCmdName: str=None) -> dict:
    if not queryCmdName:
        u_lvl = ExeI.msg_checker.get_event_lvl(event)

        # 只显示权限内可用的命令
        help_str = '\n'.join([
            f' ● {name}  （{" / ".join(ExeI.cmd_map[name].__alias__)}）'
            for name in ExeI.cmd_map.keys()
            if u_lvl >= ExeI.cmd_map[name].__auth__
        ])
        if help_str != '':
            help_str = '可用指令如下，括号内为别名：（命令可以使用别名）\n\n' \
                + help_str \
                + '\n\n此命令后跟命令名或别名获取详细信息（注意使用分隔符 {} 连接）' \
                .format(" 或 ".join(BOT_STORE["cmd"]["COMMAND_SEP"]))
    else:
        help_str = help_detail(event, queryCmdName)

    return Builder.build(
        msg_send_packer.pack(
            event,
            [Encoder.text(help_str)],
        )
    )


def help_detail(event: dict, queryCmdName: str) -> dict:
    u_lvl = ExeI.msg_checker.get_event_lvl(event)

    if queryCmdName in ExeI.alias_map.keys(): queryCmdName = ExeI.alias_map[queryCmdName]
    if queryCmdName not in ExeI.cmd_map.keys(): return '命令不存在'
    if u_lvl < ExeI.cmd_map[queryCmdName].__auth__: return '无权访问的命令'
    
    cmd_method = ExeI.cmd_map[queryCmdName]
    return "命令名：{}\n别称：{}\n说明：{}\n参数：{}\n注：方框参数为可选，括号参数为必选".format(
        queryCmdName,
        " / ".join(cmd_method.__alias__) if cmd_method.__alias__ != [] else '无',
        cmd_method.__comment__,
        cmd_method.__params__
    )

