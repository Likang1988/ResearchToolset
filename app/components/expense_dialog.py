from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                 QFileDialog)
from qfluentwidgets import (LineEdit, PushButton, DateEdit,
                          FluentIcon, ComboBox, BodyLabel)
from .batch_import_dialog import BatchImportDialog
from PySide6.QtCore import QDate
from ..models.database import BudgetCategory, Expense, Budget # Import Expense and Budget
from ..utils.ui_utils import UIUtils

class ExpenseDialog(QDialog):
    def __init__(self, engine, budget: Budget, expense: Expense = None, parent=None):
        super().__init__(parent)
        self.engine = engine # Store engine if needed, though not used in current methods
        self.budget = budget # Store budget object
        self.expense = expense # Store expense object if editing
        self.setWindowTitle("支出信息" if not expense else "编辑支出信息")
        self.setup_ui()
        if self.expense:
            self.set_data(self.expense) # Pass the actual expense object

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10) # Consistent spacing

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
        self.content = LineEdit()
        self.content.setPlaceholderText("请输入开支内容，必填")
        content_layout.addWidget(self.content)
        layout.addLayout(content_layout)

        # 规格型号
        specification_layout = QHBoxLayout()
        specification_layout.addWidget(BodyLabel("规格型号:"))
        self.specification = LineEdit()
        self.specification.setPlaceholderText("请输入规格型号")
        specification_layout.addWidget(self.specification)
        layout.addLayout(specification_layout)

        # 供应商
        supplier_layout = QHBoxLayout()
        supplier_layout.addWidget(BodyLabel("供 应 商 :")) # Keep alignment
        self.supplier = LineEdit()
        self.supplier.setPlaceholderText("请输入供应商")
        supplier_layout.addWidget(self.supplier)
        layout.addLayout(supplier_layout)

        # 报账金额
        amount_layout = QHBoxLayout()
        amount_layout.addWidget(BodyLabel("报账金额:"))
        self.amount = LineEdit()
        self.amount.setPlaceholderText("单位：元，必填")
        amount_layout.addWidget(self.amount)
        layout.addLayout(amount_layout)

        # 报账日期
        date_layout = QHBoxLayout()
        date_layout.addWidget(BodyLabel("报账日期:"))
        self.date = DateEdit()
        self.date.setDate(QDate.currentDate())
        self.date.setDisplayFormat("yyyy-MM-dd") # Ensure display format
        date_layout.addWidget(self.date)
        layout.addLayout(date_layout)

        # 备注
        remarks_layout = QHBoxLayout()
        remarks_layout.addWidget(BodyLabel("备       注:")) # Keep alignment
        self.remarks = LineEdit()
        remarks_layout.addWidget(self.remarks)
        layout.addLayout(remarks_layout)

        voucher_layout = QHBoxLayout()
        voucher_layout.addWidget(BodyLabel("支出凭证:"))
        self.voucher_path = None # Initialize voucher path storage
        self.voucher_btn = PushButton("选择凭证文件", self, FluentIcon.FOLDER)
        self.voucher_btn.clicked.connect(self.select_voucher)
        voucher_layout.addWidget(self.voucher_btn)
        layout.addLayout(voucher_layout)

        layout.addStretch() # Add stretch before buttons

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch() # Push buttons to the right

        if not self.expense:
            import_btn = PushButton("批量导入", self, FluentIcon.DICTIONARY_ADD)
            import_btn.clicked.connect(self.show_import_dialog)
            button_layout.addWidget(import_btn)

        save_btn = PushButton("保存", self, FluentIcon.SAVE)
        cancel_btn = PushButton("取消", self, FluentIcon.CLOSE)
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
            amount_text = self.amount.text().strip()
            if not amount_text:
                 UIUtils.show_warning(self, '警告', '报账金额不能为空')
                 return
            amount = float(amount_text)
            if amount <= 0:
                UIUtils.show_warning(self, '警告', '支出金额必须大于0')
                return

            # 验证必填字段
            if not self.content.text().strip():
                UIUtils.show_warning(self, '警告', '开支内容不能为空')
                return

            super().accept()

        except ValueError:
            UIUtils.show_warning(self, '警告', '请输入有效的金额')

    def show_import_dialog(self):
        """显示批量导入对话框"""
        dialog = BatchImportDialog(self.budget.project_id, self)
        dialog.exec()

    def select_voucher(self):
        """选择凭证文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择凭证文件",
            "",
            "支持的文件 (*.pdf *.jpg *.jpeg *.png *.doc *.docx *.xls *.xlsx)" # Expanded types
        )
        if file_path:
            self.voucher_path = file_path
            filename = os.path.basename(file_path)
            self.voucher_btn.setText(f"已选: {filename[:15]}..." if len(filename) > 15 else f"已选: {filename}")
            self.voucher_btn.setToolTip(file_path)

    def get_data(self):
        """获取表单数据"""
        amount_val = 0.0
        try:
            amount_val = float(self.amount.text())
        except ValueError:
            pass # Should be caught by accept validation, but default defensively

        return {
            'category': BudgetCategory(self.category.currentText()),
            'content': self.content.text().strip(),
            'specification': self.specification.text().strip(),
            'supplier': self.supplier.text().strip(),
            'amount': amount_val,
            'date': self.date.date().toPython(),
            'remarks': self.remarks.text().strip(),
            'voucher_path': self.voucher_path if self.voucher_path is not None else (self.expense.voucher_path if self.expense else None)
        }

    def set_data(self, expense_data: Expense):
        """设置表单数据"""
        self.category.setCurrentText(expense_data.category.value)
        self.content.setText(expense_data.content)
        self.specification.setText(expense_data.specification or '')
        self.supplier.setText(expense_data.supplier or '')
        self.amount.setText(str(expense_data.amount))
        self.date.setDate(QDate(expense_data.date)) # Convert date to QDate
        self.remarks.setText(expense_data.remarks or '')
        self.voucher_path = expense_data.voucher_path
        if self.voucher_path and os.path.exists(self.voucher_path):
             filename = os.path.basename(self.voucher_path)
             self.voucher_btn.setText(f"已选: {filename[:15]}..." if len(filename) > 15 else f"已选: {filename}")
             self.voucher_btn.setToolTip(self.voucher_path)
        else:
             self.voucher_btn.setText("选择凭证文件")
             self.voucher_btn.setToolTip("")

    def add_expenses(self, expenses_data):
        """批量添加支出"""
        self.parent().add_expenses(expenses_data)
