class Config:
    # 宠物设置
    DEFAULT_PET = "border_collie"
    PET_SIZE = (150, 150)
    PET_SCALE_ALERT = 2.0  # 闹钟时放大倍数

    # 动画设置
    IDLE_STATE_SWITCH_INTERVAL = 30  # 秒，空闲状态切换间隔
    ANIMATION_FPS = 30

    # 窗口设置
    MAIN_PANEL_WIDTH = 400
    MAIN_PANEL_HEIGHT = 600

    # API配置
    TRANSLATION_API_KEY = ""  # 可选：翻译API密钥
    ANTHROPIC_API_KEY = ""  # Anthropic API密钥，用于AI Agent功能

    # AI Agent配置
    ENABLE_AI_AGENT = True  # 是否启用AI Agent功能
    AI_MODEL = "claude-3-5-sonnet-20241022"  # 使用的Claude模型

    # 功能开关
    ENABLED_FEATURES = [
        "news_push",
        "timer",
    ]

    # 新闻源配置
    NEWS_SOURCES = {
        "baidu": "https://top.baidu.com/board?tab=realtime",
        "weibo": "https://s.weibo.com/top/summary",
        "google": "https://trends.google.com/trending"
    }
    NEWS_CACHE_DURATION = 3600  # 秒，新闻缓存时长

    # 闹钟配置
    DEFAULT_TIMER_MINUTES = 10
    ALERT_RUN_SPEED = 15  # 像素/帧
