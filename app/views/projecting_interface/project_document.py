from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QFileDialog, QDialog, QLabel, QHeaderView # Added QHeaderView
from PySide6.QtCore import Qt, QSize # Added QSize
# Import BodyLabel and PushButton, remove PrimaryPushButton if no longer needed elsewhere
# Also import TableItemDelegate
from qfluentwidgets import TitleLabel, FluentIcon, ComboBox, LineEdit, InfoBar, Dialog, BodyLabel, PushButton, TableItemDelegate
from ...utils.ui_utils import UIUtils
from ...models.database import Project, Base, get_engine, sessionmaker # Added sessionmaker import
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum as SQLEnum, DateTime, Engine # Added Engine type hint
from enum import Enum
from datetime import datetime
import os
import shutil
# 假设存在 attachment_utils.py 用于处理附件按钮和逻辑
from ...utils.attachment_utils import create_attachment_button, handle_attachment # Import attachment utils

class DocumentType(Enum):
    APPLICATION = "申请书"
    CONTRACT = "合同/任务书"
    RESEARCH_DATA = "研究数据"
    RESULT = "成果文件"
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
    uploader = Column(String(50))  # 上传人
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

        # 文档描述
        description_layout = QHBoxLayout()
        description_layout.addWidget(BodyLabel("文档描述:"))
        self.description_edit = LineEdit()
        self.description_edit.setPlaceholderText("请输入文档描述")
        description_layout.addWidget(self.description_edit)
        layout.addLayout(description_layout)

        # 关键词
        keywords_layout = QHBoxLayout()
        keywords_layout.addWidget(BodyLabel("关 键 词 :")) # Align label width
        self.keywords_edit = LineEdit()
        self.keywords_edit.setPlaceholderText("请输入关键词（用逗号分隔）")
        keywords_layout.addWidget(self.keywords_edit)
        layout.addLayout(keywords_layout)

        # 上传人
        uploader_layout = QHBoxLayout()
        uploader_layout.addWidget(BodyLabel("上 传 人 :")) # Align label width
        self.uploader_edit = LineEdit()
        self.uploader_edit.setPlaceholderText("请输入上传人")
        uploader_layout.addWidget(self.uploader_edit)
        layout.addLayout(uploader_layout)

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
        self.uploader_edit.setText(self.document.uploader)
        self.file_path_edit.setText(self.document.file_path)

