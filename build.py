import os
import subprocess
import sys

def run_nuitka_build():
    # 获取项目根目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    main_file = os.path.join(project_root, 'run.py')
    icon_file = os.path.join(project_root, 'app', 'assets', 'icon.ico')
    
    # 设置输出目录为项目根目录下的Compilation文件夹
    output_dir = os.path.join(project_root, 'Compilation')
    if not os.path.exists(output_dir):  # 如果目录不存在，则创建
        os.makedirs(output_dir)
    
    # 构建Nuitka命令
    cmd = [
        sys.executable, '-m', 'nuitka',
        '--standalone',  # 创建独立可执行文件
        '--enable-plugin=pyside6',  # 启用PySide6插件
    ]
    
    # 根据操作系统添加特定选项
    if sys.platform == 'win32':
        cmd.extend(['--windows-disable-console', f'--windows-icon-from-ico={icon_file}'])
    elif sys.platform == 'darwin':
        cmd.append('--macos-create-app-bundle')
    # Linux不需要特殊选项
    
    # 添加其他必要的编译选项
    cmd.extend([
        '--disable-ccache',  # 禁用ccache以避免资源文件问题
        '--disable-console',  # 禁用控制台以减少干扰
        '--include-package=dateutil',  # 包含python-dateutil包
        '--include-package=sqlalchemy',  # 包含SQLAlchemy包
        '--include-package=openpyxl',  # 包含openpyxl包
        '--include-package=matplotlib',  # 包含matplotlib包
        '--include-package=qfluentwidgets',  # 包含qfluentwidgets包
        '--include-package=pandas',  # 包含pandas包
        '--include-package=numpy',  # 包含numpy包
        '--include-package=logging',  # 包含logging包
        '--include-package-data=matplotlib',  # 包含matplotlib数据文件
        f'--include-data-dir=%s=app/assets' % os.path.join(project_root, 'app', 'assets'),  # 包含assets目录
        f'--output-dir=%s' % output_dir,  # 输出目录
        '--output-filename=ResearchToolset',  # 指定输出文件名
        '--assume-yes-for-downloads',  # 自动下载依赖
        '--follow-imports',  # 自动包含所有导入的模块
        '--jobs=4',  # 使用4个CPU核心编译
        '--show-progress',  # 显示编译进度
        '--show-memory',  # 显示内存使用情况
        '--nofollow-import-to=tkinter',  # 排除tkinter包
        '--nofollow-import-to=tk',  # 排除tk包
        '--nofollow-import-to=tcl',  # 排除tcl包
        '--remove-output',  # 在构建前清理输出目录
        '--include-qt-plugins=sensible,styles',  # 包含必要的Qt插件
        '--enable-plugin=numpy',  # 启用numpy插件
        '--enable-plugin=matplotlib',  # 启用matplotlib插件
        '--prefer-source-code',  # 优先使用源代码而不是字节码
        main_file  # 主文件
    ])
    
    # 执行编译命令
    subprocess.run(cmd, check=True)

if __name__ == '__main__':
    run_nuitka_build()
