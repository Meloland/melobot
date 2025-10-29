# 事件处理流与机制

## 处理过程与处理上下文

目前我们编写的所有 bot 功能，都通过事件绑定函数完成。事件绑定函数实际上将其他函数进行装饰，并最终返回一个处理流对象。更严谨地说，**“事件绑定函数”实际上是处理流装饰器，用于从一个函数生成处理流**。

处理流对象会被传递给插件管理器（{class}`.PluginPlanner`），随后插件管理器被 bot 加载并创建插件，由此事件处理逻辑被包裹在处理流中传递给 bot。

在 bot 加载各种协议支持后，它们会创建各种各样的事件。melobot 做的只是把所有事件广播给 bot 所有处理流对象。

```{admonition} 提示
:class: tip
**这不意味着每个处理流会处理每个事件**。相反，它通过一些机制实现了“选择性”。
```

处理流对象内部包含以下部分：

- 守卫函数
- 由处理流结点组成的 DAG（有向无环图）

事件处理流每次运行时前会生成**事件处理上下文**，并随后在此上下文中运行。上下文包含了当前事件、当前事件来源的输入源、适配器等一系列信息。

之后，处理流会首先运行守卫函数，检查事件是否能触发处理过程。若为否，则不运行任何操作。若为真，则开始对 DAG 进行遍历，每遍历到一个结点，就尝试运行这个处理流结点。

```{admonition} 提示
:class: tip
处理流是可以并发执行的。例如 melobot 先后创建事件 A 和事件 B，且都触发了处理流 f1，假设事件 A 对应的事件处理上下文为 a，同理事件 B 对应上下文 b。首先执行上下文 a 下的 f1。但执行时如果因为 await 发生了异步切换，完全可以开始运行上下文 b 下的 f1。

所以**需要注意竞争资源的并发安全性**。[会话控制](./session_control) 一章会讨论相关解决方案。
```

## 处理流结点

**处理流结点是运行事件处理的基本单元**。使用处理流装饰器，可以快速地生成只包含一个结点的处理流，对应只有一个结点的 DAG，这是最简单的情景。

创建更精细的处理流程，需要自行定义结点和流。通过 {class}`.FlowNode` 创建一个处理流结点：

```python
from melobot.handle import FlowNode

# 假设对于某个事件的处理，在某一阶段有一些操作：
# 同步、异步函数均可
async def step1() -> None:
    ...

# 随后手动实例化一个结点，结点默认命名为函数名
node1 = FlowNode(step1)

# 也可以自行命名
node1 = FlowNode(step1, name="important first step")
```

也可以通过 {func}`.node` 装饰器便捷的生成一个结点：

```python
from melobot.handle import node

# 同步、异步函数均可
@node
def node2() -> None:
    ...

# 此后 node2 已经是一个处理流结点，结点自动命名为函数名
```

别忘了我们熟悉的依赖注入，它依然适用：

```python
from melobot.handle import node
from melobot.adapter import TextEvent

@node
async def node3(e: TextEvent) -> None:
    # 依赖注入 melobot 基类事件
    ...

from melobot.protocols.onebot.v11 import MessageEvent
from melboot.protocols.console import StdinEvent

@node
async def node4(e: MessageEvent | StdinEvent) -> None:
    # 想要不同协议的多种事件？当然也是支持的
    ...
```

还记得过去说过的**依赖注入的区分调用小特性**吗？这一特性实际上就是：尝试运行此结点时，如果上下文与依赖注入的某一项不匹配，那么该结点就会被跳过，DAG 上此结点的后继结点也就不再遍历。

想象一个不需要 isinstance 和 if-else 来筛选各种上下文信息的世界，这简直太棒了 :)

在某些情况下，也可以使用更底层的 {func}`.get_event` 获取事件，但缺乏精确的类型注解：

```python
from melobot.adapter import Event
from melobot.handle import get_event

@node
async def test_node() -> None:
    e: Event = get_event()
```

实际返回的事件类型取决于多种因素。例如此结点前置结点、此结点的依赖注入等都会影响获取到的事件类型。

## 处理流

通过一个例子来了解处理流的创建和工作方式。

假设现在已经存在 `n1` 到 `n7` 七个结点。我们希望它们组成以下的 DAG 结构，以便实现特定的处理逻辑：

```{image} /_static/eg-flow-graph.svg
:alt: eg-flow-graph
:width: 400px
:align: center
```

如图所示，红色结点为 DAG 可能的遍历起始点，红色结点为 DAG 遍历终止点。

