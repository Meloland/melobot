import os
import time as t
import asyncio as aio
import importlib.util as iplu
from asyncio import Lock as aioLock, iscoroutinefunction
from threading import Lock as tLock, current_thread, main_thread
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Union, List
from copy import deepcopy
from .Definition import *
from .Store import BOT_STORE
from .Logger import BOT_LOGGER
from .Event import *
from .Action import BotAction
from . import Auth as au


__all__ = ['AuthRole', 'ExeI']


class Role(Singleton):
    """
    角色类，包含不同权限角色的常量
    """
    def __init__(self) -> None:
        super().__init__()
        self.SYS = au.SYS
        self.OWNER = au.OWNER
        self.SU = au.SU
        self.WHITE = au.WHITE
        self.USER = au.USER
        self.BLACK = au.BLACK


AuthRole = Role()


class ExecInterface(Singleton):
    """
    命令执行接口类，提供供命令模板使用的装饰器接口。
    同时给命令模板或 bot 内部提供与命令执行相关的方法
    """
    def __init__(self) -> None:
        super().__init__()
        self.msg_checker = au.MSG_CHECKER
        self.notice_checker = au.NOTICE_CHECKER
        self.pool = ThreadPoolExecutor(max_workers=BOT_STORE['kernel']['THREAD_NUM'])
        # 装入全局，方便 Monitor 管理
        BOT_STORE['kernel']['POOL'] = self.pool
        self.loop = None
        
    def callback(self, delay: float, func: Callable, *args) -> aio.TimerHandle:
        """
        设置定时回调任务
        """
        if current_thread() is main_thread():
            return self.loop.call_later(delay, func, *args)
        else:
            return self.loop.call_soon_threadsafe(
                self.loop.call_later, delay, func, *args
            )

    async def __cmd_auth_check(self, event: BotEvent, userLevel: au.UserLevel) -> bool:
        """
        命令权限校验。
        当返回 True 时，可以继续执行；当返回 False 时，不能继续执行。
        """
        # 只进行发送者权限的校验，更复杂的校验目标，应该由前端模块提前完成
        # 若在黑名单中，什么也不做
        if event.is_msg():
            if self.msg_checker.get_event_lvl(event) == AuthRole.BLACK:
                return False
            if not self.msg_checker.check(userLevel, event):
                return False
        elif event.is_notice() and event.notice.is_poke():
            if self.notice_checker.get_event_lvl(event) == AuthRole.BLACK:
                return False
            if not self.notice_checker.check(userLevel, event.notice.user_id):
                return False
        else:
            BOT_LOGGER.error(f"bot 权限校验中遇到了预期外的事件类型：{event}")
            raise BotUnexpectEvent("权限校验中遇到了预期外的事件类型")
        return True

    async def __run_cmd(self, event: BotEvent, cmd_func: Callable, *args, **kwargs) -> BotAction:
        """
        命令运行方法。
        仅供 tempalte 装饰函数内部使用，用户态运行命令应该使用 call 方法
        """
        action = None
        # 只有 bot 处于工作状态或指令为生命周期指令时，才执行指令
        if self.is_bot_working() or cmd_func.__name__ == 'lifecycle':
            if iscoroutinefunction(cmd_func):
                action = await cmd_func(event , *args, **kwargs)
            else:
                action = await self.loop.run_in_executor(
                    self.pool, cmd_func, event, *args, **kwargs
                )
            # 保存本次结束时间点至 cmd store
            BOT_STORE['cmd'][cmd_func.__name__]['state']['LAST_CALL'] = t.time()
        return action

    def __get_rest_time(self, name: str, interval: int) -> float:
        """
        对于有 interval 的命令，根据上次执行完成的时间，和本次准备开始执行的时间，
        计算需要停止命令执行的时间。
        """
        cmdName = self.get_cmd_name(name)
        state = BOT_STORE['cmd'][cmdName]['state']
        if 'LAST_CALL' not in state.keys():
            return 0
        else:
            cur_t = t.time()
            last_t = state['LAST_CALL']
            return interval-(cur_t-last_t)
    
    def template(
            self, 
            aliases: list=None, 
            userLevel: au.UserLevel=AuthRole.USER,
            isLocked: bool=False,
            interval: int=0,
            hasPrefix: bool=False, 
            comment: str='无', 
            prompt: str='无',
        ) -> Callable:
        """
        供命令模板使用的装饰器接口，内部会自动判断方法类型。
        同步任务内部使用 thread_pool 转化为异步任务。
        `aliases`: 命令别称。注意不同命令的别称不能相同
        `userLevel`: 权限等级。接受 `AuthRole` 字面量
        `isLocked`: 是否加锁。若需要更细粒度的加锁，在模板内部使用 `ExeI.get_cmd_lock()` 方法获得锁
        `interval`: 命令冷却时间（单位 秒），注意：冷却时间 >0，默认会加锁任务
        `hasPrefix`: 是否添加前缀
        `comment`: 供帮助使用的命令注释
        `prompt`: 供帮助使用的命令参数提示
        """
        def warpper(cmd_func: Callable) -> Callable:
            async def warpped_cmd_func(event: BotEvent, *args, **kwargs) -> BotAction:
                action = None
                cmd_name = cmd_func.__name__
                state = BOT_STORE['cmd'][cmd_name]['state']
                f_cmd_args_str = f'命令 {cmd_name} {" | ".join(args)}'

                try:
                    check_res = await self.__cmd_auth_check(event, userLevel)
                    if check_res == False: return None

                    if interval <= 0:
                        if isLocked:
                            async with state['LOCK']:
                                action = await self.__run_cmd(event, cmd_func, *args, **kwargs)
                        else:
                            action = await self.__run_cmd(event, cmd_func, *args, **kwargs)
                    else:
                        if state['LOCK'].locked():
                            return await self.__sys_call('echo', event, '该命令不允许多执行，请等待前一次命令完成~')
                        async with state['LOCK']:
                            cmd_name = cmd_name
                            rest_time = self.__get_rest_time(cmd_name, interval)
                            if rest_time > 0:
                                return await self.__sys_call('echo', event, f'该命令冷却中，剩余 cd：{int(rest_time)} 秒')
                            action = await self.__run_cmd(event, cmd_func, *args, **kwargs)

                    if action != None:
                        action = self.__add_prefix(action, [cmd_name, *args]) if hasPrefix else action
                        # 在 action 中封装 cmd_name 和 cmd_args，方便后续模块日志调用
                        action.cmd_name = cmd_name
                        action.cmd_args = args
                except aio.CancelledError:
                    BOT_LOGGER.error(f_cmd_args_str + '执行失败，原因：超时，尝试发送提示消息中...')
                except (TypeError, ValueError):
                    BOT_LOGGER.warning(f_cmd_args_str + '执行失败，原因：参数格式错误，尝试发送提示消息中...')
                    return await self.__ret_sys_call('echo', event, '参数有误哦~')
                except BotCmdExecFailed as e:
                    BOT_LOGGER.warning(f_cmd_args_str + '执行失败，原因：内部的自定义错误，尝试发送提示消息中...')
                    return await self.__ret_sys_call('echo', event, e.origin_err)
                except Exception as e:
                    BOT_LOGGER.error(f_cmd_args_str + f'执行失败，原因：预期之外的异常 {e}')
                    return await self.__ret_sys_call('echo', event, f"内部发生异常：[{str(e.__class__.__name__)}] {e}")
                return action
            
            # 命令别称
            warpped_cmd_func.__aliases__ = aliases if aliases is not None else []
            # 权限级别
            warpped_cmd_func.__auth__ = userLevel
            # 用于帮助的注释
            warpped_cmd_func.__comment__ = comment
            # 用于帮助的参数说明
            warpped_cmd_func.__params__ = prompt
            # 未装饰命令方法是否为异步协程
            warpped_cmd_func.__iscoro__ = iscoroutinefunction(cmd_func)
            # 是否加锁
            warpped_cmd_func.__enable_lock__ = isLocked
            # 是否启用冷却
            warpped_cmd_func.__enable_cd__ = interval > 0
            return warpped_cmd_func
        return warpper

    async def call(self, name: str, event: BotEvent, *args, **kwargs) -> BotAction:
        """
        为 bot 内部或命令模板提供调用其他命令的方法，结果 action 会返回给调用方，
        不会直接作为 action  向外部发送。name 参数可传递命令名或别称
        注意命令模板内调用该方法是一种递归调用，执行的命令仍有装饰器装饰。
        """
        try:
            cmdName = self.get_cmd_name(name)
        except BotUnknownCmdName:
            return None
        action = await self.cmd_map[cmdName](event, *args, **kwargs)
        return action

    async def __sys_call(self, cmdName: str, event: BotEvent, *args, **kwargs) -> None:
        """
        调用系统功能。系统功能调用也是通过命令执行实现。
        一般供 bot 内部在 “在执行非外部命令任务” 时使用，实现更好的逻辑分离。
        注：系统命令执行不需要前置操作，且结果 action 直接送至连接器
        """
        cmd_func = self.sys_cmd_map[cmdName]
        if iscoroutinefunction(cmd_func):
            action = await cmd_func(event, *args, **kwargs)
        else:
            action = await self.loop.run_in_executor(
                self.pool, cmd_func, event, *args, **kwargs
            )
        monitor = BOT_STORE['kernel']['MONITOR']
        await monitor.place_action(action)
    
    async def __ret_sys_call(self, cmdName: str, event: BotEvent, *args, **kwargs) -> BotAction:
        """
        和 `__sys_call` 方法类似，但有 action 返回值，而不是直接发送 action
        """
        cmd_func = self.sys_cmd_map[cmdName]
        if iscoroutinefunction(cmd_func):
            action = await cmd_func(event, *args, **kwargs)
        else:
            action = await self.loop.run_in_executor(
                self.pool, cmd_func, event, *args, **kwargs
            )
        action.cmd_name = cmd_func.__name__
        action.cmd_args = args
        return action

    def __add_prefix(self, action: BotAction, cmd_seq: list) -> BotAction:
        """
        为每个 action 添加原指令名称和参数的 prefix，方便区分结果来源于哪条指令
        直接修改，不返回结果
        """ 
        origin_a = deepcopy(action)
        # 只有为消息 action 时才触发
        action = action.extract()
        if 'message' in action['params'].keys():
            origin_ans = action['params']['message']
            prefix = f"[cmd]: {cmd_seq[0]}\n[args]: [{'] ['.join(cmd_seq[1:])}]\n\n"

            # action messages 为字符串时
            if isinstance(origin_ans, str):
                action['params']['message'] = prefix + origin_ans
            # 为单 dict 时
            elif isinstance(origin_ans, dict):
                new_ans = []
                new_ans.append({"type": "text","data": {"text": prefix,}})
                new_ans.append(origin_ans)
                action['params']['message'] = new_ans
            # 为 dict list 时
            else:
                action['params']['message'].insert(0, {"type": "text","data": {"text": prefix,}})
            origin_a.params = action['params']
        return origin_a

    def __build_cmd_store(self) -> None:
        """
        在 BOT_STORE 中建立每个命令的存储，包含全局状态和 session 空间
        """
        for cmdName in self.cmd_map.keys():
            BOT_STORE['cmd'][cmdName] = {
                'sessions': [],
                'state': {},
            }
    
    def __load_cmd_funcs(self, cmdMap: dict, sysCmdMap: dict, aliasMap: dict) -> None:
        """
        加载命令模板/方法到类中
        """
        # 先初始化属性会导致循环引用，需要等下面的 CmdMapper 载入后，再调用此方法加载
        self.cmd_map = cmdMap
        self.sys_cmd_map = sysCmdMap
        self.alias_map = aliasMap
        self.__build_cmd_store()

    def __after_loop_init(self) -> None:
        """
        初始化需要在事件循环启动后获得或构建的变量
        """
        self.loop = aio.get_running_loop()
        # 由于同步任务是线程池执行，因此同样可以使用 asyncio Lock
        for cmdName in self.cmd_map.keys():
            state = BOT_STORE['cmd'][cmdName]['state']
            cmd_func = self.cmd_map[cmdName]
            # 命令加锁选项为 True 或命令启用冷却机制，都需要在为该命令初始化命令锁
            if cmd_func.__enable_lock__ or cmd_func.__enable_cd__: 
                state['LOCK'] = aioLock()

    def is_bot_working(self):
        """
        判断 bot 是否在工作
        """
        return BOT_STORE['kernel']['WORKING_STATUS']

    def get_cmd_name(self, name: str) -> str:
        """
        获得命令名，可传入命令名或别称
        """
        if name in self.alias_map.keys():
            return self.alias_map[name]
        elif name in self.cmd_map.keys():
            return name
        else:
            raise BotUnknownCmdName("无效的命令名或命令别称")

    def get_cmd_aliases(self, name: str) -> List[str]:
        """
        供外部获取指定命令的所有别称，可使用命令名或别称
        """
        cmdName = self.get_cmd_name(name)
        return self.cmd_map[cmdName].__aliases__.copy()

    def get_cmd_auth(self, name: str) -> au.UserLevel:
        """
        供外部获取指定命令的权限限制值，可使用命令名或别称
        """
        cmdName = self.get_cmd_name(name)
        return self.cmd_map[cmdName].__auth__

    def get_cmd_comment(self, name: str) -> str:
        """
        供外部获取指定命令的注释，可使用命令名或别称
        """
        cmdName = self.get_cmd_name(name)
        return self.cmd_map[cmdName].__comment__

    def get_cmd_paramsTip(self, name: str) -> str:
        """
        供外部获取指定命令的参数说明，可使用命令名或别称
        """
        cmdName = self.get_cmd_name(name)
        return self.cmd_map[cmdName].__params__
    
    def get_cmd_lock(self, name: str) -> Union[aioLock, tLock]:
        """
        用于命令模板内部获得命令锁,以实现更细粒度的加锁控制。
        异步函数获得协程锁，同步函数获得线程锁。
        不建议在 `isLocked == True` 时使用
        """
        # 注意：用户态锁获取时，同步命令方法，不能直接返回 state 中的协程锁。此时要返回线程锁
        cmdName = self.get_cmd_name(name)
        cmd_func = self.cmd_map[cmdName]
        state = BOT_STORE['cmd'][cmdName]['state']
        if cmd_func.__iscoro__:
            if 'LOCK' not in state.keys(): 
                state['LOCK'] = aioLock()
            return state['LOCK']
        else:
            if 'TLOCK' not in state.keys(): 
                state['TLOCK'] = tLock()
            return state['TLOCK']

