# bot 对象与相关接口

前面的章节已经说明了如何创建 {class}`.Bot`、添加协议栈、加载插件和启动程序。本篇从管理者的视角补充 bot 对象的特性：它何时完成配置、怎样在运行中的代码里取得它，以及怎样查询和扩展其已注册的组件。

```{admonition} 相关知识
:class: note
如果你还不熟悉创建和启动 bot 的基本流程，请先阅读[开始创建机器人](../intro/create-bot)；源、适配器和插件的详细用法分别在[源与适配器](./source_adapter)和[插件系统与进阶用法](./plugin_usage)中介绍。
```

## 实例名称与配置期

创建 bot 时的 `name` 不只是展示名称，也是当前 Python 进程中 bot 实例的标识。同一时刻不能存在两个同名 bot：

```python
from melobot import Bot

main_bot = Bot("main")
# Bot("main")  # 抛出 BotError：同名实例已存在
test_bot = Bot("test")
```

名称还会用于日志和生命周期 hook 的标识。因此，多 bot 程序应为每个实例提供稳定且不同的名称，不建议依赖默认值 `"melobot"`。

### 配置会在首次加载插件时冻结

源和适配器必须在 bot 的**配置期**绑定。一个容易忽略的事实是：首次调用 {meth}`~.Bot.load_plugin` 就会初始化 bot 的核心组件，不必等到调用 {meth}`~.Bot.run`。从这一刻开始，{meth}`~.Bot.add_input`、{meth}`~.Bot.add_output`、{meth}`~.Bot.add_io` 和 {meth}`~.Bot.add_adapter` 都不能再调用。

```python
from melobot import Bot, PluginPlanner
from melobot.protocols.onebot.v11 import OneBotV11Protocol, WSClient

bot = Bot("main")
bot.add_protocol(OneBotV11Protocol(WSClient("ws://127.0.0.1:8080")))

# 此调用会结束配置期
bot.load_plugin(PluginPlanner("1.0.0"))

# bot.add_protocol(...)  # 错误：底层源、适配器已不能再绑定
```

这也是主程序通常采用“先添加所有协议支持，再加载插件”的原因。插件可以在启动后动态加载，但协议组件不支持以这种方式动态增删；若运行时需要启用或停用某项业务功能，应优先将它设计为插件或处理流。

```{admonition} 提示
:class: tip
{meth}`~.Bot.add_input`、{meth}`~.Bot.add_output`、{meth}`~.Bot.add_io`、{meth}`~.Bot.add_adapter` 和 {meth}`~.Bot.add_protocol` 都会返回 bot 本身，因此可以按配置顺序链式调用。
```

## 在当前上下文中获取 bot

{func}`.get_bot` 返回当前执行上下文中的 bot。它适用于不方便通过参数接收 bot 的辅助函数，以及插件加载、生命周期 hook、事件处理流等由 bot 发起的执行过程。

```python
from melobot.bot import get_bot

def get_cache_prefix() -> str:
    # 此函数必须在 bot 的执行上下文中调用
    return f"{get_bot().name}:cache"
```

在没有活动 bot 上下文的普通模块代码、独立脚本或自行创建且未继承上下文的线程中调用，会抛出 {exc}`.BotError`。因此，不要让这类通用函数在导入时立刻调用 {func}`.get_bot()`；将调用放在真正执行时更安全。

`melobot.bot` 模块还提供动态变量 {data}`~melobot.bot.bot`，它等价于在当前时刻调用 {func}`.get_bot()`。例如下面的代码位于由 {meth}`~.Bot.load_plugin` 加载的插件模块中：

```python
# __plugin__.py
from melobot.bot import bot

@bot.on_started
async def report_started() -> None:
    bot.logger.info(f"{bot.name} 已启动")
```

这里的 `bot` 在模块被访问时依赖当前上下文，并不是一个可在任意位置使用的全局单例。对于事件处理结点和各种生命周期 hook，若只需要使用 bot，仍然更推荐直接声明 `Bot` 类型参数，让依赖注入完成获取：

```python
from melobot import Bot, GenericLogger

async def setup(bot: Bot, logger: GenericLogger) -> None:
    logger.info(f"正在初始化 {bot.name}")
```

