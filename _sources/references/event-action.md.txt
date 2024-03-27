# 事件和行为

事件和行为是 melobot 和 [OneBot 标准](https://github.com/botuniverse/onebot-11/tree/master)中最重要的概念。melobot 内部的工作，总结下来也就四步：

1. 接收来自 OneBot 实现程序的“事件”，并格式化
2. 处理“事件”
3. 产生“行为”
4. “行为”格式化，并交由 OneBot 实现程序完成

“事件”：**OneBot 实现项目上报给 melobot 的事件**；

“行为”或“行为操作”：**发送给 OneBot 实现程序的，交由 OneBot 实现程序完成的操作**。

若无特别说明，本文档直接提及“事件”、“行为”、“行为操作”等词汇均是以上含义。

## 事件类型

在 OneBot 标准中，事件有[四种类型](https://github.com/botuniverse/onebot-11/blob/master/event/README.md)。而在 melobot 中，为方便使用，额外了添加一种事件类型。melobot 所有事件类型如下：

- 消息事件：{class}`.MessageEvent`
- 请求事件：{class}`.RequestEvent`
- 通知事件：{class}`.NoticeEvent`
- 元事件：{class}`.MetaEvent`
- 响应事件：{class}`.ResponseEvent`

前四种事件类型都是 OneBot 标准中的类型，它们都是 OneBot 实现程序上报事件给 melobot 后，经过格式化后产生的。但是最后一种事件，响应事件，情况有所不同。它是 melobot 内部产生行为后，发送给 OneBot 实现程序，等待 OneBot 完成这个行为后的“响应”。

通过响应事件，可以检查行为有没有被正确完成，或者获得某些行为的返回数据。例如：某个行为是“获取 bot 加入的所有群的群号”，这个行为的返回数据就会通过响应事件来传输。

## 行为类型

在 OneBot 标准中，行为通过不同的“类型标识”，产生了多种类型。在 melobot 中，各种各样行为的产生，主要由不同的“行为操作函数”完成，具体可以参阅：[行为操作函数](#action-operations)。
