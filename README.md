# 杭电钉钉我爱记单词（基于 Selenium 的自动答题）

本项目用于在“杭电我爱记单词”页面进行自动化辅助答题。当前版本已进行以下改动与优化：
- 使用 Loguru 统一日志，默认写入 run.log，日志等级可在 config.yaml 中配置。
- 使用 config.yaml 管理多用户账号，已彻底移除旧的 data.json 登录逻辑；当 config 未配置时回退到命令行交互输入。
- 登录流程更健壮：自动尝试点击登录、处理新窗口/iframe、查找多种选择器并填入账号密码，必要时可手动完成登录。
- 在做题流程中加入显式等待，减少页面切换导致的误判。
- 一词多义支持：题库中可用“|”或“｜”分隔多个含义，例如 "tough": "艰苦的 | 恶棍"；若同时出现多个匹配选项，将优先选择题库中靠前的含义（上述示例则优先“艰苦的”）。

仅供学习参考，请勿用于任何违反平台、学校或法律规定的用途。

## 环境要求
- Windows（当前脚本和说明以 Windows 为例）
- Python 3.8+（建议）
- Chrome 浏览器与匹配版本的 ChromeDriver

## 安装依赖
建议使用虚拟环境，然后安装依赖：

- 方式一：requirements.txt（推荐）
  - `pip install -r requirements.txt`
- 方式二：单独安装
  - `pip install selenium==4.26.1 loguru PyYAML`

## 浏览器与驱动准备
1. 下载与你 Chrome 版本匹配的 ChromeDriver。
   - 如使用 135.0.7049.42 版本，可参考：
     - Chrome: https://storage.googleapis.com/chrome-for-testing-public/135.0.7049.42/win64/chrome-win64.zip
     - ChromeDriver: https://storage.googleapis.com/chrome-for-testing-public/135.0.7049.42/win64/chromedriver-win64.zip
   - 其他版本请从官方索引选择对应版本：https://chromedriver.storage.googleapis.com/index.html
2. 在 hdu_bot.py 中配置你的 chromedriver.exe 路径（若需要修改示例路径）：
   - 搜索 chrome_driver_path，修改为你的实际本地路径，例如：
     - D:\\Program Files\\chrome-win64\\chromedriver.exe

## 配置账号（多用户）
1. 复制配置模板为实际配置文件：
   - 将 config.yaml.exp 复制为 config.yaml
2. 按如下格式在 config.yaml 中填写多个账号（至少一个）：

   users:
     - username: "2020123456"
       password: "your_password"
       addition: "备注（可选）"

3. 可选：配置日志等级（默认 INFO），可选值：TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL

   log_level: "INFO"

说明：
- 程序启动时会优先读取 config.yaml。若存在多个账号，会在控制台提示你选择；若未配置 users，则回退到命令行手动输入用户名与密码。
- 日志会写入 run.log，并同时输出到控制台。

## 运行
- 方式一：双击 run.cmd（Windows）
- 方式二：命令行执行
  - `python main.py`

运行流程简述：
1. 程序打开 https://skl.hduhelp.com/#/english/list 页面。
2. 自动尝试点击“登录”，并在当前页面或可能的弹出窗口/iframe 中查找用户名和密码输入框进行填充；若无法自动定位，请手动完成登录。
3. 控制台提示“请手动开始考试后按回车继续”，此时请在网页上自行开始自测/考试，然后回到控制台按回车。
4. 脚本会自动进行后续答题过程（题库来源为项目内 questions.json）。

## 常见问题
- 无法定位登录输入框/按钮：
  - 页面结构可能变化，请手动完成登录。随后按控制台提示继续。
- ElementNotInteractableException：
  - 当前版本已加入更健壮的登录点击与 iframe 处理逻辑；若仍出现，请在浏览器中手动完成登录。
- ChromeDriver 版本不匹配：
  - 请确保 Chrome 与 ChromeDriver 版本相匹配，并在 hdu_bot.py 中正确填写 chromedriver.exe 路径。
- 日志位置：
  - run.log（同目录），可通过 config.yaml 的 log_level 调整日志详尽程度。

## 免责声明
本项目仅供学习与研究使用，请遵守相关法律法规及平台/学校使用规范。因使用本项目产生的任何后果由使用者自负。

## AI 辅助判题（可选）
当题库无法匹配题目或选项时，脚本可自动调用 AI 判断答案（仅在启用并正确配置时）。

- 原理：在未命中题库时，将“题干 + 四个选项”发送到一个 OpenAI 兼容的 Chat Completions 接口，请求模型在 A/B/C/D 中给出唯一选择。
- 默认关闭；正确配置后自动启用，不影响已有题库命中逻辑。

在 config.yaml 中新增 ai 配置块：

```
ai:
  enable: false            # 是否启用AI；若未填写 base_url 或 model 则视为未启用
  base_url: "http://127.0.0.1:11434/v1"  # OpenAI兼容接口基础地址（如 Ollama、本地/私有部署、云端服务等）
  token: ""               # 访问令牌，如无需鉴权可留空
  model: "gpt-4o-mini"    # 模型名称（依你的服务端而定，如 qwen2.5, glm-4-flash, deepseek-chat 等）
  temperature: 0.2         # 采样温度（可选）
  timeout: 15              # 请求超时秒（可选）
  retries: 3               # 失败时额外重试次数（默认3），总尝试次数 = 1 + retries
```

说明与注意：
- 需要一个“OpenAI 接口兼容”的服务端（标准路径：{base_url}/chat/completions）。
- 若配置不完整或请求失败，将自动回退为原行为（记录到 error.txt 并跳过当前题）。
- 出于隐私与成本考虑，请自行评估是否启用。日志会记录 AI 是否被调用与返回解析情况（不记录你的凭证）。
