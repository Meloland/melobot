from enum import Enum

from typing_extensions import Any, Callable, Sequence

from .base import AsyncCallable


class VoidType(Enum):
    """空类型，需要区别于 `None` 时使用

    .. code:: python

        # 有些时候 `None` 也是合法值，因此需要一个额外的哨兵值：
        def foo(val: Any | VoidType = VoidType.VOID) -> None:
            ...
    """

    VOID = type("_VOID", (), {})


class LogicMode(Enum):
    """逻辑模式枚举类型"""

    AND = 1
    OR = 2
    NOT = 3
    XOR = 4

    @classmethod
    def calc(cls, logic: "LogicMode", v1: Any, v2: Any = None) -> bool:
        """将两个值使用指定逻辑模式运算

        :param logic: 逻辑模式
        :param v1: 值 1
        :param v2: 值 2
        :return: 布尔值
        """
        if logic == LogicMode.AND:
            return (v1 and v2) if v2 is not None else bool(v1)  # type: ignore[no-any-return]
        if logic == LogicMode.OR:
            return (v1 or v2) if v2 is not None else bool(v1)  # type: ignore[no-any-return]
        if logic == LogicMode.NOT:
            return not v1
        return (v1 ^ v2) if v2 is not None else bool(v1)  # type: ignore[no-any-return]

    @classmethod
    def short_calc(
        cls, logic: "LogicMode", v1: Callable[[], Any], v2: Callable[[], Any] | None
    ) -> bool:
        """与 :func:`calc` 功能类似，但运算支持短路

        :param logic: 逻辑模式
        :param v1: 生成值 1 的可调用对象
        :param v2: 生成值 2 的可调用对象
        :return: 布尔值
        """
        if logic == LogicMode.AND:
            return (v1() and v2()) if v2 is not None else bool(v1())  # type: ignore[no-any-return]
        if logic == LogicMode.OR:
            return (v1() or v2()) if v2 is not None else bool(v1())  # type: ignore[no-any-return]
        if logic == LogicMode.NOT:
            return not v1()
        return (v1() ^ v2()) if v2 is not None else bool(v1())  # type: ignore[no-any-return]

    @classmethod
    async def async_short_calc(
        cls,
        logic: "LogicMode",
        v1: AsyncCallable[[], Any],
        v2: AsyncCallable[[], Any] | None,
    ) -> bool:
        """与 :func:`short_calc` 功能类似，但运算支持异步

        :param logic: 逻辑模式
        :param v1: 生成值 1 的异步可调用对象
        :param v2: 生成值 2 的异步可调用对象
        :return: 布尔值
        """
        if logic == LogicMode.AND:
            res = (await v1() and await v2()) if v2 is not None else bool(await v1())
            return res  # type: ignore[no-any-return]
        if logic == LogicMode.OR:
            res = (await v1() or await v2()) if v2 is not None else bool(await v1())
            return res  # type: ignore[no-any-return]
        if logic == LogicMode.NOT:
            return not await v1()
        res = (await v1() ^ await v2()) if v2 is not None else bool(await v1())
        return res  # type: ignore[no-any-return]

    @classmethod
    def seq_calc(cls, logic: "LogicMode", values: list[Any]) -> bool:
        """使用指定的逻辑模式，对值序列进行运算

        .. code:: python

            # 操作等价与：True and False and True
            LogicMode.seq_calc(LogicMode.AND, [True, False, True])

        :param logic: 逻辑模式
        :param values: 值序列
        :return: 布尔值
        """
        if len(values) <= 0:
            return False
        if len(values) <= 1:
            return bool(values[0])

        idx = 0
        res: bool
        while idx < len(values):
            if idx == 0:
                res = cls.calc(logic, values[idx], values[idx + 1])
                idx += 1
            else:
                res = cls.calc(logic, res, values[idx])
            idx += 1
        return res

    @classmethod
    def short_seq_calc(
        cls, logic: "LogicMode", getters: Sequence[Callable[[], Any]]
    ) -> bool:
        """与 :func:`seq_calc` 功能类似，但运算支持短路

        :param logic: 逻辑模式
        :param getters: 一组获取值的可调用对象
        :return: 布尔值
        """
        if len(getters) <= 0:
            return False
        if len(getters) <= 1:
            return bool(getters[0]())

        idx = 0
        res: bool
        while idx < len(getters):
            if idx == 0:
                res = cls.short_calc(logic, getters[idx], getters[idx + 1])
                idx += 1
            else:
                res = cls.short_calc(logic, lambda: res, getters[idx])
            idx += 1
        return res

    @classmethod
    async def async_short_seq_calc(
        cls, logic: "LogicMode", getters: Sequence[AsyncCallable[[], Any]]
    ) -> bool:
        """与 :func:`short_seq_calc` 功能类似，但运算支持异步

        :param logic: 逻辑模式
        :param getters: 一组获取值的异步可调用对象
        :return: 布尔值
        """
        if len(getters) <= 0:
            return False
        if len(getters) <= 1:
            return bool(await getters[0]())

        idx = 0
        res: bool
        while idx < len(getters):
            if idx == 0:
                res = await cls.async_short_calc(logic, getters[idx], getters[idx + 1])
                idx += 1
            else:

                async def res_getter() -> bool:
                    return res

                res = await cls.async_short_calc(logic, res_getter, getters[idx])
            idx += 1
        return res
