import re
from copy import deepcopy
from itertools import chain, zip_longest

from ..base.exceptions import BotActionError
from ..base.typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    MsgNode,
    MsgSegment,
    Optional,
)

if TYPE_CHECKING:
    from ..base.abc import BotAction


__all__ = (
    "at_msg",
    "cq_anti_escape",
    "cq_escape",
    "cq_filter_text",
    "custom_msg_node",
    "custom_music_msg",
    "face_msg",
    "image_msg",
    "json_msg",
    "music_msg",
    "poke_msg",
    "record_msg",
    "refer_msg_node",
    "reply_msg",
    "share_msg",
    "text_msg",
    "to_cq_arr",
    "to_cq_str",
    "xml_msg",
    "custom_type_msg",
    "forward_msg",
)


def text_msg(
    text: str,
) -> MsgSegment:
    """生成普通文本消息

    参数详细说明参考 onebot 标准：`纯文本 <https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#纯文本>`_

    :param text: 文本内容
    :return: onebot 标准中的消息段对象
    """
    return {"type": "text", "data": {"text": text}}


def face_msg(
    id: int,
) -> MsgSegment:
    """生成 qq 表情消息

    参数详细说明参考 onebot 标准：`QQ 表情 <https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#qq-表情>`_

    :param id: qq 表情的 ID
    :return: onebot 标准中的消息段对象
    """
    return {"type": "face", "data": {"id": f"{id}"}}


def record_msg(
    file: str,
    magic: Literal[0, 1] = 0,
    cache: Literal[0, 1] = 1,
    proxy: Literal[0, 1] = 1,
    timeout: Optional[int] = None,
) -> MsgSegment:
    """生成语音消息

    参数详细说明参考 onebot 标准：`语音 <https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#语音>`_

    :param file: 语音文件名
    :param magic: 是否使用变声
    :param cache: 是否使用已缓存文件
    :param proxy: 是否通过代理下载文件
    :param timeout: 超时时间，默认不启用
    :return: onebot 标准中的消息段对象
    """
    base: MsgSegment = {
        "type": "record",
        "data": {
            "file": file,
            "magic": str(magic),
            "cache": str(cache),
            "proxy": str(proxy),
        },
    }
    if timeout:
        base["data"]["timeout"] = str(timeout)
    return base


def at_msg(qq: int | Literal["all"]) -> MsgSegment:
    """生成艾特消息

    参数详细说明参考 onebot 标准：`某人 <https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#某人>`_

    :param qq: 艾特的 qq 号，"all" 表示艾特全体成员
    :return: onebot 标准中的消息段对象
    """
    base: MsgSegment = {
        "type": "at",
        "data": {
            "qq": str(qq),
        },
    }
    return base


def share_msg(
    url: str,
    title: str,
    content: Optional[str] = None,
    image: Optional[str] = None,
) -> MsgSegment:
    """生成链接分享消息

    参数详细说明参考 onebot 标准：`链接分享 <https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#链接分享>`_

    :param url: 链接的 url
    :param title: 消息的标题
    :param content: 消息的内容描述（可选）
    :param image: 消息的封面图 url（可选）
    :return: onebot 标准中的消息段对象
    """
    base: MsgSegment = {
        "type": "share",
        "data": {
            "url": url,
            "title": title,
        },
    }
    if content:
        base["data"]["content"] = content
    if image:
        base["data"]["image"] = image
    return base


def music_msg(
    type: Literal["qq", "163", "xm"],
    id: str,
) -> MsgSegment:
    """生成音乐分享消息

    参数详细说明参考 onebot 标准：`音乐分享 <https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#音乐分享->`_

    :param type: 音乐平台的类型（q 音、网易云、虾米）
    :param id: 歌曲 id
    :return: onebot 标准中的消息段对象
    """
    return {"type": "music", "data": {"type": type, "id": id}}


def custom_music_msg(
    url: str,
    audio: str,
    title: str,
    content: Optional[str] = None,
    image: Optional[str] = None,
) -> MsgSegment:
    """生成音乐自定义分享 url

    参数详细说明参考 onebot 标准：`音乐自定义分享 <https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#音乐自定义分享->`_

    :param url: 点击后跳转目标 url
    :param audio: 音乐 url
    :param title: 标题
    :param content: 内容描述（可选）
    :param image: 封面图 url（可选）
    :return: onebot 标准中的消息段对象
    """
    base: MsgSegment = {
        "type": "music",
        "data": {
            "type": "custom",
            "url": url,
            "audio": audio,
            "title": title,
        },
    }
    if content:
        base["data"]["content"] = content
    if image:
        base["data"]["image"] = image
    return base


