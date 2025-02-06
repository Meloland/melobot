:tocdepth: 2

melobot.typ
===========

.. autoclass:: melobot.typ.LogicMode
    :members:

.. autofunction:: melobot.typ.is_type

.. autoclass:: melobot.typ.BetterABCMeta
    :members:
    :exclude-members: __call__, DummyAttribute

.. autoclass:: melobot.typ.BetterABC
    :members:

.. autofunction:: melobot.typ.abstractattr

.. autoclass:: melobot.typ.SingletonMeta
    :exclude-members: __call__

.. autoclass:: melobot.typ.SingletonBetterABCMeta
    :exclude-members: __call__

.. autoclass:: melobot.typ.VoidType
    :members:

.. autoclass:: melobot.typ.AsyncCallable
    :exclude-members: __call__, __init__

.. autoclass:: melobot.typ.SyncOrAsyncCallable
    :exclude-members: __call__, __init__

.. data:: melobot.typ.T

    泛型 T，无约束

.. data:: melobot.typ.T_co

    泛型 T_co，协变无约束

.. data:: melobot.typ.P

   :obj:`~typing.ParamSpec` 泛型 P，无约束
