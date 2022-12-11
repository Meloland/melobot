import asyncio as aio
from random import random, choice
from abc import abstractmethod, ABC
from .globalPattern import *
from .globalData import BOT_STORE
from .botLogger import BOT_LOGGER
from . import authority as au
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
    
    async def exec_cmd_list(self, event: dict, cmd_list: list) -> list:
        """
        低级 api，执行一组命令，自动忽略 cmd_list 中无效的命令，
        内部实现超时控制和异常处理。
        应尽量调用 execute 方法
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
                action_list[idx] = await self.ExeI.sys_call(
                    'echo', 
                    event, 
                    f'命令：{" ".join(cmd_list[idx])}\n\n✘ 等待超时，已经放弃执行\n(；′⌒`)'
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

    async def execute(self, event: dict) -> list:
        """
        精确命令执行方法，内部对事件进行精确命令列表解析。
        若存在精确命令，则执行。
        实现了单条命令执行的超时和异常控制，返回 action 列表。
        """
        cmd_list = self.ec_parser.parse(event['raw_message'])
        # 命令列表为空，什么也不做返回空列表
        if cmd_list == [[]]: return []
        return await self.exec_cmd_list(event, cmd_list)



class FuzzyCmdExecutor(BaseCmdExecutor, Singleton):
    """
    模糊命令执行器，实现关键词触发命令，依赖于外部规则文件
    """
    # TODO: 完成模糊命令执行器
    def __init__(self) -> None:
        super().__init__()
        self.ExeI = ExeI
        self.ans_dict = BOT_STORE['data']['KEY_ANS']

    async def process_answers(self, event: dict, ans_list: list) -> dict:
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

    async def answer(self, event: dict, key_list: list) -> dict:
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
        

    async def execute(self, event: dict) -> list:
        """
        模糊命令执行方法，消息包含关键词（组合），且满足出现频率要求，
        就执行规则中指定的命令。返回为 action 列表
        """
        key_list = [key for key in self.ans_dict if key in event['raw_message']]
        action_list = await self.answer(event, key_list)
        return list(filter(lambda x: x != None, action_list))


class TimeCmdExecutor(BaseCmdExecutor, Singleton):
    """
    时间命令执行器，实现对某时段消息的响应，依赖于外部规则文件
    """
    # TODO: 完成时间命令执行器
    def __init__(self) -> None:
        super().__init__()
    

    async def execute(self, event: dict) -> list:
        """
        时间命令执行方法，消息满足指定时间要求，就执行规则中指定的命令。
        返回为 action 列表
        """
        return []


exact_executor = ExactCmdExecutor()
fuzzy_executor = FuzzyCmdExecutor()
time_executor = TimeCmdExecutor()


class EventFilter(Singleton):
    """
    事件过滤器，提供基本的事件类型判断方法，
    仅供事件处理器区分应该交给哪个事件处理器处理
    """
    def __init__(self) -> None:
        pass

    # 内核事件判断
    def isKernelReport(self, event: dict) -> bool: return event['post_type'] in BOT_STORE['kernel']['EVENT_TYPE'].values()
    # 响应事件判断
    def isResp(self, event: dict) -> bool: return 'retcode' in event.keys()
    # 元上报判断
    def isMetaReport(self, event: dict) -> bool: return event['post_type'] == 'meta_event'
    # 请求上报判断
    def isReqReport(self, event: dict) -> bool: return event['post_type'] == 'request'
    # 通知上报判断
    def isNoticeReport(self, event: dict) -> bool: return event['post_type'] == 'notice'
    # 消息上报判断
    def isMsgReport(self, event: dict) -> bool: return event['post_type'] == 'message'


class KernelManager(Singleton):
    """
    内核事件处理器
    """
    def __init__(self) -> None:
        super().__init__()
        # 内核事件属于系统级事件，因此不组合用户级的 cmdExecutor
        self.ExeI = ExeI
    
    def isQfullEvent(self, event: dict) -> bool:
        return event['post_type'] == BOT_STORE['kernel']['EVENT_TYPE']['eq_full']
    
    async def handle(self, event: dict) -> list:
        res = []
        # kernelEvent 是二次包装事件，使用 origin 获得原事件对象
        if self.isQfullEvent(event):
            # 系统级事件，可以使用 sys_call
            res = await self.ExeI.sys_call(
                'echo', event['origin'], '任务太多啦，等会儿叭 qwq'
            )
        return res


class RespManager(Singleton):
    """
    响应事件处理器
    """
    def __init__(self) -> None:
        super().__init__()
        self.exact_exec = exact_executor

    def isOkResp(self, event: dict) -> bool:
        return event['retcode'] == 0 or event['retcode'] == 1
    
    async def handle(self, event: dict) -> list:
        res = []
        if not self.isOkResp(event):
            BOT_LOGGER.error(f'收到错误响应：{event}')
        return res



class MetaEventManager(Singleton):
    """
    元事件上报处理器
    """
    def __init__(self) -> None:
        super().__init__()
        self.exact_exec = exact_executor
    
    async def handle(self, event: dict) -> list:
        res = []
        return res


class ReqManager(Singleton):
    """
    请求上报处理器
    """
    def __init__(self) -> None:
        super().__init__()
        self.exact_exec = exact_executor
    
    async def handle(self, event: dict) -> list:
        res = []
        return res


class NoticeManager(Singleton):
    """
    通知上报处理器
    """
    def __init__(self) -> None:
        super().__init__()
        self.exact_exec = exact_executor
        self.notice_checker = au.NOTICE_CHECKER
    
    # 戳一戳判断
    def isPokeNotice(self, event: dict) -> bool: 
        return event['notice_type'] == 'notify' and event['sub_type'] == 'poke'
    
    async def handle(self, event: dict) -> list:
        res = []
        if self.isPokeNotice(event):
            # 如果被戳者是自己，触发 poke 命令
            # 除这里的校验外，还会在 cmdInterface 模块对消息发起者进行权限校验 
            if event["target_id"] == event["self_id"]:
                # 不调用命令接口的 sys_call，因为这是用户级命令调用
                res =  await self.exact_exec.exec_cmd_list(event, [['poke']])
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
        # 保存 lifecycle 指令所有别称和正式名称
        cmd_name_list = self.ExeI.get_cmd_alias('lifecycle')
        cmd_name_list.append('lifecycle')
        self.lifecycle_cmd_name = cmd_name_list

    def eventProcessFilter(self):
        """
        消息事件处理过滤器，根据当前的 bot 状态值，
        选择是处理事件，还是忽略所有事件。
        即实现 bot on 和 off 的功能
        """
        return BOT_STORE['kernel']['WORKING_STATUS']

    # 合法文本消息上报判断
    def isLegalTextMsg(self, event: dict) -> bool: 
        return event['message'][0]['type'] == 'text'

    # 消息上报来源判断
    def isGroupPublicMsg(self, event: dict) -> bool: 
        return event['message_type'] == 'group' and event['sub_type'] == 'normal'

    def isGroupTempMsg(self, event: dict) -> bool: 
        return event['message_type'] == 'group' and event['sub_type'] == 'group'

    def isPrivateMsg(self, event: dict) -> bool: 
        return event['message_type'] == 'private'

    def isFriendMsg(self, event: dict) -> bool: 
        return event['sub_type'] == 'friend'
    
    async def handle(self, event: dict):
        res = []
        # 不是有效的文本消息，返回空的 action 列表
        if not self.isLegalTextMsg(event): return res
        # 判断是否符合响应条件
        if self.isGroupPublicMsg(event) or self.isFriendMsg(event):

            # 如果是 lifecycle 指令，任何时候都应该执行
            cmd_list = self.exact_exec.ec_parser.parse(event['raw_message'])
            if cmd_list != [[]] and cmd_list[0][0] in self.lifecycle_cmd_name:
                res = await self.exact_exec.execute(event)
            else:
                # 判断是否应该执行事件
                if not self.eventProcessFilter(): return []

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
        self.f = EventFilter()
        # 对应调度策略不会增减，所以不使用策略模式
        self.kernel_m = KernelManager()
        self.resp_m = RespManager()
        self.meta_m = MetaEventManager()
        self.req_m = ReqManager()
        self.notice_m = NoticeManager()
        self.msg_m = MsgManager()
        

    async def handle(self, event: dict) -> None:
        """
        对传入的事件进行响应
        """
        # 所有 handle 应该返回一个 action 列表，没有结果则是一个空列表
        # 这里判断顺序不能更改
        if self.f.isResp(event):
            return await self.resp_m.handle(event)
        elif self.f.isKernelReport(event):
            return await self.kernel_m.handle(event)
        elif self.f.isMsgReport(event):
            return await self.msg_m.handle(event)
        elif self.f.isMetaReport(event):
            return await self.meta_m.handle(event)
        elif self.f.isNoticeReport(event):
            return await self.notice_m.handle(event)
        elif self.f.isReqReport(event):
            return await self.req_m.handle(event)
        else:
            raise BotUnknownEvent("未知的事件类型")