melobot.log
===========

内置日志部件
----------------

.. autoclass:: melobot.log.Logger
    :members:
    :exclude-members: __new__, findCaller

.. autoclass:: melobot.log.LogLevel
    :members:
    :exclude-members: __new__

.. autofunction:: melobot.log.get_logger

通用日志部件与通用修补
----------------------

.. autoclass:: melobot.log.GenericLogger
    :members:

.. autofunction:: melobot.log.logger_patch

.. autoclass:: melobot.log.LazyLogMethod
    :members:
    :exclude-members: __init__

.. autoclass:: melobot.log.StandardPatch
    :members:

.. autoclass:: melobot.log.LoguruPatch
    :members:

.. autoclass:: melobot.log.StructlogPatch
    :members:

上下文动态变量
----------------

.. data:: melobot.log.logger

    当前上下文中的日志器，类型为 :class:`~melobot.log.GenericLogger`
