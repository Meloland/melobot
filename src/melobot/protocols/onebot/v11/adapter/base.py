from __future__ import annotations

import asyncio
from os import PathLike

from typing_extensions import Any, Callable, Iterable, Literal, Optional, Sequence

from melobot.adapter import (
    AbstractEchoFactory,
    AbstractEventFactory,
    AbstractOutputFactory,
    ActionHandleGroup,
)
from melobot.adapter import Adapter as RootAdapter
from melobot.adapter import Content
from melobot.adapter import content as mc
from melobot.exceptions import AdapterError
from melobot.handle import try_get_event
from melobot.typ import AsyncCallable, SyncOrAsyncCallable
from melobot.utils import to_async, to_coro

from ..const import ACTION_TYPE_KEY_NAME, PROTOCOL_IDENTIFIER, T
from ..io.base import BaseIOSource
from ..io.packet import EchoPacket, InPacket, OutPacket
from . import action as ac
from . import echo as ec
from . import event as ev
from . import segment as se

_ValidateHandler = AsyncCallable[[dict[str, Any], Exception], None]


class ValidateHandleMixin:
    def __init__(self) -> None:
        self.validate_handlers: list[_ValidateHandler] = []

    def add_validate_handler(self, callback: _ValidateHandler) -> None:
        self.validate_handlers.append(callback)

    async def validate_handle(self, data: dict[str, Any], func: Callable[[dict[str, Any]], T]) -> T:
        try:
            return func(data)
        except Exception as e:
            tasks = map(
                asyncio.create_task,
                map(
                    to_coro,
                    (cb(data, e) for cb in self.validate_handlers),
                ),
            )
            if len(self.validate_handlers):
                await asyncio.wait(tasks)
        return func(data)


class EventFactory(AbstractEventFactory[InPacket, ev.Event], ValidateHandleMixin):
    async def create(self, packet: InPacket) -> ev.Event:
        return await self.validate_handle(packet.data, ev.Event.resolve)


class OutputFactory(AbstractOutputFactory[OutPacket, ac.Action]):
    async def create(self, action: ac.Action) -> OutPacket:
        return OutPacket(
            data=action.flatten(),
            action_type=action.type,
            action_params=action.params,
            echo_id=action.id,
        )


class EchoFactory(AbstractEchoFactory[EchoPacket, ec.Echo], ValidateHandleMixin):
    async def create(self, packet: EchoPacket) -> ec.Echo | None:
        if packet.noecho:
            return None

        data = packet.data
        data[ACTION_TYPE_KEY_NAME] = packet.action_type
        return await self.validate_handle(data, ec.Echo.resolve)


