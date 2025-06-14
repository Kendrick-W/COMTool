#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
串口工具启动脚本
自动检查环境并启动应用程序
"""

import sys
import subprocess
import os

def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 7):
        print("错误：需要Python 3.7或更高版本")
        print(f"当前版本：{sys.version}")
        return False
    print(f"Python版本检查通过：{sys.version.split()[0]}")
    return True

def check_dependencies():
    """检查依赖包"""
    required_packages = ['PyQt5', 'serial']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ {package} 未安装")
    
    return missing_packages

def install_dependencies(missing_packages):
    """安装缺失的依赖包"""
    if not missing_packages:
        return True
    
    print("\n正在安装缺失的依赖包...")
    try:
        # 使用requirements.txt安装
        if os.path.exists('requirements.txt'):
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                                  capture_output=True, text=True)
        else:
            # 手动安装
            packages = ['PyQt5>=5.15.0', 'pyserial>=3.5']
            result = subprocess.run([sys.executable, '-m', 'pip', 'install'] + packages, 
                                  capture_output=True, text=True)
        
        if result.returncode == 0:
            print("依赖包安装成功！")
            return True
        else:
            print(f"依赖包安装失败：{result.stderr}")
            return False
    except Exception as e:
        print(f"安装过程中出现错误：{e}")
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("        串口工具 (COMTool) 启动器")
    print("=" * 50)
    print()
    
    # 检查Python版本
    if not check_python_version():
        input("按任意键退出...")
        return
    
    print()
    print("检查依赖包...")
    missing_packages = check_dependencies()
    
    # 安装缺失的依赖包
    if missing_packages:
        print(f"\n发现缺失的依赖包：{', '.join(missing_packages)}")
        if not install_dependencies(missing_packages):
            print("\n请手动安装依赖包：")
            print("pip install PyQt5 pyserial")
            input("按任意键退出...")
            return
        
        # 重新检查
        print("\n重新检查依赖包...")
        missing_packages = check_dependencies()
        if missing_packages:
            print(f"依赖包安装失败：{', '.join(missing_packages)}")
            input("按任意键退出...")
            return
    
    print("\n所有依赖包检查完成！")
    print("\n正在启动应用程序...")
    print("=" * 50)
    
    try:
        # 启动主程序
        import main
    except Exception as e:
        print(f"\n程序启动失败：{e}")
        print("\n请检查：")
        print("1. main.py文件是否存在")
        print("2. 所有依赖包是否正确安装")
        print("3. Python环境是否正常")
        input("\n按任意键退出...")

if __name__ == '__main__':
    main()