melobot 对于处理流 DAG 的遍历规则如下：

1. 获取 DAG 所有起始点
2. 选择一个起始点，开始进行深度优先遍历（DFS）
3. DFS 遍历到的处理结点，先进行上下文和依赖注入的匹配，匹配成功则开始执行
4. 完成一次 DFS 后，取下一起始点循环第 2-3 步，直至所有起始点都被使用

图中例子，将会形成如下遍历路径：

```text
n1 -> n3 -> n4 -> n5 -> n7
n1 -> n3 -> n4 -> n6 -> n7
n2 -> n3 -> n4 -> n5 -> n7
n2 -> n3 -> n4 -> n6 -> n7
```

可以发现一些结点被遍历了多次，这意味着结点的处理逻辑，**在一次事件处理过程中可以被执行多次**，这是刻意的设计。

如果你想要每个结点只遍历一次，非常简单：让每个分叉点的后继结点的依赖注入互斥即可。例如对于 n5 和 n6 结点，在进行依赖注入时，让同一上下文无法同时满足两结点的依赖注入条目即可。

在理解处理流的结构和逻辑之后，使用 {class}`.Flow` 可以创建对应的处理流：

```python
from melobot.handle import Flow

# 假设 n1-n7 变量已经存在，并为对应的处理结点
n1, ..., n7 = nodes_list

flow = Flow(
    # 流的名称（位置参数）
    "test-flow",
    # 接下来的可变位置参数，提供 DAG 的路径结构
    [n1, n3, n4, n5, n7],
    [n2, n3, n4],
    [n4, n6, n7]
)
```

DAG 的路径结构参数，第一眼看起来比较迷惑。但格式其实非常简单：想象一个较为复杂的 DAG，如果把每条边作为参数传递，是非常繁琐的。这里允许直接传递 DAG 的路径（可迭代对象，如列表、元组等）。

只要路径包含了 DAG 中的所有边，内部就可以构建出完整的图结构。

上面的参数写法，提供了如下三条路径：

```text
n1 -> n3 -> n4 -> n5 -> n7
n2 -> n3 -> n4
n4 -> n6 -> n7
```

显然包含了图中所有的边。此外，如果存在例如 n4 分叉到 n5, n6；而后 n5, n6 又合并到 n7 这种结构，还能简写：

```python
flow = Flow(
    "test-flow",
    [n1, n3, n4, [n5, n6], n7],
    [n2, n3]
)
```

对于路径结构 `[..., n4, [n5, n6], n7, ...]`，内部会自动展开：`n4 -> n5 -> n7`，`n4 -> n6 -> n7`。

但其实还可以简化，聪明的你也许已经想到了：

```python
flow = Flow(
    "test-flow",
    [[n1, n2], n3, n4, [n5, n6], n7]
)
```

当处理流中存在孤立点时（显然此时必为起始点），这样提供参数：

```python
@node
async def alone_node(...):
    ...

flow = Flow("test-flow", ..., [alone_node], ...)
```

```{admonition} 提示
:class: tip

1. 在初始化流结点和处理流时，建议提供有意义的名称，这很有助于调试
2. 处理流的图结构如果存在环路，melobot 将会发出异常（首次运行前，或 DAG 结构变更时执行校验）
3. melobot 允许将结点提供给多个处理流对象共用，因为每个流在每次运行时都有独立的上下文。
```

## 流的组合式 API

上面展示了一般的处理流配置方式。但考虑较为复杂的情景：将处理结点分别组织在多个模块中，创建处理流的模块，将不得不导入所有处理结点所在的模块。

考虑在 [插件系统的使用](../intro/use-plugin) 中提到的 {meth}`~.PluginPlanner.use` 装饰器实现的“控制反转”，对于处理流的构建，同样有类似的“组合式” API。

首先在 `__plugin__.py` 内声明一个处理流，但不包含具体的结点定义。

```python
from melobot import PluginPlanner
from melobot.handle import Flow

# 使用 auto_import=True 将自动导入插件目录下所有可加载模块
TEST_PLUGIN = PluginPlanner(version="1.0.0", auto_import=True)
# 先创建一个无结点的空流
test_flow = Flow("test-flow")
TEST_PLUGIN.use(test_flow)
```

随后在插件根目录创建一个子目录 `flows`，在 `flows/test-flows.py` 中：

（目录和文件的命名、位置没有规定，因为现在启用了 `auto_import`）

