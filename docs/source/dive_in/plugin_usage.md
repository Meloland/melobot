# 插件系统与进阶用法

插件系统是 melobot 实现模块化扩展的核心机制。通过插件，你可以将 bot 的不同功能拆分到独立的目录中，实现高内聚、低耦合的代码组织。但更重要的是，melobot 的插件系统还提供了一套**安全的跨插件通信机制**，让你在享受模块化带来的便利时，不会陷入依赖地狱。

```{admonition} 关于"插件"术语
:class: note
在 melobot 中，"插件"一词默认指 **melobot 专用插件**——它是一个包含 `__plugin__.py` 文件的目录，而不是广义上的 Python 包或模块。本文除非特别说明，否则"插件"均指 melobot 插件。
```

```{admonition} 相关知识
:class: note
如果你不知道与插件相关的基本用法，建议先浏览：[插件的基本知识](../intro/use-plugin)
```

## 插件的两种形态

melobot 中的插件以两种形态存在：**模块级插件**和**匿名插件**（动态插件）。

### 模块级插件

模块级插件是最常用、最推荐的插件形式。它对应文件系统中的一个**目录**，该目录下必须包含一个 `__plugin__.py` 文件作为插件的入口模块。目录名即是插件的名称。

一个典型的模块级插件目录结构如下：

```
my_plugin/             # 插件目录名（也就是插件名，是插件区分的唯一标志）
├── __plugin__.py      # 插件入口（必需）
├── __init__.py        # 自动生成（由 mb pinit 生成）
├── __init__.pyi       # 自动生成（由 mb pinit 生成）
├── handlers.py        # 事件处理逻辑
├── data.py            # 数据相关
└── utils.py           # 工具函数
```

`__plugin__.py` 中必须实例化一个 {class}`.PluginPlanner`（插件管理器），melobot 通过它来识别和加载插件：

```python
# my_plugin/__plugin__.py
from melobot import PluginPlanner

# 同时指定插件版本
my_plugin = PluginPlanner("0.1.0")
```

bot 加载此插件时会动态导入 `__plugin__.py` 模块，搜索其中的 {class}`.PluginPlanner` 实例，并据此构建插件运行时对象。

```{admonition} 注意
:class: warning
插件目录中的所有模块互相引用请使用相对导入。

不要使用绝对导入，绝对导入可能会导致加载错误。具体原因在后续部分会讲解。
```

### 匿名插件（动态插件）

匿名插件不依赖文件系统。直接向 bot 传递一个插件管理器实例即可。它适用于**临时构建、测试，或需要在代码中动态生成插件**的场景：

```python
from melobot import Bot, PluginPlanner

bot = Bot("my_bot")
dyn_p = PluginPlanner("0.1.0")
bot.load_plugin(dyn_p)
```

```{admonition} 选择建议
:class: tip
对于正式项目，推荐使用**模块级插件**，因为它有清晰的目录结构、支持自动导入、可以生成 `__init__.py` 实现优雅的跨插件引用。

匿名插件适合快速原型、单元测试，或需要在运行时动态组装插件功能的特殊场景。
```

## 插件管理器

{class}`.PluginPlanner` 是插件的"声明中心"，它承载了插件的所有元信息和功能组件，每一个实例代表一个插件。

### 初始化参数

| 参数 | 说明 |
|------|------|
| `version` | 插件版本号，会写入自动生成的 `__init__.py` 中，可供其他插件查询 |
| `flows` | 插件初始化后要注册到 bot 的处理流。可先传空，后续通过 {meth}`~.PluginPlanner.use()` 绑定 |
| `shares` | 插件对外暴露的共享对象。可先传空，后续通过 {meth}`~.PluginPlanner.use()` 绑定 |
| `funcs` | 插件对外暴露的导出函数。可先传空，后续通过 {meth}`~.PluginPlanner.use()` 绑定 |
| `auto_import` | 导入插件目录下所有 `.py` 模块；也可提供相对路径列表。**对匿名插件无效** |
| `info` | 插件的描述性元信息 |

