# -*- coding: utf-8 -*-
"""HDU API client for API-based answering mode."""
from __future__ import annotations
import base64
import json
import random
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import requests
from loguru import logger

from .utils import generate_skl_ticket
from .question_processor import QuestionProcessor


class AESECBEncryptor:
    """AES ECB mode encryptor for password encryption."""
    
    @staticmethod
    def encrypt(key_b64: str, plaintext: str) -> str:
        """Encrypt plaintext using AES ECB mode with PKCS7 padding.
        
        Args:
            key_b64: Base64-encoded AES key
            plaintext: Plain text password
            
        Returns:
            Base64-encoded ciphertext
        """
        key = base64.b64decode(key_b64)
        cipher = AES.new(key, AES.MODE_ECB)
        padded_data = pad(plaintext.encode('utf-8'), AES.block_size)
        ciphertext = cipher.encrypt(padded_data)
        return base64.b64encode(ciphertext).decode('utf-8')


class HDUAuthService:
    """HDU authentication service for API login."""
    
    LOGIN_URL = "https://sso.hdu.edu.cn/login"
    BASE_SERVICE_URL = "https://skl.hdu.edu.cn/api/cas/login"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
        })
    
    def login(self, username: str, password: str) -> Optional[str]:
        """Login and get X-Auth-Token.
        
        Args:
            username: HDU username
            password: HDU password
            
        Returns:
            X-Auth-Token if successful, None otherwise
        """
        try:
            # Generate state token
            state_token = secrets.token_hex(12)
            logger.debug(f"Generated state token: {state_token}")
            
            service_url = f"{self.BASE_SERVICE_URL}?state={state_token}&index="
            
            # Step 1: Get login page and extract tokens
            crypto_key, execution, full_login_url = self._fetch_login_tokens(service_url)
            if not crypto_key or not execution:
                logger.error("Failed to fetch login tokens")
                return None
            
            logger.debug(f"AES Key: {crypto_key}, Execution: {execution[:20]}...")
            
            # Step 2: Encrypt password
            encrypted_password = AESECBEncryptor.encrypt(crypto_key, password)
            logger.debug("Password encrypted successfully")
            
            # Step 3: Post login form
            ticket_url = self._post_login_form(username, encrypted_password, crypto_key, execution, full_login_url)
            if not ticket_url:
                logger.error("Failed to post login form")
                return None
            
            logger.debug("Login successful, got ticket URL")
            
            # Step 4: Exchange ticket for X-Auth-Token
            x_auth_token = self._exchange_ticket_for_token(ticket_url, full_login_url)
            if x_auth_token:
                logger.success("Successfully obtained X-Auth-Token")
                return x_auth_token
            else:
                logger.error("Failed to exchange ticket for token")
                return None
                
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return None
    
    def _fetch_login_tokens(self, service_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Fetch crypto key and execution token from login page."""
        try:
            params = {'service': service_url}
            resp = self.session.get(self.LOGIN_URL, params=params, allow_redirects=True)
            
            # Extract crypto key
            crypto_match = re.search(r'<p[^>]*id="login-croypto"[^>]*>([^<]+)</p>', resp.text)
            # Extract execution token
            execution_match = re.search(r'<p[^>]*id="login-page-flowkey"[^>]*>([^<]+)</p>', resp.text)
            
            if crypto_match and execution_match:
                return crypto_match.group(1), execution_match.group(1), resp.url
            else:
                logger.error("Failed to extract crypto key or execution token from login page")
                return None, None, None
                
        except Exception as e:
            logger.error(f"Failed to fetch login tokens: {e}")
            return None, None, None
    
    def _post_login_form(self, username: str, encrypted_password: str, 
                        crypto_key: str, execution: str, referer: str) -> Optional[str]:
        """Post login form and get redirect URL with ticket."""
        try:
            form_data = {
                'username': username,
                'type': 'UsernamePassword',
                '_eventId': 'submit',
                'geolocation': '',
                'execution': execution,
                'password': encrypted_password,
                'croypto': crypto_key,
                'captcha_code': '',
                'captcha_payload': ''
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': referer
            }
            
            resp = self.session.post(self.LOGIN_URL, data=form_data, headers=headers, allow_redirects=False)
            
            if resp.status_code == 302:
                location = resp.headers.get('Location')
                if location:
                    return location
            
            logger.error(f"Login POST failed with status code: {resp.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to post login form: {e}")
            return None
    
    def _exchange_ticket_for_token(self, ticket_url: str, referer: str) -> Optional[str]:
        """Exchange ticket for X-Auth-Token by following redirects."""
        try:
            current_url = ticket_url
            max_redirects = 10
            
            for i in range(max_redirects):
                resp = self.session.get(current_url, headers={'Referer': referer}, allow_redirects=False)
                
                if resp.status_code == 302:
                    location = resp.headers.get('Location', '')
                    
                    # Check if token is in URL fragment
                    if 'token=' in location:
                        # Extract token from fragment
                        if '#' in location:
                            fragment = location.split('#')[1]
                            if 'token=' in fragment:
                                # Parse fragment as query string
                                fragment = fragment.lstrip('?')
                                params = dict(param.split('=') for param in fragment.split('&') if '=' in param)
                                token = params.get('token')
                                if token:
                                    logger.debug("Found token in URL fragment")
                                    return token
                    
                    referer = current_url
                    current_url = location
                    continue
                
                # Check cookies for X-Auth-Token
                if 'X-Auth-Token' in self.session.cookies:
                    logger.debug("Found token in cookies")
                    return self.session.cookies['X-Auth-Token']
                
                break
            
            logger.error("Failed to find X-Auth-Token after all redirects")
            return None
            
        except Exception as e:
            logger.error(f"Failed to exchange ticket for token: {e}")
            return None


class HDUApiClient:
    """HDU API client for exam operations."""
    
    BASE_URL = "https://skl.hdu.edu.cn/api"
    
    def __init__(self, x_auth_token: str, timeout: int = 30):
        self.x_auth_token = x_auth_token
        self.timeout = timeout
        self.session = requests.Session()
    
    def _get_common_headers(self, skl_ticket: str) -> Dict[str, str]:
        """Get common headers for API requests."""
        return {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Connection': 'keep-alive',
            'Referer': 'https://skl.hdu.edu.cn/',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
            'X-Auth-Token': self.x_auth_token,
            'skl-ticket': skl_ticket
        }
    
    def fetch_current_week(self) -> Optional[int]:
        """Fetch current week number."""
        try:
            skl_ticket = generate_skl_ticket()
            today = time.strftime("%Y-%m-%d")
            url = f"{self.BASE_URL}/course?startTime={today}"
            
            headers = self._get_common_headers(skl_ticket)
            headers.update({
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            })
            
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            
            if resp.status_code == 200:
                data = resp.json()
                week = data.get('week', 0)
                if week > 0:
                    logger.info(f"Current week: {week}")
                    return week
            
            logger.error(f"Failed to fetch current week: {resp.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch current week: {e}")
            return None
    
    def get_new_paper(self, week: int, exam_type: str = "0") -> Optional[Dict]:
        """Get new paper/exam.
        
        Args:
            week: Week number
            exam_type: Exam type (default "0")
            
        Returns:
            Paper data with paperId and list of questions
        """
        try:
            skl_ticket = generate_skl_ticket()
            start_time = int(time.time() * 1000)
            url = f"{self.BASE_URL}/paper/new?type={exam_type}&week={week}&startTime={start_time}"
            
            headers = self._get_common_headers(skl_ticket)
            
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            
            if resp.status_code == 200:
                data = resp.json()
                paper_id = data.get('paperId')
                questions = data.get('list', [])
                logger.info(f"Got new paper: {paper_id} with {len(questions)} questions")
                return data
            elif resp.status_code == 400:
                error_data = resp.json()
                if error_data.get('code') == 2 and '请勿在短时间重试' in error_data.get('msg', ''):
                    logger.warning("Rate limited: Please don't retry in a short time")
                    return None
            
            logger.error(f"Failed to get new paper: {resp.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get new paper: {e}")
            return None
    
    def submit_paper(self, paper_id: str, answers: List[Dict]) -> bool:
        """Submit paper with answers.
        
        Args:
            paper_id: Paper ID
            answers: List of answer objects with paperDetailId and input
            
        Returns:
            True if successful, False otherwise
        """
        try:
            skl_ticket = generate_skl_ticket()
            url = f"{self.BASE_URL}/paper/save"
            
            payload = {
                'paperId': paper_id,
                'type': '0',
                'list': answers
            }
            
            headers = self._get_common_headers(skl_ticket)
            headers.update({
                'Content-Type': 'application/json',
                'Origin': 'https://skl.hdu.edu.cn'
            })
            
            resp = self.session.post(url, json=payload, headers=headers, timeout=self.timeout)
            
            if resp.status_code == 200:
                logger.success("Paper submitted successfully")
                return True
            else:
                logger.error(f"Failed to submit paper: {resp.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to submit paper: {e}")
            return False


def extract_token_from_browser(driver) -> Optional[str]:
    """Extract X-Auth-Token from browser after manual/automatic login.

    Args:
        driver: Selenium WebDriver instance

    Returns:
        X-Auth-Token if found, None otherwise
    """
    try:
        # Try to get token from cookies
        cookies = driver.get_cookies()
        for cookie in cookies:
            if cookie.get('name') == 'X-Auth-Token':
                token = cookie.get('value')
                if token:
                    logger.success(f"Successfully extracted X-Auth-Token from browser")
                    return token

        # Try to get token from localStorage
        try:
            token = driver.execute_script("return localStorage.getItem('X-Auth-Token');")
            if token:
                logger.success(f"Successfully extracted X-Auth-Token from localStorage")
                return token
        except Exception:
            pass

        # Try to get token from sessionStorage
        try:
            token = driver.execute_script("return sessionStorage.getItem('X-Auth-Token');")
            if token:
                logger.success(f"Successfully extracted X-Auth-Token from sessionStorage")
                return token
        except Exception:
            pass

        logger.error("Failed to extract X-Auth-Token from browser")
        return None

    except Exception as e:
        logger.error(f"Failed to extract token from browser: {e}")
        return None


def api_mode_answer(username: str, password: str, expected_score: int, 
                   answer_time: int, question_processor: QuestionProcessor, exam_type: Optional[str] = None) -> bool:
    """Execute answering in API mode.
    
    Args:
        username: HDU username
        password: HDU password
        expected_score: Expected score (0-100)
        answer_time: Time to wait before submission (seconds)
        question_processor: Instance of QuestionProcessor for answer logic
        exam_type: Exam type - "0" for exam, "1" for self-test (None to prompt)

    Returns:
        True if successful, False otherwise
    """
    start_time = time.time()
    
    # Prompt user for exam type if not provided
    if exam_type is None:
        logger.info("=" * 50)
        logger.info("请选择模式:")
        logger.info("0 - 自测模式 (Self-test)")
        logger.info("1 - 考试模式 (Exam)")
        logger.info("=" * 50)

        while True:
            choice = input("请输入 0 或 1: ").strip()
            if choice in ['0', '1']:
                exam_type = choice
                mode_name = "自测模式" if choice == '0' else "考试模式"
                logger.info(f"已选择: {mode_name}")
                break
            else:
                logger.warning("无效输入，请输入 0 或 1")

    # 1. Login and get token
    auth_service = HDUAuthService()
    x_auth_token = auth_service.login(username, password)
    if not x_auth_token:
        logger.error("API 登录失败，无法获取 Token")
        return False

    api_client = HDUApiClient(x_auth_token)

    # 2. Get current week
    week = api_client.fetch_current_week()
    if not week:
        return False

    # 3. Get new paper
    paper_data = api_client.get_new_paper(week, exam_type=exam_type)
    if not paper_data:
        return False

    paper_id = paper_data.get('paperId')
    questions = paper_data.get('list', [])

    if not paper_id or not questions:
        logger.error("试卷数据无效")
        return False

    logger.info(f"开始处理 {len(questions)} 道题目...")

    # 4. Answer questions
    final_answers = []
    
    # Calculate number of questions to answer incorrectly
    wrong_count = 100 - expected_score
    if wrong_count < 0:
        wrong_count = 0
    elif wrong_count > len(questions):
        wrong_count = len(questions)

    # Randomly select indices of questions to answer incorrectly
    wrong_indices = set()
    if wrong_count > 0:
        wrong_indices = set(random.sample(range(len(questions)), wrong_count))
        logger.info(f"期望分数: {expected_score} 分，将随机做错 {wrong_count} 题")

    # Reload question bank to ensure it's up-to-date
    question_processor.reload_question_bank()

    for idx, q_data in enumerate(questions):
        paper_detail_id = q_data.get('paperDetailId')
        title = q_data.get('title', '').strip().rstrip('.')
        options = [
            q_data.get('answerA', '').strip().rstrip('.'),
            q_data.get('answerB', '').strip().rstrip('.'),
            q_data.get('answerC', '').strip().rstrip('.'),
            q_data.get('answerD', '').strip().rstrip('.')
        ]

        # Use QuestionProcessor to get the answer index
        correct_answer_idx = question_processor.get_answer_index(title, options)

        correct_answer_char = 'A' # Default to 'A' if no answer found
        if correct_answer_idx != -1:
            correct_answer_char = chr(correct_answer_idx + 65)
        else:
            logger.warning(f"题目 '{title}' 未找到答案，默认选择 A")

        # Determine final answer (intentionally wrong if needed)
        final_answer_char = correct_answer_char
        if idx in wrong_indices:
            wrong_options = [chr(i + 65) for i in range(4) if chr(i + 65) != correct_answer_char]
            if wrong_options:
                final_answer_char = random.choice(wrong_options)
                logger.info(f"故意做错第 {idx + 1} 题，选择 {final_answer_char} 而不是 {correct_answer_char}")

        final_answers.append({
            "paperDetailId": paper_detail_id,
            "answer": final_answer_char
        })

    # 5. Wait for the specified answer time
    elapsed_time = time.time() - start_time
    remaining_time = answer_time - elapsed_time
    if remaining_time > 0:
        logger.info(f"等待 {remaining_time:.1f} 秒以满足答题时间要求...")
        time.sleep(remaining_time)

    # 6. Submit paper
    logger.info("提交答案...")
    return api_client.submit_paper(paper_id, final_answers)
