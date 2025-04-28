melobot.log
===========

在 3.2.0 版本，日志系统进行了重构，现在推荐通过“域”规则设置和获取日志器。依据“域”来获取日志代理对象，可使用 :func:`.get_logger`，或使用上下文变量 :data:`~melobot.log.logger`。日志代理对象是通用日志器的子类，它将会内含一个有效的日志器或单纯包含空，包含空时自动丢弃所有日志记录

- 域总共有三层：顶级域、bot 域和模块域。顶级域只存在一个日志器，bot 域依据 bot 上下文构建，模块域依据文件路径树构建

- 当获取“当前域”的日志代理对象时，首先沿本模块对应的文件/目录结点向上查找存在日志器的路径结点。查找到的第一个不为 `None` 的日志器，将会提供给日志代理对象使用。如果向上查找到根路径都没有可用日志器，则开始查找 bot 域可用的日志器。当前调用点的 bot 上下文中，如果有可用 bot 存在（例如调用点在处理流中）且 bot 日志器不为空，此时就使用该 bot 的日志器。否则继续尝试顶级域日志器，如果依然为空，那么最终日志代理对象内含空，丢弃日志

- 设置顶级域的日志器使用 :func:`.set_global_logger` 方法，设置 bot 域的日志器在初始化 bot 时进行，设置模块域的日志器使用 :func:`.set_module_logger` 方法

- 值得注意的是：melobot 会默认设置顶级日志器，保证其存在且不为空，当然你也可以随时替换。另外 :class:`.Bot` 初始化方法的 `enable_log` 参数已经移除

一些实际例子：

.. code-block:: python

    # 使用日志器的一方，例如 xxx.py
    from melobot.log import logger

    # 定义日志器的一方，一般是 bot 程序的主入口脚本处：
    from melobot.log import set_module_logger, Logger, NullLogger
    # 为 melobot 核心模块对应路径结点设置一个日志器
    set_module_logger("melobot", Logger(...))
    # 设置 melobot.bot.dispatch 模块对应路径结点的日志器为 NullLogger
    # 这样就会停止向上继续查找，从而屏蔽这个模块的日志
    set_module_logger("melobot.bot.dispatch", NullLogger())
    # 再为插件目录下的所有插件设置一个单独的日志器
    set_module_logger("./plugin_dir", Logger(...))

另外 3.2.0 版本开始，提供 :func:`.log_exc` 方法用于向 melobot 核心模块报告异常信息，并体现在日志或异常回溯栈信息中。

该方法所在模块为：`melobot.log.report`，此信息可用于调整被报告异常日志输出时使用的日志器。

额外需要注意：通过依赖注入获取 `logger` 的方式依旧可用，并且该特性预计长期支持。

.. code-block:: python

    from melobot.log import GenericLogger

    async def _(logger: GenericLogger) -> None:
        # 通过依赖注入获取的 logger，永远是当前 bot 上下文中的 bot 的日志器
        # 按照依赖注入规则，如果日志器为空：
        # 对于事件处理方法，就不会被执行
        # 对于 hook 方法，就会发出一个“依赖不匹配”异常
        ...


内置日志部件
----------------

.. autoclass:: melobot.log.Logger
    :members:
    :exclude-members: __new__, findCaller, makeRecord

.. autoclass:: melobot.log.NullLogger
    :members:
    :exclude-members: generic_lazy, generic_obj

.. autoclass:: melobot.log.LogLevel
    :members:
    :exclude-members: __new__

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

上下文操作与变量
----------------

.. data:: melobot.log.logger

    当前域对应的日志器，满足 :class:`~melobot.log.GenericLogger` 的接口

.. autofunction:: melobot.log.get_logger

    获取当前域对应的日志器的方法，与上面的上下文变量行为一致

.. autofunction:: melobot.log.set_global_logger

.. autofunction:: melobot.log.set_module_logger

.. autofunction:: melobot.log.log_exc