### 插件信息类

{class}`.PluginInfo` 用于为插件附加描述性信息：

```python
from pathlib import Path
from melobot import PluginPlanner, PluginInfo

my_plugin = PluginPlanner(
    "0.1.0",
    info=PluginInfo(
        desc="一个提供天气查询功能的插件",
        author="username",
        url="https://github.com/username/my_plugin",
        keywords=("weather", "query"),
        docs=Path(__file__).parent / "README.md",
    ),
)
```

其他模块可以通过 `import` 直接获取插件的元信息：

```python
import my_plugin
print(my_plugin.__version__)   # "1.0.0"
print(my_plugin.__author__)    # "username"
print(my_plugin.__doc__)       # "一个提供天气查询功能的插件"
```

### use() 装饰器

除了在构造时传入 `flows`、`shares`、`funcs`，更常见的做法是使用组合式 API（即 {meth}`~.PluginPlanner.use()`）动态绑定：

```python
from melobot import PluginPlanner, send_text, on_start_match

my_plugin = PluginPlanner("0.1.0")

@my_plugin.use
@on_start_match(".hi")
async def greet() -> None:
    await send_text("你好！")
```

{meth}`~.PluginPlanner.use()` 能自动识别被装饰对象的类型，并最终注册到 bot 中。

```{admonition} use() 的返回值
:class: note
{meth}`~.PluginPlanner.use()` 返回被装饰对象本身，因此你可以继续在别处使用被装饰对象。
```

### 自动导入

模块级插件支持通过 `auto_import` 参数自动加载插件目录下的子模块，无需手动 import：

```python
# 导入插件目录下所有 .py 文件
my_plugin = PluginPlanner("1.0.0", auto_import=True)

# 只导入指定的模块，相对路径基于插件目录进行计算
my_plugin = PluginPlanner("1.0.0", auto_import=["handlers.py", "utils/compiled_mod.so"])
```

`auto_import=True` 会递归查找插件目录下所有 `.py` 文件并导入。导入非 `.py` 后缀的模块（如 `.pyc`、`.pyd`、`.so`）或导入指定几个模块，需要手动提供路径列表。

`auto_import=True` 时的模块扩展名优先级由 {data}`melobot.MODULE_EXTS` 定义。

```{admonition} 提示
:class: tip
`auto_import` 的主要价值不在于让你少写 `import` 语句。主要作用是可以进行“依赖反转”。

例如：在 `__plugin__.py` 中定义插件管理器和流对象，在其他需要的模块中导入就可以使用组合式 API
```

## 插件加载方法

bot 对象提供了四种加载插件的方法，覆盖了从单个插件到批量目录加载的各种场景。加载插件完全是同步过程，且多线程不安全。

### load_plugin()

这是最核心的加载方法，**其他三种方法最终都会调用它**。`plugin` 参数支持四种类型：

| 类型 | 示例 | 说明 |
|------|------|------|
| {class}`.PluginPlanner` | `bot.load_plugin(my_planner)` | 匿名插件，直接在代码中构建 |
| {class}`str`（可直接导入的模块名） | `bot.load_plugin("my_plugin")` | 作为 Python 模块名导入，遵循 sys.path 搜索 |
| {class}`str` \| {class}`~.os.PathLike`（路径） | `bot.load_plugin("./plugins/my_plugin")` | 插件目录的路径（相对或绝对） |
| {class}`~.types.ModuleType` | `bot.load_plugin(plugin_dir_module)` | 已导入的模块对象（插件目录对应的模块，不是 `__plugin__.py` 模块） |

支持链式调用：

```python
bot.load_plugin("plugin_a").load_plugin("plugin_b")
```

### load_plugins()

接收一个可迭代对象，依次调用 {meth}`~.Bot.load_plugin()`。适用于有一批插件需要加载的场景：

```python
bot.load_plugins(["plugin_a", "./plugin_b", "/home/user/mb_plugins/plugin_c", ...])
```

