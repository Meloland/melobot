import json
import logging
import logging.config
import logging.handlers
import os
import time
from asyncio import iscoroutine
from logging import CRITICAL, DEBUG, ERROR, INFO, WARN, WARNING, Logger
from .Config import BotConfig
from .Typing import *


__all__ = [
    'BotResource',
    'BOT_STORE'
]


class GlobalMeta:
    """
    全局元信息类
    """
    def __init__(self) -> None:
        self.version: str
        self.developer: str
        self.proj_name: str
        self.proj_url: str
        self.root_path: str
        self.kernel_timeout: int
        self.prior_queue_len: int

        self.cmd_mode: str
        self.bot_id: str
        self.bot_nickname: str

        self.__dict__.update({
            'version': '2.0.0-Alpha4 (dev-edition)',
            'developer': 'AiCorein',
            'proj_name': 'Qbot-MeloBot',
            'proj_url': 'https://github.com/AiCorein/Qbot-MeloBot',
            'root_path': '\\'.join(os.path.dirname(__file__).split('\\')[:-1]),
            'kernel_timeout': 5,
            'prior_queue_len': 2,
        })
        self.working_status = True

    def __setattr__(self, __name: str, __value: Any) -> None:
        if __name == 'working_status':
            self.__dict__[__name] = __value
        else:
            raise PermissionError("除 working_status 外, 其余元信息不可更改")


class GlobalLoggerBuilder:
    """
    全局日志器类
    """
    LOG_COLOR_CONFIG = {
        'DEBUG': 'purple',  # cyan white
        'INFO': 'white',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }

    LOG_LEVEL_MAP = {
        'DEBUG': DEBUG,
        'INFO': INFO,
        'WARN': WARN,
        'WARNING': WARNING,
        'ERROR': ERROR,
        'CRITICAL': CRITICAL,
    }

    LOG_CONFIG = {
        'version': 1,  # 必填项，值只能为1
        'disable_existing_loggers': True,  # 选填，默认为True，将以向后兼容的方式启用旧行为，此行为是禁用任何现有的非根日志记录器，除非它们或它们的祖先在日志配置中显式命名。如果指定为False，则在进行此调用时存在的记录器将保持启用状态
        'incremental': False,  # 选填，默认为False，作用，为True时，logging完全忽略任何formatters和filters，仅处理handlers的level

        'formatters':  # 格式器配置专用key，在这里配置formatter，可配置复数formatter
            {
                'myformatter1': {
                    '()': 'colorlog.ColoredFormatter',  # 必填，格式器对应的类
                    'format': '%(log_color)s[%(asctime)s] [%(levelname)s]: %(message)s',  # fmt格式
                    'datefmt': '%Y-%m-%d %H:%M:%S',  # 日期时间格式
                    'log_colors': LOG_COLOR_CONFIG
                },
                'myformatter2': {
                    'class': 'logging.Formatter',  # 将class改为()，代表不使用logging的类，使用我们重新定义的类
                    'format': '[%(asctime)s] [%(filename)s %(lineno)d] [%(levelname)s]: %(message)s',  # fmt格式
                    'datefmt': '%Y-%m-%d %H:%M:%S'  # 日期时间格式
                }
            },

        'handlers':  # 处理器配置专用key，在这里配置handler，可配置复数handler
            {
                'console_handler': {
                    'class': 'logging.StreamHandler',  # 必填，处理器对应的类
                    'level': logging.INFO,  # 选填，处理器的日志级别，可填字符串'info'，或者logging.INFO
                    'formatter': 'myformatter1',  # 选填，这里要填写formatters字典中的键
                },
                'file_handler': {
                    'class': 'logging.handlers.RotatingFileHandler',  # 必填，处理器对应的类
                    'level': logging.DEBUG,  # 选填，处理器的日志级别，可填字符串'info'，或者logging.INFO
                    'formatter': 'myformatter2',  # 选填，这里要填写formatters字典中的键
                    'filename': './logs/app.log',  # filehandler特有参数，文件名
                    'maxBytes': 1024*1024,  # 文件大小
                    'backupCount': 3,  # 备份数量
                    'encoding': 'UTF-8',  # 编码格式
                }
            },

        'loggers':  # 记录器配置专用key，在这里配置logger，可配置复数logger
            {
                'the_logger': {
                    'handlers': ['console_handler', 'file_handler'],  # 列表形式，元素填handlers字典中的handler
                    'level': logging.DEBUG,  # 选填，记录器的日志级别，不填则默认Warning级别
                    'propagate': False,  # 选填，为False时，禁止将日志消息传递给父级记录器
                }
            },
    }

    def __init__(self) -> None:
        if not os.path.exists('./logs'):
            os.mkdir('./logs')
    
    def build(self, log_level: str) -> Logger:
        self.log_level = log_level
        GlobalLoggerBuilder.LOG_CONFIG['handlers']['console_handler']['level'] = GlobalLoggerBuilder.LOG_LEVEL_MAP[log_level]
        logging.config.dictConfig(GlobalLoggerBuilder.LOG_CONFIG)
        return logging.getLogger('the_logger')


