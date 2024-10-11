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
