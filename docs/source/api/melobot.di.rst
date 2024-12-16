melobot.di
==========

依赖注入部件
----------------

.. autoclass:: melobot.di.Depends
    :members:
    :exclude-members: fulfill

.. autoclass:: melobot.di.DependsHook
    :members:
    :exclude-members: fulfill

.. autofunction:: melobot.di.inject_deps

依赖注入元数据标记
-------------------

依赖注入时用作 :data:`~.typing.Annotated` 元数据

.. autoclass:: melobot.di.Exclude
    :members:
    :exclude-members: __init__

.. autoclass:: melobot.di.CustomLogger
    :members:
    :exclude-members: __init__

.. autoclass:: melobot.di.Reflect
    :members:
    :exclude-members: __init__
