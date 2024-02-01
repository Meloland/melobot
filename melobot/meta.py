import os
import sys
from typing import Dict, Any


class MetaInfo:
    def __init__(self) -> None:
        self.VER = '2.0.0-pre1'
        self.PROJ_NAME = 'MeloBot'
        self.PROJ_DESC = "A qbot module with friendly interface, session control and plugin-supported."
        self.PROJ_SRC = 'https://github.com/AiCorein/Qbot-MeloBot'
        self.AUTHOR = 'AiCorein'
        self.AUTHOR_EMAIL = 'melodyecho@glowmem.com'
        self.ARGV = sys.argv
        self.PLATFORM = sys.platform
        self.PY_VER = sys.version
        self.PY_INFO = sys.version_info
        self.OS_SEP = os.sep
        self.PATH_SEP = os.pathsep
        self.LINE_SEP = os.linesep
        self.ENV = os.environ

    def get_all(self) -> Dict[str, Any]:
        return dict(self.__dict__.items())

META_INFO = MetaInfo()
