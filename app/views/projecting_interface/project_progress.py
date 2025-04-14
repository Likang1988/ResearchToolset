import sys
import math
from PySide6.QtWidgets import (QApplication, QMainWindow, QSplitter, QWidget,
                            QVBoxLayout, QHBoxLayout, QToolBar,
                            QTreeView, QHeaderView, QAbstractItemView,
                            QStyledItemDelegate, QComboBox, QGraphicsView,
                            QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
                            QGraphicsLineItem, QGraphicsPolygonItem)
from PySide6.QtCore import Qt, QSize, QDate, QAbstractTableModel, QModelIndex, QRectF, QPointF
from PySide6.QtGui import QIcon, QBrush, QColor, QPen, QFont, QPainter, QPolygonF, QAction
from sqlalchemy.orm import sessionmaker
from app.models.database import get_engine
from app.models.project_task import ProjectTask, TaskStatus
from ...utils.ui_utils import UIUtils
from datetime import datetime, date
import os

# 确保从正确的相对路径导入
from ...components.status_color_delegate import StatusColorDelegate

class TaskTableModel(QAbstractTableModel):
    """任务表格数据模型"""
    # 交换 "状态" 和 "ID" 列的位置，ID 列现在是第 0 列
    COLUMNS = [
        ("ID", "id"),             # 第 0 列，用于显示树形结构和层级编码
        ("状态", "status_icon"),  # 第 1 列
        ("任务名称", "name"),     # 第 2 列
        ("开始时间", "start_date"),
        ("结束时间", "end_date"),
        ("工期(天)", "duration"),
        ("进度(%)", "progress"),
        ("前置任务", "dependencies"),
        ("负责人", "assignee"),
        ("描述", "description")
    ]

    # 定义状态到颜色的映射 (也可以从 TaskStatus.color 获取)
    STATUS_COLOR_MAP = {
        TaskStatus.NOT_STARTED: QColor("#FFD700"), # Gold
        TaskStatus.IN_PROGRESS: QColor("#32CD32"), # LimeGreen
        TaskStatus.COMPLETED: QColor("#1E90FF"),   # DodgerBlue
        TaskStatus.PAUSED: QColor("#FF4500"),      # OrangeRed
        TaskStatus.CANCELLED: QColor("#9370DB"),   # MediumPurple
        TaskStatus.CLOSED: QColor("#A9A9A9")       # DarkGray
    }

    def __init__(self, session, project_id=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.project_id = project_id
        self.tasks = []
        self.expanded_tasks = set()  # 记录展开的任务ID
        self.visible_tasks = []  # 当前可见的任务列表
        self.task_map = {} # 用于快速查找任务
        self.hierarchical_codes = {} # 缓存计算出的层级编码
        self.load_data()

    def _get_task_by_id(self, task_id):
        """通过ID快速查找任务"""
        return self.task_map.get(task_id)

    def _calculate_hierarchical_codes(self):
        """计算所有任务的层级编码"""
        self.hierarchical_codes.clear()
        root_tasks = [task for task in self.tasks if task.parent_id is None]
        root_tasks.sort(key=lambda t: t.id) # 确保顶层任务按某种顺序排列，例如ID

        def assign_codes(tasks, prefix=""):
            tasks.sort(key=lambda t: t.id) # 确保同级任务按ID排序
            for i, task in enumerate(tasks):
                current_code = f"{prefix}{i + 1}"
                self.hierarchical_codes[task.id] = current_code
                children = [t for t in self.tasks if t.parent_id == task.id]
                if children:
                    assign_codes(children, prefix=f"{current_code}.")

        assign_codes(root_tasks)

    def load_data(self):
        """从数据库加载任务数据"""
        self.beginResetModel()
        try:
            query = self.session.query(ProjectTask)
            if self.project_id:
                query = query.filter(ProjectTask.project_id == self.project_id)
            # 加载时不再按 level 排序，层级编码计算时会处理顺序
            self.tasks = query.order_by(ProjectTask.id).all()
            # 构建 task_map 以便快速查找
            self.task_map = {task.id: task for task in self.tasks}
            # 计算层级编码
            self._calculate_hierarchical_codes()
            # 更新可见任务列表
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
        col_index = index.column()
        col_name = self.COLUMNS[col_index][1]

        # 处理 "ID" 列 (新的 index 0) - 显示层级编码，树形结构由 QTreeView 自动处理
        if col_index == 0:
            if role == Qt.DisplayRole or role == Qt.EditRole:
                # QTreeView 会自动在第0列绘制展开/折叠图标和缩进
                # 我们只需要返回层级编码即可
                return self.hierarchical_codes.get(task.id, str(task.id))
            return None # 其他 Role 返回 None

        # 处理 "状态" 列 (新的 index 1)
        elif col_index == 1:
            if role == Qt.DecorationRole:
                status = getattr(task, 'status', TaskStatus.NOT_STARTED)
                return self.STATUS_COLOR_MAP.get(status, QColor("white"))
            elif role == Qt.UserRole:
                return getattr(task, 'status', TaskStatus.NOT_STARTED)
            return None # 不显示文本

        # 处理 "任务名称" 列 (新的 index 2) - 只显示纯名称
        elif col_index == 2:
             if role == Qt.DisplayRole or role == Qt.EditRole:
                 return getattr(task, 'name', "")

        # 处理其他列 (索引需要相应调整)
        elif role == Qt.DisplayRole or role == Qt.EditRole:
            # 注意：将 id, status_icon, name 的处理移到上面
            if col_name == "duration": # 现在是 index 5
                if task.start_date and task.end_date:
                    # 确保 start_date 和 end_date 是 date 对象
                    start = task.start_date
                    end = task.end_date
                    if isinstance(start, str): start = datetime.strptime(start, "%Y-%m-%d").date()
                    if isinstance(end, str): end = datetime.strptime(end, "%Y-%m-%d").date()
                    if start and end:
                         return (end - start).days + 1
                return 0
            elif col_name == "dependencies": # 现在是 index 7
                deps_json = task.dependencies
                try:
                    # 尝试解析 JSON
                    if deps_json:
                        import json
                        deps_list = json.loads(deps_json)
                        # 将依赖的数据库ID转换为层级编码
                        dep_codes = [self.hierarchical_codes.get(dep_id, str(dep_id)) for dep_id in deps_list]
                        return ", ".join(dep_codes)
                    else:
                        return ""
                except (json.JSONDecodeError, TypeError):
                     # 如果解析失败或不是字符串，返回原始值或空字符串
                    return deps_json if isinstance(deps_json, str) else ""

            # 对于其他列，如果不是 'id', 'status_icon', 'name'，则正常获取属性
            if col_name not in ["id", "status_icon", "name"]:
                 value = getattr(task, col_name, "")
                 # 特别处理日期列
                 if isinstance(value, datetime):
                     return QDate(value.year, value.month, value.day)
                 elif isinstance(value, date):
                      return QDate(value.year, value.month, value.day)
                 return value
            # 如果是 'id'/'status_icon'/'name' 且不是 Display/Edit/Decoration/UserRole，返回 None
            return None

        elif role == Qt.BackgroundRole: # 背景色逻辑可能需要根据新状态调整
            if task.status == TaskStatus.COMPLETED:
                return QBrush(QColor(220, 255, 220))
            pass # 暂时不设置背景色

        elif role == Qt.TextAlignmentRole:
            # ID(0), 状态(1), 开始时间(3), 结束时间(4), 工期(5), 进度(6), 前置任务(7), 负责人(8) 居中
            # 任务名称(2), 描述(9) 左对齐
            if col_index in [0, 1, 3, 4, 5, 6, 7, 8]:
                return Qt.AlignCenter

        return None
    
    def setData(self, index, value, role=Qt.EditRole):
        """设置单元格数据"""
        if not index.isValid() or role != Qt.EditRole:
            return False
        if not (0 <= index.row() < len(self.visible_tasks)):
             return False
        task = self.visible_tasks[index.row()]
        col_index = index.column()
        col_name = self.COLUMNS[col_index][1]

        original_status = task.status

        try:
            # 处理 "状态" 列的编辑 (新的 index 1)
            if col_name == "status_icon":
                if isinstance(value, TaskStatus):
                    task.status = value
                else:
                    return False
            # 处理日期列 (index 3, 4)
            elif col_name == "start_date" or col_name == "end_date":
                if isinstance(value, QDate):
                    value = value.toPython()
                elif isinstance(value, str):
                    try:
                        value = datetime.strptime(value, "%Y-%m-%d").date()
                    except ValueError:
                        return False
                elif not isinstance(value, date):
                     return False
                setattr(task, col_name, value)
            elif col_name == "progress": # index 6
                try:
                    value = int(value)
                    if 0 <= value <= 100:
                        setattr(task, col_name, value)
                        if task.status in [TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED]:
                             if value == 100:
                                 task.status = TaskStatus.COMPLETED
                             elif value > 0:
                                 task.status = TaskStatus.IN_PROGRESS
                             else:
                                 task.status = TaskStatus.NOT_STARTED
                    else:
                        return False
                except ValueError:
                    return False
            # 处理依赖列 (index 7)
            elif col_name == "dependencies":
                dep_codes = [code.strip() for code in value.split(",") if code.strip()]
                dep_ids = []
                code_to_id = {code: task_id for task_id, code in self.hierarchical_codes.items()}
                for code in dep_codes:
                    task_id = code_to_id.get(code)
                    if task_id is not None:
                        dep_ids.append(task_id)
                    else:
                        print(f"警告：找不到层级编码 '{code}' 对应的任务ID。")
                import json
                task.dependencies = json.dumps(dep_ids) if dep_ids else None
            # 处理其他可编辑列 (名称列现在也在这里处理，不再需要去除前缀)
            elif col_name not in ["id", "status_icon"]: # ID(0) 和 Status(1) 不在此处处理编辑
                setattr(task, col_name, value)

            self.session.commit()

            self.dataChanged.emit(index, index)
            if task.status != original_status:
                 progress_index = self.index(index.row(), self.COLUMNS.index(("进度(%)", "progress")))
                 self.dataChanged.emit(progress_index, progress_index)

            return True
        except Exception as e:
            print(f"更新任务数据失败: {str(e)}")
            self.session.rollback()
            return False
    
    def flags(self, index):
        """设置单元格标志"""
        default_flags = super().flags(index)
        if not index.isValid():
            return default_flags

        col_index = index.column()
        # ID 列 (index 0) 不可编辑
        if col_index == 0:
            return default_flags & ~Qt.ItemIsEditable
        # 状态列 (index 1) 和其他列可编辑
        else:
            return default_flags | Qt.ItemIsEditable

    def add_task(self, task_data):
        """添加新任务到数据库和模型"""
        try:
            start_date = task_data.get('start_date')
            if isinstance(start_date, QDate):
                start_date = start_date.toPython()
            end_date = task_data.get('end_date')
            if isinstance(end_date, QDate):
                end_date = end_date.toPython()

            new_task_obj = ProjectTask(
                project_id=task_data.get('project_id', self.project_id),
                name=task_data.get('name', '新任务'),
                start_date=start_date,
                end_date=end_date,
                progress=task_data.get('progress', 0),
                status=task_data.get('status', TaskStatus.NOT_STARTED),
                level=task_data.get('level', 0),
                parent_id=task_data.get('parent_id', None),
                dependencies=task_data.get('dependencies'),
                assignee=task_data.get('assignee'),
                description=task_data.get('description')
            )
            self.session.add(new_task_obj)
            self.session.commit()
            self.load_data()
            return True
        except Exception as e:
            print(f"添加任务失败: {str(e)}")
            self.session.rollback()
            return False

    def remove_task(self, task_to_delete):
        """从数据库和模型中删除任务及其所有子任务"""
        try:
            children = self.session.query(ProjectTask).filter(ProjectTask.parent_id == task_to_delete.id).all()
            for child in children:
                self.remove_task(child)
            self.session.delete(task_to_delete)
            self.session.commit()
            return True
        except Exception as e:
            print(f"删除任务 {task_to_delete.id} 失败: {str(e)}")
            self.session.rollback()
            return False

    def remove_visible_task(self, row):
        """删除可见列表中的任务，并触发数据库删除"""
        if 0 <= row < len(self.visible_tasks):
            task_to_delete = self.visible_tasks[row]
            if self.remove_task(task_to_delete):
                self.load_data()
                return True
        return False

# 移除旧的 StatusDelegate，因为它不再需要处理进度列
# class StatusDelegate(QStyledItemDelegate):
#     """状态列委托"""
#     def createEditor(self, parent, option, index):
#         if index.column() == 5:  # 进度列
#             editor = QComboBox(parent)
#             editor.addItems([str(i) for i in range(0, 101, 10)])
#             return editor
#         return super().createEditor(parent, option, index)

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
        
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(24, 24))

        self.add_action = QAction(QIcon(UIUtils.get_svg_icon_path('add')), "添加", self)
        self.add_sub_action = QAction(QIcon(UIUtils.get_svg_icon_path('add_sub')), "添加子级", self)
        self.delete_action = QAction(QIcon(UIUtils.get_svg_icon_path('delete')), "删除", self)
        self.undo_action = QAction(QIcon(UIUtils.get_svg_icon_path('undo')), "撤销", self)
        self.redo_action = QAction(QIcon(UIUtils.get_svg_icon_path('redo')), "恢复", self)
        self.insert_above_action = QAction(QIcon(UIUtils.get_svg_icon_path('insert_above')), "上方插入", self)
        self.insert_below_action = QAction(QIcon(UIUtils.get_svg_icon_path('insert_below')), "下方插入", self)
        self.promote_action = QAction(QIcon(UIUtils.get_svg_icon_path('promote')), "升级", self)
        self.demote_action = QAction(QIcon(UIUtils.get_svg_icon_path('demote')), "降级", self)
        self.move_up_action = QAction(QIcon(UIUtils.get_svg_icon_path('move_up')), "上移", self)
        self.move_down_action = QAction(QIcon(UIUtils.get_svg_icon_path('move_down')), "下移", self)
        self.expand_all_action = QAction(QIcon(UIUtils.get_svg_icon_path('expand')), "全部展开", self)
        self.collapse_all_action = QAction(QIcon(UIUtils.get_svg_icon_path('collapse')), "全部折叠", self)
        self.zoom_in_action = QAction(QIcon(UIUtils.get_svg_icon_path('zoom_in')), "放大", self)
        self.zoom_out_action = QAction(QIcon(UIUtils.get_svg_icon_path('zoom_out')), "缩小", self)
        
        toolbar.addAction(self.add_action)
        toolbar.addAction(self.add_sub_action)
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
        
        splitter = QSplitter(Qt.Horizontal)
        
        # 创建任务表格
        self.task_table = QTreeView()
        # 移除 setRootIsDecorated(False) 和 setIndentation(0)，让 QTreeView 在第0列绘制树形结构
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.task_table.setSelectionMode(QAbstractItemView.SingleSelection)
        # 设置状态颜色委托给新的 "状态" 列 (第 1 列)
        self.status_delegate = StatusColorDelegate(self)
        self.task_table.setItemDelegateForColumn(1, self.status_delegate) # 应用到第 1 列

        # 应用样式 (保持不变)
        self.task_table.setStyleSheet("""
            QTreeView {
                background-color: transparent;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                selection-background-color: rgba(0, 120, 212, 0.1);
                selection-color: black;
                alternate-background-color: #f9f9f9; /* 添加交替行颜色 */
            }
            QTreeView::item {
                height: 32px; /* 稍微调整行高 */
                padding: 2px;
            }
            QTreeView::item:hover {
                background-color: rgba(0, 0, 0, 0.05);
            }
            QTreeView::item:selected {
                background-color: rgba(0, 120, 212, 0.1);
                color: black;
            }
            QTreeView::item:selected:active {
                background-color: rgba(0, 120, 212, 0.15);
                color: black;
            }
            QTreeView::branch { /* 样式化树形分支 */
                background: transparent;
            }
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {
                 border-image: none;
                 /* image: url(path/to/your/closed-arrow.png); 可选：自定义图标 */
            }
            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings  {
                 border-image: none;
                 /* image: url(path/to/your/open-arrow.png); 可选：自定义图标 */
            }
            QHeaderView::section {
                background-color: #f3f3f3;
                color: #333333;
                font-weight: 500;
                padding: 8px;
                border: none;
                border-bottom: 1px solid rgba(0, 0, 0, 0.1);
            }
            QHeaderView::section:hover {
                background-color: #e5e5e5;
            }
        """)

        self.task_table.setEditTriggers(QTreeView.SelectedClicked | QTreeView.DoubleClicked | QTreeView.EditKeyPressed)

        header = self.task_table.header()
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        # 新列顺序: ("ID", "id"), ("状态", "status_icon"), ("任务名称", "name"), ...
        # 调整列宽
        header.resizeSection(0, 120)  # ID (第 0 列，加宽以容纳树形结构)
        header.resizeSection(1, 40)   # 状态 (第 1 列)
        header.resizeSection(2, 300)  # 任务名称 (第 2 列)
        header.resizeSection(3, 120)  # 开始时间
        header.resizeSection(4, 120)  # 结束时间
        header.resizeSection(5, 80)   # 工期(天)
        header.resizeSection(6, 80)   # 进度(%)
        header.resizeSection(7, 100)  # 前置任务
        header.resizeSection(8, 100)  # 负责人
        header.resizeSection(9, 200)  # 描述

        self.task_model = TaskTableModel(self.session, self.project.id)
        self.task_table.setModel(self.task_model)
        
        self.task_table.clicked.connect(self.on_task_clicked)
        
        splitter.addWidget(self.task_table)
        
        self.gantt_view = GanttView(self)
        splitter.addWidget(self.gantt_view)
        
        splitter.setSizes([500, 500])
        
        self.main_layout.addWidget(splitter)
        
        self.connect_actions()
        
    def connect_actions(self):
        """连接工具栏按钮信号"""
        self.add_action.triggered.connect(self.add_task)
        self.add_sub_action.triggered.connect(self.add_sub_task)
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
        # self.undo_action.triggered.connect(self.on_undo) # 实际撤销逻辑待实现
        # self.redo_action.triggered.connect(self.on_redo) # 实际恢复逻辑待实现
        
    def add_task(self):
        """添加新任务"""
        new_task = {
            'project_id': self.project.id,
            'name': '新任务',
            'start_date': QDate.currentDate(),
            'end_date': QDate.currentDate().addDays(1),
            'progress': 0,
            'status': TaskStatus.NOT_STARTED
        }
        if self.task_model.add_task(new_task):
            self.gantt_view.update_view()

    def add_sub_task(self):
        """添加子任务"""
        index = self.task_table.currentIndex()
        if not index.isValid():
            self.add_task()
            return

        parent_task = self.task_model.visible_tasks[index.row()]
        new_task = {
            'project_id': self.project.id,
            'name': '新子任务',
            'start_date': QDate.currentDate(),
            'end_date': QDate.currentDate().addDays(1),
            'progress': 0,
            'status': TaskStatus.NOT_STARTED,
            'level': parent_task.level + 1,
            'parent_id': parent_task.id
        }
        if self.task_model.add_task(new_task):
            if parent_task.id not in self.task_model.expanded_tasks:
                 self.task_model.expanded_tasks.add(parent_task.id)
                 self.task_model.load_data() # 重新加载以显示子任务
            self.gantt_view.update_view()

    def on_task_clicked(self, index):
        """处理任务点击事件"""
        # 点击第 0 列 (ID 列) 时触发展开/折叠
        if index.column() == 0:
            self.task_model.toggle_task_expanded(index)
            # 甘特图视图也需要更新以反映行的变化
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
                # 可能需要处理排序逻辑以确保插入在正确位置
            }
            if self.task_model.add_task(new_task):
                self.gantt_view.update_view()
            
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
                # 可能需要处理排序逻辑以确保插入在正确位置
            }
            if self.task_model.add_task(new_task):
                 self.gantt_view.update_view()
            
    def promote_task(self):
        """提升任务层级"""
        index = self.task_table.currentIndex()
        if index.isValid():
            task = self.task_model.visible_tasks[index.row()]
            if task.level > 0:
                parent_task = self.task_model._get_task_by_id(task.parent_id)
                if parent_task:
                    task.parent_id = parent_task.parent_id
                    task.level -= 1
                    self.task_model.session.commit()
                    self.task_model.load_data()
                    self.gantt_view.update_view()
                    
    def demote_task(self):
        """降低任务层级"""
        index = self.task_table.currentIndex()
        if index.isValid():
            row = index.row()
            if row > 0: # 不能降级第一个可见任务
                task = self.task_model.visible_tasks[row]
                prev_task = self.task_model.visible_tasks[row - 1]
                # 只能降级到前一个可见任务的下一级，且层级不能跳跃
                if prev_task.level >= task.level:
                    task.parent_id = prev_task.id
                    task.level = prev_task.level + 1
                    self.task_model.session.commit()
                    self.task_model.load_data()
                    self.gantt_view.update_view()

    def move_task_up(self):
        """上移任务"""
        # 简单的上移/下移可能破坏层级结构，需要更复杂的逻辑
        print("上移任务（功能待实现或调整）")

    def move_task_down(self):
        """下移任务"""
        print("下移任务（功能待实现或调整）")

    def delete_task(self):
        """删除选中的任务及其子任务"""
        index = self.task_table.currentIndex()
        if index.isValid():
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(self, '确认删除',
                                         f"确定要删除选中的任务及其所有子任务吗？\n此操作不可恢复！",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                if self.task_model.remove_visible_task(index.row()):
                    self.gantt_view.update_view()
                else:
                     QMessageBox.warning(self, '删除失败', '删除任务时发生错误。')

    def expand_all_tasks(self):
        """展开所有任务"""
        self.task_model.expanded_tasks = set(task.id for task in self.task_model.tasks if any(t.parent_id == task.id for t in self.task_model.tasks))
        self.task_model.load_data()
        self.gantt_view.update_view()

    def collapse_all_tasks(self):
        """折叠所有任务"""
        self.task_model.expanded_tasks.clear()
        self.task_model.load_data()
        self.gantt_view.update_view()

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
        
        self.time_scale = "day"
        self.start_date = QDate.currentDate()
        self.end_date = self.start_date.addDays(30)
        self.day_width = 30
        self.header_height = 24  # 表头高度
        self.zoom_factor = 1.0
        
        # 获取左侧任务列表的行高
        self.row_height = self.get_task_list_row_height()
        
        self.dragging_item = None
        self.drag_start_pos = None
        self.original_dates = None
        
        self.init_ui()
        
    def get_task_list_row_height(self):
        """获取左侧任务列表的行高"""
        progress_widget = self.parent()
        if isinstance(progress_widget, QSplitter):
            progress_widget = progress_widget.parent()
        if hasattr(progress_widget, 'task_table'):
            # 获取任务表格的第一行高度
            task_table = progress_widget.task_table
            if task_table.model() and task_table.model().rowCount() > 0:
                # 创建第一行的QModelIndex
                index = task_table.model().index(0, 0)
                return task_table.rowHeight(index)
        return 34  # 默认行高
    
    def init_ui(self):
        self.setStyleSheet("background-color: white;")
        self.setMouseTracking(True)
        self.update_view() # 初始绘制
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = self.mapToScene(event.pos())
            item = self.scene.itemAt(pos, self.transform())
            if isinstance(item, QGraphicsRectItem) and item.data(0):
                self.dragging_item = item
                self.drag_start_pos = pos
                task_id = item.data(0)
                task = self.parent().task_model._get_task_by_id(task_id)
                if task:
                    self.original_dates = (task.start_date, task.end_date)
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        if self.dragging_item and self.drag_start_pos:
            pos = self.mapToScene(event.pos())
            delta_x = pos.x() - self.drag_start_pos.x()
            days_delta = round(delta_x / (self.day_width * self.zoom_factor)) # 使用 round 更精确
            
            if days_delta != 0 and self.original_dates:
                task_id = self.dragging_item.data(0)
                task = self.parent().task_model._get_task_by_id(task_id)
                if task:
                    # 确保日期是 date 对象
                    start_date = self.original_dates[0]
                    end_date = self.original_dates[1]
                    if isinstance(start_date, str): start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                    if isinstance(end_date, str): end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

                    if start_date and end_date:
                        new_start = start_date + timedelta(days=days_delta)
                        new_end = end_date + timedelta(days=days_delta)
                        
                        # 更新模型数据
                        start_index = self.parent().task_model.index(self.parent().task_model.visible_tasks.index(task), 3) # Start date column index
                        end_index = self.parent().task_model.index(self.parent().task_model.visible_tasks.index(task), 4) # End date column index
                        
                        # 使用 setData 更新模型，它会处理提交和信号
                        self.parent().task_model.setData(start_index, new_start, Qt.EditRole)
                        self.parent().task_model.setData(end_index, new_end, Qt.EditRole)
                        
                        # 更新视图（setData 会触发 dataChanged，理论上会自动更新，但显式调用确保同步）
                        self.update_view()
                        
                        # 更新拖拽起始位置和原始日期以进行连续拖动
                        self.drag_start_pos = pos
                        self.original_dates = (new_start, new_end)

        super().mouseMoveEvent(event)
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging_item = None
            self.drag_start_pos = None
            self.original_dates = None
        super().mouseReleaseEvent(event)
        
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)
            
    def zoom_in(self):
        self.zoom_factor *= 1.2
        self.update_view()
        
    def zoom_out(self):
        self.zoom_factor /= 1.2
        self.update_view()
        
    def set_time_scale(self, scale):
        self.time_scale = scale
        self.update_view()
        
    def update_view(self):
        """更新视图"""
        self.scene.clear()
        # 更新行高
        self.row_height = self.get_task_list_row_height()
        # 确保 start_date 和 end_date 是 QDate 对象
        if isinstance(self.start_date, date) and not isinstance(self.start_date, QDate):
             self.start_date = QDate(self.start_date.year, self.start_date.month, self.start_date.day)
        if isinstance(self.end_date, date) and not isinstance(self.end_date, QDate):
             self.end_date = QDate(self.end_date.year, self.end_date.month, self.end_date.day)

        self.draw_timeline()
        # 通过父级（ProjectProgressWidget）访问task_model
        progress_widget = self.parent()
        if isinstance(progress_widget, QSplitter):
            progress_widget = progress_widget.parent()
        if hasattr(progress_widget, 'task_model'):
            self.draw_tasks(progress_widget.task_model.visible_tasks)
            self.draw_dependencies(progress_widget.task_model.visible_tasks)
        
    def draw_timeline(self):
        """绘制时间轴"""
        # self.scene.clear() # 在 update_view 中已清除
        
        days = self.start_date.daysTo(self.end_date) + 1
        total_width = days * self.day_width * self.zoom_factor
        
        if self.zoom_factor <= 0.5: self.time_scale = "month"
        elif self.zoom_factor <= 1.0: self.time_scale = "week"
        else: self.time_scale = "day"
        
        self.draw_time_ruler(total_width, days)
        self.draw_grid_lines(total_width, days)
        
        # 动态调整场景高度
        # 通过父级（ProjectProgressWidget）访问task_model
        progress_widget = self.parent()
        if isinstance(progress_widget, QSplitter):
            progress_widget = progress_widget.parent()
        if hasattr(progress_widget, 'task_model'):
            scene_height = 50 + len(progress_widget.task_model.visible_tasks) * self.row_height + 50 # 50是表头高度，额外50是底部边距
            self.scene.setSceneRect(0, 0, total_width + 100, max(600, scene_height)) # 最小高度600
        else:
            self.scene.setSceneRect(0, 0, total_width + 100, 600) # 默认高度600
        
    def draw_time_ruler(self, total_width, days):
        total_header_height = self.header_height * 2
        
        # 绘制表头背景
        header_bg = QGraphicsRectItem(0, 0, total_width, total_header_height)
        header_bg.setBrush(QBrush(QColor(248, 249, 250)))  # 使用与左侧表头相同的颜色
        header_bg.setPen(QPen(Qt.NoPen))
        self.scene.addItem(header_bg)
        
        # 绘制上下两个标尺
        upper_ruler = QGraphicsRectItem(0, 0, total_width, self.header_height)
        upper_ruler.setBrush(QBrush(Qt.transparent))
        upper_ruler.setPen(QPen(QColor(220, 220, 220)))  # 与左侧表头边框颜色一致
        self.scene.addItem(upper_ruler)
        
        lower_ruler = QGraphicsRectItem(0, self.header_height, total_width, self.header_height)
        lower_ruler.setBrush(QBrush(Qt.transparent))
        lower_ruler.setPen(QPen(QColor(220, 220, 220)))
        self.scene.addItem(lower_ruler)
        
        font = QFont("Arial", 8)
        current_date = self.start_date
        last_upper_label = ""
        
        for i in range(days):
            x = i * self.day_width * self.zoom_factor
            
            line = QGraphicsLineItem(x, 0, x, total_header_height)
            line.setPen(QPen(QColor(200, 200, 200)))
            self.scene.addItem(line)
            
            upper_label = ""
            if self.time_scale == "month":
                if current_date.day() == 1: upper_label = current_date.toString("yyyy年MM月")
            elif self.time_scale == "week":
                if current_date.dayOfWeek() == 1: upper_label = f"{current_date.year()}年第{current_date.weekNumber()[0]}周"
            else: # day
                if current_date.day() == 1: upper_label = current_date.toString("yyyy年MM月")
            
            if upper_label and upper_label != last_upper_label:
                text = QGraphicsTextItem(upper_label)
                text.setFont(font)
                text.setPos(x + 2, 5)
                self.scene.addItem(text)
                last_upper_label = upper_label
            
            lower_label_text = ""
            if self.time_scale == "month":
                if current_date.day() == 1: lower_label_text = current_date.toString("MM月")
            elif self.time_scale == "week":
                if current_date.dayOfWeek() == 1: lower_label_text = current_date.toString("MM-dd")
            else: # day
                lower_label_text = current_date.toString("dd")

            if lower_label_text:
                text = QGraphicsTextItem(lower_label_text)
                text.setFont(font)
                text.setPos(x + 2, self.header_height + 5)
                self.scene.addItem(text)
            
            current_date = current_date.addDays(1)
            
    def draw_grid_lines(self, total_width, days):
        header_height = self.header_height * 2  # 两个表头的总高度
        # 通过父级（ProjectProgressWidget）访问task_model
        progress_widget = self.parent()
        if isinstance(progress_widget, QSplitter):
            progress_widget = progress_widget.parent()
        if hasattr(progress_widget, 'task_model'):
            grid_height = max(600, header_height + len(progress_widget.task_model.visible_tasks) * self.row_height + 20)  # 使用动态高度
            task_count = len(progress_widget.task_model.visible_tasks)
        else:
            grid_height = 600
            task_count = 0

        # 绘制垂直网格线
        for i in range(days + 1):
            x = i * self.day_width * self.zoom_factor
            line = QGraphicsLineItem(x, header_height, x, grid_height)
            line.setPen(QPen(QColor(240, 240, 240)))  # 使用与左侧表格相同的网格线颜色
            self.scene.addItem(line)
            
        # 绘制水平网格线
        for i in range(task_count + 1):
            y = header_height + i * self.row_height
            line = QGraphicsLineItem(0, y, total_width, y)
            line.setPen(QPen(QColor(240, 240, 240)))
            self.scene.addItem(line)
            
    def draw_tasks(self, tasks):
        header_height = 50
        for i, task in enumerate(tasks):
            # 确保日期是 date 对象
            start_date = task.start_date
            end_date = task.end_date
            if isinstance(start_date, str): start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            if isinstance(end_date, str): end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

            if not start_date or not end_date:
                continue

            # 转换为 QDate 进行计算
            start_qdate = QDate(start_date.year, start_date.month, start_date.day)
            end_qdate = QDate(end_date.year, end_date.month, end_date.day)

            start_offset = self.start_date.daysTo(start_qdate)
            # 使用 QDate 对象计算天数
            duration = start_qdate.daysTo(end_qdate) + 1 

            x = start_offset * self.day_width * self.zoom_factor
            y = header_height + i * self.row_height + 5
            width = duration * self.day_width * self.zoom_factor
            height = self.row_height - 10
            
            task_rect = QGraphicsRectItem(x, y, width, height)
            task_rect.setData(0, task.id)
            
            # 使用 TaskStatus 的 color 属性
            color = QColor(task.status.color) if task.status else QColor(200, 200, 200)
                
            task_rect.setBrush(QBrush(color))
            task_rect.setPen(QPen(QColor(50, 50, 50), 0.5)) # 细一点的边框
            task_rect.setAcceptHoverEvents(True)
            task_rect.setCursor(Qt.PointingHandCursor) # 改为手型光标
            self.scene.addItem(task_rect)
            
            # 绘制任务名称 (可选，如果条太窄可能显示不下)
            # if width > 50: # 仅在宽度足够时显示
            #     task_text = QGraphicsTextItem(task.name)
            #     font = QFont("Arial", 8)
            #     task_text.setFont(font)
            #     # 限制文本宽度
            #     text_rect = task_text.boundingRect()
            #     max_text_width = width - 10 # 留出边距
            #     if text_rect.width() > max_text_width:
            #         # 可以考虑截断文本或换行，这里简单截断
            #         metrics = QFontMetrics(font)
            #         elided_text = metrics.elidedText(task.name, Qt.ElideRight, max_text_width)
            #         task_text.setPlainText(elided_text)

            #     text_x = x + 5
            #     text_y = y + (height - text_rect.height()) / 2
            #     task_text.setPos(text_x, text_y)
            #     task_text.setDefaultTextColor(QColor(255, 255, 255) if color.lightness() < 128 else QColor(0,0,0)) # 根据背景色调整文字颜色
            #     self.scene.addItem(task_text)
            
            # 绘制进度条 (更精细)
            if task.progress > 0:
                progress_width = width * task.progress / 100
                progress_rect = QGraphicsRectItem(x, y, progress_width, height) # 覆盖在任务条上
                progress_color = color.darker(120) # 使用更深的颜色表示进度
                progress_rect.setBrush(QBrush(progress_color))
                progress_rect.setPen(QPen(Qt.NoPen))
                progress_rect.setZValue(task_rect.zValue() + 1) # 确保在任务条之上
                self.scene.addItem(progress_rect)
                
    def draw_dependencies(self, tasks):
        header_height = 50
        task_map = self.parent().task_model.task_map
        visible_task_indices = {task.id: i for i, task in enumerate(tasks)} # 快速查找可见任务的索引

        for i, task in enumerate(tasks):
            if not task.dependencies: continue
            try:
                import json
                deps = json.loads(task.dependencies)
                if not isinstance(deps, list): continue
            except (json.JSONDecodeError, TypeError): continue

            for dep_id in deps:
                dep_task = task_map.get(dep_id)
                if not dep_task or dep_task.id not in visible_task_indices: continue

                # 确保日期是 date 对象
                dep_end_date = dep_task.end_date
                task_start_date = task.start_date
                if isinstance(dep_end_date, str): dep_end_date = datetime.strptime(dep_end_date, "%Y-%m-%d").date()
                if isinstance(task_start_date, str): task_start_date = datetime.strptime(task_start_date, "%Y-%m-%d").date()

                if not dep_end_date or not task_start_date: continue

                dep_index = visible_task_indices[dep_task.id]
                current_task_index = i

                dep_end_qdate = QDate(dep_end_date.year, dep_end_date.month, dep_end_date.day)
                task_start_qdate = QDate(task_start_date.year, task_start_date.month, task_start_date.day)

                start_offset = self.start_date.daysTo(dep_end_qdate)
                end_offset = self.start_date.daysTo(task_start_qdate)

                task_bar_center_y_offset = header_height + self.row_height / 2

                start_x = (start_offset + 1) * self.day_width * self.zoom_factor # 依赖任务结束点
                start_y = dep_index * self.row_height + task_bar_center_y_offset
                end_x = end_offset * self.day_width * self.zoom_factor # 当前任务开始点
                end_y = current_task_index * self.row_height + task_bar_center_y_offset

                # 简单的直线箭头
                line = QGraphicsLineItem(start_x, start_y, end_x, end_y)
                pen = QPen(QColor(80, 80, 80), 1, Qt.SolidLine)
                pen.setCapStyle(Qt.RoundCap)
                line.setPen(pen)
                self.scene.addItem(line)
                
                # 箭头
                arrow_size = 6
                angle = math.atan2(end_y - start_y, end_x - start_x) # 使用 atan2 获取角度
                
                arrow_p1 = QPointF(end_x - arrow_size * math.cos(angle + math.pi / 6),
                                   end_y - arrow_size * math.sin(angle + math.pi / 6))
                arrow_p2 = QPointF(end_x - arrow_size * math.cos(angle - math.pi / 6),
                                   end_y - arrow_size * math.sin(angle - math.pi / 6))
                
                arrow = QGraphicsPolygonItem(QPolygonF([QPointF(end_x, end_y), arrow_p1, arrow_p2]))
                arrow.setBrush(QBrush(QColor(80, 80, 80)))
                arrow.setPen(QPen(Qt.NoPen))
                self.scene.addItem(arrow)


# 移除 TaskTableView 和 ProjectProgressWindow 类，因为它们不再需要
# class TaskTableView(QTreeView): ...
# class ProjectProgressWindow(QMainWindow): ...


if __name__ == "__main__":
    # 这个 __main__ 块可能需要调整，因为它引用了已移除的类
    # 如果这个文件只作为 Widget 使用，可以移除或注释掉 __main__ 部分
    app = QApplication(sys.argv)
    # 假设需要一个模拟的 project 对象来测试
    class MockProject: id = 1
    window = ProjectProgressWidget(MockProject()) # 使用 Widget 类
    window.setWindowTitle("项目进度测试")
    window.resize(1000, 600)
    window.show()
    sys.exit(app.exec_())
