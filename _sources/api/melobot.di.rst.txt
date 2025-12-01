melobot.di
==========

依赖注入部件
----------------

.. autoclass:: melobot.di.Depends
    :members:
    :exclude-members: fulfill

.. autoclass:: melobot.di.CbDepends
    :members:
    :exclude-members: fulfill

.. autofunction:: melobot.di.inject_deps

依赖注入元数据标记
-------------------

依赖注入时用作 :data:`~.typing.Annotated` 元数据，只能对自动依赖使用。也就是说不能和 :class:`.Depends` 同时放在 :data:`~.typing.Annotated` 中。

.. autoclass:: melobot.di.Exclude
    :members:
    :exclude-members: __init__

.. autoclass:: melobot.di.Reflect
    :members:
    :exclude-members: __init__

.. autoclass:: melobot.di.MatchEvent
    :members:
    :exclude-members: __init__
