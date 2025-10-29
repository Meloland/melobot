:tocdepth: 3

console.adapter
===============

适配器
------------

.. autoclass:: melobot.protocols.console.adapter.Adapter
    :exclude-members: __init__

事件
--------------

.. autoclass:: melobot.protocols.console.adapter.event.Event
    :exclude-members: Model, __init__, resolve

.. autoclass:: melobot.protocols.console.adapter.event.StdinEvent
    :exclude-members: Model, __init__, resolve

行为（动作）
---------------------

一般来说，无需手动通过这些原始的行为类构建行为，直接调用 :class:`~.console.adapter.base.Adapter` 的输出方法即可。

但仍然提供这些接口用于高级操作。

.. automodule:: melobot.protocols.console.adapter.action

回应
---------------

此协议无需回应，因此目前不会创建回应对象。

以下所有对象不会被行为操作方法返回。但仍然提供用于类型注解。

.. autoclass:: melobot.protocols.console.adapter.echo.Echo
    :exclude-members: Model, __init__, resolve, result
