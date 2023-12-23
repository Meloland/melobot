import re

from ..interface.typing import *
from ..interface.utils import BotParser, ParseArgs
from ..interface.exceptions import BotValueError
from ..models.event import MsgEvent


__all__ = (
    'BotParser',
    'CmdParser'
)


class CmdParser(BotParser):
    """
    命令解析器，通过解析命令名和参数的形式，解析字符串。
    命令起始符和命令间隔符不允许包含 引号，逗号，各种括号，反斜杠，数字，英文，空格
    """


    class StringFilter():
        """
        字符串过滤器，对可能干扰命令解析的字符进行过滤
        """
        def __init__(self, pattern: str=r'\t') -> None:
            self.filter_regex = re.compile(pattern)

        def purify(self, text: str):
            return self.filter_regex.sub('', text).strip(' ') \
            .strip('\r\n') \
            .strip('\n') \
            .strip('\r') \
            .strip(' ') \
        

    def __init__(self, cmd_start: Union[str, List[str]], cmd_sep: Union[str, List[str]]) -> None:
        super().__init__()
        self.start_tokens = cmd_start if isinstance(cmd_start, list) else [cmd_start]
        self.sep_tokens = cmd_sep if isinstance(cmd_sep, list) else [cmd_sep]
        self.ban_regex = re.compile(r'[\'\"\\ \,\(\)\[\]\{\}a-zA-Z0-9]')
        self.filter = CmdParser.StringFilter()
        self._build_parse_regex()

        if self.ban_regex.findall(''.join(cmd_sep+cmd_start)):
            raise BotValueError('不支持的命令起始符或命令间隔符！')

    def _build_parse_regex(self):
        """
        建立用于命令解析的正则 Pattern 对象，包含命令起始符正则 pattern 和
        命令间隔符正则 pattern
        """
        temp_regex = re.compile(r'([\`\-\=\~\!\@\#\$\%\^\&\*\(\)\_\+\[\]\{\}\|\:\,\.\/\<\>\?])')
        if not len(set(self.sep_tokens) & set(self.start_tokens)):
            self.cmd_sep = [temp_regex.sub(r'\\\1', sep_token) for sep_token in self.sep_tokens]
            self.cmd_start = [temp_regex.sub(r'\\\1', start_token) for start_token in self.start_tokens]
            self.sep_parse_regex = re.compile(rf"{'|'.join(self.cmd_sep)}")
            self.start_parse_regex = re.compile(rf"{'|'.join(self.cmd_start)}")
        else:
            raise BotValueError("起始符不能和间隔符重合")

    def _split_string(self, string: str, regex: re.Pattern, popFirst: bool=True) -> List[str]:
        """
        按照指定正则 pattern，对 string 进行分割
        """
        # 将复杂的各种分隔符替换为 特殊字符，方便分割
        temp_string = regex.sub('\u0000', string)
        temp_list = re.split('\u0000', temp_string)
        if popFirst: temp_list.pop(0)
        return list(filter(lambda x:x != '', temp_list))
    
    def _parse(self, text: str, textFilter: bool=True) -> Union[List[List[str]], None]:
        """
        解析 text
        """
        if textFilter: pure_string = self.filter.purify(text)
        else: pure_string = text
        cmd_strings = self._split_string(pure_string, self.start_parse_regex)
        cmd_list = [self._split_string(s, self.sep_parse_regex, False) for s in cmd_strings]
        cmd_list = list(filter(lambda x: x != [], cmd_list))
        return cmd_list if len(cmd_list) else None

    def parse(self, event: MsgEvent) -> Union[List[ParseArgs], None]:
        params_list = self._parse(event.text)
        if params_list:
            return [ParseArgs(params) for params in params_list]
        else:
            return None

