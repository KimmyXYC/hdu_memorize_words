# -*- coding: utf-8 -*-
"""Utility helpers for the project."""
from __future__ import annotations
from typing import List, Tuple


def save_error(question_options: Tuple[str, List[str]]) -> None:
    """Append unrecognized question and options to error.txt."""
    question, options = question_options
    error_message = f"{question}\n{options}\n"
    with open("error.txt", "a", encoding='utf-8') as f:
        f.write(error_message)
