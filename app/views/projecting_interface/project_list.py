from PySide6.QtWidgets import (QWidget, QHeaderView, QVBoxLayout, QHBoxLayout,
                                 QTableWidgetItem, QStackedWidget, QApplication)
from qfluentwidgets import Dialog, BodyLabel, ToolTipFilter, ToolTipPosition
from PySide6.QtCore import Qt, Signal # 导入 Signal
from qfluentwidgets import FluentIcon, TableWidget, TableItemDelegate, RoundMenu, Action
import os # 导入 os 模块
import shutil # 导入 shutil 模块
from ...components.project_dialog import ProjectDialog
from ...models.database import init_db, add_project_to_db, sessionmaker, Project, Budget, Expense, Actionlog, GanttTask, GanttDependency # 导入 GanttTask 和 GanttDependency
from ...utils.ui_utils import UIUtils
from datetime import datetime

class ProjectListWindow(QWidget):
    # 定义一个信号，当项目列表更新时发射
    project_list_updated = Signal()

    def __init__(self, engine=None):
        super().__init__()
        self.engine = engine
        
        
        self.project = None
        self.setup_ui()

    
    def setup_ui(self):
        # 创建主布局
        main_layout = QVBoxLayout(self)
        
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
        layout.setSpacing(10)  # 设置组件之间的垂直间距为10像素
        
        # 标题
        title_layout = UIUtils.create_title_layout("项目清单")
        layout.addLayout(title_layout)
        # 标题悬停提示
        self.title_label = title_layout.itemAt(0).widget()
        self.title_label.setToolTip("用于创建和管理项目的基本信息，后续项目经费、进度、文档、成果管理基于此列表中项目")
        self.title_label.installEventFilter(ToolTipFilter(self.title_label, showDelay=300, position=ToolTipPosition.RIGHT))
        
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
        #button_layout.addLayout(right_buttons)
        layout.addLayout(button_layout)
        
        
        # 项目表格
        self.project_table = TableWidget()
        self.project_table.setColumnCount(8)  # 减少两列
        self.project_table.setHorizontalHeaderLabels([
            "简称/代号/\n财务编号", "项目名称", "项目编号",
            "项目类别", "开始日期", "结束日期", "总经费\n（万元）","负责人" 
        ])
        self.project_table.setSelectionBehavior(TableWidget.SelectRows)
        self.project_table.setSelectionMode(TableWidget.SingleSelection)
        self.project_table.setBorderVisible(True)
        self.project_table.setBorderRadius(8)
        self.project_table.setWordWrap(False)
        self.project_table.setItemDelegate(TableItemDelegate(self.project_table))

        # 设置表格样式
        UIUtils.set_table_style(self.project_table)
        
        # 减小统计表格表头字号和行高
        stats_header = self.project_table.horizontalHeader()
        stats_header.setStyleSheet("""
            QHeaderView::section {
                font-size: 12px; /* 减小字号 */
                padding: 2px 4px; /* 调整内边距以影响行高 */
            }
        """)
        
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
        header.resizeSection(7, 80)  # 负责人 
                        
        layout.addWidget(self.project_table)
        self.refresh_project_table()

    def refresh_project_table(self):
        # 清空现有表格
        self.project_table.setRowCount(0)
        
        # 从数据库获取项目数据
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            projects = session.query(Project).order_by(Project.id.asc()).all()
            
            # 设置表格行数
            self.project_table.setRowCount(len(projects))

            # 填充表格数据
            for row_position, project in enumerate(projects):
                # 添加项目信息
                item = QTableWidgetItem(project.financial_code)
                item.setData(Qt.UserRole, project.id)  # 存储项目ID
                self.project_table.setItem(row_position, 0, item)

                item_name = QTableWidgetItem(project.name)
                self.project_table.setItem(row_position, 1, item_name)

                item_code = QTableWidgetItem(project.project_code)
                self.project_table.setItem(row_position, 2, item_code)

                item_type = QTableWidgetItem(project.project_type)
                self.project_table.setItem(row_position, 3, item_type)

                item_start_date = QTableWidgetItem(str(project.start_date))
                self.project_table.setItem(row_position, 4, item_start_date)

                item_end_date = QTableWidgetItem(str(project.end_date))
                self.project_table.setItem(row_position, 5, item_end_date)

                item_budget = QTableWidgetItem(f"{project.total_budget:.2f}")
                self.project_table.setItem(row_position, 6, item_budget)

                item_director = QTableWidgetItem(str(project.director))
                self.project_table.setItem(row_position, 7, item_director)
                # 获取总预算执行率
                total_budget = session.query(Budget).filter(
                    Budget.project_id == project.id,
                    Budget.year.is_(None)
                ).first()
                
                # 移除添加项目管理和经费管理按钮的代码
                #     ... (代码已移除) ...
                #     ... (代码已移除) ...
                #
                # # 经费管理按钮
                # ... (代码已移除) ...
            
            session.close()
            

            # 禁止直接编辑
            self.project_table.setEditTriggers(TableWidget.NoEditTriggers)

            # 设置表格对齐方式
            for row_position in range(self.project_table.rowCount()):
                for col in range(self.project_table.columnCount()):
                    item = self.project_table.item(row_position, col)
                    if item:
                        # 第0、2、3、4、5列设置为居中对齐
                        if col in [0, 1, 2, 3, 4, 5, 7]:
                            item.setTextAlignment(Qt.AlignCenter)
                        # 第6列(总经费)设置为右对齐
                        elif col in [6]:
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
            director = dialog.project_director.text().strip()
            
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
                    total_budget=float(total_budget) if total_budget else 0.0,
                    director=director
                )
                session.add(project)
                session.flush()  # 获取项目ID
                
                self.project_id = project.id
                
                # 记录添加项目的活动
                actionlog = Actionlog(
                    project_id=project.id,
                    type="项目",
                    action="新增",
                    description=f"添加项目：{name} - {financial_code}",
                    operator="系统用户",
                    new_data=f"名称: {name}, 财务编号: {financial_code}, 项目编号: {project_code}, 类型: {project_type}, 开始日期: {start_date}, 结束日期: {end_date}, 总经费: {total_budget}, 负责人: {director}"
                )
                session.add(actionlog)
                
                # 提交事务
                session.commit()
                
                # 刷新项目列表
                self.refresh_project_table()
                self.project_list_updated.emit() # 发射信号
                
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
                dialog.project_director.setText(project.director if project.director else "") # 加载负责人信息
                
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
                    project.director = dialog.project_director.text().strip() # 保存负责人信息
                    
                    # 记录编辑项目的活动
                    old_data_str = f"名称: {old_name}, 财务编号: {old_financial_code}, 项目编号: {project.project_code}, 类型: {project.project_type}, 开始日期: {project.start_date}, 结束日期: {project.end_date}, 总经费: {project.total_budget}, 负责人: {project.director}"
                    new_data_str = f"名称: {project.name}, 财务编号: {project.financial_code}, 项目编号: {project.project_code}, 类型: {project.project_type}, 开始日期: {project.start_date}, 结束日期: {project.end_date}, 总经费: {project.total_budget}, 负责人: {project.director}"

                    actionlog = Actionlog(
                        project_id=project.id,
                        type="项目",
                        action="编辑",
                        description=f"编辑项目：{project.name} - {project.financial_code}", # 使用新名称和编号
                        operator="系统用户",
                        old_data=old_data_str,
                        new_data=new_data_str
                    )
                    session.add(actionlog)
                    
                    session.commit()
                    self.refresh_project_table()
                    self.project_list_updated.emit() # 发射信号
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
        
        confirm_dialog = Dialog(
            '确认删除',
            '确定要删除该项目吗？此操作不可恢复！',
            self
        )
        
        if confirm_dialog.exec():
            Session = sessionmaker(bind=self.engine)
            session = Session()
            project_doc_dir = None
            project_voucher_dir = None
            voucher_files_to_delete = []
            project_name_for_log = "未知项目"
            project_code_for_log = "未知编号"

            try:
                # --- 1. 获取项目信息和待删除文件路径 ---
                project = session.query(Project).filter(Project.id == project_id).first()
                if not project:
                    UIUtils.show_warning(title='警告', content='未找到要删除的项目！', parent=self)
                    return

                project_name_for_log = project.name
                project_code_for_log = project.financial_code

                current_dir = os.path.dirname(os.path.abspath(__file__))
                root_dir = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))

                project_doc_dir = os.path.join(root_dir, 'documents', str(project_id))
                project_voucher_dir = os.path.join(root_dir, 'vouchers', str(project_id)) # 项目专属凭证目录（如果存在）

                # 获取关联的支出记录中的凭证文件路径 (在删除项目前获取)
                expenses_to_delete = session.query(Expense).join(Budget).filter(Budget.project_id == project_id).all()
                for expense in expenses_to_delete:
                    if expense.voucher_path and os.path.isabs(expense.voucher_path) and os.path.exists(expense.voucher_path):
                        voucher_files_to_delete.append(expense.voucher_path)
                    elif expense.voucher_path:
                        potential_path = os.path.join(root_dir, expense.voucher_path) # 示例：假设相对根目录
                        if os.path.exists(potential_path):
                             voucher_files_to_delete.append(potential_path)
                        else:
                             print(f"凭证文件路径记录存在但文件未找到: {expense.voucher_path} (尝试路径: {potential_path})")


                # --- 2. 数据库删除操作 ---
                # 记录删除项目的活动
                actionlog = Actionlog(
                    project_id=project.id, # 使用 project.id 保证关联
                    type="项目",
                    action="删除",
                    description=f"删除项目及其所有关联数据：{project_name_for_log} - {project_code_for_log}",
                    operator="系统用户"
                )
                session.add(actionlog)

                session.query(GanttTask).filter(GanttTask.project_id == project_id).delete(synchronize_session='fetch')
                session.query(GanttDependency).filter(GanttDependency.project_id == project_id).delete(synchronize_session='fetch')
                # 如果需要删除项目相关的 *其他* 活动记录，需要更复杂的查询逻辑，这里暂时保留刚添加的删除记录


                session.delete(project)
                session.commit() # 提交数据库事务

                # --- 3. 文件系统清理 (数据库提交成功后执行) ---
                try:
                    # 删除凭证文件
                    deleted_files_count = 0
                    for file_path in voucher_files_to_delete:
                        try:
                            os.remove(file_path)
                            deleted_files_count += 1
                        except OSError as e:
                            print(f"删除凭证文件失败 {file_path}: {e}")
                    if deleted_files_count > 0:
                        print(f"共删除了 {deleted_files_count} 个凭证文件。")


                    # 删除项目文档目录
                    if project_doc_dir and os.path.isdir(project_doc_dir):
                        try:
                            shutil.rmtree(project_doc_dir)
                            print(f"已删除文档目录: {project_doc_dir}")
                        except OSError as e:
                            print(f"删除文档目录失败 {project_doc_dir}: {e}")
                    elif project_doc_dir:
                         print(f"文档目录不存在，无需删除: {project_doc_dir}")


                    # 删除项目凭证目录 (如果存在且为空)
                    if project_voucher_dir and os.path.isdir(project_voucher_dir):
                        try:
                            if not os.listdir(project_voucher_dir):
                                os.rmdir(project_voucher_dir)
                                print(f"已删除空的凭证目录: {project_voucher_dir}")
                            else:
                                print(f"凭证目录非空，未删除: {project_voucher_dir}")
                        except OSError as e:
                            print(f"删除凭证目录失败 {project_voucher_dir}: {e}")
                    elif project_voucher_dir:
                        print(f"项目凭证目录不存在，无需删除: {project_voucher_dir}")


                except Exception as fs_e:
                    # 文件系统清理失败不应回滚数据库，但需要记录错误
                    print(f"文件系统清理过程中发生错误: {fs_e}")
                    UIUtils.show_error(
                        title='文件清理错误',
                        content=f'数据库记录已删除，但清理相关文件时出错: {fs_e}',
                        parent=self
                    )
                    # 即使文件清理失败，也要刷新表格并显示成功信息（因为数据库已成功）
                    self.refresh_project_table()
                    self.project_list_updated.emit() # 发射信号 (部分成功)
                    UIUtils.show_success(
                        title='部分成功',
                        content='项目数据库记录已删除，但文件清理时遇到问题。详情请查看日志。',
                        parent=self
                    )
                    return # 提前返回，避免显示完全成功的消息

                # --- 4. 完成 ---
                self.refresh_project_table()
                self.project_list_updated.emit() # 发射信号 (完全成功)
                UIUtils.show_success(
                    title='成功',
                    content=f'项目 "{project_name_for_log}" 及其所有关联数据和文件已成功删除。',
                    parent=self
                )

            except Exception as e:
                session.rollback() # 回滚数据库事务
                print(f"删除项目时发生数据库错误: {e}") # 打印详细错误到控制台
                # 提取更具体的错误信息给用户
                error_message = str(e)
                if isinstance(e, IntegrityError) and "FOREIGN KEY constraint failed" in error_message:
                     error_content = f'删除项目失败：存在未能自动删除的关联数据，请检查数据库约束设置。错误详情: {error_message}'
                elif isinstance(e, IntegrityError):
                     error_content = f'删除项目失败：数据库完整性约束冲突。错误详情: {error_message}'
                else:
                     error_content = f'删除项目失败：发生未知数据库错误。错误详情: {error_message}'

                UIUtils.show_error(
                    title='数据库错误',
                    content=error_content,
                    parent=self
                )
            finally:
                session.close()
        
    
    

    

            
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
                
                budget_id_map = {}
                
                # 导入支出数据
                for expense_data in import_data['expenses']:
                    try:
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