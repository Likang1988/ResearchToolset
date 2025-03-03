import pandas as pd
import random
from datetime import datetime, timedelta
import sys
import os

# 添加项目根目录到Python路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_dir)

from app.models.database import BudgetCategory
import os

def generate_random_expense_data(num_records=10):
    """生成随机的支出数据"""
    # 示例数据
    equipment_contents = [
        '高性能计算服务器', '实验室工作站', '数据采集设备', '网络存储设备',
        '显微镜设备', '测试仪器', '实验分析仪', '专业软件授权'
    ]
    
    material_contents = [
        '实验耗材', '化学试剂', '标准物质', '实验用品',
        '电子元件', '实验室用品', '分析材料', '测试样品'
    ]
    
    test_contents = [
        '设备性能测试', '样品检测分析', '专业技术测试', '质量检验服务',
        '环境监测服务', '可靠性测试', '性能评估服务', '标准测试服务'
    ]
    
    processing_contents = [
        '数据处理服务', '样品加工服务', '技术咨询服务', '实验外协加工',
        '专业技术服务', '分析测试服务', '工艺优化服务', '设计开发服务'
    ]
    
    travel_contents = [
        '学术会议差旅', '项目调研差旅', '实验考察差旅', '技术交流差旅',
        '项目验收差旅', '学术交流差旅', '实地考察差旅', '合作研讨差旅'
    ]
    
    meeting_contents = [
        '项目研讨会', '学术交流会', '技术研讨会', '项目推进会',
        '成果展示会', '专家咨询会', '项目总结会', '技术交流会'
    ]
    
    international_contents = [
        '国际会议注册', '国际期刊版面费', '国际合作交流', '国际实验室使用费',
        '国际专家咨询', '国际数据库使用', '国际认证费用', '国际专利申请'
    ]
    
    publication_contents = [
        '学术论文版面费', '专著出版费', '专利申请费', '成果鉴定费',
        '论文翻译费', '图文制作费', '资料印刷费', '专业文献购买'
    ]
    
    labor_contents = [
        '研究生劳务费', '临时聘用人员', '项目助理劳务', '技术支持人员',
        '实验协助人员', '数据采集人员', '实验室管理员', '技术顾问'
    ]
    
    indirect_contents = [
        '水电费', '房租费', '管理费用', '办公费用',
        '设备维护费', '网络通讯费', '物业费用', '其他间接费用'
    ]
    
    # 供应商示例
    suppliers = [
        '科技仪器有限公司', '实验器材供应商', '科研材料有限公司', '专业设备制造商',
        '技术服务公司', '实验室用品商', '科研耗材供应商', '分析仪器公司'
    ]
    
    # 规格型号示例
    specifications = [
        'A型标准版', 'B型专业版', 'C型高配版', 'D型定制版',
        'E型普通版', 'F型豪华版', 'G型特殊版', 'H型基础版'
    ]
    
    # 根据费用类别选择对应的内容
    category_content_map = {
        BudgetCategory.EQUIPMENT: equipment_contents,
        BudgetCategory.MATERIAL: material_contents + test_contents + processing_contents,
        BudgetCategory.INDIRECT: indirect_contents,
        BudgetCategory.MISCELLANEOUS: material_contents,  # 其他支出暂时使用材料费的内容
        BudgetCategory.CONFERENCE: travel_contents + meeting_contents,  # 会议差旅费用
        BudgetCategory.PUBLICATION: publication_contents,  # 出版文献费用
        BudgetCategory.FUEL: material_contents,  # 燃动费暂时使用材料费的内容

        BudgetCategory.OUTSOURCING: processing_contents,  # 外协费使用加工服务的内容
        BudgetCategory.CONSULTING: meeting_contents + international_contents,  # 专家咨询费使用会议和国际交流内容
        BudgetCategory.LABOR: labor_contents  # 劳务费使用劳务费内容
    }
    
    # 生成随机数据
    data = []
    start_date = datetime.now() - timedelta(days=365)  # 一年内的日期
    
    for _ in range(num_records):
        # 随机选择费用类别
        category = random.choice(list(BudgetCategory))
        
        # 根据费用类别选择对应的内容
        content = random.choice(category_content_map[category])
        
        # 根据费用类别设置合理的金额范围
        if category == BudgetCategory.EQUIPMENT:
            amount = random.uniform(10000, 500000)  # 设备费：1-50万
        elif category == BudgetCategory.MATERIAL:
            amount = random.uniform(1000, 50000)    # 材料费、测试费、加工费：0.1-5万
        elif category == BudgetCategory.MATERIAL:
            amount = random.uniform(1000, 50000)    # 材料费及其他费用：0.1-5万
        else:  # INDIRECT
            amount = random.uniform(1000, 50000)    # 间接费：0.1-5万
        
        # 生成随机日期（一年内）
        random_days = random.randint(0, 365)
        date = start_date + timedelta(days=random_days)
        
        data.append({
            '费用类别': category.value,
            '开支内容': content,
            '规格型号': random.choice(specifications) if random.random() > 0.3 else '',  # 30%概率为空
            '供应商': random.choice(suppliers) if random.random() > 0.3 else '',        # 30%概率为空
            '报账金额': round(amount, 2),
            '报账日期': date.strftime('%Y-%m-%d'),
            '备注': f'测试数据-{random.randint(1000, 9999)}' if random.random() > 0.5 else ''  # 50%概率有备注
        })
    
    return data

def generate_template(num_records=10, output_dir=None):
    """生成Excel模板文件"""
    if output_dir is None:
        # 默认保存在当前目录
        output_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 生成随机数据
    data = generate_random_expense_data(num_records)
    
    # 创建DataFrame
    df = pd.DataFrame(data)
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'支出导入模板_{timestamp}.xlsx'
    filepath = os.path.join(output_dir, filename)
    
    # 创建ExcelWriter对象
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
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
            "4. 报账日期格式为YYYY-MM-DD，可为空，默认为当前日期",
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
    
    return filepath

if __name__ == '__main__':
    # 生成包含20条随机记录的模板
    template_path = generate_template(20)
    print(f'模板文件已生成：{template_path}')