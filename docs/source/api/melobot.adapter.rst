melobot.adapter
===============

适配器层组件
------------------

.. autoclass:: melobot.adapter.Adapter
    :members:
    :inherited-members:
    :exclude-members: __init__

.. autoclass:: melobot.adapter.AdapterLifeSpan
    :members:

.. autoclass:: melobot.adapter.AbstractEventFactory
    :members:

.. autoclass:: melobot.adapter.AbstractOutputFactory
    :members:

.. autoclass:: melobot.adapter.AbstractEchoFactory
    :members:

实体基类
-------------

.. autoclass:: melobot.adapter.Event
    :members:
    :exclude-members: __init__

.. autoclass:: melobot.adapter.TextEvent
    :members:
    :exclude-members: __init__

.. autoclass:: melobot.adapter.Action
    :members:
    :exclude-members: __init__

.. autoclass:: melobot.adapter.Echo
    :members:
    :exclude-members: __init__

行为实体相关部件
-------------------

.. autoclass:: melobot.adapter.ActionHandle
    :members:
    :exclude-members: __init__, execute

.. autoclass:: melobot.adapter.ActionChain
    :members:
    :exclude-members: __init__

.. autofunction:: melobot.adapter.open_chain

通用实体内容
---------------

.. autoclass:: melobot.adapter.content.Content
    :members:

.. autoclass:: melobot.adapter.content.TextContent
    :members:

.. autoclass:: melobot.adapter.content.MediaContent
    :members:

.. autoclass:: melobot.adapter.content.ImageContent
    :members:

.. autoclass:: melobot.adapter.content.AudioContent
    :members:

.. autoclass:: melobot.adapter.content.VoiceContent
    :members:

.. autoclass:: melobot.adapter.content.VideoContent
    :members:

.. autoclass:: melobot.adapter.content.FileContent
    :members:

.. autoclass:: melobot.adapter.content.ReferContent
    :members:

.. autoclass:: melobot.adapter.content.ResourceContent
    :members:

通用输出方法
--------------

.. autofunction:: melobot.adapter.generic.send_text

.. autofunction:: melobot.adapter.generic.send_media

.. autofunction:: melobot.adapter.generic.send_image

.. autofunction:: melobot.adapter.generic.send_audio

.. autofunction:: melobot.adapter.generic.send_voice

.. autofunction:: melobot.adapter.generic.send_video

.. autofunction:: melobot.adapter.generic.send_file

.. autofunction:: melobot.adapter.generic.send_refer

.. autofunction:: melobot.adapter.generic.send_resource
