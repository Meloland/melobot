# OneBot 转发消息与消息结点

在前一部分 [OneBot 消息内容的数据结构](./msg) 中我们说明了 OneBot 标准是如何表示**单条 qq 消息中**可能存在的多种类型的内容的（如文本、语音或图片），主要是通过 **CQ 字符串**或**消息段数组**的形式。

但是如果是转发消息这种包含**多条消息**的消息，要如何表示呢？这个时候就需要**转发消息段或消息结点**了。

在 melobot 中，你不需要手动处理“转发消息段”、“消息结点”的数据结构。**虽然无需手动处理，但是了解这些数据结构，有助于你使用 melobot 提供的相关方法**。

## 转发消息段

每一条已存在的转发消息，都对应一个唯一的转发 id。使用转发 id 就可以表示**一条已存在的转发消息**。

两种格式的表示方法：

```json
{
    "type": "forward",
    "data": {
        "id": "xxxxxxxxx"
    }
}
```

```
[CQ:forward,id=xxxxxxxxx]
```

| 参数名 | 收 | 发 | 可能的值 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | ✓ | ✓ | - | 转发 ID |

## 消息结点

```{admonition} 提示
:class: tip
在 OneBot 标准和其他一些文档中，习惯说“消息节点”，这与本文档中的“消息结点”完全是同一概念。
```

除了使用转发 ID 表示已存在的转发消息，我们也可以通过**已存在的单条消息**或**一条新消息**来构造**一条过去不存在的转发消息（新转发消息）**。

此时，**已存在的单条消息**、**一条新消息**都需要用“消息结点”来表示。而消息结点的数组，自然也就可以表示整条“新转发消息”了。消息结点有两种：

- 合并转发结点（对应“已存在的单条消息”，需要消息 ID 来标识）
- 合并转发自定义结点（对应“一条新消息”，这条消息之前完全不存在）

### 合并转发结点

两种格式的表示方法：

```json
{
    "type": "node",
    "data": {
        "id": "123456"
    }
}
```

```
[CQ:node,id=123456]
```

| 参数名 | 收 | 发 | 可能的值 | 说明 |
| --- | --- | --- | --- | --- |
| `id` |  | ✓ | - | 转发的消息 ID |

消息 ID 在 melobot 中可通过消息事件的 {attr}`~.MessageEvent.id` 属性获得。

### 合并转发自定义结点

```{admonition} 提示
:class: tip
合并转发自定义结点的 `content` 字段，可以是“CQ字符串”或“消息段数组”。
```

例子 1：

```json
{
    "type": "node",
    "data": {
        "user_id": "10001000",
        "nickname": "某人",
        "content": "[CQ:face,id=123]哈喽～"
    }
}
```

```
[CQ:node,user_id=10001000,nickname=某人,content=&#91;CQ:face&#44;id=123&#93;哈喽～]
```

例子 2：

```json
{
    "type": "node",
    "data": {
        "user_id": "10001000",
        "nickname": "某人",
        "content": [
            {"type": "face", "data": {"id": "123"}},
            {"type": "text", "data": {"text": "哈喽～"}}
        ]
    }
}
```

| 参数名 | 收 | 发 | 可能的值 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | ✓ | ✓ | - | 发送者 QQ 号 |
| `nickname` | ✓ | ✓ | - | 发送者昵称 |
| `content` | ✓ | ✓ | - | 消息内容，即上一章所述的[单条消息内容](./msg) |

## melobot 中的表示

在 melobot 中，转发消息段、消息结点都属于消息段的类别。
