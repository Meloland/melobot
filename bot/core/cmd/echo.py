from common.Event import BotEvent
from common.Action import msg_action, BotAction


def echo(event: BotEvent, text: str) -> BotAction:
    """
    系统内部专用回显指令，用于发出提示消息等功能。
    独立于用户级 echo 调用，实现权限分离
    """
    return msg_action(
        text,
        event.msg.is_private(),
        event.msg.sender.id,
        event.msg.group_id,
        triggerEvent=event
    )