import os # Ensure os is imported
import shutil # Add shutil
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QDialog, QLabel, QHeaderView, QFileDialog, QApplication # Added QHeaderView, QFileDialog, QApplication
from PySide6.QtCore import Qt, QSize, QPoint # Added QSize and QPoint
from PySide6.QtGui import QFont, QIcon # 确保 QFont 已导入, Add QIcon
from qfluentwidgets import TitleLabel, FluentIcon, LineEdit, ComboBox, DateEdit, InfoBar, BodyLabel, PushButton, TableWidget, TableItemDelegate, Dialog, RoundMenu, Action, PlainTextEdit
# 需要在文件顶部导入
from ...utils.ui_utils import UIUtils
from ...models.database import Project, Base, get_engine, sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum as SQLEnum, Engine # Added Engine type hint
from enum import Enum
from datetime import datetime
from ...utils.attachment_utils import (
    create_attachment_button, # Keep
    sanitize_filename, ensure_directory_exists, get_timestamp_str, get_attachment_icon_path,
    view_attachment, download_attachment, ROOT_DIR # Import necessary utils
)
from ...utils.filter_utils import FilterUtils # Import FilterUtils


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
        self.authors_edit = PlainTextEdit() # Changed to PlainTextEdit
        self.authors_edit.setPlaceholderText("请输入作者或完成人")
        self.authors_edit.setFixedHeight(80) # Set height for multi-line
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
        self.description_edit = PlainTextEdit() # Changed to PlainTextEdit
        self.description_edit.setPlaceholderText("请输入成果描述")
        self.description_edit.setFixedHeight(120) # Set height for multi-line
        description_layout.addWidget(self.description_edit)
        layout.addLayout(description_layout)



        layout.addStretch() # Add stretch before buttons

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
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
        self.authors_edit.setPlainText(self.outcome.authors or "") # Use setPlainText
        if self.outcome.submit_date:
            self.submit_date.setDate(self.outcome.submit_date)
        if self.outcome.publish_date:
            self.publish_date.setDate(self.outcome.publish_date)
        self.journal_edit.setText(self.outcome.journal or "")
        self.description_edit.setPlainText(self.outcome.description or "") # Use setPlainText

