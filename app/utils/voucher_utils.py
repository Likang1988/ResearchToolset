from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget, QHBoxLayout
from qfluentwidgets import FluentIcon, ToolButton, RoundMenu, Action
import os
import subprocess
import platform
from ..utils.ui_utils import UIUtils


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


def view_voucher(voucher_path, parent=None):
    """
    查看凭证文件
    
    Args:
        voucher_path: 凭证文件路径
        parent: 父窗口，用于显示错误信息
    """
    try:
        if platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', voucher_path])
        elif platform.system() == 'Windows':
            os.startfile(voucher_path)
        else:  # Linux或其他系统
            subprocess.run(['xdg-open', voucher_path])
    except Exception as e:
        if parent:
            UIUtils.show_warning(
                title='警告',
                content=f"打开凭证文件失败: {str(e)}",
                parent=parent
            )


def create_voucher_menu(parent, current_path, view_func, replace_func, delete_func):
    """
    创建凭证右键菜单
    
    Args:
        parent: 父窗口
        current_path: 当前凭证路径
        view_func: 查看凭证的回调函数
        replace_func: 替换凭证的回调函数
        delete_func: 删除凭证的回调函数
    
    Returns:
        menu: 创建的右键菜单
    """
    menu = RoundMenu(parent=parent)
    
    # 添加菜单项并设置图标
    view_action = Action(FluentIcon.VIEW, "查看凭证", parent)
    replace_action = Action(FluentIcon.SYNC, "替换凭证", parent)
    delete_action = Action(FluentIcon.DELETE, "删除凭证", parent)
    
    # 连接信号到槽函数
    view_action.triggered.connect(lambda: view_func(current_path))
    replace_action.triggered.connect(replace_func)
    delete_action.triggered.connect(delete_func)
    
    menu.addAction(view_action)
    menu.addAction(replace_action)
    menu.addAction(delete_action)
    
    return menu