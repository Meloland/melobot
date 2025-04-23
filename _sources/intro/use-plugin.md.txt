# 插件系统的使用

## 匿名插件

在之前的例子中，我们通过实例化 {class}`.PluginPlanner` 创建了一个插件管理器，并向其中添加“处理流”（我们的函数经过绑定方法装饰后将会生成“处理流对象”）。随后又使用 {meth}`~.Bot.load_plugin` 将插件加载在 bot 中：

```python
from melobot import PluginPlanner

@on_start_match(".sayhi")
async def echo_hi() -> None:
    await send_text("Hello, melobot!")

# echo_hi 这个事件处理函数，经过 on_xxx 方法装饰，实际上变为一个“处理流”对象
test_plugin = PluginPlanner(version="1.0.0", flows=[echo_hi])

if __name__ == "__main__":
    # 此处省略创建 bot 等代码
    ...
    bot.load_plugin(test_plugin)
```

这实际上是创建了“匿名插件”并加载。一般用作临时性调试用途。在复杂的实际项目中，可能有很多功能要分别写到不同的插件中，方便管理和维护。此时再这样创建插件就不再合适。

下面我们将介绍如何通过模块为载体，来声明和加载插件。

```{admonition} 提示
:class: tip

关于“处理流”的更多内容，未来的教程我们将会详细说明。
```

## 模块级插件的声明

在任意目录中，创建子目录作为“插件目录”，例如下面例子中的 `test_plugin`：

```shell
./
└── test_plugin
```

插件目录的名称，将被 melobot 识别为插件的名称，同时也是加载时的唯一 id。因此请不要为一个 bot 加载两个同目录名的插件，这将会导致**加载错误**异常。

随后，插件管理器对象，需要存在于该目录中的 `__plugin__.py` 文件（一般称为插件入口文件）中：

```shell
./
└── test_plugin
    └── __plugin__.py
```

```python
# __plugin__.py 内：
from melobot import PluginPlanner

@on_start_match(".sayhi")
async def echo_hi() -> None:
    ...

# 变量命名为任意名称都可以，这并不影响加载过程
# 但我们建议使用常量命名规范，并为："XXX_PLUGIN" 或 "PLUGIN"
ECHO_PLUGIN = PluginPlanner(version="1.0.0", flows=[echo_hi])
```

除了 **插件目录中必须存在 `__plugin__.py`**，**插件管理器对象必须存在于 `__plugin__.py` 中** 这两条规则，其余的组件可以自由地划分到插件目录的其他模块中，甚至任意深度子目录中的子模块也没有问题。

```shell
./
├── flow2.py
├── more_flows
│   └── flow3.py
└── __plugin__.py
```

```python
# __plugin__.py 内：
from melobot import PluginPlanner
from .flow2 import another_echo_hi
from .more_flows.flow3 import third_echo_hi

@on_start_match(".sayhi")
async def echo_hi() -> None:
    ...

ECHO_PLUGIN = PluginPlanner(
    version="1.0.0",
    # 如果需要，就加到插件管理器中；不需要就甚至不用导入咯~
    flows=[echo_hi, another_echo_hi, third_echo_hi]
)
```

在某些情况下，先通过 {class}`.PluginPlanner` 创建插件管理器对象，再使用会较为方便。

但问题是，如果先创建插件管理器，此时处理流显然尚未就位。因此我们提供了 {meth}`~.PluginPlanner.use` 装饰器用于解决此问题：

```python
# __plugin__.py 内：
from melobot import PluginPlanner

ECHO_PLUGIN = PluginPlanner(version="1.0.0")

@ECHO_PLUGIN.use
@on_start_match(".sayhi")
async def echo_hi() -> None:
    ...
```

```{admonition} 提示
:class: tip
{meth}`~.PluginPlanner.use` 装饰器等相关接口，一般被称为“组合式风格”。而通过类的初始化参数声明插件功能，一般被称为“选项式风格”。

未来会介绍更多两种风格的 API。具体选择哪种风格进行开发，请根据实际情况与项目结构斟酌，并没有绝对的优劣。
```

```{admonition} 注意
:class: caution
一般情况下，**请勿在插件目录内手动创建 `__init__.py` 文件**。

在之后的教程中会详细说明为什么不要这样做，以及与此相关的**插件加载机制**与**插件高级用法**。
```

## 模块级插件的加载

在目前阶段，只需要学会通过插件目录的路径，或者插件模块的包名加载插件，就可以了：

```python
# 在创建 bot 后使用，提供插件目录的相对或绝对路径：
bot.load_plugin("test_plugin")
# 或
bot.load_plugin("./test_plugin")
# 或
bot.load_plugin("/home/test_user/my_bot/test_plugin")

# 如果是从 pip 安装的第三方模块
bot.load_plugin("melobot_plugin_xxx")
```

一般情况下，**请勿将本地插件目录名设置为与第三方插件模块相同的名称**。

虽然 melobot 会依据 `sys.path` 的优先级加载，但是同名是非常不好的习惯。

## 总结

本篇主要说明了插件系统的简单使用方法。

下一篇将重点说明：简单的交互式事件处理与会话。