class BotResource:
    """
    bot 资源结点。支持嵌套动态属性赋值。
    可以直接指定资源的值，或指定加载或释放方法（可为异步或同步）
    使用反射实现。
    """
    class ResourceInfo:
        """
        资源结点信息类
        """
        def __init__(self, value: object, type: str, load: Callable, dispose: Callable) -> None:
            self.crt_time: float
            self.__dict__['crt_time'] = time.time()
            self.value = value
            self.type: str
            self.__dict__['type'] = type
            self.load = load
            self.dispose = dispose
            
            self.disposed = False
            self.loaded = False

        def __setattr__(self, __name: str, __value: Any) -> None:
            if __name == 'crt_time' or __name == 'type':
                raise PermissionError(f"{__name} 属性不可变更")
            else:
                self.__dict__[__name] = __value
    
    def __init__(self, value: object=None, load: Callable=None, dispose: Callable=None) -> None:
        type = "class" if value is None else "resource"
        self._info: BotResource.ResourceInfo
        self.__dict__['_info'] = BotResource.ResourceInfo(value, type, load, dispose)

    def __getattr__(self, __name: str) -> "BotResource":
        self.__dict__[__name] = BotResource()
        return self.__dict__[__name]
    
    def __setattr__(self, __name: str, __value: object) -> None:
        if not isinstance(__value, BotResource):
            raise ValueError("值必须先通过 BotResource 包装")
        if __name != '_info':
            self.__dict__[__name] = __value
        else:
            raise ValueError("不能修改资源结点预置的 _info 属性")

    def __get_attrs(self) -> Dict:
        """
        获取所有除 _info 外的，动态添加的属性（资源结点）
        """
        try:
            attr_dict = self.__dict__.copy()
            attr_dict.pop("_info")
            attr_dict.pop("__iter__")
        except KeyError:
            pass
        return attr_dict

    @property
    def num(self) -> int:
        """
        获取结点下资源的个数，不包括 "class" 类型结点
        """
        if self._info.type == 'resource': 
            return 1

        count = 0
        for attrName, attrVal in self.__get_attrs().items():
            count += attrVal.num
        return count

    async def load_all(self) -> None:
        """
        加载该结点下所有需要加载的资源
        """
        if self._info.loaded == False: 
            if self._info.load is not None:
                res = self._info.load()
                if iscoroutine(res):
                    await res
                self._info.value = res
                self._info.loaded = True
                self._info.__dict__['type'] = 'resource'
            else:
                self._info.loaded = True
        
        for attrName, attrVal in self.__get_attrs().items():
            await attrVal.load_all()

    async def dispose_all(self) -> None:
        """
        释放该资源结点下所有需要释放的资源
        """
        if self._info.disposed == False:
            if self._info.dispose is not None:
                res = self._info.dispose(self._info.value)
                if iscoroutine(res):
                    await res
                self._info.value = None
                self._info.disposed = True
            else:
                self._info.disposed = True
        
        for attrName, attrVal in self.__get_attrs().items():
            await attrVal.dispose_all()

    def val(self, value: object=None) -> object:
        """
        获取或设置 self._info.value
        """
        if value is not None:
            self._info.value = value
        return self._info.value


