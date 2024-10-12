melobot.di
==========

依赖注入部件
----------------

.. autoclass:: melobot.di.Depends
    :members:

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
