import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon  # 将QFont导入提前
from app.views.main_window import MainWindow
from app.models.database import init_db, migrate_db, Base
import logging
import matplotlib as mpl

def main():
    # 添加平台检测
    import platform
    is_mac = platform.system() == 'Darwin'
    is_windows = platform.system() == 'Windows'
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # 设置字体
    font = QFont('Microsoft YaHei')
    if is_mac:
        font.setPixelSize(12)  # macOS下使用稍大的字号
    elif is_windows:
        font.setPixelSize(12)  # Windows下使用正常字号
    app.setFont(font)
    
    # 设置日志
    logging.basicConfig(level=logging.DEBUG)
    
    # 设置matplotlib中文字体
    mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
    mpl.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
    
    # 删除重复的QApplication创建和QFont导入
    # 设置应用程序图标
    icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'app', 'assets', 'icon.ico'))
    print(f"图标路径: {icon_path}")  # 打印路径以便调试
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        print(f"图标文件不存在: {icon_path}")
    
    # 获取数据库路径
    if getattr(sys, 'frozen', False):
        # 如果是打包后的exe
        base_dir = os.path.dirname(sys.executable)
    else:
        # 如果是源码运行
        base_dir = os.path.dirname(__file__)
    
    db_path = os.path.join(base_dir, 'database', 'database.db')
    
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

    # 重新启用云母/亚克力特效 (解决 QWebEngineView 导致特效失效的问题)
    # 确保在 window.show() 之后调用
    window.setMicaEffectEnabled(False)

    # Start the event loop
    sys.exit(app.exec())

if __name__ == '__main__':
    main()