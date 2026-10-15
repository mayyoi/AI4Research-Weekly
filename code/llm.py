# -*- coding: utf-8 -*-
"""
AI 接口层：同时支持 OpenAI 和 Google Gemini，谁有 Key 就用谁。

为什么写两个？
  因为这两家的接口格式、错误码、参数限制都不一样。写在一起的好处是：
  一个不可用时能自动切到另一个，而不是直接给你发一封空邮件。
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"


class LLMError(RuntimeError):
    pass


def _extract_json(text: str):
    """从模型回复里抠出 JSON（模型有时会包在 ```json 代码块里）。"""
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    return None


def _post_json(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class LLM:
    """一个"能返回 JSON 的模型接口"。provider 是 openai 或 gemini。"""

    def __init__(self, provider: str, api_key: str, models: list[str], base_url: str = ""):
        self.provider = provider
        self.api_key = api_key
        self.models = models
        self.base_url = base_url

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.models[0] if self.models else '?'}"

    def generate_json(self, prompt: str, system: str = "", temperature: float = 0.2,
                      max_retries: int = 3, timeout: int = 120):
        if self.provider == "openai":
            return self._call_openai(prompt, system, temperature, max_retries, timeout)
        return self._call_gemini(prompt, system, temperature, max_retries, timeout)

    # ---------------- OpenAI ----------------
    def _openai_once(self, model: str, payload: dict, timeout: int) -> dict:
        url = self.base_url or OPENAI_URL
        return _post_json(url, payload, {"Authorization": f"Bearer {self.api_key}"}, timeout)

    def _call_openai(self, prompt: str, system: str, temperature: float,
                     max_retries: int, timeout: int):
        last_error = None
        for model in self.models:
            payload = {
                "model": model,
                "messages": (
                    ([{"role": "system", "content": system}] if system else [])
                    + [{"role": "user", "content": prompt}]
                ),
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            }
            for attempt in range(1, max_retries + 1):
                try:
                    data = self._openai_once(model, payload, timeout)
                    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
                    parsed = _extract_json(content)
                    if parsed is None:
                        raise LLMError("返回内容不是合法 JSON")
                    return parsed
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", errors="replace")[:400]
                    last_error = LLMError(f"{model} HTTP {exc.code}: {detail}")
                    if exc.code in (401, 403):
                        raise LLMError(f"OpenAI 拒绝了这个 Key（HTTP {exc.code}）：{detail}")
                    if exc.code == 404:
                        break  # 模型名不存在，换下一个
                    if exc.code == 400:
                        # 新版模型常常不支持 temperature 或 response_format，
                        # 这里按错误提示把不支持的参数去掉再试一次。
                        lowered = detail.lower()
                        if "temperature" in lowered and "temperature" in payload:
                            print(f"  [AI] {model} 不支持 temperature，已去掉该参数重试")
                            payload.pop("temperature", None)
                            continue
                        if "response_format" in lowered and "response_format" in payload:
                            print(f"  [AI] {model} 不支持 response_format，已去掉该参数重试")
                            payload.pop("response_format", None)
                            continue
                        raise last_error
                    wait = min(2 ** attempt, 20)
                    print(f"  [AI] {model} 第 {attempt} 次失败（HTTP {exc.code}），{wait}s 后重试")
                    time.sleep(wait)
                except LLMError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    wait = min(2 ** attempt, 20)
                    print(f"  [AI] {model} 第 {attempt} 次失败（{type(exc).__name__}），{wait}s 后重试")
                    time.sleep(wait)
        raise LLMError(str(last_error) if last_error else "OpenAI 调用失败")

    # ---------------- Gemini ----------------
    def _gemini_once(self, model: str, prompt: str, system: str, temperature: float, timeout: int) -> dict:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        url = f"{GEMINI_ROOT}/{model}:generateContent?" + urllib.parse.urlencode({"key": self.api_key})
        return _post_json(url, payload, {}, timeout)

    def _call_gemini(self, prompt: str, system: str, temperature: float,
                     max_retries: int, timeout: int):
        last_error = None
        for model in self.models:
            for attempt in range(1, max_retries + 1):
                try:
                    data = self._gemini_once(model, prompt, system, temperature, timeout)
                    candidates = data.get("candidates") or []
                    if not candidates:
                        raise LLMError(f"模型没有返回内容：{data.get('promptFeedback')}")
                    parts = (candidates[0].get("content") or {}).get("parts") or []
                    text = "".join(part.get("text", "") for part in parts)
                    parsed = _extract_json(text)
                    if parsed is None:
                        raise LLMError("返回内容不是合法 JSON")
                    return parsed
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", errors="replace")[:300]
                    last_error = LLMError(f"{model} HTTP {exc.code}: {detail}")
                    if exc.code in (400, 401, 403):
                        raise last_error
                    if exc.code == 404:
                        break
                    wait = min(2 ** attempt, 20)
                    print(f"  [AI] {model} 第 {attempt} 次失败（HTTP {exc.code}），{wait}s 后重试")
                    time.sleep(wait)
                except LLMError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    wait = min(2 ** attempt, 20)
                    print(f"  [AI] {model} 第 {attempt} 次失败（{type(exc).__name__}），{wait}s 后重试")
                    time.sleep(wait)
        raise LLMError(str(last_error) if last_error else "Gemini 调用失败")


def build_llms(cfg) -> list[LLM]:
    """
    按 config.LLM_PREFERENCE 的顺序，把环境里能用的 Key 组成一个列表。
    列表里第一个是首选，跑不通会自动换下一个。
    """
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    openai_models = [os.getenv("OPENAI_MODEL", "").strip()] if os.getenv("OPENAI_MODEL", "").strip() else []

    available = {
        "openai": LLM("openai", openai_key, openai_models or list(cfg.OPENAI_MODELS), base_url),
        "gemini": LLM("gemini", gemini_key, list(cfg.GEMINI_MODELS)),
    }
    keys = {"openai": bool(openai_key), "gemini": bool(gemini_key)}

    ordered = []
    for name in cfg.LLM_PREFERENCE:
        if name in available and keys[name]:
            ordered.append(available[name])
    for name, client in available.items():  # 兜底：把剩下有 Key 的也放进来
        if keys[name] and client not in ordered:
            ordered.append(client)
    return ordered
