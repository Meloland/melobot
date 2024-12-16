melobot.io
==========

输入输出层部件
----------------

.. autoclass:: melobot.io.AbstractSource
    :members:
    :inherited-members:

.. autoclass:: melobot.io.AbstractInSource
    :members:
    :exclude-members: open, opened, close

.. autoclass:: melobot.io.AbstractOutSource
    :members:
    :exclude-members: open, opened, close

.. autoclass:: melobot.io.AbstractIOSource
    :members:
    :exclude-members: open, opened, close, input, output

.. autoclass:: melobot.io.SourceLifeSpan
    :members:

输入输出包基类
------------------

.. autoclass:: melobot.io.InPacket
    :members:
    :exclude-members: __init__

.. autoclass:: melobot.io.OutPacket
    :members:
    :exclude-members: __init__

.. autoclass:: melobot.io.EchoPacket
    :members:
    :exclude-members: __init__, ok, status, prompt, noecho
