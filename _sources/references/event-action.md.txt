# 事件和行为

事件和行为是 melobot 和 [OneBot 标准](https://github.com/botuniverse/onebot-11/tree/master)中最重要的概念。melobot 内部的工作，总结下来也就四步：

1. 接收来自 OneBot 实现程序的“事件”，封装为 melobot 事件
2. 处理“事件”，产生“行为”
4. 序列化 melobot 行为，交由 OneBot 实现程序执行

“事件”：**OneBot 实现项目向 melobot 的数据上报**；

“行为”：**发送给 OneBot 实现程序的，交由 OneBot 实现程序执行的操作**。

若无特别说明，本文档直接提及“事件”、“行为”等词汇均是以上含义。

## 事件类型

在 OneBot 标准中，事件有[四种类型](https://github.com/botuniverse/onebot-11/blob/master/event/README.md)。对应标准，melobot 所有事件类型如下：

- 消息事件：{class}`.MessageEvent`（事件处理方法中使用 {func}`.msg_event` 获得）
- 请求事件：{class}`.RequestEvent`（事件处理方法中使用 {func}`.req_event` 获得）
- 通知事件：{class}`.NoticeEvent`（事件处理方法中使用 {func}`.notice_event` 获得）
- 元事件：{class}`.MetaEvent`（事件处理方法中使用 {func}`.meta_event` 获得）

## 行为与行为操作

在 OneBot 标准中，行为通过不同的“类型标识”，产生了多种类型。在 melobot 中，各种各样行为的产生，主要由不同的“行为操作函数”完成，各种“行为操作函数”具体可以参阅：[行为操作函数](#action-operations)。

行为操作函数会产生一个行为操作，这个操作会通过它的返回值 {class}`.ActionHandle`（行为操作对象）描述。通过行为操作对象，我们可以对行为操作的流程（`行为生成、行为执行、行为响应等待`）进行更精细的处理。

## 行为响应

行为响应是 melobot 将行为操作提交给 OneBot 实现程序后，等待执行完成后返回的结果。响应**被用来检查行为是否被正确处理，或被用来获取返回数据**。响应在 melobot 中的数据类型是：{class}`.ActionResponse`。例如：“获取 bot 加入的所有群的群号”这个行为操作，它的返回数据就包含在行为响应中。

## 总结

此部分只负责对事件和行为的概念进行解释。具体用法和其他细节，将会在教程部分详细说明。
