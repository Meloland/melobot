# 依赖注入与特性

## 基本形式与依赖项

对任意函数使用 {func}`.inject_deps` 装饰器，即可开启依赖注入功能。此时函数的参数中如果存在依赖项，则会在每次调用前进行满足。

首先，让我们使用最原始的依赖项对象 {class}`.Depends`，完成最原始的依赖注入功能：

```python
# 假设 get_val 是一个运行时才能被调用，用于获取特定值的函数
def get_val() -> str:
    ...

from melobot.di import inject_deps, Depends

@inject_deps
def func(s = Depends(get_val)) -> None:
    s: str
    # 在运行时，s 实际上就是 get_val 调用后的结果
    ...
```

也可以传递异步可调用对象，melobot 知道该怎么做：

```python
async def a_get_val() -> str:
    ...

@inject_deps
def func(s = Depends(a_get_val)) -> None:
    s: str
    # 在运行时，s 实际上就是 a_get_val 调用后的结果
    ...
```

```{admonition} 提示
:class: tip
为同时兼容同步和异步情景，任何函数被 {func}`.inject_deps` 装饰后都返回异步可调用对象。

因此调用时需要使用 `await`。
```

容易理解，实际上 {class}`.Depends` 包裹了可调用对象，并在 `func` 函数运行前自动调用 `get_val()` 以满足参数需求。

