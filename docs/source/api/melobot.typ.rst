melobot.typ
===========

.. autoclass:: melobot.typ.HandleLevel
    :members:
    :exclude-members: __new__

.. autoclass:: melobot.typ.LogicMode
    :members:
    :exclude-members: calc, seq_calc

.. autofunction:: melobot.typ.is_type

.. autoclass:: melobot.typ.BetterABCMeta
    :members:

.. autoclass:: melobot.typ.BetterABC
    :members:

.. autofunction:: melobot.typ.abstractattr

.. autoclass:: melobot.typ.VoidType
    :members:

.. data:: melobot.typ.T

   泛型 T，无约束

.. data:: melobot.typ.P

   :obj:`~typing.ParamSpec` 泛型 P，无约束

.. data:: melobot.typ.AsyncCallable

   用法：AsyncCallable[P, T]
   
   是该类型的别名：Callable[P, Awaitable[T]]
