# 会话控制与管理

## 为什么需要会话

在之前的教程中，我们编写的事件处理函数，本质上都以"请求——响应"的模式工作。每当一个事件触发处理过程，处理函数开始执行、产生结果，随即结束退出。每次交互彼此独立，处理函数不记得上一次发生过什么。

这种模式对于简单指令来说已经足够：

```python
from melobot import send_text, on_start_match

@on_start_match(".ping")
async def ping() -> None:
    await send_text("pong!")
```

但考虑更复杂的交互情景——用户希望与机器人进行**多轮、步骤式的对话**。例如查询天气：

```text
用户：天气
Bot：输入您想要查询的城市哦，亲~
用户：北京
Bot：想要查看多少天的天气预报呢？
用户：7
Bot：为您查询中，请稍后...
    查询结果为：
    （此处省略结果）
    如果您对服务满意，请给我们 5 星好评哦 ^ ^
```

会话正是为了解决这些问题而设计的。它把这些复杂性封装在内部，让你用自然的线性代码风格来编写多轮交互。

### 会话能做什么

何时需要使用会话？如下：

| 场景 | 是否使用会话 |
|------|-------------|
| 单次命令响应（`.ping` → `pong!`） | 不需要 |
| 多轮交互（问答式填写、步骤式引导） | 强烈推荐 |
| 需要跨事件记住信息（计数器、表单） | 推荐 |
| 纯一次性事件处理（日志、过滤） | 不需要 |

下面是不使用会话实现交互的情形（需要手动管理状态和事件匹配）：

```python
# 不使用会话实现查天气：需要手写大量样板代码
import asyncio
from melobot import on_text, send_text
from melobot.adapter import TextEvent

# 需要全局字典来存储状态
user_states = {}
LOCK = asyncio.Lock()
user_lock = {}

@on_text()
async def query_weather(event: TextEvent) -> None:
    user_id = event.user_id
    
    async with LOCK:
        user_lock.setdefault(user_id, asyncio.Lock())
    ulock = user_lock[user_id]

    # 手动判断状态
    async with ulock:
        if user_id not in user_states:
            if event.text.startswith("天气"):
                await send_text("请输入要查询的城市：")
                user_states[user_id] = {"step": 1}
            return
    
    async with ulock:
        state = user_states[user_id]

        if state["step"] == 1:
            state["city"] = event.text
            await send_text("请输入要查询的天数：")
            state["step"] = 2

        elif state["step"] == 2:
            city = state["city"]
            days = event.text
            result = await do_query(city, days)
            await send_text(f"查询结果：{result}")
            del user_states[user_id]  # 手动清理
            del user_lock[user_id]
```

这是多么的繁琐：维护状态、并发安全的代码和业务逻辑已经混成一坨了。

## 快速上手：五分钟学会会话

让我们回到刚才的这个需求，看看使用会话的写法：

```python
from typing import Annotated
from melobot import on_text, send_text, Reflect
from melobot.adapter import TextEvent
from melobot.session import suspend, DefaultRule, enter_session

@on_text()
async def query_weather(event: Annotated[TextEvent, Reflect()]) -> None:
    if not event.text.startswith("天气"):
        return

    async with enter_session(rule=DefaultRule()):
        await send_text("请输入要查询的城市：")
        await suspend(timeout=30, auto_stop=True)
        city = event.text

        await send_text("请输入要查询的天数：")
        await suspend(timeout=30, auto_stop=True)
        days = event.text

        result = await do_query(city, event)
        await send_text(f"查询结果：{result}")
```

你可能注意到了：不需要额外变量来控制状态和保证并发安全。这是因为 {func}`.enter_session` 创建了一个安全的异步上下文。下面我们来逐一深入了解这些组件。

## 会话规则：决定"谁"能加入会话

会话规则（{class}`.Rule`）定义了**什么样的事件可以继续当前会话**。当会话暂停后，bot 会收到来自四面八方的各种事件——只有那些通过了规则判断的事件，才能唤醒这个会话。

