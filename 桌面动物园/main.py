import datetime
import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from core.pet_window import PetWindow
from core.main_panel import MainPanel
from core.greeting import get_greeting, save_last_seen
from core.state_manager import (
    load_window_position, save_window_position,
    load_timer_state, save_timer_state,
)
from features.news_push.news_feature import NewsFeature
from features.timer.timer_feature import TimerFeature
from config import Config
from utils.screen_utils import ScreenUtils


def main():
    # 设置环境变量（如果配置文件中有API密钥）
    if Config.ANTHROPIC_API_KEY:
        os.environ["ANTHROPIC_API_KEY"] = Config.ANTHROPIC_API_KEY

    app = QApplication(sys.argv)

    # 创建宠物窗口
    pet_window = PetWindow()

    # 创建主面板
    main_panel = MainPanel(pet_window)

    # 注册功能
    main_panel.register_feature(NewsFeature())
    timer_feature = TimerFeature()
    main_panel.register_feature(timer_feature)

    # 设置timer feature的pet_window引用（用于闹钟触发动画）
    if Config.ENABLE_AI_AGENT:
        try:
            from agent import get_timer_feature
            agent_timer = get_timer_feature()
            agent_timer.pet_window_ref = pet_window
        except Exception:
            pass

    # 关联窗口
    pet_window.set_main_panel(main_panel)

    # 显示宠物窗口
    pet_window.show()

    # 恢复上次窗口位置
    saved_pos = load_window_position()
    if saved_pos:
        sx, sy = saved_pos
        sw, sh = ScreenUtils.get_screen_size()
        pw, ph = Config.PET_SIZE
        sx = max(0, min(sx, sw - pw))
        sy = max(0, min(sy, sh - ph))
        pet_window.move(sx, sy)

    # 恢复定时器（如果上次退出时有活跃定时器）
    timer_state = load_timer_state()
    if timer_state and timer_state.get("is_active"):
        try:
            end_dt = datetime.datetime.fromisoformat(timer_state["end_time"])
            remaining = int((end_dt - datetime.datetime.now()).total_seconds())
            if remaining > 0:
                timer_feature.countdown.remaining_seconds = remaining
                timer_feature.countdown.timer.start(1000)
            else:
                save_timer_state("", is_active=False)
        except Exception:
            pass

    # 启动后延迟 800ms 再弹气泡，确保窗口已完全渲染
    greeting_text = get_greeting()
    QTimer.singleShot(800, lambda: pet_window.show_bubble(greeting_text, duration_ms=5000))

    # 退出时保存状态
    def on_quit():
        save_last_seen()
        pos = pet_window.pos()
        save_window_position(pos.x(), pos.y())

    app.aboutToQuit.connect(on_quit)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
