"""类型化运行配置与安全护栏。

所有密钥与运行模式集中在此，从 `.env` 注入。运行模式与 kill switch 是一等公民：
- 默认 `trading_mode=paper`；切换到 `live` 必须显式二次确认，否则拒绝启动。
- `kill_switch=true` 时禁止任何下单。
其他模块只能通过 `Settings` 读取密钥，禁止散落的 `os.getenv`。
"""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- 运行模式与护栏 ---
    trading_mode: Literal["paper", "live"] = "paper"
    live_confirmed: bool = False
    kill_switch: bool = False

    # --- LLM（信号层）---
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.0
    llm_api_key: str | None = None

    # --- 券商 / 执行 ---
    broker_provider: str = "alpaca_paper"
    alpaca_api_key_id: str | None = None
    alpaca_api_secret: str | None = None

    @model_validator(mode="after")
    def _guard_live_mode(self) -> Settings:
        if self.trading_mode == "live" and not self.live_confirmed:
            msg = "trading_mode=live 需要 live_confirmed=true（安全护栏）"
            raise ValueError(msg)
        return self

    @property
    def can_trade(self) -> bool:
        """是否允许下单：未触发 kill switch，且为 paper 或已确认的 live。"""
        if self.kill_switch:
            return False
        return self.trading_mode == "paper" or self.live_confirmed
