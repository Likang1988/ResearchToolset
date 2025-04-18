from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QComboBox, QLineEdit, QFileDialog, QDialog, QLabel # Added QLabel
from PySide6.QtCore import Qt
from qfluentwidgets import TitleLabel, PrimaryPushButton, FluentIcon, InfoBar, Dialog
from ...utils.ui_utils import UIUtils
from ...models.database import Project, Base, get_engine, sessionmaker # Added sessionmaker import
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum as SQLEnum, DateTime, Engine # Added Engine type hint
from enum import Enum
from datetime import datetime
import os
import shutil

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
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # 文档表单
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("文档名称")
        layout.addWidget(self.name_edit)
        self.type_combo = QComboBox()
        for doc_type in DocumentType:
            self.type_combo.addItem(doc_type.value)
        layout.addWidget(self.type_combo)
        
        self.version_edit = QLineEdit()
        self.version_edit.setPlaceholderText("版本号")
        layout.addWidget(self.version_edit)
        
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("文档描述")
        layout.addWidget(self.description_edit)
        
        self.keywords_edit = QLineEdit()
        self.keywords_edit.setPlaceholderText("关键词（用逗号分隔）")
        layout.addWidget(self.keywords_edit)
        
        self.uploader_edit = QLineEdit()
        self.uploader_edit.setPlaceholderText("上传人")
        layout.addWidget(self.uploader_edit)
        
        # 文件选择
        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        file_layout.addWidget(self.file_path_edit)
        
        select_file_btn = PrimaryPushButton("选择文件")
        select_file_btn.clicked.connect(self.select_file)
        file_layout.addWidget(select_file_btn)
        layout.addLayout(file_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        save_btn = PrimaryPushButton("保存")
        cancel_btn = PrimaryPushButton("取消")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
    
    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if file_path:
            self.file_path_edit.setText(file_path)
    
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
        selector_label = TitleLabel("项目文档:", self)
        self.project_selector = UIUtils.create_project_selector(self.engine, self)
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.project_selector)
        selector_layout.addStretch()
        self.main_layout.addLayout(selector_layout)
        # Connect signal after UI setup
        self.project_selector.currentIndexChanged.connect(self._on_project_selected)
        # --- Project Selector End ---

        # 按钮栏
        add_btn = UIUtils.create_action_button("上传文档", FluentIcon.ADD)
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
        self.document_table.setColumnCount(8)
        self.document_table.setHorizontalHeaderLabels(["文档名称", "类型", "版本", "描述", "关键词", "上传人", "上传时间", "文件路径"])
        UIUtils.set_table_style(self.document_table)
        
        self.main_layout.addWidget(self.document_table)
        
        # 搜索栏
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入关键词搜索文档")
        self.search_edit.textChanged.connect(self.search_documents)
        search_layout.addWidget(self.search_edit)
        
        self.type_filter = QComboBox()
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
                self.document_table.setItem(row, 0, QTableWidgetItem(doc.name))
                self.document_table.setItem(row, 1, QTableWidgetItem(doc.doc_type.value))
                self.document_table.setItem(row, 2, QTableWidgetItem(doc.version))
                self.document_table.setItem(row, 3, QTableWidgetItem(doc.description))
                self.document_table.setItem(row, 4, QTableWidgetItem(doc.keywords))
                self.document_table.setItem(row, 5, QTableWidgetItem(doc.uploader))
                self.document_table.setItem(row, 6, QTableWidgetItem(str(doc.upload_time)))
                self.document_table.setItem(row, 7, QTableWidgetItem(doc.file_path))
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