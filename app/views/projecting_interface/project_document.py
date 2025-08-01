import os # Ensure os is imported
import shutil # Ensure shutil is imported
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem, QFileDialog, QDialog, QHeaderView, QApplication
from PySide6.QtCore import Qt, QPoint 
from PySide6.QtGui import QIcon 
from qfluentwidgets import TitleLabel, FluentIcon, ComboBox, LineEdit, Dialog, BodyLabel, PushButton, TableWidget, TableItemDelegate, RoundMenu, Action, PlainTextEdit, ToolTipFilter, ToolTipPosition
from ...models.database import Project, sessionmaker 
from ...utils.ui_utils import UIUtils
from ...models.database import Base, Actionlog # Project and sessionmaker already imported, add Actionlog
from sqlalchemy import Column, Integer, String, ForeignKey, Enum as SQLEnum, DateTime, Engine 
from enum import Enum
from datetime import datetime
from ...utils.attachment_utils import (
    create_attachment_button, # Keep
    sanitize_filename, ensure_directory_exists, get_timestamp_str, get_attachment_icon_path,
    view_attachment, download_attachment, ROOT_DIR, # Import necessary utils
    handle_attachment # 添加handle_attachment函数导入
)
from ...utils.filter_utils import FilterUtils # Import FilterUtils
import pandas as pd 

class DocumentType(Enum):
    APPLICATION = "申请材料"
    INITIATION = "开题材料"
    CONTRACT = "合同/任务书"
    RESEARCH_DATA = "研究数据"
    PROGRESS = "进展报告"
    OUTSOURCING = "外协材料"
    QUALITY = "质量管理"
    FINALIZATION = "结题材料"
    MEETING = "会议纪要"
    OTHER = "其他"

class ProjectDocument(Base):
    __tablename__ = 'project_documents'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    name = Column(String(100), nullable=False)  # 文档名称
    doc_type = Column(SQLEnum(DocumentType), nullable=False)  # 文档类型
    version = Column(String(20))  # 版本号
    description = Column(String(500))  # 文档描述
    file_path = Column(String(500))  # 文件路径
    upload_time = Column(DateTime, default=datetime.now)  # 上传时间
    keywords = Column(String(200))  # 关键词，用于检索

