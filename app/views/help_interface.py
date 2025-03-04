from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt
from qfluentwidgets import (SettingCardGroup, ExpandGroupSettingCard, ScrollArea,
                          InfoBar, FluentIcon, CardWidget, TitleLabel, BodyLabel)

class HelpInterface(ScrollArea):
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        self.setObjectName("helpInterface")
        self.scrollWidget = QWidget()
        self.expandLayout = QVBoxLayout(self.scrollWidget)
        
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
        
        # 将帮助组添加到布局
        self.expandLayout.addWidget(self.helpGroup)
        
        # 设置滚动区域
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)