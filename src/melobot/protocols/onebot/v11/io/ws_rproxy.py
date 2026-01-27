from __future__ import annotations

import asyncio
import http

from typing_extensions import Any, Callable, Coroutine
from websockets.asyncio.server import ServerConnection
from websockets.http11 import Request, Response

from melobot.log import logger

from .base import InstCounter
from .ws import GenericIOLayer
from .ws_impl import WSClientImpl, WSServerImpl


class GenericRProxyLayer:
    def __init__(self) -> None:
        self.io_src: GenericIOLayer | None = None
        self.to_downstream_buf: asyncio.Queue[str] = asyncio.Queue()

        # 在继承具体的实现类后拥有这些属性
        self.name: str
        self._start: Callable[[], Coroutine[Any, Any, None]]
        self._stop: Callable[[], Coroutine[Any, Any, None]]
        self._bound = False

    def bind_src(self, src: GenericIOLayer) -> None:
        if self._bound:
            raise RuntimeError(f"{self.name} 已经绑定了一个源对象，不能重复绑定")
        self.io_src = src
        self._bound = True

    async def _on_received(self, raw: str | bytes) -> None:
        if self.io_src is None:
            logger.warning(f"{self.name} 没有绑定源对象，将丢弃收到的数据")
            return
        asyncio.create_task(self.io_src._to_upstream(raw))

    async def _on_get_output(self) -> str | bytes:
        raw = await self.to_downstream_buf.get()
        return raw

    async def open(self) -> None:
        await self._start()

    async def close(self) -> None:
        await self._stop()

    def to_downstream(self, raw: str) -> None:
        if self.to_downstream_buf.qsize() > 100:
            logger.warning(
                f"{self.name} 输出缓冲区溢出，开始丢弃发送到下游的数据。请保证连接畅通或减少数据发送频率"
            )
            raise RuntimeError("输出缓冲区溢出，发送到下游的数据被丢弃")
        self.to_downstream_buf.put_nowait(raw)


class RProxyWSClient(InstCounter, GenericRProxyLayer, WSClientImpl):
    def __init__(
        self,
        url: str,
        max_retry: int = -1,
        retry_delay: float = 4.0,
        access_token: str | None = None,
        *,
        name: str | None = None,
    ) -> None:
        InstCounter.__init__(self)
        GenericRProxyLayer.__init__(self)
        WSClientImpl.__init__(
            self,
            name=f"OB11 反代/WS 客户端 #{self.INSTANCE_COUNT}" if name is None else name,
            url=url,
            req_headers=(
                None if access_token is None else {"Authorization": f"Bearer {access_token}"}
            ),
            max_retry=max_retry,
            retry_delay=retry_delay,
        )


class RProxyWSServer(InstCounter, GenericRProxyLayer, WSServerImpl):
    def __init__(
        self, host: str, port: int, access_token: str | None = None, *, name: str | None = None
    ) -> None:
        InstCounter.__init__(self)
        GenericRProxyLayer.__init__(self)
        WSServerImpl.__init__(
            self,
            name=f"OB11 反代/WS 服务端 #{self.INSTANCE_COUNT}" if name is None else name,
            host=host,
            port=port,
        )
        self.access_token = access_token
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
