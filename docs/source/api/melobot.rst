melobot
=======

melobot 顶级对象与方法
------------------------

.. autofunction:: melobot.lazy_load

.. autofunction:: melobot.add_import_fallback

.. data:: melobot.MODULE_EXTS

    模块扩展名元组，包含当前平台所有可加载的模块扩展名。优先级从高到低，且与操作系统平台有关

.. autofunction:: melobot.install_exc_hook

.. autofunction:: melobot.uninstall_exc_hook

.. autofunction:: melobot.set_traceback_style

melobot 元信息
-----------------

.. autoclass:: melobot.MetaInfo
    :exclude-members: __init__

.. autoclass:: melobot._meta.VersionInfo
    :exclude-members: __new__
