# -*- coding: utf-8 -*-
"""Configuration loading utilities for users, AI options, and ChromeDriver path."""
from __future__ import annotations
import os
import yaml
from typing import Tuple, Optional, Dict, Any
from loguru import logger


def load_user_credentials() -> Tuple[Optional[str], Optional[str], int, int, str]:
    """Load username/password/answer_time_seconds/expected_score/mode from config.yaml (multi-user supported).

    Returns (username, password, answer_time_seconds, expected_score, mode) or (None, None, 300, 100, "browser") if not configured properly.
    Default answer_time_seconds is 300 (5 minutes).
    Default expected_score is 100 (answer all questions correctly).
    Default mode is "browser" (browser simulation).
    """
    cfg_path = "config.yaml"
    if not os.path.exists(cfg_path):
        logger.debug("未找到 config.yaml，跳过配置读取。")
        return None, None, 300, 100, "browser"
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

        users = cfg.get("users")
        if isinstance(users, list) and users:
            valid_users = []
            for idx, u in enumerate(users, start=1):
                if not isinstance(u, dict):
                    continue
                uname = str(u.get("username", "")).strip()
                pwd = str(u.get("password", "")).strip()
                addition = str(u.get("addition", "")).strip()
                # Read answer_time_seconds with default 300 (5 minutes)
                answer_time = u.get("answer_time_seconds", 300)
                try:
                    answer_time = int(answer_time)
                    if answer_time <= 0:
                        answer_time = 300
                except (ValueError, TypeError):
                    answer_time = 300
                # Read expected_score with default 100 (all correct)
                expected_score = u.get("expected_score", 100)
                try:
                    expected_score = int(expected_score)
                    if expected_score < 0:
                        expected_score = 0
                    elif expected_score > 100:
                        expected_score = 100
                except (ValueError, TypeError):
                    expected_score = 100
                # Read mode with default "browser"
                mode = str(u.get("mode", "browser")).strip().lower()
                if mode not in ["browser", "api"]:
                    mode = "browser"
                if uname and pwd:
                    valid_users.append({"idx": idx, "username": uname, "password": pwd, "addition": addition, "answer_time_seconds": answer_time, "expected_score": expected_score, "mode": mode})
            if valid_users:
                if len(valid_users) == 1:
                    u = valid_users[0]
                    add = f" ({u['addition']})" if u['addition'] else ""
                    logger.info(f"使用 config.yaml 中的账号: {u['username']}{add}")
                    logger.info(f"模式: {u['mode']}")
                    return u["username"], u["password"], u["answer_time_seconds"], u["expected_score"], u["mode"]
                else:
                    logger.info("检测到 config.yaml 中存在多个账号：")
                    for u in valid_users:
                        add = f" ({u['addition']})" if u['addition'] else ""
                        logger.info(f"{u['idx']}: {u['username']}{add}")
                    choice = input("请输入你想登录的账号（输入前面的序号）: ").strip()
                    try:
                        choice_idx = int(choice)
                        for u in valid_users:
                            if u["idx"] == choice_idx:
                                logger.info(f"模式: {u['mode']}")
                                return u["username"], u["password"], u["answer_time_seconds"], u["expected_score"], u["mode"]
                        logger.error("选择的序号不存在。")
                    except Exception:
                        logger.error("输入无效，未能选择账号。")
                    return None, None, 300, 100, "browser"

        logger.debug("config.yaml 未提供有效的 users 列表，将回退到命令行输入。")
        return None, None, 300, 100, "browser"
    except Exception as e:
        logger.error(f"读取 config.yaml 失败：{e}")
        return None, None, 300, 100, "browser"


def load_ai_config() -> Dict[str, Any]:
    """Load AI answer configuration from config.yaml.

    Returns dict with keys: enabled, base_url, token, model, temperature, timeout, retries.
    """
    cfg_path = "config.yaml"
    result: Dict[str, Any] = {"enabled": False}
    try:
        if not os.path.exists(cfg_path):
            return result
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        ai = cfg.get("ai") or {}
        if not isinstance(ai, dict):
            ai = {}
        base_url = str(ai.get("base_url") or ai.get("api_base") or ai.get("api_url") or ai.get("url") or "").strip()
        model = str(ai.get("model") or "").strip()
        token = ai.get("token")
        enable = ai.get("enable")
        if enable is None:
            enable = ai.get("enabled")
        enabled = bool(enable) if enable is not None else bool(base_url and model)
        temperature = ai.get("temperature", 0.2)
        timeout = ai.get("timeout", 15)
        retries = ai.get("retries", 3)
        result.update({
            "enabled": enabled,
            "base_url": base_url,
            "model": model,
            "token": str(token).strip() if token else None,
            "temperature": float(temperature) if isinstance(temperature, (int, float, str)) else 0.2,
            "timeout": int(timeout) if isinstance(timeout, (int, float, str)) else 15,
            "retries": int(retries) if isinstance(retries, (int, float, str)) else 3,
        })
        try:
            if result["retries"] < 0:
                result["retries"] = 0
        except Exception:
            result["retries"] = 3
        if not result["base_url"] or not result["model"]:
            result["enabled"] = False
        if result["enabled"]:
            logger.debug(f"AI已启用，使用模型: {result['model']}，API: {result['base_url']}")
        else:
            logger.debug("AI未启用或配置不完整，将在未命中题库时跳过AI。")
    except Exception as e:
        logger.warning(f"读取 AI 配置失败：{e}")
        result["enabled"] = False
    return result


def load_chrome_driver_path() -> Optional[str]:
    """Load ChromeDriver path from config.yaml (key: chrome_driver_path).

    Returns normalized absolute path string if provided, else None.
    """
    try:
        cfg_path = "config.yaml"
        if not os.path.exists(cfg_path):
            return None
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        raw = cfg.get("chrome_driver_path")
        if not raw:
            return None
        # Expand env vars and user home
        path = os.path.expandvars(os.path.expanduser(str(raw)))
        # Convert to absolute if relative
        path = os.path.abspath(path)
        if not os.path.exists(path):
            logger.warning(f"配置的 chrome_driver_path 不存在：{path}，将尝试使用 Selenium Manager 或 PATH 中的 chromedriver。")
            return path  # return anyway; caller may still try to use Selenium Manager when not exists
        logger.info(f"使用配置的 ChromeDriver: {path}")
        return path
    except Exception as e:
        logger.warning(f"读取 chrome_driver_path 失败：{e}")
        return None
