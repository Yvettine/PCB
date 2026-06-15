import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QLabel, QLineEdit, QPushButton,
                             QMessageBox, QFrame, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from database import db_manager


class LoginWindow(QMainWindow):
    login_success = pyqtSignal(dict)  # 登录成功信号，传递用户信息

    def __init__(self):
        super().__init__()
        self.setWindowTitle("电路板检测系统 - 登录")
        self.setFixedSize(450, 550)  # 稍微调整窗口大小
        self.setStyleSheet("background-color: #2c3e50;")

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(30)
        layout.setContentsMargins(40, 40, 40, 40)  # 设置边距

        # 标题
        title_label = QLabel("电路板微小缺陷检测系统")
        title_label.setStyleSheet("""
            color: white;
            font-size: 22px;
            font-weight: bold;
            padding: 10px;
        """)
        title_label.setAlignment(Qt.AlignCenter)

        # 登录框
        login_frame = QFrame()
        login_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 15);
                border-radius: 15px;
            }
        """)
        login_frame.setFixedSize(350, 350)  # 固定登录框大小

        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 5)
        login_frame.setGraphicsEffect(shadow)

        login_layout = QVBoxLayout(login_frame)
        login_layout.setSpacing(25)
        login_layout.setContentsMargins(40, 40, 40, 40)  # 设置内边距

        # 用户名输入框
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("请输入用户名")
        self.username_input.setFixedHeight(50)  # 固定高度
        self.username_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 25);
                border: 2px solid rgba(255, 255, 255, 60);
                border-radius: 10px;
                padding: 0px 15px;
                color: white;
                font-size: 14px;
                font-family: Microsoft YaHei, Arial;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
                background-color: rgba(255, 255, 255, 35);
            }
            QLineEdit::placeholder {
                color: #bdc3c7;
                font-size: 14px;
                font-family: Microsoft YaHei, Arial;
            }
        """)

        # 密码输入框
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(50)  # 固定高度
        self.password_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 25);
                border: 2px solid rgba(255, 255, 255, 60);
                border-radius: 10px;
                padding: 0px 15px;
                color: white;
                font-size: 14px;
                font-family: Microsoft YaHei, Arial;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
                background-color: rgba(255, 255, 255, 35);
            }
            QLineEdit::placeholder {
                color: #bdc3c7;
                font-size: 14px;
                font-family: Microsoft YaHei, Arial;
            }
        """)

        # 登录按钮
        login_button = QPushButton("登录")
        login_button.setFixedHeight(50)  # 固定高度
        login_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
                font-family: Microsoft YaHei, Arial;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:focus {
                outline: none;
            }
        """)
        login_button.clicked.connect(self.login)

        # 删除默认账号提示
        # tip_label = QLabel("默认账号: admin/admin123 或 user1/user123")  # 删除这行
        # tip_label.setStyleSheet("""
        #     color: #bdc3c7;
        #     font-size: 12px;
        #     font-family: Microsoft YaHei, Arial;
        #     padding: 10px;
        # """)
        # tip_label.setAlignment(Qt.AlignCenter)

        # 添加到布局
        login_layout.addWidget(self.username_input)
        login_layout.addWidget(self.password_input)
        login_layout.addWidget(login_button)
        # login_layout.addWidget(tip_label)  # 删除这行

        # 添加到主布局
        layout.addWidget(title_label)
        layout.addStretch(1)  # 添加弹性空间
        layout.addWidget(login_frame)
        layout.addStretch(1)  # 添加弹性空间

        # 设置默认焦点
        self.username_input.setFocus()

        # 回车键登录
        self.username_input.returnPressed.connect(self.login)
        self.password_input.returnPressed.connect(self.login)

    def login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "输入错误", "请输入用户名和密码")
            return

        user_info = db_manager.verify_user(username, password)

        if user_info:
            self.login_success.emit(user_info)
            self.close()
        else:
            QMessageBox.warning(self, "登录失败", "用户名或密码错误")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec_())