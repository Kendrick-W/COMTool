import sys
import time
import math
import random
from PyQt5.QtWidgets import QApplication, QSplashScreen, QLabel, QVBoxLayout, QWidget, QProgressBar
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QRect, QParallelAnimationGroup, QSequentialAnimationGroup
from PyQt5.QtGui import QPixmap, QPainter, QFont, QColor, QLinearGradient, QBrush, QPen, QFontMetrics, QRadialGradient, QPainterPath

class AnimatedSplashScreen(QSplashScreen):
    def __init__(self):
        # 创建一个透明的pixmap作为背景
        pixmap = QPixmap(600, 400)
        pixmap.fill(Qt.transparent)
        super().__init__(pixmap)
        
        # 设置窗口属性
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.SplashScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 动画属性
        self._opacity = 0.0
        self._logo_scale = 0.5
        self._text_offset = 50
        self._rotation = 0.0
        self._glow_intensity = 0.0
        self._particle_progress = 0.0
        
        # 粒子系统
        self.particles = []
        self.init_particles()
        
        # 设置字体
        self.title_font = QFont("Microsoft YaHei", 24, QFont.Bold)
        self.subtitle_font = QFont("Microsoft YaHei", 14)
        self.company_font = QFont("Microsoft YaHei", 18, QFont.Bold)
        
        # 创建动画
        self.setup_animations()
        
        # 启动定时器用于重绘
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)  # 60 FPS
        
    def init_particles(self):
        """初始化粒子系统"""
        for i in range(30):
            particle = {
                'x': random.randint(0, 600),
                'y': random.randint(0, 400),
                'vx': random.uniform(-1, 1),
                'vy': random.uniform(-1, 1),
                'size': random.uniform(1, 3),
                'alpha': random.uniform(0.3, 0.8),
                'color': random.choice([QColor(255, 102, 0), QColor(100, 149, 237), QColor(255, 255, 255)])
            }
            self.particles.append(particle)
            
    def update_animation(self):
        """更新动画和粒子"""
        # 更新粒子位置
        for particle in self.particles:
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']
            
            # 边界检测
            if particle['x'] < 0 or particle['x'] > 600:
                particle['vx'] *= -1
            if particle['y'] < 0 or particle['y'] > 400:
                particle['vy'] *= -1
                
        self.update()
        
    def setup_animations(self):
        """设置动画效果"""
        # 创建动画组
        self.animation_group = QParallelAnimationGroup()
        
        # 透明度动画
        self.opacity_animation = QPropertyAnimation(self, b"opacity")
        self.opacity_animation.setDuration(1200)
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # Logo缩放动画
        self.scale_animation = QPropertyAnimation(self, b"logo_scale")
        self.scale_animation.setDuration(2000)
        self.scale_animation.setStartValue(0.3)
        self.scale_animation.setEndValue(1.0)
        self.scale_animation.setEasingCurve(QEasingCurve.OutElastic)
        
        # 文字偏移动画
        self.text_animation = QPropertyAnimation(self, b"text_offset")
        self.text_animation.setDuration(1500)
        self.text_animation.setStartValue(80)
        self.text_animation.setEndValue(0)
        self.text_animation.setEasingCurve(QEasingCurve.OutBack)
        
        # 旋转动画
        self.rotation_animation = QPropertyAnimation(self, b"rotation")
        self.rotation_animation.setDuration(3000)
        self.rotation_animation.setStartValue(0.0)
        self.rotation_animation.setEndValue(360.0)
        self.rotation_animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        # 发光效果动画
        self.glow_animation = QPropertyAnimation(self, b"glow_intensity")
        self.glow_animation.setDuration(2000)
        self.glow_animation.setStartValue(0.0)
        self.glow_animation.setEndValue(1.0)
        self.glow_animation.setEasingCurve(QEasingCurve.InOutSine)
        
        # 粒子进度动画
        self.particle_animation = QPropertyAnimation(self, b"particle_progress")
        self.particle_animation.setDuration(2500)
        self.particle_animation.setStartValue(0.0)
        self.particle_animation.setEndValue(1.0)
        self.particle_animation.setEasingCurve(QEasingCurve.OutQuart)
        
        # 添加到动画组
        self.animation_group.addAnimation(self.opacity_animation)
        self.animation_group.addAnimation(self.scale_animation)
        self.animation_group.addAnimation(self.text_animation)
        self.animation_group.addAnimation(self.rotation_animation)
        self.animation_group.addAnimation(self.glow_animation)
        self.animation_group.addAnimation(self.particle_animation)
        
    def start_animation(self):
        """开始动画"""
        self.animation_group.start()
        
        # 3秒后自动完成
        QTimer.singleShot(3000, self.mark_completed)
        
    def mark_completed(self):
        """标记动画完成"""
        self.animation_completed = True
        
    def is_animation_completed(self):
        """检查动画是否完成"""
        return hasattr(self, 'animation_completed') and self.animation_completed
            
    @pyqtProperty(float)
    def opacity(self):
        return self._opacity
        
    @opacity.setter
    def opacity(self, value):
        self._opacity = value
        self.update()
        
    @pyqtProperty(float)
    def logo_scale(self):
        return self._logo_scale
        
    @logo_scale.setter
    def logo_scale(self, value):
        self._logo_scale = value
        self.update()
        
    @pyqtProperty(float)
    def text_offset(self):
        return self._text_offset
        
    @text_offset.setter
    def text_offset(self, value):
        self._text_offset = value
        self.update()
        
    @pyqtProperty(float)
    def rotation(self):
        return self._rotation
        
    @rotation.setter
    def rotation(self, value):
        self._rotation = value
        self.update()
        
    @pyqtProperty(float)
    def glow_intensity(self):
        return self._glow_intensity
        
    @glow_intensity.setter
    def glow_intensity(self, value):
        self._glow_intensity = value
        self.update()
        
    @pyqtProperty(float)
    def particle_progress(self):
        return self._particle_progress
        
    @particle_progress.setter
    def particle_progress(self, value):
        self._particle_progress = value
        self.update()
        
    def paintEvent(self, event):
        """自定义绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # 设置整体透明度
        painter.setOpacity(self._opacity)
        
        # 绘制背景渐变
        self.draw_background(painter)
        
        # 绘制粒子效果
        self.draw_particles(painter)
        
        # 绘制Logo区域
        self.draw_logo(painter)
        
        # 绘制公司信息
        self.draw_company_info(painter)
        
        painter.end()
        
    def draw_background(self, painter):
        """绘制背景渐变"""
        rect = self.rect()
        
        # 创建动态径向渐变
        center_x = rect.width() // 2
        center_y = rect.height() // 2
        
        # 主背景渐变
        gradient = QRadialGradient(center_x, center_y, max(rect.width(), rect.height()) // 2)
        gradient.setColorAt(0, QColor(60, 70, 90, int(200 + 55 * self._glow_intensity)))
        gradient.setColorAt(0.6, QColor(45, 52, 74, 220))
        gradient.setColorAt(1, QColor(25, 30, 45, 255))
        
        painter.fillRect(rect, QBrush(gradient))
        
        # 添加动态光晕效果
        if self._glow_intensity > 0:
            glow_gradient = QRadialGradient(center_x, center_y, 150 * self._glow_intensity)
            glow_gradient.setColorAt(0, QColor(255, 102, 0, int(50 * self._glow_intensity)))
            glow_gradient.setColorAt(1, QColor(255, 102, 0, 0))
            painter.fillRect(rect, QBrush(glow_gradient))
        
        # 添加动态边框
        border_color = QColor(100, 149, 237, int(150 + 105 * self._glow_intensity))
        painter.setPen(QPen(border_color, 3))
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 15, 15)
        
    def draw_particles(self, painter):
        """绘制粒子效果"""
        if self._particle_progress <= 0:
            return
            
        painter.save()
        
        for i, particle in enumerate(self.particles):
            # 根据粒子进度计算透明度
            progress_alpha = min(1.0, self._particle_progress * 2)
            alpha = int(particle['alpha'] * progress_alpha * 255)
            
            if alpha <= 0:
                continue
                
            # 设置粒子颜色和透明度
            color = QColor(particle['color'])
            color.setAlpha(alpha)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            
            # 绘制粒子
            size = particle['size'] * self._particle_progress
            painter.drawEllipse(int(particle['x'] - size/2), int(particle['y'] - size/2), int(size), int(size))
            
            # 添加粒子轨迹效果
            if self._particle_progress > 0.5:
                trail_color = QColor(particle['color'])
                trail_color.setAlpha(alpha // 3)
                painter.setBrush(QBrush(trail_color))
                trail_size = size * 0.3
                painter.drawEllipse(int(particle['x'] - particle['vx'] * 5 - trail_size/2), 
                                  int(particle['y'] - particle['vy'] * 5 - trail_size/2), 
                                  int(trail_size), int(trail_size))
        
        painter.restore()
        
    def draw_logo(self, painter):
        """绘制Logo区域"""
        center_x = self.width() // 2
        center_y = self.height() // 2 - 50
        
        # 计算缩放后的尺寸
        logo_width = int(200 * self._logo_scale)
        logo_height = int(80 * self._logo_scale)
        
        painter.save()
        
        # 应用旋转变换（仅对装饰元素）
        if self._rotation > 0:
            painter.translate(center_x, center_y)
            painter.rotate(self._rotation * 0.1)  # 减缓旋转速度
            painter.translate(-center_x, -center_y)
        
        # 绘制发光效果
        if self._glow_intensity > 0:
            glow_color = QColor(255, 102, 0, int(100 * self._glow_intensity))
            painter.setPen(QPen(glow_color, 3))
            painter.setFont(QFont("Arial", int(36 * self._logo_scale), QFont.Bold))
            
            # 绘制发光的HAPAE文字
            hapae_rect = QRect(center_x - logo_width//2, center_y - logo_height//2, logo_width, logo_height//2)
            painter.drawText(hapae_rect, Qt.AlignCenter, "HAPAE")
        
        painter.restore()
        
        # 绘制主要HAPAE logo文字
        main_color = QColor(255, 102, 0)
        if self._glow_intensity > 0:
            # 添加发光效果
            main_color = QColor(255, int(102 + 153 * self._glow_intensity), int(153 * self._glow_intensity))
        
        painter.setPen(main_color)
        painter.setFont(QFont("Arial", int(36 * self._logo_scale), QFont.Bold))
        
        # 计算HAPAE文字位置
        hapae_rect = QRect(center_x - logo_width//2, center_y - logo_height//2, logo_width, logo_height//2)
        painter.drawText(hapae_rect, Qt.AlignCenter, "HAPAE")
        
        # 绘制中文副标题
        subtitle_color = QColor(255, 255, 255)
        if self._glow_intensity > 0:
            subtitle_color = QColor(255, 255, int(255 + 100 * self._glow_intensity))
        
        painter.setPen(subtitle_color)
        painter.setFont(QFont("Microsoft YaHei", int(14 * self._logo_scale)))
        
        # 计算中文副标题位置
        subtitle_rect = QRect(center_x - logo_width//2, center_y + 10, logo_width, logo_height//2)
        painter.drawText(subtitle_rect, Qt.AlignCenter, "一海沛自动化一")
        
        # 绘制装饰性元素
        self.draw_decorative_elements(painter, center_x, center_y, logo_width)
        
    def draw_decorative_elements(self, painter, center_x, center_y, logo_width):
        """绘制装饰性元素"""
        painter.save()
        
        # 应用旋转变换
        painter.translate(center_x, center_y)
        painter.rotate(self._rotation * 0.5)  # 装饰元素旋转更快
        painter.translate(-center_x, -center_y)
        
        # 动态装饰线条颜色
        line_alpha = int(100 + 155 * self._glow_intensity)
        line_color = QColor(255, 102, 0, line_alpha)
        painter.setPen(QPen(line_color, 3))
        
        # 在HAPAE文字两侧绘制装饰线
        line_y = center_y
        line_length = 20 + 10 * self._glow_intensity
        
        left_line_start = center_x - logo_width//2 - 30
        left_line_end = center_x - logo_width//2 - 10
        right_line_start = center_x + logo_width//2 + 10
        right_line_end = center_x + logo_width//2 + 30
        
        painter.drawLine(left_line_start, line_y, left_line_end, line_y)
        painter.drawLine(right_line_start, line_y, right_line_end, line_y)
        
        # 添加动态圆环装饰
        if self._glow_intensity > 0.3:
            ring_color = QColor(100, 149, 237, int(80 * self._glow_intensity))
            painter.setPen(QPen(ring_color, 2))
            painter.setBrush(Qt.NoBrush)
            
            ring_radius = int(50 + 20 * self._glow_intensity)
            painter.drawEllipse(center_x - ring_radius, center_y - ring_radius, 
                              ring_radius * 2, ring_radius * 2)
        
        # 添加星形装饰
        if self._particle_progress > 0.7:
            self.draw_star_decorations(painter, center_x, center_y)
        
        painter.restore()
        
    def draw_star_decorations(self, painter, center_x, center_y):
        """绘制星形装饰"""
        star_color = QColor(255, 255, 255, int(150 * self._particle_progress))
        painter.setPen(QPen(star_color, 1))
        
        # 绘制多个小星星
        for i in range(8):
            angle = i * 45 + self._rotation
            radius = 80 + 20 * math.sin(self._rotation * math.pi / 180)
            
            star_x = center_x + radius * math.cos(math.radians(angle))
            star_y = center_y + radius * math.sin(math.radians(angle))
            
            # 绘制简单的十字星
            size = 3
            painter.drawLine(int(star_x - size), int(star_y), int(star_x + size), int(star_y))
            painter.drawLine(int(star_x), int(star_y - size), int(star_x), int(star_y + size))
        
    def draw_company_info(self, painter):
        """绘制公司信息"""
        center_x = self.width() // 2
        
        # 英文名称
        painter.setFont(self.subtitle_font)
        painter.setPen(QColor(200, 200, 200))
        english_y = int(self.height() // 2 + 60 + self._text_offset)
        painter.drawText(QRect(0, english_y, self.width(), 20), Qt.AlignCenter, "HaiPei Automation")
        
        # 产品名称
        painter.setFont(self.title_font)
        painter.setPen(QColor(255, 102, 0))  # 使用橙色主题色
        product_y = int(english_y + 40)
        painter.drawText(QRect(0, product_y, self.width(), 30), Qt.AlignCenter, "COMTool")
        
        # 版本信息
        painter.setFont(QFont("Microsoft YaHei", 10))
        painter.setPen(QColor(150, 150, 150))
        version_y = int(product_y + 35)
        painter.drawText(QRect(0, version_y, self.width(), 15), Qt.AlignCenter, "专业串口调试工具 v2.0")
        

def show_splash_screen():
    """显示启动画面"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    splash = AnimatedSplashScreen()
    splash.show()
    splash.start_animation()
    
    # 处理事件循环，确保动画流畅
    start_time = time.time()
    while time.time() - start_time < 5:  # 显示5秒
        app.processEvents()
        time.sleep(0.01)
    
    return splash

if __name__ == "__main__":
    app = QApplication(sys.argv)
    splash = show_splash_screen()
    sys.exit(app.exec_())