import os # Ensure os is imported
import shutil # Add shutil
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidgetItem, QDialog, QHeaderView, QFileDialog, QApplication 
from PySide6.QtCore import Qt, QPoint, QDate 
from PySide6.QtGui import QIcon 
from qfluentwidgets import TitleLabel, FluentIcon, LineEdit, ComboBox, DateEdit, CompactDateEdit, BodyLabel, PushButton, TableWidget, TableItemDelegate, Dialog, RoundMenu, Action, PlainTextEdit
from ...utils.ui_utils import UIUtils
from ...models.database import Project, Base, sessionmaker, Actionlog # Import Actionlog
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum as SQLEnum, Engine 
from enum import Enum
from datetime import datetime
from ...utils.attachment_utils import (
    create_attachment_button,
    sanitize_filename, ensure_directory_exists, get_timestamp_str, get_attachment_icon_path,
    view_attachment, download_attachment, ROOT_DIR,
    generate_attachment_path, handle_attachment, execute_attachment_action # 添加新导入的函数
)
from ...utils.filter_utils import FilterUtils 
import pandas as pd 

class OutcomeType(Enum):
    PAPER = "论文"
    PATENT = "专利"
    SOFTWARE = "软著"
    STANDARD = "标准"
    AWARD = "获奖"
    OTHER = "其他"

class OutcomeStatus(Enum):
    DRAFT = "草稿"
    SUBMITTED = "已提交"
    ACCEPTED = "已接收"
    PUBLISHED = "已发表/授权"
    REJECTED = "已拒绝"

class ProjectOutcome(Base): # 重命名模型类
    __tablename__ = 'project_outcome' # 重命名表名

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    name = Column(String(200), nullable=False)  # 成果名称
    type = Column(SQLEnum(OutcomeType), nullable=False)  # 成果类型
    status = Column(SQLEnum(OutcomeStatus), default=OutcomeStatus.DRAFT)  # 成果状态
    authors = Column(String(200))  # 作者/完成人
    submit_date = Column(Date)  # 投稿/申请日期
    publish_date = Column(Date)  # 发表/授权日期
    journal = Column(String(200))  # 期刊/授权单位
    description = Column(String(500))  # 成果描述
    remarks = Column(String(200))  # 备注
    attachment_path = Column(String(500)) # 新增：附件文件路径

