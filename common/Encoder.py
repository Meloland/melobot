from itertools import chain, zip_longest
from .Typing import *
import re


def escape(text: str) -> str:
    """
    cq 码特殊字符转义
    """
    return text.replace('&', '&amp;')\
                .replace('[', '&#91;')\
                .replace(']', '&#93;')\
                .replace(',', '&#44;')


def anti_escape(text: str) -> str:
    """
    cq 码特殊字符逆转义
    """
    return text.replace('&amp;', '&')\
                .replace('&#91;', '[')\
                .replace('&#93;', ']')\
                .replace('&#44;', ',')


def text(
    text: str,
) -> Msg:
    """
    普通文本消息。
    """
    face_list = []
    union_res = []
    def save_and_remark(matched: re.Match) -> str:
        face_list.append({
            "type": "face",
            "data": {
                "id": matched.group(1),
            }
        })
        return "&pos;"
    
    if '[CQ:face' not in text:
        return {
            "type": "text",
            "data": {
                "text": text,
            }
        }
    else:
        text = re.sub(r'\[CQ:face,id=(\d+?)\]', save_and_remark, text)
        text_list = [ 
            {
                "type": "text",
                "data": {
                    "text": _
                }
            }
            for _ in text.split("&pos;")
        ]
        union_res = list(chain.from_iterable(zip_longest(text_list, face_list, fillvalue={"type": "text","data": {"text": ""}})))
        return union_res


def face(
    icon_id: int, 
) -> Msg:
    """
    QQ 表情
    """
    return {
        "type": "face",
        "data": {
            "id": f"{icon_id}"
        }
    }


def record(
    url: str, 
    timeout: int=None, 
    magic: bool=False, 
) -> Msg:
    """
    语音消息
    """
    base =  {
        "type": "record",
        "data": {
            "file": url,
        }
    }
    if magic: base['data']['magic'] = 1
    if timeout: base['data']['timeout'] = str(timeout)
    return base


def at(
    qqId:Union[int ,Literal['all']], 
    notInName: str=None, 
) -> Msg:
    """
    at 消息。
    at 所有人时，`qqId` 传 "all"
    """
    base = {
        "type": "at",
        "data": {
            "qq": qqId,
        }
    }
    if notInName: base['data']['name'] = notInName
    return base


def share(
    url: str, 
    title: str, 
    content: str=None, 
    image: str=None, 
) -> Msg:
    """
    链接分享卡片消息。
    `content` 为描述语
    """
    base = {
        "type": "share",
        "data": {
            "url": url,
            "title": title,
        }
    }
    if content: base['data']['content'] = content
    if image: base['data']['image'] = image
    return base


def music(
    platType: Literal["qq", "163", "xm"],
    songId: str, 
) -> Msg:
    """
    音乐分享卡片消息（专有平台）
    """
    return {
        "type": "music",
        "data": {
            "type": platType,
            "id": songId
        }
    }


def custom_music(
    url: str, 
    audio: str, 
    title: str, 
    content: str=None, 
    image: str=None, 
) -> Msg:
    """
    自定义音乐分享卡片。
    `url` 为主页或网站起始页
    """
    base = {
        "type": "music",
        "data": {
            "type": "custom",
            "url": url,
            "audio": audio,
            "title": title,
        }
    }
    if content: base['data']['content'] = content
    if image: base['data']['image'] = image
    return base


def image(
    url: str, 
    picType: Literal["flash", "show"]=None, 
    subType: Literal[0, 1]=None, 
    useCache: Literal[0, 1]=1,
) -> Msg:
    """
    图片消息。
    `url`: 图片 url。可以为本地路径，如：`file:///C:/users/15742/desktop/QQ图片20230108225606.jpg`；也可以为网络 url；还可以为 image id。
    `picType`: flash 为闪照，show 为秀图，不填为普通图片。
    `subType`: 只出现在群聊，0 为正常图片，1 为表情包
    """
    base = {
        "type": "image",
        "data": {
            "file": url,
        }
    }
    if picType: base['data']['type'] = picType
    if subType: base['data']['subType'] = subType
    if useCache: base['data']['cache'] = useCache
    return base


def reply(
    messageId: int, 
) -> Msg:
    """
    回复消息
    """
    return {
        "type": "reply",
        "data": {
            "id": messageId,
        }
    }


def poke(
    qqId: int, 
) -> Msg:
    """
    戳一戳消息
    """
    return {
        "type": "poke",
        "data": {
            "qq": qqId,
        }
    }


def tts(
    text: str, 
) -> Msg:
    """
    腾讯自带 tts 语音消息
    """
    return {
        "type": "tts",
        "data": {
            "text": text,
        }
    }
