# OneBot 协议和实现

melobot 无法作为客户端直接与服务器直接通信。因此需要一个“媒介”作为客户端与服务器通信，melobot 与此“媒介”交流，即可间接完成与服务器的互动，例如收发平台消息，获取平台通知等。

在 melobot 中内置支持 OneBot 协议，因此后续与“媒介”的数据交换可以遵循 [OneBot-v11 协议](https://github.com/botuniverse/onebot-11/tree/master)。OneBot 协议规定的标准，被称为 OneBot 标准。实现 OneBot 协议，满足 OneBot 标准的“媒介”，被称为“OneBot 实现”或“OneBot 实现程序”。

具体的 OneBot 实现项目有很多种。此处不列出这些项目。您应该有能力自行找到它们，并学习它们的配置方法。

```{admonition} 郑重声明
:class: attention
**melobot 从始至终，只支持您使用出于学习交流形式传播和使用的 OneBot 实现端**。若您使用了包括但不限于侵犯版权、商标、商业机密或其他知识产权，以及违反任何适用的法律和法规的实现端进行开发，melobot 团队及其所有开发者成员，均不对因非法使用对应实现端而产生的任何直接、间接、附带、特殊、惩罚性或后果性损害承担责任。
```
