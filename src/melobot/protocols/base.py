from ..adapter.base import Adapter
from ..io.base import AbstractInSource, AbstractOutSource
from ..typ.cls import BetterABC, abstractattr


class ProtocolStack(BetterABC):
    """协议栈抽象类

    子类需要把以下属性按 :func:`.abstractattr` 的要求实现
    """

    inputs: set[AbstractInSource] = abstractattr()
    """该协议栈兼容的输入源序列

       :meta hide-value:
    """

    outputs: set[AbstractOutSource] = abstractattr()
    """该协议栈兼容的输出源序列

       :meta hide-value:
    """

    adapter: Adapter = abstractattr()
    """该协议栈兼容的适配器

       :meta hide-value:
    """
