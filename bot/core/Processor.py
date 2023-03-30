import asyncio as aio
import traceback
from random import random, choice
from abc import abstractmethod, ABC
from common.Typing import *
from common.Event import BotEvent
from common.Store import BOT_STORE
from common.Exceptions import *
from utils import Parser
from .Executor import EXEC, CMD_MAP, ALIAS_MAP, SYS_CMD_MAP
from asyncio import Lock


class BaseCmdExecutor(ABC):
    """
    命令执行器基类，实现了具体的命令执行方法（包含优先命令），
    但所有子类应该根据实际情况实现 execute 方法，
    以实现各种情况下对命令的调用执行。
    """
    def __init__(self) -> None:
        super().__init__()
        self.executor = EXEC
    
    async def exec_cmd_list(self, event: BotEvent, cmd_list: list) -> None:
        """
        基类方法。执行一组命令，自动忽略 cmd_list 中无效的命令，
        内部实现超时控制和异常处理。
        用于各类命令执行器内部发起命令执行
        """
        res_list = []
        tasklist = []
        cmd_name_list = []

        # 特殊处理优先事件
        for cmd_seq in cmd_list:
            if cmd_seq[0] == 'prior':
                cmd_seq.pop(0)
            cmd_name = cmd_seq[0]
            cmd_name_list.append(cmd_name)
        
        for idx, cmd_name in enumerate(cmd_name_list):
            tasklist.append(aio.create_task(aio.wait_for(
                self.executor.call(cmd_name, event, *cmd_list[idx][1:]),
                timeout=BOT_STORE.config.task_timeout
            )))
        # 等待命令执行完成，不理会传出的超时异常，异常都在内部执行时处理
        res_list = await aio.gather(*tasklist, return_exceptions=True)
        # # 若有超时异常，则替换为提示信息
        # for idx, res in enumerate(res_list):
        #     if isinstance(res, aio.exceptions.TimeoutError):
        #         await self.executor._ExecInterface__sys_call(
        #             'echo', 
        #             event, 
        #             f'命令：{" ".join(cmd_list[idx])}\n✘ 等待超时，已经放弃执行\n(；′⌒`)'
        #         )

    @abstractmethod
    async def execute(self, event: dict) -> None:
        """
        抽象方法，指定 event 传入时如何识别到命令并执行
        """
        pass


class ExactCmdExecutor(BaseCmdExecutor):
    """
    精确命令执行器类，实现从消息中精确解析命令，并执行
    """
    def __init__(self) -> None:
        super().__init__()
        self.ec_parser = Parser.EC_PARSER

    async def execute(self, event: BotEvent) -> bool:
        """
        精确命令执行方法，内部对事件进行精确命令列表解析。
        若存在精确命令，则执行。
        实现了单条命令执行的超时和异常控制。
        """
        cmd_list = self.ec_parser.parse(event.msg.text)
        # 命令列表为空，什么也不做返回空列表
        if cmd_list == [[]]: 
            return False
        else:
            await self.exec_cmd_list(event, cmd_list)
            return True


class FuzzyCmdExecutor(BaseCmdExecutor):
    """
    模糊命令执行器，实现关键词触发命令，依赖于外部规则文件
    """
    def __init__(self) -> None:
        super().__init__()
        self.executor = EXEC
        self.ans_dict = BOT_STORE.resources.key_ans.val()

    async def process_answers(self, event: BotEvent, ans_list: list) -> None:
        """
        根据 ans 中的配置，预处理应答句子，
        再通过 echo 命令执行
        """
        echo_cmd_list = []
        for ans in ans_list:
            ans_str = ans['sentence']

            if 'total-repeat' in ans.keys():
                left_bound, right_bound = ans['total-repeat'][0], ans['total-repeat'][1]
                ans_str += (ans_str*choice(
                    range(left_bound, right_bound)
                ))
            if 'ending-repeat' in ans.keys():
                left_bound, right_bound = ans['ending-repeat'][0], ans['ending-repeat'][1]
                ans_str += (ans_str[-1]*choice(
                    range(left_bound, right_bound+1)
                ))
            
            echo_cmd_list.append(['echo', ans_str])
        await self.exec_cmd_list(event, echo_cmd_list)

    async def answer(self, event: BotEvent, key_list: list) -> None:
        """
        给定关键词，做出应答
        """
        ans_list = []
        for key in key_list:
            ans_config = self.ans_dict[key]
            # 先过一遍随机
            if ans_config['prob'] < random(): continue
            # 从 ans 列表中随机取一个
            ans = choice(ans_config['ans'])
            ans_list.append(ans)
        # 交给 process_ans 处理，会读取 ans 配置，再执行
        await self.process_answers(event, ans_list)
        

    async def execute(self, event: BotEvent) -> bool:
        """
        模糊命令执行方法，消息包含关键词（组合），且满足出现频率要求，
        就执行规则中指定的命令。
        """
        key_list = [key for key in self.ans_dict if key in event.msg.text]
        if len(key_list) == 0:
            return False
        else:
            await self.answer(event, key_list)
            return True


