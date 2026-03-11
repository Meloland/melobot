<!-- 
附快速提取 commit 链接的函数：
def f(s): print(f"([{s[-40:][:7]}]({s[:-33]}))")
-->

# 更新日志

## v3.4.0

### ⏩变更

- [OneBot] 旧命名 `ForwardWebSocketIO`, `ReverseWebSocketIO`, `HttpIO` 已不再推荐，现在推荐使用新名称导入：{class}`.WSClient`, {class}`.WSServer`, {class}`.HTTPDuplex`。但依然计划支持旧命名

- [core] 工具函数 {func}`.if_` 的参数 `give_up` 默认值已变为 `True`。绝大多数使用场景应该不受影响，但可以让你省略 `reject=stop` 的参数配置：

```python
from melobot.handle import stop
from melobot.utils import if_

# 过去，我们习惯使用 stop 来提前结束处理过程
@if_(..., reject=stop)
async def func() -> None: ...
# 但现在只要条件为假，则自动放弃 func 的运行，因此不再需要 reject=stop
@if_(...)
async def func() -> None: ...
```

- [core] 旧命令 `unfold_ctx` 已不再推荐，现在推荐使用新名称导入：{func}`.ctx`。但依然计划支持旧命名

- [core] 所有事件绑定函数（流装饰器）的 `rule` 参数现支持提供 {class}`.Rule` 类对象，会在内部自动运行无参实例化。但**内部只会运行一次无参实例化，保证获得的规则对象是单例**。因此**不要在多个流装饰器中使用同一个类对象，除非这是你的本意**

- [core] 现在在流上下文中运行流守卫函数，可以正常使用 {func}`.get_event` 等上下文方法。但注意**守卫函数本身仍然不支持自动依赖注入**

- [core] `melobot.log.log_exc` 已移除。请使用通用日志记录方法 {meth}`.GenericLogger.generic_exc` 方法替代

- [core] 默认不再启用流记录，需要通过 {meth}`.Flow.enable_record` 启用

### ✨新增

- [cli] 从此版本开始，melobot 安装后将会添加命令 `mb`，等价于 `python -m melobot`

- [cli] 添加了子命令 `mb init` 用于从模板创建一个新扩展，具体用法参考：`mb init --help`

- [cli] 添加了命令选项 `mb --version` 用于获取命令行工具和 melobot 的版本信息

- [OneBot] 添加了反向代理功能，具体用法参考：[OneBot 反向代理](./ob_refer/reverse-proxy)

- [core] 更多组件已可以通过顶级命名空间 `melobot` 导入，参考：[顶级命令空间](./api/index)

- [core] {class}`.PluginPlanner` 添加了生命周期方法 {meth}`~.PluginPlanner.on_inited`

- [core] 适配器类添加了生命周期方法 {meth}`~melobot.adapter.Adapter.on_before_event_handle`, {meth}`~melobot.adapter.Adapter.on_before_action_exec`, {meth}`~melobot.adapter.Adapter.on_started`, {meth}`~melobot.adapter.Adapter.on_close`, {meth}`~melobot.adapter.Adapter.on_stopped`

- [core] 源类添加了生命周期方法 {meth}`~.AbstractSource.on_started`, {meth}`~.AbstractSource.on_restarted`, {meth}`~.AbstractSource.on_close`, {meth}`~.AbstractSource.on_stopped`

- [core] 添加新的工具函数 {func}`.truncate`，用于截断字符串或字节串

- [core] 通用内容实体 {class}`.TextContent` 支持通过 {class}`.TextStyle`, {class}`.Color` 实现更精细的跨平台格式控制，但具体实现需要各种协议自行支持

- [core] 流记录阶段枚举 {class}`.FlowRecordStage` 增加了新的字段

### 👍修复

- [OneBot] 修复了提供权限检查失败回调时，权限检查有误的问题

- [core] 修复了通过命令行工具重启 bot 程序时，未妥善处理内部异常导致的资源泄露问题

- [core] 修复了设置保持会话时，事件处理结束后依然会运行会话释放的问题

- [core] 修复了修补后的第三方日志器（如 `loguru` 日志器）无法通过 {class}`.GenericLogger` 进行依赖注入的问题

### ⚙️内部

- [core] 改进版本号变更机制，现在基于 git tags 自动变更版本号

### 其他

