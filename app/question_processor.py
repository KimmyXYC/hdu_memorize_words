# -*- coding: utf-8 -*-
"""
This module encapsulates the logic for processing questions, including searching
for answers in the local question bank, using AI for unknown questions, and
persisting AI-found answers back to the question bank.
"""
from __future__ import annotations
import json
import os
import re
from typing import List, Dict, Any, Optional

from loguru import logger

from .ai_client import ai_choose_answer
from .utils import save_error


class QuestionProcessor:
    """
    Handles the logic of finding answers to questions, coordinating between
    the local question bank and the AI client.
    """

    def __init__(self, ai_config: Optional[Dict[str, Any]] = None):
        """
        Initializes the QuestionProcessor.

        Args:
            ai_config: AI configuration dictionary.
        """
        self.question_bank = self._load_question_bank()
        self.ai_config = ai_config

    def reload_question_bank(self):
        """Reloads the question bank from the file."""
        self.question_bank = self._load_question_bank()
        logger.info("Question bank reloaded.")

    @staticmethod
    def _load_question_bank() -> Dict[str, Any]:
        """Loads the question bank from questions.json."""
        try:
            with open("questions.json", 'r', encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            logger.warning("File questions.json not found. Starting with an empty question bank.")
            return {}
        except json.JSONDecodeError:
            logger.error("File questions.json is not a valid JSON. Starting with an empty question bank.")
            return {}
        except Exception as e:
            logger.error(f"An unknown error occurred while loading the question bank: {e}")
            return {}

    @staticmethod
    def _normalize_text(s: str) -> str:
        """Normalizes a string for comparison by removing all whitespace."""
        try:
            return re.sub(r"\s+", "", str(s)).strip()
        except Exception:
            return str(s).strip()

    def _persist_answer(self, question: str, chosen_answer: str) -> None:
        """
        Writes the AI-determined answer to the questions.json file.

        - If the question is new, it's added.
        - If the question exists, the new meaning is appended (if not already present).
        """
        try:
            chosen_answer = str(chosen_answer).strip()
            if not chosen_answer:
                return

            # Use a temporary copy for modification
            current_bank = self._load_question_bank()

            existing = current_bank.get(question)
            action = ""
            if existing is None:
                current_bank[question] = chosen_answer
                action = "Added"
            else:
                meanings: List[str] = []
                if isinstance(existing, list):
                    for item in existing:
                        if isinstance(item, str):
                            parts = re.split(r"\s*[|｜]\s*", item)
                            meanings.extend(p for p in parts if p.strip())
                        else:
                            meanings.append(str(item).strip())
                elif isinstance(existing, str):
                    meanings.extend(p for p in re.split(r"\s*[|｜]\s*", existing) if p.strip())
                else:
                    meanings = [str(existing).strip()]

                seen = {self._normalize_text(m) for m in meanings}

                if self._normalize_text(chosen_answer) not in seen:
                    meanings.append(chosen_answer)
                    action = "Appended meaning"
                else:
                    action = "Already exists, no update needed"

                current_bank[question] = " | ".join(meanings)

            if "Added" in action or "Appended" in action:
                tmp_path = "questions.json.tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(current_bank, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, "questions.json")
                self.question_bank = current_bank # Update in-memory bank
                logger.success(f"{action} to question bank: {question} -> {current_bank[question]}")

        except Exception as e:
            logger.warning(f"Failed to write to question bank: {e}")

    def get_answer_index(self, question: str, options: List[str]) -> int:
        """
        Finds the answer for a given question and its options.

        It first checks the local question bank. If not found, it queries the AI.
        If the AI provides an answer, it's persisted to the bank.

        Args:
            question: The question title.
            options: A list of four answer options.

        Returns:
            The index (0-3) of the correct answer, or -1 if not found.
        """
        # 1. Search in the local question bank
        expected_answers = self.question_bank.get(question)
        if expected_answers:
            ordered_meanings: List[str] = []
            if isinstance(expected_answers, list):
                for item in expected_answers:
                    if isinstance(item, str):
                        ordered_meanings.extend(p for p in re.split(r"\s*[|｜]\s*", item) if p.strip())
            elif isinstance(expected_answers, str):
                ordered_meanings.extend(p for p in re.split(r"\s*[|｜]\s*", expected_answers) if p.strip())
            else:
                ordered_meanings.append(str(expected_answers).strip())

            seen_norm = set()
            unique_ordered_meanings = []
            for meaning in ordered_meanings:
                norm_meaning = self._normalize_text(meaning)
                if norm_meaning and norm_meaning not in seen_norm:
                    seen_norm.add(norm_meaning)
                    unique_ordered_meanings.append(norm_meaning)

            for norm_meaning in unique_ordered_meanings:
                for i, opt in enumerate(options):
                    if self._normalize_text(opt) == norm_meaning:
                        return i

        # 2. If not found in bank, try AI
        if self.ai_config and self.ai_config.get("enabled"):
            ai_idx = ai_choose_answer(question, options, self.ai_config)
            if ai_idx != -1:
                # 3. Persist AI answer
                self._persist_answer(question, options[ai_idx])
                return ai_idx

        # 4. If still not found, log error
        save_error((question, options))
        return -1

