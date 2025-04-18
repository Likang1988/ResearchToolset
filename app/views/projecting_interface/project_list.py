from PySide6.QtWidgets import (QMainWindow, QWidget, QHeaderView, QVBoxLayout, QHBoxLayout,
                                 QLabel, QTableWidgetItem, QStackedWidget, QApplication)
from qfluentwidgets import PrimaryPushButton, ToolButton, InfoBar, Dialog
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, TableWidget, TableItemDelegate, TitleLabel, RoundMenu, Action
from ...components.project_dialog import ProjectDialog
from .project_budget import ProjectBudgetWidget
from ...models.database import init_db, add_project_to_db, sessionmaker, Project, Budget, Expense, Activity
from ...utils.ui_utils import UIUtils
from ...utils.db_utils import DBUtils
from sqlalchemy import func
import os
from datetime import datetime

class ProjectListWindow(QWidget):
    def __init__(self, engine=None):
        super().__init__()
        self.engine = engine
        
        
        self.project = None
        self.setWindowTitle("经费追踪")
        self.setup_ui()

    
    def setup_ui(self):
        # 创建主布局
        main_layout = QVBoxLayout(self)
        
        # 创建QStackedWidget
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # 创建项目清单页面
        self.project_page = QWidget()
        self.setup_project_page()
        self.stacked_widget.addWidget(self.project_page)
        
        # 初始显示项目清单页面
        self.stacked_widget.setCurrentWidget(self.project_page)



    def setup_project_page(self):
        layout = QVBoxLayout(self.project_page)
        #layout.setContentsMargins(9, 9, 9, 9)  # 统一设置边距为12像素
        layout.setSpacing(10)  # 设置组件之间的垂直间距为10像素
        
        # 标题
        title_layout = UIUtils.create_title_layout("项目清单")
        layout.addLayout(title_layout)
        
        # 按钮栏
        button_layout = QHBoxLayout()

        # 左侧按钮组
        left_buttons = QHBoxLayout()
        add_btn = UIUtils.create_action_button("添加项目", FluentIcon.ADD_TO)
        edit_btn = UIUtils.create_action_button("编辑项目", FluentIcon.EDIT)
        delete_btn = UIUtils.create_action_button("删除项目", FluentIcon.DELETE)
        
        left_buttons.addWidget(add_btn)
        left_buttons.addWidget(edit_btn)
        left_buttons.addWidget(delete_btn)
        left_buttons.addStretch()


        # 右侧按钮组
        right_buttons = QHBoxLayout()
        import_btn = UIUtils.create_action_button("导入数据", FluentIcon.EMBED)
        export_btn = UIUtils.create_action_button("导出数据", FluentIcon.DOWNLOAD)
        
        # 添加鼠标悬停提示
        import_btn.setToolTip("从JSON文件导入项目基本信息、预算配置、支出记录数据")
        export_btn.setToolTip("将项目基本信息、预算配置、支出记录数据导出为JSON文件")
        
        right_buttons.addStretch()
        right_buttons.addWidget(import_btn)
        right_buttons.addWidget(export_btn)
        
        # 连接信号
        add_btn.clicked.connect(self.add_project)
        edit_btn.clicked.connect(self.edit_project)
        delete_btn.clicked.connect(self.delete_selected_project)
        import_btn.clicked.connect(self.import_project_data)
        export_btn.clicked.connect(self.export_project_data)
        
       
        button_layout.addLayout(left_buttons)
        button_layout.addLayout(right_buttons)
        layout.addLayout(button_layout)
        
        
        # 项目表格
        self.project_table = TableWidget()
        self.project_table.setColumnCount(9)  # 增加一列
        self.project_table.setHorizontalHeaderLabels([
            "简称/代号/\n财务编号", "项目名称", "项目编号",
            "项目类别", "开始日期", "结束日期", "总经费\n（万元）", "项目\n管理", "经费\n管理"
        ])
        self.project_table.setSelectionBehavior(TableWidget.SelectRows)
        self.project_table.setSelectionMode(TableWidget.SingleSelection)
        self.project_table.setBorderVisible(True)
        self.project_table.setBorderRadius(8)
        self.project_table.setWordWrap(False)
        self.project_table.setItemDelegate(TableItemDelegate(self.project_table))

        # 设置表格样式
        UIUtils.set_table_style(self.project_table)
        
        # 设置列宽模式
        header = self.project_table.horizontalHeader()  # 获取水平表头
        header.setSectionResizeMode(QHeaderView.Interactive)  # 可调整列宽  
        
        # 隐藏行号
        self.project_table.verticalHeader().setVisible(False)
        
        # 设置初始列宽
        header.resizeSection(0, 93)  # 财务编号
        header.resizeSection(1, 330)  # 项目名称
        header.resizeSection(2, 150)  # 项目编号
        header.resizeSection(3, 180)  # 项目类别
        header.resizeSection(4, 90)  # 开始日期
        header.resizeSection(5, 90)  # 结束日期
        header.resizeSection(6, 80)  # 总经费
        header.resizeSection(7, 50)  # 项目管理
        header.resizeSection(8, 50)  # 经费管理
        
        # 允许用户调整列宽
        header.setSectionsMovable(True)  # 可移动列
        header.setStretchLastSection(True)  # 最后一列自动填充剩余空间
        
        layout.addWidget(self.project_table)
        self.refresh_project_table()
    def refresh_project_table(self):
        # 清空现有表格
        self.project_table.setRowCount(0)
        
        # 从数据库获取项目数据
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            # 按ID升序排序，使新添加的项目显示在最下方
            projects = session.query(Project).order_by(Project.id.asc()).all()
            
            # 填充表格数据
            for idx, project in enumerate(projects, 1):
                row_position = self.project_table.rowCount()
                self.project_table.insertRow(row_position)
                
                # 添加项目信息
                item = QTableWidgetItem(project.financial_code)
                item.setData(Qt.UserRole, project.id)  # 存储项目ID
                self.project_table.setItem(row_position, 0, item)
                self.project_table.setItem(row_position, 1, QTableWidgetItem(project.name))            
                self.project_table.setItem(row_position, 2, QTableWidgetItem(project.project_code))
                self.project_table.setItem(row_position, 3, QTableWidgetItem(project.project_type))
                self.project_table.setItem(row_position, 4, QTableWidgetItem(str(project.start_date)))
                self.project_table.setItem(row_position, 5, QTableWidgetItem(str(project.end_date)))
                self.project_table.setItem(row_position, 6, QTableWidgetItem(str(project.total_budget)))
                
                # 获取总预算执行率
                total_budget = session.query(Budget).filter(
                    Budget.project_id == project.id,
                    Budget.year.is_(None)
                ).first()
                
                if total_budget and total_budget.total_amount > 0:
                    # 计算所有年度预算的总支出
                    total_spent = session.query(func.sum(Budget.spent_amount)).filter(
                        Budget.project_id == project.id,
                        Budget.year.isnot(None)  # 只计算年度预算
                    ).scalar() or 0.0
                    
                    # 添加项目管理按钮
                    btn_widget = QWidget()
                    btn_layout = QHBoxLayout(btn_widget)
                    btn_layout.setContentsMargins(0, 0, 0, 0)
                    btn_layout.setAlignment(Qt.AlignCenter)
                    
                    manage_btn = ToolButton()
                    manage_btn.setIcon(QIcon(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'icons', 'project.svg'))))
                    manage_btn.setToolTip("项目管理")
                    manage_btn.clicked.connect(lambda checked, p=project: self.open_project_management(p))
                    btn_layout.addWidget(manage_btn)
                    manage_btn.setFixedSize(26, 26)
                    manage_btn.setIconSize(QSize(16, 16))
                    
                    self.project_table.setCellWidget(row_position, 7, btn_widget)
                else:
                    # 添加项目管理按钮（默认启用）
                    btn_widget = QWidget()
                    btn_layout = QHBoxLayout(btn_widget)
                    btn_layout.setContentsMargins(0, 0, 0, 0)
                    btn_layout.setAlignment(Qt.AlignCenter)
                    
                    manage_btn = ToolButton()
                    manage_btn.setIcon(QIcon(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'icons', 'project.svg'))))
                    manage_btn.setToolTip("项目管理")
                    manage_btn.clicked.connect(lambda checked, p=project: self.open_project_management(p))
                    btn_layout.addWidget(manage_btn)
                    manage_btn.setFixedSize(26, 26)
                    manage_btn.setIconSize(QSize(16, 16))
                    
                    self.project_table.setCellWidget(row_position, 7, btn_widget)
                
                
                # 经费管理按钮
                btn_widget = QWidget()  # 创建一个新的QWidget
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(0, 0, 0, 0)
                btn_layout.setAlignment(Qt.AlignCenter)  # 设置按钮居中对齐
                
                budget_btn = ToolButton()
                budget_btn.setIcon(QIcon(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'icons', 'budget.svg'))))
                budget_btn.setToolTip("经费管理")
                budget_btn.clicked.connect(lambda checked=False, p=project: self.open_project_budget(p))  # 传递项目对象
                btn_layout.addWidget(budget_btn)  # 将按钮添加到布局中
                # 按钮大小
                budget_btn.setFixedSize(26, 26)
                # 图标大小
                budget_btn.setIconSize(QSize(18, 18))

                self.project_table.setCellWidget(row_position, 8, btn_widget)  # 将按钮放置在第9列（操作列）
            
            session.close()
            

            # 禁止直接编辑
            self.project_table.setEditTriggers(TableWidget.NoEditTriggers)

            # 设置表格对齐方式
            for row_position in range(self.project_table.rowCount()):
                for col in range(self.project_table.columnCount()):
                    item = self.project_table.item(row_position, col)
                    if item:
                        # 第0、2、3、4、5列设置为居中对齐
                        if col in [0, 1, 2, 3, 4, 5]:
                            item.setTextAlignment(Qt.AlignCenter)
                        # 第6列(总经费)设置为右对齐
                        elif col in [6, 7]:
                            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        # 其他列保持默认左对齐
                        else:
                            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            
            
            
            # 添加右键菜单
            self.project_table.setContextMenuPolicy(Qt.CustomContextMenu)
            self.project_table.customContextMenuRequested.connect(self.show_context_menu)

        except Exception as e:
            session.rollback()
            UIUtils.show_error(
                title='错误',
                content=f'刷新项目列表失败：{str(e)}',
                parent=self
            )
        finally:
            session.close()
            
    def show_context_menu(self, pos):
        """显示右键菜单"""
        menu = RoundMenu(parent=self)
        
        # 获取右键点击的单元格
        item = self.project_table.itemAt(pos)
        if item:
            # 添加复制操作
            copy_action = Action(FluentIcon.COPY, "复制", self)
            copy_action.triggered.connect(lambda: self.copy_cell_content(item))
            menu.addAction(copy_action)
            
        # 显示菜单
        menu.exec_(self.project_table.viewport().mapToGlobal(pos))
        
    def copy_cell_content(self, item):
        """复制单元格内容"""
        if item:
            # 获取单元格内容
            content = item.text()
            clipboard = QApplication.clipboard()
            clipboard.setText(content)
            
    def add_project(self):
        """添加项目"""
        dialog = ProjectDialog(self)
        if dialog.exec() == ProjectDialog.Accepted:
            # 获取项目信息
            financial_code = dialog.financial_code.text().strip()
            name = dialog.project_name.text().strip()
            project_code = dialog.project_code.text().strip()
            project_type = dialog.project_type.currentText()
            start_date = dialog.start_date.date().toPython()
            end_date = dialog.end_date.date().toPython()
            total_budget = dialog.total_budget.text().strip()
            
            # 添加项目到数据库
            try:
                Session = sessionmaker(bind=self.engine)
                session = Session()
                
                # 创建新项目
                project = Project(
                    name=name,
                    financial_code=financial_code,
                    project_code=project_code,
                    project_type=project_type,
                    start_date=start_date,
                    end_date=end_date,
                    total_budget=float(total_budget) if total_budget else 0.0
                )
                session.add(project)
                session.flush()  # 获取项目ID
                
                # 保存项目ID供后续使用
                self.project_id = project.id
                
                # 记录添加项目的活动
                activity = Activity(
                    project_id=project.id,
                    type="项目",
                    action="新增",
                    description=f"添加项目：{name} - {financial_code}",
                    operator="系统用户"
                )
                session.add(activity)
                
                # 提交事务
                session.commit()
                
                # 刷新项目列表
                self.refresh_project_table()
                
                # 显示成功消息
                UIUtils.show_success(
                    title='成功',
                    content='项目添加成功',
                    parent=self
                )
                
            except Exception as e:
                session.rollback()
                UIUtils.show_error(
                    title='错误',
                    content=f'添加项目失败：{str(e)}',
                    parent=self
                )
            finally:
                session.close()
    def edit_project(self):
        selected_rows = self.project_table.selectedItems()
        if not selected_rows:
            UIUtils.show_warning(
                title='警告',
                content='请选择要编辑的项目！',
                parent=self
            )
            return
            
        row = selected_rows[0].row()
        project_id = self.project_table.item(row, 0).data(Qt.UserRole)
        
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            project = session.query(Project).filter(Project.id == project_id).first()
            
            if project:
                dialog = ProjectDialog(self)
                dialog.financial_code.setText(project.financial_code)
                dialog.project_name.setText(project.name)
                dialog.project_code.setText(project.project_code)
                dialog.project_type.setCurrentText(project.project_type)
                dialog.start_date.setDate(project.start_date)
                dialog.end_date.setDate(project.end_date)
                dialog.total_budget.setText(str(project.total_budget))
                
                if dialog.exec() == ProjectDialog.Accepted:
                    old_name = project.name
                    old_financial_code = project.financial_code
                    
                    project.financial_code = dialog.financial_code.text().strip()
                    project.name = dialog.project_name.text().strip()
                    project.project_code = dialog.project_code.text().strip()
                    project.project_type = dialog.project_type.currentText()
                    project.start_date = dialog.start_date.date().toPython()
                    project.end_date = dialog.end_date.date().toPython()
                    project.total_budget = float(dialog.total_budget.text()) if dialog.total_budget.text() else 0.0
                    
                    # 记录编辑项目的活动
                    activity = Activity(
                        project_id=project.id,
                        type="项目",
                        action="编辑",
                        description=f"编辑项目：{old_name} - {old_financial_code}",
                        operator="系统用户"
                    )
                    session.add(activity)
                    
                    session.commit()
                    self.refresh_project_table()
            else:
                UIUtils.show_warning(
                    title='警告',
                    content='未找到选中的项目！',
                    parent=self
                )
                
        except Exception as e:
            session.rollback()
            UIUtils.show_error(
                title='错误',
                content=f'编辑项目失败：{str(e)}',
                parent=self
            )
        finally:
            session.close()
            
    def delete_selected_project(self):
        selected_rows = self.project_table.selectedItems()
        if not selected_rows:
            UIUtils.show_warning(
                title='警告',
                content='请选择要删除的项目！',
                parent=self
            )
            return
            
        row = selected_rows[0].row()
        project_id = self.project_table.item(row, 0).data(Qt.UserRole)
        
        # 使用InfoBar显示确认对话框
        confirm_dialog = Dialog(
            '确认删除',
            '确定要删除该项目吗？此操作不可恢复！',
            self
        )
        
        if confirm_dialog.exec():
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            try:
                # 获取项目信息用于记录活动
                project = session.query(Project).filter(Project.id == project_id).first()
                if project:
                    # 记录删除项目的活动
                    activity = Activity(
                        project_id=project.id,
                        type="项目",
                        action="删除",
                        description=f"删除项目：{project.name} - {project.financial_code}",
                        operator="系统用户"
                    )
                    session.add(activity)
                    
                    # 删除项目
                    session.delete(project)
                    session.commit()
                    self.refresh_project_table()
                    UIUtils.show_success(
                    title='成功',
                    content='项目已成功删除',
                    parent=self
                )
            except Exception as e:
                session.rollback()
                UIUtils.show_error(
                    title='错误',
                    content=f'删除项目失败：{str(e)}',
                    parent=self
                )
            finally:
                session.close()
        
    
    def open_project_management(self, project):
        """打开项目管理界面"""
        # 获取主窗口实例
        main_window = self.window()
        if main_window:
            # 创建项目管理界面并传递 engine
            from app.views.projecting_interface.project_management import ProjectManagementWidget
            # Pass self.engine during instantiation
            management_widget = ProjectManagementWidget(project, engine=self.engine)
            management_widget.setObjectName("projectManagementInterface")
            # management_widget.engine = self.engine # No longer needed as it's passed in __init__
            # 直接在主窗口中显示项目管理界面
            main_window.stackedWidget.addWidget(management_widget)
            main_window.stackedWidget.setCurrentWidget(management_widget)

    def open_project_budget(self, project):
        """打开预算管理界面"""
        # 获取主窗口实例
        main_window = self.window()
        if main_window:
            # 创建项目预算界面
            from app.views.projecting_interface.project_budget import ProjectBudgetWidget
            budget_widget = ProjectBudgetWidget(self.engine, project)
            budget_widget.setObjectName("projectBudgetInterface")
            # 直接在主窗口中显示项目预算界面
            main_window.stackedWidget.addWidget(budget_widget)
            main_window.stackedWidget.setCurrentWidget(budget_widget)

            
    def add_budget(self, budget_data):
        """添加项目预算"""
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            # 创建新的预算记录
            budget = Budget(
                project_id=budget_data['project_id'],
                year=budget_data['year'],
                total_amount=budget_data['total_amount'],
                remark=budget_data.get('remark', '')
            )
            
            session.add(budget)
            session.commit()
            
            # 如果预算管理窗口已打开，则刷新数据
            if hasattr(self, 'budget_widget'):
                self.budget_widget.refresh_budget_table()
                
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.c

    def export_project_data(self):
        """导出项目数据"""
        # 获取选中的项目
        selected_items = self.project_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(
                title='警告',
                content='请先选择要导出的项目',
                parent=self
            )
            return
        
        # 获取选中行的项目ID
        row = selected_items[0].row()
        project_id = self.project_table.item(row, 0).data(Qt.UserRole)
        
        # 选择保存文件的位置
        from PySide6.QtWidgets import QFileDialog
        import json
        from datetime import datetime
        
        file_name = QFileDialog.getSaveFileName(
            self,
            "导出项目数据",
            f"项目数据_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON文件 (*.json)"
        )[0]
        
        if not file_name:
            return
            
        try:
            # 创建数据库会话
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            # 获取项目信息
            project = session.query(Project).get(project_id)
            if not project:
                raise Exception("项目不存在")
            
            # 准备导出数据
            export_data = {
                'project': {
                    'id': project.id,
                    'name': project.name,
                    'financial_code': project.financial_code,
                    'project_code': project.project_code,
                    'project_type': project.project_type,
                    'start_date': project.start_date.isoformat(),
                    'end_date': project.end_date.isoformat(),
                    'total_budget': float(project.total_budget)
                },
                'budgets': [],
                'expenses': []
            }
            
            # 获取预算信息
            budgets = session.query(Budget).filter(Budget.project_id == project_id).all()
            for budget in budgets:
                budget_data = {
                    'id': budget.id,
                    'year': budget.year,
                    'total_amount': float(budget.total_amount),
                    'spent_amount': float(budget.spent_amount),
                    'items': []
                }
                
                # 获取预算项信息
                for item in budget.budget_items:
                    item_data = {
                        'id': item.id,
                        'category': item.category.value,
                        'amount': float(item.amount),
                        'spent_amount': float(item.spent_amount)
                    }
                    budget_data['items'].append(item_data)
                
                export_data['budgets'].append(budget_data)
            
            # 获取支出信息
            expenses = session.query(Expense).join(Budget).filter(Budget.project_id == project_id).all()
            for expense in expenses:
                expense_data = {
                    'id': expense.id,
                    'budget_id': expense.budget_id,
                    'category': expense.category.value,
                    'content': expense.content,
                    'specification': expense.specification,
                    'supplier': expense.supplier,
                    'amount': float(expense.amount),
                    'date': expense.date.isoformat(),
                    'remarks': expense.remarks,
                    'voucher_path': expense.voucher_path
                }
                export_data['expenses'].append(expense_data)
            
            # 保存数据到文件
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            session.close()
            
            UIUtils.show_success(
                title='成功',
                content=f'项目数据已导出到：\n{file_name}',
                parent=self
            )
            
            # 在文件资源清单器中打开导出目录
            import os
            os.startfile(os.path.dirname(file_name)) if os.name == 'nt' else os.system(f'open {os.path.dirname(file_name)}')
            
        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f'导出项目数据失败：{str(e)}',
                parent=self
            )
    
    def import_project_data(self):
        """导入项目数据"""
        # 选择要导入的文件
        from PySide6.QtWidgets import QFileDialog
        import json
        from ...models.database import BudgetCategory, BudgetItem
        
        file_name = QFileDialog.getOpenFileName(
            self,
            "导入项目数据",
            "",
            "JSON文件 (*.json)"
        )[0]
        
        if not file_name:
            return
            
        try:
            # 读取数据文件
            with open(file_name, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            # 验证数据格式
            if not all(key in import_data for key in ['project', 'budgets', 'expenses']):
                raise Exception("数据格式不正确")
            
            # 创建数据库会话
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            try:
                # 检查项目是否已存在
                existing_project = session.query(Project).filter(
                    Project.financial_code == import_data['project']['financial_code']
                ).first()
                
                if existing_project:
                    # 如果项目已存在，询问用户是否覆盖
                    from qfluentwidgets import MessageBox
                    box = MessageBox(
                        '项目已存在',
                        '检测到相同财务编号的项目已存在，是否覆盖？\n注意：覆盖将删除原有的所有预算和支出数据！',
                        parent=self
                    )
                    box.yesButton.setText('覆盖')
                    box.cancelButton.setText('取消')
                    
                    if not box.exec():
                        session.close()
                        return
                    
                    # 删除原有的项目数据
                    session.delete(existing_project)
                    session.commit()
                
                # 创建新项目
                project_data = import_data['project']
                try:
                    project = Project(
                        name=project_data['name'],
                        financial_code=project_data['financial_code'],
                        project_code=project_data['project_code'],
                        project_type=project_data['project_type'],
                        start_date=datetime.fromisoformat(project_data['start_date']),
                        end_date=datetime.fromisoformat(project_data['end_date']),
                        total_budget=project_data['total_budget']
                    )
                except KeyError as e:
                    raise Exception(f"项目数据缺少必要字段：{str(e)}")
                
                session.add(project)
                session.flush()  # 获取新项目的ID
                
                # 导入预算数据
                for budget_data in import_data['budgets']:
                    try:
                        # 检查是否存在相同的项目ID和年度组合
                        existing_budget = session.query(Budget).filter(
                            Budget.project_id == project.id,
                            Budget.year == budget_data['year']
                        ).first()
                        
                        if existing_budget:
                            # 如果存在，更新现有记录
                            existing_budget.total_amount = budget_data['total_amount']
                            existing_budget.spent_amount = budget_data['spent_amount']
                            budget = existing_budget
                        else:
                            # 如果不存在，创建新记录
                            budget = Budget(
                                project_id=project.id,
                                year=budget_data['year'],
                                total_amount=budget_data['total_amount'],
                                spent_amount=budget_data['spent_amount']
                            )
                            session.add(budget)
                    except KeyError as e:
                        raise Exception(f"预算数据缺少必要字段：{str(e)}")
                        
                    session.flush()
                    
                    # 删除现有的预算项
                    if existing_budget:
                        session.query(BudgetItem).filter(BudgetItem.budget_id == budget.id).delete()
                    
                    # 导入预算项
                    for item_data in budget_data['items']:
                        try:
                            budget_item = BudgetItem(
                                budget_id=budget.id,
                                category=BudgetCategory(item_data['category']),
                                amount=item_data['amount'],
                                spent_amount=item_data['spent_amount']
                            )
                        except KeyError as e:
                            raise Exception(f"预算项数据缺少必要字段：{str(e)}")
                            
                        session.add(budget_item)
                
                # 创建预算ID映射表
                budget_id_map = {}
                
                # 导入支出数据
                for expense_data in import_data['expenses']:
                    try:
                        # 根据年份找到对应的新预算ID
                        expense_date = datetime.fromisoformat(expense_data['date'])
                        expense_year = expense_date.year
                        
                        # 查找对应年份的预算
                        budget = session.query(Budget).filter(
                            Budget.project_id == project.id,
                            Budget.year == expense_year
                        ).first()
                        
                        if budget:
                            expense = Expense(
                                project_id=project.id,
                                budget_id=budget.id,  # 使用新的预算ID
                                category=BudgetCategory(expense_data['category']),
                                content=expense_data['content'],
                                specification=expense_data['specification'],
                                supplier=expense_data['supplier'],
                                amount=expense_data['amount'],
                                date=expense_date,
                                remarks=expense_data['remarks'],
                                voucher_path=expense_data.get('voucher_path', '')
                            )
                    except KeyError as e:
                        raise Exception(f"支出数据缺少必要字段：{str(e)}")
                        
                    session.add(expense)
                
                session.commit()
                
                UIUtils.show_success(
                    title='成功',
                    content='项目数据导入成功',
                    parent=self
                )
                
                # 刷新项目表格
                self.refresh_project_table()
                
                # 如果当前有打开的支出管理窗口，刷新其数据
                if hasattr(self, 'expense_widget') and self.expense_widget is not None:
                    self.expense_widget.load_expenses()
                    self.expense_widget.load_statistics()
                
            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()
                
        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f'导入项目数据失败：{str(e)}',
                parent=self
            )