### load_plugins_dir()

扫描指定目录下的所有**子目录**（排除 `__pycache__`），将每个子目录作为插件加载。适合将插件集中存放在某个目录的结构：

```
plugins/
├── weather/
│   └── __plugin__.py
├── scheduler/
│   └── __plugin__.py
└── admin/
    └── __plugin__.py
```

```python
bot.load_plugins_dir("./plugins")
```

### load_plugins_dirs()

接受多个父目录，对每个目录调用 {meth}`~.Bot.load_plugins_dir()`。适用于插件分散在多个位置的复杂项目：

```python
bot.load_plugins_dirs(["./core_plugins", "./user_plugins"])
```

(plugin_load_depth)=
### load_depth 参数

所有加载方法都接受 `load_depth` 参数（默认值为 1）。它控制插件导入后的模块命名空间名。具体来说：

- `load_depth=1`：插件 `my_plugin` → 入口模块键名 `my_plugin.__plugin__`，子模块 `my_plugin.handlers`
- `load_depth=2`：插件 `my_plugin` 位于 `extensions/my_plugin/` → 入口模块键名 `extensions.my_plugin.__plugin__`，子模块 `extensions.my_plugin.handlers`
- `load_depth=3`：依此类推，取路径最后 N 级作为前缀

```{admonition} 何时增大 load_depth
:class: tip
如果你需要**按层级组织插件**：例如 `project/feature_set/my_plugin/`，并且希望使用 `feature_set.my_plugin` 这样的完整命名空间名，就需要增大 `load_depth`。Python 依赖命名空间名执行相对导入。增大 `load_depth` 的优势是：**可以使用 "from .xxx import yyy"、"from ..uuu import vvv" 甚至更深层级的相对导入**。

大多数情况下：
- 使用来自互联网（pip 或其他平台）的插件，插件内部不使用相对导入，加载深度为 1
- 使用自行编写的插件，加载深度设为 1 或设为 2-3 即可满足需求。不建议 > 4，太深的相对导入往往说明模块组织不合理
- 使用自行解压到文件系统的插件包，加载深度请参考插件包作者
```

```{admonition} 父目录同名导致的名称冲突
:class: warning
假设 `./a/b/c/d` 目录的插件（即插件 d）使用了加载深度 2，形成命名空间名：`c.d`

此时 `./a/c/e` 目录的插件（即插件 e）若使用加载深度 2，则无法正常加载。

因为 melobot 加载插件 e 时需要的模块 c（对应 `./a/c`）名称上与加载插件 d 时已缓存的模块 c（对应 `./a/b/c`）冲突。出现这类冲突情况时 melobot 会抛出异常，按提示处理即可。
```

## 跨插件通信

在插件化的 bot 框架中，跨插件依赖是一个棘手的问题。为了更好地理解 melobot 的解决方案，让我们先看看传统框架中常见的痛点。

### 依赖问题的三种形态

**依赖地狱**：假设插件 C 依赖插件 B 的功能，插件 B 依赖插件 A 的功能。你必须严格按照 A → B → C 的顺序**加载并初始化**这些插件，否则就会出错。随着插件数量增加，手动管理加载顺序将成为一场噩梦。

**功能延迟**：即使插件 B 中有一个工具函数 `format_date()` 完全不依赖插件 A，但在"必须先初始化依赖"的约束下，整个插件 B 的所有功能都必须等到插件 A 初始化完成后才能使用——包括那些毫无关联的部分。

**循环依赖**：插件 A 需要插件 B 的某个功能，插件 B 也需要插件 A 的某个功能。无论按什么顺序加载，都会有一个插件在初始化时发现它所依赖的另一方尚未就绪。这是最致命的问题——在传统框架中，循环依赖往往意味着需要重新设计插件架构。

### 共享对象与延迟解析

melobot 解决上述问题的核心思路是：**声明时只记录依赖关系，访问时才实际解析依赖**。这通过以下两层机制实现：

