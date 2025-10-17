# -*- coding: utf-8 -*-
"""Utility helpers for the project."""
from __future__ import annotations
import secrets
from typing import List, Tuple


def save_error(question_options: Tuple[str, List[str]]) -> None:
    """Append unrecognized question and options to error.txt."""
    question, options = question_options
    error_message = f"{question}\n{options}\n"
    with open("error.txt", "a", encoding='utf-8') as f:
        f.write(error_message)


def generate_skl_ticket() -> str:
    """Generate a random skl-ticket for API requests.
    
    Based on Go implementation: generates a 21-character random string
    using a specific character set.
    """
    charset = "useandom-26T198340PX75pxJACKVERYMINDBUSHWOLF_GQZbfghjklqvwyzrict"
    length = 21
    # Generate random bytes and map to charset
    random_bytes = secrets.token_bytes(length)
    ticket = ''.join(charset[b & 63] for b in random_bytes)
    return ticket
