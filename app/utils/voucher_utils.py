from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget, QHBoxLayout
from qfluentwidgets import FluentIcon, ToolButton


def create_voucher_button(expense_id, voucher_path, handle_voucher_func):
    """
    创建统一的凭证按钮
    
    Args:
        expense_id: 支出ID
        voucher_path: 凭证文件路径
        handle_voucher_func: 处理凭证的函数
        
    Returns:
        container: 包含按钮的容器widget
    """
    # 创建按钮
    upload_btn = ToolButton()
    upload_btn.setFixedSize(28, 28)  # 设置按钮大小
    
    # 根据是否有凭证设置不同的图标和样式
    if not voucher_path:
        # 显示添加图标
        upload_btn.setIcon(FluentIcon.ADD_TO)
    else:
        # 显示凭证图标
        upload_btn.setIcon(FluentIcon.CERTIFICATE)
    
    # 设置图标大小
    upload_btn.setIconSize(QSize(16, 16))
    

    
    # 设置属性
    upload_btn.setProperty("expense_id", expense_id)
    upload_btn.setProperty("voucher_path", voucher_path)
    
    # 设置鼠标点击事件
    upload_btn.mousePressEvent = lambda event, btn=upload_btn: handle_voucher_func(event, btn)
    
    # 创建容器widget用于居中显示按钮
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.setAlignment(Qt.AlignCenter)
    layout.addWidget(upload_btn, 0, Qt.AlignCenter)
    
    return container