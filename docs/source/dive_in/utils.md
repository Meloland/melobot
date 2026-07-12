# 实用组件

`melobot.utils` 汇集了框架内部也会复用的一组小而通用的组件：事件预处理的检查、匹配与解析，以及异步包装、并发控制、调度和若干基础辅助函数。它们不依赖某个协议，因而也可以用于插件自身的业务代码。

## 检查、匹配与解析

这三类组件共同构成事件进入处理函数前的“预处理”过程：

1. **检查**（{class}`~melobot.utils.check.Checker`）判断一个事件是否允许继续处理；
2. **匹配**（{class}`~melobot.utils.match.Matcher`）判断文本事件是否符合某种文本规则；
3. **解析**（{class}`~melobot.utils.parse.Parser`）从文本中提取参数，产生 {class}`~melobot.utils.parse.AbstractParseArgs`。

在事件绑定方法中，它们的执行顺序正是上述顺序。检查适用于任意事件；匹配和解析仅适用于 {class}`.TextEvent`。常见的 {func}`.on_start_match`、{func}`.on_regex_match` 和 {func}`.on_command` 已经分别封装了对应的匹配或命令解析逻辑，因此普通业务通常不必直接实例化匹配器或解析器。

```{admonition} 继续阅读
:class: note
[事件预处理](../intro/event-preprocess)完整讲解了自定义 `Checker`、`Matcher`、`Parser`、命令解析、参数格式化和交互式补参。本篇不重复这些用法；需要精确的构造参数与方法签名时，请查阅 [melobot.utils API](../api/melobot.utils)。
```

## 异步包装与并发控制

bot 的处理过程天然是异步的，但业务代码往往同时包含同步函数、协程函数和普通上下文管理器。`utils` 提供的包装工具用于在这些接口之间衔接。

### 统一为异步调用

| 工具 | 作用 | 适用场景 |
| --- | --- | --- |
| {func}`~melobot.utils.to_async` | 将同步/异步可调用对象或可等待对象包装为异步可调用对象 | 某个回调同时接受同步与异步实现 |
| {func}`~melobot.utils.to_coro` | 将上述对象转换为一个协程对象 | 需要交给 `await` 或 `asyncio.create_task` |
| {func}`~melobot.utils.to_sync` | 将可调用对象包装为同步函数；若结果可等待则创建任务执行 | 仅为兼容同步回调接口，且不需要返回值 |

```python
import asyncio

from melobot.utils import to_async, to_coro

def get_name() -> str:
    return "melobot"

async_get_name = to_async(get_name)
name = await async_get_name()

# 需要一个协程对象时
task = asyncio.create_task(to_coro(get_name))
```

`to_sync` 不会等待异步结果，也不会向调用者返回其值；异步任务中的异常也需要由业务代码自行处理。因此它适合“通知型”的同步回调，不适合需要结果或必须传播异常的调用链。

### 函数级控制装饰器

{func}`~melobot.utils.if_`、{func}`~melobot.utils.ctx`、{func}`~melobot.utils.lock`、{func}`~melobot.utils.cooldown`、{func}`~melobot.utils.semaphore`、{func}`~melobot.utils.timelimit` 和 {func}`~melobot.utils.speedlimit` 都可装饰同步或异步函数，装饰后的函数统一为异步可调用对象。

| 工具 | 控制效果 | 发生限制时的默认行为 |
| --- | --- | --- |
| `if_` | 按条件决定是否执行 | 条件为假时不执行；可提供拒绝/接受回调 |
| `ctx` | 在同步或异步上下文管理器中执行函数 | 上下文退出后返回函数结果；不会接收 `yield` 的值 |
| `lock` | 同一装饰器实例内互斥执行 | 等待锁；提供回调时则直接执行回调 |
| `cooldown` | 一次执行结束后进入冷却期 | 等待冷却；可为忙碌或冷却状态分别提供回调 |
| `semaphore` | 限制同时运行的数量 | 等待许可；提供回调时立即执行回调 |
| `timelimit` | 限制单次执行时间 | 抛出 `TimeoutError`；可改用回调返回替代结果 |
| `speedlimit` | 固定时间窗口内限制调用次数 | 等待到可执行；可提供超限回调 |

