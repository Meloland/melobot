import os
import time
import asyncio as aio
import importlib.util as iplu
from asyncio import Lock as aioLock, iscoroutinefunction
from common.Typing import *
from common.Event import BotEvent
from common.Store import *
from common.Session import BotSession, SessionManager
from common.Exceptions import *
from utils import Access as ac


__all__ = ['AuthRole', 'EXEC']


class Role:
    """
    角色类，包含不同权限角色的常量
    """
    def __init__(self) -> None:
        super().__init__()
        self.SYS = ac.SYS
        self.OWNER = ac.OWNER
        self.SU = ac.SU
        self.WHITE = ac.WHITE
        self.USER = ac.USER
        self.BLACK = ac.BLACK


AuthRole = Role()


class ExecInterface:
    """
    命令执行接口类，提供供命令模板使用的装饰器接口。
    同时给命令模板或 bot 内部提供与命令执行相关的方法
    """
    def __init__(self) -> None:
        super().__init__()
        self.msg_checker = ac.MSG_CHECKER
        self.notice_checker = ac.NOTICE_CHECKER
        self.__session_builder = SessionManager()
        
    def callback(self, delay: float, func: Callable, *args) -> aio.TimerHandle:
        """
        设置定时回调任务
        """
        return aio.get_running_loop().call_later(delay, func, *args)

    async def __cmd_auth_check(self, event: BotEvent, userLevel: ac.UserLevel) -> bool:
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
            BOT_STORE.logger.error(f"bot 权限校验中遇到了预期外的事件类型：{event}")
            raise BotUnexpectEvent("权限校验中遇到了预期外的事件类型")
        return True

    async def __run_cmd(self, session: BotSession, cmd_func: Callable, *args, **kwargs) -> None:
        """
        命令运行方法。
        """
        # 只有 bot 处于工作状态或指令为生命周期指令时，才执行指令
        if BOT_STORE.meta.working_status or cmd_func.__name__ == 'lifecycle':
            await cmd_func(session , *args, **kwargs)
            # 保存本次结束时间点至 cmd store
            getattr(BOT_STORE.cmd, cmd_func.__name__).state.val()['LAST_CALL'] = time.time()

    def __get_rest_time(self, name: str, interval: int) -> float:
        """
        对于有 interval 的命令，根据上次执行完成的时间，和本次准备开始执行的时间，
        计算需要停止命令执行的时间。
        """
        cmdName = self.get_cmd_name(name)
        state = getattr(BOT_STORE.cmd, cmdName).state.val()
        if 'LAST_CALL' not in state.keys():
            return 0
        else:
            cur_t = time.time()
            last_t = state['LAST_CALL']
            return interval-(cur_t-last_t)

    async def __get_session(
        self, 
        cmdName: str, 
        event: BotEvent, 
        sessionCheck: Union[str, Tuple[str, ...], Callable[[BotEvent, BotEvent], bool], None]
    ) -> Union[BotSession, None]:
        """
        获取一个 session，session 的是否新建，
        取决于模板方法的配置
        """
        if sessionCheck is None:
            session = await self.__session_builder.get_session(event)
        elif isinstance(sessionCheck, str) or isinstance(sessionCheck, tuple):
            session = await self.__session_builder.get_session(
                event, 
                getattr(BOT_STORE.cmd, cmdName).sessions.val(),
                checkAttr=sessionCheck, 
                lock=self.get_cmd_lock(cmdName)
            )
        else:
            session = await self.__session_builder.get_session(
                event, 
                getattr(BOT_STORE.cmd, cmdName).sessions.val(),
                checkMethod=sessionCheck, 
                lock=self.get_cmd_lock(cmdName)
            )
        return session
    
    def template(
            self, 
            aliases: List[str]=None, 
            userLevel: ac.UserLevel=AuthRole.USER,
            isLocked: bool=False,
            interval: int=0,
            preLoad: Tuple[Callable[[], object], Union[Callable[[object], None], None]]=None,
            comment: str='无', 
            prompt: str='无',
            sessionRule: Union[str, Tuple[str, ...], Callable[[BotEvent, BotEvent], bool]]=None
        ) -> Callable:
        """
        供命令模板使用的装饰器接口。
        `aliases`: 命令别称。注意不同命令的别称不能相同
        `userLevel`: 权限等级。接受 `AuthRole` 字面量
        `isLocked`: 是否加锁。
        `interval`: 命令冷却时间（单位 秒），注意：冷却时间 >0，默认会加锁任务
        `preLoad`: 元组。资源加载方法，资源释放方法（不指定可以传递 None）
        `comment`: 供帮助使用的命令注释
        `prompt`: 供帮助使用的命令参数提示
        `sessionRule`: 是否处于同一 session 的判断规则。可以传递 event 的属性字符串，属性链元组或自定义校验方法
        """
        def warpper(cmd_func: Callable) -> Callable:
            async def warpped_cmd_func(session: BotSession, *args, **kwargs) -> None:
                cmd_name = cmd_func.__name__
                event = session.event
                state = getattr(BOT_STORE.cmd, cmd_name).state.val()
                cmd_name_args = f'命令 {cmd_name} {" | ".join(args)}'

                if not await self.__cmd_auth_check(event, userLevel): return
                if event.is_msg():
                    cmd_args = ' | '.join(args)
                    if len(cmd_args) > 40: cmd_args = cmd_args[:40] + '...'
                    BOT_STORE.logger.info(f"响应命令 {cmd_name} {cmd_args} √")

                try:
                    if interval <= 0:
                        if isLocked:
                            async with state['LOCK']:
                                await self.__run_cmd(session, cmd_func, *args, **kwargs)
                        else:
                            await self.__run_cmd(session, cmd_func, *args, **kwargs)
                    else:
                        if state['LOCK'].locked():
                            await self.__sys_call('echo', event, f'{cmd_name} 命令不允许多执行，请等待前一次执行完成~')
                            return
                        async with state['LOCK']:
                            cmd_name = cmd_name
                            rest_time = self.__get_rest_time(cmd_name, interval)
                            if rest_time > 0:
                                await self.__sys_call('echo', event, f'该命令冷却中，剩余 cd：{int(rest_time)} 秒')
                                return
                            await self.__run_cmd(session, cmd_func, *args, **kwargs)
                except aio.CancelledError:
                    BOT_STORE.logger.error(cmd_name_args + '执行异常，原因：超时，尝试发送提示消息中...')
                    await self.__sys_call('echo', event, f'{cmd_name_args}\n✘ 等待超时，已经放弃执行\n(；′⌒`)')
                except (TypeError, ValueError):
                    BOT_STORE.logger.warning(cmd_name_args + '执行异常，原因：参数格式错误，尝试发送提示消息中...')
                    await self.__sys_call('echo', event, '参数有误哦~')
                except BotCmdExecFailed as e:
                    BOT_STORE.logger.warning(cmd_name_args + '执行异常，原因：内部的自定义错误，尝试发送提示消息中...')
                    await self.__sys_call('echo', event, e.origin_err)
                except Exception as e:
                    BOT_STORE.logger.error(cmd_name_args + f'执行异常，原因：预期之外的异常 {e}')
                return
            
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
            # 是否有预先启动的配置
            warpped_cmd_func.__preload__ = preLoad
            # 是否有 session 检验规则
            warpped_cmd_func.__session_rule__ = sessionRule
            return warpped_cmd_func
        return warpper

    async def call(self, name: str, event: BotEvent, *args, **kwargs) -> None:
        """
        为 bot 内部或命令模板提供调用其他命令的方法。name 参数可传递命令名或别称。
        注意模板方法内调用该方法是一种递归调用。
        """
        try:
            cmdName = self.get_cmd_name(name)
        except BotUnknownCmdName:
            return

        session = await self.__get_session(cmdName, event, self.cmd_map[cmdName].__session_rule__)
        if session is None:
            await self.__sys_call('echo', event, f"命令 {cmdName} 相同的会话正在进行中，操作驳回")
        else:
            await self.cmd_map[cmdName](session, *args, **kwargs)
            session._BotSession__activated = False

    async def __sys_call(self, cmdName: str, event: BotEvent, *args, **kwargs) -> None:
        """
        系统功能调用。系统功能调用通过系统级命令调用实现
        一般供 bot 内部在 “在执行非外部命令任务” 时使用，实现更好的逻辑分离。
        直接由 monitor 传递给 responder
        """
        cmd_func = self.sys_cmd_map[cmdName]
        action = cmd_func(event, *args, **kwargs)
        monitor = BOT_STORE.monitor
        await monitor.responder.throw_action(action, True)

    async def __cmd_preset_build(self) -> None:
        """
        在 BOT_STORE 中建立每个命令的存储，包含全局状态和 session 空间。
        同时加载一些命令模板需要预加载的资源，并指定资源的销毁方法
        """
        for cmdName in self.cmd_map.keys():
            getattr(BOT_STORE.cmd, cmdName).sessions = BotResource([])
            getattr(BOT_STORE.cmd, cmdName).state = BotResource({})
            getattr(BOT_STORE.cmd, cmdName).store = BotResource()

            load_info = self.cmd_map[cmdName].__preload__
            if load_info is not None:
                load_method, dispose_method = load_info
                resource: BotResource = getattr(BOT_STORE.cmd, cmdName).store
                resource._info.load = load_method

                if dispose_method is None: continue
                else: resource._info.dispose = dispose_method
        
        await BOT_STORE.cmd.load_all()
    
    async def __load_cmd_funcs(self, cmdMap: dict, sysCmdMap: dict, aliasMap: dict) -> None:
        """
        加载命令模板/方法到类中
        """
        # 先初始化属性会导致循环引用，需要等下面的 CmdMapper 载入后，再调用此方法加载
        self.cmd_map = cmdMap
        self.sys_cmd_map = sysCmdMap
        self.alias_map = aliasMap
        await self.__cmd_preset_build()

    def __after_loop_init(self) -> None:
        """
        初始化需要在事件循环启动后获得或构建的变量
        """
        for cmdName in self.cmd_map.keys():
            state = getattr(BOT_STORE.cmd, cmdName).state.val()
            cmd_func = self.cmd_map[cmdName]
            # 命令加锁选项为 True 或命令启用冷却机制，都需要提前初始化命令锁
            if cmd_func.__enable_lock__ or cmd_func.__enable_cd__: 
                state['LOCK'] = aioLock()

    def get_resource(self, cmdName: str) -> Any:
        """
        获取预加载的资源
        """
        cmdName = self.get_cmd_name(cmdName)
        return getattr(BOT_STORE.cmd, cmdName).store.val()

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

    def get_cmd_auth(self, name: str) -> ac.UserLevel:
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

    def get_cmd_prompt(self, name: str) -> str:
        """
        供外部获取指定命令的参数说明，可使用命令名或别称
        """
        cmdName = self.get_cmd_name(name)
        return self.cmd_map[cmdName].__params__
    
    def get_cmd_lock(self, name: str) -> aioLock:
        """
        用于命令模板内部获得命令锁,以实现更细粒度的加锁控制。
        """
        cmdName = self.get_cmd_name(name)
        state = getattr(BOT_STORE.cmd, cmdName).state.val()
        if 'LOCK' not in state.keys(): 
            state['LOCK'] = aioLock()
        return state['LOCK']


class CmdMapper:
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
            BOT_STORE.meta.root_path, 'templates'
        )
        
        # 加载用户级 cmd
        for pypath in os.listdir(templates_path):
            if pypath != "__init__.py" and pypath != "__pycache__" and pypath.endswith(".py"):
                method_name = pypath.split('.')[0]
                spec = iplu.spec_from_file_location(
                    'foo',
                    os.path.join(
                        templates_path, pypath
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
            BOT_STORE.meta.root_path, 'core', 'cmd'
        )
        for pypath in os.listdir(sys_cmd_path):
            if pypath != "__init__.py" and pypath != "__pycache__" and pypath.endswith(".py"):
                sys_method_name = pypath.split('.')[0]
                spec = iplu.spec_from_file_location(
                    'foo',
                    os.path.join(
                        sys_cmd_path, pypath
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


EXEC = ExecInterface()
CMD_MAP = CmdMapper().exec_map
ALIAS_MAP = CmdMapper().alias_map
SYS_CMD_MAP = CmdMapper().sys_exec_map
