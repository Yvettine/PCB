import os
import cv2
import numpy as np
from PyQt5.QtWidgets import (QMainWindow, QLabel, QVBoxLayout, QWidget,
                             QHBoxLayout, QPushButton, QFileDialog, QMessageBox,
                             QInputDialog, QListWidget)
from PyQt5.QtCore import Qt, QPoint, pyqtSignal, QRect
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont


class AnnotationTool(QWidget):
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图片标注工具")

        # 初始化变量
        self.image_path = None
        self.image = None
        self.annotations = []
        self.current_label = ""
        self.drawing = False
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.previous_labels = []
        self.base_labels = ["氧化", "异物", "刮伤", "压伤", "脏污"]

        # 新增文件夹相关变量
        self.current_folder = ""
        self.image_files = []
        self.current_image_index = -1

        # 性能优化相关
        self.display_pixmap = None
        self.original_pixmap = None
        self.scale_factor = 1.0
        self.last_draw_rect = None  # 记录上一次绘制的临时矩形，用于局部刷新

        self.init_ui()

    def init_ui(self):
        # 主布局直接设置在当前部件上
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # 左侧图像显示区域
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #222222; border: 1px solid #555555;")
        self.image_label.setMinimumSize(600, 500)

        # 右侧控制区域（保持不变）
        control_layout = QVBoxLayout()
        control_layout.setSpacing(10)

        # 按钮样式
        button_style = """
            QPushButton {
                background-color: #3498db;  
                color: white;
                padding: 8px;
                border-radius: 8px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;  
            }
            QPushButton:pressed {
                background-color: #21618c;  
            }
        """

        # 导航按钮样式
        nav_button_style = """
            QPushButton {
                background-color: #3498db;  
                color: white;
                padding: 8px;
                border-radius: 8px;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;  
            }
            QPushButton:pressed {
                background-color: #21618c;  
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
        """

        # 打开图片按钮
        btn_open = QPushButton("打开图片")
        btn_open.setStyleSheet(button_style)
        btn_open.clicked.connect(self.open_image)

        # 打开文件夹按钮
        btn_open_folder = QPushButton("打开文件夹")
        btn_open_folder.setStyleSheet(button_style)
        btn_open_folder.clicked.connect(self.open_folder)

        # 导航按钮布局
        nav_layout = QHBoxLayout()

        self.btn_prev = QPushButton("上一张")
        self.btn_prev.setStyleSheet(nav_button_style)
        self.btn_prev.clicked.connect(self.previous_image)
        self.btn_prev.setEnabled(False)

        self.btn_next = QPushButton("下一张")
        self.btn_next.setStyleSheet(nav_button_style)
        self.btn_next.clicked.connect(self.next_image)
        self.btn_next.setEnabled(False)

        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)

        # 保存标注按钮
        btn_save = QPushButton("保存标注")
        btn_save.setStyleSheet(button_style)
        btn_save.clicked.connect(self.save_annotations)

        # 添加标签按钮
        btn_add_label = QPushButton("添加标签")
        btn_add_label.setStyleSheet(button_style)
        btn_add_label.clicked.connect(self.add_label)

        # 清除标注按钮
        btn_clear = QPushButton("清除当前标注")
        btn_clear.setStyleSheet(button_style)
        btn_clear.clicked.connect(self.clear_annotations)

        # 状态显示标签
        self.status_label = QLabel("未打开图片")
        self.status_label.setStyleSheet("""
            color: #bdc3c7;
            font-size: 12px;
            padding: 5px;
        """)
        self.status_label.setAlignment(Qt.AlignCenter)

        # 标签列表
        self.label_list = QListWidget()
        self.label_list.setStyleSheet("""
            QListWidget {
                background-color: #ecf0f1;
                color: #2c3e50;
                font-size: 14px;
                padding: 5px;
                border-radius: 8px;
            }
        """)
        self.label_list.itemClicked.connect(self.on_label_clicked)  # 单独的点击事件

        # 初始添加基础标签
        for label in self.base_labels:
            self.label_list.addItem(label)

        # 添加到布局
        control_layout.addWidget(btn_open)
        control_layout.addWidget(btn_open_folder)
        control_layout.addLayout(nav_layout)
        control_layout.addWidget(btn_save)
        control_layout.addWidget(btn_add_label)
        control_layout.addWidget(btn_clear)
        control_layout.addWidget(self.status_label)
        control_layout.addWidget(QLabel("标签列表:"))
        control_layout.addWidget(self.label_list)
        control_layout.addStretch()

        # 主布局添加左右两部分
        main_layout.addWidget(self.image_label, 3)
        main_layout.addLayout(control_layout, 1)

        # 安装事件过滤器，优化事件处理
        self.image_label.installEventFilter(self)

    def eventFilter(self, obj, event):
        """事件过滤器，优化鼠标事件处理"""
        if obj == self.image_label:
            if event.type() == event.MouseButtonPress and event.button() == Qt.LeftButton:
                self.mouse_press_event(event)
                return True
            elif event.type() == event.MouseMove and self.drawing:
                self.mouse_move_event(event)
                return True
            elif event.type() == event.MouseButtonRelease and event.button() == Qt.LeftButton and self.drawing:
                self.mouse_release_event(event)
                return True
        return super().eventFilter(obj, event)

    def on_label_clicked(self, item):
        """标签点击事件，单独处理避免冲突"""
        self.current_label = item.text()

    def reset_annotation_state(self):
        """重置标注工具状态（轻量版，避免频繁销毁资源）"""
        self.annotations.clear()
        self.current_label = ""
        self.drawing = False
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.last_draw_rect = None

    def clear_annotations(self):
        """清除当前所有标注"""
        if self.annotations:
            self.annotations = []
            self.update_display()
            QMessageBox.information(self, "提示", "已清除所有标注")

    def open_image(self):
        """打开单张图片"""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.tif)",
            options=options
        )

        if file_path:
            self.load_single_image(file_path)

    def open_folder(self):
        """打开文件夹"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择图片文件夹", ""
        )

        if folder_path:
            self.current_folder = folder_path
            # 获取文件夹中所有支持的图片文件
            self.image_files = []
            extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif']
            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                if os.path.isfile(file_path) and any(file.lower().endswith(ext) for ext in extensions):
                    self.image_files.append(file_path)

            if not self.image_files:
                QMessageBox.warning(self, "警告", "文件夹中没有找到支持的图片文件")
                return

            # 按文件名排序
            self.image_files.sort()
            self.current_image_index = 0

            # 启用导航按钮
            self.btn_prev.setEnabled(len(self.image_files) > 1)
            self.btn_next.setEnabled(len(self.image_files) > 1)

            # 加载第一张图片
            self.load_current_image()

    def load_single_image(self, file_path):
        """加载单张图片"""
        # 重置文件夹状态
        self.current_folder = ""
        self.image_files = []
        self.current_image_index = -1
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)

        # 加载图片
        self._load_image_file(file_path)

    def load_current_image(self):
        """加载当前索引的图片"""
        if 0 <= self.current_image_index < len(self.image_files):
            file_path = self.image_files[self.current_image_index]
            self._load_image_file(file_path)

            # 更新状态显示
            self.status_label.setText(f"图片 {self.current_image_index + 1}/{len(self.image_files)}")

            # 更新导航按钮状态
            self.btn_prev.setEnabled(self.current_image_index > 0)
            self.btn_next.setEnabled(self.current_image_index < len(self.image_files) - 1)

    def _load_image_file(self, file_path):
        """加载图片文件的通用方法"""
        # 重置状态但保留标签历史
        self.reset_annotation_state()

        self.image_path = file_path
        file_name = os.path.basename(file_path)
        self.setWindowTitle(f"图片标注工具 - {file_name}")

        # 加载并显示图片（优化版本）
        if self.load_image(file_path):
            # 更新标签列表
            all_labels = list(set(self.previous_labels + self.base_labels))
            self.update_label_list(all_labels)

            # 尝试加载已有的标注文件
            self.load_existing_annotations()
        else:
            # 如果加载失败，在文件夹模式下尝试加载下一张图片
            if self.current_folder and len(self.image_files) > 1:
                reply = QMessageBox.question(self, "加载失败",
                                             f"无法加载图片: {file_name}\n是否尝试加载下一张图片？",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    if self.current_image_index < len(self.image_files) - 1:
                        self.current_image_index += 1
                        self.load_current_image()
                    else:
                        self.status_label.setText("所有图片加载失败")

    def previous_image(self):
        """切换到上一张图片"""
        if self.current_image_index > 0:
            # 先保存当前标注
            self.save_annotations_silent()

            self.current_image_index -= 1
            self.load_current_image()

    def next_image(self):
        """切换到下一张图片"""
        if self.current_image_index < len(self.image_files) - 1:
            # 先保存当前标注
            self.save_annotations_silent()

            self.current_image_index += 1
            self.load_current_image()

    def save_annotations_silent(self):
        """静默保存标注（不显示提示框）"""
        if not self.image_path:
            return

        try:
            # 保存YOLO格式
            txt_path = os.path.splitext(self.image_path)[0] + ".txt"
            height, width = self.image.shape[:2]

            with open(txt_path, 'w', encoding='utf-8') as f:
                for ann in self.annotations:
                    label = ann["label"]
                    x1, y1, x2, y2 = ann["bbox"]

                    # 转换为YOLO格式
                    x_center = (x1 + x2) / 2 / width
                    y_center = (y1 + y2) / 2 / height
                    bbox_width = (x2 - x1) / width
                    bbox_height = (y2 - y1) / height

                    # 标签映射
                    if label in self.base_labels:
                        class_id = self.base_labels.index(label)
                    else:
                        # 确保自定义标签在列表中
                        if label not in self.previous_labels:
                            self.previous_labels.append(label)
                        class_id = len(self.base_labels) + self.previous_labels.index(label)

                    f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {bbox_width:.6f} {bbox_height:.6f}\n")

            # 保存标签映射
            mapping_path = os.path.splitext(self.image_path)[0] + "_label_mapping.txt"
            with open(mapping_path, 'w', encoding='utf-8') as mapping_file:
                for i, label in enumerate(self.base_labels):
                    mapping_file.write(f"{i} {label}\n")
                for i, label in enumerate(self.previous_labels):
                    if label not in self.base_labels:
                        mapping_file.write(f"{len(self.base_labels) + i} {label}\n")
        except Exception as e:
            print(f"保存标注失败: {str(e)}")

    def load_existing_annotations(self):
        """加载已有的标注文件"""
        if not self.image_path:
            return

        txt_path = os.path.splitext(self.image_path)[0] + ".txt"
        if os.path.exists(txt_path):
            try:
                self.annotations = []
                height, width = self.image.shape[:2]

                with open(txt_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) == 5:
                            class_id = int(parts[0])
                            x_center = float(parts[1])
                            y_center = float(parts[2])
                            bbox_width = float(parts[3])
                            bbox_height = float(parts[4])

                            # 转换为像素坐标
                            x1 = int((x_center - bbox_width / 2) * width)
                            y1 = int((y_center - bbox_height / 2) * height)
                            x2 = int((x_center + bbox_width / 2) * width)
                            y2 = int((y_center + bbox_height / 2) * height)

                            # 获取标签名称
                            if class_id < len(self.base_labels):
                                label = self.base_labels[class_id]
                            else:
                                custom_id = class_id - len(self.base_labels)
                                if custom_id < len(self.previous_labels):
                                    label = self.previous_labels[custom_id]
                                else:
                                    label = f"未知标签{class_id}"

                            self.annotations.append({
                                "label": label,
                                "bbox": [x1, y1, x2, y2]
                            })

                self.update_display()
            except Exception as e:
                print(f"加载标注文件失败: {str(e)}")

    def load_image(self, path):
        """优化的图像加载函数，避免内存泄漏"""
        try:
            # 方法1: 使用OpenCV加载图像（处理中文路径）
            try:
                # 使用imdecode读取中文路径文件
                with open(path, 'rb') as f:
                    img_data = np.frombuffer(f.read(), np.uint8)
                self.image = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
            except:
                # 方法2: 如果方法1失败，尝试直接使用imread
                self.image = cv2.imread(path)

            if self.image is None:
                # 方法3: 使用PIL作为备用方案
                try:
                    from PIL import Image
                    pil_image = Image.open(path)
                    self.image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                except ImportError:
                    raise Exception("无法读取图像文件，请安装PIL库: pip install Pillow")
                except Exception as e:
                    raise Exception(f"所有图像加载方法都失败: {str(e)}")

            # 确保图像格式正确
            if self.image is None:
                raise Exception("无法读取图像文件")

            # 确保图像是3通道的
            if len(self.image.shape) == 2:
                self.image = cv2.cvtColor(self.image, cv2.COLOR_GRAY2BGR)
            elif self.image.shape[2] == 4:
                self.image = cv2.cvtColor(self.image, cv2.COLOR_RGBA2BGR)
            elif self.image.shape[2] == 1:
                self.image = cv2.cvtColor(self.image, cv2.COLOR_GRAY2BGR)

            # 转换为QPixmap并缓存
            height, width, channel = self.image.shape
            bytes_per_line = 3 * width
            q_img = QImage(self.image.data, width, height, bytes_per_line,
                           QImage.Format_RGB888).rgbSwapped()
            self.original_pixmap = QPixmap.fromImage(q_img)
            self.display_pixmap = self.original_pixmap.copy()

            # 计算缩放因子
            self.scale_factor = min(
                self.image_label.width() / width,
                self.image_label.height() / height
            )

            self.display_image()
            return True
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载图像失败: {str(e)}")
            return False

    def display_image(self):
        """显示图像，使用缓存的pixmap提高性能"""
        if self.display_pixmap:
            scaled_pixmap = self.display_pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation  # 平滑缩放，减少锯齿
            )
            self.image_label.setPixmap(scaled_pixmap)

    def save_annotations(self):
        if not self.image_path:
            QMessageBox.warning(self, "警告", "没有打开图片")
            return

        self.save_annotations_silent()
        QMessageBox.information(self, "成功", f"标注已保存")

    def add_label(self):
        label, ok = QInputDialog.getText(
            self, "添加标签", "输入新标签名称:"
        )
        if ok and label:
            if label not in self.base_labels and label not in self.previous_labels:
                self.previous_labels.append(label)
                self.label_list.addItem(label)
                self.current_label = label
            else:
                QMessageBox.warning(self, "警告", "标签已存在")

    def update_label_list(self, labels):
        """优化标签列表更新，避免不必要的重绘"""
        current_items = [self.label_list.item(i).text() for i in range(self.label_list.count())]
        for label in labels:
            if label not in current_items:
                self.label_list.addItem(label)

    def mouse_press_event(self, event):
        if self.original_pixmap and self.current_label:
            self.drawing = True
            self.start_point = event.pos()
            self.end_point = event.pos()

    def mouse_move_event(self, event):
        if self.drawing and self.original_pixmap:
            # 限制更新频率，避免过度绘制
            self.end_point = event.pos()
            self.update_display()

    def mouse_release_event(self, event):
        if self.drawing and self.current_label and self.original_pixmap:
            self.drawing = False
            self.end_point = event.pos()

            # 计算图像在控件中的实际位置和尺寸
            scaled_pixmap = self.original_pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio
            )
            img_display_width = scaled_pixmap.width()
            img_display_height = scaled_pixmap.height()

            # 计算偏移量（居中显示）
            x_offset = (self.image_label.width() - img_display_width) // 2
            y_offset = (self.image_label.height() - img_display_height) // 2

            # 调整坐标到图像范围内
            x1 = max(0, min(self.start_point.x() - x_offset, self.end_point.x() - x_offset))
            y1 = max(0, min(self.start_point.y() - y_offset, self.end_point.y() - y_offset))
            x2 = min(img_display_width, max(self.start_point.x() - x_offset, self.end_point.x() - x_offset))
            y2 = min(img_display_height, max(self.start_point.y() - y_offset, self.end_point.y() - y_offset))

            # 确保绘制的是有效矩形
            if x1 >= x2 or y1 >= y2:
                return

            # 计算缩放比例
            scale_w = self.original_pixmap.width() / img_display_width
            scale_h = self.original_pixmap.height() / img_display_height

            # 转换为原始图像坐标
            x1_orig = int(x1 * scale_w)
            y1_orig = int(y1 * scale_h)
            x2_orig = int(x2 * scale_w)
            y2_orig = int(y2 * scale_h)

            # 添加标注
            self.annotations.append({
                "label": self.current_label,
                "bbox": [x1_orig, y1_orig, x2_orig, y2_orig]
            })

            self.update_display()

    def update_display(self):
        """优化的显示更新函数，减少不必要的绘制操作"""
        if not self.original_pixmap:
            return

        # 复制原始图像用于绘制，使用缓存提高性能
        temp_pixmap = self.original_pixmap.copy()
        painter = QPainter(temp_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)  # 抗锯齿

        # 绘制所有已保存的标注
        for ann in self.annotations:
            label = ann["label"]
            x1, y1, x2, y2 = ann["bbox"]

            # 绘制矩形框
            pen = QPen(QColor(0, 255, 0), 2)  # 绿色
            painter.setPen(pen)
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)

            # 绘制标签文字（使用Qt的绘图，确保中文显示）
            font = QFont("SimHei", 10)  # 明确使用中文字体
            painter.setFont(font)
            painter.drawText(x1, max(15, y1 - 5), label)

        # 绘制当前正在绘制的矩形
        if self.drawing:
            # 计算坐标（与mouse_release_event一致）
            scaled_pixmap = self.original_pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio
            )
            img_display_width = scaled_pixmap.width()
            img_display_height = scaled_pixmap.height()

            x_offset = (self.image_label.width() - img_display_width) // 2
            y_offset = (self.image_label.height() - img_display_height) // 2

            scale_w = self.original_pixmap.width() / img_display_width
            scale_h = self.original_pixmap.height() / img_display_height

            x1 = int((self.start_point.x() - x_offset) * scale_w)
            y1 = int((self.start_point.y() - y_offset) * scale_h)
            x2 = int((self.end_point.x() - x_offset) * scale_w)
            y2 = int((self.end_point.y() - y_offset) * scale_h)

            # 绘制临时矩形
            pen = QPen(QColor(230, 126, 34), 2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)

        painter.end()
        self.display_pixmap = temp_pixmap
        self.display_image()

    def closeEvent(self, event):
        # 释放资源
        self.image = None
        self.original_pixmap = None
        self.display_pixmap = None
        self.closed.emit()
        # 如果是在主窗口中，不关闭窗口而是隐藏
        if hasattr(self.parent(), 'stacked_widget'):
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication


    # 用于独立测试的包装窗口
    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setGeometry(100, 100, 1000, 700)
            self.setWindowTitle("标注工具测试")
            self.setCentralWidget(AnnotationTool())

    # 确保中文显示正常
    QApplication.setApplicationName("图片标注工具")
    app = QApplication(sys.argv)

    # 设置全局字体
    font = QFont("SimHei")
    app.setFont(font)

    window = AnnotationTool()
    window.show()
    sys.exit(app.exec_())