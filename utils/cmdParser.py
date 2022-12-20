from .globalPattern import *
from .globalData import BOT_STORE
from .botLogger import BOT_LOGGER
from logging import Logger
from re import Pattern
from abc import abstractmethod, ABC
import re
import time


class StringFilter():
    """
    字符串过滤器，主要用于精确命令解析，对可能干扰命令解析的字符进行过滤
    但非单例，也可由外部再实例化
    """
    def __init__(self, pattern: str=r'[\'\"\\\r\n\t]') -> None:
        super().__init__()
        self.filter_regex = re.compile(pattern)

    def purify(self, text: str):
        return self.filter_regex.sub('', text).strip(' ')


class BaseCmdParser(Singleton, ABC):
    """
    命令解析器基类，所有子类应该实现 parse 方法，
    但注意：parse 方法可以返回空列表，代表没有有效的命令触发
    """
    @abstractmethod
    def parse(self, text: str) -> list:
        pass


class ExactCmdParser(BaseCmdParser, Singleton):
    """
    精确命令解析器，根据消息中指定的命令标志进行解析
    """
    def __init__(self, cmd_start: list, cmd_sep: list, logger: Logger) -> None:
        super().__init__()
        self.start_tokens = cmd_start
        self.sep_tokens = cmd_sep
        self.ban_regex = re.compile(r'[\'\"\\ \,\(\)\[\]\{\}a-zA-Z0-9]')
        self.filter = StringFilter()
        self.LOGGER = logger
        self.single_parse_flag = False
        self.build_parse_regex()
        self.bind_parse_func()

        # 命令起始符和命令间隔符不允许包含 引号，逗号，各种括号，反斜杠，数字，英文，空格
        if self.ban_regex.findall(''.join(cmd_sep+cmd_start)):
            self.LOGGER.error('发生异常：不支持的命令起始符或命令间隔符！')
            raise BotUnsupportCmdFlag('不支持的命令起始符或命令间隔符！')

    def build_parse_regex(self):
        """
        建立用于命令解析的正则 Pattern 对象，包含命令起始符正则 pattern 和
        命令间隔符正则 pattern
        """
        temp_regex = re.compile(r'([\`\-\=\~\!\@\#\$\%\^\&\*\(\)\_\+\[\]\{\}\|\:\,\.\/\<\>\?])')
        # 如果分隔符和起始符没有冲突标志，则是多解析处理逻辑
        if not len(set(self.sep_tokens) & set(self.start_tokens)):
            self.cmd_sep = [temp_regex.sub(r'\\\1', sep_token) for sep_token in self.sep_tokens]
            self.cmd_start = [temp_regex.sub(r'\\\1', start_token) for start_token in self.start_tokens]
            self.sep_parse_regex = re.compile(rf"{'|'.join(self.cmd_sep)}")
            self.start_parse_regex = re.compile(rf"{'|'.join(self.cmd_start)}")
        # 否则是单解析处理逻辑
        else:
            self.single_parse_flag = True
            self.cmd_united = set(self.sep_tokens) | set(self.start_tokens)
            self.cmd_united = [temp_regex.sub(r'\\\1', token) for token in self.cmd_united]
            self.uninted_parse_regex = re.compile(rf"{'|'.join(self.cmd_united)}")
        
        if self.single_parse_flag:
            BOT_STORE['kernel']['CMD_MODE'] = 'single'
        else:
            BOT_STORE['kernel']['CMD_MODE'] = 'multiple'
    
    def parse(self, text: str) -> list:
        """
        解析 text，获得命令列表，其中每个命令又是一个包含子命令的列表。
        注意：结果可能为一个两层空列表
        """
        # 这里留空，具体逻辑将会动态指定
        pass

    def bind_parse_func(self):
        """
        封装 parse 的统一接口
        """
        # 封装为统一接口
        if self.single_parse_flag:
            self.parse = self.single_parse
        else:
            self.parse = self.multi_parse
    
    def single_parse(self, text: str, textFilter=True) -> list:
        """
        解析 text，获得命令列表，其中每个命令又是一个包含子命令的列表
        模式：单解析模式
        注意：结果可能为一个两层空列表
        """
        if textFilter: pure_string = self.filter.purify(text)
        else: pure_string = text
        cmd_strings = self.split_string(pure_string, self.uninted_parse_regex)
        return [cmd_strings] if len(cmd_strings) else [[]]

    
    def multi_parse(self, text: str, textFilter=True) -> list:
        """
        解析 text，获得命令列表，其中每个命令又是一个包含子命令的列表
        模式：多解析模式
        注意：结果可能为一个两层空列表
        """
        if textFilter: pure_string = self.filter.purify(text)
        else: pure_string = text
        cmd_strings = self.split_string(pure_string, self.start_parse_regex)
        cmd_list = [self.split_string(s, self.sep_parse_regex, False) for s in cmd_strings]
        cmd_list = list(filter(lambda x: x != [], cmd_list))
        return cmd_list if len(cmd_list) else [[]]
    
    def split_string(self, string: str, regex: Pattern, popFirst=True) -> list:
        """
        按照指定正则 pattern，对 string 进行分割
        """
        # 将复杂的各种分隔符替换为 双引号，方便分割
        temp_string = regex.sub('\"', string)
        temp_list = re.split('\"', temp_string)
        if popFirst: temp_list.pop(0)
        return list(filter(lambda x:x != '', temp_list))
    
    def prior_check(self, text: str) -> bool:
        """
        专用解析方法，用于检测是否包含优先命令
        """
        cmd_list = self.parse(text)
        if not len(cmd_list[0]): return False
        return any([True for cmd in cmd_list if cmd[0] == 'prior'])


