from os import PathLike
from typing import Iterable, Literal, Optional, cast

from melobot.adapter import (
    AbstractEchoFactory,
    AbstractEventFactory,
    AbstractOutputFactory,
)
from melobot.adapter import Adapter as RootAdapter
from melobot.adapter import content as mc
from melobot.adapter.content import Content
from melobot.adapter.model import ActionHandle, EchoT
from melobot.ctx import Context
from melobot.exceptions import AdapterError
from melobot.handle import try_get_event
from melobot.typ import AsyncCallable
from melobot.utils import singleton

from ..const import PROTOCOL_IDENTIFIER, P
from ..io.base import BaseIO
from ..io.packet import EchoPacket, InPacket, OutPacket
from . import action as ac
from . import echo as ec
from . import event as ev
from . import segment as se


class EventFactory(AbstractEventFactory[InPacket, ev.Event]):
    async def create(self, packet: InPacket) -> ev.Event:
        return ev.Event.resolve(packet.data)


class OutputFactory(AbstractOutputFactory[OutPacket, ac.Action]):
    async def create(self, action: ac.Action) -> OutPacket:
        return OutPacket(
            data=action.flatten(),
            action_type=action.type,
            action_params=action.params,
            echo_id=action.id if action.need_echo else None,
        )


class EchoFactory(AbstractEchoFactory[EchoPacket, ec.Echo]):
    async def create(self, packet: EchoPacket) -> ec.Echo | None:
        if packet.noecho:
            return None
        return ec.Echo.resolve(action_type=packet.action_type, **packet.data)


@singleton
class EchoRequireCtx(Context[bool]):
    def __init__(self) -> None:
        super().__init__("ONEBOT_V11_ECHO_STATUS", LookupError)