最常用的规则是 {class}`.DefaultRule`。它通过比较事件的 `scope` 属性来做判断。以 OneBot v11 为例，`scope` 被设为 `(群组ID | None, 用户ID)` 二元组——同一群聊或同一私聊的事件拥有相同的 `scope`，因而可以进入同一个会话。

这就是为什么在上面的查天气示例中，同一群聊中不同用户发送的消息不会互相干扰——因为 `scope` 不同，会话不会匹配。

### 使用默认会话规则

有两种等价的方式使用 {class}`.DefaultRule`：

**方式一：直接使用 enter_session**

```python
@on_text()
async def handler() -> None:
    async with enter_session(rule=DefaultRule()):
        await send_text("你好！在接下来的 30 秒内，我会记住你说的话。")
        await suspend(timeout=30)
        await send_text(f"你的第二句话是：{session.event.text}")
```

**方式二：使用 legacy_session 快捷参数**

文本事件绑定方法（{func}`.on_text`、{func}`.on_start_match` 等）提供了 `legacy_session` 参数，设为 `True` 相当于自动使用 {class}`.DefaultRule` 进入会话：

```python
@on_text(legacy_session=True)
async def handler(event: Annotated[TextEvent, Reflect()]) -> None:
    if not event.text.startswith("查询"):
        return
    await send_text("请输入您的学号：")
    await suspend(timeout=30)
    # ...
```

`legacy_session=True` 是最便捷的写法，适合绝大多数使用场景。

### 自定义规则

当 {class}`.DefaultRule` 不够用的时候，melobot 支持两种方式自定义规则。

#### Rule.new() 工厂方法

适合简单的比较逻辑。提供一个接收两个事件、返回布尔值的函数即可：

```python
from melobot.session import Rule
from melobot.adapter import Event

# 规则：只有来自同一用户的事件才匹配
same_user_rule = Rule.new(lambda e1, e2: e1.user_id == e2.user_id)

# 规则：只有文本内容完全相同的才匹配
same_text_rule = Rule.new(
    lambda e1, e2: (
        hasattr(e1, 'text') and hasattr(e2, 'text')
        and e1.text == e2.text
    )
)
```

然后像使用 {class}`.DefaultRule` 一样使用它们：

```python
async with enter_session(rule=same_user_rule):
    await send_text("同用户会话已开启~")
    await suspend(timeout=30)
```

#### 继承 Rule 类

当判断逻辑比较复杂，或者需要初始化一些参数时，继承 {class}`.Rule` 类更合适。你需要实现 {meth}`~.Rule.compare` 方法或 {meth}`~.Rule.compare_with` 方法，二选一即可：

```python
from melobot.session import Rule
from melobot.adapter import Event

class KeywordSessionRule(Rule[Event]):
    """关键词会话规则，包含特定关键词的事件才能继续会话"""
    
    def __init__(self, keywords: list[str]):
        super().__init__()
        self.keywords = keywords
    
    async def compare(self, e1: Event, e2: Event) -> bool:
        """
        返回 False，则认为新事件 e2 与旧事件 e1 不在同一会话
        否则认为在同一会话中
        """
        # 基本条件：同一用户
        if e1.user_id != e2.user_id:
            return False
        # 关键词匹配：新事件必须包含任一关键词
        t2 = e2.text if hasattr(e2, 'text') else ''
        return any(kw in t2 for kw in self.keywords)
```

使用：

```python
help_rule = KeywordSessionRule(["帮助", "help", "说明"])

@on_text()
async def helper() -> None:
    async with enter_session(rule=help_rule):
        await send_text("进入帮助会话。你可以输入"帮助 xxxxx"继续，或用其他消息退出。")
        while True:
            if not await suspend(timeout=30):
                # 超时则退出循环
                break
            await send_text(f"继续帮助模式...你说的是：\n{session.event.text}")
```

#### 使用 compare_with 访问会话状态

