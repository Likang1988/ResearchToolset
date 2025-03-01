from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionProgressBar, QStyle, QApplication
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QLinearGradient

class ProgressBarDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter: QPainter, option, index):
        # 获取执行率文本
        text = index.data()
        if not text or not text.endswith('%'):
            super().paint(painter, option, index)
            return

        # 解析执行率值
        try:
            rate = float(text.rstrip('%'))
        except ValueError:
            super().paint(painter, option, index)
            return

        # 创建进度条选项
        progress_bar = QStyleOptionProgressBar()
        progress_bar.rect = option.rect.adjusted(4, 4, -4, -4)  # 设置边距
        progress_bar.minimum = 0
        progress_bar.maximum = 100
        progress_bar.progress = min(int(rate), 100)  # 限制进度不超过100%
        progress_bar.text = f"{rate:.2f}%"
        progress_bar.textVisible = True
        progress_bar.textAlignment = Qt.AlignCenter

        # 保存画笔状态
        painter.save()

        # 如果该项被选中，绘制选中背景
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # 创建渐变色
        gradient = QLinearGradient(progress_bar.rect.topLeft(), progress_bar.rect.topRight())
        if rate >= 100:
            # 执行率超过100%：纯红色
            gradient.setColorAt(0, QColor(255, 0, 0))
            gradient.setColorAt(1, QColor(255, 0, 0))
        else:
            # 从绿色渐变到红色
            green_component = int(255 * (1 - rate / 100))
            red_component = int(255 * (rate / 100))
            gradient.setColorAt(0, QColor(red_component, green_component, 0))
            gradient.setColorAt(1, QColor(red_component, green_component, 0))

        # 绘制进度条背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(240, 240, 240))
        painter.drawRoundedRect(progress_bar.rect, 1, 1)

        # 绘制进度条，确保不超出单元格
        progress_rect = QRect(progress_bar.rect)
        progress_width = min(int(progress_rect.width() * rate / 100), progress_rect.width())
        progress_rect.setWidth(progress_width)
        painter.setBrush(gradient)
        painter.drawRoundedRect(progress_rect, 1, 1)  # 圆角矩形

        # 绘制文本
        painter.setPen(Qt.black)
        painter.drawText(progress_bar.rect, Qt.AlignRight | Qt.AlignVCenter, progress_bar.text)

        # 恢复画笔状态
        painter.restore()

    def sizeHint(self, option, index):
        # 返回建议的大小
        return option.rect.size()