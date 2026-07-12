# 类型工具

`melobot.typ` 提供了框架公开接口中反复出现的泛型、可调用对象协议、运行时类型工具、抽象基类和枚举。它们的主要目标是让类型注解、依赖注入和运行时校验使用同一套表达方式；多数情况下只在编写扩展组件或较通用的工具代码时需要直接使用。

## 通用泛型与可调用对象

{data}`.T`、{data}`.U`、{data}`.V` 是无约束的类型变量，{data}`.T_co` 是协变的无约束类型变量，{data}`.P` 是无约束的 `ParamSpec`。它们都以 `Any` 为默认值，方便在未显式提供泛型参数的公开接口中保持兼容。

```python
from melobot.typ import AsyncCallable, P, T

def trace(func: AsyncCallable[P, T]) -> AsyncCallable[P, T]:
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        print(f"calling {func}")
        return await func(*args, **kwargs)
    return wrapped
```

这里 `P` 保留被包装函数的位置参数和关键字参数，`T` 保留协程的返回值类型。对“同步或异步均可”的回调，则使用 {class}`.SyncOrAsyncCallable`：

| 类型 | 等价含义 |
| --- | --- |
| {class}`.AsyncCallable`\[`P`, `T`] | `Callable[P, Awaitable[T]]` |
| {class}`.SyncOrAsyncCallable`\[`P`, `T`] | `Callable[P, T \| Awaitable[T]]` |

这两个是 `Protocol`，仅描述可调用对象的形状，并不负责把同步函数转换成协程。需要实际转换时，使用[实用组件](./utils)中的 {func}`~melobot.utils.to_async` 或 {func}`~melobot.utils.to_coro`。

## 运行时类型校验

Python 的 `isinstance` 只能处理运行时类，不能直接检查 `list[str]`、联合类型或更复杂的类型提示。{func}`.is_type` 接收一个对象和任意类型提示，并按类型提示进行运行时校验：

```python
from melobot.typ import is_type

assert is_type(["a", "b"], list[str])
assert not is_type(1, str)
assert is_type("hello", str | bytes)
```

返回值带有 `TypeIs` 注解，因此静态类型检查器可以在判断通过的分支中收窄对象类型。它适合处理外部输入、插件扩展点或依赖注入内部的兼容性判断；对于已知的普通类继承关系，`isinstance` 通常更简单也更快。运行时泛型校验并不等价于逐项、完整的数据验证，尤其不应只凭一次容器类型判断就信任不受控的嵌套输入；需要严格验证时请使用 Pydantic 等专用校验工具。

{func}`.is_subhint` 则比较**两个类型提示**之间的包含关系：

```python
from melobot.typ import is_subhint

assert is_subhint(int, int | str)
assert not is_subhint(str, int)
```

它回答的是“前者能否作为后者的子类型”，并不检查任何具体对象。泛型可变性、`Any`、类型变量和第三方注解都会影响结果；将它用于接口兼容判断时，应针对自己的类型提示编写测试，而不要把它当成字符串比较工具。

## 抽象基类与单例元类

{class}`.BetterABC` 与 {class}`.BetterABCMeta` 兼容标准库抽象类机制，并额外支持 {func}`.abstractattr`。抽象属性不限制子类用类属性、实例属性还是 `property` 实现：

```python
from melobot.typ import BetterABC, abstractattr

class Storage(BetterABC):
    name: str = abstractattr()

class MemoryStorage(Storage):
    name = "memory"

class FileStorage(Storage):
    def __init__(self, path: str) -> None:
        self.name = path
```

如果子类实例化后仍缺少声明为抽象属性的字段，`BetterABC` 会拒绝实例化。它特别适合“实现形式可以不同，但最终必须提供某个数据属性”的扩展接口。

{class}`.SingletonMeta` 会让同一类的所有构造调用返回同一个实例；{class}`.SingletonBetterABCMeta` 则将单例语义与 `BetterABCMeta` 结合。它们适合框架级上下文管理器、进程内注册表等确实应只有一份状态的对象：

```python
from melobot.typ import SingletonMeta

class Registry(metaclass=SingletonMeta):
    pass

assert Registry() is Registry()
```

单例只在当前 Python 进程内成立，不会解决多线程同步、多进程共享或测试间状态污染。业务对象默认应显式传递依赖，而不是为了方便随意设计成单例。

## 常用枚举与颜色

| 类型 | 作用 |
| --- | --- |
| {class}`.LogLevel` | 与标准库 `logging` 数值兼容的 `DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL` |
| {class}`.LogicMode` | `AND`、`OR`、`NOT`、`XOR`；检查器和匹配器组合时使用 |
| {class}`.Color` | 用于表示常用色、十六进制色或 RGB 色的值对象 |

`Color` 的常用色以类属性提供，其他颜色可通过十六进制或 RGB 创建：

```python
from melobot.typ import Color

warning = Color.yellow
brand = Color("#7c3aed")
sky = Color(56, 189, 248)

assert brand.hex == "#7c3aed"
hue, saturation, lightness = sky.hsl
```

常用色没有唯一的 RGB、十六进制或 HSL 值，因此读取这些属性会抛出 `AttributeError`。大多数业务代码无需直接使用 `Color`；它主要服务于可组合的检查/匹配规则和渲染扩展。

## 总结

类型工具的重点不是为每段业务代码增加泛型，而是在编写可复用接口时准确表达“参数如何传递、返回值是否可等待、值是否满足某个类型提示”。运行时输入校验使用 `is_type`，接口提示兼容性判断使用 `is_subhint`；需要定义扩展基类或进程内协调器时，再考虑 `BetterABC` 与单例元类。

下一篇将介绍：[导入与惰性加载](./import_lazy)。
