"""
MeloBot 是插件化管理、基于异步会话机制的 qbot 开发框架。

项目源码和文档，请参考：https://github.com/aicorein/melobot
"""

from .bot import MeloBot
from .context import *
from .io import *
from .meta import MetaInfo
from .models import *
from .plugin import *
from .types import *
from .utils import *

__version__ = MetaInfo().VER