```python
from melobot.handle import node
from __plugin__ import test_flow as f

# 在流中添加一个孤立结点
@f.add
@node
async def n1() -> None:
    ...

"""沿处理流的流动方向添加结点"""
# 添加 n1 结点的后继结点，这创建了边 n1 -> n2：
@f.after(n1)
@node
async def n2() -> None:
    ...
# 添加一结点作为多个结点的后继，这创建了边 n1 -> n3, n2 -> n3
@f.merge(n1, n2)
@node
async def n3() -> None:
    ...

"""沿流动方向的反方向添加结点"""
# 添加 n1 结点的前驱结点，这创建了边 n_pre1 -> n1：
@f.before(n1)
@node
async def n_pre1() -> None:
    ...
# 添加一结点作为多个结点的前驱结点，这创建了边 n_pre2 -> n_pre1, n_pre2 -> n1
@f.fork(n_pre1, n1)
@node
async def n_pre2() -> None:
    ...
```

此外，这些组合式 API 装饰器都是可以堆叠的：

```python
from melobot.handle import node
from __plugin__ import test_flow as f

# 假设你先这样定义 n_pre2, n_pre1, n2, n3：
@f.add
@node
async def n_pre2() -> None:
    ...

@f.after(n_pre2)
@node
async def n_pre1() -> None:
    ...

@f.add
@node
async def n2() -> None:
    ...

@f.after(n2)
@node
async def n3() -> None:
    ...

# 一次性定义四条边：
# n_pre2 -> n1, n_pre1 -> n1, n1 -> n2, n1 -> n3
@f.fork(n2, n3)
@f.merge(n_pre2, n_pre1)
@node
async def n1() -> None:
    ...
```

由于 Python 装饰器的装饰顺序是“由内而外”，所以添加边的顺序与注释 `n_pre2 -> n1`, `n_pre1 -> n1`, `n1 -> n2`, `n1 -> n3` 完全一致。

```{admonition} 相关知识
:class: note
组合式 API 对于插件扩展更为友好，这在未来的 [插件机制与管理](./plugin_usage) 将会继续讨论。

例如：插件可以公开自己内部的一些处理流，外部使用组合式 API 进行扩展（处理流插槽）。
```

## 流的守卫函数

使用 {meth}`~.Flow.set_guard` 设置或重设处理流的守卫函数。

```python
from melobot.adapter import Event
from melobot.handle import Flow

f = Flow(...)

# 同步或异步函数均可，但不支持依赖注入
@f.set_guard
async def i_m_guard(event: Event) -> bool | None:
    # 返回 None 或 False 代表不通过“守卫检验”
    ...
```

守卫函数的唯一参数（第一参数）为事件对象。传入的事件类型可能是 melobot 基事件类型的任意子类型，建议注解为基类型时刻提醒自己。

```{admonition} 提示
:class: tip

这一方法对于功能开发者相对不常用，对于协议支持开发者，部分情景较为有用。

主要用于加快高层 API 内部热点逻辑执行速度，让流在最早阶段丢弃掉不需要处理的事件。
```

## 流的优先级

初始化流对象时，可以提供优先级参数：

```python
from melobot.handle import Flow

# 优先级值（越高越优先）
lvl = 5
# 默认优先级为 0，此时为 5
f = Flow(..., priority=lvl)
```

一个 bot 实例上可以绑定多个处理流，bot 总是先向优先级更高的处理流广播事件。同级的处理流处理完成后，事件才会向更低优先级的处理流传播。

高级别的处理流可以决定事件是否可以向低级别传播。使用 {meth}`~.Flow.update_priority` 可以更新优先级。

```python
from melobot.handle import on_start_match

# 在任何时候，你都可以重设处理流的优先级
# 甚至处理流运行时也可以
@on_start_match(...)
async def flow1() -> None:
    # 从 0 提升到 10
    flow1.update_priority(10)
```

处理流优先级更新方法是“尽快完成”的，一般是下一次运行时生效。

## 流的控制方法

将事件处理过程组织为结点和流的形式，一个好处是便于管理和维护。另一个重要的好处是可以使用相应的**控制方法**。

### 后继结点方法

一般来说，处理结点对应的函数返回 `None` 或 `True` 后，才会运行后继结点的遍历。返回 `False` 时，将不会运行后继结点的遍历。

```python
@node
async def node_x() -> bool | None:
    if condition:
        # 后继结点继续正常遍历
        return
    elif condition2:
        # 后继结点继续正常遍历
        return True
    else:
        # 后继结点不再进行遍历
        return False
```