class DocumentDialog(QDialog):
    def __init__(self, parent=None, document=None):
        self.document = document
        super().__init__(parent)
        self.setWindowTitle("文档信息")
        self.setup_ui()
        if document:
            self.load_document_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10) # Adjust spacing to match ExpenseDialog
        # layout.setContentsMargins(24, 24, 24, 24) # Keep original margins or adjust as needed

        # 文档名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(BodyLabel("文档名称:"))
        self.name_edit = LineEdit()
        self.name_edit.setPlaceholderText("请输入文档名称，必填")
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # 文档类型
        type_layout = QHBoxLayout()
        type_layout.addWidget(BodyLabel("文档类型:"))
        self.type_combo = ComboBox()
        for doc_type in DocumentType:
            self.type_combo.addItem(doc_type.value)
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)

        # 版本号
        version_layout = QHBoxLayout()
        version_layout.addWidget(BodyLabel("版 本 号 :")) # Align label width
        self.version_edit = LineEdit()
        self.version_edit.setPlaceholderText("请输入版本号")
        version_layout.addWidget(self.version_edit)
        layout.addLayout(version_layout)        

        # 关键词
        keywords_layout = QHBoxLayout()
        keywords_layout.addWidget(BodyLabel("关 键 词 :")) # Align label width
        self.keywords_edit = LineEdit()
        self.keywords_edit.setPlaceholderText("请输入关键词（用逗号分隔）")
        keywords_layout.addWidget(self.keywords_edit)
        layout.addLayout(keywords_layout)

        # 文档描述
        description_layout = QHBoxLayout()
        description_layout.addWidget(BodyLabel("文档描述:"))
        # Change LineEdit to PlainTextEdit for multi-line input
        self.description_edit = PlainTextEdit()
        self.description_edit.setPlaceholderText("请输入文档描述")
        # Set a reasonable minimum height for the text edit
        self.description_edit.setFixedHeight(120)
        description_layout.addWidget(self.description_edit)
        layout.addLayout(description_layout)

        # 文件选择
        file_layout = QHBoxLayout()
        file_layout.addWidget(BodyLabel("选择文件:"))
        self.file_path_edit = LineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("点击右侧按钮选择文件") # Add placeholder
        file_layout.addWidget(self.file_path_edit)
        select_file_btn = PushButton("选择文件", self, FluentIcon.FOLDER) # Use PushButton with icon
        select_file_btn.clicked.connect(self.select_file)
        file_layout.addWidget(select_file_btn)
        layout.addLayout(file_layout)

        layout.addStretch() # Add stretch before buttons

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        # Use PushButton and add icons, push to the right
        save_btn = PushButton("保存", self, FluentIcon.SAVE) # Already PushButton, ensure correct icon
        cancel_btn = PushButton("取消", self, FluentIcon.CLOSE) # Already PushButton, ensure correct icon
        save_btn.clicked.connect(self.accept) # Connect accept for validation
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch() # Push buttons to the right
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if file_path:
            self.file_path_edit.setText(file_path)

    # Add accept method for validation like in ExpenseDialog
    def accept(self):
        """Validate input before accepting the dialog."""
        if not self.name_edit.text().strip():
            UIUtils.show_warning(
                title='警告',
                content='文档名称不能为空',
                parent=self
            )
            return
        # Check if a file is selected when adding a new document
        if not self.document and not self.file_path_edit.text():
             UIUtils.show_warning(
                title='警告',
                content='请选择要上传的文件',
                parent=self
            )
             return
        super().accept()

    def load_document_data(self):
        self.name_edit.setText(self.document.name)
        self.type_combo.setCurrentText(self.document.doc_type.value)
        self.version_edit.setText(self.document.version)
        self.description_edit.setPlainText(self.document.description or "") # Use setPlainText and handle None
        self.keywords_edit.setText(self.document.keywords)
        # self.uploader_edit.setText(self.document.uploader) # Removed uploader
        self.file_path_edit.setText(self.document.file_path)

