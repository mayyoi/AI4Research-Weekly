# -*- coding: utf-8 -*-
"""
AI 接口层：支持 4 个平台，谁可用就用谁。

  1. github   —— GitHub Models，用仓库自带的 GITHUB_TOKEN，**不需要任何 Key**
  2. deepseek —— DeepSeek（OpenAI 兼容接口）
  3. openai   —— OpenAI 官方接口（也支持自定义中转地址）
  4. gemini   —— Google Gemini

好处：一个平台挂了会立刻换下一个；全部不可用时上层还有"翻译兜底"，
不会给你发一封全是英文标题的邮件。
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
GITHUB_MODELS_URL = "https://models.github.ai/inference/chat/completions"
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
GEMINI_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"


class LLMError(RuntimeError):
    """普通失败：可以重试，也可以换下一个批次。"""


class AuthError(LLMError):
    """Key 或权限问题：重试没有意义，直接换下一个平台。"""


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
    """一个能返回 JSON 的模型接口。provider 决定走哪套协议。"""

    def __init__(self, provider: str, api_key: str, models: list[str], base_url: str = ""):
        self.provider = provider
        self.api_key = api_key
        self.models = models
        self.base_url = base_url

    @property
    def label(self) -> str:
        first = self.models[0] if self.models else "?"
        return f"{self.provider}:{first}"

    def generate_json(self, prompt: str, system: str = "", temperature: float = 0.2,
                      max_retries: int = 3, timeout: int = 45):
        if self.provider == "gemini":
            return self._call_gemini(prompt, system, temperature, max_retries, timeout)
        return self._call_openai_compatible(prompt, system, temperature, max_retries, timeout)

    # ---------------- OpenAI 兼容协议（openai / github / deepseek） ----------------
    def _call_openai_compatible(self, prompt: str, system: str, temperature: float,
                               max_retries: int, timeout: int):
        url = self.base_url or OPENAI_URL
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
                    data = _post_json(url, payload, {"Authorization": f"Bearer {self.api_key}"}, timeout)
                    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
                    parsed = _extract_json(content)
                    if parsed is None:
                        raise LLMError("返回内容不是合法 JSON")
                    return parsed
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", errors="replace")[:300]
                    last_error = LLMError(f"{self.provider}/{model} HTTP {exc.code}: {detail}")
                    if exc.code in (401, 403):
                        raise AuthError(
                            f"{self.provider} 拒绝了这个凭据（HTTP {exc.code}）：{detail[:160]}"
                        )
                    if exc.code == 404:
                        break  # 模型名不存在，换下一个
                    if exc.code == 400:
                        lowered = detail.lower()
                        if "temperature" in lowered and "temperature" in payload:
                            print(f"  [AI] {model} 不支持 temperature，去掉该参数重试")
                            payload.pop("temperature", None)
                            continue
                        if "response_format" in lowered and "response_format" in payload:
                            print(f"  [AI] {model} 不支持 response_format，去掉该参数重试")
                            payload.pop("response_format", None)
                            continue
                        raise last_error
                    wait = min(2 ** attempt, 20)
                    print(f"  [AI] {model} 第 {attempt} 次失败（HTTP {exc.code}），{wait}s 后重试")
                    time.sleep(wait)
                except AuthError:
                    raise
                except LLMError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    # 网络层错误（超时 / 连不上）：重试也没有意义，直接换下一个模型
                    if isinstance(exc, (urllib.error.URLError, TimeoutError, OSError)):
                        print(f"  [AI] {model} 网络不可用（{type(exc).__name__}），换下一个模型")
                        break
                    wait = min(2 ** attempt, 20)
                    print(f"  [AI] {model} 第 {attempt} 次失败（{type(exc).__name__}），{wait}s 后重试")
                    time.sleep(wait)
        raise LLMError(str(last_error) if last_error else f"{self.provider} 调用失败")

    # ---------------- Gemini ----------------
    def _call_gemini(self, prompt: str, system: str, temperature: float,
                     max_retries: int, timeout: int):
        last_error = None
        for model in self.models:
            body = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
            }
            if system:
                body["systemInstruction"] = {"parts": [{"text": system}]}
            url = f"{GEMINI_ROOT}/{model}:generateContent?" + urllib.parse.urlencode({"key": self.api_key})
            for attempt in range(1, max_retries + 1):
                try:
                    data = _post_json(url, body, {}, timeout)
                    candidates = data.get("candidates") or []
                    if not candidates:
                        raise LLMError(f"模型没有返回内容：{data.get('promptFeedback')}")
                    parts = (candidates[0].get("content") or {}).get("parts") or []
                    parsed = _extract_json("".join(part.get("text", "") for part in parts))
                    if parsed is None:
                        raise LLMError("返回内容不是合法 JSON")
                    return parsed
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", errors="replace")[:300]
                    last_error = LLMError(f"gemini/{model} HTTP {exc.code}: {detail}")
                    if exc.code in (400, 401, 403):
                        raise AuthError(f"gemini 拒绝了这个凭据（HTTP {exc.code}）：{detail[:160]}")
                    if exc.code == 404:
                        break
                    wait = min(2 ** attempt, 20)
                    print(f"  [AI] {model} 第 {attempt} 次失败（HTTP {exc.code}），{wait}s 后重试")
                    time.sleep(wait)
                except AuthError:
                    raise
                except LLMError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if isinstance(exc, (urllib.error.URLError, TimeoutError, OSError)):
                        print(f"  [AI] {model} 网络不可用（{type(exc).__name__}），换下一个模型")
                        break
                    wait = min(2 ** attempt, 20)
                    print(f"  [AI] {model} 第 {attempt} 次失败（{type(exc).__name__}），{wait}s 后重试")
                    time.sleep(wait)
        raise LLMError(str(last_error) if last_error else "Gemini 调用失败")


def build_llms(cfg) -> list[LLM]:
    """
    按 config.LLM_PREFERENCE 的顺序组装可用的平台。
    只有对应的凭据存在时才会被启用；顺序决定优先尝试谁。
    """
    github_token = os.getenv("GITHUB_TOKEN", "").strip()
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_base = os.getenv("OPENAI_BASE_URL", "").strip()
    openai_model_override = os.getenv("OPENAI_MODEL", "").strip()

    candidates = {
        "github": LLM("github", github_token, list(cfg.GITHUB_MODELS), GITHUB_MODELS_URL),
        "deepseek": LLM("deepseek", deepseek_key, list(cfg.DEEPSEEK_MODELS), DEEPSEEK_URL),
        "openai": LLM(
            "openai",
            openai_key,
            [openai_model_override] if openai_model_override else list(cfg.OPENAI_MODELS),
            openai_base or OPENAI_URL,
        ),
        "gemini": LLM("gemini", gemini_key, list(cfg.GEMINI_MODELS)),
    }

    ordered: list[LLM] = []
    for name in list(cfg.LLM_PREFERENCE) + list(candidates):
        client = candidates.get(name)
        if client and client.api_key and client not in ordered:
            ordered.append(client)
    return ordered
