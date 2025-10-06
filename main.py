# -*- coding: utf-8 -*-
"""项目主入口。

使用方式：
    python main.py

说明：
- 实际业务逻辑位于模块 hdu_bot.HDU 中。
- 日志初始化在 logging_config.init_logger_from_config 中完成，写入 run.log。
"""
from __future__ import annotations
from app.logging_config import init_logger_from_config
from app.hdu_bot import HDU


def main() -> None:
    # 初始化日志（文件 + 控制台）
    init_logger_from_config()

    # 启动自动化流程
    hdu = HDU()
    hdu.start()


if __name__ == "__main__":
    main()