class FuzzyCmdParser(BaseCmdParser, Singleton):
    """
    模糊命令解析器，检测消息中的特定关键词或关键词组合，返回布尔值
    """
    def __init__(self) -> None:
        super().__init__()

    def parse(self, text: str, condition: str, lowerFreq: int=1, pos: str='any') -> bool:
        """
        模糊命令单解析方法，指定关键词，出现频次和位置
        pos 可能取值：any, begin, end
        """
        matches = [matcher.span() for matcher in re.finditer(condition, text)]
        if len(matches) < lowerFreq:
            return False
        if pos == 'any':
            return True
        elif pos == 'begin':
            return matches[0][0] == 0
        elif pos == 'end':
            return matches[-1][-1] == len(text)
        else:
            raise ValueError("无效的 pos 值")

    def multi_parse(self, text: str, condition: list) -> bool:
        """
        模糊命令多解析方法，指定关键词组合
        """
        condition = f"{'|'.join(condition)}"
        matches = [matcher.group() for matcher in re.finditer(condition, text)]
        return all([s in matches for s in condition])


class TimeCmdParser(BaseCmdParser, Singleton):
    """
    时间命令解析器，检测消息是否满足特定时间条件，再决定是否封装为命令
    """
    def __init__(self) -> None:
        super().__init__()
    

    def parse(self, unixSec: int, lowerBound: int=0, upperBound: int=24):
        """
        判断消息时间是否在指定小时区间内，左右闭区间
        """
        return lowerBound <= time.localtime(unixSec)[3] <= upperBound


EC_PARSER = ExactCmdParser(BOT_STORE['cmd']['COMMAND_START'], \
    BOT_STORE['cmd']['COMMAND_SEP'], \
    BOT_LOGGER
)
FC_PARSER = FuzzyCmdParser()
TC_PARSER = TimeCmdParser()


if __name__ == "__main__":
    cp = ExactCmdParser(['~/', './'], ['#/', '!/'], None)
    fp = FuzzyCmdParser()
    tp = TimeCmdParser()
    from time import perf_counter
    a = perf_counter()

    print(cp.parse("""
    这是没用的前置消息
    ~/主命令1#/子命令1!/子命令2
    ~/主命令2!!/子命令3#/子命令4/#
    ./主命令3#/#子命令5/!/子命令6////
    \t\n\n\n\t\t\t\t\n

    """))
    # print(cp.parse('alsdjfl;ajf'))
    # print(fp.parse('12341234', '4'))
    # print(tp.parse(time.time(), 6, 21))

    b = perf_counter()

    cp = ExactCmdParser(['.', '~'], ['#', '.'], None)
    print(cp.parse('\n\t   这是没用的前置消息 #prior.restart,setting.init!123  \t\n'))
    print(b-a)