不过，更鼓励使用 [`Annotated`](https://docs.python.org/3/library/typing.html#typing.Annotated)，让依赖注入与类型注解完全兼容:

```python
...

from typing import Annotated

@inject_deps
def func(s: Annotated[str, Depends(get_val)]) -> None:
    ...
```

```{admonition} 提示
:class: tip
默认值风格的依赖注入写法，可以在 `lambda` 函数中进行使用。这也是这一写法存在的主要意义。
```

对于 `func` 这样经过 {func}`.inject_deps` 装饰后，需要依赖注入的函数，在运行前满足所有参数的过程，被称为一次“依赖满足”过程。而装饰这一操作，也被称为“依赖注入标记”或“标记为需要依赖注入”。

## 依赖项的特性

### 依赖项的缓存

```python
def get_val() -> int:
    return 42

@inject_deps
def f1(n: Annotated[int, Depends(get_val, cache=True)]) -> None:
    # 每次 f1 调用前都需要获取 n
    # 但是 get_val 仅被调用一次，此后将从缓存中获取
    ...
```

### 依赖项的递归

假设已有以下被依赖注入的函数：

```python
from typing import cast

@inject_deps
def f1(
    a: Annotated[float, Depends(lambda: 3.14)],
    b = Depends(lambda: 1),
) -> float:
    return a + cast(int, b)
```

但**如果 `f1` 实际上只会作为依赖项被另一函数 `f2` 使用，而不存在单独调用的情况**：

```python
@inject_deps
async def f2(val: Annotated[float, Depends(f1)]) -> None:
    print(val)
```

那么实际上，`f1` 甚至不需要被 {func}`.inject_deps` 装饰。因为 `f2` 中初始化 `Depends(f1)` 时默认启用了 `recursive=True`（递归机制）。这会自动对 `f1` 使用 {func}`.inject_deps`。这一特性被称为**依赖注入的自动递归**。

也可以通过设置 `recursive=False` 来关闭这一特性。

```python
def f1() -> float:
    return 3.14

@inject_deps
def f2(num: Annotated[float, Depends(f1, recursive=False)]) -> None:
    ...
```

### 依赖项的子获取器

某些情况下，需要**先获取对应的依赖，在此基础上再获取其他值**，此时可以使用子获取器：

```python
from typing import Annotated, cast, TypedDict

class NumPair(TypedDict):
    a: float
    b: float

def f1(
    a: Annotated[float, Depends(lambda: 3.14)],
    b = Depends(lambda: 1),
) -> NumPair:
    return {"a": a, "b": float(cast(int, b))}
```

我们在 `f2` 中，仅需要 `f1` 返回结果中的一部分：

```python
@inject_deps
async def f2(
    num_b: Annotated[float, Depends(f1, sub_getter=lambda dic: dic["b"])]
) -> None:
    ...
```

### 基于依赖项的依赖

一个被 {func}`.inject_deps` 标记了需要依赖注入的函数，在一次依赖满足过程中，可以让后满足的依赖项，依赖于先满足的依赖项：

```python
_d1 = Depends(lambda: 3.14)

def get_var() -> int:
    return 42

@inject_deps
def test(
    # 依赖项可以在外部初始化
    a: Annotated[float, _d1],
    # 此参数的依赖项，依赖于 _d1，随后通过子获取器获得整型值
    b: Annotated[int, Depends(_d1, sub_getter=lambda x: int(x))],
    # 此参数的依赖项同时赋值给 _d2 变量
    c = (_d2 := Depends(get_var)),
    # 此参数的依赖项，依赖于 _d2，随后通过子获取器获得字符串
    d = Depends(_d2, sub_getter=lambda x: str(x)),
) -> None:
    # 输出："a: 3.14, b: 3, c: 42, d: 42"
    print(f"a: {a}, b: {b}, c: {c}, d: {d}")
```

```{admonition} 提示
:class: tip
1. melobot 对于参数的依赖注入顺序是**从左至右**，因此 b 依赖于 a，d 依赖于 c，在逻辑上是可行的。

2. a、b 参数的写法是兼容类型注解的写法，而 c、d 参数的写法是默认值的写法，可根据实际情况选用，一般更推荐兼容类型注解的写法。

3. 例子中的 `_d1` 和 `_d2` 都是全局作用域的变量，请特别注意
```

### 依赖注入与手动传参

一般来说，标记了需要依赖注入的函数**不能手动传参**。

```python
# 错误的用法
@inject_deps
def func(a: int) -> None:
    ...
# 即使 a 没有关联到任何依赖项，也不能手动传参
```

但通过以下方法可允许手动传参：

```python
inject_allow_manual = lambda f: inject_deps(f, manual_arg=True)

@inject_allow_manual
def func(a: int, b: Annotated[int, Depends(lambda: 42)]) -> None:
    ...

# 使用时可以传参 a
await func(1)
# 或
await func(a=1)
```

但位置参数和关键字参数，任何情况下都无法进行依赖注入，也就始终允许手动提供：

```python
@inject_deps
def func(..., *args: str, ..., **kwargs: int) -> None:
    args: tuple[str]
    kwargs: dict[str, int]

# 使用时
await func(..., "1", "2", ..., a=3, b=4)
```

## 自动依赖项

对于一些常见的依赖，melobot 提供了更简洁的写法。例如对于以下很典型的情景：

```python
from melobot.bot import get_bot, Bot
from melobot.handle import get_event

from melobot.di import Depends, inject_deps
from melobot.protocols.onebot.v11 import Adapter, MessageEvent
from typing import Annotated

@inject_deps
def process_node(
    bot: Annotated[Bot, Depends(get_bot)],
    adapter: Annotated[Adapter, Depends(lambda: get_bot().get_adapter(Adapter))],
    event: Annotated[MessageEvent, Depends(get_event)]
) -> None:
    ...
```

很显然诸如 `bot`, `adapter`, `event` 等都是非常常用的，使用基本的依赖注入虽然省去了在函数体内调用 {func}`.get_bot`，{func}`.get_event` 等方法，但实际上还更加繁琐了。

为此，melobot 对于常用的依赖，会创建自动依赖项，此时只需要提供类型注解即可：

```python
@inject_deps
def process_node(bot: Bot, adapter: Adapter, event: MessageEvent) -> None:
    ...
```

这便是最常见的依赖注入使用方式。所有自动依赖项均**只依靠类型注解完成依赖满足**：如果当前上下文中存在对应类型的依赖值，则可满足。所以参数位置和名称完全不重要。

所有支持自动依赖的类型注解如下所示：

| 类型注解 | 对应的依赖值 |
| --- | --- |
| {class}`~.melobot.adapter.model.Event` | 当前事件 |
| {class}`.Bot` | 当前 bot 实例 |
| {class}`~.melobot.adapter.base.Adapter` | 当前 bot 实例的对应类型的适配器 |
| {class}`~.melobot.log.base.Logger` | 当前 bot 的日志器 |
| {class}`.FlowStore` | 当前处理流的流存储 |
| {external:class}`.tuple`\[{class}`.FlowRecord`, ...\] | 当前处理流的流记录 |
| {class}`.Session` | 当前会话的会话对象 |
| {class}`.SessionStore` | 当前会话的会话存储 |
| {class}`.Rule` | 当前会话的会话规则 |
| {class}`.AbstractParseArgs` | 当前解析参数 |

注：可以提供这些类型的子类型。

当使用自动依赖时，如果同时启用了允许手动传参的功能，那么会根据手动传参的情况，调整自动依赖的满足：

```python
inject_allow_manual = lambda f: inject_deps(f, manual_arg=True)

@inject_allow_manual
def f(bot: Bot, adapter: Adapter, event: MessageEvent) -> None:
    ...

new_bot = Bot(...)
await f(new_bot)
# 或
await f(bot=new_bot)
```

此时 `bot` 形参的值仅来源于手动提供的实参。

## 其他组件中的依赖注入

在 melobot 中，使用流装饰器会自动进行依赖注入：

```python
from melobot.handle import on_text

@on_text(...)
async def f() -> None: ...
# on_text 内部对函数进行了依赖注入标记，因此可以使用自动依赖
```

使用 {func}`.node` 装饰器也会自动进行依赖注入：

```python
from melobot.handle import node

@node
async def f1() -> None: ...
@node(...)
async def f2() -> None: ...
# node 内部对函数进行了依赖注入标记，因此可以使用自动依赖
```

但使用 {class}`.FlowNode` 时，可以通过初始化参数 `no_deps` 调整是否需要依赖注入。而 {class}`.Flow` 内部，实际上不进行依赖注入标记操作。

值得注意的是，流装饰器和 {func}`.node` 装饰器，本质上是通过设置 {class}`.FlowNode` 的 `no_deps=False` 进行依赖注入。因此**处理流结点拥有隐式的依赖注入**。

常规的依赖注入在依赖不匹配时，将会发出异常并传播到外部。但处理流在运行时进行了额外处理，当处理流结点发生依赖不匹配时，仅会影响处理流结点的遍历。

```{admonition} 提示
:class: tip
除处理流结点外，此前提过的**生命周期钩子的相关装饰器**，以及未来会提到的**插件共享对象的某些方法**，也存在隐式的依赖注入。所以这些地方也可以**使用自动依赖，或直接提供依赖项**。
```

(di_with_multiple_deco)=
## 依赖注入与多层装饰

melobot 的依赖注入可以穿透多层装饰并正常工作：

```python
@inject_deps
@a(...)
@b(...)
async def func(...) -> None: ...
```

但是需要满足以下条件：

1. {func}`.inject_deps` 以下，`func` 以上的所有装饰器（以下简称夹层装饰器），必须使用 `functools.wraps` 包装。否则将丢失 `func` 的注解信息，无法进行注入。
2. 夹层装饰器，不能修改 `func` 的参数性质（参数类型、个数、位置或名称）
3. `func` 所有依赖，要在夹层装饰运行前就可被满足。因为 {func}`.inject_deps` 尝试满足依赖时，夹层装饰还尚未运行。

因此，如果可以，更建议将 {func}`.inject_deps` 始终置于函数装饰的最内层。此时无需考虑以上限制：

```python
@a(...)
@b(...)
@inject_deps
async def func(...) -> None: ...
```

但是对于流装饰器和 {func}`.node` 装饰器，{func}`.inject_deps` 将不得不置于装饰的最外层：

```python
@on_text(...)
@a(...)
@b(...)
async def f1(...) -> None: ...

@node
@a(...)
@b(...)
async def f1(...) -> None: ...
```

如果满足以上限制条件，则无需做任何调整。若违反了任何一条规则，请在需要的依赖注入时机对应的装饰层，放置 {func}`.inject_deps`。

```python
@on_text(...)
@a(...)
@inject_deps
@b(...)
async def f1(...) -> None: ...

# 或：

@node
@a(...)
@b(...)
@inject_deps
async def f1(...) -> None: ...
```

流装饰器和 {func}`.node` 装饰器，识别到装饰链上已经存在依赖注入时，会自动放弃内部的依赖注入。

例如以下典型例子：

```python
from melobot.handle import stop
from melobot.utils import if_, unfold_ctx

# 创建一个消息事件的处理流
@on_message(checker=OWNER_CHECKER)
# 当解析器解析成功时，继续运行，否则停止处理流
@if_(lambda: PARSER.parse(get_event().text), reject=stop)
# 随即展开一个会话
@unfold_ctx(lambda: enter_session(rule))
# 下面的参数需要会话，但会话在 unfold_ctx 前不存在，所以要调整依赖注入的时机
@inject_deps
async def session_test(session: Session, store: SessionStore) -> None:
    ...
```

## 其他

其他依赖注入相关接口（例如附加元数据），请参考 [API 文档](../api/melobot.di)。

## 总结

本篇主要说明了 melobot 的依赖注入机制与特性。

下一篇将重点说明：会话控制。
