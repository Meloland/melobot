from __future__ import annotations

import asyncio
import copy
import json
from dataclasses import dataclass, field

from typing_extensions import Any, cast

from melobot.io import EchoPacket as RootEchoPak
from melobot.io import InPacket as RootInPak
from melobot.io import OutPacket as RootOutPak

from ..const import PROTOCOL_IDENTIFIER


@dataclass(kw_only=True)
class InPacket(RootInPak):  # type: ignore[override]
    data: dict
    protocol: str = PROTOCOL_IDENTIFIER


@dataclass(kw_only=True)
class OutPacket(RootOutPak):  # type: ignore[override]
    data: str
    action_type: str
    action_params: dict
    echo_id: str | None = None
    protocol: str = PROTOCOL_IDENTIFIER


@dataclass(kw_only=True)
class EchoPacket(RootEchoPak):  # type: ignore[override]
    action_type: str = ""
    data: dict = field(default_factory=dict)
    protocol: str = PROTOCOL_IDENTIFIER


@dataclass(kw_only=True)
class ShareToDownstreamInPacket(InPacket):  # type: ignore[override]
    to_downstream: asyncio.Future[EventToDownstream] = field(
        default_factory=lambda: asyncio.get_running_loop().create_future()
    )


@dataclass(kw_only=True)
class DownstreamCallInPacket(InPacket):  # type: ignore[override]
    to_upstream: asyncio.Future[ActionToUpstream] = field(
        default_factory=lambda: asyncio.get_running_loop().create_future()
    )


@dataclass(kw_only=True)
class UpstreamRetInPacket(InPacket):  # type: ignore[override]
    to_downstream: asyncio.Future[EchoToDownstream] = field(
        default_factory=lambda: asyncio.get_running_loop().create_future()
    )


class ActionToUpstream:
    def __init__(self, type: str, params: dict[str, Any], echo: str) -> None:
        self.type = type
        self.params = params
        self.echo = echo

        self._params_updated = False
        self._forbidden = False

    def set_param(self, key: str, value: Any) -> None:
        """设置传递给上游的数据的 `params` 字段中的字段

        :param key: `params` 字典中的键
        :param value: 新值
        """
        if not self._params_updated:
            self.params = copy.deepcopy(self.params)
            self._params_updated = True
        self.params[key] = value

    def override(self, new_dic: dict[str, Any]) -> None:
        """覆盖传递给上游的数据

        :param new_dic: 新的字典，必须包含 `type` 和 `params` 键，`echo` 键不存在时设置为空字符串
        """
        self.type = cast(str, new_dic["type"])
        if new_dic["params"] is not self.params:
            self._params_updated = True
        self.params = cast(dict[str, Any], new_dic["params"])
        self.echo = cast(str, new_dic.get("echo", ""))

    def is_forbidden(self) -> bool:
        """检查数据是否被阻止传递给上游"""
        return self._forbidden

    def forbidden(self) -> None:
        """阻止数据传递给上游"""
        self._forbidden = True

    def get_dict(self, deepcopy: bool = True) -> dict[str, Any]:
        """获得传递给上游的数据的字典表示"""
        return {
            "action": self.type,
            "params": copy.deepcopy(self.params) if deepcopy else self.params,
            "echo": self.echo,
        }

    def get_json(self) -> str:
        """获得传递给上游的数据的 JSON 字符串表示"""
        return json.dumps(
            {"action": self.type, "params": self.params, "echo": self.echo}, ensure_ascii=False
        )


class ToDownstream:
    def __init__(self, dic: dict[str, Any]) -> None:
        self._raw = dic
        self._updated = False
        self._forbidden = False

    def set_param(self, key: str, value: Any) -> None:
        """设置传递给下游的数据中的字段

        :param key: 键
        :param value: 新值
        """
        if not self._updated:
            self._raw = copy.deepcopy(self._raw)
            self._updated = True
        self._raw[key] = value

    def override(self, new_dic: dict[str, Any]) -> None:
        """覆盖传递给下游的数据

        :param new_dic: 新的字典
        """
        if new_dic is not self._raw:
            self._updated = True
        self._raw = new_dic

    def is_forbidden(self) -> bool:
        """检查数据是否被阻止传递给上游"""
        return self._forbidden

    def forbidden(self) -> None:
        """阻止数据传递给上游"""
        self._forbidden = True

    def get_dict(self, deepcopy: bool = True) -> dict[str, Any]:
        """获得传递给下游的数据的字典表示"""
        return copy.deepcopy(self._raw) if deepcopy else self._raw

    def get_json(self) -> str:
        """获得传递给下游的数据的 JSON 字符串表示"""
        return json.dumps(self._raw, ensure_ascii=False)


class EventToDownstream(ToDownstream):
    pass


class EchoToDownstream(ToDownstream):
    def set_data_param(self, key: str, value: Any) -> None:
        """设置传递给下游的数据的 `data` 字段中的字段

        :param key: 键
        :param value: 新值
        """
        if not self._updated:
            self._raw = copy.deepcopy(self._raw)
            self._updated = True
        self._raw["data"][key] = value