class ProjectDocumentWidget(QWidget):
    # Modify __init__ to accept engine and remove project
    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent=parent)
        # self.project = project # Removed
        self.engine = engine # Store engine
        self.current_project = None # Track selected project
        self.setup_ui()
        # self.load_documents() # Don't load initially, wait for selection
    
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
        download_btn = UIUtils.create_action_button("下载文档", FluentIcon.DOWNLOAD)
        
        add_btn.clicked.connect(self.add_document)
        edit_btn.clicked.connect(self.edit_document)
        delete_btn.clicked.connect(self.delete_document)
        download_btn.clicked.connect(self.download_document)
        
        button_layout = UIUtils.create_button_layout(add_btn, edit_btn, delete_btn, download_btn)
        self.main_layout.addLayout(button_layout)
        
        # 文档列表
        self.document_table = QTableWidget()
        self.document_table.setColumnCount(9) # 增加一列用于附件
        self.document_table.setHorizontalHeaderLabels([
            "文档名称", "类型", "版本", "描述", "关键词",
            "上传人", "上传时间", "文件路径", "附件" # 添加附件列标题
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
        # header.setSortIndicatorShown(True) # 可选：启用排序
        # header.sectionClicked.connect(self.sort_table) # 可选：连接排序信号

        # 隐藏行号
        self.document_table.verticalHeader().setVisible(False)

        # 设置初始列宽 (需要调整以适应新列)
        header.resizeSection(0, 150) # 文档名称
        header.resizeSection(1, 100) # 类型
        header.resizeSection(2, 80)  # 版本
        header.resizeSection(3, 150) # 描述
        header.resizeSection(4, 120) # 关键词
        header.resizeSection(5, 80)  # 上传人
        header.resizeSection(6, 120) # 上传时间
        header.resizeSection(7, 150) # 文件路径 (可能需要调整)
        header.resizeSection(8, 80)  # 附件列

        # 允许用户调整列宽和移动列
        header.setSectionsMovable(True)
        # header.setStretchLastSection(True) # 取消最后一列拉伸

        self.document_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.document_table.setSelectionBehavior(QTableWidget.SelectRows)

        self.main_layout.addWidget(self.document_table)
        
        # 搜索栏
        search_layout = QHBoxLayout()
        self.search_edit = LineEdit()
        self.search_edit.setPlaceholderText("输入关键词搜索文档")
        self.search_edit.textChanged.connect(self.search_documents)
        search_layout.addWidget(self.search_edit)
        
        self.type_filter = ComboBox()
        self.type_filter.addItem("全部类型")
        for doc_type in DocumentType:
            self.type_filter.addItem(doc_type.value)
        self.type_filter.currentTextChanged.connect(self.search_documents)
        search_layout.addWidget(self.type_filter)
        
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
        """Loads documents for the currently selected project."""
        self.document_table.setRowCount(0) # Clear table first
        if not self.current_project:
            print("DocumentWidget: No project selected, cannot load documents.")
            return

        # Use the stored engine
        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            print(f"DocumentWidget: Loading documents for project ID: {self.current_project.id}")
            documents = session.query(ProjectDocument).filter(
                ProjectDocument.project_id == self.current_project.id
            ).order_by(ProjectDocument.upload_time.desc()).all() # Order by upload time

            self.document_table.setRowCount(len(documents))
            for row, doc in enumerate(documents):
                # 设置文本对齐方式
                name_item = QTableWidgetItem(doc.name)
                type_item = QTableWidgetItem(doc.doc_type.value)
                type_item.setTextAlignment(Qt.AlignCenter)
                version_item = QTableWidgetItem(doc.version or "")
                version_item.setTextAlignment(Qt.AlignCenter)
                description_item = QTableWidgetItem(doc.description or "")
                keywords_item = QTableWidgetItem(doc.keywords or "")
                uploader_item = QTableWidgetItem(doc.uploader or "")
                uploader_item.setTextAlignment(Qt.AlignCenter)
                upload_time_item = QTableWidgetItem(doc.upload_time.strftime("%Y-%m-%d %H:%M") if doc.upload_time else "")
                upload_time_item.setTextAlignment(Qt.AlignCenter)
                file_path_item = QTableWidgetItem(doc.file_path or "") # 文件路径可能为空

                self.document_table.setItem(row, 0, name_item)
                self.document_table.setItem(row, 1, type_item)
                self.document_table.setItem(row, 2, version_item)
                self.document_table.setItem(row, 3, description_item)
                self.document_table.setItem(row, 4, keywords_item)
                self.document_table.setItem(row, 5, uploader_item)
                self.document_table.setItem(row, 6, upload_time_item)
                self.document_table.setItem(row, 7, file_path_item)

                # 在其他单元格也存储文档ID
                for col in range(self.document_table.columnCount() - 1): # 排除最后一列
                    cell_item = self.document_table.item(row, col)
                    if cell_item:
                        cell_item.setData(Qt.UserRole, doc.id)

                # 添加附件管理按钮
                container = create_attachment_button(
                    item_id=doc.id,
                    attachment_path=doc.file_path, # 文档模型使用 file_path
                    handle_attachment_func=lambda event, btn, item_id=doc.id: self.handle_document_attachment(event, btn, item_id),
                    parent_widget=self,
                    item_type='document' # 标识附件类型为文档
                )
                self.document_table.setCellWidget(row, 8, container) # 第 8 列是附件列
        finally:
            session.close()
    
    def search_documents(self):
        keyword = self.search_edit.text().lower()
        doc_type = self.type_filter.currentText()
        
        for row in range(self.document_table.rowCount()):
            show_row = True
            
            # 关键词匹配
            if keyword:
                match_found = False
                for col in [0, 3, 4]:  # 搜索文档名称、描述和关键词列
                    cell_text = self.document_table.item(row, col).text().lower()
                    if keyword in cell_text:
                        match_found = True
                        break
                show_row = match_found
            
            # 类型过滤
            if show_row and doc_type != "全部类型":
                cell_type = self.document_table.item(row, 1).text()
                show_row = (cell_type == doc_type)
            
            self.document_table.setRowHidden(row, not show_row)
    
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
            shutil.copy2(file_path, new_file_path)
            
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
                    uploader=dialog.uploader_edit.text(),
                    file_path=new_file_path
                )
                session.add(document)
                session.commit()
                self.load_documents()
                UIUtils.show_success(self, "成功", "文档上传成功")
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
        doc_name = self.document_table.item(row, 0).text()
        
        # Use the stored engine
        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            document = session.query(ProjectDocument).filter(
                ProjectDocument.project_id == self.current_project.id, # Use current_project.id
                ProjectDocument.name == doc_name
            ).first()

            if document:
                dialog = DocumentDialog(self, document)
                if dialog.exec():
                    document.name = dialog.name_edit.text()
                    document.doc_type = DocumentType(dialog.type_combo.currentText())
                    document.version = dialog.version_edit.text()
                    document.description = dialog.description_edit.text()
                    document.keywords = dialog.keywords_edit.text()
                    document.uploader = dialog.uploader_edit.text()
                    
                    new_file_path = dialog.file_path_edit.text()
                    if new_file_path and new_file_path != document.file_path:
                        project_doc_dir = os.path.join("documents", str(self.current_project.id)) # Use current_project.id
                        os.makedirs(project_doc_dir, exist_ok=True)
                        
                        new_file_path = os.path.join(project_doc_dir, os.path.basename(new_file_path))
                        shutil.copy2(dialog.file_path_edit.text(), new_file_path)
                        document.file_path = new_file_path
                    
                    session.commit()
                    self.load_documents()
                    UIUtils.show_success(self, "成功", "文档更新成功")
        finally:
            session.close()
    
    def delete_document(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return
        selected_items = self.document_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择要删除的文档")
            return
        
        row = selected_items[0].row()
        doc_name = self.document_table.item(row, 0).text()
        
        # Use the stored engine
        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            document = session.query(ProjectDocument).filter(
                ProjectDocument.project_id == self.current_project.id, # Use current_project.id
                ProjectDocument.name == doc_name
            ).first()

            if document:
                # 删除文件
                if os.path.exists(document.file_path):
                    os.remove(document.file_path)
                
                session.delete(document)
                session.commit()
                self.load_documents()
                UIUtils.show_success(self, "成功", "文档删除成功")
        finally:
            session.close()
    
    def download_document(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return
        selected_items = self.document_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择要下载的文档")
            return
        
        row = selected_items[0].row()
        file_path = self.document_table.item(row, 7).text()
        
        if not os.path.exists(file_path):
            UIUtils.show_error(self, "错误", "文件不存在")
            return
        
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存文件",
            os.path.basename(file_path)
        )
        
        if save_path:
            try:
                shutil.copy2(file_path, save_path)
                UIUtils.show_success(self, "成功", "文件下载成功")
            except Exception as e:
                UIUtils.show_error(self, "错误", f"文件下载失败：{str(e)}")

    # --- 添加附件处理逻辑 ---
    def handle_document_attachment(self, event, btn, doc_id):
        """处理文档附件的操作"""
        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            document = session.query(ProjectDocument).filter(ProjectDocument.id == doc_id).first()
            if not document:
                UIUtils.show_error(self, "错误", "找不到对应的文档记录")
                return

            # 调用通用的附件处理函数
            handle_attachment(
                event=event,
                btn=btn,
                item=document, # 传递文档对象
                session=session,
                parent_widget=self,
                project=self.current_project, # 传递当前项目
                item_type='document', # 标识类型
                attachment_attr='file_path', # 指定存储路径的属性名
                base_folder='documents' # 指定存储的根目录
            )
            # 刷新列表以更新按钮状态
            self.load_documents()

        except Exception as e:
            session.rollback() # Ensure rollback on error
            UIUtils.show_error(self, "附件操作错误", f"处理文档附件时出错: {e}")
        finally:
            session.close()