文档勘误及不重要变更，参考完整记录：[3.3.0...3.4.0](https://github.com/Meloland/melobot/compare/3.3.0...3.4.0)

## v3.3.0

### ⏩变更

- [core] 内置日志器 {class}`~.melobot.log.Logger` 的初始化参数 `is_parellel` 已改为正确的名称 `is_parallel`，请更改代码以匹配正确的参数名

- [core] `if_not()` 由于名称与行为不匹配令人困惑，现已更名为 {func}`.if_`。原始名称依然可以用于导入，但文档中将使用新名称 {func}`.if_`，且不排除未来移除旧名称支持

- [core] {class}`.BotLifeSpan.RELOADED` 的名称令人困惑，现已更名为 {class}`.BotLifeSpan.RESTARTED`。旧名称仍可以继续使用，但不再推荐。同时建议更改 {meth}`.Bot.on_reloaded` 为 {meth}`.Bot.on_restarted`

- [core] 改进了依赖注入的实现。事件绑定函数（流装饰器）绝大多数情况下不再需要提供 `decos` 参数，与此相关的新用法请参考：[依赖注入与多层装饰](di_with_multiple_deco)

- [core] 命令解析器 {class}`.CmdParser` 的解析参数 {class}`.CmdArgs` 现提供更丰富的接口。但过去的接口依然保持兼容

- [core] 流存储对象 {class}`.FlowStore` 和会话存储对象 {class}`.SessionStore` 现支持任意可哈希对象作为键，而不是过去的仅支持字符串

- [core] 所有事件绑定函数（流装饰器）的 `block` 参数的含义发生变化。当 `block=False` 时，不再重设事件的传播状态为 `True`，而是对于传播状态不做任何修改

- [core] 移除了令人困惑、极少使用的 `CustomLogger` 依赖注入元数据标记类

- [core] 由于存在潜在问题，用于特定情景的哨兵类型 `VoidType` 已移除。请使用自定义哨兵对象替代，例如：`sentinel = object()`

- [core] {meth}`.Bot.add_flows` 方法任何时刻均可使用，无需等待特定的生命周期阶段

- [core] 处理流链接方法 {meth}`.Flow.link` 现支持为返回的新流设置自定义名称

- [core] 会话对象的 `set_completed()` 方法现已更名为 {meth}`~.Session.release`，但用法没有发生变化

### ✨新增

- [Console] 新增协议适配 `melobot.protocols.console`，请参考 [相关文档](./console_api/index)

- [core] {func}`.suspend` 方法提供新参数 `auto_stop` 用于简化以下流程：

```python
from melobot.handle import stop
from melobot.session import suspend

if not await suspend(timeout=10):
    await stop()

# 现在简化为：
await suspend(timeout=10, auto_stop=True)
```

- [core] 命令解析器 {class}`.CmdParser` 支持为参数设置自定义索引名称。但需要通过格式化器设置：

```python
from melobot.utils.parse import CmdArgFormatter, CmdParserFactory

PARSER_FACTORY = CmdParserFactory(".", " ")
TRANSLATE_CMD_PARSER = PARSER_FACTORY.get(
    targets=["translate", "trans", "翻译"],
    formatters=[
        CmdArgFormatter(
            validate=lambda x: x in ["en", "zh", "jp"],
            src_desc="翻译目标语种",
            src_expect="值为 [en, zh, jp] 其中之一",
            # 设置自定义索引名称
            key="lang",
        ),
    ],
)
```

```python
# 使用时：
lang = args["lang"]
# 当然过去的用法依然可以使用
lang = args.vals[0]
```

- [core] 命令解析器 {class}`.CmdParser` 支持交互式模式。在参数缺失时自动发出交互式询问，以尝试补全参数。但对应参数必须启用格式化器：

```python
from melobot.utils.parse import CmdArgFormatter, CmdParserFactory

PARSER_FACTORY = CmdParserFactory(".", " ")
TRANSLATE_CMD_PARSER = PARSER_FACTORY.get(
    targets=["translate", "trans", "翻译"],
    # 启用交互式功能
    interactive=True
    formatters=[
        # 设置交互式问询的超时时间
        CmdArgFormatter(..., i_timeout=30),
        ...
    ]
)

# 或在解析器初始化时提供
parser = CmdParser(..., interactive=True)
```

- [core] 新增依赖注入接口 {func}`.get_flow_arg`, {func}`.get_session_arg`, {func}`.get_cmd_arg`。它们本质上都是返回一个依赖项。因此你可以按以下方式进行使用：（关于依赖项，参考 [依赖注入文档](./dive_in/dependency_injection)）

```python
from melobot.utils.parse import get_cmd_arg

@on_xxx(...)
# lang 标注为当时存入的类型，melobot 不做限制
async def f(lang: str = get_cmd_arg("lang")) -> None:
    # 等价于首先通过注解获取 args（类型 CmdArgs）
    # 然后：lang = args["lang"]
    ...
# 或者使用 Annotated 风格的写法
async def f(lang: Annotated[str, get_cmd_arg("lang")])
# 如果你不理解这种风格的写法，请参考上面提到的依赖注入文档
```

```python
from melobot.handle import get_flow_arg

@on_xxx(...)
# arg1 标注为当时存入的类型，melobot 不做限制
async def f(arg1: str = get_flow_arg("flow_arg1")) -> None:
    # 等价于： arg1 = melobot.handle.get_flow_store()["flow_arg1"]
    ...
# 或者使用 Annotated 风格的写法
async def f(arg1: Annotated[str, get_flow_arg("flow_arg1")])
```

```python
from melobot.session import get_session_arg

@on_xxx(...)
# arg1 标注为当时存入的类型，melobot 不做限制
async def f(arg1: int = get_session_arg("s_arg_1")) -> None:
    # 等价于： arg1 = melobot.session.get_session_store()["s_arg_1"]
    ...
# 或者使用 Annotated 风格的写法
async def f(arg1: Annotated[int, get_session_arg("s_arg_1")])
```

- [core] 新增**适配器关闭前**的生命周期枚举 {class}`.AdapterLifeSpan.CLOSE`，和 **源关闭前** 的生命周期枚举 {class}`.SourceLifeSpan.CLOSE`

- [core] {meth}`.Bot.add_protocol` 方法支持传递协议栈类，内部将自动运行无参实例化

- [core] {func}`.node` 装饰器提供带参形式，可在创建处理流结点时添加常用功能

- [core] 新增方法 {meth}`.Bot.run_async`，用于在已经创建的事件循环中异步地运行 bot，仅推荐在测试环境中使用

- [core] 新增方法 {meth}`.Bot.wait_finish`，用于等待事件被 bot 所有处理流处理完成

- [core] 现在支持对 `functools.partial` 对象使用依赖注入

- [core] 处理流新增接口 {meth}`.Flow.add` 方法，{meth}`.Flow.start` 和它是等价形式，具体用法参考 [相关文档](./dive_in/process_flow)

### 👍修复

- [core] 修复了某些情景下，通过依赖注入获取适配器失败的问题 ([#43](https://github.com/Meloland/melobot/issues/43))

- [core] 修复了在 Python 3.14 下的适配问题

- [core] 修复了空日志器 {class}`.NullLogger` 在调用懒惰日志方法时的错误

- [core] 修复了在 bot 实例销毁后仍然无法创建同名 bot 的问题

- [core] 修复了加载插件时，无法正确解析部分相对路径的问题

- [core] 修复了某些可调用对象在依赖注入时的错误

- [core] 修复了会话结束时，若处理流未结束将错误设置事件状态的问题

- [core] 修复了进入子流方法 {func}`.flow_to` 对当前上下文的污染问题

- [OneBot] 修复 {class}`.MessageEvent` 返回有误 `repr` 字符串的问题

### 其他

文档勘误及不重要变更，参考完整记录：[3.2.2...3.3.0](https://github.com/Meloland/melobot/compare/3.2.2...3.3.0)

## v3.2.2

### ⏩变更

- [core] 预计于 3.2.1 版本移除的所有组件正式移除：{class}`melobot.protocols.onebot.v11.EchoRequireCtx` 和 {meth}`melobot.protocols.onebot.v11.Adapter.with_echo` ([74968a0](https://github.com/Meloland/melobot/commit/74968a0))

- [core] 现在 {meth}`~.Bot.get_adapter` 在使用类型对象获取适配器时，返回更精准的类型注解 ([3a48150](https://github.com/Meloland/melobot/commit/3a48150))

```python
from melobot.adapter import Adapter
from melobot.protocols.onebot.v11 import Adapter as ObAdapter
from typing import reveal_type

# 过往版本返回的是基类型
reveal_type(bot.get_adapter(ObAdapter)) # infer: Adapter | None
# 当前版本
reveal_type(bot.get_adapter(ObAdapter)) # infer: ObAdapter | None
```

### ✨新增

- [core] 现在所有事件对象可以通过 {meth}`~melobot.adapter.Event.get_origin_info` 获取事件来源信息对象 {class}`.EventOrigin` ([3a48150](https://github.com/Meloland/melobot/commit/3a48150))

- [core] 新增依赖注入元数据标记 {class}`.MatchEvent`，还更改了适配器依赖注入的逻辑。新逻辑及用法参考 {class}`.MatchEvent` 文档

### 👍修复

- [core] 修复了某些源对象在启动失败后，适配器会额外重复启动一次的错误 ([942ba8c](https://github.com/Meloland/melobot/commit/942ba8c))

- [core] 修复了实例方法、类方法、静态方法无法进行依赖注入的问题 ([3a48150](https://github.com/Meloland/melobot/commit/3a48150))

- [core] 修复了由流装饰器（事件绑定方法）产生的流对象拥有错误名称属性的问题 ([7a8087d](https://github.com/Meloland/melobot/commit/7a8087d))

- [core] 修复了适配器在自动确定输出源时，可能会选择非本协议的输出源的问题 ([209fe61](https://github.com/Meloland/melobot/commit/209fe61))

### ⚙️内部

- [core] 移除了针对 OneBot v12 协议的适配计划，短期内不再考虑适配 ([42a7037](https://github.com/Meloland/melobot/commit/42a7037))

### 其他

文档勘误及不重要变更，参考完整记录：[3.2.1...3.2.2](https://github.com/Meloland/melobot/compare/3.2.1...3.2.2)

### 生态新闻

- 适用于 Minecraft 服务端进程管理的 melobot 协议 [melobot_protocol_mcpm](https://github.com/aicorein/melobot-protocol-mcpm) 第一个版本已经开发完成，完成了对 vanilla/fabric 端的适配。

## v3.2.1

### ✨新增

- [core] 元信息 {class}`.MetaInfo` 新增了 `pkg_path` 属性，指向 melobot 顶级包的路径 ([1e43cbc](https://github.com/Meloland/melobot/commit/1e43cbc))

### 👍修复

- [core] 修复了 melobot 导入系统，在一些 Windows 系统版本（LTSC，Server...）上因路径字符串格式不一致导致的导入错误 ([1e43cbc](https://github.com/Meloland/melobot/commit/1e43cbc))

### 其他

文档勘误及不重要变更，参考完整记录：[3.2.0...3.2.1](https://github.com/Meloland/melobot/compare/3.2.0...3.2.1)


## v3.2.0

### ⏩变更

- [core] 各类匹配的事件绑定函数，以及一些检查器、插件相关接口，现在入参类型更为宽松，不再要求 `list` 类型 ([312ecf4](https://github.com/Meloland/melobot/commit/312ecf4), [64deea9](https://github.com/Meloland/melobot/commit/64deea9))

- [core] 命令解析器 {class}`.CmdParser` 现在使用 `strict` 参数控制是否严格解析。严格意为不去除文本两侧的空白文本，默认不启用。此外命令解析器现在认为：如果字符串不以命令起始符起始，那么永远不应该有解析结果，即解析得到 `None` 值。这可避免“误触发”命令的情景 ([312ecf4](https://github.com/Meloland/melobot/commit/312ecf4))

- [core] 基于日志器上下文的日志器设置、获取机制，及混合类 `LogMixin` 已移除。现在推荐使用基于“域”的日志器设置、获取方式。参考：[新版日志机制](./api/melobot.log) ([fb54633](https://github.com/Meloland/melobot/commit/fb54633))

- [core] 修复了 melobot 导入系统的错误，并引入导入回退机制 {func}`.add_import_fallback` ([fe23c85](https://github.com/Meloland/melobot/commit/fe23c85))

- [OneBot] {class}`.EchoRequireCtx` 和 {meth}`~.onebot.v11.Adapter.with_echo` 已弃用，将于 3.2.1 移除。现在不再需要手动声明即可等待回应，而且没有额外的性能成本 ([c3f6c38](https://github.com/Meloland/melobot/commit/c3f6c38))

- [core] 行为操作句柄相关的接口已经发生改变，所有返回行为操作句柄元组的接口，现在改为返回 {class}`.ActionHandleGroup` 对象。但这与过去的接口完全兼容，更多用法参考：[行为操作](./intro/action-echo) ([7006bac](https://github.com/Meloland/melobot/commit/7006bac))

- [core] {class}`.LogicMode` 的相关运算方法过于冗杂，已全部移除。但现在提供一个获取运算逻辑的方法 {meth}`~.LogicMode.get_operator` ([d08ddae](https://github.com/Meloland/melobot/commit/d08ddae))

- [core] 内置日志实现 {class}`~melobot.log.Logger` 改进了日志渲染过程，对应模块加载时间可缩短 90% ([725f116](https://github.com/Meloland/melobot/commit/725f116))

- [core] 对核心模块使用惰性加载，显著提高了顶级模块的导入速度，约减少 0.5-1.5s ([0f9a070](https://github.com/Meloland/melobot/commit/0f9a070))

- [core,OneBot] 优化了事件分发的效率，及事件处理流的执行效率，处理流普遍提速 1 倍左右。在 OneBot 协议支持的特定情景中，二次执行甚至可以快 1.5-2.5 倍 ([d08ddae](https://github.com/Meloland/melobot/commit/d08ddae), [5fe5021](https://github.com/Meloland/melobot/commit/5fe5021))

- [core] 改进了 hook 过程和依赖注入过程的性能，某一 200-300ns 的固定操作用时现在已被优化，目前这一操作耗时是原来的 1% ([739f18a](https://github.com/Meloland/melobot/commit/739f18a))

- [core] 在版本 `>=3.12` 的 python 解释器上，现在拥有更快的异步任务执行速度 ([6635326](https://github.com/Meloland/melobot/commit/6635326))

### ✨新增

- [core] 在大多数支持绑定 hook 的对象上（bot, adapter, source 等），现在支持 {meth}`~.HookMixin.get_hook_evoke_time` 方法。支持获取某一 hook 最后触发的时间戳 ([0a9c20a](https://github.com/Meloland/melobot/commit/0a9c20a))

- [core] 现在导入 melobot 会安装默认的异常回溯栈的格式化器，相关接口参考：{func}`.install_exc_hook`, {func}`.uninstall_exc_hook`, {func}`.set_traceback_style` ([725f116](https://github.com/Meloland/melobot/commit/725f116))

- [core] 在所有支持的 python 版本上，现在提供安全、便捷的多进程相关 API，参考：[melobot.mp](./api/melobot.mp) ([1a15175](https://github.com/Meloland/melobot/commit/1a15175))

- [core] 为内置日志实现 {class}`~melobot.log.Logger` 添加多进程并行渲染支持。在 `DEBUG` 日志级别实测下，日志格式化造成的阻塞已大大缓解。处理每事件的周转时间平均减少 1-2ms ([1b63382](https://github.com/Meloland/melobot/commit/1b63382))

- [core] 添加了通用的惰性导入支持，参考：{func}`.lazy_load` ([834eda8](https://github.com/Meloland/melobot/commit/834eda8))

- [core] 为插件目录内的模块添加自动导入机制。通过插件管理器 {class}`.PluginPlanner` 的 `auto_import` 参数实现。本特性的加入，将有利于其他组合式 API 的广泛使用 ([de4acb7](https://github.com/Meloland/melobot/commit/de4acb7))

- [core] 事件处理流 {class}`.Flow` 现在支持依赖反转式的声明，依靠相关装饰器或装饰器函数 API 的实现。包括：{meth}`~.Flow.start`, {meth}`~.Flow.before`, {meth}`~.Flow.after`, {meth}`~.Flow.merge`, {meth}`~.Flow.fork`。它们都是组合式 API 的一部分 ([c28f289](https://github.com/Meloland/melobot/commit/c28f289))

- [core] 事件处理流 {class}`.Flow` 新增 `guard` 初始化参数，也可通过 {meth}`~.Flow.set_guard` 重设这一参数 ([d08ddae](https://github.com/Meloland/melobot/commit/d08ddae), [c28f289](https://github.com/Meloland/melobot/commit/c28f289))

### 👍修复

- [core] {func}`.on_regex_match` 函数拥有错误参数 `logic_mode` 的问题已修复，已替换为正确的参数 `regex_flags` ([d08ddae](https://github.com/Meloland/melobot/commit/d08ddae))

- [core] 现在尝试为插件添加一个不在本插件目录内定义的共享对象或导出函数，将会发出详细的异常而不是 `IndexError` ([aff5438](https://github.com/Meloland/melobot/commit/aff5438))

- [core] 核心模块现在使用更安全、可靠的启动机制，内部异常处理方式得到了改进。此外 bot 程序现在已能正常响应中断和终止信号 ([6429bf8](https://github.com/Meloland/melobot/commit/6429bf8))

- [cli] 命令行界面的 `dev`, `run` 命令现在使用更安全的启动方式，且可以正常响应中断和终止信号 ([6429bf8](https://github.com/Meloland/melobot/commit/6429bf8))

- [OneBot] 部分事件错误地生成 repr 字符串的问题已得到修复 ([41ae0c1](https://github.com/Meloland/melobot/commit/41ae0c1))

### ⚙️内部

- [core] 开发与 CI 流程不再使用 `pdm`，全面转向 `uv` ([d5d6c15](https://github.com/Meloland/melobot/commit/d5d6c15))

- [core] 添加了三方代码使用的许可证，并按要求随源代码进行分发。参考：[THIRD-PARTY-NOTICES](https://github.com/Meloland/melobot/blob/main/THIRD-PARTY-NOTICES.md) ([dd5b242](https://github.com/Meloland/melobot/commit/dd5b242))

### 其他

其他文档勘误及非阶段性变更，请参考完整记录：[3.1.3...3.2.0](https://github.com/Meloland/melobot/compare/3.1.3...3.2.0)


## v3.1.3

### ⏩变更

- [core] 内部分发过程，现在提供更清晰的调试日志 ([f3178fc](https://github.com/Meloland/melobot/commit/f3178fc), [50d7449](https://github.com/Meloland/melobot/commit/50d7449))

- [core] 插件管理器初始化时的 {class}`.PluginInfo` 对象，现在不再需要 `version` 参数。插件版本由 {class}`.PluginPlanner` 初始化的第一参数唯一确定 ([03ad408](https://github.com/Meloland/melobot/commit/03ad408))

### ✨新增

- [core] 新增上下文动态变量，可以在合适的场景中 import 它们来使用，免去调用 `get_xxx()` 方法的麻烦 ([89e4e1f](https://github.com/Meloland/melobot/commit/89e4e1f))。**但注意 import 时，上下文中必须已经存在对应类型的对象**。新增的变量有：{data}`~melobot.bot.bot`, {data}`~melobot.handle.f_records`, {data}`~melobot.handle.f_store`, {data}`~melobot.handle.event`, {data}`~melobot.session.session`, {data}`~melobot.session.s_store`, {data}`~melobot.session.rule`, {data}`~melobot.log.logger`

- [core] 插件初始化现在可以把插件版本、插件作者等元信息，自动生成到 `__init__.py` 中。此外插件目录模块现在拥有 `__plugin_info__` 属性，可返回插件管理器中的 {class}`.PluginInfo` 对象 ([03ad408](https://github.com/Meloland/melobot/commit/03ad408))

### 👍修复

- [core] 改进了调试日志中，事件循环策略对象打印的方式。现在更加直观清晰 ([e78dbcc](https://github.com/Meloland/melobot/commit/e78dbcc))

- [core] 加载插件时，如果插件目录不存在，现在显示合理的错误提示信息 ([adc43b0](https://github.com/Meloland/melobot/commit/adc43b0))

- [core] 修复了会话的“自动完成”功能，现在已按预期工作 ([0e23432](https://github.com/Meloland/melobot/commit/0e23432))

- [core] 修复了 {func}`.singleton` 函数在装饰类时，类型注解丢失的问题 ([245b14a](https://github.com/Meloland/melobot/commit/245b14a))

- [OneBot] 修复了 {class}`~.v11.adapter.echo.GetForwardMsgEcho` 的类型注解 ([dbf0de4](https://github.com/Meloland/melobot/commit/dbf0de4))

## v3.1.2

### ⏩变更

- [core] 移除所有原本预计在 `3.1.1` 版本移除的组件 ([4b14ed5](https://github.com/Meloland/melobot/commit/4b14ed5))

- [core] 内置日志器现在启用 `two_stream`，warning 级别的日志也将被分流到 `xxxxx.err.log` 中 ([8a2f1d7](https://github.com/Meloland/melobot/commit/8a2f1d7))

- [core] 更新了插件共享对象获取的逻辑，无需更新任何代码。但新的插件初始化过程生成的 `__init__.py` 将采用新的运行逻辑 ([a207f27](https://github.com/Meloland/melobot/commit/a207f27))

- [OneBot] 现在 {class}`~.v11.io.HttpIO` 的初始化参数 `onebot_host` 和 `onebot_port` 已移除，改为使用 `onebot_url`。这有利于更自由的提供 http 服务的 url ([5a2cbb6](https://github.com/Meloland/melobot/commit/5a2cbb6))

### 👍修复

- [OneBot] 修复创建自定义消息段类型的方法 {meth}`~.Segment.add_type` 的类型注解问题，并更新了相关文档 ([e2175d1](https://github.com/Meloland/melobot/commit/e2175d1))。无需更新任何代码。文档被更新处：[自定义消息段的构造](https://docs.melobot.org/intro/msg-action.html#id3)

- [Docs] 文档笔误修复 ([23076b8](https://github.com/Meloland/melobot/commit/23076b8), [b37874e](https://github.com/Meloland/melobot/commit/b37874e))

### ⚙️内部

- [core] 开发项目时不再使用 pylint 监测代码质量 ([1b49dfb](https://github.com/Meloland/melobot/commit/1b49dfb))

## v3.1.1

### ⏩变更

- [OneBot] 所有消息段内的 str 类型参数，现在不再进行除类型判断以外的校验。现在你必须自行验证这些字符串是否非空，以及是否符合特定格式（例如 url 格式）([f6b5a56](https://github.com/Meloland/melobot/commit/f6b5a56))

### 👍修复

- [core] 异常日志过于冗杂，且输出过多敏感信息 ([0154d2e](https://github.com/Meloland/melobot/commit/0154d2e))

- [OneBot] 部分消息段的初始化失败问题、{meth}`~.v11.adapter.segment.Segment.to_dict` 或 {meth}`~.v11.adapter.segment.Segment.to_json` 转换失败问题 ([#36](https://github.com/Meloland/melobot/issues/36) -> [f6b5a56](https://github.com/Meloland/melobot/commit/f6b5a56))

## v3.1.0

### ⏩变更

- [core] 改进了内部事件分发机制，现在所有情况下的事件处理都不再阻塞分发。原始的处理流优先级枚举 `HandleLevel` 已移除，现在通过 int 值定义优先级，默认处理流优先级为 0 ([e2aaa72](https://github.com/Meloland/melobot/commit/e2aaa72))

- [core] {func}`.async_later` 和 {func}`.async_at` 现在返回 {external:class}`~asyncio.Task` 而不是 {external:class}`~asyncio.Future` ([3b7bea2](https://github.com/Meloland/melobot/commit/3b7bea2))

- [core] 现在插件的 {attr}`.PluginLifeSpan.INITED` 生命周期钩子结束前，该插件所有处理流不会生效。避免通过此钩子运行异步初始化，初始化未完成处理流就先启动的不合理现象。如果需要避免额外的等待，请在钩子函数内使用 {external:func}`~asyncio.create_task` ([ca06a05](https://github.com/Meloland/melobot/commit/ca06a05))

- [All] 绝大多数只支持 {class}`.AsyncCallable` 参数的接口，现在变更为支持 {class}`.SyncOrAsyncCallable`，参数可接受同步或异步的可调用对象 ([b6c7f24](https://github.com/Meloland/melobot/commit/b6c7f24))

- [All] 为避免依赖注入出现问题，现在不能在 `on_xxx` 函数下方使用装饰器 ([9ba2265](https://github.com/Meloland/melobot/commit/9ba2265))，必须通过 `decos` 参数：

```python
# 现在不能再使用以下形式：
@on_xxx(...)
@aaa(...)
@bbb(...)
async def _(): ...

# 需要换为：
@on_xxx(..., decos=[aaa(...), bbb(...)])
async def _(): ...
```

- [OneBot] 移除了有严重问题而无法修复的 `msg_session` 函数 ([1a372de](https://github.com/Meloland/melobot/commit/1a372de))，推荐使用 {class}`.DefaultRule` 或 `legacy_session` 参数或 `rule` 参数替代：

```python
# 原始用法
with msg_session(): ...

# 现在的替代方法：

_RULE = DefaultRule()
# 注意不要直接在 enter_session 中初始化
# 这样会导致每次生成一个新的 rule
with enter_session(_RULE): ...

# 或者

# 对于 on_xxx 接口，如有 legacy_session 参数，
# 置为 True 实现类似 msg_session 效果
@on_xxx(..., legacy_session=True)
async def _():
    # 注意进入会话在所有 decos 装饰器之前
    # 如果这个顺序不符合你的需求，还是建议在 decos 中使用 unfold_ctx(enter_session(...))
    ...

# 或者

class MyRule(Rule): ...
# 对于 on_xxx 接口，如有 rule 参数
# 可以直接在这里初始化规则，并提供
@on_xxx(..., rule=MyRule())
async def _():
    # 注意进入会话在所有 decos 装饰器之前
    ...
```

- [OneBot] 部分 api 已并入 melobot core。尝试按原样导入并使用这些 api 依然可以工作，但会发出弃用警告。兼容原样导入的行为将在 `3.1.1` 移除 ([841eddd](https://github.com/Meloland/melobot/commit/841eddd))，请及时迁移。我们强烈建议您重新阅读一遍 [相关使用方法](./intro/event-preprocess) 来了解**新 api 的使用技巧**。以下是变动的 api：

```shell
# 原始位置 (onebot 模块是 melobot.protocols.onebot) -> 新位置
onebot.v11.utils.Checker           ->  melobot.utils.check.Checker

onebot.v11.utils.Matcher           ->  melobot.utils.match.Matcher
onebot.v11.utils.StartMatcher      ->  melobot.utils.match.StartMatcher
onebot.v11.utils.ContainMatcher    ->  melobot.utils.match.ContainMatcher
onebot.v11.utils.EndMatcher        ->  melobot.utils.match.EndMatcher
onebot.v11.utils.FullMatcher       ->  melobot.utils.match.FullMatcher
onebot.v11.utils.RegexMatcher      ->  melobot.utils.match.RegexMatcher

onebot.v11.utils.Parser            ->  melobot.utils.parse.Parser
onebot.v11.utils.ParseArgs         ->  melobot.utils.parse.CmdArgs
onebot.v11.utils.CmdParser         ->  melobot.utils.parse.CmdParser
onebot.v11.utils.CmdParserFactory  ->  melobot.utils.parse.CmdParserFactory
onebot.v11.utils.CmdArgFormatter   ->  melobot.utils.parse.CmdArgFormatter
onebot.v11.utils.FormatInfo        ->  melobot.utils.parse.CmdArgFormatInfo

onebot.v11.handle.on_start_match   ->  melobot.handle.on_start_match
onebot.v11.handle.on_contain_match ->  melobot.handle.on_contain_match
onebot.v11.handle.on_end_match     ->  melobot.handle.on_end_match
onebot.v11.handle.on_full_match    ->  melobot.handle.on_full_match
onebot.v11.handle.on_regex_match   ->  melobot.handle.on_regex_match
onebot.v11.handle.on_command       ->  melobot.handle.on_command

# 特别注意，此 api 原本用作默认值，表示需要一个解析参数。但现在只需要注解类型即可
# 但此 api 依然可以使用，但下一版本直接删除，在整个项目中将完全不存在
onebot.v11.handle.GetParseArgs     ->  melobot.handle.GetParseArgs
```

- [OneBot] 除以上变更的 api 外，其余 onebot 协议支持部分的公开接口可以从 `melobot.protocols.onebot.v11` 直接导入 ([e2aaa72](https://github.com/Meloland/melobot/commit/e2aaa72))

### ✨ 新增

- [core] {class}`.Rule` 现在支持两种抽象方法 {meth}`~.Rule.compare` 与 {meth}`~.Rule.compare_with` （提供更有用的对比信息），二选一实现即可 ([ef173c6](https://github.com/Meloland/melobot/commit/ef173c6))

- [core] {class}`.SessionStore` 现在可以使用 set 方法设置值，方便链式调用 ([36b555e](https://github.com/Meloland/melobot/commit/36b555e))

```python
# 等价于 store[key] = value
store.set(key, value)
```

- [core] 现在会话可以被直接依赖注入，或在当前上下文通过 {func}`.get_session` 获取 ([e2aaa72](https://github.com/Meloland/melobot/commit/e2aaa72))。例如：

```python
from melobot.session import Session, get_session

@on_xxx(...)
async def _(session: Session, ...): ...

# 或者

@on_xxx(...)
async def _(...):
    # 获取当前上下文中的会话对象
    session = get_session()
```

- [core] 新增接口兼容装饰器函数 {func}`.to_sync`，非常不常用。极少数需要兼容同步接口时使用 ([ca06a05](https://github.com/Meloland/melobot/commit/ca06a05))

- [core] {func}`.if_not` 现在支持新参数 `accept`，作为条件为真时执行的回调 ([d89d62e](https://github.com/Meloland/melobot/commit/d89d62e))

- [core] 新增了跨协议的 `on_xxx` 方法：{func}`~.melobot.handle.on_event`（用于绑定任意协议的任意事件处理方法） 和 {func}`~.melobot.handle.on_text`（用于绑定任意文本事件处理方法）([841eddd](https://github.com/Meloland/melobot/commit/841eddd))

- [core] 现在 {class}`.CmdParser` 支持初始化参数 `tag` ([a7a183e](https://github.com/Meloland/melobot/commit/a7a183e), [9fdde3b](https://github.com/Meloland/melobot/commit/9fdde3b))，该值会传递给解析参数，用于标识：

```python
parser = CmdParser(cmd_start=".", cmd_sep=" ", targets=["echo", "回显"], tag="bar")
args = await parser.parse(".回显 hi")
if args is not None:
    assert args.name == "回显"
    assert args.tag == "bar"

# 不指定 tag 时，自动设置为 targets 第一元素，或 targets 本身（如果为字符串）
parser = CmdParser(cmd_start=".", cmd_sep=" ", targets=["echo", "回显"])
args = await parser.parse(".回显 你好呀")
if args is not None:
    assert args.name == "回显"
    assert args.tag == "echo"
```

- [core] 新增了用于合并检查器序列的函数 {func}`.checker_join`。相比于使用 | & ^ ~ 运算符，此函数可以接受检查器序列，并返回一个合并检查器。检查器序列可以为检查器对象，检查函数或空值 ([841eddd](https://github.com/Meloland/melobot/commit/841eddd))

- [core] 现在支持动态增加、删除处理流，以及变更处理流的优先级 ([e2aaa72](https://github.com/Meloland/melobot/commit/e2aaa72))。例如：

```python
# 在 BotLifeSpan.STARTED 生命周期之后，可以动态的增加处理流：
bot.add_flows(...)

# 在任何时候拿到处理流对象后，可以移除该处理流
# 如果在某处理流内部移除此处理流，依然不影响本次处理过程
flow.dismiss()

# 在任何时候拿到处理流对象后，可以更新优先级
# 如果在某处理流内部更新此处理流优先级，依然不影响本次处理过程
flow.update_priority(priority=3)
```

- [core] 新增了一些 mixin 类，主要提供给协议支持的开发者，参考文档中的 [melobot.mixin](./api/melobot.mixin) 部分。插件与 bot 开发者无需关心 ([e2aaa72](https://github.com/Meloland/melobot/commit/e2aaa72), [6f8253e](https://github.com/Meloland/melobot/commit/6f8253e))

- [All] 多数 `on_xxx` 接口提供了新参数 `rule`，用于在内部自动展开会话 ([52a1e7b](https://github.com/Meloland/melobot/commit/52a1e7b))。先前已有示例，此处不再演示。

- [OneBot] 新增 {func}`.get_group_role` 和 {func}`.get_level_role` 用于获取权限等级 ([65d447e](https://github.com/Meloland/melobot/commit/65d447e))

- [OneBot] 新增 {class}`.OneBotV11Protocol` 协议栈对象，启动代码现在更为简洁 ([6f8253e](https://github.com/Meloland/melobot/commit/6f8253e))，例如：

```python
from melobot import Bot
from melobot.protocols.onebot.v11 import ForwardWebSocketIO, OneBotV11Protocol

bot = Bot()
# 无需再手动添加适配器
bot.add_protocol(OneBotV11Protocol(ForwardWebSocketIO(...)))
bot.load_plugin(...)
...
bot.run()
```

### 👍修复

- [core] 通过依赖注入获取适配器时，返回值可能为空的错误 ([1c7d170](https://github.com/Meloland/melobot/commit/1c7d170))

- [core] 更改部分内置数据结构为集合，避免重复添加元素导致未定义行为 ([7ec9709](https://github.com/Meloland/melobot/commit/7ec9709))

- [All] 小幅度提升异步任务创建的性能，修复一些异步任务序列为空可能导致的错误，以及更好的异常提示 ([33c1c68](https://github.com/Meloland/melobot/commit/33c1c68))

- [OneBot] 优化了 event, action 和 echo 对象的 repr 显示。在调试时或错误日志中，repr 不再显示为超长字符串 ([33c1c68](https://github.com/Meloland/melobot/commit/33c1c68))

- [OneBot] 现在使用更安全的校验。意外传递反射依赖项到 checker 不再会导致校验默认通过 ([dcf782f](https://github.com/Meloland/melobot/commit/dcf782f))

- [OneBot] 小幅度提升了 event 与 echo 验证错误时的回调的执行性能 ([4af5422](https://github.com/Meloland/melobot/commit/4af5422))


## v3.0.0

### ⚠️特别：

- **melobot v3 是跨平台、跨协议、支持多路 IO 及其他高级特性的 bot 开发框架，与 v2 完全不兼容。** 

- v3 文档教程：[melobot docs](https://docs.melobot.org)

| 特色           | 描述                                                         |
| -------------- | ------------------------------------------------------------ |
| 实用接口       | 封装高频使用的异步逻辑，使业务开发更简洁                     |
| 插件管理       | 低耦合度、无序的插件加载与通信                               |
| 处理流设计     | 可自由组合“处理中间件”为处理流，提升了各组件的复用率         |
| 热插拔/重启    | 处理流支持动态热插拔，支持 bot 级别的重启                   |
| 会话支持       | 可在处理流中自动传递的、可自定义的会话上下文                 |
| 协议支持       | 所有协议被描述为 IO 过程，因此支持各类协议                   |
| 跨平台         | 更简洁的跨平台接口，便捷实现跨平台插件开发                   |
| 跨协议 IO      | 支持多个协议实现端同时输入，自由输出到指定协议实现端         |
| 日志支持       | 日志记录兼容标准库和绝大多数日志框架，可自行选择             |

对比上一预发布版本 `3.0.0rc21`，主要有：

### ⏩变更

- [core] 移除计划移除的 api 和组件（移除了方法 `Args`, `Context.in_ctx` 与传统插件类 `Plugin`）([ec518f5](https://github.com/Meloland/melobot/commit/ec518f5))

- [core] 改进了 io 层的 packet 限制，现在所有 packet 不再是 `frozen` 的 ([88eeb85](https://github.com/Meloland/melobot/commit/88eeb85))

- [core] 改进了 adapter 层的组件，现在钩子 `BEFORE_EVENT` 重命名为 `BEFORE_EVENT_CREATE`，钩子 `BEFORE_ACTION` 重命名为 `BEFORE_ACTION_EXEC` ([d50d3a3](https://github.com/Meloland/melobot/commit/d50d3a3))

### ✨ 新增

- [core] 内置日志器添加 `yellow_warn` 参数，可在智能着色模式下强制警告消息为醒目的黄色 ([0dae81d](https://github.com/Meloland/melobot/commit/0dae81d))

- [core] 现在使用 {class}`.PluginPlanner` 声明插件及各种插件功能 ([4508081](https://github.com/Meloland/melobot/commit/4508081))

- [core] {class}`.PluginPlanner` 现在支持使用 {meth}`~.PluginPlanner.use` 装饰器来收集各种插件组件（处理流、共享对象与导出函数）([ecec685](https://github.com/Meloland/melobot/commit/ecec685))

- [OneBot] 添加了用于处理 OneBot v11 实体（事件、动作与回应）数据模型验证异常的 OneBot v11 适配器接口 {meth}`~.protocols.onebot.v11.adapter.base.Adapter.when_validate_error` ([4bddb6a](https://github.com/Meloland/melobot/commit/4bddb6a), [0589f3a](https://github.com/Meloland/melobot/commit/0589f3a), [a4d35b3](https://github.com/Meloland/melobot/commit/a4d35b3))

### 👍修复

- [OneBot] 自定义消息段类型创建和解析 ([3026543](https://github.com/Meloland/melobot/commit/3026543), [51f7cbe](https://github.com/Meloland/melobot/commit/51f7cbe), [f006ee0](https://github.com/Meloland/melobot/commit/f006ee0), [819489f](https://github.com/Meloland/melobot/commit/819489f))

- [OneBot] 正向 websocket IO 源忽略 bot 停止信号 ([da0e3df](https://github.com/Meloland/melobot/commit/da0e3df))

- [All] 项目各处类型注解的改进 ([1bd8760](https://github.com/Meloland/melobot/commit/1bd8760))

- [All] 文档与内置异常提示更正

### ♥️新贡献者

* [@Asankilp](https://github.com/Asankilp) 首次提交 [#14](https://github.com/Meloland/melobot/pull/14)

* [@NingmengLemon](https://github.com/NingmengLemon) 首次提交 [#15](https://github.com/Meloland/melobot/pull/15)
