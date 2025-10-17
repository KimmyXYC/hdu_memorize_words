# 杭电钉钉我爱记单词（基于 Selenium 的自动答题）

本项目提供两种方式进行自动答题：
1. **Python Selenium 自动化脚本**（需要配置环境和浏览器驱动）
2. **Tampermonkey 浏览器脚本**（推荐，开箱即用）

仅供学习参考，请勿用于任何违反平台、学校或法律规定的用途。

---

## 🚀 方式一：Tampermonkey 脚本（推荐）

### 特点
- ✅ 无需安装 Python 和 ChromeDriver
- ✅ 无需配置环境
- ✅ 支持本地题库匹配
- ✅ 支持 AI 辅助答题
- ✅ 可视化控制面板
- ✅ 题库自动导入/导出
- ✅ 开箱即用

### 安装步骤

#### 1. 安装 Tampermonkey 浏览器扩展
- **Chrome/Edge**: 在扩展商店搜索 "Tampermonkey" 并安装
- **Firefox**: 在附加组件市场搜索 "Tampermonkey" 并安装

#### 2. 安装脚本
访问脚本页面并点击安装：
- **Greasy Fork**: https://greasyfork.org/zh-CN/scripts/551830-hdu%E8%8B%B1%E8%AF%AD%E8%87%AA%E6%B5%8B%E8%87%AA%E5%8A%A8%E7%AD%94%E9%A2%98%E5%8A%A9%E6%89%8B

或手动安装：
1. 打开 Tampermonkey 管理面板
2. 点击 "+" 创建新脚本
3. 复制 `hdu_auto_answer.user.js` 的内容并粘贴
4. 保存（Ctrl+S）

### 使用方法

#### 1. 访问答题页面
打开杭电钉钉英语我爱记单词页面：https://skl.hdu.edu.cn/#/english/list

#### 2. 配置脚本
页面右上角会出现 **📚 HDU答题助手** 控制面板：

**基础功能：**
- 显示题库数量和已答题数
- 暂停/开始自动答题
- 导出/导入题库（JSON格式）

**AI 配置：**（题库未匹配时使用）
1. 勾选 "启用AI辅助"
2. 填写配置信息：
   - **API地址**: 你的 AI API 地址（如 `https://api.openai.com/v1`）
   - **API密钥**: 你的 API Key
   - **模型名称**: 如 `gpt-3.5-turbo`, `gpt-4o-mini` 等
   - **温度**: 0-1 之间，推荐 0.2（数值越小越确定）
   - **超时**: 请求超时时间（毫秒），默认 15000
   - **重试次数**: 失败后重试次数，默认 3
3. 点击 "💾 保存AI配置"

#### 3. 导入题库
- 点击 "导入题库" 按钮
- 选择项目中的 `questions.json` 文件
- 题库数据会保存在浏览器本地存储中

#### 4. 开始答题
- 手动进入答题页面
- 脚本会自动识别题目并答题
- 答题过程会在浏览器控制台（F12）显示日志

### 控制面板功能

**面板操作：**
- **拖拽**: 按住蓝色标题栏可拖动面板位置
- **最小化**: 点击右上角 "−" 按钮收起面板，点击 "+" 展开
- **位置记忆**: 面板位置和最小化状态会自动保存

**答题模式：**
1. **题库优先**: 优先从本地题库匹配答案（速度快，准确率高）
2. **AI辅助**: 题库未匹配时自动调用 AI 判断（需配置）
3. **自动学习**: AI 判定的答案会自动保存到题库，下次直接使用

### 支持的 AI 服务

脚本支持任何 OpenAI 兼容的 API，包括但不限于：
- OpenAI 官方 API
- Azure OpenAI
- 国内大模型（通义千问、文心一言、智谱AI等）
- 本地部署（Ollama、LocalAI 等）
- 各类 API 代理服务

### 数据管理

**导出题库：**
- 点击 "导出题库" 按钮
- 下载 JSON 格式的题库文件
- 文件名格式：`hdu_questions_时间戳.json`

**导入题库：**
- 点击 "导入题库" 按钮
- 选择 JSON 格式的题库文件
- 新题目会与现有题库合并（不覆盖）