class Adapter(
    RootAdapter[EventFactory, OutputFactory, EchoFactory, ac.Action, BaseIOSource, BaseIOSource]
):
    def __init__(self) -> None:
        super().__init__(PROTOCOL_IDENTIFIER, EventFactory(), OutputFactory(), EchoFactory())

    def when_validate_error(self, validate_type: Literal["event", "echo"]) -> Callable[
        [SyncOrAsyncCallable[[dict[str, Any], Exception], None]],
        AsyncCallable[[dict[str, Any], Exception], None],
    ]:
        def when_validate_error_wrapper(
            func: SyncOrAsyncCallable[[dict[str, Any], Exception], None],
        ) -> AsyncCallable[[dict[str, Any], Exception], None]:
            f = to_async(func)
            if validate_type == "event":
                self._event_factory.add_validate_handler(f)
            elif validate_type == "echo":
                self._echo_factory.add_validate_handler(f)
            else:
                raise AdapterError("无效的验证类型，合法值是 'event', 'echo' 之一")
            return f

        return when_validate_error_wrapper

    async def __send_text__(self, text: str) -> ActionHandleGroup[ec.SendMsgEcho]:
        return await self.send(text)

    async def __send_media__(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> ActionHandleGroup[ec.SendMsgEcho]:
        return await self.send(
            se.contents_to_segs([mc.MediaContent(name=name, url=url, raw=raw, mimetype=mimetype)])[
                0
            ]
        )

    async def __send_image__(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> ActionHandleGroup[ec.SendMsgEcho]:
        return await self.send(
            se.contents_to_segs([mc.ImageContent(name=name, url=url, raw=raw, mimetype=mimetype)])[
                0
            ]
        )

    async def __send_audio__(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> ActionHandleGroup[ec.SendMsgEcho]:
        return await self.send(
            se.contents_to_segs([mc.AudioContent(name=name, url=url, raw=raw, mimetype=mimetype)])[
                0
            ]
        )

    async def __send_voice__(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> ActionHandleGroup[ec.SendMsgEcho]:
        return await self.send(
            se.contents_to_segs([mc.VoiceContent(name=name, url=url, raw=raw, mimetype=mimetype)])[
                0
            ]
        )

    async def __send_video__(
        self,
        name: str,
        raw: bytes | None = None,
        url: str | None = None,
        mimetype: str | None = None,
    ) -> ActionHandleGroup[ec.SendMsgEcho]:
        return await self.send(
            se.contents_to_segs([mc.VideoContent(name=name, url=url, raw=raw, mimetype=mimetype)])[
                0
            ]
        )

    async def __send_file__(
        self, name: str, path: str | PathLike[str]
    ) -> ActionHandleGroup[ec.SendMsgEcho]:
        return await self.send(se.contents_to_segs([mc.FileContent(name=name, flag=str(path))])[0])

    async def __send_refer__(
        self, event: ev.RootEvent, contents: Sequence[Content] | None = None
    ) -> ActionHandleGroup[ec.SendMsgEcho]:
        if not isinstance(event, ev.MessageEvent):
            raise AdapterError(
                f"提供的事件不是 {ev.MessageEvent.__qualname__} 类型，无法用于发送 refer 消息"
            )

        segs = se.contents_to_segs(list(contents)) if contents else []
        segs.insert(0, se.ReplySegment(str(event.message_id)))
        if isinstance(event, ev.GroupMessageEvent):
            return await self.send_custom(segs, group_id=event.group_id)
        return await self.send_custom(segs, user_id=event.user_id)

    async def __send_resource__(self, name: str, url: str) -> ActionHandleGroup[ec.SendMsgEcho]:
        return await self.send(se.contents_to_segs([mc.ResourceContent(name, url)])[0])

    async def send(
        self, msgs: str | se.Segment | Iterable[se.Segment] | dict | Iterable[dict]
    ) -> ActionHandleGroup[ec.SendMsgEcho]:
        event = try_get_event()
        if not isinstance(event, ev.MessageEvent):
            raise AdapterError(
                f"当前上下文中不存在事件，或事件不为 {ev.MessageEvent.__qualname__} 类型，无法发送消息"
            )

        if isinstance(event, ev.GroupMessageEvent):
            return await self.send_custom(msgs, group_id=event.group_id)
        return await self.send_custom(msgs, user_id=event.user_id)

    async def send_reply(
        self, msgs: str | se.Segment | Iterable[se.Segment] | dict | Iterable[dict]
    ) -> ActionHandleGroup[ec.SendMsgEcho]:
        event = try_get_event()
        if not isinstance(event, ev.MessageEvent):
            raise AdapterError(
                f"当前上下文中不存在事件，或事件不为 {ev.MessageEvent.__qualname__} 类型，无法发送消息"
            )

        kwargs: dict[str, Any] = {
            "msgs": ac.msgs_to_dicts(se.ReplySegment(str(event.message_id)))
            + ac.msgs_to_dicts(msgs)
        }
        if isinstance(event, ev.GroupMessageEvent):
            kwargs["group_id"] = event.group_id
        else:
            kwargs["user_id"] = event.user_id
        return await self.call_output(ac.SendMsgAction(**kwargs))

    async def send_custom(
        self,
        msgs: str | se.Segment | Iterable[se.Segment] | dict | Iterable[dict],
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> ActionHandleGroup[ec.SendMsgEcho]:
        return await self.call_output(ac.SendMsgAction(msgs, user_id, group_id))

    async def send_forward(
        self, msgs: Iterable[se.NodeSegment]
    ) -> ActionHandleGroup[ec.SendForwardMsgEcho]:
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
    ) -> ActionHandleGroup[ec.SendForwardMsgEcho]:
        return await self.call_output(ac.SendForwardMsgAction(msgs, user_id, group_id))

    async def delete_msg(self, msg_id: int) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(ac.DeleteMsgAction(msg_id))

    async def get_msg(self, msg_id: int) -> ActionHandleGroup[ec.GetMsgEcho]:
        return await self.call_output(ac.GetMsgAction(msg_id))

    async def get_forward_msg(self, forward_id: str) -> ActionHandleGroup[ec.GetForwardMsgEcho]:
        return await self.call_output(ac.GetForwardMsgAction(forward_id))

    async def send_like(self, user_id: int, times: int = 1) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(ac.SendLikeAction(user_id, times))

    async def set_group_kick(
        self, group_id: int, user_id: int, later_reject: bool = False
    ) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(ac.SetGroupKickAction(group_id, user_id, later_reject))

    async def set_group_ban(
        self, group_id: int, user_id: int, duration: int = 30 * 60
    ) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(ac.SetGroupBanAction(group_id, user_id, duration))

    async def set_group_anonymous_ban(
        self,
        group_id: int,
        anonymous: ac.SetGroupAnonymousBanAction.AnonymousDict,
        anonymous_flag: str,
        duration: int = 30 * 60,
    ) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(
            ac.SetGroupAnonymousBanAction(group_id, anonymous, anonymous_flag, duration)
        )

    async def set_group_whole_ban(
        self, group_id: int, enable: bool = True
    ) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(ac.SetGroupWholeBanAction(group_id, enable))

    async def set_group_admin(
        self, group_id: int, enable: bool = True
    ) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(ac.SetGroupAdminAction(group_id, enable))

    async def set_group_anonymous(
        self, group_id: int, enable: bool = True
    ) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(ac.SetGroupAnonymousAction(group_id, enable))

    async def set_group_card(
        self, group_id: int, user_id: int, card: str = ""
    ) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(ac.SetGroupCardAction(group_id, user_id, card))

    async def set_group_name(self, group_id: int, name: str) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(ac.SetGroupNameAction(group_id, name))

    async def set_group_leave(
        self, group_id: int, is_dismiss: bool = False
    ) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(ac.SetGroupLeaveAction(group_id, is_dismiss))

    async def set_group_special_title(
        self, group_id: int, user_id: int, title: str = "", duration: int = -1
    ) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(
            ac.SetGroupSpecialTitleAction(group_id, user_id, title, duration)
        )

    async def set_friend_add_request(
        self, add_flag: str, approve: bool = True, remark: str = ""
    ) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(ac.SetFriendAddRequestAction(add_flag, approve, remark))

    async def set_group_add_request(
        self,
        add_flag: str,
        add_type: Literal["add", "invite"],
        approve: bool = True,
        reason: str = "",
    ) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(
            ac.SetGroupAddRequestAction(add_flag, add_type, approve, reason)
        )

    async def get_login_info(self) -> ActionHandleGroup[ec.GetLoginInfoEcho]:
        return await self.call_output(ac.GetLoginInfoAction())

    async def get_stranger_info(
        self, user_id: int, no_cache: bool = False
    ) -> ActionHandleGroup[ec.GetStrangerInfoEcho]:
        return await self.call_output(ac.GetStrangerInfoAction(user_id, no_cache))

    async def get_friend_list(self) -> ActionHandleGroup[ec.GetFriendListEcho]:
        return await self.call_output(ac.GetFriendlistAction())

    async def get_group_info(
        self, group_id: int, no_cache: bool = False
    ) -> ActionHandleGroup[ec.GetGroupInfoEcho]:
        return await self.call_output(ac.GetGroupInfoAction(group_id, no_cache))

    async def get_group_list(self) -> ActionHandleGroup[ec.GetGroupListEcho]:
        return await self.call_output(ac.GetGrouplistAction())

    async def get_group_member_info(
        self, group_id: int, user_id: int, no_cache: bool = False
    ) -> ActionHandleGroup[ec.GetGroupMemberInfoEcho]:
        return await self.call_output(ac.GetGroupMemberInfoAction(group_id, user_id, no_cache))

    async def get_group_member_list(
        self, group_id: int
    ) -> ActionHandleGroup[ec.GetGroupMemberListEcho]:
        return await self.call_output(ac.GetGroupMemberlistAction(group_id))

    async def get_group_honor_info(
        self,
        group_id: int,
        type: Literal["talkative", "performer", "legend", "strong_newbie", "emotion", "all"],
    ) -> ActionHandleGroup[ec.GetGroupHonorInfoEcho]:
        return await self.call_output(ac.GetGroupHonorInfoAction(group_id, type))

    async def get_cookies(self, domain: str = "") -> ActionHandleGroup[ec.GetCookiesEcho]:
        return await self.call_output(ac.GetCookiesAction(domain))

    async def get_csrf_token(self) -> ActionHandleGroup[ec.GetCsrfTokenEcho]:
        return await self.call_output(ac.GetCsrfTokenAction())

    async def get_credentials(self, domain: str = "") -> ActionHandleGroup[ec.GetCredentialsEcho]:
        return await self.call_output(ac.GetCredentialsAction(domain))

    async def get_record(self, file: str, out_format: str) -> ActionHandleGroup[ec.GetRecordEcho]:
        return await self.call_output(ac.GetRecordAction(file, out_format))

    async def get_image(self, file: str) -> ActionHandleGroup[ec.GetImageEcho]:
        return await self.call_output(ac.GetImageAction(file))

    async def can_send_image(self) -> ActionHandleGroup[ec.CanSendImageEcho]:
        return await self.call_output(ac.CanSendImageAction())

    async def can_send_record(self) -> ActionHandleGroup[ec.CanSendRecordEcho]:
        return await self.call_output(ac.CanSendRecordAction())

    async def get_status(self) -> ActionHandleGroup[ec.GetStatusEcho]:
        return await self.call_output(ac.GetStatusAction())

    async def get_version_info(self) -> ActionHandleGroup[ec.GetVersionInfoEcho]:
        return await self.call_output(ac.GetVersionInfoAction())

    async def set_restart(self, delay: int = 0) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(ac.SetRestartAction(delay))

    async def clean_cache(self) -> ActionHandleGroup[ec.EmptyEcho]:
        return await self.call_output(ac.CleanCacheAction())
