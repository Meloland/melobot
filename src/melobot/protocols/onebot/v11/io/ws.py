from __future__ import annotations

import asyncio
import http
import json
import time
from asyncio import Future

from typing_extensions import TYPE_CHECKING, Any, Callable, Coroutine
from websockets.asyncio.server import ServerConnection
from websockets.http11 import Request, Response

from melobot._hook import HookBus
from melobot.io import SourceLifeSpan
from melobot.log import log_exc, logger
from melobot.utils import get_id

from ..const import ACTION_TYPE_KEY_NAME
from .base import BaseIOSource, InstCounter
from .packet import (
    DownstreamCallInPacket,
    EchoPacket,
    EchoToDownstream,
    EventToDownstream,
    InPacket,
    OutPacket,
    ShareToDownstreamInPacket,
    UpstreamRetInPacket,
)
from .ws_impl import WSClientImpl, WSServerImpl

if TYPE_CHECKING:
    from .ws_rproxy import RProxyWSClient, RProxyWSServer


class GenericIOLayer:
    def __init__(self, rproxy: "RProxyWSClient | RProxyWSServer | None") -> None:
        self._in_buf: asyncio.Queue[InPacket] = asyncio.Queue()
        self._out_buf: asyncio.Queue[OutPacket] = asyncio.Queue()
        self._pre_send_time = time.time_ns()
        self._echo_table: dict[str, tuple[str, Future[EchoPacket]]] = {}
        self._echo_mapping: dict[str, tuple[str, str]] = {}

        self._rproxy = rproxy
        if self._rproxy is not None:
            self._rproxy.bind_src(self)

        # 在继承具体的实现类后拥有这些属性
        self.name: str
        self.cd_time: float
        self._hook_bus: HookBus
        self._start: Callable[[], Coroutine[Any, Any, None]]
        self._stop: Callable[[], Coroutine[Any, Any, None]]
        self._opened: asyncio.Event

    async def _on_received(self, raw: str | bytes) -> None:
        if raw == "":
            return

        raw_dic = json.loads(raw)
        if "post_type" in raw_dic:
            if self._rproxy is None:
                self._in_buf.put_nowait(InPacket(time=raw_dic["time"], data=raw_dic))
            else:
                share_pak = ShareToDownstreamInPacket(time=raw_dic["time"], data=raw_dic)
                self._in_buf.put_nowait(share_pak)
                asyncio.create_task(self._to_downstream(share_pak.to_downstream))
            return

        echo_id = raw_dic.get("echo")
        if echo_id in (None, ""):
            return

        if self._rproxy is not None and echo_id in self._echo_mapping:
            # 构造由下游调用引发的结果返回事件
            event_data: dict[str, Any] = {}
            event_data["post_type"] = "upstream_ret"
            event_data["time"] = int(time.time_ns() / 1e9)
            event_data["self_id"] = -1

            # 查表获得下游发起调用时使用的回声字段
            calling_type, down_seen_echo = self._echo_mapping.pop(echo_id)
            raw_dic[ACTION_TYPE_KEY_NAME] = calling_type
            raw_dic["echo"] = down_seen_echo
            event_data["ret"] = raw_dic

            ret_pak = UpstreamRetInPacket(time=event_data["time"], data=event_data)
            # 放入缓存，随后传递给适配器形成上游返回事件
            self._in_buf.put_nowait(ret_pak)
            asyncio.create_task(self._to_downstream(ret_pak.to_downstream))
        else:
            # 在这里处理 melobot 内部发起的调用的返回结果
            action_type, fut = self._echo_table.pop(echo_id)
            fut.set_result(
                EchoPacket(
                    time=int(time.time_ns() / 1e9),
                    data=raw_dic,
                    ok=raw_dic["status"] == "ok",
                    status=raw_dic["retcode"],
                    action_type=action_type,
                )
            )

    async def _on_get_output(self) -> str | bytes | None:
        out_packet = await self._out_buf.get()
        wait_time = self.cd_time - ((time.time_ns() - self._pre_send_time) / 1e9)
        await asyncio.sleep(wait_time)
        return out_packet.data

    async def _on_sent(self, out: str | bytes) -> None:
        self._pre_send_time = time.time_ns()

    async def _on_relinked(self) -> None:
        await self._hook_bus.emit(SourceLifeSpan.RESTARTED, False)

    async def input(self) -> InPacket:
        return await self._in_buf.get()

    async def output(self, packet: OutPacket) -> EchoPacket:
        if self._out_buf.qsize() > 100:
            logger.warning(
                f"{self.name} 输出缓冲区溢出，开始丢弃操作请求。请保证连接畅通或减少操作请求频率"
            )
            raise RuntimeError("输出缓冲区溢出，操作请求被丢弃")
        self._out_buf.put_nowait(packet)
        if packet.echo_id is None:
            return EchoPacket(noecho=True)

        fut: Future[EchoPacket] = asyncio.get_running_loop().create_future()
        if len(self._echo_table) > 256:
            logger.warning(
                f"{self.name} echo 标识映射表溢出，开始丢弃操作请求。请保证连接畅通或减少操作请求频率"
            )
            raise RuntimeError("echo 标识映射表溢出，操作请求被丢弃")
        self._echo_table[packet.echo_id] = (packet.action_type, fut)
        return await fut

    async def _to_downstream(
        self, fut: Future[EventToDownstream] | Future[EchoToDownstream]
    ) -> None:
        try:
            ret = await fut
            if not ret.is_forbidden() and self._rproxy is not None:
                self._rproxy.to_downstream(ret.get_json())
        except Exception as e:
            log_exc(e, f"{self.name} 传递数据给下游时发生异常", obj={"fut": fut})

    async def _to_upstream(self, raw: str | bytes) -> None:
        try:
            if raw == "":
                return
            raw_dic = json.loads(raw)
            raw_dic["post_type"] = "downstream_call"
            raw_dic["time"] = int(time.time_ns() / 1e9)
            raw_dic["self_id"] = -1
            pak = DownstreamCallInPacket(time=raw_dic["time"], data=raw_dic)

            # 放入缓存，随后传递给适配器形成下游调用事件
            await self._in_buf.put(pak)
            out = await pak.to_upstream
            if out.is_forbidden():
                return

            # 替换回声标识，并存入映射表保存
            # 因为下游的回声标识可能和 melobot 内部的冲突，虽然概率很小
            down_seen_echo = out.echo
            up_seen_echo = get_id()
            out_data = json.dumps(
                {**out.get_dict(deepcopy=False), "echo": up_seen_echo}, ensure_ascii=False
            )
            out_pak = OutPacket(
                data=out_data,
                action_type=out.type,
                action_params=out.params,
                echo_id=up_seen_echo,
            )
            if len(self._echo_mapping) > 256:
                logger.warning(
                    f"{self.name} 反代 echo 标识映射表溢出，开始丢弃操作请求。请保证连接畅通或减少操作请求频率"
                )
                raise RuntimeError(f"{self.name} 反代 echo 标识映射表溢出，操作请求被丢弃")
            self._echo_mapping[up_seen_echo] = (out_pak.action_type, down_seen_echo)
            self._out_buf.put_nowait(out_pak)
        except Exception as e:
            log_exc(e, f"{self.name} 传递数据给上游时发生异常", obj={"raw": raw})

    async def open(self) -> None:
        await self._start()
        if self._rproxy is not None:
            await self._rproxy.open()

    def opened(self) -> bool:
        return self._opened.is_set()

    async def close(self) -> None:
        if self._rproxy is not None:
            await self._rproxy.close()
        await self._stop()