1. **共享对象**（{class}`.SyncShare` / {class}`.AsyncShare`）：插件将需要对外暴露的数据或功能包装为共享对象，在加载时注册到 bot
2. **延迟解析**：跨插件访问时，动态获取目标值，而非在 import 时就建立硬依赖

这意味着：
- 加载顺序不再重要——因为加载时只注册声明，不做实际调用
- 功能延迟不再是问题——每个组件在真正被使用时才解析依赖
- 循环依赖不再是死结——A 和 B 互相引用共享对象，只要不在各自的初始化阶段相互调用就不会出错

(share_object_usage)=
### 共享对象的定义和基本使用

共享对象是跨插件通信的基本单元。根据访问方式的不同，分为两种：

**同步共享对象** {class}`.SyncShare`：通过同步 getter/setter 访问。

```python
from melobot.plugin import SyncShare
from melobot.exceptions import ShareObjectCallbackFailed as CbFailed

# 定义一个共享计数器，其他插件使用 "counter" 引用
counter = SyncShare[int]("counter")

@counter
def get_counter() -> int:
    # 从数据库或其他地方获取计数值
    return count

@counter.setter
def set_counter(val: int) -> None:
    # 很显然地，可以在 setter 中运行校验再执行具体操作
    if not condition:
        # 如果校验不通过，建议包装在特定异常中便于传播
        # 从而与其他可能发生的异常区分开来
        raise CbFailed(...)
    ...

# 如果已经提前实例化了 PluginPlanner 对象（假设为 my_plugin），直接使用 use
my_plugin.use(counter)
# 或者在插件管理器实例化时注册
my_plugin = PluginPlanner(shares=[counter])
```

**异步共享对象** {class}`.AsyncShare`：通过异步 getter/setter 访问（支持依赖注入）。

```python
from melobot import Bot, GenericLogger
from melobot.plugin import AsyncShare

# 定义一个异步共享的配置对象，其他插件使用 "config" 引用
config = AsyncShare[dict]("config")

@config
# 可以执行依赖注入
async def get_config(bot: Bot, logger: GenericLogger) -> dict:
    # 异步读取配置
    return await read_config_from_db()

@config.setter
# 依然可以执行依赖注入，保证第一参数用于接受请求的修改值即可
async def set_config(val: dict, bot: Bot, ...) -> None:
    # 依然可以使用验证，这里略去
    await write_config_to_db(val)

# 使用 use 或在插件管理器实例化时注册
...
```

一种花哨的写法，可以让你少写几行：

```python
@(attr := AsyncShare("attr"))
async def get_attr() -> str: ...

@attr.setter
async def set_attr(val: str) -> None: ...
```

```{admonition} 警告
:class: warning
提供给插件管理器的共享对象，必须在本插件目录内定义。也就是说，你不能进行类似“重导出”的操作。
```

#### 静态共享对象

当共享对象的值是**不需要其他插件修改**的，你可以将其设为静态模式：

```python
# 静态共享对象：不需要也不能设置 setter
@SyncShare[float]("pi", static=True)
def _() -> float:
    return 3.1415926535

@AsyncShare[str]("magic_str", static=True)
async def _() -> str:
    # 异步地返回一个字符串
    ...
```

#### 构造时绑定

共享对象的 getter 和 setter 可以在构造时绑定：

```python
from melobot.utils import to_async

# 仅推荐使用简单 lambda 时，采用构造时绑定
count = SyncShare[int]("count", reflector=lambda: ..., callback=lambda v: ...)
config = AsyncShare[dict](
    "config", 
    # 使用 to_async 可以包装它为异步函数
    reflector=to_async(lambda: ...),
    # 或者让 lambda 自己返回一个可等待对象，在接口上是兼容的
    callback=lambda v: ...
)
```

#### 导出函数：共享对象的便捷包装

如果你只是想对外暴露一个普通函数，不需要 getter/setter 的复杂语义，可以使用**导出函数**：本质上是自动包装为静态 {class}`.SyncShare` 的函数：

