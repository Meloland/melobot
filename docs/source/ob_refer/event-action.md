# OneBot 事件、行为和回应

## 事件

在 OneBot 标准中，事件有[四种类型](https://github.com/botuniverse/onebot-11/blob/master/event/README.md)。对应标准，melobot OneBot 支持中有以下事件：

- 消息事件：{class}`.MessageEvent`
- 请求事件：{class}`.RequestEvent`
- 通知事件：{class}`.NoticeEvent`
- 元事件：{class}`.MetaEvent`

## 行为与行为操作

在 OneBot 标准中，行为通过不同的“类型标识”，产生了多种类型。在 melobot 的 OneBot 支持中，行为操作由 {class}`~.onebot.v11.Adapter` 的各种方法完成。

行为操作一般会返回一个操作句柄组（{class}`.ActionHandleGroup`）。通过操作句柄组我们可以进行更精细的处理：等待操作，等待操作返回的响应数据等。

## 回应

OneBot 的回应在 melobot 中的数据类型是：{class}`~.onebot.v11.adapter.echo.Echo`。

## 总结

此部分只负责对事件、行为和回应的概念进行解释。具体用法和其他细节，将会在教程部分详细说明。
