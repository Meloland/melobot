:tocdepth: 3

melobot.base
=====================

abc 模块
-----------------------

本模块包含 melobot 重要的抽象类或基类。

.. autoclass:: melobot.base.abc.AbstractConnector
   :members:
   :exclude-members: __init__

.. autoclass:: melobot.base.abc.BotEvent
   :members:
   :exclude-members: __init__

.. autoclass:: melobot.base.abc.BotAction
   :members:
   :exclude-members: __init__

.. autoclass:: melobot.base.abc.SessionRule
   :members:

.. autoclass:: melobot.base.abc.BotChecker
   :members:

.. autoclass:: melobot.base.abc.WrappedChecker
   :members:
   :exclude-members: __init__, check

.. autoclass:: melobot.base.abc.BotMatcher
   :members:

.. autoclass:: melobot.base.abc.WrappedMatcher
   :members:
   :exclude-members: __init__, match

.. autoclass:: melobot.base.abc.BotParser
   :members:

exceptions 模块
------------------------------

本模块包含 melobot 的异常类，此处仅展示对外部有利用价值的异常类。

.. autoclass:: melobot.base.exceptions.BotException
   :exclude-members: __init__

.. autoclass:: melobot.base.exceptions.BotSessionTimeout
   :exclude-members: __init__

tools 模块
--------------------------

本模块包含了 melobot 内部使用的工具类和工具函数，它们也可被外部使用。

.. autoclass:: melobot.base.tools.RWController
    :members:

.. autofunction:: melobot.base.tools.get_id

.. autofunction:: melobot.base.tools.this_dir

.. autofunction:: melobot.base.tools.to_async

.. autofunction:: melobot.base.tools.to_coro

.. autofunction:: melobot.base.tools.to_task

.. autofunction:: melobot.base.tools.lock

.. autofunction:: melobot.base.tools.cooldown

.. autofunction:: melobot.base.tools.semaphore

.. autofunction:: melobot.base.tools.timelimit

.. autofunction:: melobot.base.tools.speedlimit

.. autofunction:: melobot.base.tools.call_later

.. autofunction:: melobot.base.tools.call_at

.. autofunction:: melobot.base.tools.async_later

.. autofunction:: melobot.base.tools.async_at

.. autofunction:: melobot.base.tools.async_interval

typing 模块
--------------------------

本模块包含了 melobot 自定义的、用于类型注解的类型。可供外部参考。

.. autoclass:: melobot.base.typing.MsgSegment
   :members:
   :undoc-members:

.. autoclass:: melobot.base.typing.StdCustomNodeData
   :members:
   :undoc-members:

.. autoclass:: melobot.base.typing.GocqCustomNodeData
   :members:
   :undoc-members:

.. autoclass:: melobot.base.typing.ReferNodeData
   :members:
   :undoc-members:

.. autoclass:: melobot.base.typing.MsgNode
   :members:
   :undoc-members:

.. autoclass:: melobot.base.typing.ParseArgs
   :members:
   :undoc-members:

.. autoclass:: melobot.base.typing.LogicMode
   :members:
   :undoc-members:
   :exclude-members: calc, seq_calc

.. autoclass:: melobot.base.typing.User
   :members:
   :undoc-members:
   :exclude-members: __new__

.. autoclass:: melobot.base.typing.PriorLevel
   :members:
   :undoc-members:
   :exclude-members: __new__

.. autoclass:: melobot.base.typing.BotLife
   :members:
   :undoc-members:

.. autoclass:: melobot.base.typing.Void
   :members:

.. data:: melobot.base.typing.VoidType

    “无值”对象的类型标注，定义如下：

    .. code:: python

       VoidType: TypeAlias = Type[Void]

.. data:: melobot.base.typing.T

   泛型 T，无约束

.. data:: melobot.base.typing.T1

   泛型 T1，无约束

.. data:: melobot.base.typing.T2

   泛型 T2，无约束

.. data:: melobot.base.typing.T3

   泛型 T3，无约束

.. data:: melobot.base.typing.P

   :obj:`~typing.ParamSpec` 泛型 P，无约束