```python
def format_weather(city: str, temp: float) -> str:
    return f"{city}：{temp}°C"

# 注册为导出函数
my_plugin = PluginPlanner("1.0.0", funcs=[format_weather])
# 或通过 use
@my_plugin.use
def format_weather(...) -> str: ...
```

#### 原始插件通信

在其他插件中，你可以使用原始插件通信方法获取共享对象：

```python
# 获取 my_plugin 中名为 "counter", "config" 的共享对象
counter = bot.get_share("my_plugin", "counter")
config = bot.get_share("my_plugin", "config")

# 在实际需要时，例如就绪 hook 中或事件处理流中：
# 获取值
cnt = counter.get()
cfg = await config.get()
# 设置值
counter.set(new_cnt)
await config.set(new_cfg)
```

实际开发中很少使用 {meth}`.Bot.get_share()`，太繁琐了。melobot 提供了更优雅的方式，见下一节。

### 自动注解生成与使用

`mb pinit` 是 melobot CLI 提供的命令，用于为插件目录自动生成 `__init__.py` 和 `__init__.pyi` 文件并写入必要元信息。它的核心作用是：**让跨插件引用像普通的 Python import 一样自然**。操作步骤为：

1. 在 `__plugin__.py` 中定义共享对象和导出函数，并通过插件管理器注册
2. 运行 `mb pinit <插件目录>`
3. 在其他插件中 `from <位置> import <插件名>` 即可使用

```bash
# 为单个插件生成
mb pinit ./plugins/my_plugin

# 为多个插件生成
mb pinit ./plugins/plugin_a ./plugins/plugin_b

# 指定 load_depth（与加载时的 load_depth 保持一致）
mb pinit -d 2 ./plugins/my_plugin
```

```python
# 假设在与 my_plugin 插件同级目录中，存在另一插件 another_plugin
# 且我们设置 another_plugin 插件的 load_depth >= 2
from .. import my_plugin as p

# 在实际需要时，例如就绪 hook 中或事件处理流中：
cnt = p.counter.get()
config = await p.config.get()

# 在需要发起修改时：
p.counter.set(new_cnt)
await p.config.set(new_config)
```

不要在导入其他插件后，立即访问它们上面的共享对象，因为此时未就绪。

对于静态共享对象，在跨插件访问时会直接返回 {meth}`~.SyncShare.get()` 的结果值，就像导入了一个常量：

```python
from .. import my_plugin as p

# 在实际需要时，例如就绪 hook 中或事件处理流中：
pi = p.pi_value
magic_str = await p.magic_str
```

## 插件的生命周期

1. **插件模块执行**：由四种加载方式中的任何一种触发，完全是同步过程。加载目录内 `__plugin__.py` 对应模块，如果设置了 `auto_import`，即使没有 `import` 语句产生关联，也自动递归发现并加载剩余模块。此阶段 bot 实例、所有源与适配器已经存在，可以通过各种方式获取。
2. **插件就绪**：bot 调用启动方法（{meth}`~.Bot.run` 或 {meth}`~.Bot.run_async`）后，异步执行所有插件的就绪 hook。**就绪 hook 中可以访问其他插件的共享对象，也可运行耗时的异步初始化操作**。这一阶段源和适配器可能未开始工作，因为它们正在异步启动中。
3. **插件运行**：本插件的就绪 hook 运行结束后，本插件的处理流才能处理事件。
4. **插件停止**：bot 停止工作，触发源与适配器进行资源清理。插件不再接收到事件，即停止工作。插件自身的资源清理，应该和 bot 的生命周期（{meth}`~.Bot.on_close` 或 {meth}`~.Bot.on_stopped`）绑定。

插件内通过 {meth}`~.PluginPlanner.on_ready` 属性或 {meth}`~.HookMixin.on` 方法绑定就绪 hook：

