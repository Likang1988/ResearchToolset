from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from enum import Enum
from .database import Base

class BudgetEditCategory(Enum):
    """预算编制类别"""
    DIRECT = "直接费"
    INDIRECT = "间接费"

class BudgetEditSubCategory(Enum):
    """预算编制子类别"""
    # 直接费子项
    MATERIAL = "材料费"
    EXTERNAL = "外部协作费"
    FUEL = "燃料动力费"
    TRAVEL = "会议/差旅/国际合作与交流费"
    PUBLICATION = "出版/文献/信息传播/知识产权事务费"
    LABOR = "劳务费"
    EXPERT = "专家咨询费"
    OTHER = "其他支出"
    # 间接费子项
    MANAGEMENT = "管理费用"
    PERFORMANCE = "科研绩效津贴"

class BudgetEditProject(Base):
    """预算编制项目"""
    __tablename__ = 'budget_edit_projects'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    items = relationship("BudgetEditItem", back_populates="project", cascade="all, delete-orphan")

class BudgetEditItem(Base):
    """预算编制条目"""
    __tablename__ = 'budget_edit_items'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('budget_edit_projects.id'), nullable=False)
    parent_id = Column(Integer, ForeignKey('budget_edit_items.id'))
    category = Column(SQLEnum(BudgetEditCategory))
    subcategory = Column(SQLEnum(BudgetEditSubCategory))
    name = Column(String(200))  # 预算内容
    specification = Column(String(100))  # 规格型号
    unit_price = Column(Float, default=0.0)  # 单价
    quantity = Column(Integer, default=0)  # 数量
    amount = Column(Float, default=0.0)  # 经费数额
    remarks = Column(String(200))  # 备注
    
    project = relationship("BudgetEditProject", back_populates="items")
    parent = relationship("BudgetEditItem", remote_side=[id], backref="children")