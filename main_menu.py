import sys
import os

try:
    import textract
except ImportError:
    # 如果textract不可用，使用替代方案
    textract = None
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QStackedWidget,
                             QFrame, QGraphicsDropShadowEffect, QTextEdit,
                             QScrollArea, QMessageBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QLineEdit,
                             QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                             QListWidget, QListWidgetItem, QFileDialog, QInputDialog)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QPixmap, QFont, QColor, QIcon, QPainter, QPen, QTextCursor
from datetime import datetime
from openai import OpenAI

# 设置Qt插件路径
try:
    import PyQt5

    pyqt5_path = os.path.dirname(PyQt5.__file__)
    correct_plugin_path = r"D:\Python\Lib\site-packages\PyQt5\Qt5\plugins"

    if os.path.exists(correct_plugin_path):
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = correct_plugin_path
        print(f"✅ 已设置Qt插件路径: {correct_plugin_path}")
    else:
        possible_paths = [
            os.path.join(pyqt5_path, "Qt5", "plugins"),
            os.path.join(pyqt5_path, "Qt", "plugins"),
            os.path.join(pyqt5_path, "plugins"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = path
                print(f"✅ 使用自动找到的路径: {path}")
                break
        else:
            print("❌ 未找到Qt插件路径，使用备用方案")
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = ''
except ImportError as e:
    print(f"PyQt5导入错误: {e}")
    pass

# 使用全局数据库实例
from database import db_manager


# ==================== AI聊天相关类 ====================

class APIKeyManager:
    """API密钥管理类，用于存储和获取API密钥"""
    _instance = None
    _api_key = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(APIKeyManager, cls).__new__(cls)
            # 尝试从环境变量加载API Key
            cls._instance.load_from_env()
        return cls._instance

    def load_from_env(self):
        """从环境变量加载API Key"""
        self._api_key = os.environ.get("ARK_API_KEY")

    def set_api_key(self, api_key):
        """设置API Key"""
        self._api_key = api_key
        # 同时设置环境变量
        os.environ["ARK_API_KEY"] = api_key

    def get_api_key(self):
        """获取API Key"""
        return self._api_key

    def is_valid(self):
        """检查API Key是否有效"""
        return self._api_key is not None and len(self._api_key.strip()) > 0


class ChatWorker(QThread):
    """处理AI聊天的后台线程"""
    response_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, message, current_defect_type):
        super().__init__()
        self.message = message
        self.current_defect_type = current_defect_type
        self.api_manager = APIKeyManager()

    def run(self):
        try:
            # 检查API Key是否存在
            api_key = self.api_manager.get_api_key()
            if not api_key:
                self.error_occurred.emit("API Key未配置，请先设置API Key")
                return

            # 初始化OpenAI客户端
            client = OpenAI(
                base_url="https://ark.cn-beijing.volces.com/api/v3",
                api_key=api_key,  # 直接使用从管理器获取的API Key
            )

            # 构建包含当前缺陷类型的提示信息
            system_prompt = f"你是电路板缺陷专家，正在讨论'{self.current_defect_type}'相关问题。请专业、简洁地回答关于该缺陷的成因、修复方法等问题。"

            completion = client.chat.completions.create(
                model="doubao-seed-1-6-251015",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": self.message}
                ],
                reasoning_effort="medium"
            )

            if completion.choices and completion.choices[0].message.content:
                self.response_received.emit(completion.choices[0].message.content)
            else:
                self.error_occurred.emit("未获取到有效回复")

        except Exception as e:
            self.error_occurred.emit(f"发生错误: {str(e)}")