```python
from melobot import GenericLogger
from melobot.plugin import PluginLifeSpan

my_plugin = PluginPlanner("0.1.0")

@my_plugin.on_ready
async def setup(logger: GenericLogger) -> None:
    await connect_db()
    ...
    logger.info("my_plugin 异步资源初始化完成")

# 或者使用 on
@my_plugin.on(PluginLifeSpan.READY)
async def _() -> None: ...
```

很显然，上面的例子展示了就绪 hook 可以使用依赖注入，但是请注意**就绪 hook 运行时源和适配器不一定开始工作**。

```{admonition} 注意
:class: warning
不要在顶层作用域内、就绪 hook 中直接运行耗时的同步操作，这会在插件加载时阻塞整个 bot 进程。

正确的做法是：IO 密集型耗时同步操作使用 async 风格接口或交给线程池，CPU 密集型耗时同步操作交给进程池，最后再异步等待。并且如果是初始化操作，最好都在就绪 hook 中完成等待。
```

常规的插件加载都在 bot 启动（调用 {meth}`~.Bot.run` 或 {meth}`~.Bot.run_async`）前，即静态加载。但实际上 melobot 支持在 bot 启动后再加载插件，这也被称为动态加载。优势是：可以用于实现插件的选择性加载。

仅推荐在插件就绪 hook 中、处理流运行时进行动态加载。

```{admonition} 危险
:class: danger
melobot 支持动态加载插件，但是不支持动态卸载插件。**Python 的底层机制决定：动态卸载模块是不安全的**。

即使递归清除 {data}`sys.modules` 缓存且清理干净所有残余引用，重复导入一些模块也可能造成以下问题：解释器崩溃、内存泄漏、关键操作不再保持原子性。
```

(plugin_init_args)=
## 插件的初始化参数

在加载插件时可以向插件提供**初始化参数**：

```python
# 注意 load_depth 为仅位置参数
# 初始化参数按仅关键字参数的形式提供
bot.load_plugin("./plugin_a", 3, arg1="hello", a=[1, 2], b=3)

# 其他三种加载插件的方法，按对应格式提供初始化参数即可，请自行查阅
```

在就绪回调中可以接收初始化参数：

```python
my_plugin = PluginPlanner("0.1.0")

@my_plugin.on_ready
async def setup(
    # 其他组件的依赖注入依然可以使用
    logger: GenericLogger, bot: Bot, 
    # 初始化参数的名称必须对应，顺序无所谓
    b: int, a: list[int], 
    # 也可以设置默认值
    arg1: str = "hi"
) -> None:
    ...
```

如果你想要“带有类型提示”的方案，可以按照以下步骤操作。首先在插件目录下撰写 `__pargs__.py`：

```python
# __pargs__.py 内：
from typing import TypedDict, NotRequired

# 类名必须为 Args，必须继承 TypedDict
class Args(TypedDict):
    a: list[int]
    b: int
    # 这只是标记拥有默认值，默认值请在就绪回调函数中设置
    arg1: NotRequired[str]
```

`__pargs__.py` 仅用于定义初始化参数的类型，辅助进行静态类型分析。因此此模块**不应导入插件内其他任何模块**。而且此模块应尽可能轻量，使用 `TYPE_CHECKING` 技巧可以避免加载耗时的模块：

```python
from typing import TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    # 这个非常耗时，所以不要直接导入它
    import torch

class Args(TypedDict):
    # 对应注解用引号包裹即可
    magic_tensor: "torch.Tensor"
```

接下来我们运行一次 `mb pinit` 即可在插件目录模块上绑定此 `Args` 类。加载插件时让用户使用以下形式即可：

```python
import my_plugin

# my_plugin 是插件目录模块
bot.load_plugin(my_plugin, **my_plugin.Args(...))
```

如果 load_depth > 1，需要注意导入插件目录模块的方式。此时你需要**自行保证模块名和导入深度是匹配的**：

