:tocdepth: 3

melobot.context
===============

会话
----------------------

会话是 melobot 的重要机制之一。以下是涉及会话控制和会话信息获取的相关类和函数：

.. autoclass:: melobot.context.AttrSessionRule
   :members:
   :show-inheritance:
   :exclude-members: compare

.. autofunction:: melobot.context.any_event

.. autofunction:: melobot.context.msg_event

.. autofunction:: melobot.context.msg_args

.. autofunction:: melobot.context.msg_text

.. autofunction:: melobot.context.req_event

.. autofunction:: melobot.context.notice_event

.. autofunction:: melobot.context.meta_event

.. autofunction:: melobot.context.get_store

.. autofunction:: melobot.context.pause

.. autofunction:: melobot.context.dispose

高级行为操作
-------------
在 melobot 中，所有行为都是 :class:`.BotAction` 类的实例对象。
调用行为操作函数，即可生成 :class:`.BotAction` 对象并自动发送一个行为。

所有行为操作分为两大类：高级行为操作与基本行为操作。

高级行为操作是 melobot 在 onebot 标准的基础上，利用会话信息进一步封装的行为操作。
以下函数均为高级行为操作函数：

.. autofunction:: melobot.context.send

.. autofunction:: melobot.context.send_forward

.. autofunction:: melobot.context.send_wait

.. autofunction:: melobot.context.send_reply

.. autofunction:: melobot.context.finish

.. autofunction:: melobot.context.reply_finish

.. _action-operations:

基本行为操作
------------------

基本行为操作是与 onebot 标准中的“API 接口”相吻合的行为操作。

注意部分 onebot API 接口在 melobot 中未提供支持：

.. admonition:: 注意
   :class: caution

   在 `onebot 标准 <https://github.com/botuniverse/onebot-11/blob/master/api/public.md>`_ 中，以下不常用或难以被 onebot 实现项目实现的行为操作暂时不支持：

      - set_group_anonymous_ban 群组匿名用户禁言
      - set_group_anonymous 群组匿名
      - get_cookies 获取 Cookies
      - get_csrf_token 获取 CSRF Token
      - get_credentials 获取 QQ 相关接口凭证
      - set_restart 重启 OneBot 实现
      - clean_cache 清理缓存

另外为提升 API 接口可读性，部分接口名称与 onebot 标准不同，请注意辨别。还有部分接口被合并（如发送私聊消息与发送群聊消息） 

.. autofunction:: melobot.context.send_custom_msg

.. autofunction:: melobot.context.send_custom_forward

.. autofunction:: melobot.context.msg_recall

.. autofunction:: melobot.context.get_msg

.. autofunction:: melobot.context.get_forward_msg

.. autofunction:: melobot.context.get_image

.. autofunction:: melobot.context.send_like

.. autofunction:: melobot.context.group_kick

.. autofunction:: melobot.context.group_ban

.. autofunction:: melobot.context.group_whole_ban

.. autofunction:: melobot.context.set_group_admin

.. autofunction:: melobot.context.set_group_card

.. autofunction:: melobot.context.set_group_name

.. autofunction:: melobot.context.group_leave

.. autofunction:: melobot.context.set_group_title

.. autofunction:: melobot.context.set_friend_add

.. autofunction:: melobot.context.set_group_add

.. autofunction:: melobot.context.get_login_info

.. autofunction:: melobot.context.get_stranger_info

.. autofunction:: melobot.context.get_friend_list

.. autofunction:: melobot.context.get_group_info

.. autofunction:: melobot.context.get_group_list

.. autofunction:: melobot.context.get_group_member_info

.. autofunction:: melobot.context.get_group_member_list

.. autofunction:: melobot.context.get_group_honor

.. autofunction:: melobot.context.check_send_image

.. autofunction:: melobot.context.check_send_record

.. autofunction:: melobot.context.get_onebot_version

.. autofunction:: melobot.context.get_onebot_status

手动行为操作
-----------------

如果需要手动处理行为对象，而不是创建后立即执行，令以上函数的 `auto` 参数为 :obj:`False`，函数即可返回行为对象。
处理完毕后可通过以下函数触发发送操作：

.. autofunction:: melobot.context.take_custom_action

如果因为兼容性问题，你需要创建 melobot 预置行为操作函数无法创建的 onebot 标准行为，可以使用以下函数生成自定义的行为对象：

随后这个行为可以通过 :func:`.take_custom_action` 处理。

.. autofunction:: melobot.context.make_action
