import ntpath
import os
import posixpath
import sys

import toml

from ..interface.typing import *

__all__ = (
    'BOT_CONFIG'
)


class ConfigGenerator:
    """
    配置管理器
    """
    def __init__(self, ConfigDirPath: str) -> None:
        self.config = {}
        self.default_config = DEFAULT_CONFIG
        self.default_config_text = DEFAULT_CONFIG_TEXT
        self.config_dir = ConfigDirPath
        self.config_path = os.path.join(
            self.config_dir, 'bot_config.toml'
        )

    def get(self) -> dict:
        """
        获取配置文件
        """
        self.init_config()
        self.fill_defaults()
        return self.config

    def init_config(self) -> None:
        """
        初始化配置项，若没有配置文件，则创建。
        若存在配置文件，则读取配置
        """
        if not os.path.exists(self.config_dir):
            os.mkdir(self.config_dir)
        if not os.path.exists(self.config_path):
            with open(self.config_path, 'w', encoding='utf-8') as fp:
                fp.write(self.default_config_text)
            print("未检测到配置文件，已自动生成，请填写配置后重启 bot")
            sys.exit(0)
        else:
            with open(self.config_path, encoding='utf-8') as fp:
                self.config = toml.load(fp)

    def fill_defaults(self) -> None:
        """
        使用默认值填充不存在的配置项
        """
        for item_name in self.default_config.keys():
            if self.config.get(item_name) is None:
                self.config[item_name] = self.default_config[item_name]


class BotConfig:
    """
    配置类
    """
    def __init__(self, config_dir: str) -> None:
        self.connect_host: str = None
        self.connect_port: int = None
        self.log_level: str = None
        self.cooldown_time: int = None
        self.log_dir_path: str = None

        self._build(config_dir)

    def _build(self, config_dir: str) -> None:
        self._raw = ConfigGenerator(config_dir).get()
        self.connect_host = self._raw['CONNECT_HOST']
        self.connect_port = self._raw['CONNECT_PORT']
        self.log_level = self._raw['LOG_LEVEL']
        self.cooldown_time = self._raw['COOLDOWN_TIME']
        self.log_dir_path = self._raw['LOG_DIR_PATH']

        if sys.platform == 'win32' and ntpath.isabs(self.log_dir_path):
            return
        if posixpath.isabs(self.log_dir_path):
            return
        self.log_dir_path = os.path.join(config_dir, self.log_dir_path)


DEFAULT_CONFIG_TEXT = \
"""# 以下为自动生成的默认配置文件

# go-cq 服务的 host
CONNECT_HOST = "localhost"
# go-cq 服务的端口
CONNECT_PORT = 8080
# 全局日志等级（LOG, INFO, DEBUG, WARN, WARNING, CRITICAL）
LOG_LEVEL = "INFO"
# 消息发送冷却时间（防止发送消息过快被风控）
COOLDOWN_TIME = 0.5
# 日志输出目录（会在该目录初始化 app.log 文件）
LOG_DIR_PATH = "../logs"
"""


DEFAULT_CONFIG = {
    "CONNECT_HOST": "localhost",
    "CONNECT_PORT": 8080,
    "LOG_LEVEL": "INFO",
    "COOLDOWN_TIME": 0.5,
    "LOG_DIR_PATH": "../logs"
}
