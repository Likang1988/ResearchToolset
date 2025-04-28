from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout)
from PySide6.QtCore import QUrl, QFileInfo
from qfluentwidgets import FluentWindow, FluentIcon
from qframelesswindow.webengine import FramelessWebEngineView
import sys
import os


class Widget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("homeInterface")

        # 1. 将 QWebEngineView 替换成 FramelessWebEngineView
        self.webView = FramelessWebEngineView(self)
        # Construct the absolute path to gantt.html
        current_dir = os.path.dirname(os.path.abspath(__file__))
        gantt_path = os.path.join(current_dir, '..', 'views', 'projecting_interface', 'jQueryGantt', 'gantt.html')
        gantt_path = os.path.normpath(gantt_path)
        
        # Read HTML content and set base URL
        gantt_file_info = QFileInfo(gantt_path)
        gantt_dir = gantt_file_info.absolutePath()
        try:
            with open(gantt_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            self.webView.setHtml(html_content, baseUrl=QUrl.fromLocalFile(gantt_dir + '/'))
        except Exception as e:
            print(f"Error loading gantt.html: {e}")
            # Fallback or error handling
            self.webView.load(QUrl("https://example.com/error")) # Load an error page or similar

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
        self.resize(1500, 900)
        #self.setWindowIcon(QIcon(':/qfluentwidgets/images/logo.png'))
        self.setWindowTitle('PyQt-Fluent-Widgets')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = Window()
    w.show()

    # 2. 重新启用云母特效
    w.setMicaEffectEnabled(True)

    app.exec()
