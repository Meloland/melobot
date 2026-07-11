# 元信息

melobot 在顶级模块提供只读的项目元信息 {class}`.MetaInfo`，以及结构化版本号对象 {class}`.VersionInfo`。它们适合用于诊断信息、插件兼容性提示、CLI 输出和定位安装位置，而不需要依赖私有实现文件。

## MetaInfo

`MetaInfo` 的属性都定义在类上，应直接通过类名读取：

```python
from melobot import MetaInfo

print(MetaInfo.name)      # "melobot"
print(MetaInfo.ver)       # 版本字符串
print(MetaInfo.src)       # 项目地址
print(MetaInfo.pkg_path)  # 顶级包的 pathlib.Path
```

| 属性 | 含义 |
| --- | --- |
| `name` | 项目名称 |
| `desc` | 项目描述 |
| `src` | 项目源码地址 |
| `ver` | 当前版本字符串；与 `melobot.__version__` 对应 |
| `ver_info` | 当前版本的 {class}`.VersionInfo` |
| `pkg_path` | 已安装 melobot 顶级包所在的绝对 `Path` |
| `logo` | 用于终端展示的 ASCII 图标文本 |

```python
from melobot import MetaInfo

def diagnostics() -> dict[str, str]:
    return {
        "framework": MetaInfo.name,
        "version": MetaInfo.ver,
        "package_path": str(MetaInfo.pkg_path),
    }

print(MetaInfo.logo)
```

这些属性是只读的。不要尝试修改它们来伪装版本或重定向框架路径；需要记录应用自身的信息，应单独定义配置对象。

## VersionInfo

`VersionInfo` 是一个具名元组，字段结构与 Python 常见的版本信息一致：

```python
from melobot import MetaInfo, VersionInfo

version: VersionInfo = MetaInfo.ver_info
print(version.major, version.minor, version.micro)
print(version.releaselevel, version.serial)
```

| 字段 | 含义 |
| --- | --- |
| `major` | 主版本号；重大架构更新时变化 |
| `minor` | 次版本号；重要功能更新时变化 |
| `micro` | 微版本号；一般功能更新或修复时变化 |
| `releaselevel` | `"alpha"`、`"beta"`、`"pre-release"` 或 `"final"` |
| `serial` | 非正式发行阶段的序列号；正式版时与 `micro` 相同 |

版本比较应优先比较结构化字段，而不是依赖版本字符串的字典序：

```python
from melobot import MetaInfo

version = MetaInfo.ver_info
if (version.major, version.minor) < (3, 4):
    raise RuntimeError("此插件需要 melobot 3.4 或更新版本")
```

`releaselevel` 适合在开发、测试或预发行环境中提示兼容性风险。若插件要求严格的版本范围，仍建议使用包管理器的依赖声明作为第一道约束，并把运行时判断作为清晰的错误提示。

## 总结

使用 `MetaInfo` 读取框架身份、路径和当前版本；需要依据版本做逻辑判断时使用 `MetaInfo.ver_info` 的结构化字段。它们是诊断和兼容性辅助信息，不应替代包元数据中的依赖约束或应用自身的配置。

下一篇将介绍：[CLI 界面](./cli)。