考虑需要展开自定义上下文环境，再运行后继结点的情况。在当前流的调用链上（流结点内，流结点调用的其他函数内），使用 {func}`.nextn` 控制后继结点的运行时机：

```python
from melobot.handle import nextn

@node
async def node_x() -> None:
    ...
    with some_context:
        # 告诉 melobot 运行到此处时，可以开始遍历后继结点
        await nextn()
        # 后继所有结点遍历、运行完成后，再返回到这里
    # 这样就可以方便地运行一些清理，或其他收尾工作
    ...
```

```{admonition} 提示
:class: tip

1. 结点对应的函数内，可以多次调用 {func}`.nextn`。但只有第一次会触发后继结点的遍历、运行，后续调用都是**直接返回**。
2. 结点对应的函数返回时，若至少调用了一次 {func}`.nextn`，返回值不再能决定是否遍历后继结点。因为后继结点已经遍历。
```

### 传播阻断方法

假设现有优先级为 0 的处理流 `A`, `B`, `C`。melobot 会尝试并发地让它们处理产生的事件。

处理流默认不会阻断事件向更低优先级传播，但**同优先级的处理流中，若有一个处理流决定阻断事件传播，则事件无法向更低优先级传播**。同优先级的流不受影响，因为它们的处理流程已经被启动。

在当前流的调用链上，使用 {func}`.block` 函数阻断当前事件向更低优先级传播：

```python
from melobot.handle import block

@node
async def node_x() -> None:
    ...
    # 运行到此处时，标记当前事件不应向更低优先级级传播
    await block()
    ...
```

### 立即终止方法

使用 {func}`.stop` 在当前流的调用链上，立即终止当前结点、后续所有结点的遍历和运行过程。

```python
from melobot.handle import stop

@node
async def node_x() -> None:
    ...
    if condition:
        # 运行到此处时，立即退出整个处理流
        # DAG 无论遍历到何处，都将被终止
        # 比较有用的是：多层函数嵌套下，可以方便退出而不是逐级 return
        await stop()
    ...
```

### 结点跳过方法

使用 {func}`.bypass` 在当前流的调用链上，立即跳过当前结点剩余步骤，运行下一处理结点：

```python
from melobot.handle import bypass

@node
async def node_x() -> None:
    ...
    if condition:
        # 运行到此处时，立即退出当前节点执行，继续遍历下一结点
        await bypass()
    ...

@node
async def node_y() -> None:
    ...
    if condition:
        sub_func()
    ...

def sub_func() -> None:
    ...
    # 实现多层退出，即便有多层函数调用
    await bypass()
    ...
```

### 结点重入方法

使用 {func}`.rewind` 在当前流的调用链上，立即跳过当前结点剩余步骤，重新运行当前结点：

```python
from melobot.handle import rewind

@node
async def node_x() -> None:
    ...
    if condition:
        # 运行到此处时，重新回到结点起始位置，后续一般与会话搭配使用
        # 这不会影响 DAG 遍历规则，因为内部并不认为 rewind 导致结点“结束遍历”
        await rewind()
    ...
```

### 进入子流方法

使用 {func}`.flow_to` 在当前流的调用链上，进入一个子流的调用：

```python
from melobot.handle import flow_to

f1 = Flow(...)
f2 = Flow(...)

# 假设此结点现在只包含在 f1 中：
@node
async def eg_node() -> None:
    ...
    # 调用（或者说进入）一个子流 f2，陷入异步等待
    # f2 运行时直接复制此时的上下文
    await flow_to(f2)
```

```{admonition} 提示
:class: tip

1. 外部流 f1 会暂时停止结点运行和遍历，等待子流运行完成、使用控制方法退出或发生异常
2. 子流 f2 内调用任何控制方法，不会影响外部流 f1 的运行。除非发生异常，此时会传播到 f1 中
3. 子流内依然可以继续调用子流
```

“进入子流方法”同样很适合用于扩展处理流，简单理解就是组合流为更大的流。

## 流的状态和反射

刚才提到，每个处理流在每次运行时都有独立的上下文。因此处理流间、不同事件触发的同一处理流都可以并发的运行。

除已有的上下文信息外，处理结点可能需要向后续结点传递其他信息。melobot 提供了流运行期的存储结构 {class}`.FlowStore`（流存储对象，字典子类），它在流一次运行期内有效。

```python
# 例如此前提到的流结构
flow = Flow(
    "test-flow",
    [n1, n3, n4, n5, n7],
    [n2, n3, n4],
    [n4, n6, n7]
)
```

