# -*- coding: utf-8 -*-
"""HDU English self-test automation bot (core browser automation)."""
from __future__ import annotations
import json
import os
import random
import re
import time
import threading
from typing import Tuple, List

from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait

from .config_loader import load_user_credentials, load_chrome_driver_path, load_ai_config
from .utils import save_error
from .question_processor import QuestionProcessor


class HDU:
    """自动化答题主类，封装核心操作逻辑"""

    def __init__(self):
        """初始化配置和资源（浏览器驱动将根据模式按需初始化）"""
        # 先加载用户配置获取模式
        username, password, answer_time_seconds, expected_score, mode = load_user_credentials()
        
        self.mode = mode  # 存储模式
        self.username = username
        self.password = password
        self.answer_time_seconds = answer_time_seconds
        self.expected_score = expected_score
        self.driver = None  # 浏览器驱动（仅在 browser 模式下初始化）
        self._last_user_el = None
        self._last_pwd_el = None

        # 初始化 QuestionProcessor
        ai_cfg = load_ai_config()
        self.question_processor = QuestionProcessor(ai_cfg)

        # 根据模式初始化浏览器（仅 browser 模式需要）
        if self.mode == "browser":
            logger.info("使用浏览器模拟模式")
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
        else:
            logger.info("使用 API 模式")

        # 计时器相关状态（仅用于 browser 模式）
        self.timer_expired = False  # 计时器是否已到期
        self.answering_completed = False  # 答题是否完成
        self.timer_lock = threading.Lock()  # 线程锁保护状态
        self.wrong_question_indices = set()  # 需要故意答错的题目索引集合

    def _start_timer(self):
        """启动答题计时器（从按下回车开始计时）"""
        def timer_thread():
            logger.info(f"计时器已启动，将在 {self.answer_time_seconds} 秒后自动提交")
            for remaining in range(self.answer_time_seconds, 0, -1):
                time.sleep(1)
                # 每30秒或最后10秒提示一次
                if remaining % 30 == 0 or remaining <= 10:
                    logger.info(f"剩余时间: {remaining} 秒")
            
            # 时间到
            with self.timer_lock:
                self.timer_expired = True
                if self.answering_completed:
                    logger.info("时间到且答题已完成，准备提交...")
                else:
                    logger.warning("时间到但答题未完成，将在答题完成后立即提交")
        
        timer = threading.Thread(target=timer_thread, daemon=True)
        timer.start()

    def login(self):
        """处理用户登录凭证：优先 config.yaml（多用户），否则在网页端完成手动登录。
        
        注意：此方法仅用于 browser 模式。API 模式不调用此方法。
        """
        if self.username and self.password:
            logger.info("使用 config.yaml 中的登录信息")
            logger.info(f"答题时间设置为 {self.answer_time_seconds} 秒")
            logger.info(f"期望分数设置为 {self.expected_score} 分")
        else:
            logger.info("未配置账号密码，将在网页端完成手动登录")
            logger.info(f"答题时间设置为 {self.answer_time_seconds} 秒（默认）")
            logger.info(f"期望分数设置为 {self.expected_score} 分（默认）")

        self.login_web(self.username, self.password)

    def login_web(self, username: str, password: str) -> None:
        """执行网页登录操作：先打开业务页触发重定向到 SSO，再自动填充登录。"""
        # 先打开业务页面，由其自动跳转到带 service/state 的 SSO 登录页
        list_url = "https://skl.hdu.edu.cn/#/english/list"
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

        # 如果账号密码为空，则让用户在网页端手动登录
        if username is None or password is None:
            logger.info("请在浏览器中手动完成登录")
            input("登录完成后，请按回车继续...")
            # 导航到业务页面
            try:
                self.driver.get("https://skl.hdu.edu.cn/#/english/list")
            except Exception:
                pass
            input("请手动开始考试后按回车继续")
            self._start_timer()  # 从摁下回车开始计时
            return

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
            self.driver.get("https://skl.hdu.edu.cn/#/english/list")
        except Exception:
            pass

        input("请手动开始考试后按回车继续")
        self._start_timer()  # 从摁下回车开始计时

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
        return self.question_processor.get_answer_index(question, options_list)

    def get_wrong_answer(self, correct_index: int) -> int:
        """获取一个错误答案的索引（随机选择除了正确答案外的其他选项）。
        
        Args:
            correct_index: 正确答案的索引（0-3），如果为-1表示没有找到答案，直接返回随机选项
        
        Returns:
            错误答案的索引（0-3）
        """
        if correct_index == -1:
            # 如果没有找到正确答案，返回随机选项
            return random.randint(0, 3)
        
        # 从0-3中排除正确答案，随机选择一个错误答案
        wrong_options = [i for i in range(4) if i != correct_index]
        return random.choice(wrong_options)

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
        """执行交卷前的等待和提交操作（基于计时器）"""
        logger.info("答题完成，准备提交...")
        logger.info("错误题目已保存至 error.txt")

        # 检查计时器状态
        with self.timer_lock:
            if self.timer_expired:
                # 时间已到，立即提交
                logger.info("计时时间已到，立即提交")
            else:
                # 时间未到，等待计时器到期
                logger.info("答题已完成，等待计时器到期后提交...")
        
        # 等待计时器到期（如果还没到期的话）
        while True:
            with self.timer_lock:
                if self.timer_expired:
                    break
            time.sleep(0.5)
        
        logger.info("开始提交...")
        
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
        """主控制流程 - 根据模式选择浏览器模拟或API模式"""
        if self.mode == "api":
            # API 模式
            self._start_api_mode()
        else:
            # 浏览器模式
            self._start_browser_mode()
    
    def _start_api_mode(self):
        """API 模式的主控制流程"""
        logger.info("=" * 50)
        logger.info("启动 API 模式")
        logger.info("=" * 50)
        
        x_auth_token = None

        # 尝试 API 登录（需要密码）
        if self.username and self.password:
            logger.info(f"用户名: {self.username}")
            logger.info(f"答题时间: {self.answer_time_seconds} 秒")
            logger.info(f"期望分数: {self.expected_score} 分")

            # 如果密码已配置，直接使用 api_mode_answer 函数
            # 该函数会提示用户选择考试模式或自测模式
            from .hdu_api_client import api_mode_answer

            success = api_mode_answer(
                self.username,
                self.password,
                self.expected_score,
                self.answer_time_seconds,
                self.question_processor,  # 传递 QuestionProcessor 实例
                exam_type=None  # None 表示提示用户输入
            )

            if success:
                logger.success("API 模式答题完成！")
            else:
                logger.error("API 模式答题失败")
            return

        # 未配置密码，回退到浏览器登录获取 token
        logger.warning("未配置密码，将回退到浏览器登录")
        logger.info("=" * 50)
        logger.info("回退到浏览器登录模式")
        logger.info("=" * 50)

        # 初始化浏览器驱动
        self._init_browser_driver()

        # 执行浏览器登录
        logger.info("开始浏览器登录...")
        self.login_web(self.username, self.password)

        # 从浏览器提取 X-Auth-Token
        logger.info("尝试从浏览器会话中提取 X-Auth-Token...")
        from .hdu_api_client import extract_token_from_browser, HDUApiClient
        x_auth_token = extract_token_from_browser(self.driver)

        if not x_auth_token:
            logger.error("无法从浏览器提取 X-Auth-Token，任务失败")
            if self.driver:
                self.driver.quit()
            return

        logger.success("成功从浏览器提取 X-Auth-Token")

        # 关闭浏览器
        logger.info("关闭浏览器...")
        if self.driver:
            self.driver.quit()
            self.driver = None

        logger.info("切换回 API 模式完成任务...")

        # 提示用户选择模式
        logger.info("=" * 50)
        logger.info("请选择模式:")
        logger.info("0 - 自测模式 (Self-test)")
        logger.info("1 - 考试模式 (Exam)")
        logger.info("=" * 50)

        exam_type = None
        while True:
            choice = input("请输入 0 或 1: ").strip()
            if choice in ['0', '1']:
                exam_type = choice
                mode_name = "自测模式" if choice == '0' else "考试模式"
                logger.info(f"已选择: {mode_name}")
                break
            else:
                logger.warning("无效输入，请输入 0 或 1")

        # 使用获取的 token 完成答题任务
        api_client = HDUApiClient(x_auth_token)

        # 获取当前周次
        week = api_client.fetch_current_week()
        if not week:
            logger.error("获取当前周次失败")
            return

        # 获取新试卷
        logger.info(f"Getting paper with type={exam_type} (0=自测, 1=考试)...")
        paper_data = api_client.get_new_paper(week, exam_type=exam_type)
        if not paper_data:
            logger.error("获取试卷失败")
            return

        paper_id = paper_data.get('paperId')
        questions = paper_data.get('list', [])

        if not paper_id or not questions:
            logger.error("试卷数据无效")
            return

        logger.info(f"开始处理 {len(questions)} 道题目...")

        # 答题逻辑
        start_time = time.time()
        final_answers = []

        # 计算需要答错的题目数量
        wrong_count = 100 - self.expected_score
        if wrong_count < 0:
            wrong_count = 0
        elif wrong_count > len(questions):
            wrong_count = len(questions)

        # 随机选择需要答错的题目索引
        wrong_indices = set()
        if wrong_count > 0:
            wrong_indices = set(random.sample(range(len(questions)), wrong_count))
            logger.info(f"期望分数: {self.expected_score} 分，将随机做错 {wrong_count} 题")

        # 重新加载题库以确保最新
        self.question_processor.reload_question_bank()

        for idx, question in enumerate(questions):
            paper_detail_id = question.get('paperDetailId')
            title = question.get('title', '').strip().rstrip('.')
            option_a = question.get('answerA', '').strip().rstrip('.')
            option_b = question.get('answerB', '').strip().rstrip('.')
            option_c = question.get('answerC', '').strip().rstrip('.')
            option_d = question.get('answerD', '').strip().rstrip('.')

            options = [option_a, option_b, option_c, option_d]

            # 使用 QuestionProcessor 获取答案
            correct_answer_idx = self.question_processor.get_answer_index(title, options)

            correct_answer = None
            if correct_answer_idx != -1:
                correct_answer = chr(correct_answer_idx + 65)

            # 如果仍未找到答案，默认选 A
            if not correct_answer:
                correct_answer = 'A'
                logger.warning(f"题目 '{title}' 未找到答案，默认选择 A")

            # 确定最终答案（是否需要故意答错）
            final_answer_char = correct_answer
            if idx in wrong_indices:
                # 获取一个错误答案
                wrong_options = [chr(i + 65) for i in range(4) if chr(i + 65) != correct_answer]
                if wrong_options:
                    final_answer_char = random.choice(wrong_options)
                    logger.info(f"故意做错第 {idx + 1} 题，选择 {final_answer_char} 而不是 {correct_answer}")

            final_answers.append({
                "paperDetailId": paper_detail_id,
                "answer": final_answer_char
            })

        # 检查答题用时
        elapsed_time = time.time() - start_time
        remaining_time = self.answer_time_seconds - elapsed_time
        if remaining_time > 0:
            logger.info(f"等待 {remaining_time:.1f} 秒以满足答题时间要求...")
            time.sleep(remaining_time)

        # 提交答案
        logger.info("提交答案...")
        if api_client.submit_paper(paper_id, final_answers):
            logger.success("API 模式答题成功！")
        else:
            logger.error("API 模式答题失败。")

    def _init_browser_driver(self):
        """Initializes the browser driver if it's not already initialized."""
        if self.driver is None:
            logger.info("Initializing browser driver for token extraction...")
            options = webdriver.ChromeOptions()
            options.add_experimental_option('mobileEmulation', {'deviceName': 'iPhone 6'})
            driver_path = load_chrome_driver_path()
            try:
                if driver_path and os.path.exists(driver_path):
                    service = Service(executable_path=driver_path)
                    self.driver = webdriver.Chrome(options=options, service=service)
                else:
                    self.driver = webdriver.Chrome(options=options)
            except Exception as e:
                logger.error(f"Failed to initialize Chrome driver: {e}")
                raise

    def _start_browser_mode(self):
        """浏览器模式的主控制流程"""
        logger.info("=" * 50)
        logger.info("启动浏览器模式")
        logger.info("=" * 50)

        # 初始化浏览器驱动
        self._init_browser_driver()

        # 执行登录
        logger.info("开始登录...")
        self.login_web(self.username, self.password)

        logger.info("登录成功，准备答题...")

        input("请手动开始考试后按回车继续")
        self._start_timer()  # 从摁下回车开始计时

        # 主答题循环
        question_options = None
        try:
            while True:
                # 查找题目
                question_options = self.find_question()
                if not question_options:
                    logger.warning("未能提取到题目，可能是已答题完毕或页面结构变化")
                    break

                question, options_list = question_options

                # 查找答案
                answer_index = self.find_answer(question_options)

                if answer_index == -1:
                    logger.warning(f"未能找到题目 '{question}' 的答案")
                    # 随机选择一个选项
                    answer_index = random.randint(0, 3)

                # 点击答案
                logger.info(f"选择答案: {chr(answer_index + 65)}")
                self.click_answer(answer_index)

                # 人为延迟，避免操作过快
                time.sleep(1)
        except Exception as e:
            logger.error(f"答题过程中发生错误：{e}")
            if question_options:
                save_error(question_options)

        # 等待交卷
        self.wait()
