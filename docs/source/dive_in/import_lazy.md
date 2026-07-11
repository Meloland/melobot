# 导入与惰性加载

melobot 允许插件与扩展以多种 Python 模块形式组织，同时对少数不兼容的第三方包提供导入回退，并提供跨版本可用的惰性加载工具。本篇只介绍公开接口及其使用边界。

## 可加载模块后缀

{data}`melobot.MODULE_EXTS` 是当前平台可加载模块扩展名的元组，按优先级从高到低排列。它包含 CPython 扩展、Python 源文件和字节码文件等实际可加载形式：

```python
import melobot

for ext in melobot.MODULE_EXTS:
    print(ext)
```

后缀集合和顺序依赖操作系统、Python 实现及版本，不应在业务代码中硬编码。它的典型用途是插件的 `auto_import`：自动导入默认只查找 `.py` 文件；如果插件还包含已编译模块等其他可加载文件，可根据 `MODULE_EXTS` 选择后缀并显式提供路径。相关的插件组织方式可参阅[插件系统与进阶用法](./plugin_usage)。

```{admonition} 提示
:class: tip
`MODULE_EXTS` 描述的是当前解释器能识别的模块文件形式，并不意味着任意同后缀文件都能被正确加载。尤其是二进制扩展仍必须与当前 Python ABI 和平台兼容。
```

## 导入回退

绝大多数包可以直接导入。若某个**尚未导入**的模块或包与当前导入环境不兼容，可通过 {func}`.add_import_fallback` 标记其名称前缀，使其回退到 Python 默认导入机制：

```python
from melobot import add_import_fallback

# 必须在首次导入目标包之前调用
add_import_fallback("problematic_package")

import problematic_package
```

传入的是名称前缀，因此 `"problematic_package"` 同时覆盖其子模块。应尽量提供完整、明确的包名，避免宽泛前缀意外影响无关模块。

导入回退是兼容性措施，不是常规配置。只有确认某个第三方包确实无法正常导入时才使用；调用后仍由该包自己的导入错误和依赖要求决定是否成功。

## 惰性加载

惰性加载将导入工作推迟到名称第一次被实际使用时，适合启动阶段并不一定会使用、而导入成本很高的可选依赖，例如图像处理、机器学习或报表库。

### Python 3.15 及以上

Python 3.15 提供语言级的 `lazy` 导入语法。仅支持 Python 3.15+ 的代码优先使用它：

```python
lazy import heavy_module as hm
lazy from heavy_module import build_report

# 首次真正访问时才加载
report = build_report(data)
```

该语法只能放在模块作用域，不能用于函数、类体或 `try`/`except`/`finally` 块；也不能用于星号导入或未来导入。详细限制可参考 [Python 3.15 的 lazy import 说明](https://docs.python.org/3.15/reference/simple_stmts.html#lazy-imports)。

### 兼容 Python 3.10—3.14

项目仍需兼容较早 Python 版本时，使用 {func}`.lazy_load`。在类型检查分支写正常导入，在运行时分支向当前模块的 `globals()` 注册延迟代理：

```python
from typing import TYPE_CHECKING

from melobot import lazy_load

if TYPE_CHECKING:
    import heavy_module as hm
    from heavy_module import build_report
else:
    lazy_load(globals(), "heavy_module", alias="hm")
    lazy_load(globals(), "heavy_module", item="build_report")

# 访问属性或调用对象时触发导入
report = build_report(data)
```

`lazy_load` 覆盖四种常规导入形式：

| 常规导入 | `lazy_load` 调用 |
| --- | --- |
| `import xxx` | `lazy_load(globals(), "xxx")` |
| `import xxx as yyy` | `lazy_load(globals(), "xxx", alias="yyy")` |
| `from xxx import yyy` | `lazy_load(globals(), "xxx", item="yyy")` |
| `from xxx import yyy as zzz` | `lazy_load(globals(), "xxx", item="yyy", alias="zzz")` |

加载完成后，`globals()` 中对应名称会被真实模块或对象替换，之后与普通导入没有区别。在此之前它是代理对象，`repr`、身份比较、序列化等行为可能与真实对象不同；不要依赖这些加载前的行为。`lazy_load` 不支持相对导入，`location` 应为绝对模块路径。

```{admonition} 注意
:class: warning
惰性加载会把 `ImportError` 和模块顶层代码的异常推迟到第一次使用处。对于程序启动时必须可用的依赖，应保持普通导入，让错误尽早暴露。
```

## 总结

`MODULE_EXTS` 用于了解当前平台的模块文件优先级，`add_import_fallback` 仅用于少数第三方包的兼容问题。面对可选的重型依赖，Python 3.15+ 优先采用 `lazy import`；需要兼容旧版本时用 `lazy_load(globals(), ...)`，并保留 `TYPE_CHECKING` 分支以获得正常的类型提示。

下一篇将介绍：[上下文管理](./context)。
