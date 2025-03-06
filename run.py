import sys
import os
from PySide6.QtWidgets import QApplication
from app.views.main_window import MainWindow
from app.models.database import init_db, migrate_db, Base
import logging
import matplotlib as mpl

def main():
    # 设置日志
    logging.basicConfig(level=logging.DEBUG)
    
    # 设置matplotlib中文字体
    mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
    mpl.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # 设置应用程序图标
    icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'app', 'assets', 'icon.ico'))
    print(f"图标路径: {icon_path}")  # 打印路径以便调试
    if os.path.exists(icon_path):
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(icon_path))
    else:
        print(f"图标文件不存在: {icon_path}")
    
    # 获取数据库路径
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'database.db')
    
    # 确保数据库目录存在
    db_dir = os.path.dirname(db_path)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    # 初始化数据库
    engine = init_db(db_path)
    
    # 检查数据库是否存在，不存在则初始化
    if not os.path.exists(db_path):
        logging.info("初始化数据库")
        Base.metadata.create_all(engine)
    else:
        # 如果数据库已存在，执行迁移
        logging.info("执行数据库迁移")
        migrate_db(engine)
    
    # 创建主窗口
    window = MainWindow(engine)
    window.show()
    
    # Start the event loop
    sys.exit(app.exec())

if __name__ == '__main__':
    main()