class ProjectOutcomeWidget(QWidget): # 重命名 Widget 类
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
        selector_layout = QHBoxLayout()
        selector_label = TitleLabel("项目成果-", self)
        self.project_selector = UIUtils.create_project_selector(self.engine, self)
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.project_selector)
        selector_layout.addStretch()
        self.main_layout.addLayout(selector_layout)
        self.project_selector.currentIndexChanged.connect(self._on_project_selected)

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
        self.outcome_table.setWordWrap(False)
        self.outcome_table.setItemDelegate(TableItemDelegate(self.outcome_table))
        UIUtils.set_table_style(self.outcome_table) # 应用通用样式

        # 设置列宽模式和排序
        header = self.outcome_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSortIndicatorShown(True) # 启用排序
        header.sectionClicked.connect(self.sort_table) # 连接排序信号

        # 隐藏行号

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

        self.outcome_table.setSelectionMode(TableWidget.ExtendedSelection)
        self.outcome_table.setSelectionBehavior(TableWidget.SelectRows)

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

        reset_btn = PushButton("重置筛选")
        reset_btn.clicked.connect(self.reset_filters)
        search_layout.addWidget(reset_btn)

        self.main_layout.addLayout(search_layout)

        # 添加右键菜单
        self.outcome_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.outcome_table.customContextMenuRequested.connect(self.show_outcome_context_menu)

    def _on_project_selected(self, index):
        """Handles project selection change."""
        selected_project = self.project_selector.itemData(index)
        if selected_project and isinstance(selected_project, Project):
            self.current_project = selected_project
            print(f"OutcomeWidget: Project selected - {self.current_project.name}")
            self.load_outcome() # Load outcome for the selected project
        else:
            self.current_project = None
            self.outcome_table.setRowCount(0) # Clear table if no project selected
            print("OutcomeWidget: No valid project selected.")

    def load_outcome(self):
        """Loads all outcomes for the current project into memory and populates the table."""
        self.all_outcomes = []
        self.current_outcomes = []
        self.outcome_table.setRowCount(0) # Clear table first
        if not self.current_project:
            print("OutcomeWidget: No project selected, cannot load outcome.")
            return

        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            print(f"OutcomeWidget: Loading outcome for project ID: {self.current_project.id}")
            self.all_outcomes = session.query(ProjectOutcome).filter(
                ProjectOutcome.project_id == self.current_project.id
            ).order_by(ProjectOutcome.publish_date.desc()).all() # Order by publish date
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
        self.outcome_table.setRowCount(0) # Clear table first

        for row, outcome in enumerate(outcomes_list):
            self.outcome_table.insertRow(row)

            name_item = QTableWidgetItem(outcome.name)
            name_item.setData(Qt.UserRole, outcome.id) # Store ID here
            self.outcome_table.setItem(row, 0, name_item)

            type_item = QTableWidgetItem(outcome.type.value)
            type_item.setTextAlignment(Qt.AlignCenter)
            self.outcome_table.setItem(row, 1, type_item)

            status_item = QTableWidgetItem(outcome.status.value)
            status_item.setTextAlignment(Qt.AlignCenter)
            self.outcome_table.setItem(row, 2, status_item)

            authors_item = QTableWidgetItem(outcome.authors or "")
            authors_item.setTextAlignment(Qt.AlignCenter)
            self.outcome_table.setItem(row, 3, authors_item)

            submit_date_str = str(outcome.submit_date) if outcome.submit_date else ""
            submit_date_item = QTableWidgetItem(submit_date_str)
            submit_date_item.setTextAlignment(Qt.AlignCenter)
            submit_date_item.setData(Qt.UserRole + 1, outcome.submit_date) # Store date for sorting
            self.outcome_table.setItem(row, 4, submit_date_item)

            publish_date_str = str(outcome.publish_date) if outcome.publish_date else ""
            publish_date_item = QTableWidgetItem(publish_date_str)
            publish_date_item.setTextAlignment(Qt.AlignCenter)
            publish_date_item.setData(Qt.UserRole + 1, outcome.publish_date) # Store date for sorting
            self.outcome_table.setItem(row, 5, publish_date_item)

            journal_item = QTableWidgetItem(outcome.journal or "")
            self.outcome_table.setItem(row, 6, journal_item)

            description_item = QTableWidgetItem(outcome.description or "")
            self.outcome_table.setItem(row, 7, description_item)


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
        """Applies filters based on search keyword, type, and status using FilterUtils."""
        if not self.all_outcomes: # Don't filter if nothing is loaded
             return

        keyword = self.search_edit.text() # Keep original case, FilterUtils handles lowercasing
        outcome_type_filter = self.type_filter.currentText()
        outcome_status_filter = self.status_filter.currentText()

        filter_criteria = {
            'keyword': keyword,
            'keyword_attributes': ['name', 'authors', 'journal', 'description'], # Attributes to search in
            'outcome_type': outcome_type_filter,
            'outcome_status': outcome_status_filter
        }

        attribute_mapping = {
            'outcome_type': 'type', # Map filter key to object attribute
            'outcome_status': 'status' # Map filter key to object attribute
        }

        self.current_outcomes = FilterUtils.apply_filters(
            self.all_outcomes,
            filter_criteria,
            attribute_mapping
        )
        self._populate_table(self.current_outcomes)

    def reset_filters(self):
        """Resets filter inputs and reapplies filters."""
        self.search_edit.clear()
        self.type_filter.setCurrentText("全部类型")
        self.status_filter.setCurrentText("全部状态")
        self.apply_filters() # Re-apply filters to show all items

    def _generate_outcome_path(self, project, outcome_type_enum, original_filename):
        """Generates the specific path for a project outcome based on business rules."""
        if not project or not outcome_type_enum or not original_filename:
            print("Error: Missing project, outcome type, or filename for path generation.")
            return None

        base_folder = "outcomes" # Changed base folder
        project_code = project.financial_code if project.financial_code else "unknown_project"
        outcome_type_str = sanitize_filename(outcome_type_enum.value)
        timestamp = get_timestamp_str() # Get current timestamp string

        original_basename = os.path.basename(original_filename)
        base_name, ext = os.path.splitext(original_basename)
        sanitized_base_name = sanitize_filename(base_name)

        new_filename = f"{timestamp}_{sanitized_base_name}{ext}"

        target_dir = os.path.join(ROOT_DIR, base_folder, project_code, outcome_type_str)
        full_path = os.path.join(target_dir, new_filename)

        return os.path.normpath(full_path)

    def add_outcome(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return

        dialog = OutcomeDialog(self, project=self.current_project)
        if dialog.exec():

            Session = sessionmaker(bind=self.engine)
            session = Session()
            try:
                outcome = ProjectOutcome(
                    project_id=self.current_project.id,
                    name=dialog.name_edit.text().strip(),
                    type=OutcomeType(dialog.type_combo.currentText()),
                    status=OutcomeStatus(dialog.status_combo.currentText()),
                    authors=dialog.authors_edit.toPlainText().strip(), # Use toPlainText
                    submit_date=dialog.submit_date.date().toPython(),
                    publish_date=dialog.publish_date.date().toPython(),
                    journal=dialog.journal_edit.text().strip(),
                    description=dialog.description_edit.toPlainText().strip(), # Use toPlainText
                )
                session.add(outcome)
                session.commit()
                self.load_outcome() # Reload outcomes to show the new one
                UIUtils.show_success(self, "成功", "成果添加成功")
            except Exception as e:
                session.rollback()
                UIUtils.show_error(self, "错误", f"添加成果到数据库失败: {e}")
            finally:
                session.close()

    def _handle_outcome_attachment_new(self, event, btn):
        """Handles clicks on the attachment button (add/view/download/delete)."""
        outcome_id = btn.property("item_id")
        action_type = btn.property("action_type") # 'add', 'view', 'download', 'delete'

        if not outcome_id:
            print("Error: No outcome ID found on button.")
            return

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            if action_type == 'add':
                outcome = session.query(ProjectOutcome).filter(ProjectOutcome.id == outcome_id).first()
                if not outcome:
                     UIUtils.show_warning(self, "警告", "未找到关联的成果记录")
                     return

                source_file_path, _ = QFileDialog.getOpenFileName(self, "选择成果附件")
                if not source_file_path:
                    return # User cancelled

                new_file_path = self._generate_outcome_path(
                    project=self.current_project, # Assumes current_project is set
                    outcome_type_enum=outcome.type,
                    original_filename=source_file_path
                )
                if not new_file_path:
                    UIUtils.show_error(self, "错误", "无法生成附件保存路径")
                    return

                target_dir = os.path.dirname(new_file_path)
                ensure_directory_exists(target_dir)

                try:
                    shutil.copy2(source_file_path, new_file_path)
                except Exception as e:
                    UIUtils.show_error(self, "错误", f"复制附件失败: {e}")
                    return

                outcome.attachment_path = new_file_path
                session.commit()
                btn.setIcon(FluentIcon.DOCUMENT)
                btn.setToolTip(f"查看/下载: {os.path.basename(new_file_path)}")
                btn.setProperty("action_type", "view") # Change action type for next click
                UIUtils.show_success(self, "成功", "附件已添加")

            elif action_type == 'delete':
                 outcome = session.query(ProjectOutcome).filter(ProjectOutcome.id == outcome_id).first()
                 if outcome and outcome.attachment_path:
                     file_to_delete = outcome.attachment_path
                     confirm_dialog = Dialog(
                         '确认删除附件',
                         f'确定要删除附件文件吗？\n{os.path.basename(file_to_delete)}\n此操作不可恢复！',
                         self
                     )
                     if confirm_dialog.exec():
                         try:
                             os.remove(file_to_delete)
                             outcome.attachment_path = None
                             session.commit()
                             btn.setIcon(FluentIcon.ADD)
                             btn.setToolTip("添加附件")
                             btn.setProperty("action_type", "add")
                             UIUtils.show_success(self, "成功", "附件已删除")
                         except OSError as e:
                             UIUtils.show_error(self, "错误", f"删除附件文件失败: {e}")
                         except Exception as e:
                             session.rollback()
                             UIUtils.show_error(self, "错误", f"更新数据库失败: {e}")
                 else:
                      UIUtils.show_warning(self, "警告", "未找到附件或附件已被删除")

            else: # Handle 'view' and 'download'
                self._execute_outcome_action_new(action_type, outcome_id, btn, session)

        except Exception as e:
             UIUtils.show_error(self, "操作失败", f"处理成果附件时出错: {e}")
             print(f"Error handling outcome attachment: {e}") # Log detailed error
        finally:
            session.close()

    def _execute_outcome_action_new(self, action_type, outcome_id, btn, session):
        """Executes view or download action for an outcome."""
        outcome = session.query(ProjectOutcome).filter(ProjectOutcome.id == outcome_id).first()
        if not outcome or not outcome.attachment_path:
            UIUtils.show_warning(self, "警告", "未找到成果附件或文件路径无效")
            btn.setIcon(FluentIcon.ADD)
            btn.setToolTip("添加附件")
            btn.setProperty("action_type", "add")
            return

        file_path = outcome.attachment_path
        if not os.path.exists(file_path):
            UIUtils.show_error(self, "错误", f"附件文件不存在: {file_path}")
            try:
                outcome.attachment_path = None
                session.commit()
                btn.setIcon(FluentIcon.ADD)
                btn.setToolTip("添加附件")
                btn.setProperty("action_type", "add")
            except Exception as e:
                 session.rollback()
                 print(f"Error updating DB for missing file: {e}")
            return

        if action_type == 'view':
            view_attachment(file_path, self)
        elif action_type == 'download':
            original_filename = os.path.basename(file_path)
            _, ext = os.path.splitext(original_filename)
            suggested_filename = f"{sanitize_filename(outcome.name)}_附件{ext}" # Add suffix

            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "下载成果附件",
                suggested_filename,
                f"文件 (*{ext})"
            )
            if save_path:
                download_attachment(file_path, save_path, self)
        else:
            print(f"Unknown action type: {action_type}")


    def edit_outcome(self):
        selected_items = self.outcome_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请选择要编辑的成果")
            return

        row = selected_items[0].row()
        outcome_id = self.outcome_table.item(row, 0).data(Qt.UserRole)

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            outcome = session.query(ProjectOutcome).filter(
                ProjectOutcome.id == outcome_id
            ).first()

            if not outcome:
                UIUtils.show_warning(self, "警告", "未找到选中的成果")
                return

            dialog = OutcomeDialog(self, outcome=outcome, project=self.current_project)
            if dialog.exec():
                outcome.name = dialog.name_edit.text().strip()
                outcome.type = OutcomeType(dialog.type_combo.currentText())
                outcome.status = OutcomeStatus(dialog.status_combo.currentText())
                outcome.authors = dialog.authors_edit.toPlainText().strip() # Use toPlainText
                outcome.submit_date = dialog.submit_date.date().toPython()
                outcome.publish_date = dialog.publish_date.date().toPython()
                outcome.journal = dialog.journal_edit.text().strip()
                outcome.description = dialog.description_edit.toPlainText().strip() # Use toPlainText

                session.commit()
                self.load_outcome() # Reload to show changes
                UIUtils.show_success(self, "成功", "成果信息更新成功")

        except Exception as e:
            session.rollback()
            UIUtils.show_error(self, "错误", f"编辑成果失败: {e}")
        finally:
            session.close()

    def delete_outcome(self):
        selected_items = self.outcome_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请选择要删除的成果")
            return

        outcome_ids_to_delete = list(set(self.outcome_table.item(item.row(), 0).data(Qt.UserRole) for item in selected_items))

        confirm_dialog = Dialog(
            '确认删除',
            f'确定要删除选中的 {len(outcome_ids_to_delete)} 个成果吗？\n此操作将同时删除关联的附件文件（如果存在），且不可恢复！',
            self
        )

        if confirm_dialog.exec():
            Session = sessionmaker(bind=self.engine)
            session = Session()
            deleted_count = 0
            failed_files = []
            try:
                for outcome_id in outcome_ids_to_delete:
                    outcome = session.query(ProjectOutcome).filter(
                        ProjectOutcome.id == outcome_id
                    ).first()
                    if outcome:
                        file_path_to_delete = outcome.attachment_path
                        session.delete(outcome)
                        session.flush() # Ensure delete happens before file removal attempt

                        if file_path_to_delete and os.path.exists(file_path_to_delete):
                            try:
                                os.remove(file_path_to_delete)
                            except OSError as e:
                                print(f"Error deleting attachment file {file_path_to_delete}: {e}")
                                failed_files.append(os.path.basename(file_path_to_delete))

                        deleted_count += 1

                session.commit()
                self.load_outcome() # Refresh the table

                if failed_files:
                    UIUtils.show_warning(
                        self, "删除部分失败",
                        f"成功删除 {deleted_count} 个成果记录。\n但以下附件文件删除失败，请手动处理：\n{', '.join(failed_files)}"
                    )
                elif deleted_count > 0:
                    UIUtils.show_success(self, "成功", f"成功删除 {deleted_count} 个成果及其关联附件")
                else:
                     UIUtils.show_warning(self, "未删除", "没有成果被删除（可能已被其他操作移除）")

            except Exception as e:
                session.rollback()
                UIUtils.show_error(self, "错误", f"删除成果过程中发生数据库错误: {e}")
            finally:
                session.close()


    def sort_table(self, column):
        """根据点击的列对 self.current_outcomes 列表进行排序并更新表格"""
        current_order = self.outcome_table.horizontalHeader().sortIndicatorOrder()
        order = Qt.AscendingOrder if current_order == Qt.DescendingOrder else Qt.DescendingOrder

        column_map = {
            0: 'name',
            1: 'type', # Sort by enum value
            2: 'status', # Sort by enum value
            3: 'authors',
            4: 'submit_date', # Use the stored date object
            5: 'publish_date', # Use the stored date object
            6: 'journal',
            7: 'description',
        }

        sort_attribute = column_map.get(column)
        if sort_attribute:
            def sort_key(outcome):
                value = getattr(outcome, sort_attribute, None)
                if isinstance(value, (OutcomeType, OutcomeStatus)):
                    return value.value # Sort by enum string value
                if value is None: # Handle None values for dates and strings
                    attr_type = type(getattr(ProjectOutcome, sort_attribute).type.python_type)
                    if attr_type is datetime.date:
                        return datetime.min.date()
                    else: # Assume string or similar
                        return ""
                if isinstance(value, str):
                    return value.lower() # Case-insensitive string sort
                return value # For dates, numbers, etc.

            reverse_sort = (order == Qt.DescendingOrder)
            self.current_outcomes.sort(key=sort_key, reverse=reverse_sort)
            self._populate_table(self.current_outcomes)
            self.outcome_table.horizontalHeader().setSortIndicator(column, order)

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

    def copy_cell_content(self, item):
        """复制单元格内容"""
        if item:
            # 获取单元格内容
            content = item.text()
            clipboard = QApplication.clipboard()
            clipboard.setText(content)