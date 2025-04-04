# -*- coding: utf-8 -*-
import time

from selenium.common import NoSuchElementException
from selenium.webdriver.support import expected_conditions as ec  # 提供了一组预定义的条件，
from selenium.webdriver.support.wait import WebDriverWait  # 上通常与WebDriverWait一起使用，用于等待某个特定条件成立后再继续执行代码
from selenium import webdriver
from selenium.webdriver.common.by import By  # 定位页面元素的方法
from selenium.webdriver.chrome.service import Service
import os
import json
import re


class HDU:
    def __init__(self):
        options = webdriver.ChromeOptions()
        # 开启手机模式
        options.add_experimental_option('mobileEmulation', {'deviceName': 'iPad'})  # 开启手机模式
        # 驱动路径
        chrome_driver_path = r"C:\Users\yyy\.cache\selenium\chromedriver\win64\chromedriver-win64\chromedriver.exe"

        service = Service(executable_path=chrome_driver_path)  # , service=service

        self.driver = webdriver.Chrome(options=options, service=service)  # 实例化ChromeDriver对象

        # 加载tm。json
        try:
            with open("题库.json", 'r', encoding='utf-8') as file:
                self.answer = json.load(file)
        except FileNotFoundError:
            print(f"错误: 文件未找到。")
        except json.JSONDecodeError:
            print(f"错误: 文件不是有效的JSON格式。")
        except Exception as e:
            print(f"错误: 发生未知错误: {e}")

    def login(self):
        if os.path.exists("data.json"):
            with open("data.json", "r", encoding='utf-8') as f:
                data = json.load(f)
                print(data)
                # 缺一段新建用户的代码
                inp = input("请输入你想登录的账号")
                username = data[inp]["username"]
                password = data[inp]["password"]
        else:
            # 新建账号密码文件
            username = input(" 请输入用户名：")
            password = input(" 请输入密码：")
            addition = input(" 请输入备注：")
            new_user = {1: {"username": username, "password": password, "addition": addition}}
            with open("data.json", "w", encoding='utf-8') as f:
                json.dump(new_user, f, ensure_ascii=False)
        self.loginweb(username, password)

    def loginweb(self, username, password):
        url = "https://skl.hduhelp.com/#/english/list"  # 网址
        # 打开网页
        self.driver.get(url)
        WebDriverWait(self.driver, 10).until(
            ec.element_to_be_clickable((By.CSS_SELECTOR, '.login-button'))
        )
        # 输入用户名密码
        self.driver.find_element(By.NAME, "username").send_keys(username)
        self.driver.find_element(By.NAME, "passwordPre").send_keys(password)
        self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        input("请手动开始考试后按回车继续")
    #加个选自测和考试的跳转

    def find_question(self) -> tuple[str, list[str]]:
        # 获取题目单词
        span_elements = self.driver.find_element(By.CLASS_NAME, "van-col--17").find_elements(By.TAG_NAME, "span")
        question = span_elements[1].text.strip()[:-2]  # 去掉最后的标点符号

        # 获取选项
        options = self.driver.find_elements(By.CLASS_NAME, "van-cell__title")
        options_list = [re.sub(r'\s.', '', opt.text[3:]) for opt in options[:4]]
        print(f"\n{question}\n"
              f"A: {options_list[0]}\n"
              f"B：{options_list[1]}\n"
              f"C：{options_list[2]}\n"
              f"D：{options_list[3]}\n")

        return question, options_list

    def find_answer(self, question_options: tuple[str, list[str]]) -> int:
        question, options_list = question_options
        for i in range(len(options_list)):
            try:
                if self.answer[question] == options_list[i]:
                    return i
            except KeyError:
                self.SaveError(question_options)
                return -1
        self.SaveError(question_options)
        return -1

    def click_answer(self, index: int) -> None:
        if index == -1:
            next_button = self.driver.find_element(
                By.XPATH, '//*[@id="app"]/div/div[3]/div/div[5]/div[1]/div[3]/button'
            )
            next_button.click()
        else:
            options = self.driver.find_elements(By.CLASS_NAME, "van-cell__title")
            print(index)
            options[index].click()

    @staticmethod
    def SaveError(question_options):
        question, options = question_options
        error_message = f"{question}\n{options}\n"
        with open("error.txt", "a", encoding='utf-8') as f:
            f.write(error_message)

    def wait(self):
        # 等待答题时间
        print("已经作答完毕大部分题目,可以点击提交了")
        print("错误题目已保存到error.txt")
        for i in range(300, -1, -1):
            # 使用 '\r' 返回行首，不换行，'end='' 确保不追加新行
            print(f"\r剩余时间: {i} 秒，时间到后将自动提交", end='', flush=True)
            time.sleep(1)
        try:
            submit_btn = self.driver.find_element(By.CLASS_NAME, "van-nav-bar__right")
            submit_btn.click()
            time.sleep(1)
            check_btn = self.driver.find_element(By.CSS_SELECTOR, ".van-dialog__confirm.van-hairline--left")
            check_btn.click()
            time.sleep(1)
            print("\n")
        except Exception as e:
            print("靠(艹皿艹 )，程序又崩了，快自己点击救一下啊！")

    def start(self):
        self.login()
        for i in range(100):
            question_options = self.find_question()
            answer_index = self.find_answer(question_options)
            self.click_answer(answer_index)
            time.sleep(1)
        self.wait()
        time.sleep(5)
        self.driver.quit()


if __name__ == "__main__":
    hdu = HDU()
    hdu.start()
