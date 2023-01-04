import asyncio as aio
from random import random, choice
from abc import abstractmethod, ABC
from .globalPattern import *
from .globalData import BOT_STORE
from .botEvent import *
from .botLogger import BOT_LOGGER
from . import cmdParser as cp
from .cmdInterface import ExeI


class BaseCmdExecutor(ABC, Singleton):
    """
    命令执行器基类，实现了具体的命令执行方法（包含优先命令），
    但所有子类应该根据实际情况实现 execute 方法，
    以实现各种情况下对命令的调用执行。
    """
    def __init__(self) -> None:
        super().__init__()
        self.ExeI = ExeI
    
    async def exec_cmd_list(self, event: BotEvent, cmd_list: list) -> list:
        """
        基类方法。执行一组命令，自动忽略 cmd_list 中无效的命令，
        内部实现超时控制和异常处理。
        用于各类命令执行器内部发起命令执行
        """
        action_list = []
        tasklist = []
        cmd_name_list = []

        # 特殊处理优先事件
        for cmd_seq in cmd_list:
            if cmd_seq[0] == 'prior':
                cmd_seq.pop(0)
            cmd_name = cmd_seq[0]
            cmd_name_list.append(cmd_name)
        
        for idx, cmd_name in enumerate(cmd_name_list):
            tasklist.append(aio.create_task(
                aio.wait_for(
                    self.ExeI.call(cmd_name, event, *cmd_list[idx][1:]),
                    timeout=BOT_STORE['operation']['TASK_TIMEOUT']
                )
            ))
        # 等待命令列表执行完成
        action_list = await aio.gather(*tasklist, return_exceptions=True)
        # 若有超时异常，则替换为提示信息
        for idx, action in enumerate(action_list):
            if isinstance(action, aio.exceptions.TimeoutError):
                action_list[idx] = await self.ExeI._ExecInterface__ret_sys_call(
                    'echo', 
                    event, 
                    f'命令：{" ".join(cmd_list[idx])}\n✘ 等待超时，已经放弃执行\n(；′⌒`)'
                )
        return list(filter(lambda x: x != None, action_list))

    @abstractmethod
    async def execute(self, event: dict) -> list:
        """
        抽象方法，指定 event 传入时如何识别到命令并执行
        """
        pass


class ExactCmdExecutor(BaseCmdExecutor, Singleton):
    """
    精确命令执行器类，实现从消息中精确解析命令，并执行
    """
    def __init__(self) -> None:
        super().__init__()
        self.ec_parser = cp.EC_PARSER

    async def execute(self, event: BotEvent) -> list:
        """
        精确命令执行方法，内部对事件进行精确命令列表解析。
        若存在精确命令，则执行。
        实现了单条命令执行的超时和异常控制，返回 action 列表。
        """
        cmd_list = self.ec_parser.parse(event.msg.text)
        # 命令列表为空，什么也不做返回空列表
        if cmd_list == [[]]: return []
        return await self.exec_cmd_list(event, cmd_list)



