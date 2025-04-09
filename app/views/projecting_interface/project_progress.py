from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                              QDateEdit, QTextEdit, QSpinBox, QLabel, QMenu,
                              QGraphicsItem, QGraphicsRectItem, QDialog,
                              QListWidget, QPushButton, QInputDialog,
                              QGraphicsView, QTreeWidget, QTreeWidgetItem)
from PySide6.QtCore import Qt, QDate, QRectF, QPoint, Signal
from PySide6.QtGui import (QPainter, QColor, QLinearGradient,
                          QMouseEvent, QContextMenuEvent, QBrush, QPen,
                          QCursor)
from PySide6.QtCharts import (QChart, QChartView, QBarCategoryAxis,
                             QValueAxis, QBarSet, QBarSeries, QLineSeries)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWebSockets import QWebSocket
from qfluentwidgets import TitleLabel, PrimaryPushButton, FluentIcon, InfoBar, Dialog, LineEdit
from app.utils.ui_utils import UIUtils
from ...models.database import Project, Base, get_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum as SQLEnum
from enum import Enum

class TaskStatus(Enum):
    NOT_STARTED = "未开始"
    IN_PROGRESS = "进行中"
    COMPLETED = "已完成"
    DELAYED = "已延期"

class ProjectTask(Base):
    __tablename__ = 'project_tasks'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    name = Column(String(100), nullable=False)  # 任务名称
    description = Column(String(500))  # 任务描述
    start_date = Column(Date)  # 开始日期
    end_date = Column(Date)  # 结束日期
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.NOT_STARTED)  # 任务状态
    progress = Column(Integer, default=0)  # 进度百分比
    dependencies = Column(String)  # 依赖任务ID列表(JSON格式)
    assignee = Column(String(50))  # 负责人
    phase = Column(String(20))  # 研究阶段



class GanttBarItem(QGraphicsRectItem):
    """甘特图任务条图形项"""
    def __init__(self, task_id, rect, parent=None):
        super().__init__(rect, parent)
        self.task_id = task_id
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
    def mousePressEvent(self, event):
        self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)
        
    def hoverEnterEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)

