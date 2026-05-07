# 桌面动物园 - 边牧AI助手

一个可爱的桌面宠物应用，以边牧为形象，集成 LangGraph AI Agent，能够理解自然语言并自主规划任务执行。

## 功能特性

### 核心功能
- **桌面宠物**: 悬浮在桌面，可拖动，有多种动画状态
- **交互动画**: 单击触发互动（洗脸、摇尾巴），双击打开主面板
- **新闻推送**: 聚合百度热搜、微博热搜、Google热搜
- **闹钟提醒**: 倒计时结束后边牧会放大并全屏跑动

### AI Agent 功能 ⭐
- **自然语言理解**: 用人话告诉边牧你想做什么
- **任务自动规划**: 基于 LangGraph，自动将复杂任务分解为步骤
- **工具自主调用**: 智能选择和调用合适的功能
- **错误反思**: 执行失败时自动分析原因并重新规划
- **插件化架构**: 轻松扩展新功能

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API 密钥

编辑 `config.py` 文件，添加你的 Anthropic API 密钥：

```python
class Config:
    # ...
    ANTHROPIC_API_KEY = "sk-ant-xxxxx"  # 在这里填入你的API密钥
    ENABLE_AI_AGENT = True  # 启用AI Agent功能
```

如果没有 API 密钥：
- 访问 https://console.anthropic.com/ 获取
- 或设置 `ENABLE_AI_AGENT = False` 使用传统模式（只有按钮功能）

### 3. 运行应用

```bash
python main.py
```

## 使用方法

### 传统模式（按钮）
1. 双击桌面上的边牧打开主面板
2. 点击"推送今天的新闻"或"定一个10分钟的闹钟"按钮
3. 查看对话列表中的结果

### AI Agent 模式（自然语言）⭐
在主面板的输入框中输入自然语言，例如：

```
"帮我看看今天有什么热点新闻"
"设置一个15分钟的闹钟"
"先看新闻，然后定个5分钟的闹钟"
```

边牧会：
1. 理解你的意图
2. 制定执行计划
3. 自动调用相应的工具
4. 返回执行结果

### 交互方式
- **单击边牧**: 触发互动动画（洗脸、摇尾巴）
- **双击边牧**: 打开主面板
- **拖动边牧**: 移动到桌面任意位置
- **闹钟到时**: 边牧会放大并全屏跑动，双击停止

## 项目结构

```
桌面动物园/
├── main.py                  # 应用入口
├── config.py                # 配置文件
├── requirements.txt         # Python依赖
│
├── agent/                   # 🆕 AI Agent模块（LangGraph）
│   ├── state.py            # Agent状态定义
│   ├── graph.py            # LangGraph工作流
│   ├── nodes.py            # 节点实现（理解、规划、执行、反思、回复）
│   └── tools.py            # 工具包装器
│
├── core/                    # 核心模块
│   ├── pet_window.py       # 桌面宠物窗口
│   ├── main_panel.py       # 主面板（集成AI Agent）
│   ├── animation_manager.py # 动画状态管理
│   └── event_handler.py    # 事件处理
│
├── features/                # 功能插件（可被AI Agent调用）
│   ├── base_feature.py     # 功能基类
│   ├── news_push/          # 新闻推送
│   └── timer/              # 闹钟
│
├── ui/                      # UI组件
│   ├── chat_list.py        # 对话列表
│   └── feature_button.py   # 功能按钮
│
├── utils/                   # 工具模块
│   ├── network.py          # 网络请求
│   ├── translator.py       # 翻译
│   └── screen_utils.py     # 屏幕工具
│
└── assets/                  # 资源文件
    └── animations/          # 动画资源
        └── border_collie/   # 边牧动画GIF
```

## 技术架构

### LangGraph 工作流

```
用户输入
    ↓
[understand] 理解意图
    ↓
[plan] 制定计划
    ↓
[execute] 执行步骤 ←──┐
    ↓                  │
    ├─ 成功 → 下一步 ──┘
    ├─ 失败 → [reflect] 反思
    │            ↓
    │         重新规划/继续/放弃
    ↓
[respond] 生成回复
    ↓
显示结果
```

### 核心技术栈

- **GUI框架**: PyQt6
- **AI框架**: LangGraph + LangChain
- **LLM**: Claude 3.5 Sonnet (Anthropic)
- **网络爬虫**: requests + BeautifulSoup4
- **状态管理**: 基于图的状态机

## 添加新功能

### 方式1：添加传统功能（按钮）

1. 在 `features/` 下创建新文件夹
2. 继承 `BaseFeature` 类实现功能逻辑
3. 在 `main.py` 中注册功能

### 方式2：添加AI工具（可被Agent调用）

1. 在 `agent/tools.py` 中添加新的 `@tool` 装饰器函数
2. Agent 会自动识别并在需要时调用

示例：

```python
@tool
def get_weather(city: str) -> dict:
    """获取指定城市的天气信息

    Args:
        city: 城市名称

    Returns:
        dict: 包含天气信息的字典
    """
    # 实现天气查询逻辑
    return {"success": True, "message": f"{city}今天晴天"}
```

## 注意事项

- 动画资源需要放在 `assets/animations/border_collie/` 目录下
- macOS可能需要授予辅助功能权限
- 新闻爬虫的DOM选择器可能需要根据网站更新调整

## 常见问题

### 1. 提示"AI Agent初始化失败"
- 检查是否安装了所有依赖：`pip install -r requirements.txt`
- 检查 API 密钥是否正确配置
- 检查网络连接

### 2. 新闻爬取失败
- 网站的DOM结构可能已更新，需要修改 `features/news_push/fetcher.py` 中的选择器
- 检查是否被反爬虫机制拦截

### 3. 边牧没有动画
- 动画资源需要手动添加到 `assets/animations/border_collie/` 目录
- 如果没有动画文件，会显示占位文本

### 4. macOS权限问题
- 系统可能需要授予"辅助功能"权限
- 前往"系统偏好设置 → 安全性与隐私 → 辅助功能"添加应用

## 示例对话

### 简单任务
```
用户: 帮我看看今天的新闻
边牧: 好的！让我为你获取今日热点...
     [显示新闻列表]
```

### 复杂任务
```
用户: 先看新闻，然后给我定个10分钟的闹钟
边牧: 收到！我会先获取新闻，然后设置闹钟。

     第一步：获取今日新闻
     [显示新闻]

     第二步：设置10分钟闹钟
     闹钟已设置，时间到了我会提醒你！
```

## 未来规划

### 短期目标
- [ ] 添加边牧动画GIF资源
- [ ] 实现Google Trends爬取
- [ ] 添加真实的翻译API
- [ ] 优化爬虫的反爬机制

### 中期目标
- [ ] 天气预报功能
- [ ] 待办事项管理
- [ ] 番茄钟
- [ ] 快捷启动器
- [ ] 剪贴板历史

### 长期目标
- [ ] 多宠物切换（猫、兔子等）
- [ ] 语音交互
- [ ] 更复杂的AI任务规划
- [ ] 持久化对话记忆
- [ ] 插件市场

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License
