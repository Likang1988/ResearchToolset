from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionProgressBar, QStyle
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor

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

        # 根据执行率计算颜色
        if rate >= 100:
            # 执行率超过100%：浅红色
            color = QColor(255, 153, 153)
        else:
            # 根据执行率在浅绿色和浅红色之间插值
            progress_ratio = min(rate / 100.0, 1.0)
            start_r, start_g, start_b = 153, 255, 153
            end_r, end_g, end_b = 255, 153, 153
            # 线性插值计算当前颜色
            r = int(start_r + (end_r - start_r) * progress_ratio)
            g = int(start_g + (end_g - start_g) * progress_ratio)
            b = int(start_b + (end_b - start_b) * progress_ratio)
            color = QColor(r, g, b)

        # 绘制进度条背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(240, 240, 240))
        painter.drawRoundedRect(progress_bar.rect, 1, 1)

        # 绘制进度条，确保不超出单元格
        progress_rect = QRect(progress_bar.rect)
        progress_width = min(int(progress_rect.width() * rate / 100), progress_rect.width())
        progress_rect.setWidth(progress_width)
        painter.setBrush(color)
        painter.drawRoundedRect(progress_rect, 1, 1)  # 圆角矩形

        # 绘制文本
        painter.setPen(Qt.black)
        painter.drawText(progress_bar.rect, Qt.AlignRight | Qt.AlignVCenter, progress_bar.text)

        # 恢复画笔状态
        painter.restore()

    def sizeHint(self, option, index):
        # 返回建议的大小
        return option.rect.size()