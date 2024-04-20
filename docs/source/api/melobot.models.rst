:tocdepth: 3

melobot.models
==============

.. _event-type:

事件类型
--------

melobot 主要包含五种事件类型：:class:`.MessageEvent`, :class:`.RequestEvent`, :class:`.NoticeEvent`, 
:class:`.ResponseEvent`, :class:`.MetaEvent`。

.. autoclass:: melobot.models.MessageEvent
   :members:
   :show-inheritance:
   :exclude-members: __init__

.. autoclass:: melobot.models.RequestEvent
   :members:
   :show-inheritance:
   :exclude-members: __init__

.. autoclass:: melobot.models.NoticeEvent
   :members:
   :show-inheritance:
   :exclude-members: __init__

.. autoclass:: melobot.models.ResponseEvent
   :members:
   :show-inheritance:
   :exclude-members: __init__

.. autoclass:: melobot.models.MetaEvent
   :members:
   :show-inheritance:
   :exclude-members: __init__

.. _msg-build:

消息构造
----------------

在 melobot 中，使用以下函数构造符合 onebot 标准的消息段。不过部分标准中的方法没有被包含，同时部分方法有所改变。

.. autofunction:: melobot.models.text_msg

.. autofunction:: melobot.models.face_msg

.. autofunction:: melobot.models.record_msg

.. autofunction:: melobot.models.at_msg

.. autofunction:: melobot.models.share_msg

.. autofunction:: melobot.models.music_msg

.. autofunction:: melobot.models.custom_music_msg

.. autofunction:: melobot.models.image_msg

.. autofunction:: melobot.models.reply_msg

.. autofunction:: melobot.models.poke_msg

.. autofunction:: melobot.models.xml_msg

.. autofunction:: melobot.models.json_msg

.. autofunction:: melobot.models.custom_msg_node

.. autofunction:: melobot.models.refer_msg_node

.. autofunction:: melobot.models.forward_msg

自定义消息内容
--------------

该方法可构造自定义的消息段对象，实现自定义的消息段。

.. autofunction:: melobot.models.custom_type_msg

消息内容处理
---------------

使用以下函数可以处理消息内容，例如进行消息格式转换或实现特定的处理。

.. admonition:: 提示
   :class: tip

   这些函数过于底层，在 melobot 实际使用中并不常用。有所了解即可。

.. autofunction:: melobot.models.cq_filter_text

.. autofunction:: melobot.models.cq_escape

.. autofunction:: melobot.models.cq_anti_escape

.. autofunction:: melobot.models.to_segments

.. autofunction:: melobot.models.to_cq_str