class ChatInterface(QWidget):
    """聊天界面组件"""

    def __init__(self, parent=None, defect_type=""):
        super().__init__(parent)
        self.current_defect_type = defect_type
        self.api_manager = APIKeyManager()
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("background-color: #ecf0f1;")
        layout = QVBoxLayout(self)

        # 添加API Key设置按钮
        api_layout = QHBoxLayout()
        api_layout.setAlignment(Qt.AlignRight)

        api_btn = QPushButton("设置API Key")
        api_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        api_btn.clicked.connect(self.set_api_key_dialog)
        api_layout.addWidget(api_btn)

        layout.addLayout(api_layout)

        # 聊天历史区域
        history_frame = QFrame()
        history_frame.setStyleSheet("background-color: white; border-radius: 8px;")
        history_layout = QVBoxLayout(history_frame)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("border: none; padding: 10px;")
        self.chat_history.setFont(QFont("SimHei", 10))
        history_layout.addWidget(self.chat_history)

        # 初始消息
        self.append_message("系统", f"欢迎咨询关于'{self.current_defect_type}'的问题，我会为您提供专业解答。")

        # 检查API Key状态
        if not self.api_manager.is_valid():
            self.append_message("系统", "提示：API Key未配置，请点击右上角按钮设置")

        layout.addWidget(history_frame, 7)

        # 输入区域
        input_frame = QFrame()
        input_frame.setStyleSheet("background-color: #34495e; padding: 10px; border-radius: 8px; margin-top: 10px;")
        input_layout = QHBoxLayout(input_frame)

        self.message_input = QTextEdit()
        self.message_input.setStyleSheet("background-color: white; border-radius: 4px; padding: 5px;")
        self.message_input.setFont(QFont("SimHei", 10))
        self.message_input.setMaximumHeight(80)
        input_layout.addWidget(self.message_input, 8)

        send_btn = QPushButton("发送")
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 15px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(send_btn, 1)

        layout.addWidget(input_frame, 2)

    def set_api_key_dialog(self):
        """显示设置API Key的对话框"""
        current_key = self.api_manager.get_api_key() or ""
        api_key, ok = QInputDialog.getText(
            self,
            "设置API Key",
            "请输入火山方舟API Key:",
            text=current_key
        )

        if ok and api_key:
            self.api_manager.set_api_key(api_key)
            self.append_message("系统", "API Key已更新")
            QMessageBox.information(self, "成功", "API Key设置成功")

    def append_message(self, sender, message):
        """添加消息到聊天历史"""
        if sender == "你":
            self.chat_history.append(f"<b style='color:#3498db;'>{sender}:</b> {message}<br>")
        else:
            self.chat_history.append(f"<b style='color:#e74c3c;'>{sender}:</b> {message}<br>")

        # 滚动到底部
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_history.setTextCursor(cursor)

    def send_message(self):
        """发送消息并获取回复"""
        # 检查API Key是否已配置
        if not self.api_manager.is_valid():
            self.append_message("系统", "请先设置API Key")
            # 自动弹出设置对话框
            self.set_api_key_dialog()
            return

        message = self.message_input.toPlainText().strip()
        if not message:
            return

        # 添加用户消息到历史
        self.append_message("你", message)
        self.message_input.clear()

        # 显示"正在输入"提示
        self.append_message("系统", "正在思考，请稍候...")

        # 启动后台线程处理AI请求
        self.worker = ChatWorker(message, self.current_defect_type)
        self.worker.response_received.connect(self.on_response_received)
        self.worker.error_occurred.connect(self.on_error_occurred)
        self.worker.start()

    @pyqtSlot(str)
    def on_response_received(self, response):
        """处理AI回复"""
        # 移除"正在输入"提示
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.select(QTextCursor.BlockUnderCursor)
        cursor.removeSelectedText()

        # 添加AI回复
        self.append_message("专家", response)

    @pyqtSlot(str)
    def on_error_occurred(self, error):
        """处理错误信息"""
        # 移除"正在输入"提示
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.select(QTextCursor.BlockUnderCursor)
        cursor.removeSelectedText()

        # 添加错误信息
        self.append_message("系统", error)

    def update_defect_type(self, defect_type):
        """更新当前缺陷类型"""
        self.current_defect_type = defect_type
        self.append_message("系统", f"已切换到'{defect_type}'相关咨询，您可以继续提问。")


