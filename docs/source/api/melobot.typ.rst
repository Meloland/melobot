:tocdepth: 2

melobot.typ
===========

.. autoclass:: melobot.typ.HandleLevel
    :members:
    :exclude-members: __new__

.. autoclass:: melobot.typ.LogicMode
    :members:

.. autofunction:: melobot.typ.is_type

.. autofunction:: melobot.typ.abstractattr

.. autoclass:: melobot.typ.BetterABCMeta
    :members:
    :exclude-members: __call__, DummyAttribute

.. autoclass:: melobot.typ.BetterABC
    :members:

.. autoclass:: melobot.typ.SingletonMeta
    :exclude-members: __call__

.. autoclass:: melobot.typ.SingletonBetterABCMeta
    :exclude-members: __call__

.. autoclass:: melobot.typ.Markable
    :members:
    :exclude-members: __init__

.. autoclass:: melobot.typ.VoidType
    :members:

.. data:: melobot.typ.T

    泛型 T，无约束

.. data:: melobot.typ.T_co

    泛型 T_co，协变无约束

.. data:: melobot.typ.P

   :obj:`~typing.ParamSpec` 泛型 P，无约束

.. autoclass:: melobot.typ.AsyncCallable
    :exclude-members: __call__, __init__
