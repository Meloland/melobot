import sys
import os
import asyncio as aio
import importlib.util as iplu
from asyncio import Lock as aioLock
from threading import Lock as tLock
from .globalPattern import *
from .globalData import BOT_STORE
from .botLogger import BOT_LOGGER
from . import authority as au
from . import cmdParser as cp
from concurrent.futures import ThreadPoolExecutor
from typing import Callable


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


class ExecInterface(Singleton):
    """
    命令执行接口类，提供供命令模板使用的装饰器接口。
    同时给命令模板或 bot 内部提供执行命令并返回结果的方法
    """
    def __init__(self) -> None:
        super().__init__()
        self.role = Role()
        self.msg_checker = au.MSG_CHECKER
        self.notice_checker = au.NOTICE_CHECKER
        self.ec_parser = cp.EC_PARSER
        self.fc_parser = cp.FC_PARSER
        self.tc_parser = cp.TC_PARSER
        self.logger = BOT_LOGGER
        self.pool = ThreadPoolExecutor(max_workers=BOT_STORE['kernel']['THREAD_NUM'])
        # 装入全局，方便 Monitor 管理
        BOT_STORE['kernel']['POOL'] = self.pool
    

    def add_map(self, cmdMap: dict, sysCmdMap: dict, aliasMap: dict) -> None:
        """
        绑定映射表
        """
        # 先初始化属性会导致循环引用，需要等下面的 CmdMapper 载入后，再调用此方法加载
        self.cmd_map = cmdMap
        self.sys_cmd_map = sysCmdMap
        self.alias_map = aliasMap

    def get_cmd_alias(self, cmdName: str) -> list:
        """
        供外部获取指定命令的所有别称
        """
        return self.cmd_map[cmdName].__alias__.copy()

    def get_cmd_auth(self, cmdName: str) -> au.UserLevel:
        """
        供外部获取指定命令的权限限制值
        """
        return self.cmd_map[cmdName].__auth__

    def get_cmd_comment(self, cmdName: str) -> str:
        """
        供外部获取指定命令的注释
        """
        return self.cmd_map[cmdName].__comment__

    def get_cmd_paramsTip(self, cmdName: str) -> str:
        """
        供外部获取指定命令的参数说明
        """
        return self.cmd_map[cmdName].__params__

    def sync_method(self, alias: list=None, userLevel: au.UserLevel=au.USER, lock: bool=False, \
                        prefix: bool=False, comment: str='', paramsTip: str='无说明') -> Callable:
        """
        供命令模板使用的装饰器接口，适用于同步方法，
        内部使用 thread_pool 转化同步操作为异步任务。
        装饰器选项：命令别称、权限校验、是否加锁、是否添加前缀。
        注意：不同命令的别称不能相同，相同将会导致覆盖
        """
        def warpper_exec(cmd_func: Callable) -> Callable:
            async def after_cmd_func(event: dict, *args, **kwargs):
                nonlocal alias, prefix
                # 先检查是不是系统级权限认证
                if userLevel == au.SYS:
                    if not (self.msg_checker.isSysEvent(event) or self.msg_checker.enableSysRole(event)):
                        BOT_LOGGER.warning('检测到非法调用系统级指令，已拦截...')
                        return
                else:
                    # 只进行发送者权限的校验，更复杂的校验目标，应该由前端模块提前完成
                    if self.msg_checker.isMsgReport(event):
                        if not self.msg_checker.check(userLevel, event):
                            return await self.sys_call('echo', event, \
                                f'需要 {self.msg_checker.auth_str_map[userLevel]} 权限，权限不够呢 qwq')
                    elif self.notice_checker.isNoticeReport(event):
                        if not self.notice_checker.check(("user_id", userLevel), event):
                            return await self.sys_call('echo', event, \
                                f'需要 {self.msg_checker.auth_str_map[userLevel]} 权限，权限不够呢 qwq')
                    else:
                        BOT_LOGGER.error(f"bot 权限校验中遇到了预期外的事件类型：{event}")
                        raise BotUnexpectedEvent("权限校验中遇到了预期外的事件类型")
                
                action = None
                try:
                    if lock:
                        with tLock():
                            loop = aio.get_running_loop()
                            action = await loop.run_in_executor(
                                self.pool, cmd_func, event, *args, **kwargs
                            )
                    else:
                        loop = aio.get_running_loop()
                        action = await loop.run_in_executor(
                            self.pool, cmd_func, event, *args, **kwargs
                        )
                    
                    if action != None:
                        # 添加前缀
                        self.add_prefix(action, [cmd_func.__name__, *args]) if prefix else None
                        # 在 action 中封装 cmd_name 和 cmd_args，方便后续模块日志调用
                        action['cmd_name'] = cmd_func.__name__
                        action['cmd_args'] = args
                except aio.CancelledError:
                    BOT_LOGGER.error(f'命令 {cmd_func.__name__} | {" | ".join(args)} 执行失败，原因：超时，尝试发送提示消息中...')
                except (TypeError, ValueError):
                    BOT_LOGGER.warning(f'命令 {cmd_func.__name__} | {" | ".join(args)} 执行失败，原因：参数错误，尝试发送提示消息中...')
                    action = await self.sys_call('echo', event, '参数有误哦~')
                    return action if action else None
                except BotCmdWrongParams as e:
                    BOT_LOGGER.warning(f'命令 {cmd_func.__name__} | {" | ".join(args)} 执行失败，原因：参数格式不正确，尝试发送提示消息中...')
                    action = await self.sys_call('echo', event, e.origin_err)
                    return action if action else None
                except Exception as e:
                    BOT_LOGGER.error(f'命令 {cmd_func.__name__} | {" | ".join(args)} 执行失败，原因：预期之外的异常 {e}')
                    action = await self.sys_call('echo', event, '参数有误哦~')
                    return action if action else None
                return action

            # 封装 alias 到装饰后的命令模板中
            after_cmd_func.__alias__ = alias
            # 封装调用权限级别
            after_cmd_func.__auth__ = userLevel
            # 封装简单注释
            after_cmd_func.__comment__ = comment
            # 封装简单的参数说明文本
            after_cmd_func.__params__ = paramsTip
            return after_cmd_func
        return warpper_exec

    def async_method(self, alias: list=None, userLevel: au.UserLevel=au.USER, lock: bool=False, \
                        prefix: bool=False, comment: str='', paramsTip: str='无说明') -> Callable:
        """
        供命令模板使用的装饰器接口，适用于异步方法。
        装饰器选项：用户权限校验、任务是否加锁
        """
        def warpper_exec(cmd_func: Callable) -> Callable:
            async def after_cmd_func(event: dict, *args, **kwargs):
                nonlocal alias, prefix
                # 先检查是不是系统级权限认证
                if userLevel == au.SYS:
                    if not (self.msg_checker.isSysEvent(event) or self.msg_checker.enableSysRole(event)): 
                        BOT_LOGGER.warning('检测到非法调用系统级指令，已拦截...')
                        return
                else:
                    # 只进行发送者权限的校验，更复杂的校验目标，应该由前端模块提前完成
                    if self.msg_checker.isMsgReport(event):
                        if not self.msg_checker.check(userLevel, event):
                            return await self.sys_call('echo', event, \
                                f'需要 {self.msg_checker.auth_str_map[userLevel]} 权限，权限不够呢 qwq')
                    elif self.notice_checker.isNoticeReport(event):
                        if not self.notice_checker.check(("user_id", userLevel), event):
                            return await self.sys_call('echo', event, \
                                f'需要 {self.msg_checker.auth_str_map[userLevel]} 权限，权限不够呢 qwq')
                    else:
                        BOT_LOGGER.error(f"bot 权限校验中遇到了预期外的事件类型：{event}")
                        raise BotUnexpectedEvent("权限校验中遇到了预期外的事件类型")
                
                action = None
                try:
                    if lock:
                        async with aioLock():
                            action = await cmd_func(event, *args, **kwargs)
                    else:
                        action = await cmd_func(event, *args, **kwargs)
                    
                    if action != None:
                        # 添加前缀
                        self.add_prefix(action, [cmd_func.__name__, *args]) if prefix else None
                        # 在 action 中封装 cmd_name 和 cmd_args，方便后续模块日志调用
                        action['cmd_name'] = cmd_func.__name__
                        action['cmd_args'] = args
                except aio.CancelledError:
                    BOT_LOGGER.error(f'命令 {cmd_func.__name__} | {" | ".join(args)} 执行失败，原因：超时，尝试发送提示消息中...')
                except (TypeError, ValueError):
                    BOT_LOGGER.warning(f'命令 {cmd_func.__name__} | {" | ".join(args)} 执行失败，原因：参数错误，尝试发送提示消息中...')
                    action = await self.sys_call('echo', event, '参数有误哦~')
                    return action if action else None
                except BotCmdWrongParams as e:
                    BOT_LOGGER.warning(f'命令 {cmd_func.__name__} | {" | ".join(args)} 执行失败，原因：参数格式不正确，尝试发送提示消息中...')
                    action = await self.sys_call('echo', event, e.origin_err)
                    return action if action else None
                except Exception as e:
                    BOT_LOGGER.error(f'命令 {cmd_func.__name__} | {" | ".join(args)} 执行失败，原因：预期之外的异常 {e}')
                    action = await self.sys_call('echo', event, '参数有误哦~')
                    return action if action else None
                return action
                
            # 封装 alias 到装饰后的命令模板中
            after_cmd_func.__alias__ = alias
            # 封装调用权限级别到装饰后的命令模板中
            after_cmd_func.__auth__ = userLevel
            # 封装简单注释到装饰后的命令模板中
            after_cmd_func.__comment__ = comment
            # 封装简单的参数说明文本
            after_cmd_func.__params__ = paramsTip
            return after_cmd_func
        return warpper_exec
    
    async def call(self, cmdName: str, event: dict, *args, **kwargs) -> dict:
        """
        为 bot 内部或命令模板提供调用其他命令的方法，结果会返回给调用方，
        不会直接作为 action  向外部发送。
        注意：命令模板内调用该方法是一种递归调用，执行的命令仍有装饰器装饰。
        且调用函数必须为异步函数。同时注意调用命令返回 action 的 encode 模式是 str 还是 dict
        """
        if cmdName in self.cmd_map.keys():
            pass
        elif cmdName in self.alias_map.keys():
            cmdName = self.alias_map[cmdName]
        else:
            return None
        
        action = await self.cmd_map[cmdName](event, *args, **kwargs)
        return action

    async def sys_call(self, cmdName: str, event: dict, *args, **kwargs) -> dict:
        """
        调用系统命令的方法。一般仅供 bot 内部在 “在非执行外部命令任务” 时使用，实现更好的权限分离。
        命令模板内应避免此种调用方式
        """
        # 设置标志位
        event['sys_pass'] = 1
        action = await self.sys_cmd_map[cmdName](event, *args, **kwargs)
        return action
    
    def add_prefix(self, action: dict, cmd_seq: list) -> None:
        """
        为每个 action 添加原指令名称和参数的 prefix，方便区分结果来源于哪条指令
        直接修改，不返回结果
        """
        # 只有为消息 action 时才触发
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
        # 提前导入上层路径，这样加载命令模板时，命令模块的内部模块引用就可以正常找到
        sys.path.append('..')
        templates_path = os.path.join(
            os.path.dirname(__file__), '..', 'templates'
        )
        
        # 加载用户级 cmd
        for pypath in os.listdir(templates_path):
            if pypath != "__init__.py" and pypath != "__pycache__":
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
            if pypath != "__init__.py" and pypath != "__pycache__":
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
            if func.__alias__:
                for alias in func.__alias__:
                    self.alias_map[alias] = cmd_name


ExeI = ExecInterface()
CMD_MAP = CmdMapper().exec_map
ALIAS_MAP = CmdMapper().alias_map
SYS_CMD_MAP = CmdMapper().sys_exec_map
BOT_STORE['kernel']['CMD_MAP'] = CMD_MAP
BOT_STORE['kernel']['SYS_CMD_MAP'] = SYS_CMD_MAP
BOT_STORE['kernel']['ALIAS_MAP'] = ALIAS_MAP
ExeI.add_map(CMD_MAP, SYS_CMD_MAP, ALIAS_MAP)