def image_msg(
    file: str,
    type: Optional[Literal["flash"]] = None,
    cache: Literal[0, 1] = 1,
    proxy: Literal[0, 1] = 1,
    timeout: Optional[int] = None,
) -> MsgSegment:
    """生成图片消息

    参数详细说明参考 onebot 标准：`图片 <https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#图片>`_

    :param file: 图片文件名或图片 base64 内容
    :param type: 图片类型
    :param cache: 是否使用已缓存的文件
    :param proxy: 是否通过代理下载文件
    :param timeout: 超时时间，默认不超时
    :return: onebot 标准中的消息段对象
    """
    base: MsgSegment = {
        "type": "image",
        "data": {
            "file": file,
            "cache": str(cache),
            "proxy": str(proxy),
        },
    }
    if type:
        base["data"]["type"] = type
    if timeout:
        base["data"]["timeout"] = str(timeout)
    return base


def reply_msg(
    id: int,
) -> MsgSegment:
    """生成回复消息

    参数详细说明参考 onebot 标准：`回复 <https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#回复>`_

    :param id: 消息 id
    :return: onebot 标准中的消息段对象
    """
    return {
        "type": "reply",
        "data": {
            "id": str(id),
        },
    }


def poke_msg(
    qq: int,
) -> MsgSegment:
    """生成戳一戳消息

    .. admonition:: 提示
       :class: tip

       鉴于目前大多数实现 cq 协议的项目都采用了此参数规范，因此在 melobot 中，也采用此规范。虽然这种规范实际上不符合 onebot 标准

    :param qq: 戳的 qq 号
    :return: onebot 标准中的消息段对象
    """
    return {
        "type": "poke",
        "data": {
            "qq": str(qq),
        },
    }


def xml_msg(data: str) -> MsgSegment:
    """生成 xml 消息

    参数详细说明参考 onebot 标准：`xml 消息 <https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#xml-消息>`_

    :param data: xml 内容
    :return: onebot 标准中的消息段对象
    """
    return {"type": "xml", "data": {"data": data}}


def json_msg(data: str) -> MsgSegment:
    """生成 json 消息

    参数详细说明参考 onebot 标准：`json 消息 <https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#json-消息>`_

    :param data: json 内容
    :return: onebot 标准中的消息段对象
    """
    return {"type": "json", "data": {"data": data}}


def forward_msg(forwardId: str) -> MsgSegment:
    """生成一条完整的转发消息，以消息段的形式

    .. admonition:: 注意
       :class: caution

       这与通过结点来构造转发消息是不同的，这里直接构造一个消息段对象，就可以代表整条转发消息。
       因为这里使用的是转发 id。

    参数详细说明参考 onebot 标准：`forward 消息段 <https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#合并转发->`_

    :param forwardId: 转发 id
    :return: onebot 标准中的消息段对象
    """
    return {"type": "forward", "data": {"id": str(forwardId)}}


def custom_msg_node(
    content: str | MsgSegment | list[MsgSegment],
    sendName: str,
    sendId: int,
    seq: Optional[list[MsgSegment]] = None,
    useStd: bool = False,
) -> MsgNode:
    """生成一个自定义合并消息转发结点

    .. admonition:: 提示
       :class: tip

       鉴于此方法涉及的消息构造，存在两种规范：
       `onebot 规范 <https://github.com/botuniverse/onebot-11/blob/master/message/segment.md#合并转发自定义节点>`_、
       `go-cq 规范 <https://docs.go-cqhttp.org/cqcode/#合并转发消息节点>`_，
       因此在 melobot 中，支持你使用 useStd 参数自定义选择哪种风格来构造

    :param content: 消息结点内容
    :param sendName: 消息结点标记的发送人名字
    :param sendId: 消息结点标记的发送人 qq 号
    :param seq: 消息 seq 号（一般来说你不需要使用这个）
    :param useStd: 消息段对象构造时是否遵循 onebot 标准，默认为否（使用 go-cq 风格）
    :return: onebot 标准中的消息段对象
    """
    if isinstance(content, str):
        _ = text_msg(content)
        if not isinstance(_, list):
            msgs = [_]
    elif isinstance(content, dict):
        msgs = [content]
    elif isinstance(content, list):
        temp = []
        for _ in content:
            if isinstance(_, list):
                temp.extend(_)
            else:
                temp.append(_)
        msgs = temp
    if not useStd:
        ret: MsgNode = {
            "type": "node",
            "data": {"name": sendName, "uin": str(sendId), "content": msgs},
        }
    else:
        ret: MsgNode = {  # type: ignore
            "type": "node",
            "data": {"user_id": sendId, "nickname": sendName, "content": msgs},
        }
    if seq:
        ret["data"]["seq"] = seq  # type: ignore
    return ret


def refer_msg_node(id: int) -> MsgNode:
    """生成一个引用合并消息转发结点

    :param id: 消息 id
    :return: onebot 标准中的消息段对象
    """
    return {"type": "node", "data": {"id": str(id)}}


