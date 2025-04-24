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

        self.webView = FramelessWebEngineView(self)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        gantt_path = os.path.join(current_dir, '..', 'views', 'projecting_interface', 'jQueryGantt', 'gantt.html')
        gantt_path = os.path.normpath(gantt_path)
        
        gantt_file_info = QFileInfo(gantt_path)
        gantt_dir = gantt_file_info.absolutePath()
        try:
            with open(gantt_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            self.webView.setHtml(html_content, baseUrl=QUrl.fromLocalFile(gantt_dir + '/'))
        except Exception as e:
            print(f"Error loading gantt.html: {e}")
            self.webView.load(QUrl("https://example.com/error")) # Load an error page or similar

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(0, 48, 0, 0)
        self.vBoxLayout.addWidget(self.webView)
