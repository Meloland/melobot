from abc import abstractmethod

from typing_extensions import Any

from ...typ.cls import BetterABC, abstractattr


class AbstractParseArgs:
    """解析参数抽象类

    子类需要把以下属性按 :func:`.abstractattr` 的要求实现
    """

    vals: Any = abstractattr()
    """解析值

       :meta hide-value:
    """


class Parser(BetterABC):
    """解析器基类

    解析器一般用作从消息文本中按规则批量提取参数
    """

    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    async def parse(self, text: str) -> AbstractParseArgs | None:
        """解析方法

        任何解析器应该实现此抽象方法

        :param text: 消息文本内容
        :return: 解析结果，为空代表没有有效的解析参数

        """
        raise NotImplementedError
