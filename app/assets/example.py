''' 背景失效解决办法:
在 Win11 系统下，FluentWindow 默认启用了云母特效，如果窗口中使用了 QWebEngineView 
或者 QOpenGLWidget，会导致窗口背景特效失效，同时圆角和阴影也会消失。
下述例子演示了如何正确地在 FluentWindow 中使用 Web 引擎。
'''

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout)
from PySide6.QtCore import QUrl
from qfluentwidgets import FluentWindow, FluentIcon
from qframelesswindow.webengine import FramelessWebEngineView
import sys


class Widget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("homeInterface")

        self.webView = FramelessWebEngineView(self)
        self.webView.load(QUrl("https://www.baidu.com/"))

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(0, 48, 0, 0)
        self.vBoxLayout.addWidget(self.webView)


class Window(FluentWindow):

    def __init__(self):
        super().__init__()

        # 创建并添加子界面
        self.homeInterface = Widget(self)
        self.addSubInterface(self.homeInterface, FluentIcon.HOME, "Home")

        # 初始化窗口
        self.resize(900, 700)
        self.setWindowTitle('PyQt-Fluent-Widgets')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = Window()
    w.show()

    # 2. 重新启用云母特效
    w.setMicaEffectEnabled(True)

    app.exec()
