import os
import sys
import toml
from .globalPattern import *


defaultConfigText = \
"""# 以下为自动生成的默认配置文件
# 配置项参考：https://proj.glowmem.com/MeloBot/config/botConfig/
#
# bot 工作流程配置（目前与 cq 的通信暂时只支持正向 ws）
[operation]
# cq 正向 ws 的 host
CONNECT_HOST = "localhost"
# cq 正向 ws 的 port
CONNECT_PORT = 8080


# 个性化配置
[custom]
# bot owner（只能设置一个人），拥有最高权限，只有 owner 可以发送优先命令和一些生命周期命令
OWNER = -1
# 群聊使用白名单机制：必须白名单内的群才能触发 bot 行为
WHITE_GROUP_LIST = []
# bot 对自己的称呼
BOT_NAME = "MeloBot"


# 命令功能配置，注意：以下配置对优先命令也生效
[cmd]
# 注意：命令起始符和命令分隔符都不能包含以下任意字符之一：
# (引号，逗号，各种括号，反斜杠，数字，英文，空格和控制字符)
# 同时注意：命令起始符不能是命令分隔符的前缀
#
# 命令起始符
COMMAND_START = ['~']
# 命令分隔符
COMMAND_SEP = ['#']
"""


defaultConfig = {
    "operation": {
        "CONNECT_HOST": "localhost",
        "CONNECT_PORT": 8080,
        "WORK_QUEUE_LEN": 20,
        "LOG_LEVEL": "INFO",
        "TASK_TIMEOUT": 15,
        "COOLDOWN_TIME": 1,
        "WORKING_TIME": -1,
    },
    "custom": {
        "OWNER": None,
        "SUPER_USER": [],
        "WHITE_LIST": [],
        "BLACK_LIST": [],
        "WHITE_GROUP_LIST": [],
        "ENABLE_SYS_ROLE": False,
        "NICK_NAME": [],
        "BOT_NAME": 'MeloBot'
    },
    "cmd": {
        "COMMAND_START": [],
        "COMMAND_SEP": []
    }
}


class ConfigManager(Singleton):
    """
    配置管理器
    """
    def __init__(self) -> None:
        super().__init__()
        self.config = {}
        self.defaultConfig = defaultConfig
        self.defaultConfigText = defaultConfigText
        self.configDir = os.path.join(
            os.path.dirname(__file__), '..', 'config'
        )
        self.configPath = os.path.join(
            self.configDir, 'botConfig.toml'
        )

    def get_config(self) -> dict:
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
        if not os.path.exists(self.configDir):
            os.mkdir(self.configDir)
        if not os.path.exists(self.configPath):
            with open(self.configPath, 'w', encoding='utf-8') as fp:
                fp.write(self.defaultConfigText)
            print("未检测到配置文件，已自动生成，请填写配置后重启 bot")
            sys.exit(1)
        else:
            with open(self.configPath, encoding='utf-8') as fp:
                self.config = toml.load(fp)

    def fill_defaults(self) -> None:
        """
        使用默认值填充不存在的配置项
        """
        for configClass in self.defaultConfig.keys():
            if configClass not in self.config.keys():
                self.config[configClass] = {}
            for item, val in self.defaultConfig[configClass].items():
                if item not in self.config[configClass]:
                    self.config[configClass][item] = val