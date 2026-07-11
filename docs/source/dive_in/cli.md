# CLI 界面

安装 melobot 后可使用 `mb` 命令。除创建项目模板的 `mb init` 外，其余命令用于查看版本、生成插件导出接口，以及以支持重启或自动重载的方式运行 bot。

```{admonition} 依赖
:class: note
`mb dev` 依赖文件监测功能。若命令提示缺少依赖，请安装 CLI 可选依赖：`pip install 'melobot[cli]'`。
```

## 查看帮助与版本

```shell
mb --help
mb --version
# 或
mb -v
```

`--help` 显示全部可用命令及参数；`--version` 同时显示 `mb` 程序自身和当前安装的 melobot 版本。这通常是提交问题报告时最先需要的信息。

## 初始化插件接口：mb pinit

```shell
mb pinit <插件目录> [<插件目录> ...]
mb pinit -d 2 ./plugins/weather
```

`mb pinit` 读取插件的 `__plugin__.py`，为插件生成 `__init__.py` 和 `__init__.pyi`。生成的模块暴露插件版本、共享对象、导出函数及可选的初始化参数类型，使其他插件可以像普通 Python 导入一样访问它们。

`-d` / `--depth` 指定向上引用深度，必须与加载该插件时的 `load_depth` 保持一致。命令会覆盖已有的生成文件，因此不要手动编辑 `__init__.py`、`__init__.pyi`。插件接口生成、跨插件调用及初始化参数的完整说明见[插件系统与进阶用法](./plugin_usage)。

## 可重启运行：mb run

```shell
mb run bot.py
# .py 后缀可省略
mb run bot
```

`mb run` 会以子进程运行入口脚本，并转发其标准输入、输出和错误输出。当 bot 调用 {meth}`~.Bot.restart` 时，子进程以特定退出码结束，`mb run` 随即重新启动它；正常停止则结束命令。

重启能力仅在入口脚本通过 `mb run` 启动且进程中只运行一个 bot 时有效。若只是希望普通启动，直接执行 `python bot.py` 仍然完全可行，但 `Bot.restart()` 不可用。

```{admonition} 提示
:class: tip
`mb run` 不监测文件改动。需要在修改源码后自动重启时，应使用下一节的 `mb dev`。
```

## 开发模式：mb dev

```shell
# 默认递归监测当前目录
mb dev bot.py

# 只监测指定目录或文件
mb dev bot.py --watch src plugins
```

`mb dev` 同样以子进程运行入口脚本，并支持 `Bot.restart()`；此外，它会递归监测 `--watch` 提供的路径。检测到创建、修改、移动或删除后，会停止当前子进程并重新启动。`--watch` 未提供参数时默认监测当前目录 `.`。

开发模式适合本地迭代插件和处理流。生产环境通常使用进程管理器、容器编排或发布系统完成重启，不建议依赖文件监测器。

## 命令速查

| 命令 | 用途 |
| --- | --- |
| `mb --help` | 查看命令帮助 |
| `mb --version` / `mb -v` | 查看 CLI 与 melobot 版本 |
| `mb pinit [-d 深度] <插件目录>...` | 生成插件入口与类型接口 |
| `mb run <入口文件>` | 运行 bot，支持程序主动重启 |
| `mb dev <入口文件> [-w 路径...]` | 开发模式运行，支持主动重启和文件变动自动重载 |

## 总结

`mb pinit` 解决插件接口生成，`mb run` 为程序主动重启提供运行环境，`mb dev` 在此基础上增加文件监测。其余时候使用 `mb --help` 确认参数，使用 `mb --version` 记录运行环境即可。

下一篇将介绍：[多进程支持](./mp)。
