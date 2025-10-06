# -*- coding: utf-8 -*-
"""AI client for answer selection using an OpenAI-compatible API."""
from __future__ import annotations
import re
import time
import requests
from typing import List, Optional, Dict, Any
from loguru import logger
from .config_loader import load_ai_config


def ai_choose_answer(question: str, options_list: List[str], cfg: Optional[Dict[str, Any]] = None) -> int:
    """Call AI service to choose an answer among A/B/C/D.

    Returns 0-3 for index, or -1 on failure.
    """
    if cfg is None:
        cfg = load_ai_config()
    if not cfg.get("enabled"):
        return -1

    base_url = cfg.get("base_url", "").rstrip("/")
    endpoint = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if cfg.get("token"):
        headers["Authorization"] = f"Bearer {cfg['token']}"

    user_content = (
        f"请根据题目选择最合适的选项，只输出A/B/C/D其中一个字母。\n"
        f"题目：{question}\n"
        f"选项：\n"
        f"A. {options_list[0]}\n"
        f"B. {options_list[1]}\n"
        f"C. {options_list[2]}\n"
        f"D. {options_list[3]}\n"
        f"注意：只输出A、B、C或D，不要输出其他任何内容。"
    )
    payload = {
        "model": cfg.get("model"),
        "messages": [
            {"role": "system", "content": "你是英语单词选择题助手。根据题干与四个选项选择正确答案。"},
            {"role": "user", "content": user_content},
        ],
        "temperature": cfg.get("temperature", 0.2),
        "max_tokens": 5,
    }

    # Retry policy
    retries_cfg = cfg.get("retries", 3)
    try:
        retries = int(retries_cfg)
    except Exception:
        retries = 3
    if retries < 0:
        retries = 0
    total_attempts = 1 + retries

    for attempt in range(1, total_attempts + 1):
        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=cfg.get("timeout", 15))
            if resp.status_code != 200:
                logger.warning(f"[AI 第{attempt}/{total_attempts}次] HTTP {resp.status_code}: {resp.text[:200]}")
                if attempt < total_attempts:
                    time.sleep(0.5)
                continue
            data = resp.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except Exception:
                content = str(data)
            text = str(content).strip().upper()
            idx = -1
            m = re.search(r"([ABCD])", text)
            if m:
                letter = m.group(1)
                idx = {"A": 0, "B": 1, "C": 2, "D": 3}.get(letter, -1)
            if idx == -1:
                m2 = re.search(r"\b([1-4])\b", text)
                if m2:
                    idx = int(m2.group(1)) - 1
            if idx == -1:
                for i, opt in enumerate(options_list):
                    if str(opt).strip() and str(opt).strip() in text:
                        idx = i
                        break
            if idx in (0, 1, 2, 3):
                logger.info(f"AI判定答案: {chr(idx + 65)}（第{attempt}次）")
                return idx
            else:
                logger.warning(f"[AI 第{attempt}/{total_attempts}次] 返回无法解析: {text}")
                if attempt < total_attempts:
                    time.sleep(0.5)
        except Exception as e:
            logger.warning(f"[AI 第{attempt}/{total_attempts}次] 请求异常：{e}")
            if attempt < total_attempts:
                time.sleep(0.5)
    return -1