class OutcomeDialog(QDialog):
    def __init__(self, parent=None, outcome=None, project=None):
        super().__init__(parent)
        self.outcome = outcome
        self.project = project
        self.setup_ui()
        if outcome:
            self.load_outcome_data()

    def setup_ui(self):
        self.setWindowTitle("成果信息")
        layout = QVBoxLayout(self)
        layout.setSpacing(10) # Add spacing between rows

        # 成果名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(BodyLabel("成果名称:"))
        self.name_edit = LineEdit()
        self.name_edit.setPlaceholderText("请输入成果名称，必填")
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # 类型
        type_layout = QHBoxLayout()
        type_layout.addWidget(BodyLabel("成果类型:"))
        self.type_combo = ComboBox()
        for type_enum in OutcomeType:
            self.type_combo.addItem(type_enum.value)
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)

        # 状态
        status_layout = QHBoxLayout()
        status_layout.addWidget(BodyLabel("成果状态:"))
        self.status_combo = ComboBox()
        for status_enum in OutcomeStatus:
            self.status_combo.addItem(status_enum.value)
        status_layout.addWidget(self.status_combo)
        layout.addLayout(status_layout)

        # 作者/完成人
        authors_layout = QHBoxLayout()
        authors_layout.addWidget(BodyLabel("作者/完成人:"))
        self.authors_edit = PlainTextEdit()
        self.authors_edit.setPlaceholderText("请输入作者或完成人")
        self.authors_edit.setFixedHeight(80)
        authors_layout.addWidget(self.authors_edit)
        layout.addLayout(authors_layout)

        # 投稿/申请日期
        submit_date_layout = QHBoxLayout()
        submit_date_layout.addWidget(BodyLabel("投稿/申请日期:"))
        self.submit_date = DateEdit()
        self.submit_date.setDate(datetime.now().date()) # Use .date()
        self.submit_date.setDisplayFormat("yyyy-MM-dd")
        submit_date_layout.addWidget(self.submit_date)
        layout.addLayout(submit_date_layout)

        # 发表/授权日期
        publish_date_layout = QHBoxLayout()
        publish_date_layout.addWidget(BodyLabel("发表/授权日期:"))
        self.publish_date = DateEdit()
        self.publish_date.setDate(datetime.now().date()) # Use .date()
        self.publish_date.setDisplayFormat("yyyy-MM-dd")
        publish_date_layout.addWidget(self.publish_date)
        layout.addLayout(publish_date_layout)

        # 期刊/授权单位
        journal_layout = QHBoxLayout()
        journal_layout.addWidget(BodyLabel("期刊/授权单位:"))
        self.journal_edit = LineEdit()
        self.journal_edit.setPlaceholderText("请输入期刊或授权单位")
        journal_layout.addWidget(self.journal_edit)
        layout.addLayout(journal_layout)

        # 成果描述
        description_layout = QHBoxLayout()
        description_layout.addWidget(BodyLabel("成果描述:"))
        self.description_edit = PlainTextEdit()
        self.description_edit.setPlaceholderText("请输入成果描述")
        self.description_edit.setFixedHeight(120)
        description_layout.addWidget(self.description_edit)
        layout.addLayout(description_layout)

        
        layout.addStretch() # Add stretch before buttons

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        # Use PushButton and add icons, push to the right
        save_btn = PushButton("保存", self, FluentIcon.SAVE)
        cancel_btn = PushButton("取消", self, FluentIcon.CLOSE)
        save_btn.clicked.connect(self.accept) # Connect accept for validation
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch() # Push buttons to the right
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def accept(self):
        """Validate input before accepting the dialog."""
        if not self.name_edit.text().strip():
            UIUtils.show_warning(
                title='警告',
                content='成果名称不能为空',
                parent=self
            )
            return
        super().accept()

    def load_outcome_data(self):
        self.name_edit.setText(self.outcome.name)
        self.type_combo.setCurrentText(self.outcome.type.value)
        self.status_combo.setCurrentText(self.outcome.status.value)
        self.authors_edit.setPlainText(self.outcome.authors)
        if self.outcome.submit_date:
            self.submit_date.setDate(self.outcome.submit_date)
        if self.outcome.publish_date:
            self.publish_date.setDate(self.outcome.publish_date)
        self.journal_edit.setText(self.outcome.journal)
        self.description_edit.setPlainText(self.outcome.description)
       