```python
from plugins import her_plugin
# her_plugin 此时模块名为 plugins.her_plugin
# plugins.her_plugin 与 2 级加载深度是匹配的
bot.load_plugin(her_plugin, 2, **her_plugin.Args(...))
```

对于本地自行撰写的插件，某些情况下可能要通过操纵 `sys.path` 来实现这一点。而对于线上平台获取的插件，加载深度恒为 1。

最后，在就绪回调中使用解包类型注解语法：

```python
from typing import Unpack
from .__pargs__ import Args

@my_plugin.on_ready
async def _(bot: Bot, **args: Unpack[Args]) -> None:
    # 获得的值拥有精确的类型注解
    val = args["xxx"]
    ...
```

```{admonition} 注意
:class: warning
“带有类型提示”的方案**并不保证类型安全**。因为整个过程没有进行任何类型验证。

如果你需要类型验证，请自行使用 Pydantic 等三方模块提供的对 TypedDict 的类型验证功能。在就绪回调中对 `Unpack` 标注的 `args` 参数进行验证即可。
```

```{admonition} 提示
:class: tip
匿名插件也可以使用初始化参数，不过一般没有必要。
```

## 最佳实践

### 尽量少使用原始插件通信接口

{meth}`.Bot.get_share` 是底层接口，直接使用这种方式缺乏类型安全（没有 `.pyi` 的类型提示）保证，还降低了代码可读性。

只有在**确实需要动态性**，比如在运行时根据变量名查找共享对象时，才使用原始插件通信接口。

### 只写插件入口，让工具生成其余文件

melobot 插件的理念要求：

- **你只撰写** `__plugin__.py`（插件的真实入口），包含插件管理器和所有功能绑定
- **你永远不手动撰写** `__init__.py` 和 `__init__.pyi`，让它们通过 `mb pinit` 自动生成

手动写 `__init__.py`，可能不小心引入了对另一插件的硬 import，从而破坏了延迟解析的优势。

### 尽量在顶层作用域建立插件引用，但非共享对象引用

当你需要引用其他插件的共享对象时，尽量在模块的**顶层作用域**完成**插件目录模块**的 import。

顶层 import 让依赖关系一目了然，也方便后续各个共享对象使用时直接引用。除非你需要使用延迟 import 解决少量循环依赖问题，但大量的循环依赖意味着需要重构。

### 耗时操作永远不要同步阻塞

不要在顶层作用域内、就绪 hook 中直接运行耗时的同步操作，这会在插件加载时阻塞整个 bot 进程。

正确的做法是：IO 密集型耗时同步操作使用 async 风格接口或交给线程池，CPU 密集型耗时同步操作交给进程池，最后再异步等待。且如果是资源初始化，最好在就绪 hook 中完成等待。

### 合理使用自动导入

自动导入虽然方便，但递归查找并导入大量模块会拖慢加载速度，请酌情使用。

如果没有进行“依赖反转”以使用组合式 API 的需求，建议不使用自动导入。

### 共享对象命名规范

- 共享对象名、导出函数名**不能以 `_` 开头**
- 共享对象、导出函数名**不能与插件根目录下的文件名或目录名重复**

## 总结

melobot 的插件系统提供了一套完整的模块化开发方案，其核心优势在于：

| 特性 | 说明 |
|------|------|
| **两种插件形态** | 模块级插件（目录 + `__plugin__.py`）适合正式项目；匿名插件适合原型和测试 |
| **灵活的加载方式** | bot 提供 4 种加载方法，覆盖单插件、批量、单目录、多目录等场景 |
| **延迟解析的插件通信** | 通过共享对象，实现声明时不依赖、访问时才解析 |
| **生命周期 hook** | 就绪 hook 支持依赖注入，也可动态加载插件 |
| **解决三大依赖难题** | 依赖地狱、功能延迟、循环依赖——通过声明与解析分离得到根本性解决 |

掌握了插件系统与插件通信机制，你就能将 melobot 项目组织为清晰、可维护的模块化架构。

下一篇将介绍：[bot 对象与相关接口](./bot)。
