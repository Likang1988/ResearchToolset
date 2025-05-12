from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFileDialog)
from PySide6.QtCore import Qt
import pandas as pd
from datetime import datetime
from qfluentwidgets import (PushButton, BodyLabel, FluentIcon)
from ..models.database import BudgetCategory
from ..utils.ui_utils import UIUtils

class BatchImportDialog(QDialog):
    def __init__(self, project_id, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.setWindowTitle("批量导入支出信息")
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 文件选择
        file_layout = QHBoxLayout()
        file_layout.addWidget(BodyLabel("选择文件:"))
        self.file_path = BodyLabel("未选择文件")
        self.file_path.setStyleSheet("color: #666; font-style: italic;")
        file_layout.addWidget(self.file_path)
        
        select_btn = PushButton("选择", self, FluentIcon.FOLDER)
        select_btn.clicked.connect(self.select_file)
        file_layout.addWidget(select_btn)
        layout.addLayout(file_layout)
        
        # 添加说明标签
        instruction_label = BodyLabel(
            "注意事项：\n"
            "1. 费用类别、开支内容和报账金额为必填项\n"
            "2. 费用类别必须是系统预设的类别之一\n"
            "3. 报账金额必须大于0\n"
            "4. 报账日期格式为YYYY-MM-DD，可为空"
        )
        instruction_label.setStyleSheet("color: #666; margin: 10px 0;")
        layout.addWidget(instruction_label)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 添加下载模板按钮
        template_btn = PushButton("下载模板", self, FluentIcon.DOWNLOAD)
        template_btn.clicked.connect(self.download_template)
        
        import_btn = PushButton("导入", self, FluentIcon.EMBED)
        cancel_btn = PushButton("取消", self, FluentIcon.CLOSE)
        
        button_layout.addWidget(template_btn)
        button_layout.addWidget(import_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        # 连接信号
        import_btn.clicked.connect(self.import_data)
        cancel_btn.clicked.connect(self.reject)
        
    def select_file(self):
        """选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", "Excel文件 (*.xlsx *.xls);;CSV文件 (*.csv)")
        if file_path:
            self.file_path.setText(file_path)
            
    def download_template(self):
        """下载导入模板"""
        try:
            save_path, _ = QFileDialog.getSaveFileName(
                self, 
                "保存模板文件",
                "支出导入模板.xlsx",
                "Excel文件 (*.xlsx)"
            )
            
            if save_path:
                # 创建示例数据
                example_data = {
                    '费用类别': ['设备费', '材料费'],
                    '开支内容': ['设备A采购', '材料B采购'],
                    '规格型号': ['型号X', '型号Y'],
                    '供应商': ['供应商A', '供应商B'],
                    '报账金额': [10000, 5000],
                    '报账日期': [datetime.now().strftime('%Y-%m-%d'), ''],
                    '备注': ['示例数据1', '示例数据2']
                }
                df = pd.DataFrame(example_data)
                
                with pd.ExcelWriter(save_path, engine='openpyxl', datetime_format='YYYY-MM-DD') as writer:
                    # 写入数据表
                    df.to_excel(writer, sheet_name='支出信息', index=False)
                    
                    # 创建数据有效性验证表
                    validation_data = pd.DataFrame({
                        '费用类别': [category.value for category in BudgetCategory],
                        '说明': [''] * len(BudgetCategory)
                    })
                    validation_data.to_excel(writer, sheet_name='费用类别', index=False)
                    
                    # 创建使用说明表
                    instructions = [
                        "使用说明：",
                        "1. 费用类别、开支内容、报账金额为必填项",
                        "2. 费用类别必须是以下之一：",
                        "   " + "、".join([category.value for category in BudgetCategory]),
                        "3. 报账金额必须大于0",
                        "4. 报账日期支持常见格式（如：YYYY-MM-DD、YYYY/MM/DD、DD/MM/YYYY等），可为空，默认为当前日期",
                        "5. 规格型号、供应商、备注为选填项",
                        "6. 请勿修改表头名称",
                        "7. 请勿删除或修改本说明"
                    ]
                    pd.DataFrame(instructions).to_excel(
                        writer, 
                        sheet_name='使用说明',
                        index=False,
                        header=False
                    )
                    
                UIUtils.show_success(
                    title='成功',
                    content=f'模板已保存至: {save_path}',
                    parent=self
                )
                
        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f'保存模板失败: {str(e)}',
                parent=self
            )

    def import_data(self):
        """导入数据"""
        if not self.file_path.text() or self.file_path.text() == "未选择文件":
            UIUtils.show_warning(
                title='警告',
                content='请先选择文件！',
                parent=self
            )
            return
            
        try:
            # 读取文件
            file_path = self.file_path.text()
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path, sheet_name='支出信息')
                
            # 数据验证
            required_columns = ['费用类别', '开支内容', '报账金额']
            optional_columns = ['规格型号', '供应商', '报账日期', '备注'] 
            
            # 检查必要列
            missing_required = [col for col in required_columns if col not in df.columns]
            if missing_required:
                UIUtils.show_warning(
                    title='警告',
                    content=f'文件缺少必要列！\n缺失列：{', '.join(missing_required)}\n必须包含：{', '.join(required_columns)}',
                    parent=self
                )
                return

            # 检查必填字段是否为空
            empty_required = []
            for col in required_columns:
                if df[col].isna().any():
                    empty_required.append(col)
            
            if empty_required:
                UIUtils.show_warning(
                    title='警告',
                    content=f'以下必填列存在空值：{', '.join(empty_required)}',
                    parent=self
                )
                return

            # 检查费用类别是否有效
            valid_categories = [category.value for category in BudgetCategory]
            invalid_categories = df[~df['费用类别'].isin(valid_categories)]['费用类别'].unique()
            
            if len(invalid_categories) > 0:
                UIUtils.show_warning(
                    title='警告',
                    content=f'存在无效的费用类别：{', '.join(invalid_categories)}\n有效的费用类别包括：{', '.join(valid_categories)}',
                    parent=self
                )
                return

            # 检查金额格式
            try:
                df['报账金额'] = pd.to_numeric(df['报账金额'])
            except Exception:
                UIUtils.show_warning(
                    title='警告',
                    content='报账金额列包含无效的数字格式',
                    parent=self
                )
                return

            if (df['报账金额'] <= 0).any():
                UIUtils.show_warning(
                    title='警告',
                    content='报账金额必须大于0',
                    parent=self
                )
                return

            # 检查日期格式
            if '报账日期' in df.columns and not df['报账日期'].isna().all():
                try:
                    df['报账日期'] = pd.to_datetime(df['报账日期'], format=None)
                    df['报账日期'] = df['报账日期'].dt.strftime('%Y-%m-%d')
                    df['报账日期'] = pd.to_datetime(df['报账日期'])
                except Exception as e:
                    UIUtils.show_warning(
                        title='警告',
                        content='无法识别报账日期格式，请使用常见的日期格式，如：YYYY-MM-DD、YYYY/MM/DD、DD/MM/YYYY等',
                        parent=self
                    )
                    return
            else:
                df['报账日期'] = pd.Timestamp.now()

            # 添加缺失的可选列
            for col in optional_columns:
                if col not in df.columns:
                    df[col] = None

            # 将数据转换为字典列表
            expenses = []
            for _, row in df.iterrows():
                expense = {
                    '类别': row['费用类别'],
                    '开支内容': row['开支内容'],
                    '报账金额': float(row['报账金额']),
                    '规格型号': row['规格型号'] if pd.notna(row['规格型号']) else None,
                    '供应商': row['供应商'] if pd.notna(row['供应商']) else None,
                    '报账日期': row['报账日期'].to_pydatetime() if pd.notna(row['报账日期']) else datetime.now(),
                    '备注': row['备注'] if pd.notna(row['备注']) else None
                }
                expenses.append(expense)
                
            # 发送信号或调用主窗口的添加方法
            if self.parent():
                self.parent().add_expenses(expenses)
                
            UIUtils.show_success(
                title='成功',
                content=f'成功导入 {len(expenses)} 条记录！',
                parent=self
            )
            self.accept()
            
        except pd.errors.EmptyDataError:
            UIUtils.show_error(
                title='错误',
                content='导入的文件为空！',
                parent=self
            )
        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f'导入失败: {str(e)}',
                parent=self
            )