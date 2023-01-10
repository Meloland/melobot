from core.Interface import ExeI, AuthRole
from common import *
from common.Action import msg_action


@ExeI.template(
    aliases=['stat', '状态'], 
    userLevel=AuthRole.SU, 
    comment='bot 状态',
    prompt='无参数'
)
def status(event: BotEvent) -> BotAction:
    stat_list = [
        BOT_STORE['operation']['TASK_TIMEOUT'],
        BOT_STORE['operation']['COOLDOWN_TIME'],
        BOT_STORE['cmd']['COMMAND_START'],
        BOT_STORE['cmd']['COMMAND_SEP'],
        BOT_STORE['kernel']['CMD_MODE'],
        BOT_STORE['operation']['WORK_QUEUE_LEN'],
        BOT_STORE['kernel']['PRIOR_QUEUE_LEN'],
        BOT_STORE['kernel']['THREAD_NUM'],
        BOT_STORE['kernel']['EVENT_HANDLER_NUM'],
        BOT_STORE['kernel']['MONITOR'].bot_start_time,
        BOT_STORE['kernel']['MONITOR'].bot_running_time,
    ]
    stat_str = "bot 当前状态如下： \n\n\
 ● 任务超时时间：{}s \n\
 ● 响应冷却时间：{}s \n\
 ● 命令起始符：{} \n\
 ● 命令分隔符：{} \n\
 ● 命令解析模式：{} \n\
 ● 任务缓冲区长度：{} \n\
 ● 优先任务缓冲区长度：{} \n\
 ● 线程池最大线程数：{} \n\
 ● 可工作的调度器数：{} \n\
    \n启动时间：{} \n已运行时间：{}".format(*stat_list)

    return msg_action(
        stat_str,
        event.msg.is_private(),
        event.msg.sender.id,
        event.msg.group_id,
        True
    )