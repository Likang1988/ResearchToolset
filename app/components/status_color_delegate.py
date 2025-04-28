from PySide6.QtWidgets import (QStyledItemDelegate, QWidget, QPushButton, QHBoxLayout,
                             QApplication, QStyleOptionViewItem, QColorDialog, QDialog, QVBoxLayout)
# 将 QModelIndex 和 QAbstractTableModel 移到 QtCore 的导入
from PySide6.QtCore import Qt, QSize, Signal, QEvent, QPoint, QRect, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QPainter, QColor, QBrush, QPen
from enum import Enum, unique

# 定义状态及其对应的颜色 (十六进制)
# 黄: 未开始, 绿: 进行中, 蓝: 已完成, 红: 已暂停, 紫: 已取消, 灰: 已关闭
STATUS_COLORS = {
    "NOT_STARTED": "#FFD700",  # Gold (Yellowish)
    "IN_PROGRESS": "#32CD32",  # LimeGreen
    "COMPLETED": "#1E90FF",    # DodgerBlue
    "PAUSED": "#FF4500",       # OrangeRed
    "CANCELLED": "#9370DB",    # MediumPurple
    "CLOSED": "#A9A9A9"        # DarkGray
}

@unique
class TaskStatus(Enum):
    NOT_STARTED = "未开始"
    IN_PROGRESS = "进行中"
    COMPLETED = "已完成"
    PAUSED = "已暂停"      # 替换 DELAYED
    CANCELLED = "已取消"
    CLOSED = "已关闭"

    @property
    def color(self):
        """获取状态对应的颜色"""
        return STATUS_COLORS.get(self.name, "#FFFFFF") # 默认为白色

class StatusColorButton(QPushButton):
    """自定义按钮，用于显示和选择颜色"""
    colorChanged = Signal(TaskStatus)

    def __init__(self, status, color, parent=None):
        super().__init__(parent)
        self.status = status
        self.color = QColor(color)
        self.setFixedSize(20, 20)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.color.name()};
                border: 1px solid gray;
                border-radius: 10px; /* 使其成为圆形 */
            }}
            QPushButton:hover {{
                border: 2px solid black;
            }}
        """)
        self.setToolTip(status.value) # 显示状态名称作为提示
        self.clicked.connect(self._emit_color_changed)

    def _emit_color_changed(self):
        self.colorChanged.emit(self.status)

class StatusColorEditor(QDialog):
    """状态颜色选择编辑器 (弹出对话框)"""
    statusSelected = Signal(TaskStatus)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint) # 设置为无边框弹出窗口
        self.setWindowOpacity(0.95)
        self.setStyleSheet("background-color: white; border: 1px solid lightgray; border-radius: 4px;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 添加所有状态的颜色按钮
        for status in TaskStatus:
            color = STATUS_COLORS.get(status.name, "#FFFFFF")
            button = StatusColorButton(status, color, self)
            button.colorChanged.connect(self.on_status_selected)
            layout.addWidget(button)

        self.setLayout(layout)
        self.adjustSize() # 调整大小以适应内容

    def on_status_selected(self, status):
        self.statusSelected.emit(status)
        self.accept() # 关闭对话框

    def eventFilter(self, watched, event):
        # 如果在对话框外部点击，则关闭对话框
        if event.type() == QEvent.MouseButtonPress:
            if not self.geometry().contains(event.globalPos()):
                self.reject()
                return True
        return super().eventFilter(watched, event)

    def showEvent(self, event):
        # 安装事件过滤器以捕获外部点击
        QApplication.instance().installEventFilter(self)
        super().showEvent(event)

    def hideEvent(self, event):
        # 卸载事件过滤器
        QApplication.instance().removeEventFilter(self)
        super().hideEvent(event)


class StatusColorDelegate(QStyledItemDelegate):
    """用于绘制和编辑状态颜色的委托"""

    # 移除 index 的类型提示 : QModelIndex
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        # 获取状态颜色
        color = index.data(Qt.DecorationRole) # 从模型获取颜色
        if isinstance(color, QColor):
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)

            # 设置固定的圆圈大小和位置
            rect = option.rect
            size = 15  # 固定圆圈大小像素
            x = rect.center().x() - size / 2
            y = rect.center().y() - size / 2
            circle_rect = QRect(int(x), int(y), int(size), int(size))

            # 绘制圆圈
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.gray, 0.5)) # 添加一个细边框
            painter.drawEllipse(circle_rect)

            painter.restore()
        else:
            # 如果没有颜色数据，调用默认绘制方法
            super().paint(painter, option, index)

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        # 创建自定义编辑器
        editor = StatusColorEditor(parent)
        return editor

    def setEditorData(self, editor: QWidget, index: QModelIndex):
        # 不需要特别设置编辑器的初始数据，因为它总是显示所有颜色
        pass

    def setModelData(self, editor: QWidget, model: QAbstractTableModel, index: QModelIndex):
        # 当编辑器发出 statusSelected 信号时，更新模型
        # 这个连接在 editor 创建后进行，或者通过 editor 的信号直接更新模型
        # 这里我们假设 editor 会发出一个包含 TaskStatus 的信号
        # (在 StatusColorEditor 中通过 statusSelected 信号实现)
        editor.statusSelected.connect(lambda status: model.setData(index, status, Qt.EditRole))

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem, index: QModelIndex):
        # 将编辑器定位在单元格附近的合适位置
        rect = option.rect
        editor_size = editor.sizeHint()
        
        # 获取单元格在屏幕上的绝对位置
        view = option.widget
        if view:
            global_pos = view.mapToGlobal(rect.topLeft())
            rect.moveTopLeft(global_pos)
        
        # 计算初始位置（优先显示在单元格下方）
        x = rect.center().x() - editor_size.width() / 2
        y = rect.bottom()
        
        # 获取屏幕尺寸
        screen = QApplication.primaryScreen().geometry()
        
        # 确保编辑器不会超出屏幕边界
        if x + editor_size.width() > screen.right():
            x = screen.right() - editor_size.width()
        if x < screen.left():
            x = screen.left()
        
        # 如果底部放不下，就显示在上方
        if y + editor_size.height() > screen.bottom():
            y = rect.top() - editor_size.height()
        
        editor.move(int(x), int(y))

    def editorEvent(self, event, model, option, index):
        # 处理鼠标点击事件以弹出编辑器
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            editor = self.createEditor(option.widget, option, index)
            self.setEditorData(editor, index)
            self.setModelData(editor, model, index) # 连接信号
            self.updateEditorGeometry(editor, option, index)
            editor.exec() # 显示为模态对话框，等待选择
            # 不需要显式调用 commitAndCloseEditor，因为 StatusColorEditor 关闭时会触发信号更新模型
            return True # 事件已处理

        return super().editorEvent(event, model, option, index)