class DefectPage(QWidget):
    """单个缺陷类型展示页面，包含详情和聊天界面切换"""

    def __init__(self, image_paths, left_text, right_text, defect_type, parent=None):
        super().__init__(parent)
        self.defect_type = defect_type
        self.image_paths = image_paths  # 接收图片路径列表
        self.init_ui(left_text, right_text)

    def init_ui(self, left_text, right_text):
        # 主布局
        main_layout = QVBoxLayout(self)

        # 切换按钮
        toggle_layout = QHBoxLayout()
        self.detail_btn = QPushButton("缺陷详情")
        self.chat_btn = QPushButton("咨询专家")

        for btn in [self.detail_btn, self.chat_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:checked {
                    background-color: #21618c;
                }
            """)
            btn.setCheckable(True)
            toggle_layout.addWidget(btn)

        self.detail_btn.clicked.connect(lambda: self.switch_view(0))
        self.chat_btn.clicked.connect(lambda: self.switch_view(1))
        self.detail_btn.setChecked(True)

        main_layout.addLayout(toggle_layout)

        # 堆叠窗口用于切换详情和聊天
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # 详情页面
        detail_page = QWidget()
        detail_layout = QVBoxLayout(detail_page)

        # 图片展示区域 - 2行3列布局
        image_frame = QFrame()
        image_frame.setStyleSheet("background-color: #34495e; padding: 10px; border-radius: 8px;")
        image_layout = QVBoxLayout(image_frame)

        # 第一行图片
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(10)
        # 第二行图片
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(10)

        # 添加图片到布局中
        for i, img_path in enumerate(self.image_paths):
            img_label = QLabel()
            img_label.setAlignment(Qt.AlignCenter)
            img_label.setMinimumHeight(150)  # 设置最小高度确保图片有足够空间

            try:
                pixmap = QPixmap(img_path)
                if not pixmap.isNull():
                    # 按比例缩放图片
                    scaled_pixmap = pixmap.scaled(300, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    img_label.setPixmap(scaled_pixmap)
                else:
                    img_label.setText("图片加载失败")
                    img_label.setStyleSheet("color: white; font-size: 14px;")
            except Exception as e:
                img_label.setText(f"图片错误: {str(e)}")
                img_label.setStyleSheet("color: white; font-size: 14px;")

            # 前3张放第一行，后3张放第二行
            if i < 3:
                row1_layout.addWidget(img_label)
            else:
                row2_layout.addWidget(img_label)

        image_layout.addLayout(row1_layout)
        image_layout.addLayout(row2_layout)
        detail_layout.addWidget(image_frame)

        # 文本内容区域（分为左右两部分）
        text_frame = QFrame()
        text_frame.setStyleSheet("background-color: #34495e; padding: 10px; border-radius: 8px; margin-top: 10px;")
        text_layout = QHBoxLayout(text_frame)
        text_layout.setSpacing(20)

        # 左侧文本（缺陷类型及成因）
        left_text_edit = QTextEdit()
        left_text_edit.setReadOnly(True)
        left_text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #ecf0f1;
                color: #2c3e50;
                font-size: 14px;
                padding: 15px;
                border-radius: 8px;
            }
        """)
        left_text_edit.setFont(QFont("SimHei", 10))
        left_text_edit.setText(left_text)
        # 设置垂直滚动条策略为永不显示
        left_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 设置文本编辑框根据内容自动调整大小
        left_text_edit.setSizeAdjustPolicy(QTextEdit.AdjustToContents)
        left_text_edit.setMinimumHeight(200)  # 设置最小高度
        left_text_edit.setMaximumHeight(16777215)  # 设置最大高度为最大值
        text_layout.addWidget(left_text_edit, 1)

        # 右侧文本（修复建议与方案）
        right_text_edit = QTextEdit()
        right_text_edit.setReadOnly(True)
        right_text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #ecf0f1;
                color: #2c3e50;
                font-size: 14px; 
                padding: 15px;
                border-radius: 8px;
            }
        """)
        right_text_edit.setFont(QFont("SimHei", 10))
        right_text_edit.setText(right_text)
        right_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 设置文本编辑框根据内容自动调整大小
        right_text_edit.setSizeAdjustPolicy(QTextEdit.AdjustToContents)
        right_text_edit.setMinimumHeight(200)  # 设置最小高度
        right_text_edit.setMaximumHeight(16777215)  # 设置最大高度为最大值
        text_layout.addWidget(right_text_edit, 1)

        detail_layout.addWidget(image_frame, 3)  # 图片区域占3份
        detail_layout.addWidget(text_frame, 2)  # 文本区域占2份

        self.stacked_widget.addWidget(detail_page)

        # 聊天页面
        self.chat_interface = ChatInterface(defect_type=self.defect_type)
        self.stacked_widget.addWidget(self.chat_interface)

    def switch_view(self, index):
        """切换详情和聊天视图"""
        self.detail_btn.setChecked(index == 0)
        self.chat_btn.setChecked(index == 1)
        self.stacked_widget.setCurrentIndex(index)

    def update_chat_defect_type(self):
        """更新聊天界面的缺陷类型"""
        self.chat_interface.update_defect_type(self.defect_type)


class DefectTypeWidget(QWidget):
    """缺陷类型总览页面，包含五个可切换的子页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("background-color: #2c3e50;")

        # 主布局
        main_layout = QVBoxLayout(self)

        # 切换按钮区域
        button_frame = QFrame()
        button_frame.setStyleSheet("background-color: #34495e;")
        button_layout = QHBoxLayout(button_frame)
        button_layout.setSpacing(10)

        self.buttons = []
        self.defect_types = ["刮伤", "脏污", "异物", "压伤", "氧化"]

        for i, defect_type in enumerate(self.defect_types):
            btn = QPushButton(defect_type)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    padding: 8px 15px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed, QPushButton:checked {
                    background-color: #21618c;
                }
            """)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self.switch_page(idx))
            self.buttons.append(btn)
            button_layout.addWidget(btn)

        main_layout.addWidget(button_frame)

        # 堆叠窗口用于切换不同缺陷类型页面
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # 初始化五个缺陷页面
        self.init_defect_pages()

        # 默认选中第一个按钮和页面
        self.buttons[0].setChecked(True)
        self.stacked_widget.setCurrentIndex(0)

    def init_defect_pages(self):
        # 五个缺陷类型的示例数据，每个类型包含6张图片路径
        defect_data = [
            {
                # "image_paths": [  # 修改为图片路径列表 D:\Python\python正式文件\PCB\img
                #     "D:/Python/python正式文件/PCB/img/01_missing_hole_01.jpg",
                #     "D:/Python/python正式文件/PCB/img/04_missing_hole_01.jpg",
                #     "D:/Python/python正式文件/PCB/img/04_missing_hole_15.jpg",
                #     "D:/Python/python正式文件/PCB/img/05_missing_hole_04.jpg",
                #     "D:/Python/python正式文件/PCB/img/10_missing_hole_01.jpg",
                #     "D:/Python/python正式文件/PCB/img/10_missing_hole_05.jpg",
                # ],
                "image_paths": [  # 修改为图片路径列表 D:\Python\python正式文件\PCB\img
                    "D:/Python/python正式文件/PCB/img2/01_刮伤_02.jpg",
                    "D:/Python/python正式文件/PCB/img2/01_刮伤_04.jpg",
                    "D:/Python/python正式文件/PCB/img2/01_刮伤_05.jpg",
                    "D:/Python/python正式文件/PCB/img2/01_刮伤_07.jpg",
                    "D:/Python/python正式文件/PCB/img2/01_刮伤_09.jpg",
                    "D:/Python/python正式文件/PCB/img2/01_刮伤_11.jpg",
                ],
                "left_text": "【刮伤缺陷】\n\n成因：\n1. 生产过程中刀具或夹具划伤\n2. 人工操作时硬物接触板面\n3. 运输过程中摩擦碰撞\n4. 检测设备探针刮擦\n5. 板面清洁工具硬度不当",
                "right_text": "【修复建议】\n\n解决方案：\n1. 轻微刮伤可使用专用修复剂填补\n2. 严重刮伤需打磨后重新涂覆阻焊层\n3. 更换磨损的生产夹具和刀具\n4. 优化运输包装，增加防护措施\n5. 规范操作流程，避免硬物接触",
                "type": "刮伤"
            },
            {
                # "image_paths": [
                #     "D:/Python/python正式文件/PCB/img2/01_mouse_bite_04.jpg",
                #     "D:/Python/python正式文件/PCB/img2/01_mouse_bite_17.jpg",
                #     "D:/Python/python正式文件/PCB/img2/04_mouse_bite_11.jpg",
                #     "D:/Python/python正式文件/PCB/img2/07_mouse_bite_04.jpg",
                #     "D:/Python/python正式文件/PCB/img2/07_mouse_bite_07.jpg",
                #     "D:/Python/python正式文件/PCB/img2/07_mouse_bite_08.jpg",
                # ],
                "image_paths": [
                    "D:/Python/python正式文件/PCB/img2/05_脏污_49.jpg",
                    "D:/Python/python正式文件/PCB/img2/05_脏污_50.jpg",
                    "D:/Python/python正式文件/PCB/img2/05_脏污_52.jpg",
                    "D:/Python/python正式文件/PCB/img2/05_脏污_54.jpg",
                    "D:/Python/python正式文件/PCB/img2/05_脏污_55.jpg",
                    "D:/Python/python正式文件/PCB/img2/05_脏污_57.jpg",
                ],
                "left_text": "【脏污缺陷】\n\n成因：\n1. 生产环境粉尘过多\n2. 清洗工艺不彻底\n3. 操作人员手上油污污染\n4. 助焊剂或清洗剂残留\n5. 存储环境潮湿发霉",
                "right_text": "【修复建议】\n\n解决方案：\n1. 使用无尘布配合专用清洁剂擦拭\n2. 严重脏污可进行超声波清洗\n3. 优化生产环境的除尘和温湿度控制\n4. 操作人员佩戴无尘手套\n5. 改善存储条件，做好防潮处理",
                "type": "脏污"
            },
            {
                # "image_paths": [
                #     "D:/Python/python正式文件/PCB/img/01_open_circuit_01.jpg",
                #     "D:/Python/python正式文件/PCB/img/04_open_circuit_11.jpg",
                #     "D:/Python/python正式文件/PCB/img/04_open_circuit_13.jpg",
                #     "D:/Python/python正式文件/PCB/img/05_open_circuit_08.jpg",
                #     "D:/Python/python正式文件/PCB/img/05_open_circuit_09.jpg",
                #     "D:/Python/python正式文件/PCB/img/12_open_circuit_08.jpg"
                # ],
                "image_paths": [
                    "D:/Python/python正式文件/PCB/img2/04_异物_29.jpg",
                    "D:/Python/python正式文件/PCB/img2/04_异物_30.jpg",
                    "D:/Python/python正式文件/PCB/img2/04_异物_32.jpg",
                    "D:/Python/python正式文件/PCB/img2/04_异物_34.jpg",
                    "D:/Python/python正式文件/PCB/img2/04_异物_35.jpg",
                    "D:/Python/python正式文件/PCB/img2/04_异物_37.jpg"
                ],
                "left_text": "【异物缺陷】\n\n成因：\n1. 生产车间空气中的金属碎屑\n2. 焊锡球或助焊剂残渣\n3. 板材加工产生的粉尘颗粒\n4. 组装过程中掉落的微小零件\n5. 包装材料碎屑混入",
                "right_text": "【修复建议】\n\n解决方案：\n1. 使用防静电毛刷清除表面异物\n2. 真空吸除细小颗粒状异物\n3. 高压气枪吹扫缝隙中的异物\n4. 对关键区域进行局部清洗\n5. 优化生产环境的过滤系统",
                "type": "异物"
            },
            {
                # "image_paths": [
                #     "D:/Python/python正式文件/PCB/img/01_short_04.jpg",
                #     "D:/Python/python正式文件/PCB/img/01_short_07.jpg",
                #     "D:/Python/python正式文件/PCB/img/01_short_11.jpg",
                #     "D:/Python/python正式文件/PCB/img/01_short_13.jpg",
                #     "D:/Python/python正式文件/PCB/img/06_short_07.jpg",
                #     "D:/Python/python正式文件/PCB/img/07_short_05.jpg",
                # ],
                "image_paths": [
                    "D:/Python/python正式文件/PCB/img2/02_压伤_25.jpg",
                    "D:/Python/python正式文件/PCB/img2/02_压伤_27.jpg",
                    "D:/Python/python正式文件/PCB/img2/02_压伤_29.jpg",
                    "D:/Python/python正式文件/PCB/img2/02_压伤_30.jpg",
                    "D:/Python/python正式文件/PCB/img2/02_压伤_32.jpg",
                    "D:/Python/python正式文件/PCB/img2/02_压伤_34.jpg",
                ],
                "left_text": "【压伤缺陷】\n\n成因：\n1. 生产设备压力参数设置不当\n2. 堆叠存放时重压导致变形\n3. 夹具夹紧力过大\n4. 运输过程中挤压碰撞\n5. 检测治具下压力度超标",
                "right_text": "【修复建议】\n\n解决方案：\n1. 轻微压伤可通过加热整平修复\n2. 严重压伤需更换受损区域板材\n3. 调整设备压力参数至标准范围\n4. 优化堆叠方式，控制堆叠高度\n5. 更换缓冲型夹具和治具",
                "type": "压伤"
            },
            {
                # "image_paths": [
                #     "D:/Python/python正式文件/PCB/img/01_spurious_copper_19.jpg",
                #     "D:/Python/python正式文件/PCB/img/06_spurious_copper_09.jpg",
                #     "D:/Python/python正式文件/PCB/img/07_spurious_copper_09.jpg",
                #     "D:/Python/python正式文件/PCB/img/09_spurious_copper_09.jpg",
                #     "D:/Python/python正式文件/PCB/img/12_spurious_copper_04.jpg",
                #     "D:/Python/python正式文件/PCB/img/12_spurious_copper_08.jpg",
                # ],
                "image_paths": [
                    "D:/Python/python正式文件/PCB/img2/03_氧化_40.jpg",
                    "D:/Python/python正式文件/PCB/img2/03_氧化_42.jpg",
                    "D:/Python/python正式文件/PCB/img2/03_氧化_44.jpg",
                    "D:/Python/python正式文件/PCB/img2/03_氧化_45.jpg",
                    "D:/Python/python正式文件/PCB/img2/03_氧化_47.jpg",
                    "D:/Python/python正式文件/PCB/img2/03_氧化_49.jpg",
                ],
                "left_text": "【氧化缺陷】\n\n成因：\n1. 存储环境湿度超标\n2. 板面防氧化层涂覆不均\n3. 长时间暴露在空气中\n4. 清洗液酸碱度不当\n5. 焊接温度过高加速氧化",
                "right_text": "【修复建议】\n\n解决方案：\n1. 轻微氧化可用专用除锈剂清洁\n2. 氧化严重的焊盘需重新镀锡处理\n3. 改善存储环境，使用真空包装\n4. 重新涂覆防氧化保护涂层\n5. 控制焊接温度和时间参数",
                "type": "氧化"
            }
        ]

        # 创建并添加所有缺陷页面
        for data in defect_data:
            page = DefectPage(
                data["image_paths"],  # 传递图片路径列表
                data["left_text"],
                data["right_text"],
                data["type"]
            )
            self.stacked_widget.addWidget(page)

    def switch_page(self, index):
        # 切换页面时更新按钮状态
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)

        # 切换页面并更新聊天界面的缺陷类型
        self.stacked_widget.setCurrentIndex(index)
        current_page = self.stacked_widget.currentWidget()
        if hasattr(current_page, 'update_chat_defect_type'):
            current_page.update_chat_defect_type()


# ==================== 用户管理相关类 ====================

class AddUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加用户")
        self.setFixedSize(400, 300)
        self.setStyleSheet("QDialog { background-color: #2c3e50; }")
        layout = QFormLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名")
        self.username_input.setMinimumHeight(40)
        self.username_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(200, 200, 200, 20);
                border: 2px solid rgba(255, 255, 255, 30);
                border-radius: 8px;
                padding: 8px 15px;
                color: white;
                font-size: 14px;
                min-height: 40px;
            }
            QLineEdit:focus { border: 2px solid #3498db; background-color: rgba(200, 200, 200, 25); }
            QLineEdit::placeholder { color: #bdc3c7; font-size: 13px; }
        """)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(40)
        self.password_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(200, 200, 200, 20);
                border: 2px solid rgba(255, 255, 255, 30);
                border-radius: 8px;
                padding: 8px 15px;
                color: white;
                font-size: 14px;
                min-height: 40px;
            }
            QLineEdit:focus { border: 2px solid #3498db; background-color: rgba(200, 200, 200, 25); }
            QLineEdit::placeholder { color: #bdc3c7; font-size: 13px; }
        """)

        self.role_combo = QComboBox()
        self.role_combo.addItems(['user', 'admin'])
        self.role_combo.setMinimumHeight(40)
        self.role_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(200, 200, 200, 20);
                border: 2px solid rgba(255, 255, 255, 30);
                border-radius: 8px;
                padding: 8px 15px;
                color: white;
                font-size: 14px;
                min-height: 40px;
            }
            QComboBox:focus { border: 2px solid #3498db; background-color: rgba(200, 200, 200, 25); }
            QComboBox QAbstractItemView {
                background-color: #34495e; border: 1px solid #3498db; color: white;
                selection-background-color: #3498db;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow { color: white; }
        """)

        username_label = QLabel("用户名:")
        password_label = QLabel("密码:")
        role_label = QLabel("角色:")
        label_style = "QLabel { color: white; font-size: 16px; font-weight: bold; padding: 5px 0; }"
        username_label.setStyleSheet(label_style)
        password_label.setStyleSheet(label_style)
        role_label.setStyleSheet(label_style)

        layout.addRow(username_label, self.username_input)
        layout.addRow(password_label, self.password_input)
        layout.addRow(role_label, self.role_combo)

        buttons = QDialogButtonBox()
        confirm_button = QPushButton("确认")
        cancel_button = QPushButton("取消")
        buttons.addButton(confirm_button, QDialogButtonBox.AcceptRole)
        buttons.addButton(cancel_button, QDialogButtonBox.RejectRole)
        buttons.setStyleSheet("""
            QDialogButtonBox { background-color: transparent; margin-top: 20px; }
            QPushButton {
                background-color: #3498db; color: white; border: none; border-radius: 6px;
                padding: 10px 20px; font-size: 14px; font-weight: bold; min-width: 100px; min-height: 40px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #21618c; }
            QPushButton:focus { outline: none; }
        """)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_user_data(self):
        return {
            'username': self.username_input.text(),
            'password': self.password_input.text(),
            'role': self.role_combo.currentText()
        }


class CustomMessageBox(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QMessageBox {
                background-color: #2c3e50; color: white; border: 2px solid #3498db; border-radius: 10px;
            }
            QMessageBox QLabel { color: white; font-size: 14px; background-color: transparent; }
            QMessageBox QPushButton {
                background-color: #3498db; color: white; border: none; border-radius: 5px;
                padding: 8px 15px; font-size: 12px; min-width: 80px;
            }
            QMessageBox QPushButton:hover { background-color: #2980b9; }
            QMessageBox QPushButton:pressed { background-color: #21618c; }
        """)


class MainMenu(QMainWindow):
    def __init__(self, user_info):
        super().__init__()
        self.user_info = user_info

        # 初始化所有属性
        self.detection_page = None
        self.annotation_tool = None
        self.menu_buttons = []
        self.stacked_widget = None
        self.defect_type_page = None

        # 对于管理员和用户的不同页面
        if self.user_info['role'] == 'admin':
            self.user_management_page = None
        else:
            self.defect_analysis_page = None

        # 设置与检测界面相同的窗口大小
        self.setWindowTitle(f"电路板微小缺陷检测系统 - {user_info['username']}({user_info['role']})")
        self.setFixedSize(1200, 800)
        self.setStyleSheet("background-color: #2c3e50;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        title_text = f"电路板微小缺陷检测系统 - 欢迎 {user_info['username']}"
        if user_info['role'] == 'admin':
            title_text += " [管理员]"
        title_bar = QLabel(title_text)
        title_bar.setStyleSheet("""
            background-color: #34495e; color: white; font-size: 20px; font-weight: bold;
            padding: 15px; border-bottom: 2px solid #16a085;
        """)
        title_bar.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_bar)

        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        menu_frame = QFrame()
        menu_frame.setStyleSheet("QFrame { background-color: #34495e; border-right: 2px solid #16a085; }")
        menu_frame.setFixedWidth(250)
        menu_layout = QVBoxLayout(menu_frame)
        menu_layout.setSpacing(10)
        menu_layout.setContentsMargins(20, 30, 20, 30)

        # 创建菜单按钮
        self.create_menu_buttons(menu_layout)

        menu_layout.addStretch()
        self.stacked_widget = QStackedWidget()

        # 创建所有页面
        self.create_all_pages()

        content_layout.addWidget(menu_frame)
        content_layout.addWidget(self.stacked_widget)
        main_layout.addWidget(content_widget)

        # 默认显示欢迎页面
        self.stacked_widget.setCurrentIndex(0)

    def create_menu_buttons(self, menu_layout):
        """创建菜单按钮"""
        # 清空现有按钮
        for i in reversed(range(menu_layout.count())):
            widget = menu_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        self.menu_buttons = []

        # 根据用户角色显示不同的菜单
        if self.user_info['role'] == 'admin':
            buttons = [
                ("开始检测", "开始检测"),
                ("用户管理", "用户管理"),
                #("图片标注工具", "图片标注"),
                ("退出系统", "退出")
            ]
        else:
            buttons = [
                ("开始检测", "开始检测"),
                ("缺陷类型及方案", "缺陷类型"),
                #("图片标注工具", "图片标注"),
                ("退出系统", "退出")
            ]

        for text, action in buttons:
            btn = QPushButton(text)
            btn.setMinimumHeight(50)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db; color: white; border: none; border-radius: 8px;
                    font-size: 14px; font-weight: bold; padding: 10px;
                }
                QPushButton:hover { background-color: #2980b9; }
                QPushButton:pressed { background-color: #21618c; }
            """)
            btn.clicked.connect(lambda checked, a=action: self.on_menu_click(a))
            self.menu_buttons.append(btn)
            menu_layout.addWidget(btn)

    def create_all_pages(self):
        """创建所有页面"""
        try:
            # 如果stacked_widget不存在，先创建
            if self.stacked_widget is None:
                self.stacked_widget = QStackedWidget()

            # 清空现有页面
            for i in reversed(range(self.stacked_widget.count())):
                widget = self.stacked_widget.widget(i)
                self.stacked_widget.removeWidget(widget)
                widget.deleteLater()

            # 欢迎页面 - 总是第一个页面 (索引 0)
            welcome_page = self.create_welcome_page()
            self.stacked_widget.addWidget(welcome_page)

            # 根据用户角色添加其他页面
            if self.user_info['role'] == 'admin':
                # 用户管理页面 - 第二个页面 (索引 1)
                self.user_management_page = self.create_user_management_page()
                self.stacked_widget.addWidget(self.user_management_page)

                # 图片标注工具 - 第三个页面 (索引 2)
                #self.annotation_page = self.create_annotation_page()
                #self.stacked_widget.addWidget(self.annotation_page)
            else:
                # 普通用户的缺陷类型页面 - 第二个页面 (索引 1)
                self.defect_type_page = DefectTypeWidget()
                self.stacked_widget.addWidget(self.defect_type_page)

                # 图片标注工具 - 第三个页面 (索引 2)
                #self.annotation_page = self.create_annotation_page()
                #self.stacked_widget.addWidget(self.annotation_page)

            print(f"✅ 页面创建完成，共 {self.stacked_widget.count()} 个页面")
            if self.user_info['role'] == 'admin':
                print(f"✅ 管理员页面索引: 0-欢迎页, 1-用户管理 ")
            else:
                print(f"✅ 普通用户页面索引: 0-欢迎页, 1-缺陷类型")

        except Exception as e:
            print(f"❌ 创建页面时出错: {e}")
            import traceback
            traceback.print_exc()

    def create_welcome_page(self):
        """创建欢迎页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        welcome_label = QLabel("欢迎使用电路板微小缺陷检测系统")
        welcome_label.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        welcome_label.setAlignment(Qt.AlignCenter)

        role_text = "管理员" if self.user_info['role'] == 'admin' else "用户"
        sub_label = QLabel(f"当前用户: {self.user_info['username']} ({role_text})\n请从左侧菜单选择功能")
        sub_label.setStyleSheet("color: #bdc3c7; font-size: 18px;")
        sub_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(welcome_label)
        layout.addWidget(sub_label)
        return page

    def create_user_management_page(self):
        """创建用户管理页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("用户管理")
        title.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        button_layout = QHBoxLayout()
        add_user_btn = QPushButton("添加用户")
        add_user_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; border: none; padding: 8px 15px; border-radius: 5px; } QPushButton:hover { background-color: #219a52; }")
        add_user_btn.clicked.connect(self.add_user)

        delete_user_btn = QPushButton("删除用户")
        delete_user_btn.setStyleSheet(
            "QPushButton { background-color: #e74c3c; color: white; border: none; padding: 8px 15px; border-radius: 5px; } QPushButton:hover { background-color: #c0392b; }")
        delete_user_btn.clicked.connect(self.delete_user)

        button_layout.addWidget(add_user_btn)
        button_layout.addWidget(delete_user_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.users_table = QTableWidget()
        self.users_table.setStyleSheet("""
            QTableWidget { 
                background-color: white; 
                color: black; 
                border: 1px solid #bdc3c7; 
            }
            QHeaderView::section { 
                background-color: #34495e; 
                color: white; 
                padding: 8px; 
                border: none; 
            }
        """)
        self.users_table.setColumnCount(4)
        self.users_table.setHorizontalHeaderLabels(["ID", "用户名", "角色", "创建时间"])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.users_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.users_table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.users_table)

        # 加载用户数据
        self.load_users()
        return page

    def load_users(self):
        """加载用户列表"""
        try:
            users = db_manager.get_all_users()
            self.users_table.setRowCount(len(users))
            for row, user in enumerate(users):
                for col, value in enumerate(user):
                    # 格式化时间显示
                    if col == 3 and value:  # 创建时间列
                        # 如果是字符串时间，尝试格式化
                        if isinstance(value, str):
                            try:
                                # 尝试解析数据库时间格式
                                dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                                value = dt.strftime('%Y-%m-%d %H:%M:%S')
                            except:
                                # 如果解析失败，使用原始值
                                pass
                    item = QTableWidgetItem(str(value))
                    self.users_table.setItem(row, col, item)
        except Exception as e:
            print(f"❌ 加载用户列表时出错: {e}")

    def add_user(self):
        """添加用户"""
        dialog = AddUserDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            user_data = dialog.get_user_data()
            if not user_data['username'] or not user_data['password']:
                msg = CustomMessageBox(self)
                msg.setWindowTitle("输入错误")
                msg.setText("用户名和密码不能为空")
                msg.setIcon(QMessageBox.Warning)
                msg.exec_()
                return

            # 使用全局数据库实例添加用户
            if db_manager.add_user(user_data['username'], user_data['password'], user_data['role']):
                msg = CustomMessageBox(self)
                msg.setWindowTitle("成功")
                msg.setText("用户添加成功")
                msg.setIcon(QMessageBox.Information)
                msg.exec_()
                self.load_users()  # 自动刷新列表
            else:
                msg = CustomMessageBox(self)
                msg.setWindowTitle("错误")
                msg.setText("用户添加失败，用户名可能已存在")
                msg.setIcon(QMessageBox.Warning)
                msg.exec_()

    def delete_user(self):
        """删除用户"""
        current_row = self.users_table.currentRow()
        if current_row < 0:
            msg = CustomMessageBox(self)
            msg.setWindowTitle("选择错误")
            msg.setText("请先选择要删除的用户")
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()
            return
        user_id = int(self.users_table.item(current_row, 0).text())
        username = self.users_table.item(current_row, 1).text()
        if user_id == self.user_info['id']:
            msg = CustomMessageBox(self)
            msg.setWindowTitle("删除失败")
            msg.setText("不能删除当前登录的用户")
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()
            return
        confirm_msg = CustomMessageBox(self)
        confirm_msg.setWindowTitle("确认删除")
        confirm_msg.setText(f"确定要删除用户 '{username}' 吗？\n此操作将同时删除该用户的所有检测记录，且不可恢复！")
        confirm_msg.setIcon(QMessageBox.Question)
        confirm_msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        confirm_msg.setDefaultButton(QMessageBox.No)
        if confirm_msg.exec_() == QMessageBox.Yes:
            # 使用全局数据库实例删除用户
            if db_manager.delete_user(user_id):
                msg = CustomMessageBox(self)
                msg.setWindowTitle("成功")
                msg.setText("用户删除成功")
                msg.setIcon(QMessageBox.Information)
                msg.exec_()
                self.load_users()  # 自动刷新列表
            else:
                msg = CustomMessageBox(self)
                msg.setWindowTitle("错误")
                msg.setText("用户删除失败")
                msg.setIcon(QMessageBox.Warning)
                msg.exec_()

    def on_menu_click(self, action):
        """菜单点击处理"""
        try:
            print(f"🔄 尝试切换到: {action}")
            print(f"📊 当前堆栈页面数: {self.stacked_widget.count()}")

            if action == "开始检测":
                self.show_detection_page()
            elif action == "缺陷类型":
                # 只有普通用户才能访问缺陷类型页面
                if self.user_info['role'] == 'user':
                    target_index = 1
                    print(f"🎯 切换到缺陷类型页面，索引: {target_index}")
                    self.stacked_widget.setCurrentIndex(target_index)
            elif action == "用户管理":
                if self.user_info['role'] == 'admin':
                    target_index = 1  # 现在用户管理是第二个页面
                    print(f"🎯 切换到用户管理页面，索引: {target_index}")
                    self.stacked_widget.setCurrentIndex(target_index)
            elif action == "退出":
                self.close()
            else:
                print(f"点击了: {action}")

            print(f"✅ 切换到: {action}")

            '''elif action == "图片标注":
                if self.user_info['role'] == 'admin':
                    target_index = 2  # 管理员标注工具是第三个页面
                else:
                    target_index = 2  # 普通用户标注工具是第三个页面
                print(f"🎯 切换到图片标注工具页面，索引: {target_index}")
                self.stacked_widget.setCurrentIndex(target_index)'''



        except Exception as e:
            print(f"❌ 菜单点击处理出错: {e}")
            import traceback
            traceback.print_exc()

    def show_detection_page(self):
        """显示检测页面"""
        try:
            if self.detection_page is None:
                print("🔄 初始化检测页面...")
                from main2 import MyMainWindow
                try:
                    from tool.parser import get_config
                    cfg = get_config()
                    path_cfg = 'D:/Python/python正式文件/PCB/config/configs.yaml'
                    cfg.merge_from_file(path_cfg)
                    self.detection_page = MyMainWindow(cfg)
                except Exception as e:
                    print(f"❌ 使用配置文件失败: {e}，使用默认配置")
                    self.detection_page = MyMainWindow()

                # 传递用户信息给检测页面
                self.detection_page.user_info = self.user_info
                self.detection_page.db_manager = db_manager

                # 设置检测窗口为独立窗口，而不是嵌入到堆栈中
                self.detection_page.setParent(None)  # 移除父级关系
                self.detection_page.setWindowFlags(Qt.Window)  # 设置为独立窗口

                print("✅ 检测页面已初始化")

            # 显示检测窗口
            self.detection_page.show()
            self.detection_page.raise_()
            self.detection_page.activateWindow()
            print("✅ 检测页面已显示")

        except Exception as e:
            print(f"❌ 显示检测页面时出错: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "错误", f"无法打开检测页面: {str(e)}")



if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    user_info = {'id': 1, 'username': 'admin', 'role': 'admin'}
    window = MainMenu(user_info)
    window.show()
    sys.exit(app.exec_())