这种写法具有明确的依赖关系，也更便于测试。自动依赖注入的完整规则可参阅[依赖注入与特性](./dependency_injection)。

## 查询已绑定的适配器

### 查询一个适配器

{meth}`~.Bot.get_adapter` 支持三种查询方式：协议字符串、适配器类型或过滤函数。没有匹配项时返回 `None`。

```python
from melobot.protocols.onebot.v11 import Adapter

# 按协议标识查询
adapter = bot.get_adapter("OneBot-v11@Meloland")

# 按具体适配器类型查询，类型提示会保留为 Adapter | None
adapter = bot.get_adapter(Adapter)

# 需要按运行时条件选择时使用过滤函数
adapter = bot.get_adapter(filter=lambda a: a.protocol.endswith("@Meloland"))
```

`type` 参数存在时会优先按类型或协议查询，`filter` 仅在不提供 `type` 时生效。若确实需要一组适配器，使用 {meth}`~.Bot.get_adapters`：

```python
# 获得所有已绑定适配器的一个集合副本
all_adapters = bot.get_adapters()

# 获得满足条件的集合
active_protocols = bot.get_adapters(filter=lambda a: a.protocol.startswith("OneBot"))
```

在事件处理函数中，若你想要的是**产生当前事件的适配器**，应直接将对应适配器类型声明为依赖，或读取事件的来源信息；不要按类型重新查询。后两种方式分别可获得精确类型和精确来源，详见[源与适配器](./source_adapter)。

## 运行时添加处理流

插件中的处理流会在插件就绪时自动加入 bot。对于少数确实需要动态启用功能的场景，可使用 {meth}`~.Bot.add_flows` 直接注册一个或多个 {class}`.Flow`：

```python
from melobot import Bot, on_start_match, send_text

@on_start_match(".health")
async def health_check() -> None:
    await send_text("ok")

def enable_health_check(bot: Bot) -> None:
    # health_check 此前没有交给 PluginPlanner
    bot.add_flows(health_check)
```

注册后，处理流会参与**之后收到的事件**分发；已经开始分发的事件不会回头执行新流。此接口不是线程安全的，应在单一事件循环的受控位置调用，例如启动 hook、处理流或插件就绪 hook 中。

处理流一旦无需继续工作，可以调用其 {meth}`~.Flow.dismiss` 方法停用：

```python
health_check.dismiss()
```

停用的流不再处理新事件，且不能重新启用。需要恢复同类功能时，创建并注册新的流对象。处理流的优先级、阻断传播和并发规则请参考[事件处理流与机制](./process_flow)。

## 等待事件完成分发

{meth}`~.Bot.wait_finish` 是面向适配器扩展等底层场景的异步接口。它等待一个已经交给该 bot 分发器的事件，直到所有能够处理它的流都完成，或事件不再向更低优先级传播。

```python
from melobot import Bot
from melobot.adapter import Event

async def after_dispatch(bot: Bot, event: Event) -> None:
    # 前提：event 已经被投入 bot 的分发器
    await bot.wait_finish(event)
    # 此处再执行依赖于全部处理结果的后续操作
```

通常而言，插件中的事件处理函数不要使用它：调用者本身就是待完成的处理流之一，在其中等待同一事件会造成死锁。普通业务逻辑应让处理结果沿处理流、会话或插件共享对象传递；只有自定义协议适配器等“事件提交者”才应在提交事件之后等待它结束。

## 其他查询与通信接口

{meth}`~.Bot.get_plugins` 可返回已加载插件的名称列表，{meth}`~.Bot.get_share` 可按“插件名 + 共享对象标识”取得跨插件通信对象。后者属于底层接口，动态按名称查找时很有用；常规跨插件调用仍建议使用 `mb pinit` 生成的带类型提示接口。具体示例和边界条件请参阅[共享对象的定义和基本使用](#share_object_usage)。

## 总结

bot 对象既是程序的配置入口，也是运行时组件的统一查询入口。

实践中应牢记三点：先完成协议配置再加载插件；在受控上下文中获取当前 bot；将动态业务功能组织为处理流或插件，而不是尝试在运行期修改协议组件。

下一篇将介绍：[日志组件与日志修补](./log)。
