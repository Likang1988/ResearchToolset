import sys
import math
from PySide6.QtWidgets import (QApplication, QMainWindow, QSplitter, QWidget,
                            QVBoxLayout, QHBoxLayout, QToolBar,
                            QTableView, QHeaderView, QAbstractItemView,
                            QStyledItemDelegate, QComboBox, QGraphicsView,
                            QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
                            QGraphicsLineItem, QGraphicsPolygonItem)
from PySide6.QtCore import Qt, QSize, QDate, QAbstractTableModel, QModelIndex, QRectF, QPointF
from PySide6.QtGui import QIcon, QBrush, QColor, QPen, QFont, QPainter, QPolygonF, QAction
from sqlalchemy.orm import sessionmaker
from app.models.database import get_engine
from app.models.project_task import ProjectTask, TaskStatus
from datetime import datetime
import os

class TaskTableModel(QAbstractTableModel):
    """任务表格数据模型"""
    COLUMNS = [
        ("任务编码", "id"),
        ("任务名称", "name"), 
        ("开始时间", "start_date"),
        ("结束时间", "end_date"),
        ("工期(天)", "duration"),
        ("进度(%)", "progress"),
        ("前置任务", "dependencies"),
        ("负责人", "assignee"),
        ("描述", "description")
    ]
    
    def __init__(self, session, project_id=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.project_id = project_id
        self.tasks = []
        self.expanded_tasks = set()  # 记录展开的任务ID
        self.visible_tasks = []  # 当前可见的任务列表
        self.load_data()
    
    def load_data(self):
        """从数据库加载任务数据"""
        self.beginResetModel()
        try:
            query = self.session.query(ProjectTask)
            if self.project_id:
                query = query.filter(ProjectTask.project_id == self.project_id)
            self.tasks = query.order_by(ProjectTask.level, ProjectTask.id).all()
            self.update_visible_tasks()
        except Exception as e:
            print(f"加载任务数据失败: {str(e)}")
            self.tasks = []
            self.visible_tasks = []
        finally:
            self.endResetModel()
    
    def update_visible_tasks(self):
        """更新可见任务列表"""
        self.visible_tasks = []
        for task in self.tasks:
            if task.parent_id is None:  # 顶层任务
                self.visible_tasks.append(task)
                if task.id in self.expanded_tasks:
                    self._add_child_tasks(task)
    
    def _add_child_tasks(self, parent_task):
        """递归添加子任务到可见列表"""
        for task in self.tasks:
            if task.parent_id == parent_task.id:
                self.visible_tasks.append(task)
                if task.id in self.expanded_tasks:
                    self._add_child_tasks(task)
    
    def toggle_task_expanded(self, index):
        """切换任务的展开/折叠状态"""
        if not index.isValid():
            return
        
        task = self.visible_tasks[index.row()]
        has_children = any(t.parent_id == task.id for t in self.tasks)
        
        if has_children:
            self.beginResetModel()
            if task.id in self.expanded_tasks:
                self.expanded_tasks.remove(task.id)
            else:
                self.expanded_tasks.add(task.id)
            self.update_visible_tasks()
            self.endResetModel()
    

        
    def load_data(self):
        """从数据库加载任务数据"""
        self.beginResetModel()
        try:
            query = self.session.query(ProjectTask)
            if self.project_id:
                query = query.filter(ProjectTask.project_id == self.project_id)
            self.tasks = query.order_by(ProjectTask.id).all()
        except Exception as e:
            print(f"加载任务数据失败: {str(e)}")
            self.tasks = []
        finally:
            self.endResetModel()
    
    def rowCount(self, parent=QModelIndex()):
        """返回行数"""
        return len(self.visible_tasks)
    
    def columnCount(self, parent=QModelIndex()):
        """返回列数"""
        return len(self.COLUMNS)
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """设置表头数据"""
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLUMNS[section][0]
        return super().headerData(section, orientation, role)
    
    def data(self, index, role=Qt.DisplayRole):
        """获取单元格数据"""
        if not index.isValid() or not (0 <= index.row() < len(self.visible_tasks)):
            return None
            
        task = self.visible_tasks[index.row()]
        col_name = self.COLUMNS[index.column()][1]
        
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if col_name == "name":
                indent = "    " * task.level
                has_children = any(t.parent_id == task.id for t in self.tasks)
                if has_children:
                    expand_icon = "▼" if task.id in self.expanded_tasks else "▶"
                    return f"{indent}{expand_icon} {task.name}"
                return f"{indent}{task.name}"
        
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if col_name == "duration":
                if task.start_date and task.end_date:
                    return (task.end_date - task.start_date).days + 1
                return 0
            elif col_name == "dependencies":
                deps = task.dependencies
                return ", ".join(str(dep) for dep in deps) if deps else ""
            return getattr(task, col_name, "")
            
        elif role == Qt.BackgroundRole:
            if task.status == TaskStatus.COMPLETED:
                return QBrush(QColor(220, 255, 220))
            elif task.status == TaskStatus.DELAYED:
                return QBrush(QColor(255, 220, 220))
            elif task.status == TaskStatus.IN_PROGRESS:
                return QBrush(QColor(220, 220, 255))
                
        return None
    
    def setData(self, index, value, role=Qt.EditRole):
        """设置单元格数据"""
        if not index.isValid() or role != Qt.EditRole:
            return False
            
        task = self.tasks[index.row()]
        col_name = self.COLUMNS[index.column()][1]
        
        try:
            if col_name == "start_date" or col_name == "end_date":
                if isinstance(value, str):
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                setattr(task, col_name, value)
            elif col_name == "progress":
                value = int(value)
                setattr(task, col_name, value)
                task.status = TaskStatus.COMPLETED if value == 100 else (
                    TaskStatus.IN_PROGRESS if value > 0 else TaskStatus.NOT_STARTED)
            elif col_name == "dependencies":
                deps = [int(dep.strip()) for dep in value.split(",") if dep.strip()]
                task.dependencies = deps
            else:
                setattr(task, col_name, value)
                
            self.session.commit()
            self.dataChanged.emit(index, index)
            return True
        except Exception as e:
            print(f"更新任务数据失败: {str(e)}")
            self.session.rollback()
            return False
    
    def flags(self, index):
        """设置单元格标志"""
        default_flags = super().flags(index)
        if index.isValid():
            return default_flags | Qt.ItemIsEditable
        return default_flags
    
    def add_task(self, task_data):
        """添加新任务"""
        row = len(self.tasks)
        self.beginInsertRows(QModelIndex(), row, row)
        try:
            task = ProjectTask(**task_data)
            self.session.add(task)
            self.session.commit()
            self.tasks.append(task)
            self.endInsertRows()
            return True
        except Exception as e:
            print(f"添加任务失败: {str(e)}")
            self.session.rollback()
            self.endInsertRows()
            return False
    
    def remove_task(self, row):
        """删除任务"""
        if 0 <= row < len(self.tasks):
            self.beginRemoveRows(QModelIndex(), row, row)
            try:
                task = self.tasks.pop(row)
                self.session.delete(task)
                self.session.commit()
                self.endRemoveRows()
                return True
            except Exception as e:
                print(f"删除任务失败: {str(e)}")
                self.session.rollback()
                self.endRemoveRows()
                return False
        return False

class StatusDelegate(QStyledItemDelegate):
    """状态列委托"""
    def createEditor(self, parent, option, index):
        if index.column() == 5:  # 进度列
            editor = QComboBox(parent)
            editor.addItems([str(i) for i in range(0, 101, 10)])
            return editor
        return super().createEditor(parent, option, index)

class ProjectProgressWidget(QWidget):
    """项目进度管理窗口"""
    def __init__(self, project, parent=None):
        super().__init__(parent=parent)
        self.project = project
        self.engine = get_engine()
        self.session = sessionmaker(bind=self.engine)()
        self.setup_ui()
        
    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        
        # 创建工具栏
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(24, 24))
        
        # 获取图标路径
        icons_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'icons'))

        # 增删任务
        self.add_action = QAction(QIcon(os.path.join(icons_dir, 'add.svg')), "添加", self)
        self.delete_action = QAction(QIcon(os.path.join(icons_dir, 'delete.svg')), "删除", self)

        # 撤销/恢复
        self.undo_action = QAction(QIcon(os.path.join(icons_dir, 'undo.svg')), "撤销", self)
        self.redo_action = QAction(QIcon(os.path.join(icons_dir, 'redo.svg')), "恢复", self)
        
        # 插入任务
        self.insert_above_action = QAction(QIcon(os.path.join(icons_dir, 'insert_above.svg')), "上方插入", self)
        self.insert_below_action = QAction(QIcon(os.path.join(icons_dir, 'insert_below.svg')), "下方插入", self)
        
        # 任务层级
        self.promote_action = QAction(QIcon(os.path.join(icons_dir, 'promote.svg')), "升级", self)
        self.demote_action = QAction(QIcon(os.path.join(icons_dir, 'demote.svg')), "降级", self)
        
        # 移动任务
        self.move_up_action = QAction(QIcon(os.path.join(icons_dir, 'move_up.svg')), "上移", self)
        self.move_down_action = QAction(QIcon(os.path.join(icons_dir, 'move_down.svg')), "下移", self)      
        
        # 展开/折叠
        self.expand_all_action = QAction(QIcon(os.path.join(icons_dir, 'expand.svg')), "全部展开", self)
        self.collapse_all_action = QAction(QIcon(os.path.join(icons_dir, 'collapse.svg')), "全部折叠", self)
        
        # 缩放
        self.zoom_in_action = QAction(QIcon(os.path.join(icons_dir, 'zoom_in.svg')), "放大", self)
        self.zoom_out_action = QAction(QIcon(os.path.join(icons_dir, 'zoom_out.svg')), "缩小", self)
        
        # 添加工具栏按钮
        toolbar.addAction(self.add_action)
        toolbar.addAction(self.delete_action)
        toolbar.addSeparator()
        
        toolbar.addAction(self.insert_above_action)
        toolbar.addAction(self.insert_below_action)
        toolbar.addSeparator()
        toolbar.addAction(self.promote_action)
        toolbar.addAction(self.demote_action)
        toolbar.addSeparator()
        toolbar.addAction(self.move_up_action)
        toolbar.addAction(self.move_down_action)
        toolbar.addSeparator()

        toolbar.addAction(self.expand_all_action)
        toolbar.addAction(self.collapse_all_action)
        toolbar.addSeparator()
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()
        toolbar.addAction(self.zoom_in_action)
        toolbar.addAction(self.zoom_out_action)
        
        self.main_layout.addWidget(toolbar)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 创建任务表格
        self.task_table = QTableView()
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.task_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.task_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.task_table.horizontalHeader().setStretchLastSection(True)
        self.task_table.setItemDelegate(StatusDelegate())
        
        # 创建任务数据模型
        self.task_model = TaskTableModel(self.session, self.project.id)
        self.task_table.setModel(self.task_model)
        
        # 连接任务表格的点击事件
        self.task_table.clicked.connect(self.on_task_clicked)
        
        splitter.addWidget(self.task_table)
        
        # 创建甘特图视图
        self.gantt_view = GanttView(self)
        splitter.addWidget(self.gantt_view)
        
        # 设置分割器初始比例
        splitter.setSizes([500, 500])
        
        self.main_layout.addWidget(splitter)
        
        # 连接工具栏按钮信号
        self.connect_actions()
        
    def connect_actions(self):
        """连接工具栏按钮信号"""
        self.insert_above_action.triggered.connect(self.insert_task_above)
        self.insert_below_action.triggered.connect(self.insert_task_below)
        self.promote_action.triggered.connect(self.promote_task)
        self.demote_action.triggered.connect(self.demote_task)
        self.move_up_action.triggered.connect(self.move_task_up)
        self.move_down_action.triggered.connect(self.move_task_down)
        self.delete_action.triggered.connect(self.delete_task)
        self.expand_all_action.triggered.connect(self.expand_all_tasks)
        self.collapse_all_action.triggered.connect(self.collapse_all_tasks)
        self.zoom_in_action.triggered.connect(self.gantt_view.zoom_in)
        self.zoom_out_action.triggered.connect(self.gantt_view.zoom_out)
    
    def on_undo(self):
        """撤销操作"""
        print("撤销操作")
        
    def on_redo(self):
        """恢复操作"""
        print("恢复操作")
        
    def insert_task(self, above=False):
        """插入任务"""
        print(f"在{'上方' if above else '下方'}插入任务")
        
    def promote_task(self):
        """升级任务层级"""
        print("升级任务层级")
        
    def demote_task(self):
        """降级任务层级"""
        print("降级任务层级")
        
    def move_task_up(self):
        """上移任务"""
        print("上移任务")
        
    def move_task_down(self):
        """下移任务"""
        print("下移任务")
        
    def delete_task(self):
        """删除任务"""
        print("删除任务")
        
    def expand_all(self):
        """展开所有任务"""
        print("展开所有任务")
        
    def collapse_all(self):
        """折叠所有任务"""
        print("折叠所有任务")
        
    def zoom_in(self):
        """放大视图"""
        print("放大视图")
        
    def zoom_out(self):
        """缩小视图"""
        print("缩小视图")
        
    def on_task_clicked(self, index):
        """处理任务点击事件"""
        if index.column() == 1:  # 任务名称列
            self.task_model.toggle_task_expanded(index)
            self.gantt_view.update_view()
        
    def insert_task_above(self):
        """在选中任务上方插入新任务"""
        index = self.task_table.currentIndex()
        if index.isValid():
            task = self.task_model.visible_tasks[index.row()]
            new_task = {
                'project_id': self.project.id,
                'name': '新任务',
                'level': task.level,
                'parent_id': task.parent_id
            }
            self.task_model.add_task(new_task)
            
    def insert_task_below(self):
        """在选中任务下方插入新任务"""
        index = self.task_table.currentIndex()
        if index.isValid():
            task = self.task_model.visible_tasks[index.row()]
            new_task = {
                'project_id': self.project.id,
                'name': '新任务',
                'level': task.level,
                'parent_id': task.parent_id
            }
            self.task_model.add_task(new_task)
            
    def promote_task(self):
        """提升任务层级"""
        index = self.task_table.currentIndex()
        if index.isValid():
            task = self.task_model.visible_tasks[index.row()]
            if task.level > 0:
                parent_task = next((t for t in self.task_model.tasks if t.id == task.parent_id), None)
                if parent_task:
                    task.parent_id = parent_task.parent_id
                    task.level -= 1
                    self.task_model.session.commit()
                    self.task_model.load_data()
                    
    def demote_task(self):
        """降低任务层级"""
        index = self.task_table.currentIndex()
        if index.isValid():
            row = index.row()
            if row > 0:
                task = self.task_model.visible_tasks[row]
                prev_task = self.task_model.visible_tasks[row - 1]
                if task.level <= prev_task.level:
                    task.parent_id = prev_task.id
                    task.level = prev_task.level + 1
                    self.task_model.session.commit()
                    self.task_model.load_data()
                    
    def move_task_up(self):
        """上移任务"""
        index = self.task_table.currentIndex()
        if index.isValid() and index.row() > 0:
            self.task_model.move_task(index.row(), index.row() - 1)
            
    def move_task_down(self):
        """下移任务"""
        index = self.task_table.currentIndex()
        if index.isValid() and index.row() < len(self.task_model.visible_tasks) - 1:
            self.task_model.move_task(index.row(), index.row() + 1)
            
    def delete_task(self):
        """删除任务"""
        index = self.task_table.currentIndex()
        if index.isValid():
            self.task_model.remove_task(index.row())
            
    def expand_all_tasks(self):
        """展开所有任务"""
        self.task_model.expanded_tasks = set(task.id for task in self.task_model.tasks)
        self.task_model.load_data()
        
    def collapse_all_tasks(self):
        """折叠所有任务"""
        self.task_model.expanded_tasks.clear()
        self.task_model.load_data()

