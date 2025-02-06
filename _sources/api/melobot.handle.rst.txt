melobot.handle
==============

处理流
----------------

.. autoclass:: melobot.handle.Flow
    :members:
    :exclude-members: on_priority_reset, starts, ends, run


.. autoclass:: melobot.handle.FlowNode
    :members:
    :exclude-members: __init__, process

处理节点
-----------

.. autofunction:: melobot.handle.node

.. autofunction:: melobot.handle.no_deps_node

流装饰器
----------

流装饰相关的组件，可以将一个普通函数装饰为一个处理流。

这些组件，在 melobot 的教程中，早期我们称它们为“事件绑定方法”或“事件绑定函数”。

.. autoclass:: melobot.handle.FlowDecorator
    :exclude-members: auto_flow_wrapped

.. autofunction:: melobot.handle.on_event

.. autofunction:: melobot.handle.on_text

.. autofunction:: melobot.handle.on_start_match

.. autofunction:: melobot.handle.on_contain_match

.. autofunction:: melobot.handle.on_end_match

.. autofunction:: melobot.handle.on_full_match

.. autofunction:: melobot.handle.on_regex_match

.. autofunction:: melobot.handle.on_command

处理流控制
-------------

.. autofunction:: melobot.handle.nextn

.. autofunction:: melobot.handle.block

.. autofunction:: melobot.handle.bypass

.. autofunction:: melobot.handle.rewind

.. autofunction:: melobot.handle.stop

.. autofunction:: melobot.handle.flow_to

处理流状态
----------------

.. autoclass:: melobot.handle.FlowStore
    :members:

.. autoclass:: melobot.handle.FlowRecordStage
    :members:

.. autoclass:: melobot.handle.FlowRecord
    :members:
    :exclude-members: __init__

.. autofunction:: melobot.handle.get_flow_store

.. autofunction:: melobot.handle.get_flow_records

.. autofunction:: melobot.handle.get_event

.. autofunction:: melobot.handle.try_get_event

弃用项，临时存在
----------------

.. autofunction:: melobot.handle.GetParseArgs