def custom_type_msg(type: str, params: dict[str, str]) -> MsgSegment:
    """生成一个自定义消息段对象

    :param type: 消息段对象的类型标识
    :param params: 消息段的参数
    :return: 符合 onebot 格式，但不在 onebot 标准中的消息段对象
    """
    ret: MsgSegment = {"type": type, "data": {}}
    for k, v in params.items():
        ret["data"][k] = str(v)
    return ret


def cq_filter_text(s: str) -> str:
    """cq 文本过滤函数

    可从 cq 字符串中过滤出纯文本消息部分

    :param s: cq 字符串
    :return: 纯文本消息部分
    """
    regex = re.compile(r"\[CQ:.*?\]")
    return regex.sub("", s)


def cq_escape(text: str) -> str:
    """cq 字符串特殊符号转义

    如：将 "&" 转义为 "&amp;"

    :param text: 需要转义的 cq 字符串
    :return: 转义特殊符号后的 cq 字符串
    """
    return (
        text.replace("&", "&amp;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
        .replace(",", "&#44;")
    )


def cq_anti_escape(text: str) -> str:
    """cq 字符串特殊符号逆转义

    如：将 "&amp;" 逆转义为 "&"

    :param text: 需要逆转义的 cq 字符串
    :return: 逆转义特殊符号后的 cq 字符串
    """
    return (
        text.replace("&#44;", ",")
        .replace("&#93;", "]")
        .replace("&#91;", "[")
        .replace("&amp;", "&")
    )


def to_cq_arr(s: str) -> list[MsgSegment]:
    """将 cq 字符串转换为消息段对象列表

    :param s: cq 字符串
    :return: 消息段对象列表
    """

    def replace_func(m) -> str:
        s, e = m.regs[0]
        cq_texts.append(m.string[s:e])
        return "\u0000"

    cq_regex = re.compile(r"\[CQ:.*?\]")
    cq_texts: list[str] = []
    no_cq_str = cq_regex.sub(replace_func, s)
    pure_texts = map(
        lambda x: f"[CQ:text,text={x}]" if x != "" else x,
        no_cq_str.split("\u0000"),
    )
    _: str = "".join(
        chain.from_iterable(zip_longest(pure_texts, cq_texts, fillvalue=""))
    )

    cq_entity: list[str] = _.split("]")[:-1]
    content: list = []
    for e in cq_entity:
        __ = e.split(",")
        cq_type = __[0][4:]
        data: dict[str, float | int | str] = {}
        for param_pair in __[1:]:
            name, val = param_pair.split("=")
            if cq_type != "text":
                val = cq_anti_escape(val)
            if val.isdigit() or (len(val) >= 2 and val[0] == "-" and val[1:].isdigit()):
                data[name] = int(val)
                continue
            try:
                data[name] = float(val)
            except Exception:
                data[name] = val
        content.append({"type": cq_type, "data": data})
    return content


def to_cq_str(content: list[MsgSegment]) -> str:
    """将消息段对象列表转换为 cq 字符串

    :param content: 消息段对象列表
    :return: cq 字符串
    """
    if isinstance(content, str):
        return content
    msgs: list[str] = []
    for item in content:
        if item["type"] == "text":
            msgs.append(item["data"]["text"])  # type: ignore
            continue
        s = f"[CQ:{item['type']}"
        for k, v in item["data"].items():
            s += f",{k}={cq_escape(str(v))}"
        s += "]"
        msgs.append(s)
    return "".join(msgs)


def _to_cq_str_action(action: "BotAction") -> "BotAction":
    def _format_msg_action(action: "BotAction") -> None:
        action.params["message"] = to_cq_str(action.params["message"])

    def _format_forward_action(action: "BotAction") -> None:
        for item in action.params["messages"]:
            if "id" in item["data"].keys():
                continue
            item["data"]["content"] = to_cq_str(item["data"]["content"])

    _action = deepcopy(action)
    if _action.type == "send_msg":
        _format_msg_action(_action)
    elif _action.type in ("send_private_forward_msg", "send_group_forward_msg"):
        _format_forward_action(_action)
    else:
        raise BotActionError("传入的 action 因类型不匹配，不可被 cq 序列化")
    return _action


def _get_cq(content: list[MsgSegment], cq_type: str) -> list[MsgSegment]:
    return [item for item in content if item["type"] == cq_type]


def _get_cq_params(
    content: list[MsgSegment],
    cq_type: str,
    param: str,
    type: Optional[Callable[[Any], Any]] = None,
) -> list[Any]:
    res: list[Any] = []
    for item in content:
        if item["type"] == cq_type:
            val = item["data"].get(param)
            res.append(val)
    if type is not None:
        res = list(map(lambda x: type(x), res))
    return res