流存储对象在一次运行期内存活，一次运行指 DAG 被完整遍历一次。当然，控制方法可能导致 DAG 的遍历提前终止。流调用链上均可通过 {func}`.get_flow_store` 获取流存储：

```python
from melobot.handle import get_flow_store

@node
async def test_node() -> None:
    store = get_flow_store()
```

更推荐的方式是通过依赖注入获取：

```python
from melobot.handle import FlowStore

# 这一依赖注入条目，不具有结点选择性
# 因为流存储在流运行时，始终存在于上下文中
@node
async def test_node(store: FlowStore) -> None:
    ...
```

在计算机科学中，反射式编程或反射，是指计算机程序在运行时可以访问、检测和修改它本身状态或行为的一种能力[^1]。对于处理流对象，它在运行期也可以实现对于自身状态和行为的探察。使用 {func}`.get_flow_records` 获得流记录的元组，这记录了运行至当前结点的遍历路径、发生的“控制操作记录”（控制方法的调用）：

```python
from melobot.handle import get_flow_records

@node
async def test_node() -> None:
    records = get_flow_records()
    for r in records:
        ...
```

在流记录元组中，甚至会记录依赖注入项不匹配时跳过的结点。还能获取前置结点的运行情况（正常结束或控制方法导致的提前结束）。更多内容参考流记录对象的文档：{class}`.FlowRecord`。

同样推荐使用依赖注入获取：

```python
from melobot.handle import FlowRecord

# 这一依赖注入条目，不具有结点选择性
# 因为流记录信息在流运行时，始终存在于上下文环境中
@node
async def test_node(records: tuple[FlowRecord, ...]) -> None:
    ...
```

```{admonition} 提示
:class: tip

流存储和流记录不会在主流、子流间共享。无法使用这些功能完成跨流信息传递。
```

## 流的上下文传播

常规的同步函数调用，或异步函数的直接 `await`，不会影响事件处理流上下文的传播。

在处理流的调用链上，可能存在异步任务创建操作：

```python
@node
async def eg_node() -> None:
    t = asyncio.create_task(...)
    await t
```

异步任务 `t` 运行时将形成一条新的调用链，与流的调用链只存在回调依赖关系。

如果任务内部需要**访问事件处理流的上下文**，请务必在复制的上下文中运行任务：

```python
import asyncio
import contextvars
from functools import partial

async def func(...): ...

@node
async def eg_node() -> None:
    flow_ctx = contextvars.copy_context()
    t = asyncio.create_task(flow_ctx.run(func))
    await t
    # 传递参数，使用 lambda 技巧或 partial 包裹
    t2 = asyncio.create_task(flow_ctx.run(lambda: func(...)))
    await t2
    t3 = asyncio.create_task(flow_ctx.run(partial(func, ...)))
    await t3
```

如果任务需要**修改事件处理流的上下文内容**，例如在流存储设置字段等操作，考虑将“修改操作”作为返回值传递，在流调用链中实际修改。

## 流的上下文动态变量

在 [melobot.handle](../api/melobot.handle) 模块内，存在一些动态变量。当你尝试引用它们时，它们会基于当前上下文返回对应的值：

```python
from melobot.adapter import Event
from melobot.handle import FlowStore, FlowRecord
import melobot.handle as mbh

@node
async def test_node() -> None:
    # 当前事件
    e: Event = mbh.event
    # 当前流存储
    store: FlowStore = mbh.f_store
    # 当前流记录元组
    records: tuple[FlowRecord, ...] = mbh.f_records
```

不在事件处理上下文中时，引用这些变量会发出异常。

所以不能在模块顶级作用域使用 `from ... import ...`，也不能在缺乏有效上下文的情景中使用：

```python
import melobot.handle as mbh
# 错误用法，此时不在上下文中，尝试引用会失败
from melobot.handle import event

# 假设这个函数不在流调用链上，也没有在复制的流上下文中运行
async def func(...) -> None:
    # 错误用法，不在上下文中，尝试引用会失败
    mbh.event
```

同理，此时显然也无法使用 {func}`.get_event`, {func}`.get_flow_store` 等方法。

## 总结

本篇主要说明了 melobot 事件处理流及其机制。

内容较多，建议善用文档的搜索功能和浏览器的 `Ctrl-F` 功能。

下一篇将重点说明：依赖注入及其特性。


[^1]: [反射式编程](https://zh.wikipedia.org/wiki/反射式编程)
