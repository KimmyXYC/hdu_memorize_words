# -*- coding: utf-8 -*-
"""HDU英语自测自动化答题程序，使用Selenium实现浏览器自动化操作"""
import json
import os
import re
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By  # 定位页面元素的方法
from selenium.webdriver.support import expected_conditions as ec  # 提供了一组预定义的条件
from selenium.webdriver.support.wait import WebDriverWait  # 通常与WebDriverWait一起使用，用于等待某个特定条件成立后再继续执行代码


class HDU:
    """自动化答题主类，封装核心操作逻辑"""
    def __init__(self):
        """初始化浏览器驱动并加载题库"""
        options = webdriver.ChromeOptions()
        # 移动端模拟配置
        options.add_experimental_option('mobileEmulation', {'deviceName': 'iPhone 6'})

        # 浏览器驱动配置
        chrome_driver_path = r"C:\Users\yyy\.cache\selenium\chromedriver\win64\chromedriver-win64\chromedriver.exe"
        service = Service(executable_path=chrome_driver_path)  # , service=service
        self.driver = webdriver.Chrome(options=options, service=service)

        # 题库加载处理
        try:
            with open("题库.json", 'r', encoding='utf-8') as file:
                self.answer = json.load(file)
        except FileNotFoundError:
            print(f"错误: 文件未找到。")
            self.answer = {}
        except json.JSONDecodeError:
            print(f"错误: 文件不是有效的JSON格式。")
            self.answer = {}
        except Exception as e:
            print(f"错误: 发生未知错误: {e}")
            self.answer = {}

    def login(self):
        """处理用户登录凭证
            - 存在data.json时选择已有账号
            - 不存在时创建新用户档案
        """
        if os.path.exists("data.json"):
            with open("data.json", "r", encoding='utf-8') as f:
                data = json.load(f)
                print(data)
                # 缺一段新建用户的代码
                inp = input("请输入你想登录的账号（输入前面的序号）")
                username = data[inp]["username"]
                password = data[inp]["password"]
        else:
            # 新用户注册
            username = input(" 请输入用户名：")
            password = input(" 请输入密码：")
            addition = input(" 请输入备注：")
            new_user = {1: {"username": username, "password": password, "addition": addition}}
            with open("data.json", "w", encoding='utf-8') as f:
                json.dump(new_user, f, ensure_ascii=False)
        self.login_web(username, password)

    def login_web(self, username: str, password: str) -> None:
        """执行网页登录操作
           Args:
               username: 用户名
               password: 密码
       """
        url = "https://skl.hduhelp.com/#/english/list"  # 网址
        self.driver.get(url)

        # 等待登录按钮可点击
        WebDriverWait(self.driver, 10).until(
            ec.element_to_be_clickable((By.CSS_SELECTOR, '.login-button'))
        )

        # 填充凭证并提交
        self.driver.find_element(By.NAME, "username").send_keys(username)
        self.driver.find_element(By.NAME, "passwordPre").send_keys(password)
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        input("请手动开始考试后按回车继续")

    # 加个选自测和考试的跳转

    def find_question(self) -> tuple[str, list[str]]:
        """提取题目和选项
            Returns:
            tuple: (题目文本, 选项列表)
        """
        # 提取题目文本（去除末尾标点）
        span_elements = self.driver.find_element(By.CLASS_NAME, "van-col--17").find_elements(By.TAG_NAME, "span")
        question = span_elements[1].text.strip()[:-2]

        # 处理选项文本（去除序号和多余字符）
        options = self.driver.find_elements(By.CLASS_NAME, "van-cell__title")
        options_list = [re.sub(r'\s.', '', opt.text[3:]) for opt in options[:4]]

        # 格式化输出题目信息
        print(f"\n{question}\n"
              f"A: {options_list[0]}\n"
              f"B：{options_list[1]}\n"
              f"C：{options_list[2]}\n"
              f"D：{options_list[3]}\n")

        return question, options_list

    def find_answer(self, question_options: tuple[str, list[str]]) -> int:
        """在题库中查找答案
            Args:
                question_options: 包含题目和选项的元组
            Returns:
                int: 正确答案索引，未找到返回-1
        """
        question, options_list = question_options
        for i, option in enumerate(options_list):
            try:
                if self.answer[question] == option:
                    return i
            except KeyError:
                self.SaveError(question_options)
                return -1
        self.SaveError(question_options)
        return -1

    def click_answer(self, index: int) -> None:
        """点击答案选项
            Args:
                index: 选项索引（0-3），-1时跳过
        """
        if index == -1:
            next_button = self.driver.find_element(
                By.XPATH, '//*[@id="app"]/div/div[3]/div/div[5]/div[1]/div[3]/button'
            )
            next_button.click()
        else:
            options = self.driver.find_elements(By.CLASS_NAME, "van-cell__title")
            print(chr(index+65))
            options[index].click()

    @staticmethod
    def SaveError(question_options: tuple[str, list[str]]) -> None:
        """保存未识别题目到错误日志
            Args:
                question_options: 包含题目和选项的元组
        """
        question, options = question_options
        error_message = f"{question}\n{options}\n"
        with open("error.txt", "a", encoding='utf-8') as f:
            f.write(error_message)

    def wait(self):
        """执行交卷前的等待和提交操作"""
        print("答题完成，准备提交...")
        print("错误题目已保存至error.txt")

        # 倒计时
        for i in range(300, -1, -1):
            # 使用 '\r' 返回行首，不换行，'end='' 确保不追加新行
            print(f"\r剩余时间: {i} 秒，时间到后将自动提交", end='', flush=True)
            time.sleep(1)

        # 交卷
        try:
            submit_btn = self.driver.find_element(By.CLASS_NAME, "van-nav-bar__right")
            submit_btn.click()
            time.sleep(1)
            check_btn = self.driver.find_element(By.CSS_SELECTOR, ".van-dialog__confirm.van-hairline--left")
            check_btn.click()
            time.sleep(1)
            print("\n")
        except Exception as e:
            print(f"\n提交失败，请手动操作！错误信息：{str(e)}")

    def start(self):
        """主控制流程"""
        self.login()
        for i in range(100):
            question_options = self.find_question()
            answer_index = self.find_answer(question_options)
            self.click_answer(answer_index)
            time.sleep(1)  # 应该改成显式等待的，不会捏
        self.wait()
        input("最后按回车结束代码")
        self.driver.quit()


if __name__ == "__main__":
    hdu = HDU()
    hdu.start()