class WSClient(InstCounter, GenericIOLayer, WSClientImpl, BaseIOSource):
    def __init__(
        self,
        url: str,
        max_retry: int = -1,
        retry_delay: float = 4.0,
        cd_time: float = 0,
        access_token: str | None = None,
        rproxy: "RProxyWSClient | RProxyWSServer | None" = None,
        *,
        name: str | None = None,
    ) -> None:
        InstCounter.__init__(self)
        GenericIOLayer.__init__(self, rproxy=rproxy)
        WSClientImpl.__init__(
            self,
            name=f"OB11 WS 客户端 #{self.INSTANCE_COUNT}" if name is None else name,
            url=url,
            req_headers=(
                None if access_token is None else {"Authorization": f"Bearer {access_token}"}
            ),
            max_retry=max_retry,
            retry_delay=retry_delay,
        )
        BaseIOSource.__init__(self, cd_time=cd_time)
        self._hook_bus.set_tag(self.name)


class WSServer(InstCounter, GenericIOLayer, WSServerImpl, BaseIOSource):
    def __init__(
        self,
        host: str,
        port: int,
        cd_time: float = 0,
        access_token: str | None = None,
        rproxy: "RProxyWSClient | RProxyWSServer | None" = None,
        *,
        name: str | None = None,
    ) -> None:
        InstCounter.__init__(self)
        GenericIOLayer.__init__(self, rproxy=rproxy)
        WSServerImpl.__init__(
            self,
            name=f"OB11 WS 服务端 #{self.INSTANCE_COUNT}" if name is None else name,
            host=host,
            port=port,
        )
        BaseIOSource.__init__(self, cd_time=cd_time)
        self.access_token = access_token

        self._hook_bus.set_tag(self.name)
        self._req_lock = asyncio.Lock()
        self._conn_requested = False

    async def _on_req(self, conn: ServerConnection, req: Request) -> Response | None:
        _headers = dict(req.headers)
        reconn_refused = "Already accepted the unique connection\n"
        auth_failed = "Authorization failed\n"
        if self._conn_requested:
            return conn.respond(http.HTTPStatus.FORBIDDEN, reconn_refused)

        async with self._req_lock:
            if self._conn_requested:
                return conn.respond(http.HTTPStatus.FORBIDDEN, reconn_refused)
            if (
                self.access_token is not None
                and _headers.get("authorization") != f"Bearer {self.access_token}"
                and _headers.get("Authorization") != f"Bearer {self.access_token}"
            ):
                logger.warning(f"{self.name} ws 客户端请求的 access_token 不匹配，拒绝连接")
                return conn.respond(http.HTTPStatus.FORBIDDEN, auth_failed)

            self._conn_requested = True
            return None

    async def _on_unlinked(self, ws: ServerConnection) -> None:
        self._conn_requested = False
