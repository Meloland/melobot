# bot 生命周期

典型的 bot 程序的生命周期如下所示：

```{image} /_static/lifetime.png
:alt: lifetime
:width: 250px
:align: center
```

1. 注入自定义机制：`import melobot` 发生时，会注入 melobot 自定义的导入机制与多进程生成机制，用于一些内部功能的实现。**多数情况不会对用户代码造成影响**。
2. 创建 bot：在实例化 {class}`.Bot` 对象后，即创建了 bot 对象（bot 实例）。
3. 添加源与适配器（或协议栈）：这些组件添加后并不会立即启动，但它们已作为对象存在。
4. 添加插件：开始加载插件，并把插件中的功能扩展到 bot 实例上。
5. 启动 bot：开始运行各项功能。
6. bot 运行期：运行各类功能，执行各类协议组件与用户插件的功能。
6. 停止 bot：停止各项功能，并进行资源清理。

## bot 启停阶段

启动 bot 的过程在时序上如图所示：

```{image} /_static/bot-start.png
:alt: lifetime
:width: 400px
:align: center
```

为了简化逻辑，图中的调用关系为同步，实际上全是异步过程。

1. 简单来说，一个 bot 实例在启动时，会尝试异步地启动其上添加的所有适配器。
2. 每个适配器启动时，会尝试异步地启动同协议的所有源。
3. 同一协议的所有源，都启动完成并开始工作后，适配器也就启动完成并开始工作。
4. 如此递归直至所有源与适配器都启动完毕，bot 实例也就可以开始工作

停止 bot 的过程在时序上正好相反：

1. bot 实例的停止可以由 close 方法或终止信号（SIGINT，SIGTERM）触发
2. 停止时的顺序，正好与启动时相反，就像“栈”一样

假设有以下启动过程：

```text
bot 启动
    A 的适配器启动
        A 的源 A1 启动
        A1 开始工作
    A 的适配器开始工作
    B 的适配器启动
        B 的源 B1 启动
        B1 开始工作
        B 的源 B2 启动
        B2 开始工作
    B 的适配器开始工作
bot 开始工作
```

那么停止时的顺序为：

```
bot 准备停止
    B 的适配器准备停止
        源 B2 准备停止
        源 B2 结束工作
        源 B1 准备停止
        源 B1 结束工作
    B 结束工作
    A 的适配器准备停止
        源 A1 准备停止
        源 A1 结束工作
    A 结束工作
bot 结束工作
```


```{admonition} 警告
:class: attention
大多数情况下，外部应该使用 bot 实例提供的接口，来顺便完成对适配器、源的启动。直接调用适配器、源的启停方法将发生未定义行为。

但不排除部分适配器或源有重启实现，这种情况下可以手动启停。不过具体用法要以文档说明为准。
```


## 生命周期钩子

bot，适配器，源对象都可以在指定的生命周期添加生命周期钩子。这一般也称作添加 hook。在对象抵达对应的生命周期结点后，便会执行你添加的钩子函数。

对于 bot 实例，有以下方法获取：

```python
# 创建 bot 时可以拿到对象
bot = Bot(...)

# 或者在插件中获取当前上下文的 bot
from melobot.bot import get_bot
bot = get_bot()

# 当然依赖注入也是可以的
@on_xxx(...)
async def _(bot: Bot) -> None: ...
```

所有源对象和适配器对象都是可 hook 的。使用 {meth}`~.HookMixin.on` 方法，配合 {class}`.BotLifeSpan` 可以绑定一个 hook 函数：

```python
async def f1() -> None: ...
def f2() -> None: ...

from melobot.bot import BotLifeSpan
# 直接使用
bot.on(BotLifeSpan.LOADED)(f1)

# 或取得装饰器
on_my_bot_loaded = bot.on(BotLifeSpan.LOADED)
on_my_bot_loaded(f1)
on_my_bot_loaded(f2)

# 或直接使用装饰器语法
@bot.on(BotLifeSpan.LOADED)
async def f3() -> None: ...
```

各种 hook 类型的含义，参考 {class}`.BotLifeSpan` 的 API 文档。

实际上，bot 对象还有专属的语法糖：

```python
# 使用属性，绑定在 LOADED 生命周期的 hook
@bot.on_loaded
async def _() -> None: ...
# 其他 hook 类型类似
```

所有可 hook 对象，可以使用 {meth}`~melobot.mixin.HookMixin.get_hook_evoke_time` 获取最后一次触发 hook 的时间戳：

```python
# 例如 bot 对象在任何时候都可以尝试：
bot.get_hook_evoke_time(BotLifeSpan.STARTED)
# 如果尚未抵达此生命周期，返回 -1
# 如果抵达并触发过所有 hook，那么会返回一个时间戳值
```

其他组件的生命周期钩子，会在后续章节穿插讲解。


## 总结

本篇主要说明了 melobot 重要组件的生命周期与钩子。

下一篇将重点说明：源与适配器。