如果需要在判断时访问会话当前的状态（例如[会话存储](#session-store)中的数据），实现 {meth}`~.Rule.compare_with` 方法：

```python
from melobot.session import Rule, CompareInfo
from melobot.adapter import Event

class StepAwareRule(Rule[Event]):
    """结合会话状态的规则，不同步骤接受不同类型的事件"""
    
    async def compare_with(self, info: CompareInfo[Event]) -> bool:
        # 基本 scope 判断
        if info.old_event.scope != info.new_event.scope:
            return False
        
        # 取出已经存在的会话
        session = info.session
        # 取出该会话存储的一些信息
        step = session.store.get("step", 1)
        
        if step == 1:
            # 第 1 步：只接受文本事件
            return hasattr(info.new_event, 'text')
        elif step == 2:
            # 第 2 步：假设需要图片事件
            return hasattr(info.new_event, 'is_image') and info.new_event.is_image
        return True
```

{class}`.CompareInfo` 提供了三个字段：`session`（已存在的会话对象）、`old_event`（该会话当前指向的事件）、`new_event`（待判断的新事件）。

## 会话管理

### 进入会话

{func}`.enter_session` 是开启一段会话的标准方式。它返回一个异步上下文管理器：

```python
from melobot.session import enter_session

@on_text()
async def handler() -> None:
    async with enter_session(rule=DefaultRule()) as session:
        # 在此上下文中，会话处于活跃状态
        # 可以使用 suspend()、访问 session.store 等
        ...
    # 退出上下文后，会话自动结束
```

`enter_session` 的参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `rule` | `Rule \| type[Rule]` | 无默认值 | 会话规则（或规则类，传入类时会自动实例化） |
| `wait` | `bool` | `True` | “同一会话”正在运行时，是否等待其变为空闲再进入 |
| `nowait_cb` | `Callable` | `None` | `wait=False` “同一会话”已经在运行时，执行的回调（同步或异步均可） |
| `keep` | `bool` | `False` | 退出会话上下文后是否保持会话不销毁（会话不销毁，会话存储也会持续存在） |
| `auto_release` | `bool` | `True` | 暂停后是否自动释放当前事件（一般不需要改动） |

**关于 `rule` 参数**：决定了会话能否在多个处理流/处理结点间**共享**。传递 `rule` 的方式不同，行为也不同：

1. **传递一个规则对象（实例）**：该规则对象仅用于这一次会话。如果你将同一个规则对象传给多处 {func}`.enter_session` 调用，这些调用就可以进入同一个会话。这是**跨处理流/处理结点共享会话**的基础。

2. **传递一个规则类（而非实例）**：melobot 内部会运行无参实例化并将其缓存为单例。如果在多处 {func}`.enter_session` 调用中传递同一个规则类，这些调用同样可以进入同一个会话——因为 melobot 为同一规则类只维护一个单例实例，效果等同于共享同一个规则对象。

由此，有三种推荐的调用规范：

| 场景 | 推荐写法 | 说明 |
|------|----------|------|
| 会话不需要共享，且规则类只在一处使用 | `enter_session(rule=DefaultRule)` | 传递类对象，单例自动管理 |
| 会话不需要共享（通用、安全） | `enter_session(rule=DefaultRule())` | 传递实例，即便多处使用也互不影响 |
| 会话需要在多处共享 | 多处均传同一 `rule` 实例或同一 `rule` 类 | 让 melobot 在多个流/结点间匹配到同一会话 |

```python
# 规范 a：不需要共享，传递手动实例化的 rule 对象（最安全）
@on_text()
async def handler1() -> None:
    async with enter_session(rule=DefaultRule()):
        ...

# 规范 b：不需要共享，且确定 DefaultRule 类只在此处使用
@on_text()
async def handler2() -> None:
    async with enter_session(rule=DefaultRule):
        ...
```

```python
# 规范 c：需要在多处共享——使用同一个 rule 实例
shared_rule = KeywordRule(["继续", "下一步"])

@on_text()
async def handler_a() -> None:
    async with enter_session(rule=shared_rule):
        ...

@on_text()
async def handler_b() -> None:
    async with enter_session(rule=shared_rule):
        ...
# 或传递同一个 rule 类：
@on_text()
async def handler_c() -> None:
    async with enter_session(rule=KeywordRule):
        ...

@on_text()
async def handler_d() -> None:
    async with enter_session(rule=KeywordRule):
        ...
```

如果不确定，使用规范 a（传递实例）是最安全的选择。

**关于 `wait` 和 `nowait_cb` 参数**：melobot 会自动管理同一规则下的多个并发会话。这对用户是完全透明的——你不需要写任何并发控制代码。举个例子：假设你有一个"猜数字"的会话处理函数。在同一个群聊中，用户 A 先发起了"猜数字"，然后用户 B 也发起了"猜数字"。因为 {class}`.DefaultRule` 会匹配 scope，而 scope 在 OneBot v11 中包含用户 ID，所以 A 和 B 的 scope 不同，**会创建两个独立的会话**。这两个会话并发运行，互不干扰。

但如果由于某种原因，两个 scope 相同的事件几乎同时到来（例如 A 快速发起两次“猜数字”），默认情况下后来的事件会排队等待（`wait=True`）。如果你希望冲突时通知用户，使用 `wait=False` + `nowait_cb` 的组合：

```python
async def busy_notify() -> None:
    await send_text("您有一个正在进行的操作，请先等待它完成～")

@on_text()
@ctx(partial(enter_session, DefaultRule(), wait=False, nowait_cb=busy_notify))
async def handler() -> None:
    await send_text("会话已开启。")
    await suspend(timeout=60)
```

这样就不会运行重复的“猜数字”，`busy_notify` 回调会被执行。而第二次“猜数字”事件不会被这一会话接管，它将继续向低优先级的处理流传播。

**关于 `keep` 参数**：默认情况下（`keep=False`），退出 {func}`.enter_session` 上下文后会话自动结束。如果你希望会话在退出上下文后继续存活（例如等待其他处理流来接管），设置 `keep=True`。之后需要手动调用 {meth}`~.Session.stop_keep()` 来允许会话销毁：

```python
async with enter_session(rule=DefaultRule(), keep=True) as session:
    await send_text("会话已开启。即使退出也会保持。")
    await suspend(timeout=60)
    # 退出上下文后会话继续存在

# 之后在某个时刻必须手动结束，否则会造成资源泄漏！
session.stop_keep()
```

`keep=True` 的典型使用场景是**跨处理流共享会话**。假设你有两个不同的处理流——一个负责收集用户的查询条件，另一个负责处理用户的确认操作。通过 `keep=True`，第一个处理流创建的会话可以在退出上下文后保持活跃，第二个处理流被触发时可以直接匹配到这个会话，继续同一轮交互。

**关于 `auto_release` 参数**：默认（`auto_release=True`）会在会话暂停后自动释放事件，允许事件被更低优先级的处理流使用。如果你的会话在暂停后，不希望刚才的事件被低优先级的处理流使用，那么请设置为 `False`，并在合适的时候使用 {meth}`~.Session.release` 释放对事件的控制权：

```python
# 释放此会话上所有历经事件的控制权，它们将可以向低优先级传播
session.release()
# 释放一个或多个历经的事件：
session.release(e1, e2, ...)
```

忘记释放控制权将导致资源泄漏！并可能导致低等级处理流的饥饿。 

### 进入会话（精简版）

对于典型的，进行简单判断后再进入会话的精简写法：

```python
from functools import partial
from melobot.utils import _if, ctx

# 也可以替换为 @node
@on_text(...)
# on_text 保证进行判断是一定是 TextEvent
# 所以下面可以安全的取 text 属性
@_if(lambda: e.text.startswith("xxx"))
# 下面不要使用 @ctx(lambda: enter_session(DefaultRule()))
# 这样每次都会创建一个新规则，是不对的！
# 而使用 partial 会直接缓存参数，因此不会重复创建规则
@ctx(partial(enter_session, DefaultRule()))
# 但是如果你已经有一个 rule 对象，那么这样写是可以的：
# @ctx(lambda: enter_session(rule))
async with _(...) -> None: ...
```

当然 {func}`._if` 装饰器也可以在 {func}`.ctx` 之下，这取决于你的需求。

### 暂停等待

{func}`.suspend` 是会话中最核心的操作——将当前处理暂停，等待匹配的新事件来唤醒：

```python
from melobot.session import suspend

# 无限期暂停（一直等到匹配事件）
await suspend()

# 限时暂停（超时返回 False）
if not await suspend(timeout=30):
    await send_text("等待超时，操作已取消。")
    return

# 超时自动停止处理流
await suspend(timeout=30, auto_stop=True)
# 如果超时，后续代码不会执行
```

(session-store)=
### 会话存储

{any}`SessionStore` 是会话生命周期内的键值存储。它就是一个字典（带有一个额外的便捷方法 `set`），用于在暂停/恢复之间传递数据：

```python
from melobot.session import SessionStore

@on_text()
@ctx(partial(enter_session, DefaultRule()))
async def handler(store: SessionStore) -> None:
    # 两种写入方式等价
    store["step"] = 1
    store.set("username", "Alice")

    # 读取
    current_step = store["step"]
    
    await suspend(timeout=30)
    # 恢复后 store 中的数据依然存在
    store["step"] = 2
```

常见的用法包括：
- 保存多步操作中的中间输入（像个"便签本"）
- 记录当前处于哪个步骤
- 暂存需要在后续步骤中使用的计算结果
- 保存状态信息，供会话规则进行“比较”时使用

会话存储的生命周期与会话一致：进入会话时创建，会话结束时销毁。不同会话之间的存储完全独立，互不影响。

### 动态属性与动态函数

除了通过 `async with enter_session(...) as session` 获取会话对象，melobot 还提供了上下文感知的快捷方式：

```python
import melobot.session as mb_session

@on_text()
@ctx(partial(enter_session, DefaultRule()))
async def handler() -> None:
    # 动态属性——始终反映当前上下文的最新值
    cur_session = mb_session.session      # 当前 Session 对象
    cur_store = mb_session.s_store        # 当前 SessionStore
    cur_rule = mb_session.rule            # 当前 Rule 对象
    
    # 也可以用函数形式
    from melobot.session import get_session, get_session_store, get_rule
    cur_session = get_session()           # 等价于 mb_session.session
    cur_store = get_session_store()       # 等价于 mb_session.s_store
    cur_rule = get_rule()                 # 等价于 mb_session.rule
```

这些动态属性会自动更新。但注意它们只在会话上下文中可用，在模块顶级 `from melobot.session import session` 会失败。

以及不要赋值给新变量，新变量显然不会自动更新。

## 会话中的依赖注入

### 注入会话组件

以下类型可以在类型注解中用于依赖注入：

| 注入类型 | 获取的值 |
|----------|---------|
| {class}`.Session` | 当前会话对象 |
| {class}`.SessionStore` | 当前会话存储 |
| {class}`.Rule` | 当前会话的规则对象 |

示例：

```python
from melobot.session import Session, SessionStore

@ctx(partial(enter_session, DefaultRule()))
async def handler(session: Session, store: SessionStore, rule: Rule) -> None:
    ...
```

### 反射式事件注入

{class}`.Reflect()` 创建了一个**反射代理**。从使用者的角度看，`event` 和普通的事件对象没有区别——访问属性、调用方法都一样。区别在于，每次你访问 `event.text` 时，它都会自动从当前上下文中获取最新的事件对象，然后返回其 `text` 属性。

#### 注意事项

```python
# ✅ 直接访问属性和调用方法是安全的
text = event.text
event.some_method()

# ⚠️ 进行 isinstance 判断时，需要获取原始对象
from melobot.protocols.onebot.v11 import MessageEvent
is_msg = isinstance(event.__origin__, MessageEvent)

# ⚠️ 传给不了解反射机制的函数时，也需要原始对象
some_external_func(event.__origin__)

# ⚠️ 不要对反射对象使用 == 比较或作为字典键
```

(get_session_arg_doc)=
### 注入会话存储的值

如果你的处理流中，前几个结点已经将数据存入了 {class}`.SessionStore`，后续结点可以直接通过 {func}`.get_session_arg` 将指定键的值注入为参数：

```python
from melobot.session import get_session_arg

@node
async def step3(
    user_name: str = get_session_arg("name"),
    user_age: int = get_session_arg("age"),
) -> None:
    # 相当于自动执行了 store["name"] 和 store["age"]
    print(f"处理用户: {user_name}, {user_age} 岁")
```

{func}`.get_session_arg` 让依赖注入系统从当前会话存储中查找指定键。如果键不存在，依赖注入失败，结点被自动跳过——**这又是一种"区分调用"的实现方式**。

需要注意的是，{func}`.get_session_arg` 在进入函数前取值。如果需要最新的值，从暂停中恢复后应该从会话存储手动再取值：

```python
@node
async def handler(store: SessionStore) -> None:
    store["step"] = 1
    await suspend(timeout=30)
    # 恢复后手动获取
    current_step = store["step"]
```

{func}`.get_session_arg` 函数的其他参数类似于 {func}`.get_flow_arg`，参考：[对应用法](#get_flow_arg_doc)

### 依赖注入可用情况

下表总结了会话不同阶段各类依赖注入的可用情况：

| 阶段 | `Session` | `SessionStore` | `Rule` | 事件（常规注入） | 事件（Reflect） | `get_session_arg` |
|------|-----------|---------------|--------|----------------|----------------|-------------------|
| 进入会话前 | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| 会话运行期 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 挂起中 | — | — | — | — | — | — |
| 恢复后 | ✅ | ✅ | ✅ | 仍是旧事件 | 自动指向新事件 | 仍是挂起前的值 |
| 退出会话后 | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |

最需要留意的是 **事件（常规注入）和事件（Reflect）** 在恢复后的差异——这就是为什么在会话中使用事件时，几乎总要搭配 {class}`.Reflect`。


## 常见问题与注意事项

1. **不能在会话外使用 suspend**：{func}`.suspend()` 只能在 {func}`.enter_session` 上下文管理器内调用。如果在会话外调用，会因为找不到会话上下文而抛出异常
2. **不能嵌套会话**：melobot 不支持在已存在的会话内再创建新会话。这会抛出异常。

### 与事件预处理（check/match/parse）的关系

`legacy_session=True` 与 `checker`/`matcher`/`parser` 的执行顺序为：预处理先行，会话后创建。因此检查器、匹配器和解析器**不能使用 {func}`.suspend` 或访问会话存储**。

如需在这些阶段使用会话特性，应手动使用 {func}`.ctx` 和 {func}`.enter_session` 将会话创建提前，或将预处理逻辑合并到处理函数内部。

## 小结

本篇介绍了 melobot 的会话控制系统，核心要点如下：

- **为什么需要会话**——多轮交互需要"状态保持"和"异步等待"，会话将这些复杂性封装为简单的 API
- **会话规则**——{class}`.DefaultRule` 满足大多数需求（通过 `legacy_session=True` 一键开启）；特殊需求时通过 {meth}`~.Rule.new()` 或继承 {class}`.Rule` 自定义规则
- **会话管理**——{func}`.enter_session` 进入会话、{func}`.suspend` 暂停等待、{class}`.SessionStore` 存储中间数据，三者配合即可实现任意复杂的交互流程
- **依赖注入**——在会话中使用 {class}`.Reflect()` 注入事件是**最关键的技巧**（确保挂起恢复后事件自动更新）；{func}`.get_session_arg` 可将存储值注入为参数，简化代码

会话控制使得 melobot 的处理流从"无状态"的单次处理跃升到"有状态"的多轮交互。结合依赖注入和处理流控制，你可以实现各种形式的交互式对话逻辑——从简单的问答到复杂的多分支交互。

下一篇将介绍：[插件系统与进阶用法](./plugin_usage)。
