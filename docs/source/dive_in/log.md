# 日志组件与日志修补

日志往往在程序出问题时才被认真对待，但对异步 bot 而言，它也是观察并发处理、协议连接与插件运行状态的主要窗口。melobot 的日志系统并不要求所有代码共用同一个日志器；它根据**记录发生的位置**和**当前 bot 上下文**，在运行时选择真正接收日志的对象。

本文会说明这套选择规则、通用日志接口，以及如何接入标准库和常见的第三方日志器。

## 日志器是如何被选择的

在业务模块中，通常只需导入动态日志代理并直接使用：

```python
from melobot.log import logger

logger.info("天气插件已加载")
```

这里的 `logger` 并非某个固定的全局实例，而是一个与**导入位置所在文件**关联的代理对象。每次记录日志时，代理都会按以下顺序解析实际日志器：

| 顺序 | 日志域 | 何时使用 |
| --- | --- | --- |
| 1 | 模块域 | 当前文件或其父目录/父包配置了日志器 |
| 2 | bot 域 | 上述没有可用日志器，当前处于 bot 上下文，且该 bot 初始化时提供了 `logger` |
| 3 | 顶级域 | 上述两者都没有可用日志器 |
| 4 | 丢弃 | 顶级域也被设为 `None`，此时丢弃日志 |

模块域按文件路径形成一棵树。假设调用代码位于 `plugins/weather/handlers.py`，系统会先找该文件对应结点的日志器；没有则向 `plugins/weather`、`plugins` 乃至更高层目录逐级查找。找到的第一个日志器便会生效，因此更具体的配置会覆盖更宽泛的配置。

### 配置三个日志域

顶级域是整个进程的最终兜底。melobot 默认已经为它配置了 `Logger("[global]")`，所以不做任何设置时也能看到框架日志。主入口可以按需替换它：

```python
from melobot.log import Logger, LogLevel, set_global_logger

set_global_logger(Logger("app", level=LogLevel.INFO, to_dir="logs"))
```

bot 域由创建 {class}`.Bot` 时的 `logger` 参数设置：

```python
from melobot import Bot
from melobot.log import Logger, LogLevel

bot = Bot("bot_a", logger=Logger("bot_a", level=LogLevel.INFO))
```

只要日志调用点没有模块域配置，在 `bot` 的处理流中调用 `logger.info(...)` 就会落到 bot 域的日志器上。

模块域使用 {func}`.set_module_logger` 设置。第一个参数可以是可导入的模块名、模块对象，或一个存在的文件/目录路径：

```python
from melobot.log import Logger, LogLevel, NullLogger, set_module_logger

# 为 melobot 自身及其子模块设置较详细的日志
set_module_logger("melobot", Logger("framework", level=LogLevel.DEBUG))

# 为本地插件目录及其后代设置单独日志器
set_module_logger("./plugins", Logger("plugins", to_dir="logs"))

# 精确屏蔽一个噪声较大的模块
set_module_logger("melobot.bot.dispatch", NullLogger())
```

```{admonition} None 与 NullLogger 不同
:class: warning
将某个模块域设为 `None` 表示“这里没有配置”，解析仍会继续向父模块、bot 域和顶级域回退。若要明确屏蔽此模块及其后代的日志，应设置 {class}`.NullLogger`；它是一个真正的空日志器，会终止向上查找并丢弃所有记录。
```

域配置会影响整个进程，适合放在主入口或统一的日志配置模块中。插件和工具模块应当只取得 `logger` 并记录日志，不应擅自修改顶级域或其他模块的域配置。

{func}`.get_logger` 与导入 {data}`~melobot.log.logger` 的效果相同。绝大多数情况下推荐后者：它可以在模块顶层导入一次，代理仍会在每次调用时重新依据当前 bot 上下文选择日志器。

## 通用日志接口

{class}`.GenericLogger` 是 melobot 对日志器的最小抽象。bot 的 `logger` 参数、模块域和顶级域都接受符合这个接口的对象。它包含两类方法：

| 方法 | 用途 |
| --- | --- |
| `debug`、`info`、`warning`、`error`、`critical` | 记录普通消息 |
| `exception` | 在 `except` 块中记录消息与当前异常栈 |
| `generic_lazy` | 仅在需要输出时计算较昂贵的消息参数 |
| `generic_obj` | 记录消息以及一个对象的可读表示 |
| `generic_exc` | 记录当前异常，并附带相关对象 |

普通消息可以直接使用 f-string：

```python
logger.info(f"已连接到上游，账号：{self_id}")

try:
    await request_api()
except Exception:
    logger.exception("请求上游接口失败")
```

若生成消息参数本身很昂贵，例如序列化大型事件或计算诊断信息，应使用 {meth}`~.GenericLogger.generic_lazy`。它使用 `%s` 占位符，而每个参数由一个无参函数提供：

