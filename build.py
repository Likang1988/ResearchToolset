import os
import subprocess
import sys

def run_nuitka_build():
    # 获取项目根目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    main_file = os.path.join(project_root, 'run.py')
    icon_file = os.path.join(project_root, 'app', 'assets', 'icon.ico')
    
    # 构建Nuitka命令
    cmd = [
        sys.executable, '-m', 'nuitka',
        '--standalone',  # 创建独立可执行文件
        '--windows-disable-console',  # 禁用控制台
        '--enable-plugin=pyside6',  # 启用PySide6插件
        f'--windows-icon-from-ico={icon_file}',  # 设置应用图标
        '--include-package=dateutil',  # 包含python-dateutil包
        '--include-package=sqlalchemy',  # 包含SQLAlchemy包
        '--include-package=openpyxl',  # 包含openpyxl包
        '--include-package=matplotlib',  # 包含matplotlib包
        '--include-package=qfluentwidgets',  # 包含qfluentwidgets包
        '--include-package-data=matplotlib',  # 包含matplotlib数据文件
        '--include-data-dir=%s=app/assets' % os.path.join(project_root, 'app', 'assets'),  # 包含assets目录
        '--output-dir=%s' % os.path.join(project_root, 'dist'),  # 输出目录
        '--assume-yes-for-downloads',  # 自动下载依赖
        '--jobs=4',  # 使用4个CPU核心编译
        main_file  # 主文件
    ]
    
    # 执行编译命令
    subprocess.run(cmd, check=True)

if __name__ == '__main__':
    run_nuitka_build()
