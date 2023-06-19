import importlib
import os
from asyncio import iscoroutinefunction

from ..interface.core import IActionResponder
from ..interface.plugins import (CallerWrapper, ExecutorWrapper, IEventHandler,
                                 IHookRunner, IBotPlugin, PluginTemplate)
from ..interface.typing import *
from ..models.exceptions import *
from .handler import MsgEventHandler, NoticeEventHandler, ReqEventHandler


class BotPlugin(IBotPlugin):
    """
    bot 插件类。
    bot 所有自定义功能都由插件实现。
    """
    __always_public__ = ('name', 'version', 'rw_auth', 'call_auth')
    __handlers_map__ = {
        'at_message': MsgEventHandler,
        'at_request': ReqEventHandler,
        'at_notice': NoticeEventHandler
    }
    __runner_map__ = {}

    def __init__(self, template: PluginTemplate, responder: IActionResponder) -> None:
        self._template = template
        self._responder = responder
        
        self.name: str
        self.version: str=None
        self.rw_auth: bool=False
        self.call_auth: bool=False
        self.store: Dict[str, Any]={}

        self.handlers: List[IEventHandler]=None
        self.runners: List[IHookRunner]=None

        self._build()

    def _build(self) -> None:
        """
        从模板初始化插件
        """
        executor_wrappers = None
        caller_wrappers = None

        for name in self._template.__dict__.keys():
            if name == 'executors':
                executor_wrappers = self._template.__dict__[name]
            elif name == 'callers':
                caller_wrappers = self._template.__dict__[name]
            else:
                setattr(self, name, self._template.__dict__[name])
        
        self._init_handlers(executor_wrappers)
        self._init_runners(caller_wrappers)

    def _init_handlers(self, wrappers: List[ExecutorWrapper]) -> None:
        if wrappers is None:
            return 
        self.handlers = []
        for wrapper in wrappers:
            self.handlers.append(
                BotPlugin.__handlers_map__[wrapper.type](wrapper.executor, self, self._responder, *wrapper.params)
            )

    def _init_runners(self, wrappers: List[CallerWrapper]) -> None:
        # TODO: 完成 hook runner 的初始化
        pass


class PluginLoader:
    @classmethod
    def _load_main(cls, dir: str) -> ModuleType:
        """
        将插件目录下的入口文件，加载为模块
        """
        if not os.path.exists(os.path.join(dir, 'main.py')):
            raise BotException("缺乏入口主文件，插件无法加载")
        
        main_path = os.path.join(dir, 'main.py')
        spec = importlib.util.spec_from_file_location(os.path.basename(main_path), main_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    
    @classmethod
    def _load_template(cls, module: ModuleType) -> PluginTemplate:
        """
        从模块加载出插件模板对象
        """
        template_class = None
        for obj in module.__dict__.values():
            if isinstance(obj, type) and issubclass(obj, PluginTemplate) and obj.__name__ != 'PluginTemplate':
                template_class = obj
                break
        if template_class is None:
            raise BotException("不存在插件模版类，无法加载插件")
        return template_class()
    
    @classmethod
    def _template_verify(cls, template: PluginTemplate) -> None:
        """
        模板有效性校验
        """
        # TODO: 完善校验
        if template.executors:
            for exec_wrapper in template.executors:
                if not iscoroutinefunction(exec_wrapper.executor):
                    raise BotException("事件执行方法必须为异步函数")
                if not iscoroutinefunction(exec_wrapper.params[-1]) or not iscoroutinefunction(exec_wrapper.params[-2]):
                    raise BotException("回调方法必须为异步函数")
        

    @classmethod
    def load_plugin(cls, plugin_path: str, responder: IActionResponder) -> BotPlugin:
        module = cls._load_main(plugin_path)
        template = cls._load_template(module)
        cls._template_verify(template)
        return BotPlugin(template, responder)