```python
from melobot.log import LogLevel, logger

logger.generic_lazy(
    "收到事件 %s，完整内容：%s",
    lambda: event.id,
    lambda: serialize_event_for_debug(event),
    level=LogLevel.DEBUG,
)
```

此方法会先检查目标等级是否开启，再调用这些函数；因此在生产环境关闭 `DEBUG` 后，`serialize_event_for_debug` 不会执行。

{meth}`~.GenericLogger.generic_obj` 适合在诊断信息中输出结构化对象；内置日志器会使用 Rich 进行可读渲染：

```python
logger.generic_obj(
    "无法解析输入包，相关数据：",
    {"packet": packet, "source": source, "retry": retry_count},
    level=LogLevel.ERROR,
)

try:
    await action.execute()
except Exception:
    logger.generic_exc("行为执行失败", {"action": action, "event": event})
```

{meth}`~.GenericLogger.generic_exc` 等价于先调用 `exception`，再以 `ERROR` 级别记录对象。

### 依赖注入取得的日志器

日志器同样是自动依赖项：

```python
from melobot import Bot
from melobot.log import GenericLogger

async def setup(bot: Bot, logger: GenericLogger) -> None:
    logger.info(f"正在初始化 {bot.name}")
```

这里注入的是**当前 bot 的 `logger` 属性**，不是按模块域解析后的代理。如果 bot 初始化时没有提供日志器，该依赖无法满足。因此，想要遵守模块域规则时使用 `from melobot.log import logger`；想要明确把日志器作为处理函数或 hook 的依赖时，使用 {class}`.GenericLogger` 注解。

## 内置 Logger

{class}`.Logger` 基于标准库 `logging.Logger`，实现了 {class}`.GenericLogger`，并额外提供彩色控制台、Rich 对象渲染、异常格式化和滚动文件输出。多数项目直接使用它即可：

```python
from melobot import Bot
from melobot.log import Logger, LogLevel

app_logger = Logger(
    "my-bot",
    level=LogLevel.INFO,
    file_level=LogLevel.DEBUG,
    to_console=True,
    to_dir="logs",
    two_stream=True,
)
bot = Bot("my-bot", logger=app_logger)
```

常用初始化参数如下：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `name` | `"[default]"` | 显示在日志中的日志器名称，也是文件名前缀 |
| `level` | `INFO` | 控制台输出的最低等级 |
| `file_level` | `DEBUG` | 文件输出的最低等级 |
| `to_console` | `True` | 是否输出到控制台；`ERROR` 及以上会写入 stderr，其余写入 stdout |
| `to_dir` | `None` | 日志目录；提供后启用滚动文件输出 |
| `two_stream` | `False` | 是否将普通日志与 `WARNING` 以上的问题日志分开写入文件 |
| `add_tag` | `True` | 是否在每行中显示 `name` 标签 |
| `legacy` | `False` | 使用传统的按日志等级着色样式，而不是 Rich 内容渲染样式 |
| `yellow_warn` | `True` | 非传统样式下，是否分别突出显示警告内容 |
| `red_error` | `True` | 非传统样式下，是否分别突出显示错误内容 |
| `is_parallel` | `False` | 在主线程的运行期异步渲染日志内容，降低渲染阻塞 |

提供 `to_dir` 时，每个文件达到 1 MiB 会滚动，保留最多 10 个备份。`two_stream=False` 时写入 `<name>.log`；设为 `True` 后，`DEBUG`、`INFO` 写入 `<name>.out.log`，`WARNING` 及以上写入 `<name>.err.log`。若目录不存在，Logger 会创建最后一级目录；因此其父目录需要已经存在。

`is_parallel=True` 会把 Rich 格式化交给独立的渲染任务处理，适合大量、复杂对象的日志；代价是少量相邻日志可能改变显示顺序。

创建后可使用 {meth}`~.Logger.set_level` 修改控制台等级：

```python
app_logger.set_level(LogLevel.DEBUG)
```

该方法不会改变文件 handler 的等级；需要保留文件调试信息、但让控制台保持简洁时，这正是预期行为。

## 修补已有日志器

已有项目可能已经使用标准库、Loguru 或 Structlog。此时无需重写整套日志配置：{func}`.logger_patch` 会在原日志器对象上补充 `generic_lazy`、`generic_obj` 和 `generic_exc`，并将它标记为兼容的 {class}`.GenericLogger`。

```{admonition} 修补会原地修改对象
:class: note
`logger_patch` 返回的仍是传入的日志器对象，只是其接口被扩展。请在完成第三方日志器自身的 handler、sink 或 processor 配置后再修补，并将返回值提供给 `Bot` 或日志域配置。
```

### 标准库 logging

标准库日志器使用 {class}`.StandardPatch`：

