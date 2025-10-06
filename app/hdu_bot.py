# -*- coding: utf-8 -*-
"""HDU English self-test automation bot (core browser automation)."""
from __future__ import annotations
import json
import os
import re
import time
from typing import Tuple, List

from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait

from .config_loader import load_user_credentials, load_chrome_driver_path
from .ai_client import ai_choose_answer
from .utils import save_error


class HDU:
    """自动化答题主类，封装核心操作逻辑"""

    def __init__(self):
        """初始化浏览器驱动并加载题库"""
        options = webdriver.ChromeOptions()
        # 移动端模拟配置
        options.add_experimental_option('mobileEmulation', {'deviceName': 'iPhone 6'})

        # 浏览器驱动配置：优先使用 config.yaml 中的 chrome_driver_path；否则交给 Selenium Manager 或 PATH
        driver_path = load_chrome_driver_path()
        try:
            if driver_path:
                if os.path.exists(driver_path):
                    service = Service(executable_path=driver_path)
                    self.driver = webdriver.Chrome(options=options, service=service)
                else:
                    logger.warning(f"配置的 chrome_driver_path 路径不存在：{driver_path}，将尝试使用默认驱动（Selenium Manager 或 PATH）。")
                    self.driver = webdriver.Chrome(options=options)
            else:
                self.driver = webdriver.Chrome(options=options)
        except Exception as e:
            logger.error(f"初始化 Chrome 驱动失败：{e}")
            raise
        # 存储最近一次定位到的用户名/密码输入框，便于后续回车提交等兜底操作
        self._last_user_el = None
        self._last_pwd_el = None

        # 题库加载处理
        try:
            with open("questions.json", 'r', encoding='utf-8') as file:
                self.answer = json.load(file)
        except FileNotFoundError:
            logger.error("文件 questions.json 未找到。")
            self.answer = {}
        except json.JSONDecodeError:
            logger.error("文件 questions.json 不是有效的 JSON 格式。")
            self.answer = {}
        except Exception as e:
            logger.error(f"加载题库时发生未知错误: {e}")
            self.answer = {}

    def login(self):
        """处理用户登录凭证：优先 config.yaml（多用户），否则命令行输入。"""
        username, password = load_user_credentials()
        if username and password:
            logger.info("使用 config.yaml 中的登录信息")
        else:
            username = input(" 请输入用户名：")
            password = input(" 请输入密码：")

        self.login_web(username, password)

    def login_web(self, username: str, password: str) -> None:
        """执行网页登录操作：先打开业务页触发重定向到 SSO，再自动填充登录。"""
        # 先打开业务页面，由其自动跳转到带 service/state 的 SSO 登录页
        list_url = "https://skl.hduhelp.com/#/english/list"
        try:
            self.driver.get(list_url)
        except Exception:
            pass
        # 等待跳转到 SSO（含 service 参数）；若未跳转则回退到 SSO 登录首页
        try:
            WebDriverWait(self.driver, 15).until(lambda d: "sso.hdu.edu.cn/login" in d.current_url)
        except Exception:
            try:
                self.driver.get("https://sso.hdu.edu.cn/login")
            except Exception:
                pass

        # 等待页面和脚本初始化完成
        try:
            WebDriverWait(self.driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
        except Exception:
            pass

        # 尝试切换到“用户名密码”登录方式（有些场景默认是其他方式）
        try:
            tab = WebDriverWait(self.driver, 5).until(
                ec.element_to_be_clickable((
                    By.XPATH,
                    "//*[contains(text(),'用户名密码') or contains(text(),'账号密码') or contains(text(),'用户名')]/ancestor-or-self::*[self::a or self::button or self::div]"
                ))
            )
            try:
                tab.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", tab)
            logger.debug("已切换到‘用户名密码’登录方式")
        except Exception:
            # 如果不存在该入口，忽略
            pass

        def _find_interactable(selectors, timeout: int = 15):
            """在当前文档内查找可见可交互的元素，支持多选择器，直到超时。"""
            end = time.time() + timeout
            while time.time() < end:
                for by, sel in selectors:
                    try:
                        elements = self.driver.find_elements(by, sel)
                        for el in elements:
                            try:
                                if el.is_displayed() and el.is_enabled() and el.size.get('width', 1) > 0 and el.size.get('height', 1) > 0:
                                    try:
                                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                                    except Exception:
                                        pass
                                    return el
                            except Exception:
                                continue
                    except Exception:
                        continue
                time.sleep(0.25)
            return None

        def _fill_inputs_in_current_context() -> bool:
            # 常见用户名/密码字段匹配（适配新版 SSO）
            user_selectors = [
                (By.CSS_SELECTOR, "input[name='username']"),
                (By.CSS_SELECTOR, "input#username"),
                (By.CSS_SELECTOR, "input[autocomplete='username']"),
                (By.XPATH, "//input[contains(@placeholder,'用户名') or contains(@placeholder,'账号') or contains(@placeholder,'学工号') or contains(@placeholder,'手机号') or contains(@placeholder,'邮箱')]") ,
                (By.XPATH, "//input[@type='text' or @type='email' or @type='tel']"),
            ]
            pwd_selectors = [
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.CSS_SELECTOR, "input[name='password']"),
                (By.CSS_SELECTOR, "input#password"),
                (By.CSS_SELECTOR, "input[name='passwordPre']"),
                (By.XPATH, "//input[contains(@placeholder,'密码') and @type='password']"),
            ]

            user_el = _find_interactable(user_selectors, timeout=15)
            pwd_el = _find_interactable(pwd_selectors, timeout=15)
            if not user_el or not pwd_el:
                return False

            # 填充用户名
            try:
                try:
                    user_el.clear()
                except Exception:
                    pass
                WebDriverWait(self.driver, 3).until(ec.element_to_be_clickable(user_el))
                try:
                    user_el.click()
                except Exception:
                    pass
                user_el.send_keys(username)
            except Exception:
                # 兜底：通过 JS 注入值
                try:
                    self.driver.execute_script(
                        "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
                        user_el, username
                    )
                except Exception:
                    return False

            # 填充密码
            try:
                try:
                    pwd_el.clear()
                except Exception:
                    pass
                WebDriverWait(self.driver, 3).until(ec.element_to_be_clickable(pwd_el))
                try:
                    pwd_el.click()
                except Exception:
                    pass
                pwd_el.send_keys(password)
            except Exception:
                # 兜底：通过 JS 注入值
                try:
                    self.driver.execute_script(
                        "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
                        pwd_el, password
                    )
                except Exception:
                    return False

            try:
                self._last_user_el = user_el
                self._last_pwd_el = pwd_el
            except Exception:
                pass
            try:
                self.driver.execute_script(
                    "for(const el of arguments){ if(el){ el.dispatchEvent(new Event('change',{bubbles:true})); el.dispatchEvent(new Event('blur',{bubbles:true})); }}",
                    user_el, pwd_el
                )
            except Exception:
                pass
            logger.info("已自动填入账号密码")
            return True

        # 先在主文档尝试
        filled = _fill_inputs_in_current_context()

        # 若主文档未找到，尝试在 iframe 中查找
        frame_used = None
        if not filled:
            try:
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            except Exception:
                iframes = []
            for idx, frame in enumerate(iframes):
                try:
                    self.driver.switch_to.default_content()
                    self.driver.switch_to.frame(frame)
                    if _fill_inputs_in_current_context():
                        logger.debug(f"在第 {idx} 个 iframe 中找到并填充了登录表单")
                        filled = True
                        frame_used = frame
                        break
                except Exception:
                    continue
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass

        # 点击登录/提交按钮
        if filled:
            # 若在某个 iframe 中完成填充，则切换到该 iframe 再查找登录按钮
            if 'frame_used' in locals() and frame_used is not None:
                try:
                    self.driver.switch_to.default_content()
                    self.driver.switch_to.frame(frame_used)
                    logger.debug("已切换到包含登录按钮的 iframe，准备点击提交")
                except Exception:
                    pass
            submit_candidates = [
                (By.XPATH, "//button[contains(., '登录') or contains(., '登 录')]") ,
                (By.XPATH, "//span[normalize-space(text())='登录' or normalize-space(text())='登 录']/ancestor::*[self::button or self::a][1]"),
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.CSS_SELECTOR, "input[type='submit']"),
                (By.CSS_SELECTOR, "button.login-btn"),
                (By.CSS_SELECTOR, "button.el-button--primary"),
            ]
            clicked = False
            for by, sel in submit_candidates:
                try:
                    btns = self.driver.find_elements(by, sel)
                    btn = None
                    for b in btns:
                        try:
                            if b.is_displayed() and b.is_enabled():
                                btn = b
                                break
                        except Exception:
                            continue
                    if not btn:
                        continue
                    try:
                        WebDriverWait(self.driver, 5).until(ec.element_to_be_clickable(btn))
                    except Exception:
                        pass
                    try:
                        btn.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", btn)
                    logger.info("已尝试自动点击登录按钮")
                    clicked = True
                    break
                except Exception:
                    continue
            if not clicked:
                # 尝试通过回车提交
                try:
                    if getattr(self, "_last_pwd_el", None):
                        self._last_pwd_el.send_keys(Keys.ENTER)
                        logger.info("已尝试通过回车提交登录表单")
                        clicked = True
                except Exception:
                    pass
            if not clicked:
                # JS 兜底提交
                try:
                    self.driver.execute_script(
                        "(function(){"
                        "var btns = Array.from(document.querySelectorAll('button, input[type=\"submit\"]'));"
                        "for (var i=0;i<btns.length;i++){"
                        "var b=btns[i];"
                        "var visible = !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length);"
                        "if (visible && !b.disabled){"
                        "var txt = (b.innerText || b.value || '').trim();"
                        "if (txt.indexOf('登录') !== -1 || txt.indexOf('登 录') !== -1 || b.type === 'submit'){"
                        "try{ b.click(); return; }catch(e){}"
                        "}"
                        "}"
                        "}"
                        "var f = document.querySelector('form');"
                        "if (f){ try{ f.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})); }catch(e){} try{ f.submit(); }catch(e){} }"
                        "})();"
                    )
                    logger.info("已尝试通过脚本提交登录表单")
                    clicked = True
                except Exception:
                    pass
            if not clicked:
                logger.warning("未能自动点击登录按钮，请手动点击登录。")

            # 等待从 SSO 页面跳转完成
            try:
                WebDriverWait(self.driver, 10).until(lambda d: "sso.hdu.edu.cn/login" not in d.current_url)
            except Exception:
                pass
        else:
            logger.error("未能定位到登录输入框，请手动在页面完成登录。")

        # 不论是否自动点了登录，都导航到业务页面继续后续流程（若 SSO 已登录，将自动带票登录）
        try:
            self.driver.get("https://skl.hduhelp.com/#/english/list")
        except Exception:
            pass

        input("请手动开始考试后按回车继续")

    def _normalize_text(self, s: str) -> str:
        """规范化字符串用于匹配对比：移除所有空白并去除首尾空格。"""
        try:
            return re.sub(r"\s+", "", str(s)).strip()
        except Exception:
            return str(s).strip()

    def _persist_ai_answer(self, question: str, chosen_value: str) -> None:
        """将AI判定的结果写入题库 questions.json。
        - 若题目不存在：新增条目 question: chosen_value
        - 若题目已存在：在原有含义后追加（使用 " | " 分隔），避免重复（按规范化值去重）。
        写入采用原子替换，尽量避免文件损坏。
        """
        try:
            chosen_value = str(chosen_value).strip()
            if not chosen_value:
                return

            existing = self.answer.get(question)
            action = ""
            if existing is None:
                self.answer[question] = chosen_value
                action = "新增"
            else:
                meanings: List[str] = []
                if isinstance(existing, list):
                    for item in existing:
                        if isinstance(item, str):
                            parts = re.split(r"\s*[|｜]\s*", item)
                            for seg in parts:
                                seg = str(seg).strip()
                                if seg:
                                    meanings.append(seg)
                        else:
                            meanings.append(str(item).strip())
                elif isinstance(existing, str):
                    for seg in re.split(r"\s*[|｜]\s*", existing):
                        seg = str(seg).strip()
                        if seg:
                            meanings.append(seg)
                else:
                    meanings = [str(existing).strip()]

                # 去重但保留顺序
                seen = set()
                dedup: List[str] = []
                for seg in meanings:
                    norm = self._normalize_text(seg)
                    if norm and norm not in seen:
                        seen.add(norm)
                        dedup.append(seg)
                if self._normalize_text(chosen_value) not in {self._normalize_text(x) for x in dedup}:
                    dedup.append(chosen_value)
                    action = "追加含义"
                else:
                    action = "已存在，无需更新"
                self.answer[question] = " | ".join(dedup)

            tmp_path = "questions.json.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.answer, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, "questions.json")
            logger.success(f"{action}到题库：{question} -> {self.answer[question]}")
        except Exception as e:
            logger.warning(f"写入题库失败：{e}")

    def find_question(self) -> Tuple[str, List[str]]:
        """提取题目和选项"""
        # 提取题目文本（去除末尾标点）
        span_elements = self.driver.find_element(By.CLASS_NAME, "van-col--17").find_elements(By.TAG_NAME, "span")
        question = span_elements[1].text.strip()[:-2]

        # 处理选项文本（去除序号和多余字符）
        options = self.driver.find_elements(By.CLASS_NAME, "van-cell__title")
        options_list = [re.sub(r'\s.', '', opt.text[3:]) for opt in options[:4]]

        # 格式化输出题目信息（日志）
        logger.info(f"{question}")
        logger.debug(f"A: {options_list[0]}")
        logger.debug(f"B: {options_list[1]}")
        logger.debug(f"C: {options_list[2]}")
        logger.debug(f"D: {options_list[3]}")

        return question, options_list

    def find_answer(self, question_options: Tuple[str, List[str]]) -> int:
        """在题库中查找答案，支持一词多义；若多个选项同时匹配，优先按照题库中含义的先后顺序进行选择；未匹配则尝试 AI。"""
        question, options_list = question_options

        def _normalize(s: str) -> str:
            # 去除所有空白符，首尾空格，并保持最小侵入式的比较
            return re.sub(r"\s+", "", str(s)).strip()

        expected = self.answer.get(question, None)
        if expected is None:
            # 题库无此题，尝试AI判定
            ai_idx = ai_choose_answer(question, options_list)
            if ai_idx in (0, 1, 2, 3):
                try:
                    self._persist_ai_answer(question, options_list[ai_idx])
                except Exception:
                    pass
                return ai_idx
            save_error(question_options)
            return -1

        # 构造“有序可接受含义列表”：支持字符串中使用“|/｜”分隔多个含义，或直接是列表
        ordered: List[str] = []
        try:
            if isinstance(expected, list):
                for item in expected:
                    if isinstance(item, str):
                        parts = re.split(r"\s*[|｜]\s*", item)
                        for seg in parts:
                            seg = str(seg).strip()
                            if seg:
                                ordered.append(seg)
            elif isinstance(expected, str):
                for seg in re.split(r"\s*[|｜]\s*", expected):
                    seg = str(seg).strip()
                    if seg:
                        ordered.append(seg)
            else:
                ordered.append(str(expected).strip())
        except Exception:
            ordered = [str(expected).strip()]

        # 去重但保留先后顺序（按规范化后的值去重）
        seen_norm = set()
        ordered_norm: List[str] = []
        for seg in ordered:
            norm = _normalize(seg)
            if norm and norm not in seen_norm:
                seen_norm.add(norm)
                ordered_norm.append(norm)

        # 依据“含义顺序优先”进行匹配：
        # 先按含义顺序遍历，再在选项中寻找对应匹配，这样当多个选项同时命中时，优先题库里靠前的含义
        for meaning_norm in ordered_norm:
            for i, option in enumerate(options_list):
                if _normalize(option) == meaning_norm:
                    return i

        # 题库未匹配，尝试AI
        ai_idx = ai_choose_answer(question, options_list)
        if ai_idx in (0, 1, 2, 3):
            try:
                self._persist_ai_answer(question, options_list[ai_idx])
            except Exception:
                pass
            return ai_idx

        # 未命中则记录
        save_error(question_options)
        return -1

    def click_answer(self, index: int) -> None:
        """点击答案选项，-1时点击下一题。"""
        if index == -1:
            next_button = self.driver.find_element(
                By.XPATH, '//*[@id="app"]/div/div[3]/div/div[5]/div[1]/div[3]/button'
            )
            next_button.click()
        else:
            options = self.driver.find_elements(By.CLASS_NAME, "van-cell__title")
            logger.info(chr(index + 65))
            options[index].click()

    def wait(self):
        """执行交卷前的等待和提交操作"""
        logger.info("答题完成，准备提交...")
        logger.info("错误题目已保存至 error.txt")

        # 倒计时
        for i in range(300, -1, -1):
            logger.opt(raw=True).info(f"\r剩余时间: {i} 秒，时间到后将自动提交")
            time.sleep(1)
        logger.opt(raw=True).info("\n")

        # 交卷
        try:
            submit_btn = self.driver.find_element(By.CLASS_NAME, "van-nav-bar__right")
            submit_btn.click()
            time.sleep(1)
            check_btn = self.driver.find_element(By.CSS_SELECTOR, ".van-dialog__confirm.van-hairline--left")
            check_btn.click()
            time.sleep(1)
            logger.info("提交完成。")
        except Exception as e:
            logger.error(f"提交失败，请手动操作！错误信息：{str(e)}")

    def start(self):
        """主控制流程"""
        self.login()
        for i in range(100):
            question_options = self.find_question()
            answer_index = self.find_answer(question_options)
            prev_question = question_options[0]
            self.click_answer(answer_index)
            # 显式等待下一题加载完成（等待题干发生变化）
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.find_element(By.CLASS_NAME, "van-col--17").find_elements(By.TAG_NAME, "span")[1].text.strip()[:-2] != prev_question
                )
            except Exception as e:
                logger.warning(f"等待下一题加载失败或超时：{e}")
        self.wait()
        input("最后按回车结束代码")
        self.driver.quit()