class FuzzyCmdExecutor(BaseCmdExecutor, Singleton):
    """
    模糊命令执行器，实现关键词触发命令，依赖于外部规则文件
    """
    def __init__(self) -> None:
        super().__init__()
        self.ExeI = ExeI
        self.ans_dict = BOT_STORE['data']['KEY_ANS']

    async def process_answers(self, event: BotEvent, ans_list: list) -> dict:
        """
        根据 ans 中的配置，预处理应答句子，
        再通过 echo 命令封装为 action
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
        return await self.exec_cmd_list(event, echo_cmd_list)

    async def answer(self, event: BotEvent, key_list: list) -> dict:
        """
        给定关键词，返回应答句子的 action。
        由于回复概率设置，可能返回为空。
        """
        ans_list = []
        for key in key_list:
            ans_config = self.ans_dict[key]
            # 先过一遍随机
            if ans_config['prob'] < random(): continue
            # 从 ans 列表中随机取一个
            ans = choice(ans_config['ans'])
            ans_list.append(ans)
        # 交给 process_ans 处理，会读取 ans 配置，先做一些处理，最后返回 action
        return await self.process_answers(event, ans_list)
        

    async def execute(self, event: BotEvent) -> list:
        """
        模糊命令执行方法，消息包含关键词（组合），且满足出现频率要求，
        就执行规则中指定的命令。返回为 action 列表
        """
        key_list = [key for key in self.ans_dict if key in event.msg.text]
        action_list = await self.answer(event, key_list)
        return list(filter(lambda x: x != None, action_list))


class TimeCmdExecutor(BaseCmdExecutor, Singleton):
    """
    时间命令执行器，实现对某时段消息的响应，依赖于外部规则文件
    """
    # TODO: 完成时间命令执行器
    def __init__(self) -> None:
        super().__init__()
    

    async def execute(self, event: BotEvent) -> list:
        """
        时间命令执行方法，消息满足指定时间要求，就执行规则中指定的命令。
        返回为 action 列表
        """
        return []


exact_executor = ExactCmdExecutor()
fuzzy_executor = FuzzyCmdExecutor()
time_executor = TimeCmdExecutor()


class KernelManager(Singleton):
    """
    内核事件处理器
    """
    def __init__(self) -> None:
        super().__init__()
        self.ExeI = ExeI
    
    async def handle(self, event: BotEvent) -> list:
        res = []
        if event.kernel.is_queue_full():
            res.append(await self.ExeI._ExecInterface__ret_sys_call(
                'echo', event.kernel.origin_event, '任务太多啦，等会儿叭 qwq'
            ))
        return res


class RespManager(Singleton):
    """
    响应事件处理器
    """
    def __init__(self) -> None:
        super().__init__()
        self.exact_exec = exact_executor
    
    def isBotInfoResp(self, event: BotEvent) -> bool:
        if event.resp.data is None: return False
        e_data = event.resp.data
        return len(e_data.keys()) == 2 and \
            'nickname' in e_data.keys() and 'user_id' in e_data.keys()
    
    async def handle(self, event: BotEvent) -> list:
        res = []
        if event.resp.is_failed():
            BOT_LOGGER.error(f'收到失败响应：{event.raw}')
        elif event.resp.is_processing():
            BOT_LOGGER.warning(f'收到仍在处理的响应：{event.raw}')
        elif event.resp.is_ok():
            if self.isBotInfoResp(event):
                BOT_STORE['kernel']['NICKNAME'] = event.resp.data['nickname']
                BOT_STORE['kernel']['BOT_ID'] = event.resp.data['user_id']
                BOT_LOGGER.info("已成功获得 bot 登录号相关信息")
        return res


class MetaEventManager(Singleton):
    """
    元事件上报处理器
    """
    def __init__(self) -> None:
        super().__init__()
        self.exact_exec = exact_executor
    
    async def handle(self, event: BotEvent) -> list:
        res = []
        return res


class ReqManager(Singleton):
    """
    请求上报处理器
    """
    def __init__(self) -> None:
        super().__init__()
        self.exact_exec = exact_executor
    
    async def handle(self, event: BotEvent) -> list:
        res = []
        return res


class NoticeManager(Singleton):
    """
    通知上报处理器
    """
    def __init__(self) -> None:
        super().__init__()
        self.exact_exec = exact_executor
        self.ExeI = ExeI
    
    async def handle(self, event: BotEvent) -> list:
        res = []
        if event.notice.is_poke() and event.notice.user_id == event.bot_id:
            # 如果被戳者是自己，触发 poke 命令
            # 除这里的校验外，还会在 cmdInterface 模块对消息发起者进行权限校验 
            res.append(await self.ExeI.call('poke', event))
        return res


class MsgManager(Singleton):
    """
    消息上报处理器
    """
    def __init__(self) -> None:
        super().__init__()
        self.exact_exec = exact_executor
        self.fuzzy_exec = fuzzy_executor
        self.time_exec = time_executor
        self.ExeI = ExeI
    
    async def handle(self, event: BotEvent):
        res = []
        # 若没有文本消息，返回空的 action 列表
        if event.msg.text == '': return res
        # 判断是否符合响应条件
        if event.msg.is_group_normal() or event.msg.is_friend():
            # 依次尝试执行 精确命令 -> 模糊命令 -> 时间命令
            res = await self.exact_exec.execute(event)
            if res: return res
            res = await self.fuzzy_exec.execute(event)
            if res: return res
            # 暂时不实现和使用时间命令解析器
            # res = await self.time_exec.execute(event)
            # if res: return res
        return res


class EventProcesser(Singleton):
    """
    事件处理器，调度各类事件处理器以完成对事件的响应。
    """
    def __init__(self) -> None:
        super().__init__()
        self.ExeI = ExeI
        # 该方法用于初始化需要在循环启动后获得的变量
        self.ExeI._ExecInterface__after_loop_init()
        # 对应调度策略不会增减，所以不使用策略模式
        self.kernel_m = KernelManager()
        self.resp_m = RespManager()
        self.meta_m = MetaEventManager()
        self.req_m = ReqManager()
        self.notice_m = NoticeManager()
        self.msg_m = MsgManager()
        

    async def handle(self, event: BotEvent) -> None:
        """
        对传入的事件进行响应
        """
        # 所有 handle 应该返回一个 action 列表，没有结果则是一个空列表
        if event.is_kernel():
            return await self.kernel_m.handle(event)
        elif event.is_msg():
            return await self.msg_m.handle(event)
        elif event.is_resp():
            return await self.resp_m.handle(event)
        elif event.is_notice():
            return await self.notice_m.handle(event)
        elif event.is_req():
            return await self.req_m.handle(event)
        elif event.is_meta():
            return await self.meta_m.handle(event)
        else:
            raise BotUnknownEvent("未知的事件类型")