class IdWorker:
    """
    雪花算法生成 ID
    """
    def __init__(self, datacenter_id, worker_id, sequence=0) -> int:
        self.MAX_WORKER_ID = -1 ^ (-1 << 3)
        self.MAX_DATACENTER_ID = -1 ^ (-1 << 5)
        self.WOKER_ID_SHIFT = 12
        self.DATACENTER_ID_SHIFT = 12 + 3
        self.TIMESTAMP_LEFT_SHIFT = 12 + 3 + 5
        self.SEQUENCE_MASK = -1 ^ (-1 << 12)
        self.STARTEPOCH = 1064980800000
        # sanity check
        if worker_id > self.MAX_WORKER_ID or worker_id < 0:
            raise ValueError('worker_id 值越界')
        if datacenter_id > self.MAX_DATACENTER_ID or datacenter_id < 0:
            raise ValueError('datacenter_id 值越界')
        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.sequence = sequence
        self.last_timestamp = -1  # 上次计算的时间戳

    def __gen_timestamp(self) -> int:
        """
        生成整数时间戳
        """
        return int(time.time() * 1000)

    def get_id(self) -> int:
        """
        获取新 ID
        """
        timestamp = self.__gen_timestamp()

        # 时钟回拨
        if timestamp < self.last_timestamp:
            raise ValueError(f'时钟回拨，{self.last_timestamp} 前拒绝 id 生成请求')
        if timestamp == self.last_timestamp:
            self.sequence = (self.sequence + 1) & self.SEQUENCE_MASK
            if self.sequence == 0:
                timestamp = self.__til_next_millis(self.last_timestamp)
        else:
            self.sequence = 0
        self.last_timestamp = timestamp
        new_id = ((timestamp - self.STARTEPOCH) << self.TIMESTAMP_LEFT_SHIFT) | (self.datacenter_id << self.DATACENTER_ID_SHIFT) | (
                    self.worker_id << self.WOKER_ID_SHIFT) | self.sequence
        return new_id

    def __til_next_millis(self, last_timestamp) -> int:
        """
        等到下一毫秒
        """
        timestamp = self.__gen_timestamp()
        while timestamp <= last_timestamp:
            timestamp = self.__gen_timestamp()
        return timestamp


class BotStore:
    """
    bot 全局对象，对 Bot 的所有资源和数据进行存储、访问和修改
    """
    def __init__(self) -> None:
        self.meta = GlobalMeta()
        self.config = self.__build_config()
        self.logger = GlobalLoggerBuilder().build(self.config.log_level)
        self.monitor = None
        self.id_worker = IdWorker(1, 1, 0)

        self.resources = BotResource()
        self.plugins = BotResource()
        self.cmd = BotResource({})

    def __build_config(self) -> BotConfig:
        configObj = BotConfig()
        configObj.build(os.path.join(self.meta.root_path, 'config'))
        return configObj


BOT_STORE = BotStore()
# 加载关键词词表并简单处理
corpus_path = os.path.join(
    BOT_STORE.meta.root_path, 'config', 'key_ans.json'
)
with open(corpus_path, encoding='utf-8') as fp:
    raw_dict = json.load(fp)
mapped_dict = {}
for rule in raw_dict:
    for keyword in rule['keys']:
        mapped_dict[keyword] = {
            "prob": rule['prob'],
            "ans": rule['ans']
        }
BOT_STORE.resources.key_ans = BotResource(mapped_dict)
