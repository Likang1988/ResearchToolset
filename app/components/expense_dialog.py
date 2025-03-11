from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                                 QWidget, QMessageBox, QFileDialog)
from qfluentwidgets import (LineEdit, PushButton, DateEdit,
                          InfoBar, MessageBox, FluentIcon, ComboBox, EditableComboBox, BodyLabel)
from .batch_import_dialog import BatchImportDialog
from PySide6.QtCore import Qt, QDate
from ..models.database import BudgetCategory
from ..utils.ui_utils import UIUtils

class ExpenseDialog(QDialog):
    def __init__(self, project_id, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.setWindowTitle("支出信息")
        self.setup_ui()
        self.load_history_data()
        
    def load_history_data(self):
        """从数据库加载历史数据"""
        from ..models.database import sessionmaker, Expense
        try:
            # 遍历父窗口链，找到包含engine属性的窗口
            parent = self.parent()
            while parent:
                if hasattr(parent, 'engine'):
                    engine = parent.engine
                    break
                parent = parent.parent()
            else:
                raise AttributeError("无法找到包含engine属性的父窗口")
            Session = sessionmaker(bind=engine)
            session = Session()
            
            # 获取开支内容历史记录
            contents = session.query(Expense.content).distinct().all()
            self.content.addItems([c[0] for c in contents if c[0]])
            
            # 获取规格型号历史记录
            specifications = session.query(Expense.specification).distinct().all()
            self.specification.addItems([s[0] for s in specifications if s[0]])
            
            # 获取供应商历史记录
            suppliers = session.query(Expense.supplier).distinct().all()
            self.supplier.addItems([s[0] for s in suppliers if s[0]])
            
        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f'加载历史数据失败: {str(e)}',
                parent=self
            )
        finally:
            if session:
                session.close()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 类别
        category_layout = QHBoxLayout()
        category_layout.addWidget(BodyLabel("费用类别:"))
        self.category = ComboBox()
        for category in BudgetCategory:
            self.category.addItem(category.value)
        category_layout.addWidget(self.category)
        layout.addLayout(category_layout)
        
        # 开支内容
        content_layout = QHBoxLayout()
        content_layout.addWidget(BodyLabel("开支内容:"))
        self.content = EditableComboBox()
        self.content.setPlaceholderText("请输入开支内容")
        content_layout.addWidget(self.content)
        layout.addLayout(content_layout)
        
        # 规格型号
        specification_layout = QHBoxLayout()
        specification_layout.addWidget(BodyLabel("规格型号:"))
        self.specification = EditableComboBox()
        self.specification.setPlaceholderText("请输入规格型号")
        specification_layout.addWidget(self.specification)
        layout.addLayout(specification_layout)
        
        # 供应商
        supplier_layout = QHBoxLayout()
        supplier_layout.addWidget(BodyLabel("供应商:"))
        self.supplier = EditableComboBox()
        self.supplier.setPlaceholderText("请输入供应商")
        supplier_layout.addWidget(self.supplier)
        layout.addLayout(supplier_layout)
        
        # 报账金额
        amount_layout = QHBoxLayout()
        amount_layout.addWidget(BodyLabel("报账金额:"))
        self.amount = LineEdit()
        self.amount.setPlaceholderText("单位：元")
        amount_layout.addWidget(self.amount)
        layout.addLayout(amount_layout)
        
        # 报账日期
        date_layout = QHBoxLayout()
        date_layout.addWidget(BodyLabel("报账日期:"))
        self.date = DateEdit()
        self.date.setDate(QDate.currentDate())
        date_layout.addWidget(self.date)
        layout.addLayout(date_layout)
        
        # 备注
        remarks_layout = QHBoxLayout()
        remarks_layout.addWidget(BodyLabel("备注:"))
        self.remarks = LineEdit()
        remarks_layout.addWidget(self.remarks)
        layout.addLayout(remarks_layout)
        
        # 支出凭证
        voucher_layout = QHBoxLayout()
        voucher_layout.addWidget(BodyLabel("支出凭证:"))
        self.voucher_path = None  # 存储凭证路径
        self.voucher_btn = PushButton("选择凭证文件", self, FluentIcon.FOLDER)
        self.voucher_btn.clicked.connect(self.select_voucher)
        voucher_layout.addWidget(self.voucher_btn)
        layout.addLayout(voucher_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        # 添加批量导入按钮
        import_btn = PushButton("批量导入", self, FluentIcon.DICTIONARY_ADD)
        import_btn.clicked.connect(self.show_import_dialog)
        
        # 按钮样式与project_dialog一致
        save_btn = PushButton("保存", self, FluentIcon.SAVE)
        cancel_btn = PushButton("取消", self, FluentIcon.CLOSE)
        button_layout.addWidget(import_btn)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        # 连接信号
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        
    def accept(self):
        """确认对话框"""
        try:
            # 验证金额
            amount = float(self.amount.text())
            if amount <= 0:
                UIUtils.show_warning(
                    title='警告',
                    content='支出金额必须大于0',
                    parent=self
                )
                return
            
            # 验证必填字段
            if not self.content.currentText().strip():
                UIUtils.show_warning(
                    title='警告',
                    content='开支内容不能为空',
                    parent=self
                )
                return
            
            super().accept()
            
        except ValueError:
            UIUtils.show_warning(
                title='警告',
                content='请输入有效的金额',
                parent=self
            )
            
    def show_import_dialog(self):
        """显示批量导入对话框"""
        dialog = BatchImportDialog(self.project_id, self)
        dialog.exec()
            
    def select_voucher(self):
        """选择凭证文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择凭证文件",
            "",
            "支持的文件 (*.pdf *.jpg *.jpeg *.png)"
        )
        if file_path:
            self.voucher_path = file_path
            self.voucher_btn.setText("已选择凭证")
    
    def get_data(self):
        """获取表单数据"""
        return {
            'category': BudgetCategory(self.category.currentText()),
            'content': self.content.currentText(),
            'specification': self.specification.currentText(),
            'supplier': self.supplier.currentText(),
            'amount': float(self.amount.text()),
            'date': self.date.date().toPython(),
            'remarks': self.remarks.text(),
            'voucher_path': self.voucher_path
        }
    
    def set_data(self, data):
        """设置表单数据"""
        self.category.setCurrentText(data['category'].value)
        self.content.setCurrentText(data['content'])
        self.specification.setCurrentText(data['specification'] or '')
        self.supplier.setCurrentText(data['supplier'] or '')
        self.amount.setText(str(data['amount']))
        self.date.setDate(data['date'])
        self.remarks.setText(data['remarks'] or '')
        self.voucher_path = data.get('voucher_path')
        if self.voucher_path:
            self.voucher_btn.setText("已有凭证")
            
    def add_expenses(self, expenses_data):
        """批量添加支出"""
        self.parent().add_expenses(expenses_data)