class GanttView(QGraphicsView):
    """甘特图视图"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        # 时间轴参数
        self.time_scale = "day"  # day/week/month
        self.start_date = QDate.currentDate()
        self.end_date = self.start_date.addDays(30)
        self.day_width = 30  # 每天的像素宽度
        self.row_height = 30  # 每行高度
        self.zoom_factor = 1.0  # 缩放因子
        
        # 拖拽相关
        self.dragging_item = None
        self.drag_start_pos = None
        self.original_dates = None
        
        # 初始化UI
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        self.setStyleSheet("background-color: white;")
        self.setMouseTracking(True)  # 启用鼠标追踪
        self.draw_timeline()
        
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            pos = self.mapToScene(event.pos())
            item = self.scene.itemAt(pos, self.transform())
            if isinstance(item, QGraphicsRectItem) and item.data(0):
                self.dragging_item = item
                self.drag_start_pos = pos
                task_id = item.data(0)
                task = next((t for t in self.parent().task_model.tasks if t.id == task_id), None)
                if task:
                    self.original_dates = (task.start_date, task.end_date)
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.dragging_item and self.drag_start_pos:
            pos = self.mapToScene(event.pos())
            delta_x = pos.x() - self.drag_start_pos.x()
            days_delta = int(delta_x / (self.day_width * self.zoom_factor))
            
            if days_delta != 0:
                task_id = self.dragging_item.data(0)
                task = next((t for t in self.parent().task_model.tasks if t.id == task_id), None)
                if task:
                    new_start = self.original_dates[0] + datetime.timedelta(days=days_delta)
                    new_end = self.original_dates[1] + datetime.timedelta(days=days_delta)
                    task.start_date = new_start
                    task.end_date = new_end
                    self.parent().task_model.session.commit()
                    self.update_view()
                    self.drag_start_pos = pos
        super().mouseMoveEvent(event)
        
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self.dragging_item = None
            self.drag_start_pos = None
            self.original_dates = None
        super().mouseReleaseEvent(event)
        
    def wheelEvent(self, event):
        """鼠标滚轮事件"""
        if event.modifiers() & Qt.ControlModifier:
            # 缩放
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)
            
    def zoom_in(self):
        """放大"""
        self.zoom_factor *= 1.2
        self.update_view()
        
    def zoom_out(self):
        """缩小"""
        self.zoom_factor /= 1.2
        self.update_view()
        
    def set_time_scale(self, scale):
        """设置时间粒度"""
        self.time_scale = scale
        self.update_view()
        
    def update_view(self):
        """更新视图"""
        self.scene.clear()
        self.draw_timeline()
        if hasattr(self.parent(), 'task_model'):
            self.draw_tasks(self.parent().task_model.visible_tasks)
            self.draw_dependencies(self.parent().task_model.visible_tasks)
        
    def draw_timeline(self):
        """绘制时间轴"""
        self.scene.clear()
        
        # 计算时间范围
        days = self.start_date.daysTo(self.end_date) + 1
        total_width = days * self.day_width
        
        # 绘制时间轴标尺
        self.draw_time_ruler(total_width, days)
        
        # 绘制网格线
        self.draw_grid_lines(total_width, days)
        
        # 设置场景大小
        self.scene.setSceneRect(0, 0, total_width + 100, 1000)
        
    def draw_time_ruler(self, total_width, days):
        """绘制时间标尺"""
        # 主时间轴
        ruler = QGraphicsRectItem(0, 0, total_width, 30)
        ruler.setBrush(QBrush(QColor(240, 240, 240)))
        ruler.setPen(QPen(Qt.NoPen))
        self.scene.addItem(ruler)
        
        # 时间刻度
        font = QFont("Arial", 8)
        current_date = self.start_date
        for i in range(days + 1):
            x = i * self.day_width
            line = QGraphicsLineItem(x, 0, x, 30)
            line.setPen(QPen(QColor(200, 200, 200)))
            self.scene.addItem(line)
            
            # 每天/每周/每月显示日期标签
            if self.time_scale == "day" or \
               (self.time_scale == "week" and current_date.dayOfWeek() == 1) or \
               (self.time_scale == "month" and current_date.day() == 1):
                text = QGraphicsTextItem(current_date.toString("MM-dd"))
                text.setFont(font)
                text.setPos(x + 2, 5)
                self.scene.addItem(text)
                
            current_date = current_date.addDays(1)
            
    def draw_grid_lines(self, total_width, days):
        """绘制网格线"""
        # 垂直网格线
        for i in range(days + 1):
            x = i * self.day_width
            line = QGraphicsLineItem(x, 30, x, 1000)
            line.setPen(QPen(QColor(230, 230, 230)))
            self.scene.addItem(line)
            
        # 水平网格线
        for i in range(50):  # 假设最多50行
            y = 30 + i * self.row_height
            line = QGraphicsLineItem(0, y, total_width, y)
            line.setPen(QPen(QColor(230, 230, 230)))
            self.scene.addItem(line)
            
    def draw_tasks(self, tasks):
        """绘制任务条"""
        for i, task in enumerate(tasks):
            if not task.start_date or not task.end_date:
                continue
                
            # 计算任务位置和大小
            start_offset = self.start_date.daysTo(QDate.fromString(str(task.start_date), "yyyy-MM-dd"))
            duration = (task.end_date - task.start_date).days + 1
            x = start_offset * self.day_width * self.zoom_factor
            y = 30 + i * self.row_height + 5
            width = duration * self.day_width * self.zoom_factor
            height = self.row_height - 10
            
            # 绘制任务条
            task_rect = QGraphicsRectItem(x, y, width, height)
            task_rect.setData(0, task.id)  # 存储任务ID
            
            # 根据状态设置颜色
            if task.status == TaskStatus.COMPLETED:
                color = QColor(100, 200, 100)
            elif task.status == TaskStatus.IN_PROGRESS:
                color = QColor(100, 100, 200)
            elif task.status == TaskStatus.DELAYED:
                color = QColor(200, 100, 100)
            else:
                color = QColor(200, 200, 200)
                
            task_rect.setBrush(QBrush(color))
            task_rect.setPen(QPen(QColor(0, 0, 0), 1))
            task_rect.setAcceptHoverEvents(True)  # 启用鼠标悬停事件
            task_rect.setCursor(Qt.SizeHorCursor)  # 设置鼠标指针样式
            self.scene.addItem(task_rect)
            
            # 绘制任务名称
            indent = "    " * task.level
            task_text = QGraphicsTextItem(indent + task.name)
            task_text.setPos(x + 5, y + 5)
            task_text.setDefaultTextColor(QColor(0, 0, 0))
            self.scene.addItem(task_text)
            
            # 绘制进度条
            if task.progress > 0:
                progress_width = width * task.progress / 100
                progress_rect = QGraphicsRectItem(x, y + height - 5, progress_width, 3)
                progress_rect.setBrush(QBrush(QColor(0, 0, 0)))
                progress_rect.setPen(QPen(Qt.NoPen))
                self.scene.addItem(progress_rect)
                
    def draw_dependencies(self, tasks):
        """绘制任务依赖关系"""
        for i, task in enumerate(tasks):
            if not task.dependencies:
                continue
                
            deps = json.loads(task.dependencies)
            for dep_id in deps:
                # 查找依赖任务
                dep_task = next((t for t in tasks if t.id == dep_id), None)
                if not dep_task or not dep_task.end_date or not task.start_date:
                    continue
                    
                # 计算箭头位置
                dep_index = tasks.index(dep_task)
                start_x = self.start_date.daysTo(QDate.fromString(str(dep_task.end_date), "yyyy-MM-dd")) * self.day_width * self.zoom_factor
                start_y = 30 + dep_index * self.row_height + self.row_height / 2
                end_x = self.start_date.daysTo(QDate.fromString(str(task.start_date), "yyyy-MM-dd")) * self.day_width * self.zoom_factor
                end_y = 30 + i * self.row_height + self.row_height / 2
                
                # 绘制箭头线
                line = QGraphicsLineItem(start_x, start_y, end_x, end_y)
                line.setPen(QPen(QColor(100, 100, 100), 1, Qt.DashLine))
                self.scene.addItem(line)
                
                # 绘制箭头
                arrow_size = 5
                angle = line.line().angle()
                arrow_p1 = line.line().p2() - QPointF(
                    arrow_size * 0.5 * (1 + math.cos(math.radians(angle + 30))),
                    arrow_size * 0.5 * (1 - math.sin(math.radians(angle + 30)))
                )
                arrow_p2 = line.line().p2() - QPointF(
                    arrow_size * 0.5 * (1 + math.cos(math.radians(angle - 30))),
                    arrow_size * 0.5 * (1 - math.sin(math.radians(angle - 30)))
                )
                
                arrow = QGraphicsPolygonItem(
                    QPolygonF([line.line().p2(), arrow_p1, arrow_p2]))
                arrow.setBrush(QBrush(QColor(100, 100, 100)))
                arrow.setPen(QPen(Qt.NoPen))
                self.scene.addItem(arrow)

class TaskTableView(QTableView):
    """任务表格视图"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.setStyleSheet("""
            QTableView {
                border: 1px solid #ddd;
                alternate-background-color: #f9f9f9;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: 1px solid #ddd;
            }
        """)

class ProjectProgressWindow(QMainWindow):
    """项目进度主窗口"""
    def __init__(self, project_id=None):
        super().__init__()
        self.project_id = project_id
        self.session = None
        self.init_db()
        self.init_ui()
        
    def init_db(self):
        """初始化数据库连接"""
        engine = get_engine()
        Session = sessionmaker(bind=engine)
        self.session = Session()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("项目进度管理")
        self.setMinimumSize(1000, 600)
        
        # 创建工具栏
        self.create_toolbar()
        
        # 主内容区域
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        
        # 分割器 - 左侧任务列表和右侧甘特图
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧任务列表
        self.task_table = TaskTableView()
        self.task_model = TaskTableModel(self.session, self.project_id)
        self.task_table.setModel(self.task_model)
        
        # 设置委托
        self.task_table.setItemDelegateForColumn(5, StatusDelegate())  # 进度列
        
        splitter.addWidget(self.task_table)
        
        # 右侧甘特图
        self.gantt_view = GanttView()
        splitter.addWidget(self.gantt_view)
        
        # 设置分割器初始比例
        splitter.setSizes([300, 700])
        
        main_layout.addWidget(splitter)
        self.setCentralWidget(main_widget)
        
        # 连接数据变化信号
        self.task_model.dataChanged.connect(self.update_gantt_view)
        
        # 初始绘制甘特图
        self.update_gantt_view()
        
    def update_gantt_view(self):
        """更新甘特图视图"""
        self.gantt_view.draw_tasks(self.task_model.tasks)
        self.gantt_view.draw_dependencies(self.task_model.tasks)
        

    


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProjectProgressWindow()
    window.show()
    sys.exit(app.exec_())

