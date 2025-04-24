from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QFileDialog, QDialog, QLabel, QHeaderView # Added QHeaderView
from PySide6.QtCore import Qt, QSize, QPoint # Added QSize and QPoint
from PySide6.QtGui import QFont # 确保 QFont 已导入
# Import BodyLabel and PushButton, remove PrimaryPushButton if no longer needed elsewhere
# Also import TableItemDelegate
from qfluentwidgets import TitleLabel, FluentIcon, ComboBox, LineEdit, InfoBar, Dialog, BodyLabel, PushButton, TableWidget, TableItemDelegate
# 需要在文件顶部导入
from ...models.database import Project, sessionmaker
from ...utils.ui_utils import UIUtils
from ...models.database import Base, get_engine # Project and sessionmaker already imported
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum as SQLEnum, DateTime, Engine # Added Engine type hint
from enum import Enum
from datetime import datetime
import os
import shutil
# 假设存在 attachment_utils.py 用于处理附件按钮和逻辑
from ...utils.attachment_utils import create_attachment_button, handle_attachment # Import attachment utils
from ...utils.filter_utils import FilterUtils # Import FilterUtils

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

    # This setup_ui method seems correct based on the previous successful application.
    # No changes needed here unless there was an unseen modification.
    # The diff will focus on adding the accept method correctly.
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
        self.description_edit = LineEdit()
        self.description_edit.setPlaceholderText("请输入文档描述")
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
        self.description_edit.setText(self.document.description)
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
        # --- Add Project Selector ---
        selector_layout = QHBoxLayout()
        selector_label = TitleLabel("项目文档-", self)
        self.project_selector = UIUtils.create_project_selector(self.engine, self)
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

        # 设置列宽模式和排序
        header = self.document_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSortIndicatorShown(True) # 启用排序
        header.sectionClicked.connect(self.sort_table) # 连接排序信号

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

        self.main_layout.addLayout(search_layout)

    def _on_project_selected(self, index):
        """Handles project selection change."""
        selected_project = self.project_selector.itemData(index)
        if selected_project and isinstance(selected_project, Project):
            self.current_project = selected_project
            print(f"DocumentWidget: Project selected - {self.current_project.name}")
            self.load_documents() # Load documents for the selected project
        else:
            self.current_project = None
            self.document_table.setRowCount(0) # Clear table if no project selected
            print("DocumentWidget: No valid project selected.")

    def load_documents(self):
        """Loads all documents for the current project into memory and populates the table."""
        self.all_documents = []
        self.current_documents = []
        self.document_table.setRowCount(0)
        if not self.current_project:
            print("DocumentWidget: No project selected, cannot load documents.")
            return

        # Use the stored engine
        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            print(f"DocumentWidget: Loading documents for project ID: {self.current_project.id}")
            self.all_documents = session.query(ProjectDocument).filter(
                ProjectDocument.project_id == self.current_project.id
            ).order_by(ProjectDocument.upload_time.desc()).all()
            self.current_documents = self.all_documents[:] # Initial view shows all
            self._populate_table(self.current_documents)
        finally:
            session.close()

    def _populate_table(self, documents_list):
        """Populates the table based on the provided list of ProjectDocument objects."""
        self.document_table.setSortingEnabled(False)
        self.document_table.setRowCount(0)

        for row, doc in enumerate(documents_list):
            self.document_table.insertRow(row)

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
            # Col 5: Uploader (Removed)
            # uploader_item = QTableWidgetItem(doc.uploader or ""); uploader_item.setTextAlignment(Qt.AlignCenter); self.document_table.setItem(row, 5, uploader_item)
            # Col 7: File Path (Removed)
            # file_path_item = QTableWidgetItem(doc.file_path or ""); self.document_table.setItem(row, 7, file_path_item) # 移除文件路径列

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

    def add_document(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return

        dialog = DocumentDialog(self)
        if dialog.exec():
            file_path = dialog.file_path_edit.text()
            if not file_path:
                UIUtils.show_warning(self, "警告", "请选择要上传的文件")
                return

            # 复制文件到项目文档目录
            project_doc_dir = os.path.join("documents", str(self.current_project.id))
            os.makedirs(project_doc_dir, exist_ok=True)

            new_file_path = os.path.join(project_doc_dir, os.path.basename(file_path))
            try:
                shutil.copy2(file_path, new_file_path)
            except (IOError, OSError) as e:
                UIUtils.show_error(self, "文件复制错误", f"无法复制文件到项目目录：{e}")
                return # Stop if copy fails

            # Use the stored engine
            Session = sessionmaker(bind=self.engine)
            session = Session()
            try:
                document = ProjectDocument(
                    project_id=self.current_project.id, # Use current_project.id
                    name=dialog.name_edit.text(),
                    doc_type=DocumentType(dialog.type_combo.currentText()),
                    version=dialog.version_edit.text(),
                    description=dialog.description_edit.text(),
                    keywords=dialog.keywords_edit.text(),
                    # uploader=dialog.uploader_edit.text(), # Removed uploader
                    file_path=new_file_path
                )
                session.add(document)
                session.commit()
                self.load_documents()
                UIUtils.show_success(self, "成功", "文档上传成功")
            except Exception as db_err: # Catch potential DB errors
                session.rollback()
                UIUtils.show_error(self, "数据库错误", f"保存文档信息失败：{db_err}")
                # Attempt to remove the copied file if DB save failed
                try:
                    if os.path.exists(new_file_path):
                        os.remove(new_file_path)
                except OSError as remove_err:
                     print(f"Warning: Failed to remove copied file after DB error: {remove_err}") # Log or print warning
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
                document.description = dialog.description_edit.text()
                document.keywords = dialog.keywords_edit.text()
                # document.uploader = dialog.uploader_edit.text() # Removed uploader update
                # File path is not edited here, only through attachment handling
                session.commit()
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
                session.commit()
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

    def handle_document_attachment(self, event, btn): # Removed doc_id from signature
        """Wraps the handle_attachment call specifically for documents."""
        # Get the document ID from the button's property
        doc_id = btn.property("item_id")
        if doc_id is None:
            print("Error: Could not get document ID from button property.")
            return

        # Find the row this button belongs to (optional, might not be needed if handle_attachment updates btn directly)
        # button_pos = btn.mapToGlobal(self.mapToGlobal(QPoint(0, 0)))
        # row_index = self.document_table.indexAt(self.document_table.viewport().mapFromGlobal(button_pos)).row()
        # if row_index < 0: return

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            document = session.query(ProjectDocument).get(doc_id) # Use ID fetched from button
            if not document:
                UIUtils.show_error(self, "错误", "找不到对应的文档记录")
                return

            # Call the generic handler from attachment_utils with correct parameters
            handle_attachment(
                event=event,
                btn=btn,
                item=document, # Pass the actual document object
                session=session, # Pass the current session
                parent_widget=self,
                project=self.current_project, # Pass the current project object
                item_type='document', # Pass the item type identifier
                attachment_attr='file_path', # Pass the attribute name for the path
                base_folder='documents' # Pass the base folder name
            )

            # The handle_attachment function from attachment_utils now handles
            # database updates, file operations, button state updates,
            # and user feedback messages internally.
            # No further action is needed in this wrapper function after calling handle_attachment.

            # --- Add logic to update the in-memory list ---
            # Get the potentially updated path from the button property
            updated_path = btn.property("attachment_path")

            # Find the corresponding document in the main list and update its path
            for doc_in_list in self.all_documents:
                if doc_in_list.id == doc_id:
                    doc_in_list.file_path = updated_path
                    break # Found and updated, exit loop

            # Note: We don't need to explicitly update self.current_documents here,
            # as filtering/sorting operations typically rebuild it from self.all_documents.

        except Exception as e:
            session.rollback()
            UIUtils.show_error(self, "错误", f"处理文档附件时出错: {e}")
            print(f"Error in handle_document_attachment: {e}")
        finally:
            session.close()

    def sort_table(self, column):
        """Sorts the table based on the clicked column."""
        if not self.current_documents: return

        # Map column index to attribute name and type
        column_map = {
            0: ('name', 'str'),
            1: ('doc_type', 'enum'),
            2: ('version', 'str_none'),
            3: ('keywords', 'str_none'),    # Index changed from 4 to 3
            4: ('upload_time', 'datetime'), # Index changed from 6 to 4
            5: ('description', 'str_none'), # Index changed from 3 to 5
            # 6: ('attachment', None) # Not sortable (Index changed from 7 to 6)
            # Removed 'uploader' (was index 5)
        }

        if column not in column_map: return

        attr_name, sort_type = column_map[column]
        current_order = self.document_table.horizontalHeader().sortIndicatorOrder()
        reverse = (current_order == Qt.DescendingOrder)

        def sort_key(doc):
            value = getattr(doc, attr_name, None)
            if sort_type == 'enum':
                return value.value if value else ""
            elif sort_type == 'str_none':
                return value.lower() if value else ""
            elif sort_type == 'str':
                return value.lower()
            elif sort_type == 'datetime':
                 # Use epoch for None datetimes to sort them consistently
                 return value.timestamp() if value else 0
            return value if value is not None else "" # Fallback for other types

        try:
            self.current_documents.sort(key=sort_key, reverse=reverse)
        except Exception as e:
            print(f"Error during document sorting: {e}")
            return

        self._populate_table(self.current_documents)
        self.document_table.horizontalHeader().setSortIndicator(column, current_order)