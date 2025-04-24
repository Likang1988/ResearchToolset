import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from PySide6.QtWidgets import (QApplication, QWidget)
from PySide6.QtGui import QIcon
from app.assets.test_sub import Widget as SubWidget # 使用绝对导入
from PySide6.QtCore import QUrl, QFileInfo
from qfluentwidgets import FluentWindow, FluentIcon
from qframelesswindow.webengine import FramelessWebEngineView
import sys
import os


class Window(FluentWindow):

    def __init__(self):
        super().__init__()

        # 创建并添加子界面
        self.homeInterface = QWidget(self)
        self.homeInterface.setObjectName("mainHomeInterface") # 设置 objectName
        self.subInterface = SubWidget(self)
        self.addSubInterface(self.homeInterface, FluentIcon.HOME, "Home")
        self.addSubInterface(self.subInterface, FluentIcon.APPLICATION, "子页面") # 添加 test_sub.py 的界面
        

        # 初始化窗口
        self.resize(1500, 900)
        self.setWindowIcon(QIcon(':/app/assets/icon.png'))
        self.setWindowTitle('PyQt-Fluent-Widgets')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = Window()
    w.show()

    # 2. 重新启用云母特效
    w.setMicaEffectEnabled(True)

    app.exec()
