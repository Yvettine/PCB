import sqlite3
from configparser import ConfigParser
import os
from datetime import datetime


class DatabaseManager:
    def __init__(self):
        self.db_type = 'sqlite'  # 强制使用 SQLite
        self.config = self.load_config()
        try:
            self.conn = sqlite3.connect('pcb_detection.db', check_same_thread=False)
            # 设置行工厂以支持列名访问
            self.conn.row_factory = sqlite3.Row
            self.init_database()
            print("✅ 数据库初始化成功")
        except Exception as e:
            print(f"❌ 数据库初始化失败: {e}")
            # 创建基本的数据库连接
            self.conn = sqlite3.connect(':memory:', check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.init_database()

    def load_config(self):
        config = ConfigParser()
        config_file = 'config/database.ini'

        if not os.path.exists(config_file):
            # 创建默认配置
            config['DATABASE'] = {
                'type': 'sqlite',
                'host': 'localhost',
                'port': '3306',
                'user': 'root',
                'password': 'password',
                'database': 'pcb_detection'
            }
            os.makedirs('config', exist_ok=True)
            with open(config_file, 'w') as f:
                config.write(f)

        config.read(config_file)
        return config['DATABASE']

    def get_connection(self):
        """获取数据库连接 - 只使用 SQLite"""
        conn = sqlite3.connect('pcb_detection.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """初始化数据库和表"""
        cursor = self.conn.cursor()

        # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_time DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建检测记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detection_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                image_path TEXT,
                detection_result TEXT,
                detection_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                confidence REAL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # 插入默认管理员账户 - 使用精确的当前时间
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            cursor.execute(
                "INSERT OR IGNORE INTO users (username, password, role, created_time) VALUES (?, ?, ?, ?)",
                ('admin', 'admin123', 'admin', current_time)
            )
            cursor.execute(
                "INSERT OR IGNORE INTO users (username, password, role, created_time) VALUES (?, ?, ?, ?)",
                ('user1', 'user123', 'user', current_time)
            )
            print(f"✅ 默认用户创建时间: {current_time}")
        except Exception as e:
            print(f"插入默认用户时出错: {e}")

        self.conn.commit()

    def verify_user(self, username, password):
        """验证用户登录"""
        cursor = self.conn.cursor()

        cursor.execute(
            "SELECT id, username, role FROM users WHERE username = ? AND password = ?",
            (username, password)
        )
        user = cursor.fetchone()

        if user:
            return {
                'id': user[0],
                'username': user[1],
                'role': user[2]
            }
        return None

    def add_user(self, username, password, role='user'):
        """添加用户（管理员功能）"""
        cursor = self.conn.cursor()

        try:
            # 使用精确的当前系统时间
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            print(f"🕒 插入用户时间: {current_time}")

            cursor.execute(
                "INSERT INTO users (username, password, role, created_time) VALUES (?, ?, ?, ?)",
                (username, password, role, current_time)
            )
            self.conn.commit()

            # 验证插入的时间
            cursor.execute("SELECT created_time FROM users WHERE username = ?", (username,))
            result = cursor.fetchone()
            actual_time = result[0] if result else None
            print(f"✅ 数据库中的实际时间: {actual_time}")

            return True
        except sqlite3.IntegrityError:
            print(f"添加用户失败: 用户名 '{username}' 已存在")
            return False
        except Exception as e:
            print(f"添加用户失败: {e}")
            return False

    def get_all_users(self):
        """获取所有用户（管理员功能）"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, username, role, created_time FROM users ORDER BY id DESC")
        users = cursor.fetchall()

        # 将行对象转换为元组列表
        result = []
        for user in users:
            created_time = user['created_time']
            result.append((
                user['id'],
                user['username'],
                user['role'],
                created_time
            ))

        return result

    def delete_user(self, user_id):
        """删除用户"""
        cursor = self.conn.cursor()
        try:
            # 先删除用户的检测记录
            cursor.execute("DELETE FROM detection_records WHERE user_id = ?", (user_id,))
            # 再删除用户
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"删除用户失败: {e}")
            return False

    def get_user_records(self, user_id):
        """获取用户的检测记录"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, image_path, detection_result, confidence, detection_time FROM detection_records WHERE user_id = ? ORDER BY detection_time DESC",
            (user_id,))
        return cursor.fetchall()

    def get_all_records(self):
        """获取所有检测记录"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT r.id, u.username, r.image_path, r.detection_result, r.confidence, r.detection_time 
            FROM detection_records r 
            JOIN users u ON r.user_id = u.id 
            ORDER BY r.detection_time DESC
        ''')
        return cursor.fetchall()

    def add_detection_record(self, user_id, image_path, detection_result, confidence):
        """添加检测记录"""
        cursor = self.conn.cursor()
        try:
            # 使用精确的当前时间
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                "INSERT INTO detection_records (user_id, image_path, detection_result, confidence, detection_time) VALUES (?, ?, ?, ?, ?)",
                (user_id, image_path, str(detection_result), confidence, current_time))
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"添加检测记录失败: {e}")
            return None

    def get_user_by_username(self, username):
        """根据用户名获取用户信息"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, username, role, created_time FROM users WHERE username = ?",
            (username,)
        )
        user = cursor.fetchone()
        if user:
            return {
                'id': user['id'],
                'username': user['username'],
                'role': user['role'],
                'created_time': user['created_time']
            }
        return None

    def update_user_password(self, user_id, new_password):
        """更新用户密码"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (new_password, user_id)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"更新密码失败: {e}")
            return False

    def close_connection(self):
        """关闭数据库连接"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()


# 全局数据库实例
db_manager = DatabaseManager()