class Adapter(
    RootAdapter[EventFactory, OutputFactory, EchoFactory, ac.Action, BaseIO, BaseIO]
):
    def __init__(self) -> None:
        super().__init__(
            PROTOCOL_IDENTIFIER, EventFactory(), OutputFactory(), EchoFactory()
        )

    async def call_output(self, action: ac.Action) -> tuple[ActionHandle, ...]:
        """输出行为的底层方法

        :param action: 行为对象
        :return: :class:`.ActionHandle` 元组
        """
        if EchoRequireCtx().try_get():
            action.need_echo = True
        return await super().call_output(action)

    def with_echo(
        self, func: AsyncCallable[P, tuple[ActionHandle[EchoT | None], ...]]
    ) -> AsyncCallable[P, tuple[ActionHandle[EchoT], ...]]:
        async def wrapped_api(
            *args: P.args, **kwargs: P.kwargs
        ) -> tuple[ActionHandle[EchoT], ...]:
            with EchoRequireCtx().in_ctx(True):
                handles = await func(*args, **kwargs)
            return cast(tuple[ActionHandle[EchoT], ...], handles)

        return wrapped_api

    async def send_text(
        self, text: str
    ) -> tuple[ActionHandle[ec.SendMsgEcho | None], ...]:
        return await self.send(text)

    async def send_media(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle[ec.SendMsgEcho | None], ...]:
        return await self.send(
            se.contents_to_segs(
                [mc.MediaContent(name=name, url=url, raw=raw, mimetype=mimetype)]
            )[0]
        )

    async def send_image(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle[ec.SendMsgEcho | None], ...]:
        return await self.send(
            se.contents_to_segs(
                [mc.ImageContent(name=name, url=url, raw=raw, mimetype=mimetype)]
            )[0]
        )

    async def send_audio(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle[ec.SendMsgEcho | None], ...]:
        return await self.send(
            se.contents_to_segs(
                [mc.AudioContent(name=name, url=url, raw=raw, mimetype=mimetype)]
            )[0]
        )

    async def send_voice(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle[ec.SendMsgEcho | None], ...]:
        return await self.send(
            se.contents_to_segs(
                [mc.VoiceContent(name=name, url=url, raw=raw, mimetype=mimetype)]
            )[0]
        )

    async def send_video(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> tuple[ActionHandle[ec.SendMsgEcho | None], ...]:
        return await self.send(
            se.contents_to_segs(
                [mc.VideoContent(name=name, url=url, raw=raw, mimetype=mimetype)]
            )[0]
        )

    async def send_file(
        self, name: str, path: str | PathLike[str]
    ) -> tuple[ActionHandle[ec.SendMsgEcho | None], ...]:
        return await self.send(
            se.contents_to_segs([mc.FileContent(name=name, flag=str(path))])[0]
        )

    async def send_refer(
        self, event: ev.RootEvent, contents: ev.Sequence[Content] | None = None
    ) -> tuple[ActionHandle[ec.SendMsgEcho | None], ...]:
        if not isinstance(event, ev.MessageEvent):
            raise AdapterError(
                f"提供的事件不是 {ev.MessageEvent.__qualname__} 类型，无法用于发送 refer 消息"
            )

        segs = se.contents_to_segs(list(contents)) if contents else []
        segs.insert(0, se.ReplySegment(str(event.message_id)))
        if isinstance(event, ev.GroupMessageEvent):
            return await self.send_custom(segs, group_id=event.group_id)
        return await self.send_custom(segs, user_id=event.user_id)

    async def send_resource(
        self, name: str, url: str
    ) -> tuple[ActionHandle[ec.SendMsgEcho | None], ...]:
        return await self.send(se.contents_to_segs([mc.ResourceContent(name, url)])[0])

    async def send(
        self, msgs: str | se.Segment | Iterable[se.Segment] | dict | Iterable[dict]
    ) -> tuple[ActionHandle[ec.SendMsgEcho | None], ...]:
        event = try_get_event()
        if not isinstance(event, ev.MessageEvent):
            raise AdapterError(
                f"当前上下文中不存在事件，或事件不为 {ev.MessageEvent.__qualname__} 类型，无法发送消息"
            )

        if isinstance(event, ev.GroupMessageEvent):
            return await self.send_custom(msgs, group_id=event.group_id)
        return await self.send_custom(msgs, user_id=event.user_id)

    async def send_custom(
        self,
        msgs: str | se.Segment | Iterable[se.Segment] | dict | Iterable[dict],
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> tuple[ActionHandle[ec.SendMsgEcho | None], ...]:
        return await self.call_output(ac.SendMsgAction(msgs, user_id, group_id))

    async def send_forward(
        self, msgs: Iterable[se.NodeSegment]
    ) -> tuple[ActionHandle[ec.SendForwardMsgEcho | None], ...]:
        event = try_get_event()
        if not isinstance(event, ev.MessageEvent):
            raise AdapterError(
                f"当前上下文中不存在事件，或事件不为 {ev.MessageEvent.__qualname__} 类型，无法发送消息"
            )

        if isinstance(event, ev.GroupMessageEvent):
            return await self.send_forward_custom(msgs, group_id=event.group_id)
        return await self.send_forward_custom(msgs, user_id=event.user_id)

    async def send_forward_custom(
        self,
        msgs: Iterable[se.NodeSegment] | Iterable[dict],
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> tuple[ActionHandle[ec.SendForwardMsgEcho | None], ...]:
        return await self.call_output(ac.SendForwardMsgAction(msgs, user_id, group_id))

    async def delete_msg(
        self, msg_id: int
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(ac.DeleteMsgAction(msg_id))

    async def get_msg(
        self, msg_id: int
    ) -> tuple[ActionHandle[ec.GetMsgEcho | None], ...]:
        return await self.call_output(ac.GetMsgAction(msg_id))

    async def get_forward_msg(
        self, forward_id: str
    ) -> tuple[ActionHandle[ec.GetForwardMsgEcho | None], ...]:
        return await self.call_output(ac.GetForwardMsgAction(forward_id))

    async def send_like(
        self, user_id: int, times: int = 1
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(ac.SendLikeAction(user_id, times))

    async def set_group_kick(
        self, group_id: int, user_id: int, later_reject: bool = False
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(
            ac.SetGroupKickAction(group_id, user_id, later_reject)
        )

    async def set_group_ban(
        self, group_id: int, user_id: int, duration: int = 30 * 60
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(ac.SetGroupBanAction(group_id, user_id, duration))

    async def set_group_anonymous_ban(
        self,
        group_id: int,
        anonymous: ac.SetGroupAnonymousBanAction.AnonymousDict,
        anonymous_flag: str,
        duration: int = 30 * 60,
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(
            ac.SetGroupAnonymousBanAction(group_id, anonymous, anonymous_flag, duration)
        )

    async def set_group_whole_ban(
        self, group_id: int, enable: bool = True
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(ac.SetGroupWholeBanAction(group_id, enable))

    async def set_group_admin(
        self, group_id: int, enable: bool = True
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(ac.SetGroupAdminAction(group_id, enable))

    async def set_group_anonymous(
        self, group_id: int, enable: bool = True
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(ac.SetGroupAnonymousAction(group_id, enable))

    async def set_group_card(
        self, group_id: int, user_id: int, card: str = ""
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(ac.SetGroupCardAction(group_id, user_id, card))

    async def set_group_name(
        self, group_id: int, name: str
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(ac.SetGroupNameAction(group_id, name))

    async def set_group_leave(
        self, group_id: int, is_dismiss: bool = False
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(ac.SetGroupLeaveAction(group_id, is_dismiss))

    async def set_group_special_title(
        self, group_id: int, user_id: int, title: str = "", duration: int = -1
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(
            ac.SetGroupSpecialTitleAction(group_id, user_id, title, duration)
        )

    async def set_friend_add_request(
        self, add_flag: str, approve: bool = True, remark: str = ""
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(
            ac.SetFriendAddRequestAction(add_flag, approve, remark)
        )

    async def set_group_add_request(
        self,
        add_flag: str,
        add_type: Literal["add", "invite"],
        approve: bool = True,
        reason: str = "",
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(
            ac.SetGroupAddRequestAction(add_flag, add_type, approve, reason)
        )

    async def get_login_info(self) -> tuple[ActionHandle[ec.GetLoginInfoEcho], ...]:
        return await self.call_output(ac.GetLoginInfoAction())

    async def get_stranger_info(
        self, user_id: int, no_cache: bool = False
    ) -> tuple[ActionHandle[ec.GetStrangerInfoEcho], ...]:
        return await self.call_output(ac.GetStrangerInfoAction(user_id, no_cache))

    async def get_friend_list(self) -> tuple[ActionHandle[ec.GetFriendListEcho], ...]:
        return await self.call_output(ac.GetFriendlistAction())

    async def get_group_info(
        self, group_id: int, no_cache: bool = False
    ) -> tuple[ActionHandle[ec.GetGroupInfoEcho], ...]:
        return await self.call_output(ac.GetGroupInfoAction(group_id, no_cache))

    async def get_group_list(self) -> tuple[ActionHandle[ec.GetGroupListEcho], ...]:
        return await self.call_output(ac.GetGrouplistAction())

    async def get_group_member_info(
        self, group_id: int, user_id: int, no_cache: bool = False
    ) -> tuple[ActionHandle[ec.GetGroupMemberInfoEcho], ...]:
        return await self.call_output(
            ac.GetGroupMemberInfoAction(group_id, user_id, no_cache)
        )

    async def get_group_member_list(
        self, group_id: int
    ) -> tuple[ActionHandle[ec.GetGroupMemberListEcho], ...]:
        return await self.call_output(ac.GetGroupMemberlistAction(group_id))

    async def get_group_honor_info(
        self,
        group_id: int,
        type: Literal[
            "talkative", "performer", "legend", "strong_newbie", "emotion", "all"
        ],
    ) -> tuple[ActionHandle[ec.GetGroupHonorInfoEcho], ...]:
        return await self.call_output(ac.GetGroupHonorInfoAction(group_id, type))

    async def get_cookies(
        self, domain: str = ""
    ) -> tuple[ActionHandle[ec.GetCookiesEcho], ...]:
        return await self.call_output(ac.GetCookiesAction(domain))

    async def get_csrf_token(self) -> tuple[ActionHandle[ec.GetCsrfTokenEcho], ...]:
        return await self.call_output(ac.GetCsrfTokenAction())

    async def get_credentials(
        self, domain: str = ""
    ) -> tuple[ActionHandle[ec.GetCredentialsEcho], ...]:
        return await self.call_output(ac.GetCredentialsAction(domain))

    async def get_record(
        self, file: str, out_format: str
    ) -> tuple[ActionHandle[ec.GetRecordEcho], ...]:
        return await self.call_output(ac.GetRecordAction(file, out_format))

    async def get_image(self, file: str) -> tuple[ActionHandle[ec.GetImageEcho], ...]:
        return await self.call_output(ac.GetImageAction(file))

    async def can_send_image(self) -> tuple[ActionHandle[ec.CanSendImageEcho], ...]:
        return await self.call_output(ac.CanSendImageAction())

    async def can_send_record(self) -> tuple[ActionHandle[ec.CanSendRecordEcho], ...]:
        return await self.call_output(ac.CanSendRecordAction())

    async def get_status(self) -> tuple[ActionHandle[ec.GetStatusEcho], ...]:
        return await self.call_output(ac.GetStatusAction())

    async def get_version_info(self) -> tuple[ActionHandle[ec.GetVersionInfoEcho], ...]:
        return await self.call_output(ac.GetVersionInfoAction())

    async def set_restart(
        self, delay: int = 0
    ) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(ac.SetRestartAction(delay))

    async def clean_cache(self) -> tuple[ActionHandle[ec.EmptyEcho | None], ...]:
        return await self.call_output(ac.CleanCacheAction())