例如，为一个耗时操作限制并发数并设置超时：

```python
from melobot.utils import semaphore, timelimit

@semaphore(value=3)
@timelimit(timeout=10)
async def fetch_weather(city: str) -> str:
    return await request_weather_service(city)
```

这些装饰器把锁、计数和时间状态保存在装饰器创建时的闭包中。因此它们控制的是**整个被装饰函数**的所有调用，而不是按用户、群组或会话自动隔离。需要“每个用户独立限流”之类的规则时，应结合会话、字典和显式锁自行组织状态。

```{admonition} 提示
:class: tip
`speedlimit` 使用固定窗口算法：窗口边界附近可能出现短时间内较集中的调用。这对于一般命令保护已经足够；若需要平滑的令牌桶或分布式限流，应使用专门的限流组件。
```

### 读写上下文

{class}`.RWContext` 是异步读写锁风格的上下文管理器：多个读操作可以同时进行，写操作与任何读、写操作互斥。`read_limit` 可进一步限制并发读数量。

```python
from melobot.utils import RWContext

cache_lock = RWContext(read_limit=20)

async def get_cache(key: str) -> str | None:
    async with cache_lock.read():
        return cache.get(key)

async def set_cache(key: str, value: str) -> None:
    async with cache_lock.write():
        cache[key] = value
```

## 延迟与定时调度

这些工具都要求在正在运行的事件循环中调用，并返回 `asyncio` 的调度句柄或任务：

| 工具 | 接受的对象 | 返回值 | 说明 |
| --- | --- | --- | --- |
| {func}`~melobot.utils.call_later` | 同步回调函数 | `asyncio.TimerHandle` | 延迟若干秒执行 |
| {func}`~melobot.utils.call_at` | 同步回调函数 | `asyncio.TimerHandle` | 在 Unix 时间戳对应时刻执行；过去时间会尽快执行 |
| {func}`~melobot.utils.async_later` | **协程对象** | `asyncio.Task` | 延迟后等待该协程 |
| {func}`~melobot.utils.async_at` | **协程对象** | `asyncio.Task` | 在指定时间戳执行协程 |
| {func}`~melobot.utils.async_interval` | 返回协程的无参函数 | `asyncio.Task` | 间隔执行；取消任务即可停止 |

```python
from melobot.utils import async_interval, async_later

# 传入协程对象，而不是 async 函数本身
warmup_task = async_later(warmup(), delay=5)

# 传入可重复调用、每次都产生新协程的函数
report_task = async_interval(report_metrics, interval=60)

# 不再需要周期任务时
report_task.cancel()
```

`async_interval` 会等待每次回调完成后再进入下一轮，因此不会让同一周期任务重叠运行；回调耗时会延后下一次实际执行时间。持有返回的 `Task` 并在 bot 停止时取消，是管理这类后台任务的基本做法。

## 其他基础工具

下表用于快速定位其余常用组件；它们都可从 `melobot.utils` 导入。

| 工具 | 简介 |
| --- | --- |
| {func}`~melobot.utils.truncate` | 截断过长的 `str` 或 `bytes`，可指定占位符和最大长度 |
| {func}`~melobot.utils.get_obj_name` | 尽力取得函数、类或一般对象的可读名称，常用于日志和错误信息 |
| {func}`~melobot.utils.singleton` | 将类声明为单例，适合全局协调器等确实只应有一份状态的对象 |
| {func}`~melobot.utils.get_id` | 使用内部雪花算法生成 URL 安全的 Base64 字符串 id；不保证线程安全 |

```{admonition} 关于单例与全局 id
:class: caution
`singleton` 和 `get_id` 面向进程内的便捷使用，并不提供跨进程协调能力。多进程部署时，分布式锁、全局唯一 id 或共享配置应交由数据库、消息系统或专用服务处理。
```

## 总结

`utils` 的价值在于让通用控制逻辑从业务处理函数中抽离出来。事件筛选和命令参数处理优先复用现成的检查、匹配和解析机制；并发、超时、调度与读写协调则根据资源作用域选择装饰器、`RWContext` 或独立的后台任务。所有组件的完整参数、返回类型与继承接口均可在 [melobot.utils API](../api/melobot.utils) 中查阅。

下一篇将介绍：[类型工具](./typ)。