exact_executor = ExactCmdExecutor()
fuzzy_executor = FuzzyCmdExecutor()


class MsgManager:
    """
    消息上报处理器
    """
    def __init__(self) -> None:
        self.exact_exec = exact_executor
        self.fuzzy_exec = fuzzy_executor
        self.executor = EXEC
    
    async def handle(self, event: BotEvent) -> None:
        if event.msg.text == '': return
        # 判断是否符合响应条件
        if event.msg.is_group_normal() or event.msg.is_friend():
            # 依次尝试执行 精确命令 -> 模糊命令
            if await self.exact_exec.execute(event): return
            elif await self.fuzzy_exec.execute(event): return


class KernelManager:
    """
    内核事件处理器
    """
    def __init__(self) -> None:
        self.executor = EXEC
    
    async def handle(self, event: BotEvent) -> None:
        if event.kernel.is_queue_full():
            await self.executor._ExecInterface__sys_call(
                'echo', event.kernel.origin_event, '任务太多啦，等会儿叭 qwq'
            )


class MetaEventManager:
    """
    元事件上报处理器
    """
    def __init__(self) -> None:
        self.exact_exec = exact_executor
    
    async def handle(self, event: BotEvent) -> None:
        pass


class ReqManager:
    """
    请求上报处理器
    """
    def __init__(self) -> None:
        self.exact_exec = exact_executor
    
    async def handle(self, event: BotEvent) -> None:
        pass


class NoticeManager:
    """
    通知上报处理器
    """
    def __init__(self) -> None:
        self.exact_exec = exact_executor
        self.executor = EXEC
    
    async def handle(self, event: BotEvent) -> None:
        if event.notice.is_poke() and event.notice.user_id == event.bot_id:
            # 如果被戳者是自己，触发 poke 命令
            # 除这里的校验外，还会在 cmdInterface 模块对消息发起者进行权限校验 
            await self.executor.call('poke', event)


class EventProcesser:
    """
    事件处理器，调度各类事件处理器以完成对事件的响应。
    """
    def __init__(self) -> None:
        self.executor = EXEC
        # 对应调度策略不会增减，所以不使用策略模式
        self.kernel_m = KernelManager()
        self.meta_m = MetaEventManager()
        self.req_m = ReqManager()
        self.notice_m = NoticeManager()
        self.msg_m = MsgManager()

        self.exec_load_lock = Lock()
        self.exec_load_flag = False
        
    async def build_executor(self) -> None:
        """
        异步加载和存储命令接口的资源
        """
        async with self.exec_load_lock:
            if self.exec_load_flag: 
                return
            self.exec_load_flag = True
            await EXEC._ExecInterface__load_cmd_funcs(CMD_MAP, SYS_CMD_MAP, ALIAS_MAP)
            # 该方法用于初始化需要在循环启动后获得的变量
            self.executor._ExecInterface__after_loop_init()

    async def handle(self, event: BotEvent) -> None:
        """
        对传入的事件进行响应
        """
        try:
            if event.is_kernel():
                await self.kernel_m.handle(event)
            elif event.is_msg():
                await self.msg_m.handle(event)
            elif event.is_notice():
                await self.notice_m.handle(event)
            elif event.is_req():
                await self.req_m.handle(event)
            elif event.is_meta():
                await self.meta_m.handle(event)
            else:
                raise BotUnknownEvent("未知的事件类型")
        except aio.TimeoutError:
            pass
        except BotUnknownEvent:
            BOT_STORE.logger.warning(f'出现 bot 未知事件：{event.raw}')
        except Exception as e:
            BOT_STORE.logger.debug(traceback.format_exc())
            BOT_STORE.logger.error(f'内部发生预期外的异常：{e}，事件为：{event.raw}（bot 仍在运行）')