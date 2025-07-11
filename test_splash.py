#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动动画测试文件
用于测试海沛自动化启动动画效果
"""

import sys
from PyQt5.QtWidgets import QApplication
from splash_screen import AnimatedSplashScreen
import time

def test_splash():
    """测试启动动画"""
    app = QApplication(sys.argv)
    
    # 设置全局样式
    app.setStyle("Fusion")
    
    # 创建并显示启动动画
    splash = AnimatedSplashScreen()
    splash.show()
    splash.start_animation()
    
    # 处理事件循环，显示动画（2秒）
    start_time = time.time()
    while splash.isVisible() and time.time() - start_time < 3:  # 最多等待3秒
        app.processEvents()
        time.sleep(0.01)
        # 检查动画是否完成
        if splash.is_animation_completed():
            time.sleep(0.5)  # 测试时多显示0.5秒
            break
    
    splash.close()
    print("启动动画测试完成！")
    
if __name__ == "__main__":
    test_splash()