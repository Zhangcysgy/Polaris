"""核心 — LLM 客户端统一接口

支持 DeepSeek + 智谱双后端，统一 OpenAI 兼容接口。
读 polaris.yaml 获取 API Key 和模型配置。

用法:
    client = LLMClient.from_config()
    reply = client.chat([
        {"role": "system", "content": "你是一位审稿人"},
        {"role": "user", "content": "请审稿这篇论文..."}
    ])
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Optional

# 尝试导入 openai SDK
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


@dataclass
class LLMResponse:
    """LLM 回复。"""
    content: str
    model: str
    usage: dict = None       # {"prompt_tokens": N, "completion_tokens": M}
    elapsed_seconds: float = 0.0
    finish_reason: str = "stop"

    def __post_init__(self):
        if self.usage is None:
            self.usage = {}


@dataclass
class LLMConfig:
    """单个 LLM 后端的配置。"""
    provider: str            # "deepseek" | "zhipu"
    model: str               # "deepseek-chat" | "glm-4-plus"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.3
    max_tokens: int = 8192


class LLMClient:
    """统一的 LLM 调用接口。

    用法:
        # 方式1：从 polaris.yaml 加载
        client = LLMClient.from_config()

        # 方式2：手动配置
        client = LLMClient(LLMConfig(
            provider="deepseek",
            model="deepseek-chat",
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com/v1",
        ))

        # 调用
        response = client.chat(messages)
        print(response.content)
    """

    # 已知模型的价格（per 1M tokens, USD）
    PRICING = {
        "deepseek-chat":    {"input": 0.27, "output": 1.10},
        "deepseek-reasoner":{"input": 0.55, "output": 2.19},
        "glm-4-plus":       {"input": 7.00, "output": 7.00},    # 估算
        "glm-4-flash":      {"input": 0.14, "output": 0.14},    # 估算
    }

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: Optional[OpenAI] = None if HAS_OPENAI else None
        self._total_cost: float = 0.0

    @classmethod
    def from_config(cls, config_path: str = "polaris.yaml", backend: str = "primary") -> "LLMClient":
        """从 polaris.yaml 加载配置。"""
        from .config import get_config

        cfg = get_config(config_path)
        llm_cfg = cfg.get("llm", backend)
        if llm_cfg is None:
            raise ValueError(f"LLM 配置 '{backend}' 未在 polaris.yaml 中找到。")

        api_key = os.environ.get(llm_cfg.get("api_key_env", ""), "")
        if not api_key:
            # 尝试从配置直接读取
            api_key = llm_cfg.get("api_key", "")

        return cls(LLMConfig(
            provider=llm_cfg.get("provider", "deepseek"),
            model=llm_cfg.get("model", "deepseek-chat"),
            api_key=api_key,
            base_url=llm_cfg.get("base_url", "https://api.deepseek.com/v1"),
            temperature=llm_cfg.get("temperature", 0.3),
            max_tokens=llm_cfg.get("max_tokens", 8192),
        ))

    @property
    def client(self) -> "OpenAI":
        """延迟初始化 OpenAI 客户端。"""
        if self._client is None:
            if not HAS_OPENAI:
                raise ImportError(
                    "需要 openai Python 包。安装: pip install openai"
                )
            if not self.config.api_key:
                raise ValueError(
                    f"API Key 未设置。请设置环境变量或检查 polaris.yaml。\n"
                    f"Provider: {self.config.provider}"
                )
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )
        return self._client

    def chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_retries: int = 3,
        timeout_seconds: int = 120,
    ) -> LLMResponse:
        """发送消息到 LLM 并获取回复。

        Args:
            messages: OpenAI 格式的消息列表 [{"role": ..., "content": ...}]
            temperature: 覆盖配置文件中的温度
            max_tokens: 覆盖配置文件中的最大 token 数
            max_retries: 最大重试次数
            timeout_seconds: 超时时间

        Returns:
            LLMResponse 包含回复内容和元数据
        """
        temp = temperature if temperature is not None else self.config.temperature
        mt = max_tokens if max_tokens is not None else self.config.max_tokens

        last_error = None
        for attempt in range(max_retries):
            try:
                start = time.time()
                completion = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=mt,
                    timeout=timeout_seconds,
                )
                elapsed = time.time() - start

                choice = completion.choices[0]
                usage = completion.usage

                response = LLMResponse(
                    content=choice.message.content or "",
                    model=self.config.model,
                    usage={
                        "prompt_tokens": usage.prompt_tokens if usage else 0,
                        "completion_tokens": usage.completion_tokens if usage else 0,
                        "total_tokens": usage.total_tokens if usage else 0,
                    },
                    elapsed_seconds=round(elapsed, 2),
                    finish_reason=choice.finish_reason or "stop",
                )

                # 累计成本
                self._add_cost(usage)
                return response

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = 2 ** attempt  # 指数退避
                    time.sleep(wait)
                else:
                    break

        raise RuntimeError(
            f"LLM 调用失败（{max_retries}次重试后）:\n"
            f"  Provider: {self.config.provider}\n"
            f"  Model: {self.config.model}\n"
            f"  Error: {last_error}"
        )

    def _add_cost(self, usage) -> None:
        """累计 API 调用成本。"""
        if usage is None:
            return
        pricing = self.PRICING.get(self.config.model, {})
        input_cost = pricing.get("input", 0) * usage.prompt_tokens / 1_000_000
        output_cost = pricing.get("output", 0) * usage.completion_tokens / 1_000_000
        self._total_cost += input_cost + output_cost

    @property
    def total_cost(self) -> float:
        """累计 API 调用成本（USD）。"""
        return round(self._total_cost, 6)

    def estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数。

        简易估算：中文 ~1.5 字符/token，英文 ~4 字符/token。
        """
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)