class GanttChartView(QGraphicsView):
    """自定义甘特图视图"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        
    def wheelEvent(self, event):
        """处理滚轮缩放事件"""
        zoom_factor = 1.2
        if event.angleDelta().y() > 0:
            self.scale(zoom_factor, zoom_factor)
        else:
            self.scale(1.0 / zoom_factor, 1.0 / zoom_factor)

class TeamManagementDialog(QDialog):
    """团队管理对话框"""
    def __init__(self, project_id, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.setWindowTitle("团队管理")
        self.setup_ui()
        self.load_team_members()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.member_list = QListWidget()
        layout.addWidget(self.member_list)
        
        button_layout = QHBoxLayout()
        add_btn = QPushButton("添加成员")
        remove_btn = QPushButton("移除成员")
        
        add_btn.clicked.connect(self.add_member)
        remove_btn.clicked.connect(self.remove_member)
        
        button_layout.addWidget(add_btn)
        button_layout.addWidget(remove_btn)
        layout.addLayout(button_layout)
        
    def load_team_members(self):
        """加载团队成员"""
        Session = sessionmaker(bind=get_engine())
        session = Session()
        try:
            project = session.query(Project).get(self.project_id)
            self.member_list.clear()
            for member in project.team_members.split(','):
                if member.strip():
                    self.member_list.addItem(member.strip())
        finally:
            session.close()
            
    def add_member(self):
        """添加新成员"""
        name, ok = QInputDialog.getText(
            self, "添加成员", "输入成员姓名:")
        if ok and name:
            self.member_list.addItem(name)
            
    def remove_member(self):
        """移除选中成员"""
        if self.member_list.currentItem():
            self.member_list.takeItem(self.member_list.currentRow())
            
    def get_team_members(self):
        """获取团队成员列表"""
        return [self.member_list.item(i).text()
                for i in range(self.member_list.count())]

class ProjectProgressWidget(QWidget):
    taskUpdated = Signal()
    taskDragged = Signal(int, QDate, QDate)  # task_id, new_start, new_end
    
    def __init__(self, project, parent=None):
        super().__init__(parent=parent)
        self.project = project
        self.dragging_task = None
        self.drag_start_pos = None
        self.network_manager = QNetworkAccessManager()
        self.websocket = QWebSocket()
        self.setup_ui()
        self.load_tasks()
        self.setup_connections()
    
    def setup_ui(self):
        """设置用户界面"""
        self.main_layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        # 时间范围选择
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["天视图", "周视图", "月视图"])
        toolbar.addWidget(QLabel("显示:"))
        toolbar.addWidget(self.timeframe_combo)
        
        # 团队按钮
        team_btn = UIUtils.create_action_button("团队", FluentIcon.PEOPLE)
        team_btn.clicked.connect(self.manage_team)
        toolbar.addWidget(team_btn)
        
        # 导出按钮
        export_btn = UIUtils.create_action_button("导出", FluentIcon.SAVE)
        export_btn.clicked.connect(self.show_export_menu)
        toolbar.addWidget(export_btn)
        
        # 协作按钮
        self.collab_btn = UIUtils.create_action_button("协作", FluentIcon.SHARE)
        self.collab_btn.setCheckable(True)
        self.collab_btn.clicked.connect(self.toggle_collaboration)
        toolbar.addWidget(self.collab_btn)
        
        self.main_layout.addLayout(toolbar)
        
        # 甘特图视图
        self.chart = QChart()
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        self.chart.setTheme(QChart.ChartThemeLight)
        
        self.chart_view = GanttChartView(self)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setMouseTracking(True)
        
        # 任务树控件
        self.task_tree = QTreeWidget()
        self.task_tree.setHeaderLabels(["任务名称", "描述", "开始日期", "结束日期", "状态", "负责人", "进度"])
        self.task_tree.setColumnWidth(0, 200)
        self.main_layout.addWidget(self.task_tree)
        
        # 添加任务按钮
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加任务")
        add_child_btn = QPushButton("添加子任务")
        delete_btn = QPushButton("删除任务")
        
        add_btn.clicked.connect(self.add_task)
        add_child_btn.clicked.connect(self.add_child_task)
        delete_btn.clicked.connect(self.delete_task)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(add_child_btn)
        btn_layout.addWidget(delete_btn)
        self.main_layout.addLayout(btn_layout)
        
        self.main_layout.addWidget(self.chart_view)
        
        # 状态栏
        self.status_label = QLabel()
        self.main_layout.addWidget(self.status_label)
    
    def setup_connections(self):
        """设置信号槽连接"""
        self.timeframe_combo.currentTextChanged.connect(self.update_chart)
        self.websocket.connected.connect(self.on_websocket_connected)
        self.websocket.textMessageReceived.connect(self.on_websocket_message)
        self.taskUpdated.connect(self.update_chart)
        
    def manage_team(self):
        """管理团队成员"""
        dialog = TeamManagementDialog(self.project.id, self)
        if dialog.exec_() == QDialog.Accepted:
            Session = sessionmaker(bind=get_engine())
            session = Session()
            try:
                project = session.query(Project).get(self.project.id)
                project.team_members = ','.join(dialog.get_team_members())
                session.commit()
            finally:
                session.close()
                
    def toggle_collaboration(self):
        """切换协作模式"""
        if self.collab_btn.isChecked():
            self.websocket.open(QUrl("ws://localhost:8080/collab"))
            self.collab_btn.setText("协作中")
            self.collab_btn.setIcon(FluentIcon.CHECKBOX)
        else:
            self.websocket.close()
            self.collab_btn.setText("协作")
            self.collab_btn.setIcon(FluentIcon.SHARE)
            
    def on_websocket_connected(self):
        """WebSocket连接成功"""
        UIUtils.show_success(self, "成功", "已连接到协作服务器")
        
    def on_websocket_message(self, message):
        """接收WebSocket消息"""
        data = json.loads(message)
        if data['type'] == 'task_update':
            self.load_tasks()
            self.update_chart()
            
    def send_task_update(self, task_id):
        """发送任务更新到协作服务器"""
        if self.websocket.state() == QAbstractSocket.ConnectedState:
            message = {
                'type': 'task_update',
                'task_id': task_id,
                'project_id': self.project.id
            }
            self.websocket.sendTextMessage(json.dumps(message))

    def update_chart(self):
        """更新甘特图显示"""
        self.chart.removeAllSeries()
        
        # 创建任务条系列
        bar_set = QBarSet("任务进度")
        categories = []
        
        # 添加任务条
        for task in self.tasks:
            duration = (task.end_date - task.start_date).days
            bar_set.append(duration)
            bar_set.setLabel(task.name)
            categories.append(task.name)
            
            # 添加进度条
            progress_duration = duration * task.progress / 100
            if progress_duration > 0:
                progress_set = QBarSet("")
                progress_set.append(progress_duration)
                progress_set.setLabel(f"{task.progress}%")
                self.chart.addSeries(progress_set)
        
        # 添加依赖关系线
        for task in self.tasks:
            if task.dependencies:
                line_series = QLineSeries()
                for dep_id in task.dependencies:
                    dep_task = next(t for t in self.tasks if t.id == dep_id)
                    line_series.append(dep_task.end_date.toJulianDay(),
                                      self.tasks.index(dep_task) + 0.5)
                    line_series.append(task.start_date.toJulianDay(),
                                     self.tasks.index(task) + 0.5)
                self.chart.addSeries(line_series)
        
        # 设置图表轴
        axis_x = QValueAxis()
        axis_x.setRange(self.project.start_date.toJulianDay(),
                       self.project.end_date.toJulianDay())
        axis_x.setFormat("yyyy-MM-dd")
        self.chart.addAxis(axis_x, Qt.AlignBottom)
        
        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        self.chart.addAxis(axis_y, Qt.AlignLeft)
        
    def show_export_menu(self):
        """显示导出菜单"""
        menu = QMenu(self)
        
        png_action = menu.addAction("导出为PNG")
        pdf_action = menu.addAction("导出为PDF")
        excel_action = menu.addAction("导出为Excel")
        
        action = menu.exec_(QCursor.pos())
        if action == png_action:
            self.export_to_png()
        elif action == pdf_action:
            self.export_to_pdf()
        elif action == excel_action:
            self.export_to_excel()
            
    def export_to_png(self):
        """导出为PNG图片"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出PNG", "", "PNG图片 (*.png)")
        if file_path:
            pixmap = self.chart_view.grab()
            pixmap.save(file_path, "PNG")
            
    def export_to_pdf(self):
        """导出为PDF文档"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出PDF", "", "PDF文档 (*.pdf)")
        if file_path:
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(file_path)
            
            painter = QPainter(printer)
            self.chart_view.render(painter)
            painter.end()
            
    def export_to_excel(self):
        """导出为Excel文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出Excel", "", "Excel文件 (*.xlsx)")
        if file_path:
            df = pd.DataFrame([{
                '任务名称': task.name,
                '开始日期': task.start_date.toString(Qt.ISODate),
                '结束日期': task.end_date.toString(Qt.ISODate),
                '进度': f"{task.progress}%",
                '状态': task.status.value,
                '负责人': task.assignee
            } for task in self.tasks])
            
            df.to_excel(file_path, index=False)

    def load_tasks(self):
        Session = sessionmaker(bind=get_engine())
        session = Session()
        
        try:
            tasks = session.query(ProjectTask).filter(
                ProjectTask.project_id == self.project.id
            ).all()
            
            self.task_tree.clear()
            for task in tasks:
                item = QTreeWidgetItem()
                item.setText(0, task.name)
                item.setText(1, task.description)
                item.setText(2, str(task.start_date))
                item.setText(3, str(task.end_date))
                item.setText(4, task.status.value)
                item.setText(5, task.assignee)
                item.setText(6, f"{task.progress}%")
                self.task_tree.addTopLevelItem(item)
        finally:
            session.close()
    
    def add_task(self):
            
        # 添加新行
        item = QTreeWidgetItem()
        item.setText(0, "新任务")
        item.setText(1, "")
        item.setText(2, QDate.currentDate().toString(Qt.ISODate))
        item.setText(3, QDate.currentDate().toString(Qt.ISODate))
        item.setText(4, TaskStatus.NOT_STARTED.value)
        item.setText(5, "")
        item.setText(6, "0%")
        
        # 设置可编辑
        for i in range(7):
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            
        self.task_tree.addTopLevelItem(item)
        self.task_tree.editItem(item, 0)
    
    def add_child_task(self):
        selected_items = self.task_tree.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择父级任务")
            return
            
        # 添加子级任务
        parent_item = selected_items[0]
        child_item = QTreeWidgetItem(parent_item)
        child_item.setText(0, "子任务")
        child_item.setText(1, "")
        child_item.setText(2, QDate.currentDate().toString(Qt.ISODate))
        child_item.setText(3, QDate.currentDate().toString(Qt.ISODate))
        child_item.setText(4, TaskStatus.NOT_STARTED.value)
        child_item.setText(5, "")
        child_item.setText(6, "0%")
        
        # 设置可编辑
        for i in range(7):
            child_item.setFlags(child_item.flags() | Qt.ItemIsEditable)
            
        self.task_tree.expandItem(parent_item)
        self.task_tree.editItem(child_item, 0)
    
    def delete_task(self):
        selected_items = self.task_tree.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择要删除的任务")
            return
        
        task_name = selected_items[0].text(0)
        
        Session = sessionmaker(bind=get_engine())
        session = Session()
        
        try:
            task = session.query(ProjectTask).filter(
                ProjectTask.project_id == self.project_combo.currentData(),
                ProjectTask.name == task_name
            ).first()
            
            if task:
                session.delete(task)
                session.commit()
                self.load_tasks()
                UIUtils.show_success(self, "成功", "任务删除成功")
        finally:
            session.close()