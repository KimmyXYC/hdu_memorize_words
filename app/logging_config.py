# -*- coding: utf-8 -*-
"""Loguru logging configuration utilities."""
import os
import yaml
from loguru import logger

VALID_LOG_LEVELS = {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}

def init_logger_from_config() -> None:
    """Initialize Loguru file sink based on config.yaml's log_level (default INFO).
    This keeps console logging and adds run.log file logging.
    """
    level = "INFO"
    try:
        if os.path.exists("config.yaml"):
            with open("config.yaml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            cfg_level = str(cfg.get("log_level", "")).strip().upper()
            if cfg_level in VALID_LOG_LEVELS:
                level = cfg_level
    except Exception:
        # Ignore errors and keep default level
        pass
    try:
        logger.add("run.log", level=level, encoding="utf-8", enqueue=True)
        logger.info(f"日志初始化，等级: {level}，文件: run.log")
    except Exception:
        # Ignore file sink errors; console logging remains
        pass