class CmdMapper(Singleton):
    """
    命令映射类，载入命令模板并存入映射表（具体命令执行方法）。
    同时建立 alias 到真实命令名的映射
    """
    def __init__(self) -> None:
        super().__init__()
        self.exec_map = {}
        self.alias_map = {}
        # 系统级命令封装于此
        self.sys_exec_map = {}
        self.load_templates()
        self.build_alias_map()
        self.load_sys_cmd()

    def load_templates(self) -> None:
        """
        加载模板，即具体的命令执行方法
        """
        templates_path = os.path.join(
            os.path.dirname(__file__), '..', 'templates'
        )
        
        # 加载用户级 cmd
        for pypath in os.listdir(templates_path):
            if pypath != "__init__.py" and pypath != "__pycache__" and pypath.endswith(".py"):
                method_name = pypath.split('.')[0]
                spec = iplu.spec_from_file_location(
                    'foo',
                    os.path.join(
                        os.path.dirname(__file__), '..', 'templates', pypath
                    )
                )
                foo = iplu.module_from_spec(spec)
                spec.loader.exec_module(foo)
                self.exec_map[method_name] = vars(foo)[method_name]

    def load_sys_cmd(self) -> None:
        """
        加载系统级命令
        """
        # 加载系统级 cmd
        sys_cmd_path = os.path.join(
            os.path.dirname(__file__), 'cmd'
        )
        for pypath in os.listdir(sys_cmd_path):
            if pypath != "__init__.py" and pypath != "__pycache__" and pypath.endswith(".py"):
                sys_method_name = pypath.split('.')[0]
                spec = iplu.spec_from_file_location(
                    'foo',
                    os.path.join(
                        os.path.dirname(__file__), 'cmd', pypath
                    )
                )
                foo = iplu.module_from_spec(spec)
                spec.loader.exec_module(foo)
                self.sys_exec_map[sys_method_name] = vars(foo)[sys_method_name]

    def build_alias_map(self) -> None:
        """
        建立命令别称到命令名的映射表
        """
        for cmd_name in self.exec_map:
            func = self.exec_map[cmd_name]
            if func.__aliases__:
                for alias in func.__aliases__:
                    self.alias_map[alias] = cmd_name


ExeI = ExecInterface()
CMD_MAP = CmdMapper().exec_map
ALIAS_MAP = CmdMapper().alias_map
SYS_CMD_MAP = CmdMapper().sys_exec_map
ExeI._ExecInterface__load_cmd_funcs(CMD_MAP, SYS_CMD_MAP, ALIAS_MAP)
