from core.Executor import EXEC, AuthRole
from common import *


@EXEC.template(
    aliases=['stat', '状态'], 
    userLevel=AuthRole.SU, 
    comment='bot 状态',
    prompt='无参数'
)
async def status(session: BotSession) -> None:
    stat_list = [
        BOT_STORE.config.task_timeout,
        BOT_STORE.config.cooldown_time,
        BOT_STORE.config.command_start,
        BOT_STORE.config.command_sep,
        BOT_STORE.meta.cmd_mode,
        BOT_STORE.config.work_queue_len,
        BOT_STORE.meta.prior_queue_len,
        BOT_STORE.monitor.bot_start_time,
        BOT_STORE.monitor.bot_running_time
    ]
    stat_str = "bot 当前状态如下： \n\n\
 ● 任务超时时间：{}s \n\
 ● 响应冷却时间：{}s \n\
 ● 命令起始符：{} \n\
 ● 命令分隔符：{} \n\
 ● 命令解析模式：{} \n\
 ● 任务缓冲区长度：{} \n\
 ● 优先任务缓冲区长度：{} \n\
    \n启动时间：{} \n已运行时间：{}".format(*stat_list)

    await session.send(stat_str)