### 注意事项
- 使用 Tampermonkey 脚本时，**必须搭配插件 [User-Agent Switcher and Manager](https://chromewebstore.google.com/detail/user-agent-switcher-and-m/bhchdcejhohfmigjafbampogmaanbfkg)**，否则在考试模式下无法正常答题。
- 题库和配置数据存储在浏览器本地，建议定期导出备份
- 清除浏览器数据会导致题库和配置丢失
- AI 配置不会导出，需要在每个浏览器中单独配置
- 脚本仅在 `https://skl.hdu.edu.cn/*` 域名下运行

---

## 🖥️ 方式二：Python Selenium 脚本

### 环境要求
- Windows（当前脚本和说明以 Windows 为例）
- Python 3.8+（建议）
- Chrome 浏览器与匹配版本的 ChromeDriver

### 安装依赖
建议使用虚拟环境，然后安装依赖：

- 方式一：requirements.txt（推荐）
  - `pip install -r requirements.txt`
- 方式二：单独安装
  - `pip install selenium==4.26.1 loguru PyYAML`

### 浏览器与驱动准备
1. 下载与你 Chrome 版本匹配的 ChromeDriver。
   - 如使用 135.0.7049.42 版本，可参考：
     - Chrome: https://storage.googleapis.com/chrome-for-testing-public/135.0.7049.42/win64/chrome-win64.zip
     - ChromeDriver: https://storage.googleapis.com/chrome-for-testing-public/135.0.7049.42/win64/chromedriver-win64.zip
   - 其他版本请从官方索引选择对应版本：https://chromedriver.storage.googleapis.com/index.html
2. 在 `config.yaml` 中配置 `chrome_driver_path`（可选）：
   - 在根目录的 `config.yaml` 增加或修改 chrome_driver_path，例如：
     - chrome_driver_path: "D:\\Program Files\\chrome-win64\\chromedriver.exe"
   - 若不配置，将尝试使用 Selenium Manager 或 PATH 中的 chromedriver。

### 配置账号（多用户）
1. 复制配置模板为实际配置文件：
   - 将 `config.yaml.exp` 复制为 `config.yaml`
2. 按如下格式在 `config.yaml` 中填写多个账号（至少一个）：

```
   users:
     - username: "2020123456"
       password: "your_password"
       addition: "备注（可选）"
       answer_time_seconds: 300  # 答题时间（秒），默认300秒（5分钟）
```

3. 可选：配置日志等级（默认 INFO），可选值：TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL

```
   log_level: "INFO"
```

说明：
- 程序启动时会优先读取 `config.yaml`。若存在多个账号，会在控制台提示你选择；若未配置 users，则会在网页端完成手动登录。
- 日志会写入 `run.log`，并同时输出到控制台。
- `answer_time_seconds` 用于设置答题时间（秒），从按下回车开始计时。若计时结束且答题完成，则提交；若计时结束但答题未完成，则答题完成后立即提交。可按用户单独配置，默认为 300 秒（5 分钟）。

### 运行
- 命令行执行
  - `python main.py`

运行流程简述：
1. 程序打开 https://skl.hdu.edu.cn/#/english/list 页面。
2. 自动尝试点击“登录”，并在当前页面或可能的弹出窗口/iframe 中查找用户名和密码输入框进行填充；若无法自动定位，请手动完成登录。
3. 控制台提示“请手动开始考试后按回车继续”，此时请在网页上自行开始自测/考试，然后回到控制台按回车。
4. **从按下回车的那一刻开始计时**，脚本会自动进行后续答题过程（题库来源为项目内 `questions.json`）。
5. 提交逻辑：
   - 若计时结束且答题已完成，则立即提交。
   - 若计时结束但答题未完成，则等待答题完成后立即提交。
   - 若答题完成但计时未结束，则等待计时结束后提交。

### 常见问题
- 无法定位登录输入框/按钮：
  - 页面结构可能变化，请手动完成登录。随后按控制台提示继续。
- ElementNotInteractableException：
  - 当前版本已加入更健壮的登录点击与 iframe 处理逻辑；若仍出现，请在浏览器中手动完成登录。
- ChromeDriver 版本不匹配：
  - 请确保 Chrome 与 ChromeDriver 版本相匹配，并在 `config.yaml` 中通过 chrome_driver_path 指定 `chromedriver.exe` 路径（或将 chromedriver 加入 PATH）。
- 日志位置：
  - `run.log`（同目录），可通过 `config.yaml` 的 log_level 调整日志详尽程度。

### 免责声明
本项目仅供学习与研究使用，请遵守相关法律法规及平台/学校使用规范。因使用本项目产生的任何后果由使用者自负。

### AI 辅助判题（可选）
当题库无法匹配题目或选项时，脚本可自动调用 AI 判断答案（仅在启用并正确配置时）。

- 原理：在未命中题库时，将“题干 + 四个选项”发送到一个 OpenAI 兼容的 Chat Completions 接口，请求模型在 A/B/C/D 中给出唯一选择。
- 默认关闭；正确配置后自动启用，不影响已有题库命中逻辑。

在 `config.yaml` 中新增 ai 配置块：

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
- 需要一个“OpenAI 接口兼容”的服务端（标准路径：`{base_url}/chat/completions`）。
- 若配置不完整或请求失败，将自动回退为原行为（记录到 `error.txt` 并跳过当前题）。
- 出于隐私与成本考虑，请自行评估是否启用。日志会记录 AI 是否被调用与返回解析情况（不记录你的凭证）。


### AI 自动学习（自动更新题库）
- 当题库未命中且启用 AI 时，若 AI 返回了可解析的选项，脚本会自动将该题目与所选含义写入 `questions.json`。
- 若题目已存在但不包含该含义，将以“ | ”分隔符追加，形成一词多义；重复含义会自动去重，不会重复写入。
- 当同一题目出现多个匹配含义时，仍然优先选择题库中靠前的含义（与一词多义的优先规则一致）。


## 项目结构
- app/: 模块化核心代码
  - hdu_bot.py: 浏览器自动化与答题逻辑
  - ai_client.py: AI 判题客户端（OpenAI 兼容）
  - config_loader.py: 配置读取（多用户、AI、chrome_driver_path）
  - logging_config.py: 日志初始化（写入 run.log）
  - utils.py: 工具函数
- main.py: 程序入口
- config.yaml / config.yaml.exp: 配置文件与模板
- questions.json: 题库
- error.txt: 未匹配题目记录
- run.log: 运行日志
