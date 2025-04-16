from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import NavigationInterface, NavigationItemPosition
from qframelesswindow.webengine import FramelessWindow, FramelessWebEngineView
from app.utils.ui_utils import UIUtils
import os

class ProjectProgressWidget(QWidget):
    """项目进度管理组件，集成jQueryGantt甘特图"""
    
    # 定义信号
    progress_updated = Signal()
    """项目进度管理组件，集成jQueryGantt甘特图"""
    
    def __init__(self, engine=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setObjectName("projectProgressWidget")
        self.setup_ui()
        
    def setup_ui(self):
        """初始化界面"""
        self.setStyleSheet("background: transparent;")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建WebEngineView并设置样式
        self.web_view = FramelessWebEngineView(self)
        
        self.layout.addWidget(self.web_view)
        
        # 加载本地甘特图资源
        self.load_gantt()
    
    def load_gantt(self):
        """加载本地jQueryGantt资源"""
        try:
            # 获取绝对路径并确保路径存在
            gantt_dir = os.path.dirname(os.path.abspath(__file__))
            gantt_path = os.path.join(gantt_dir, "jQueryGantt", "gantt.html")
            
            if not os.path.exists(gantt_path):
                raise FileNotFoundError(f"Gantt file not found at {gantt_path}")
            
            # 转换为file:// URL格式并设置基础URL
            gantt_url = QUrl.fromLocalFile(gantt_path)
            self.web_view.setUrl(gantt_url)
            
            # 设置页面加载完成后的回调
            self.web_view.loadFinished.connect(self.on_gantt_loaded)
        except Exception as e:
            print(f"Error loading Gantt: {str(e)}")
    
    def on_gantt_loaded(self, success):
        """甘特图加载完成回调"""
        if success:
            print("jQueryGantt loaded successfully")
            # 初始化甘特图数据
            self.init_gantt_data()
        else:
            print("Failed to load jQueryGantt")
    
    def init_gantt_data(self):
        """初始化甘特图数据"""
        # 初始化已在 gantt.html 中完成 (ge = new GanttMaster(); ge.init(...))
        # 如果需要加载初始数据，可以在这里调用 update_progress_data
        # 例如，加载示例数据:
        # demo_data = self.get_demo_project_data() # 需要实现获取示例数据的方法
        # self.update_progress_data(demo_data)
        print("Gantt initialized via HTML. Ready to load data.")
        pass # 无需在此执行额外的JS初始化

    def update_progress_data(self, data):
        """更新甘特图数据"""
        # 确保传入的 data 是符合 jQueryGantt (GanttMaster) 期望的 project JSON 格式
        # 格式类似于 gantt.html 中的 getDemoProject() 返回的结构
        # 主要包含 'tasks', 'resources', 'roles', 'canWrite' 等键
        update_script = f"""
        // 使用 ge 对象加载项目数据
        var projectData = {data};
        if (typeof ge !== 'undefined' && ge.loadProject) {{
            ge.loadProject(projectData);
            ge.redraw(); // 可选：强制重绘
            console.log("Project data loaded via Python.");
        }} else {{
            console.error("Gantt object 'ge' not found or loadProject method missing.");
        }}
        """
        self.web_view.page().runJavaScript(update_script)