class ProjectDocumentWidget(QWidget):
    # Modify __init__ to accept engine and remove project
    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent=parent)
        self.engine = engine
        self.current_project = None
        self.all_documents = [] # Store all loaded documents
        self.current_documents = [] # Store currently displayed documents
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
                print("ProjectDocumentWidget: Connected to project_updated signal.")
            else:
                 print("ProjectDocumentWidget: Could not find main window or project_updated signal.")
        except Exception as e:
            print(f"ProjectDocumentWidget: Error connecting signal: {e}")

    def _refresh_project_selector(self):
        """刷新项目选择下拉框的内容"""
        print("ProjectDocumentWidget: Refreshing project selector...")
        if not hasattr(self, 'project_selector') or not self.engine:
            print("ProjectDocumentWidget: Project selector or engine not initialized.")
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
            print(f"Error refreshing project selector in DocumentWidget: {e}")
            self.project_selector.addItem("加载项目出错", userData=None)
            self.project_selector.setEnabled(False)
        finally:
            session.close()
            print("ProjectDocumentWidget: Project selector refreshed.")

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(18, 18, 18, 18) # Add some margins
        self.main_layout.setSpacing(10)
        # --- Add Project Selector ---
        selector_layout = QHBoxLayout()
        selector_label = TitleLabel("项目文档-", self)
        selector_label.setToolTip("用于创建和管理项目的文档信息")
        selector_label.installEventFilter(ToolTipFilter(selector_label, showDelay=300, position=ToolTipPosition.RIGHT))
        self.project_selector = UIUtils.create_project_selector(self.engine, self)

        # 手动添加“全部数据”选项
        self.project_selector.insertItem(0, "全部文档", userData="all")
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.project_selector)
        selector_layout.addStretch()
        self.main_layout.addLayout(selector_layout)
        # Connect signal after UI setup
        self.project_selector.currentIndexChanged.connect(self._on_project_selected)
        # --- Project Selector End ---

        # 按钮栏
        add_btn = UIUtils.create_action_button("添加文档", FluentIcon.ADD)
        edit_btn = UIUtils.create_action_button("编辑文档", FluentIcon.EDIT)
        delete_btn = UIUtils.create_action_button("删除文档", FluentIcon.DELETE)
        

        add_btn.clicked.connect(self.add_document)
        edit_btn.clicked.connect(self.edit_document)
        delete_btn.clicked.connect(self.delete_document)
        

        button_layout = UIUtils.create_button_layout(add_btn, edit_btn, delete_btn)
        self.main_layout.addLayout(button_layout)

        # 文档列表
        self.document_table = TableWidget()
        self.document_table.setColumnCount(7) # 移除上传人列，总列数减1
        self.document_table.setHorizontalHeaderLabels([
            "文档名称", "类型", "版本", "关键词", # 调整顺序
            "上传时间", "描述", "文档附件" # 调整顺序，移除上传人
        ])
        # 设置表格样式
        #self.document_table.setBorderVisible(True)
        #self.document_table.setBorderRadius(8)
        self.document_table.setWordWrap(False)
        self.document_table.setItemDelegate(TableItemDelegate(self.document_table))
        UIUtils.set_table_style(self.document_table) # 应用通用样式

        # 禁止直接编辑
        self.document_table.setEditTriggers(TableWidget.NoEditTriggers)

        # 设置列宽模式和排序
        header = self.document_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSortIndicatorShown(True) # 启用排序

        # 隐藏行号
        #self.document_table.verticalHeader().setVisible(False)

        # 设置初始列宽 (需要调整以适应新列)
        header.resizeSection(0, 310) # 文档名称
        header.resizeSection(1, 100) # 类型
        header.resizeSection(2, 80)  # 版本
        header.resizeSection(3, 120) # 关键词 (索引改为3)
        header.resizeSection(4, 125) # 上传时间 (索引改为4)
        header.resizeSection(5, 250) # 描述 (索引改为5)
        header.resizeSection(6, 80)  # 附件列 (索引改为6)

        # 允许用户调整列宽和移动列
        header.setSectionsMovable(True)
        # header.setStretchLastSection(True) # 取消最后一列拉伸

        vheader = self.document_table.verticalHeader()        
        vheader.setDefaultAlignment(Qt.AlignCenter)

        self.document_table.setSelectionMode(TableWidget.ExtendedSelection)
        self.document_table.setSelectionBehavior(TableWidget.SelectRows)

        self.main_layout.addWidget(self.document_table)

        # 搜索栏
        search_layout = QHBoxLayout()
        self.search_edit = LineEdit()
        self.search_edit.setPlaceholderText("输入关键词搜索文档")
        self.search_edit.textChanged.connect(self.apply_filters) # Connect to new filter method
        search_layout.addWidget(self.search_edit)

        self.type_filter = ComboBox()
        self.type_filter.addItem("全部类型")
        for doc_type in DocumentType:
            self.type_filter.addItem(doc_type.value)
        self.type_filter.currentTextChanged.connect(self.apply_filters) # Connect to new filter method
        search_layout.addWidget(self.type_filter)

        # Add reset button
        reset_btn = PushButton("重置筛选")
        reset_btn.clicked.connect(self.reset_filters)
        search_layout.addWidget(reset_btn)
        # 增加分隔线
        search_layout.addSpacing(10)

        # 导出按钮
        export_excel_btn = PushButton("导出信息")
        export_excel_btn.clicked.connect(self.export_document_excel)
        search_layout.addWidget(export_excel_btn)

        export_attachment_btn = PushButton("导出附件")
        export_attachment_btn.clicked.connect(self.export_document_attachments)
        search_layout.addWidget(export_attachment_btn)
        self.main_layout.addLayout(search_layout)
        self.document_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.document_table.customContextMenuRequested.connect(self.show_document_context_menu)

    def _on_project_selected(self, index):
        """Handles project selection change."""
        selected_data = self.project_selector.itemData(index)
        if selected_data == "all":
            self.current_project = None # Set current_project to None for "全部数据"
            UIUtils.show_success(self, "项目文档", "'全部文档' 已选择")
            self.load_documents(load_all=True) # Load all documents
        elif selected_data and isinstance(selected_data, Project):
            self.current_project = selected_data
            UIUtils.show_success(self, "项目文档", f"项目已选择: {self.current_project.name}")
            self.load_documents() # Load documents for the selected project
        else:
            self.current_project = None
            self.document_table.setRowCount(0) # Clear table if no project selected
            UIUtils.show_info(self, "项目文档", "请选择一个项目以查看文档")

    def load_documents(self, load_all=False):
        """Loads documents into memory and populates the table.
           If load_all is True, loads documents for all projects.
           Otherwise, loads documents for the current project.
        """
        self.all_documents = []
        self.current_documents = []
        self.document_table.setRowCount(0)

        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            if load_all:
                print("DocumentWidget: Loading all documents.")
                self.all_documents = session.query(ProjectDocument).order_by(ProjectDocument.upload_time.desc()).all()
            elif self.current_project:
                print(f"DocumentWidget: Loading documents for project ID: {self.current_project.id}")
                self.all_documents = session.query(ProjectDocument).filter(
                    ProjectDocument.project_id == self.current_project.id
                ).order_by(ProjectDocument.upload_time.desc()).all()
            else:
                print("DocumentWidget: No project selected and load_all is False, cannot load documents.")
                return

            self.current_documents = self.all_documents[:] # Initial view shows all
            self._populate_table(self.current_documents)
        finally:
            session.close()

    def _populate_table(self, documents_list):
        """Populates the table based on the provided list of ProjectDocument objects."""
        self.document_table.setSortingEnabled(False)
        # self.document_table.setRowCount(0) # Remove clearing here

        # Set the row count based on the number of documents
        self.document_table.setRowCount(len(documents_list))

        for row, doc in enumerate(documents_list):
            # self.document_table.insertRow(row) # Remove insertRow

            # Col 0: Name
            name_item = QTableWidgetItem(doc.name)
            name_item.setData(Qt.UserRole, doc.id) # Store ID here
            self.document_table.setItem(row, 0, name_item)            
            # Col 1: Type
            type_item = QTableWidgetItem(doc.doc_type.value); type_item.setTextAlignment(Qt.AlignCenter); self.document_table.setItem(row, 1, type_item)
            # Col 2: Version
            version_item = QTableWidgetItem(doc.version or ""); version_item.setTextAlignment(Qt.AlignCenter); self.document_table.setItem(row, 2, version_item)
            # Col 3: Keywords (Index changed from 4 to 3)
            keywords_item = QTableWidgetItem(doc.keywords or ""); self.document_table.setItem(row, 3, keywords_item)
            # Col 4: Upload Time (Index changed from 6 to 4)
            upload_time_str = doc.upload_time.strftime("%Y-%m-%d %H:%M") if doc.upload_time else ""
            upload_time_item = QTableWidgetItem(upload_time_str); upload_time_item.setTextAlignment(Qt.AlignCenter)
            upload_time_item.setData(Qt.UserRole + 1, doc.upload_time) # Store datetime for sorting
            self.document_table.setItem(row, 4, upload_time_item)
            # Col 5: Description (Index changed from 3 to 5)
            description_item = QTableWidgetItem(doc.description or ""); self.document_table.setItem(row, 5, description_item)
            
            # Col 6: Attachment Button (Index changed from 7 to 6)
            container = create_attachment_button(
                item_id=doc.id,
                attachment_path=doc.file_path,
                handle_attachment_func=self.handle_document_attachment, # Pass the method reference directly
                parent_widget=self,
                item_type='document'
            )
            self.document_table.setCellWidget(row, 6, container) # 附件列索引从7改为6

        self.document_table.setSortingEnabled(True)

    def apply_filters(self):
        """Applies filters based on search keyword and type, updates the table."""
        # from ...utils.filter_utils import FilterUtils # Import moved to top

        keyword = self.search_edit.text() # Keep original case for potential future needs, FilterUtils handles lowercasing
        doc_type_filter = self.type_filter.currentText()

        filter_criteria = {
            'keyword': keyword,
            'keyword_attributes': ['name', 'description', 'keywords'], # Removed 'uploader'
            'doc_type': doc_type_filter
        }

        attribute_mapping = {
            'doc_type': 'doc_type' # Map filter key 'doc_type' to object attribute 'doc_type'
        }

        self.current_documents = FilterUtils.apply_filters(
            self.all_documents,
            filter_criteria,
            attribute_mapping
        )
        self._populate_table(self.current_documents)

    def reset_filters(self):
        """Resets filter inputs and reapplies filters."""
        self.search_edit.clear()
        self.type_filter.setCurrentText("全部类型")
        self.apply_filters() # Re-apply filters to show all items

    # _generate_document_path 方法已移除，使用attachment_utils.py中的generate_attachment_path函数代替

    def add_document(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return

        dialog = DocumentDialog(self)
        if dialog.exec():
            source_file_path = dialog.file_path_edit.text() # Path selected by user
            if not source_file_path:
                # This case should be handled by Dialog's accept validation, but double-check
                UIUtils.show_warning(self, "警告", "请选择要上传的文件")
                return

            doc_type_enum = DocumentType(dialog.type_combo.currentText())

            # --- Generate new path using specific rule ---
            new_file_path = self._generate_document_path(
                project=self.current_project,
                doc_type_enum=doc_type_enum,
                original_filename=source_file_path
            )
            if not new_file_path:
                 UIUtils.show_error(self, "错误", "无法生成文档保存路径")
                 return
            # --- End path generation ---

            # Ensure directory exists and copy file
            try:
                ensure_directory_exists(os.path.dirname(new_file_path))
                shutil.copy2(source_file_path, new_file_path)
            except (IOError, OSError) as e:
                UIUtils.show_error(self, "文件复制错误", f"无法复制文件到目标目录：{e}")
                return # Stop if copy fails

            # Save to database
            Session = sessionmaker(bind=self.engine)
            session = Session()
            try:
                document = ProjectDocument(
                    project_id=self.current_project.id,
                    name=dialog.name_edit.text(),
                    doc_type=doc_type_enum, # Use the enum object
                    version=dialog.version_edit.text(),
                    description=dialog.description_edit.toPlainText(), # Use toPlainText()
                    keywords=dialog.keywords_edit.text(),
                    file_path=new_file_path # Save the NEW path
                )
                session.add(document)
                session.commit()

                # 添加操作日志
                actionlog = Actionlog(
                    project_id=self.current_project.id,
                    project_document_id=document.id,
                    type="文档",
                    action="新增",
                    description=f"新增文档: {document.name}",
                    operator="当前用户", # TODO: 获取当前登录用户
                    related_info=f"类型: {document.doc_type.value}, 版本: {document.version or '无'}"
                )
                session.add(actionlog)
                session.commit() # 提交日志

                self.load_documents() # Reload table
                UIUtils.show_success(self, "成功", "文档添加成功")
            except Exception as db_err:
                session.rollback()
                UIUtils.show_error(self, "数据库错误", f"保存文档信息失败：{db_err}")
                # Attempt to remove the copied file if DB save failed
                try:
                    if os.path.exists(new_file_path):
                        os.remove(new_file_path)
                except OSError as remove_err:
                     print(f"警告: 移除复制的文件失败: {remove_err}")
            finally:
                session.close()

    def edit_document(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return
        selected_items = self.document_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择要编辑的文档")
            return

        row = selected_items[0].row()
        # Get ID from UserRole of the first column item
        id_item = self.document_table.item(row, 0)
        if not id_item: return
        doc_id = id_item.data(Qt.UserRole)

        # Use the stored engine
        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            document = session.query(ProjectDocument).filter(
                ProjectDocument.id == doc_id,
                ProjectDocument.project_id == self.current_project.id
            ).first()
            if not document:
                UIUtils.show_error(self, "错误", "未找到选中的文档记录")
                return

            dialog = DocumentDialog(self, document=document)
            if dialog.exec():
                document.name = dialog.name_edit.text()
                document.doc_type = DocumentType(dialog.type_combo.currentText())
                document.version = dialog.version_edit.text()
                document.description = dialog.description_edit.toPlainText() # Use toPlainText()
                document.keywords = dialog.keywords_edit.text()
                # document.uploader = dialog.uploader_edit.text() # Removed uploader update
                # File path is not edited here, only through attachment handling
                session.commit()

                # 添加操作日志
                actionlog = Actionlog(
                    project_id=self.current_project.id,
                    project_document_id=document.id,
                    type="文档",
                    action="编辑",
                    description=f"编辑文档: {document.name}",
                    operator="当前用户", # TODO: 获取当前登录用户
                    related_info=f"类型: {document.doc_type.value}, 版本: {document.version or '无'}"
                )
                session.add(actionlog)
                session.commit() # 提交日志

                self.load_documents()
                UIUtils.show_success(self, "成功", "文档信息编辑成功")
        except Exception as e:
            session.rollback()
            UIUtils.show_error(self, "数据库错误", f"编辑文档信息失败：{e}")
        finally:
            session.close()

    def delete_document(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return
        selected_rows = sorted(list(set(item.row() for item in self.document_table.selectedItems())), reverse=True)
        if not selected_rows:
            UIUtils.show_warning(self, "警告", "请先选择要删除的文档")
            return

        doc_ids_to_delete = []
        for row in selected_rows:
            id_item = self.document_table.item(row, 0)
            if id_item:
                doc_ids_to_delete.append(id_item.data(Qt.UserRole))

        if not doc_ids_to_delete:
             UIUtils.show_error(self, "错误", "无法获取选中的文档ID")
             return

        confirm_dialog = Dialog(
            title='确认删除',
            content=f'确定要删除选中的 {len(doc_ids_to_delete)} 条文档记录吗？相关文件也将被删除。此操作不可恢复。',
            parent=self
        )
        confirm_dialog.cancelButton.setText('取消')
        confirm_dialog.yesButton.setText('确认删除')

        if confirm_dialog.exec():
            Session = sessionmaker(bind=self.engine)
            session = Session()
            deleted_count = 0
            try:
                for doc_id in doc_ids_to_delete:
                    document = session.query(ProjectDocument).filter(
                        ProjectDocument.id == doc_id,
                        ProjectDocument.project_id == self.current_project.id
                    ).first()
                    if document:
                        # 删除文件
                        if document.file_path and os.path.exists(document.file_path):
                            try:
                                os.remove(document.file_path)
                            except OSError as e:
                                print(f"Warning: Could not delete document file {document.file_path}: {e}")
                                # Decide if deletion should proceed or stop

                        session.delete(document)
                        deleted_count += 1

                        # 添加操作日志
                        actionlog = Actionlog(
                            project_id=self.current_project.id,
                            type="文档",
                            action="删除",
                            description=f"删除文档: {document.name}",
                            operator="当前用户", # TODO: 获取当前登录用户
                            related_info=f"类型: {document.doc_type.value}, 版本: {document.version or '无'}"
                        )
                        session.add(actionlog)

                session.commit() # 在循环外部统一提交
                self.load_documents()
                UIUtils.show_success(self, "成功", f"成功删除 {deleted_count} 条文档记录")
            except Exception as e:
                session.rollback()
                UIUtils.show_error(self, "数据库错误", f"删除文档失败：{e}")
            finally:
                session.close()

    def download_document(self):
        selected_items = self.document_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择要下载的文档")
            return

        row = selected_items[0].row()
        id_item = self.document_table.item(row, 0)
        if not id_item: return
        doc_id = id_item.data(Qt.UserRole)

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            document = session.query(ProjectDocument).get(doc_id)
            if not document or not document.file_path or not os.path.exists(document.file_path):
                UIUtils.show_error(self, "错误", "找不到文档文件或文件路径无效")
                return

            # 获取原始文件名
            original_filename = os.path.basename(document.file_path)
            # 建议保存的文件名（可以包含文档名等信息）
            suggested_filename = f"{document.name}_{original_filename}"

            # 打开文件保存对话框
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存文档",
                suggested_filename, # 建议的文件名
                f"All Files (*)" # 文件类型过滤器
            )

            if save_path:
                try:
                    shutil.copy2(document.file_path, save_path)
                    UIUtils.show_success(self, "成功", f"文档已成功下载到：\n{save_path}")
                except Exception as e:
                    UIUtils.show_error(self, "下载错误", f"下载文件失败：{e}")
        finally:
            session.close()

    def handle_document_attachment(self, event, btn):
        """处理文档附件操作，使用通用附件处理函数"""
        doc_id = btn.property("item_id")
        Session = sessionmaker(bind=self.engine)
        
        # 定义获取文档对象的函数
        def get_document(session, doc_id):
            return session.query(ProjectDocument).get(doc_id)
        
        # 调用通用附件处理函数
        handle_attachment(
            event=event,
            btn=btn,
            item_id=doc_id,
            item_type="document",
            session_maker=Session,
            parent_widget=self,
            get_item_func=get_document,
            attachment_attr="file_path",
            project_attr="project_id",
            base_folder="documents"
        )

    # _execute_document_action 方法已移除，使用attachment_utils.py中的execute_attachment_action函数代替

    
    def show_document_context_menu(self, pos):
        """显示文档表格的右键菜单"""
        menu = RoundMenu(parent=self)

        # 获取右键点击的单元格
        item = self.document_table.itemAt(pos)
        if item:
            # 添加复制操作
            copy_action = Action(FluentIcon.COPY, "复制", self)
            copy_action.triggered.connect(lambda: self.copy_cell_content(item))
            menu.addAction(copy_action)

        # 显示菜单
        menu.exec_(self.document_table.viewport().mapToGlobal(pos))

    def export_document_excel(self):
        """导出文档信息到Excel"""
        if not self.current_project or not self.current_documents:
            UIUtils.show_warning(self, "警告", "没有可导出的文档数据")
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
            for doc in self.current_documents:
                data.append({
                    "文档名称": doc.name,
                    "文档类型": doc.doc_type.value,
                    "版本号": doc.version or "",
                    "关键词": doc.keywords or "",
                    "上传时间": doc.upload_time.strftime("%Y-%m-%d %H:%M") if doc.upload_time else "",
                    "文档描述": doc.description or "",
                    "文件路径": doc.file_path or ""
                })

            # 创建DataFrame并导出
            df = pd.DataFrame(data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = os.path.join(export_dir, f"文档信息_{self.current_project.financial_code}_{timestamp}.xlsx")
            
            df.to_excel(export_path, index=False)
            UIUtils.show_success(self, "成功", f"文档信息已导出到: {export_path}")

        except Exception as e:
            UIUtils.show_error(self, "错误", f"导出文档信息失败: {str(e)}")

    def export_document_attachments(self):
        """导出文档附件"""
        if not self.current_project or not self.current_documents:
            UIUtils.show_warning(self, "警告", "没有可导出的文档附件")
            return

        export_dir = QFileDialog.getExistingDirectory(
            self, "选择导出目录",
            os.path.expanduser("~")
        )
        if not export_dir:
            return

        try:
            # 创建项目子目录
            project_dir = os.path.join(export_dir, f"文档附件_{self.current_project.financial_code}")
            os.makedirs(project_dir, exist_ok=True)

            # 导出附件
            exported_count = 0
            for doc in self.current_documents:
                if doc.file_path and os.path.exists(doc.file_path):
                    filename = os.path.basename(doc.file_path)
                    dest_path = os.path.join(project_dir, filename)
                    
                    # 避免文件名冲突
                    counter = 1
                    while os.path.exists(dest_path):
                        base, ext = os.path.splitext(filename)
                        dest_path = os.path.join(project_dir, f"{base}_{counter}{ext}")
                        counter += 1
                    
                    shutil.copy2(doc.file_path, dest_path)
                    exported_count += 1

            if exported_count > 0:
                UIUtils.show_success(self, "成功", f"成功导出 {exported_count} 个文档附件到: {project_dir}")
            else:
                UIUtils.show_warning(self, "警告", "没有找到可导出的文档附件")

        except Exception as e:
            UIUtils.show_error(self, "错误", f"导出文档附件失败: {str(e)}")

    def copy_cell_content(self, item):
        """复制单元格内容"""
        if item:
            # 获取单元格内容
            content = item.text()
            clipboard = QApplication.clipboard()
            clipboard.setText(content)