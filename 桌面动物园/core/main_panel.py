import datetime

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from config import Config
from core.state_manager import load_chat_history, save_chat_history
from ui.chat_list import ChatList
from ui.feature_button import FeatureButton
from features.base_feature import BaseFeature
from typing import List
from langchain_core.messages import HumanMessage


class AgentThread(QThread):
    """异步执行Agent的线程"""
    finished = pyqtSignal(str)

    def __init__(self, agent_graph, user_input):
        super().__init__()
        self.agent_graph = agent_graph
        self.user_input = user_input

    def run(self):
        try:
            # 初始化状态
            initial_state = {
                "messages": [HumanMessage(content=self.user_input)],
                "current_task": "",
                "plan": [],
                "steps_completed": [],
                "tool_results": {},
                "reasoning": "",
                "needs_human_approval": False,
                "status": "planning"
            }

            # 运行Agent
            result = self.agent_graph.invoke(initial_state)

            # 获取最终回复
            final_message = result["messages"][-1].content if result["messages"] else "执行完成"
            self.finished.emit(final_message)
        except Exception as e:
            self.finished.emit(f"抱歉，执行过程中出现了错误：{str(e)}")


class FeatureManager:
    def __init__(self):
        self.features = {}

    def register(self, feature: BaseFeature):
        self.features[feature.get_name()] = feature

    def get_feature(self, name: str) -> BaseFeature:
        return self.features.get(name)

    def get_all_features(self) -> List[BaseFeature]:
        return list(self.features.values())


class MainPanel(QWidget):
    def __init__(self, pet_window):
        super().__init__()
        self.pet_window = pet_window
        self.feature_manager = FeatureManager()
        self.agent_graph = None
        self.agent_thread = None
        self._chat_history: list = []

        # 初始化AI Agent
        if Config.ENABLE_AI_AGENT:
            try:
                from agent import create_agent_graph
                self.agent_graph = create_agent_graph()
            except Exception as e:
                print(f"AI Agent初始化失败: {e}")

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("边牧助手")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(Config.MAIN_PANEL_WIDTH, Config.MAIN_PANEL_HEIGHT)

        # 主布局
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # 对话列表
        self.chat_list = ChatList()
        layout.addWidget(self.chat_list, stretch=1)

        # AI输入框（如果启用了AI Agent）
        if Config.ENABLE_AI_AGENT and self.agent_graph:
            input_layout = QHBoxLayout()
            input_layout.setSpacing(10)

            self.input_box = QLineEdit()
            self.input_box.setPlaceholderText("输入你的需求，让边牧帮你...")
            self.input_box.setStyleSheet("""
                QLineEdit {
                    padding: 10px;
                    border: 2px solid #007AFF;
                    border-radius: 5px;
                    font-size: 14px;
                }
            """)
            self.input_box.returnPressed.connect(self.on_user_input)

            send_button = FeatureButton("发送")
            send_button.setMaximumWidth(80)
            send_button.clicked.connect(self.on_user_input)

            input_layout.addWidget(self.input_box, stretch=1)
            input_layout.addWidget(send_button)
            layout.addLayout(input_layout)

        # 功能按钮区域
        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(10)
        button_layout = self.button_layout
        self.feature_buttons = {}

        # 动态创建功能按钮
        for feature in self.feature_manager.get_all_features():
            button = FeatureButton(feature.get_button_text())
            button.clicked.connect(lambda checked, f=feature: self.execute_feature(f))
            self.feature_buttons[feature.get_name()] = button
            button_layout.addWidget(button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # 加载历史对话
        saved_history = load_chat_history(limit=50)
        if saved_history:
            self._chat_history = list(saved_history)
            for msg in saved_history:
                self.chat_list.add_message(msg["content"], is_user=(msg["role"] == "user"))
        else:
            # 无历史记录时显示欢迎消息
            if Config.ENABLE_AI_AGENT and self.agent_graph:
                welcome = "你好！我是你的桌面边牧AI助手，你可以用自然语言告诉我你想做什么，我会帮你完成！"
            else:
                welcome = "你好！我是你的桌面边牧助手，有什么可以帮你的吗？"
            self.chat_list.add_message(welcome)
            self._record_message(welcome, "pet")

    def _record_message(self, content: str, role: str) -> None:
        """记录一条消息到内存和磁盘"""
        self._chat_history.append({
            "role": role,
            "content": content,
            "ts": datetime.datetime.now().isoformat(),
        })
        if len(self._chat_history) > 200:
            self._chat_history = self._chat_history[-200:]
        save_chat_history(self._chat_history[-50:])

    def register_feature(self, feature: BaseFeature):
        self.feature_manager.register(feature)
        # 动态添加按钮
        button = FeatureButton(feature.get_button_text())
        button.clicked.connect(lambda checked, f=feature: self.execute_feature(f))
        self.feature_buttons[feature.get_name()] = button
        self.button_layout.addWidget(button)

    def execute_feature(self, feature: BaseFeature):
        # 显示用户请求
        self.chat_list.add_message(feature.get_button_text(), is_user=True)
        self._record_message(feature.get_button_text(), "user")

        # 执行功能
        result = feature.execute()

        # 显示结果
        msg = result.get('message', '执行完成')
        self.chat_list.add_message(msg)
        self._record_message(msg, "pet")

        # 触发回调
        feature.on_result(result, self.pet_window)

    def on_user_input(self):
        """处理用户自然语言输入"""
        if not hasattr(self, 'input_box'):
            return

        user_text = self.input_box.text().strip()
        if not user_text:
            return

        # 清空输入框
        self.input_box.clear()

        # 显示用户消息
        self.chat_list.add_message(user_text, is_user=True)
        self._record_message(user_text, "user")

        # 如果没有启用AI Agent，回退到简单回复
        if not self.agent_graph:
            fallback = "抱歉，AI功能未启用。请使用下方的功能按钮。"
            self.chat_list.add_message(fallback)
            self._record_message(fallback, "pet")
            return

        # 显示思考中
        self.chat_list.add_message("让我想想... 🤔")

        # 在后台线程运行Agent
        self.agent_thread = AgentThread(self.agent_graph, user_text)
        self.agent_thread.finished.connect(self.on_agent_finished)
        self.agent_thread.start()

    def on_agent_finished(self, response: str):
        """Agent执行完成的回调"""
        self.chat_list.add_message(response)
        self._record_message(response, "pet")
