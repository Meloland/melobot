melobot.handle
==============

处理流
----------------

.. autoclass:: melobot.handle.Flow
    :members:

处理节点
-----------

.. autofunction:: melobot.handle.node

.. autofunction:: melobot.handle.no_deps_node

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

.. autofunction:: melobot.handle.get_flow_store

.. autofunction:: melobot.handle.get_flow_records

.. autofunction:: melobot.handle.get_event

.. autofunction:: melobot.handle.try_get_event