```python
import logging

from melobot import Bot
from melobot.log import StandardPatch, logger_patch

std_logger = logging.getLogger("my-bot")
std_logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
std_logger.addHandler(handler)

bot_logger = logger_patch(std_logger, StandardPatch(std_logger))
bot = Bot("my-bot", logger=bot_logger)
```

`StandardPatch` 会通过标准库的等级判断实现惰性参数求值，并保留当前异常信息。标准库 handler、formatter、传播规则仍完全由你的 `logging` 配置决定。

### Loguru

Loguru 使用 {class}`.LoguruPatch`。先按 Loguru 的方式配置 sink，再进行修补：

```python
import sys

from loguru import logger as loguru_logger

from melobot import Bot
from melobot.log import LoguruPatch, logger_patch

loguru_logger.remove()
loguru_logger.add(sys.stderr, level="INFO")

bot_logger = logger_patch(loguru_logger, LoguruPatch(loguru_logger))
bot = Bot("my-bot", logger=bot_logger)
```

Loguru 使用 `{}` 格式化，而 melobot 的 `generic_lazy` 使用 `%s`。`LoguruPatch` 会在转发时完成这种占位符转换，并通过 Loguru 的 `lazy=True` 保持惰性求值。普通的 `debug`、`info` 等调用仍遵守 Loguru 自身的格式化语法。

### Structlog

Structlog 使用 {class}`.StructlogPatch`：

```python
import structlog

from melobot import Bot
from melobot.log import StructlogPatch, logger_patch

# processor、renderer 等配置按项目需要完成
struct_logger = structlog.get_logger("my-bot")

bot_logger = logger_patch(struct_logger, StructlogPatch(struct_logger))
bot = Bot("my-bot", logger=bot_logger)
```

`StructlogPatch` 将消息和参数直接交给 Structlog，因此 JSON renderer、上下文字段和 processor 链仍由 Structlog 配置控制。需要注意的是，当前实现会在调用 Structlog 前执行所有 `generic_lazy` 的参数函数；它主要用于接口兼容，**不保证**关闭日志等级时跳过昂贵计算。此类场景可在调用前自行判断等级，或实现下节的自定义修补器。

### 自定义修补器

要接入其他日志库，目标对象首先需要提供 `debug`、`info`、`warning`、`error`、`critical` 与 `exception` 方法。随后实现一个符合 {class}`.LazyLogMethod` 调用约定的对象，并交给 `logger_patch`。下面的例子假设第三方日志器有 `enabled(level)` 用于判断等级：

```python
from typing import Any, Callable

from melobot.log import LogLevel, logger_patch

class MyLazyPatch:
    def __init__(self, target: Any) -> None:
        self.target = target

    def __call__(
        self,
        msg: str,
        *arg_getters: Callable[[], Any],
        level: LogLevel,
        with_exc: bool = False,
    ) -> None:
        # 必须先判断，再执行 getter，才能真正保持惰性
        if not self.target.enabled(level):
            return

        message = msg % tuple(getter() for getter in arg_getters)
        if with_exc:
            self.target.exception(message)
            return

        methods = {
            LogLevel.DEBUG: self.target.debug,
            LogLevel.INFO: self.target.info,
            LogLevel.WARNING: self.target.warning,
            LogLevel.ERROR: self.target.error,
            LogLevel.CRITICAL: self.target.critical,
        }
        methods[level](message)

third_party_logger = create_third_party_logger(...)
bot_logger = logger_patch(third_party_logger, MyLazyPatch(third_party_logger))
```

自定义实现的关键在于三点：只在确实会记录时调用 `arg_getters`；`with_exc=True` 时使用目标库能保留当前异常栈的方法；明确处理 `LogLevel` 到目标库等级或方法的映射。若目标库支持结构化字段，也可以不进行 `%` 插值，而是将 `msg` 和计算后的参数作为字段传入。

## 事件循环中的未捕获异常

调用 {meth}`~.Bot.run` 或 {meth}`~.Bot.run_async` 时，默认会临时安装 melobot 的事件循环异常处理器，并通过当前日志机制报告未捕获异常。`strict_log=False`（默认）会把“从未取回的任务异常”视为调试信息；设为 `True` 后会以错误级别打印完整异常栈：

```python
bot.run(strict_log=True)
```

若宿主程序已经接管事件循环的异常策略，可将 `use_exc_handler=False`，保留其原有处理器。无论哪种方式，都应尽量在自己的协程中捕获并记录可预期的业务异常；事件循环异常处理器只应作为最后一道诊断防线。

## 总结

业务模块使用动态 `logger` 即可获得模块优先、bot 次之、全局兜底的日志路由。需要统一配置时，在主入口设置日志域；需要可移植的高级记录时依赖 {class}`.GenericLogger`；已有项目则通过修补器保留原有日志生态。这样既能让框架和插件共享一致的诊断能力，也不会强迫整个项目迁移到单一日志库。

下一篇将介绍：[实用组件](./utils)。
