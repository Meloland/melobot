import re
from copy import deepcopy
from itertools import chain, zip_longest

from ..types.exceptions import BotActionError
from ..types.typing import (
    TYPE_CHECKING,
    Any,
    CQMsgDict,
    Literal,
    MsgNodeDict,
    Optional,
    Type,
)

if TYPE_CHECKING:
    from ..types.abc import BotAction


def text_msg(
    text: str,
) -> CQMsgDict:
    """
    普通文本消息
    """
    return {"type": "text", "data": {"text": text}}


def face_msg(
    icon_id: int,
) -> CQMsgDict:
    """
    QQ 表情
    """
    return {"type": "face", "data": {"id": f"{icon_id}"}}


def audio_msg(
    url: str,
    timeout: Optional[int] = None,
    magic: bool = False,
) -> CQMsgDict:
    """
    语音消息
    """
    base: CQMsgDict = {
        "type": "record",
        "data": {
            "file": url,
        },
    }
    if magic:
        base["data"]["magic"] = 1
    if timeout:
        base["data"]["timeout"] = str(timeout)
    return base


def at_msg(
    qqId: int | Literal["all"],
    notInName: Optional[str] = None,
) -> CQMsgDict:
    """
    at 消息。
    at 所有人时，`qqId` 传 "all"
    """
    base: CQMsgDict = {
        "type": "at",
        "data": {
            "qq": str(qqId),
        },
    }
    if notInName:
        base["data"]["name"] = notInName
    return base


def share_msg(
    url: str,
    title: str,
    content: Optional[str] = None,
    image: Optional[str] = None,
) -> CQMsgDict:
    """
    链接分享卡片消息。
    `content` 为描述语
    """
    base: CQMsgDict = {
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
    platType: Literal["qq", "163", "xm"],
    songId: str,
) -> CQMsgDict:
    """
    音乐分享卡片消息（专有平台）
    """
    return {"type": "music", "data": {"type": platType, "id": songId}}


def custom_music_msg(
    url: str,
    audio: str,
    title: str,
    content: Optional[str] = None,
    image: Optional[str] = None,
) -> CQMsgDict:
    """
    自定义音乐分享卡片。
    `url` 为主页或网站起始页
    """
    base: CQMsgDict = {
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
    url: str,
    picType: Optional[Literal["flash", "show"]] = None,
    subType: Optional[Literal[0, 1]] = None,
    useCache: Literal[0, 1] = 1,
) -> CQMsgDict:
    """
    图片消息。
    `url`: 图片 url。可以为本地路径，如：`file:///C:/users/15742/desktop/QQ图片20230108225606.jpg`；也可以为网络 url；还可以为 image id。
    `picType`: flash 为闪照，show 为秀图，不填为普通图片。
    `subType`: 只出现在群聊，0 为正常图片，1 为表情包
    """
    base: CQMsgDict = {
        "type": "image",
        "data": {
            "file": url,
        },
    }
    if picType:
        base["data"]["type"] = picType
    if subType:
        base["data"]["subType"] = str(subType)
    if useCache:
        base["data"]["cache"] = str(useCache)
    return base


def reply_msg(
    messageId: int,
) -> CQMsgDict:
    """
    回复消息
    """
    return {
        "type": "reply",
        "data": {
            "id": str(messageId),
        },
    }


def poke_msg(
    qqId: int,
) -> CQMsgDict:
    """
    戳一戳消息
    """
    return {
        "type": "poke",
        "data": {
            "qq": str(qqId),
        },
    }


def touch_msg(
    qqId: int,
) -> CQMsgDict:
    """
    openshamrock 的戳一戳消息
    """
    return {
        "type": "touch",
        "data": {
            "id": str(qqId),
        },
    }


def tts_msg(
    text: str,
) -> CQMsgDict:
    """
    腾讯自带 tts 语音消息
    """
    return {
        "type": "tts",
        "data": {
            "text": text,
        },
    }


def custom_msg_node(
    content: str | CQMsgDict | list[CQMsgDict],
    sendName: str,
    sendId: int,
    seq: Optional[list[CQMsgDict]] = None,
) -> MsgNodeDict:
    """
    自定义消息节点构造方法。转化字符串、消息、消息段为消息节点
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
    ret: MsgNodeDict = {
        "type": "node",
        "data": {"name": sendName, "uin": str(sendId), "content": msgs},
    }
    if seq:
        ret["data"]["seq"] = seq  # type: ignore
    return ret


def refer_msg_node(msgId: int) -> MsgNodeDict:
    """
    引用消息节点构造方法
    """
    return {"type": "node", "data": {"id": str(msgId)}}


def cq_filter_text(s: str) -> str:
    """
    从 cq 消息字符串中，获取纯净的 cq text 类型消息
    """
    regex = re.compile(r"\[CQ:.*?\]")
    return regex.sub("", s)


def cq_escape(text: str) -> str:
    """
    cq 码特殊字符转义
    """
    return (
        text.replace("&", "&amp;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
        .replace(",", "&#44;")
    )


def cq_anti_escape(text: str) -> str:
    """
    cq 码特殊字符逆转义
    """
    return (
        text.replace("&#44;", ",")
        .replace("&#93;", "]")
        .replace("&#91;", "[")
        .replace("&amp;", "&")
    )


def to_cq_arr(s: str) -> list[CQMsgDict]:
    """
    从 cq 消息字符串转换为 cq 消息段
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


def to_cq_str(content: list[CQMsgDict]) -> str:
    """
    从 cq 消息段转换为 cq 消息字符串
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


def to_cq_str_action(action: "BotAction") -> "BotAction":
    """
    转化 action 携带的 message 字段转为 cq 字符串格式，并返回新的 action。
    支持的 action 类型有：msg_action 和 forward_action
    """

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


def get_cq(content: list[CQMsgDict], cq_type: str) -> list[CQMsgDict]:
    """
    从 content 获取指定类型的 cq 消息 dict
    """
    return [item for item in content if item["type"] == cq_type]


def get_cq_params(
    content: list[CQMsgDict], cq_type: str, param: str, type: Optional[Type[Any]] = None
) -> list[Any]:
    """
    从当前 content 中获取指定类型 cq 消息的指定 param，以列表形式返回。
    当没有任何对应类型的 cq 消息时，为空列表。如果有对应类型 cq 消息，
    但是 param 不存在，则在列表中产生值 None

    可以指定 type 来强制转换类型
    """
    res: list[Any] = []
    for item in content:
        if item["type"] == cq_type:
            val = item["data"].get(param)
            res.append(val)
    if type is not None:
        res = list(map(lambda x: type(x), res))
    return res
