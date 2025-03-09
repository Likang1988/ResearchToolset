from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from qfluentwidgets import (SettingCardGroup, ExpandGroupSettingCard, ScrollArea,
                          InfoBar, FluentIcon, CardWidget, TitleLabel, BodyLabel)
import os

class HelpInterface(ScrollArea):
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        self.setObjectName("helpInterface")
        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        self.expandLayout.setContentsMargins(16, 16, 16, 16)  # 设置边距
        self.expandLayout.setSpacing(16)  # 设置内容组之间的间距
        
        # 创建软件简介内容组
        self.readmeGroup = ExpandGroupSettingCard(FluentIcon.DOCUMENT, "软件简介", "", self.scrollWidget)
        
        # 创建软件简介卡片
        readme_card = CardWidget(self.readmeGroup)
        readme_layout = QVBoxLayout(readme_card)
        
        # 添加图标
        icon_layout = QHBoxLayout()
        icon_layout.setAlignment(Qt.AlignCenter)
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icon.ico')
        icon_pixmap = QPixmap(icon_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(icon_pixmap)
        icon_layout.addWidget(icon_label)
        readme_layout.addLayout(icon_layout)
        
        # 添加标题
        title = TitleLabel("科研工具集 - ResearchToolset", readme_card)
        title.setAlignment(Qt.AlignCenter)
        readme_layout.addWidget(title)
        
        # 添加副标题
        subtitle = BodyLabel("基于 PySide6 和 QFluentWidgets 的跨平台科研经费管理软件", readme_card)
        subtitle.setAlignment(Qt.AlignCenter)
        readme_layout.addWidget(subtitle)
        
        # 添加截图
        screenshot_label = QLabel()
        screenshot_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'screenshots', '经费追踪-预算管理.png')
        screenshot_pixmap = QPixmap(screenshot_path)
        screenshot_label.setPixmap(screenshot_pixmap.scaled(800, 450, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        screenshot_label.setAlignment(Qt.AlignCenter)
        readme_layout.addWidget(screenshot_label)

        # 添加项目简介
        intro_text = BodyLabel(
            "目前软件的功能主要为科研经费管理，旨在帮助科研人员高效管理和追踪项目资金使用情况。\n\n"
            "后续将不断丰富完善和优化软件功能，慢慢形成一个真正能有效服务科研工作者的工具集。\n\n"
            "项目源于本人日常科研工作需要，利用VSCode+Cline+DeepSeek进行开发，项目代码还比较混乱，可能有很多重复代码和未知bug，未必适用于所有科研工作者，请谨慎使用。",
            
            readme_card
        )
        intro_text.setWordWrap(True)
        readme_layout.addWidget(intro_text)
        
        # 添加主要功能
        features_title = TitleLabel("主要功能", readme_card)
        readme_layout.addWidget(features_title)
        
        features_text = BodyLabel(
            "- 经费追踪\n"
            "  用于项目实施阶段的经费执行情况追踪的工具\n\n"
            "  - 项目管理\n"
            "    - 添加、编辑、删除项目信息\n"
            "    - 支持多种项目类别（国家自然科学基金、国家重点研发计划等）\n"
            "    - 项目基本信息维护（项目编号、起止时间、总经费等）\n\n"
            "  - 预算管理\n"
            "    - 总预算管理\n"
            "    - 添加、编辑、删除年度预算信息\n"
            "    - 直观显示总预算及年度预算的预算额、支出额、结余额、执行率\n"
            "    - 总预算及年度预算执行情况统计，按类别、时间分布统计饼图\n\n"
            "  - 支出管理\n"
            "    - 添加、编辑、删除支出记录\n"
            "    - 支持批量导入支出信息\n"
            "    - 支持导入支出凭证\n"
            "    - 支出记录排序、筛选、导出\n\n"
            "- 预算编制\n"
            "  - 用于课题申请阶段的预算编制工具，功能开发中\n\n"
            "- 小工具\n"
            "  - 间接经费计算器\n\n"
            "- 更多功能待添加……",
            readme_card
        )
        features_text.setWordWrap(True)
        readme_layout.addWidget(features_text)
        
        # 添加计划
        plan_title = TitleLabel("计划", readme_card)
        readme_layout.addWidget(plan_title)
        
        plan_text = BodyLabel(
            "- ✅ 基于qfluentwidgets重构UI（持续优化中）\n"
            "- ✅ 支出信息批量导入\n"
            "- ✅ 支出信息列表排序、筛选、导出\n"
            "- ✅ 支出凭证插入、导出\n"
            "- ✅ 预算管理列表执行率进度条\n"
            "- ✅ 预算管理界面统计图表\n"
            "  - ✅ 按列表支出分布\n"
            "  - ✅ 按时间支出分布\n"
            "- ❌ 预算编制功能模块 (开发中...)\n"
            "- ❌ 预算编制数据导出 (明细、汇总、分年度...)\n"
            "- ❌ 丰富主页功能 (项目执行率、统计图卡片...)",
            readme_card
        )
        plan_text.setWordWrap(True)
        readme_layout.addWidget(plan_text)
        
        # 添加系统要求
        sys_req_title = TitleLabel("系统要求", readme_card)
        readme_layout.addWidget(sys_req_title)
        
        sys_req_text = BodyLabel(
            "- Python 3.6+\n"
            "- Windows 操作系统",
            readme_card
        )
        sys_req_text.setWordWrap(True)
        readme_layout.addWidget(sys_req_text)
        
        # 添加依赖项
        deps_title = TitleLabel("依赖项", readme_card)
        readme_layout.addWidget(deps_title)
        
        deps_text = BodyLabel(
            "- PySide6 >= 6.5.0\n"
            "- PySide6-Fluent-Widgets >= 1.7.4\n"
            "- pandas >= 2.0.0\n"
            "- matplotlib >= 3.7.0\n"
            "- openpyxl >= 3.1.0\n"
            "- python-dateutil >= 2.8.2\n"
            "- SQLAlchemy >= 2.0.0",
            readme_card
        )
        deps_text.setWordWrap(True)
        readme_layout.addWidget(deps_text)
        
        # 添加注意事项
        notes_title = TitleLabel("注意事项", readme_card)
        readme_layout.addWidget(notes_title)
        
        notes_text = BodyLabel(
            "- 建议定期备份数据库文件\n"
            "- 批量导入数据时请使用系统提供的模板",
            readme_card
        )
        notes_text.setWordWrap(True)
        readme_layout.addWidget(notes_text)
        
        # 添加许可证
        license_title = TitleLabel("许可证", readme_card)
        readme_layout.addWidget(license_title)
        
        license_text = BodyLabel(
            "ResearchToolset使用 GPLv3 许可证进行授权。\n\n"
            "版权所有 © 2025 by Likang1988.",
            readme_card
        )
        license_text.setWordWrap(True)
        readme_layout.addWidget(license_text)
        
        self.readmeGroup.addGroupWidget(readme_card)
        

        
        self.readmeGroup.addGroupWidget(readme_card)
        
        # 创建帮助内容组
        self.helpGroup = ExpandGroupSettingCard(FluentIcon.HELP, "使用帮助", "", self.scrollWidget)
        
        # 创建系统介绍卡片
        intro_card = CardWidget(self.helpGroup)
        intro_layout = QVBoxLayout(intro_card)
        
        intro_title = TitleLabel("系统介绍", intro_card)
        intro_content = BodyLabel(
            "科研项目经费管理系统是一个帮助科研人员高效管理项目经费的工具。\n"
            "系统提供项目管理、经费追踪等功能，让您轻松掌控项目资金使用情况。",
            intro_card
        )
        intro_content.setWordWrap(True)
        
        intro_layout.addWidget(intro_title)
        intro_layout.addWidget(intro_content)
        self.helpGroup.addGroupWidget(intro_card)
        
        # 创建功能指南卡片
        guide_card = CardWidget(self.helpGroup)
        guide_layout = QVBoxLayout(guide_card)
        
        guide_title = TitleLabel("功能指南", guide_card)
        guide_content = BodyLabel(
            "1. 项目管理：\n"
            "   - 添加新项目：点击'添加项目'按钮，填写项目信息\n"
            "   - 编辑项目：选择项目后点击'编辑项目'按钮\n"
            "   - 删除项目：选择项目后点击'删除项目'按钮\n\n"
            "2. 经费管理：\n"
            "   - 点击项目列表中的'经费管理'按钮\n"
            "   - 可以添加、编辑、删除经费记录\n"
            "   - 支持批量导入支出记录",
            guide_card
        )
        guide_content.setWordWrap(True)
        
        guide_layout.addWidget(guide_title)
        guide_layout.addWidget(guide_content)
        self.helpGroup.addGroupWidget(guide_card)
        
        # 创建常见问题卡片
        faq_card = CardWidget(self.helpGroup)
        faq_layout = QVBoxLayout(faq_card)
        
        faq_title = TitleLabel("常见问题", faq_card)
        faq_content = BodyLabel(
            "Q: 如何批量导入支出记录？\n"
            "A: 在经费管理页面点击'批量导入'按钮，选择Excel文件即可。\n\n"
            "Q: 如何查看项目支出明细？\n"
            "A: 在经费管理页面可以查看所有支出记录。\n\n"
            "Q: 如何导出经费报表？\n"
            "A: 目前正在开发导出功能，敬请期待。",
            faq_card
        )
        faq_content.setWordWrap(True)
        
        faq_layout.addWidget(faq_title)
        faq_layout.addWidget(faq_content)
        self.helpGroup.addGroupWidget(faq_card)
        
        # 将内容组添加到布局
        self.expandLayout.addWidget(self.readmeGroup)
        self.expandLayout.addWidget(self.helpGroup)
        
        # 设置滚动区域
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)