class ProjectOutcomeWidget(QWidget): 
    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent=parent)       
        self.engine = engine # Store engine
        self.current_project = None # Track selected project
        self.all_outcomes = [] # Store all loaded outcomes
        self.current_outcomes = [] # Store currently displayed outcomes
        self.setup_ui()
        

    def showEvent(self, event):
        """在窗口显示时连接信号"""
        super().showEvent(event)
        # 尝试连接信号
        try:
            main_window = self.window()
            if main_window and hasattr(main_window, 'project_updated'):
                # 先断开旧连接，防止重复连接
                try:
                    main_window.project_updated.disconnect(self._refresh_project_selector)
                except RuntimeError:
                    pass # 信号未连接，忽略错误
                main_window.project_updated.connect(self._refresh_project_selector)
                print("ProjectOutcomeWidget: Connected to project_updated signal.")
            else:
                 print("ProjectOutcomeWidget: Could not find main window or project_updated signal.")
        except Exception as e:
            print(f"ProjectOutcomeWidget: Error connecting signal: {e}")

    def _refresh_project_selector(self):
        """刷新项目选择下拉框的内容"""
        print("ProjectOutcomeWidget: Refreshing project selector...")
        if not hasattr(self, 'project_selector') or not self.engine:
            print("ProjectOutcomeWidget: Project selector or engine not initialized.")
            return

        current_project_id = None
        if self.current_project: # 使用 self.current_project 存储的ID
            current_project_id = self.current_project.id

        self.project_selector.clear()
        self.project_selector.addItem("请选择项目...", userData=None) # 添加默认提示项

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            projects = session.query(Project).order_by(Project.financial_code).all()
            if not projects:
                self.project_selector.addItem("没有找到项目", userData=None)
                self.project_selector.setEnabled(False)
            else:
                self.project_selector.setEnabled(True)
                for project in projects:
                    self.project_selector.addItem(f"{project.financial_code} ", userData=project)

                # 尝试恢复之前的选择
                if current_project_id is not None:
                    for i in range(self.project_selector.count()):
                        data = self.project_selector.itemData(i)
                        if isinstance(data, Project) and data.id == current_project_id:
                            self.project_selector.setCurrentIndex(i)
                            break
                    else:
                        # 如果之前的项目找不到了（可能被删除），则触发一次选中事件以清空表格
                        self._on_project_selected(0) # 选中 "请选择项目..."

        except Exception as e:
            print(f"Error refreshing project selector in OutcomeWidget: {e}")
            self.project_selector.addItem("加载项目出错", userData=None)
            self.project_selector.setEnabled(False)
        finally:
            session.close()
            print("ProjectOutcomeWidget: Project selector refreshed.")

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(18, 18, 18, 18) # Add some margins
        self.main_layout.setSpacing(10)
        # --- Add Project Selector ---
        selector_layout = QHBoxLayout()
        selector_label = TitleLabel("项目成果-", self)
        selector_label.setToolTip("用于创建和管理项目的成果信息")
        self.project_selector = UIUtils.create_project_selector(self.engine, self)

        # 手动添加“全部数据”选项
        self.project_selector.insertItem(0, "全部成果", userData="all")
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.project_selector)
        selector_layout.addStretch()
        self.main_layout.addLayout(selector_layout)
        # Connect signal after UI setup
        self.project_selector.currentIndexChanged.connect(self._on_project_selected)
        # --- Project Selector End ---

        # 按钮栏
        add_btn = UIUtils.create_action_button("添加成果", FluentIcon.ADD)
        edit_btn = UIUtils.create_action_button("编辑成果", FluentIcon.EDIT)
        delete_btn = UIUtils.create_action_button("删除成果", FluentIcon.DELETE)

        add_btn.clicked.connect(self.add_outcome)
        edit_btn.clicked.connect(self.edit_outcome)
        delete_btn.clicked.connect(self.delete_outcome)

        button_layout = UIUtils.create_button_layout(add_btn, edit_btn, delete_btn)
        self.main_layout.addLayout(button_layout)

        # 成果列表
        self.outcome_table = TableWidget()
        self.outcome_table.setColumnCount(9) # 移除备注列，总列数减1
        self.outcome_table.setHorizontalHeaderLabels([
            "成果名称", "类型", "状态", "作者/完成人", "投稿/申请日期",
            "发表/授权日期", "期刊/授权单位", "描述", "成果附件" # 移除备注，调整附件列标题
        ])
        # 设置表格样式 (复用 expense 的样式设置)
        #self.outcome_table.setBorderVisible(True)
        #self.outcome_table.setBorderRadius(8)
        self.outcome_table.setWordWrap(False) 
        self.outcome_table.setItemDelegate(TableItemDelegate(self.outcome_table))
        UIUtils.set_table_style(self.outcome_table) # 应用通用样式

        # 设置列宽模式和排序
        header = self.outcome_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSortIndicatorShown(True) # 启用排序

        # 隐藏行号
        #self.outcome_table.verticalHeader().setVisible(False)

        # 设置初始列宽 (需要调整以适应新列)
        header.resizeSection(0, 200) # 成果名称
        header.resizeSection(1, 60) # 类型
        header.resizeSection(2, 80) # 状态
        header.resizeSection(3, 150) # 作者/完成人
        header.resizeSection(4, 92) # 投稿/申请日期
        header.resizeSection(5, 92) # 发表/授权日期
        header.resizeSection(6, 120) # 期刊/授权单位
        header.resizeSection(7, 200) # 描述
        header.resizeSection(8, 80)  # 附件列 (索引从9改为8)

        # 允许用户调整列宽和移动列
        header.setSectionsMovable(True)
        # header.setStretchLastSection(True) # 取消最后一列拉伸，手动设置附件列宽度
        
        vheader = self.outcome_table.verticalHeader()        
        vheader.setDefaultAlignment(Qt.AlignCenter)

        self.outcome_table.setSelectionMode(TableWidget.ExtendedSelection)
        self.outcome_table.setSelectionBehavior(TableWidget.SelectRows)
        # 禁止直接编辑
        self.outcome_table.setEditTriggers(TableWidget.NoEditTriggers)

        self.main_layout.addWidget(self.outcome_table)

        # 搜索栏（移动到列表下方）
        search_layout = QHBoxLayout()
        self.search_edit = LineEdit()
        self.search_edit.setPlaceholderText("输入关键词搜索成果")
        self.search_edit.textChanged.connect(self.apply_filters) # Connect to apply_filters
        search_layout.addWidget(self.search_edit)

        self.type_filter = ComboBox()
        self.type_filter.addItem("全部类型")
        for type_enum in OutcomeType: # Use different variable name
            self.type_filter.addItem(type_enum.value)
        self.type_filter.currentTextChanged.connect(self.apply_filters) # Connect to apply_filters
        search_layout.addWidget(self.type_filter)

        self.status_filter = ComboBox()
        self.status_filter.addItem("全部状态")
        for status_enum in OutcomeStatus: # Use different variable name
            self.status_filter.addItem(status_enum.value)
        self.status_filter.currentTextChanged.connect(self.apply_filters) # Connect to apply_filters
        search_layout.addWidget(self.status_filter)
        
        # 日期范围筛选
        search_layout.addWidget(QLabel("发表/授权日期:"))
        self.start_date = CompactDateEdit()
        self.end_date = CompactDateEdit()
        # 设置默认日期范围
        if self.current_project:
            start_qdate = QDate(self.current_project.start_date.year, self.current_project.start_date.month, self.current_project.start_date.day)
            self.start_date.setDate(start_qdate)
        else:
            self.start_date.setDate(QDate(QDate.currentDate().year() - 1, 1, 1))  # 默认为当前年份的前一年1月1日
        self.end_date.setDate(QDate.currentDate())
        
        self.start_date.dateChanged.connect(self.apply_filters)
        self.end_date.dateChanged.connect(self.apply_filters)
        
        search_layout.addWidget(self.start_date)
        search_layout.addWidget(QLabel("至"))
        search_layout.addWidget(self.end_date)

        # Add reset button
        reset_btn = PushButton("重置筛选")
        reset_btn.clicked.connect(self.reset_filters)
        search_layout.addWidget(reset_btn)
        # 增加分隔线
        search_layout.addSpacing(10)
        
        # 导出按钮
        export_excel_btn = PushButton("导出信息")
        export_excel_btn.clicked.connect(self.export_outcome_excel)
        search_layout.addWidget(export_excel_btn)

        export_attachment_btn = PushButton("导出附件")
        export_attachment_btn.clicked.connect(self.export_outcome_attachments)
        search_layout.addWidget(export_attachment_btn)
        self.main_layout.addLayout(search_layout)
        # 添加右键菜单
        self.outcome_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.outcome_table.customContextMenuRequested.connect(self.show_outcome_context_menu)

    def _on_project_selected(self, index):
        """Handles project selection change."""
        selected_data = self.project_selector.itemData(index)
        if selected_data == "all":
            self.current_project = None # Set current_project to None for "全部数据"
            UIUtils.show_success(self, "项目成果", "'全部成果' 已选择")
            self.load_outcome(load_all=True) # Load all outcomes
        elif selected_data and isinstance(selected_data, Project):
            self.current_project = selected_data
            UIUtils.show_success(self, "项目成果", f"项目已选择: {self.current_project.name}")
            self.load_outcome() # Load outcome for the selected project
        else:
            self.current_project = None
            self.outcome_table.setRowCount(0) # Clear table if no project selected
            UIUtils.show_info(self, "项目成果", "请选择一个项目以查看成果")

    def load_outcome(self, load_all=False):
        """Loads outcomes into memory and populates the table.
           If load_all is True, loads outcomes for all projects.
           Otherwise, loads outcomes for the current project.
        """
        self.all_outcomes = []
        self.current_outcomes = []
        self.outcome_table.setRowCount(0) # Clear table first

        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            if load_all:
                print("OutcomeWidget: Loading all outcomes.")
                self.all_outcomes = session.query(ProjectOutcome).order_by(ProjectOutcome.publish_date.desc()).all()
            elif self.current_project:
                print(f"OutcomeWidget: Loading outcome for project ID: {self.current_project.id}")
                self.all_outcomes = session.query(ProjectOutcome).filter(
                    ProjectOutcome.project_id == self.current_project.id
                ).order_by(ProjectOutcome.publish_date.desc()).all() # Order by publish date
            else:
                print("OutcomeWidget: No project selected and load_all is False, cannot load outcome.")
                return

            self.current_outcomes = self.all_outcomes[:] # Initial view shows all
            self._populate_table(self.current_outcomes)
        except Exception as e:
             UIUtils.show_error(self, "错误", f"加载成果数据失败: {e}")
             print(f"Error loading outcomes: {e}")
        finally:
            session.close()

    def _populate_table(self, outcomes_list):
        """Populates the table based on the provided list of ProjectOutcome objects."""
        self.outcome_table.setSortingEnabled(False) # Disable sorting during population
        # self.outcome_table.setRowCount(0) # Remove clearing here

        # Set the row count based on the number of outcomes
        self.outcome_table.setRowCount(len(outcomes_list))

        for row, outcome in enumerate(outcomes_list):
            # self.outcome_table.insertRow(row) # Remove insertRow

            # --- Populate Cells ---
            # Col 0: Name
            name_item = QTableWidgetItem(outcome.name)
            name_item.setData(Qt.UserRole, outcome.id) # Store ID here
            self.outcome_table.setItem(row, 0, name_item)
            # Col 1: Type
            type_item = QTableWidgetItem(outcome.type.value)
            type_item.setTextAlignment(Qt.AlignCenter)
            self.outcome_table.setItem(row, 1, type_item)
            # Col 2: Status
            status_item = QTableWidgetItem(outcome.status.value)
            status_item.setTextAlignment(Qt.AlignCenter)
            self.outcome_table.setItem(row, 2, status_item)
            # Col 3: Authors
            authors_item = QTableWidgetItem(outcome.authors or "")
            authors_item.setTextAlignment(Qt.AlignCenter)
            self.outcome_table.setItem(row, 3, authors_item)
            # Col 4: Submit Date
            submit_date_str = str(outcome.submit_date) if outcome.submit_date else ""
            submit_date_item = QTableWidgetItem(submit_date_str)
            submit_date_item.setTextAlignment(Qt.AlignCenter)
            submit_date_item.setData(Qt.UserRole + 1, outcome.submit_date) # Store date for sorting
            self.outcome_table.setItem(row, 4, submit_date_item)
            # Col 5: Publish Date
            publish_date_str = str(outcome.publish_date) if outcome.publish_date else ""
            publish_date_item = QTableWidgetItem(publish_date_str)
            publish_date_item.setTextAlignment(Qt.AlignCenter)
            publish_date_item.setData(Qt.UserRole + 1, outcome.publish_date) # Store date for sorting
            self.outcome_table.setItem(row, 5, publish_date_item)
            # Col 6: Journal
            journal_item = QTableWidgetItem(outcome.journal or "")
            self.outcome_table.setItem(row, 6, journal_item)
            # Col 7: Description
            description_item = QTableWidgetItem(outcome.description or "")
            self.outcome_table.setItem(row, 7, description_item)
            # Col 8: Attachment Button (Index changed from 9 to 8)
            container = create_attachment_button(
                item_id=outcome.id,
                attachment_path=outcome.attachment_path,
                handle_attachment_func=self._handle_outcome_attachment_new, # Pass the RENAMED method reference
                parent_widget=self,
                item_type='outcome'
            )
            self.outcome_table.setCellWidget(row, 8, container) # 附件列索引从9改为8

        self.outcome_table.setSortingEnabled(True) # Re-enable sorting

    def apply_filters(self):
        """Applies filters based on search keyword, type, status, and date range using FilterUtils."""
        if not self.all_outcomes: # Don't filter if nothing is loaded
             return

        keyword = self.search_edit.text() # Keep original case, FilterUtils handles lowercasing
        outcome_type_filter = self.type_filter.currentText()
        outcome_status_filter = self.status_filter.currentText()
        
        # 获取日期范围
        start_date = self.start_date.date().toPython() if self.start_date.date() else None
        end_date = self.end_date.date().toPython() if self.end_date.date() else None

        filter_criteria = {
            'keyword': keyword,
            'keyword_attributes': ['name', 'authors', 'journal', 'description'], # Removed 'remarks'
            'outcome_type': outcome_type_filter,
            'status': outcome_status_filter,
            'start_date': start_date,
            'end_date': end_date
        }

        # Define how filter keys map to ProjectOutcome object attributes
        attribute_mapping = {
            'outcome_type': 'type', # Filter key 'outcome_type' maps to ProjectOutcome.type
            'status': 'status',     # Filter key 'status' maps to ProjectOutcome.status
            'date': 'publish_date'  # 使用发表/授权日期进行筛选
        }

        # Apply filters using FilterUtils
        self.current_outcomes = FilterUtils.apply_filters(
            self.all_outcomes,
            filter_criteria,
            attribute_mapping
        )

        # Update the table with filtered data
        self._populate_table(self.current_outcomes)
        
    def reset_filters(self):
        """重置所有筛选条件到默认值"""
        # 重置搜索框
        self.search_edit.clear()
        
        # 重置类型筛选
        self.type_filter.setCurrentIndex(0)  # 设置为"全部类型"
        
        # 重置状态筛选
        self.status_filter.setCurrentIndex(0)  # 设置为"全部状态"
        
        # 重置日期范围
        if self.current_project:
            start_qdate = QDate(self.current_project.start_date.year, self.current_project.start_date.month, self.current_project.start_date.day)
            self.start_date.setDate(start_qdate)
        else:
            self.start_date.setDate(QDate(QDate.currentDate().year() - 1, 1, 1))  # 默认为当前年份的前一年1月1日
        self.end_date.setDate(QDate.currentDate())
        
        # 重新加载所有数据
        self.current_outcomes = self.all_outcomes[:]
        self._populate_table(self.current_outcomes)

    def reset_filters(self):
        """Resets all filter inputs and reapplies filters."""
        self.search_edit.clear()
        self.type_filter.setCurrentText("全部类型")
        self.status_filter.setCurrentText("全部状态")
        
        # 重置日期范围
        if self.current_project:
            start_qdate = QDate(self.current_project.start_date.year, self.current_project.start_date.month, self.current_project.start_date.day)
            self.start_date.setDate(start_qdate)
        else:
            self.start_date.setDate(QDate(QDate.currentDate().year() - 1, 1, 1))  # 默认为当前年份的前一年1月1日
        self.end_date.setDate(QDate.currentDate())
        
        self.apply_filters() # Re-apply filters to show all items

    # _generate_outcome_path 方法已移除，使用 attachment_utils.py 中的 generate_attachment_path 函数

    def add_outcome(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return

        # Note: OutcomeDialog doesn't have a file selection field currently.
        # Assuming attachment is added/replaced via the button after creation.
        dialog = OutcomeDialog(self, project=self.current_project)
        if dialog.exec():
            Session = sessionmaker(bind=self.engine)
            session = Session()
            try:
                outcome = ProjectOutcome(
                    project_id=self.current_project.id,
                    name=dialog.name_edit.text(),
                    type=OutcomeType(dialog.type_combo.currentText()),
                    status=OutcomeStatus(dialog.status_combo.currentText()),
                    authors=dialog.authors_edit.toPlainText(),
                    submit_date=dialog.submit_date.date().toPython(),
                    publish_date=dialog.publish_date.date().toPython(),
                    journal=dialog.journal_edit.text(),
                    description=dialog.description_edit.toPlainText(),
                    attachment_path=None # Initially no attachment path
                )
                session.add(outcome)
                session.commit()

                # 添加操作日志
                actionlog = Actionlog(
                    project_id=self.current_project.id,
                    project_outcome_id=outcome.id,
                    type="成果",
                    action="新增",
                    description=f"新增成果: {outcome.name}",
                    operator="当前用户", # TODO: 获取当前登录用户
                    related_info=f"类型: {outcome.type.value}, 状态: {outcome.status.value}"
                )
                session.add(actionlog)
                session.commit() # 提交日志

                self.load_outcome()
                UIUtils.show_success(self, "成功", "成果添加成功 (请稍后添加附件)")
            except Exception as e:
                session.rollback()
                UIUtils.show_error(self, "数据库错误", f"保存成果信息失败：{e}")
            finally:
                session.close()

    
    def _handle_outcome_attachment_new(self, event, btn):
        """处理成果附件操作，使用通用附件处理函数"""
        outcome_id = btn.property("item_id")
        Session = sessionmaker(bind=self.engine)
        
        # 定义获取成果对象的函数
        def get_outcome(session, outcome_id):
            return session.query(ProjectOutcome).get(outcome_id)
        
        # 调用通用附件处理函数
        handle_attachment(
            event=event,
            btn=btn,
            item_id=outcome_id,
            item_type="outcome",
            session_maker=Session,
            parent_widget=self,
            get_item_func=get_outcome,
            attachment_attr="attachment_path",
            project_attr="project_id",
            base_folder="outcomes"
        )
    # 剩余的附件处理代码已移除，使用 attachment_utils.py 中的 execute_attachment_action 函数

    def edit_outcome(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return
        selected_items = self.outcome_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择要编辑的成果")
            return

        row = selected_items[0].row()
        # Get ID from UserRole of the first column item
        id_item = self.outcome_table.item(row, 0)
        if not id_item: return
        outcome_id = id_item.data(Qt.UserRole)

        # Use the stored engine
        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            outcome = session.query(ProjectOutcome).filter(
                ProjectOutcome.id == outcome_id,
                ProjectOutcome.project_id == self.current_project.id
            ).first()
            if not outcome:
                UIUtils.show_error(self, "错误", "未找到选中的成果记录")
                return

            dialog = OutcomeDialog(self, outcome=outcome)
            if dialog.exec():
                outcome.name = dialog.name_edit.text()
                outcome.type = OutcomeType(dialog.type_combo.currentText())
                outcome.status = OutcomeStatus(dialog.status_combo.currentText())
                outcome.authors = dialog.authors_edit.text()
                outcome.submit_date = dialog.submit_date.date().toPython()
                outcome.publish_date = dialog.publish_date.date().toPython()
                outcome.journal = dialog.journal_edit.text()
                outcome.description = dialog.description_edit.text()
                # outcome.remarks = dialog.remarks_edit.text() # Removed remarks update
                # Note: Attachment path is handled by handle_outcome_attachment
                session.commit()

                # 添加操作日志
                actionlog = Actionlog(
                    project_id=self.current_project.id,
                    project_outcome_id=outcome.id,
                    type="成果",
                    action="编辑",
                    description=f"编辑成果: {outcome.name}",
                    operator="当前用户", # TODO: 获取当前登录用户
                    related_info=f"类型: {outcome.type.value}, 状态: {outcome.status.value}"
                )
                session.add(actionlog)
                session.commit() # 提交日志

                self.load_outcome() # Reload all outcomes
                UIUtils.show_success(self, "成功", "成果编辑成功")
        except Exception as e: # Catch potential DB errors
             session.rollback()
             UIUtils.show_error(self, "数据库错误", f"编辑成果信息失败：{e}")
        finally:
            session.close()

    def delete_outcome(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return
        selected_rows = sorted(list(set(item.row() for item in self.outcome_table.selectedItems())), reverse=True)
        if not selected_rows:
            UIUtils.show_warning(self, "警告", "请先选择要删除的成果")
            return

        outcome_ids_to_delete = []
        for row in selected_rows:
            id_item = self.outcome_table.item(row, 0)
            if id_item:
                outcome_ids_to_delete.append(id_item.data(Qt.UserRole))

        if not outcome_ids_to_delete:
             UIUtils.show_error(self, "错误", "无法获取选中的成果ID")
             return

        confirm_dialog = Dialog(
            title='确认删除',
            content=f'确定要删除选中的 {len(outcome_ids_to_delete)} 条成果记录吗？相关附件也将被删除（如果存在）。此操作不可恢复。',
            parent=self
        )
        confirm_dialog.cancelButton.setText('取消')
        confirm_dialog.yesButton.setText('确认删除')

        if confirm_dialog.exec():
            # Use the stored engine
            Session = sessionmaker(bind=self.engine)
            session = Session()
            deleted_count = 0
            try:
                for outcome_id in outcome_ids_to_delete:
                    outcome = session.query(ProjectOutcome).filter(
                        ProjectOutcome.id == outcome_id,
                        ProjectOutcome.project_id == self.current_project.id
                    ).first()
                    if outcome:
                        # 删除附件文件
                        if outcome.attachment_path and os.path.exists(outcome.attachment_path):
                            try:
                                os.remove(outcome.attachment_path)
                            except OSError as e:
                                print(f"Warning: Could not delete attachment file {outcome.attachment_path}: {e}")
                                # Decide if deletion should proceed or stop

                        session.delete(outcome)
                        deleted_count += 1

                        # 添加操作日志
                        actionlog = Actionlog(
                            project_id=self.current_project.id,
                            type="成果",
                            action="删除",
                            description=f"删除成果: {outcome.name}",
                            operator="当前用户", # TODO: 获取当前登录用户
                            related_info=f"类型: {outcome.type.value}, 状态: {outcome.status.value}"
                        )
                        session.add(actionlog)

                session.commit() # 在循环外部统一提交
                self.load_outcome() # Reload all outcomes
                UIUtils.show_success(self, "成功", f"成功删除 {deleted_count} 条成果记录")
            except Exception as e: # Catch potential DB errors
                 session.rollback()
                 UIUtils.show_error(self, "数据库错误", f"删除成果失败：{e}")
            finally:
                session.close()

   

    def show_outcome_context_menu(self, pos):
        """显示成果表格的右键菜单"""
        menu = RoundMenu(parent=self)

        # 获取右键点击的单元格
        item = self.outcome_table.itemAt(pos)
        if item:
            # 添加复制操作
            copy_action = Action(FluentIcon.COPY, "复制", self)
            copy_action.triggered.connect(lambda: self.copy_cell_content(item))
            menu.addAction(copy_action)

        # 显示菜单
        menu.exec_(self.outcome_table.viewport().mapToGlobal(pos))

    def export_outcome_excel(self):
        """导出成果信息到Excel"""
        if not self.current_project or not self.current_outcomes:
            UIUtils.show_warning(self, "警告", "没有可导出的成果数据")
            return

        export_dir = QFileDialog.getExistingDirectory(
            self, "选择导出目录",
            os.path.expanduser("~")
        )
        if not export_dir:
            return

        try:
            # 准备数据
            data = []
            for outcome in self.current_outcomes:
                data.append({
                    "成果名称": outcome.name,
                    "成果类型": outcome.type.value,
                    "成果状态": outcome.status.value,
                    "作者/完成人": outcome.authors or "",
                    "投稿/申请日期": str(outcome.submit_date) if outcome.submit_date else "",
                    "发表/授权日期": str(outcome.publish_date) if outcome.publish_date else "",
                    "期刊/授权单位": outcome.journal or "",
                    "成果描述": outcome.description or "",
                    "附件路径": outcome.attachment_path or ""
                })

            # 创建DataFrame并导出
            df = pd.DataFrame(data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = os.path.join(export_dir, f"成果信息_{self.current_project.financial_code}_{timestamp}.xlsx")
            
            df.to_excel(export_path, index=False)
            UIUtils.show_success(self, "成功", f"成果信息已导出到: {export_path}")

        except Exception as e:
            UIUtils.show_error(self, "错误", f"导出成果信息失败: {str(e)}")

    def export_outcome_attachments(self):
        """导出成果附件"""
        if not self.current_project or not self.current_outcomes:
            UIUtils.show_warning(self, "警告", "没有可导出的成果附件")
            return

        export_dir = QFileDialog.getExistingDirectory(
            self, "选择导出目录",
            os.path.expanduser("~")
        )
        if not export_dir:
            return

        try:
            # 创建项目子目录
            project_dir = os.path.join(export_dir, f"成果附件_{self.current_project.financial_code}")
            os.makedirs(project_dir, exist_ok=True)

            # 导出附件
            exported_count = 0
            for outcome in self.current_outcomes:
                if outcome.attachment_path and os.path.exists(outcome.attachment_path):
                    filename = os.path.basename(outcome.attachment_path)
                    dest_path = os.path.join(project_dir, filename)
                    
                    # 避免文件名冲突
                    counter = 1
                    while os.path.exists(dest_path):
                        base, ext = os.path.splitext(filename)
                        dest_path = os.path.join(project_dir, f"{base}_{counter}{ext}")
                        counter += 1
                    
                    shutil.copy2(outcome.attachment_path, dest_path)
                    exported_count += 1

            if exported_count > 0:
                UIUtils.show_success(self, "成功", f"成功导出 {exported_count} 个成果附件到: {project_dir}")
            else:
                UIUtils.show_warning(self, "警告", "没有找到可导出的成果附件")

        except Exception as e:
            UIUtils.show_error(self, "错误", f"导出成果附件失败: {str(e)}")

    def copy_cell_content(self, item):
        """复制单元格内容"""
        if item:
            # 获取单元格内容
            content = item.text()
            clipboard = QApplication.clipboard()
            clipboard.setText(content)