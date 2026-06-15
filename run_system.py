import sys
import os

# 设置Qt插件路径
try:
    import PyQt5

    pyqt5_path = os.path.dirname(PyQt5.__file__)
    correct_plugin_path = (r"D:/Python/Lib/site-packages/PyQt5/Qt5/plugins")

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

from PyQt5.QtWidgets import QApplication
from login_window import LoginWindow
from main_menu import MainMenu
from database import db_manager  # 导入全局数据库实例


class SystemLauncher:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setStyle("Fusion")

        # 显示登录窗口
        self.login_window = LoginWindow()
        self.login_window.login_success.connect(self.on_login_success)
        self.login_window.show()

    def on_login_success(self, user_info):
        """登录成功后的回调"""
        print(f"✅ 用户 {user_info['username']} 登录成功")

        # 关闭登录窗口，显示主菜单
        self.login_window.close()

        # 创建主菜单窗口
        self.main_menu = MainMenu(user_info)
        self.main_menu.show()

    def run(self):
        """运行应用程序"""
        try:
            return self.app.exec_()
        except Exception as e:
            print(f"❌ 应用程序运行错误: {e}")
            return 1
        finally:
            # 程序退出时关闭数据库连接
            if hasattr(db_manager, 'close_connection'):
                db_manager.close_connection()


if __name__ == "__main__":
    launcher = SystemLauncher()
    sys.exit(launcher.run())