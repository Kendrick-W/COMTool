import sys
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QCheckBox, QPushButton, QFrame, QScrollArea, QLineEdit
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor

class DigitalDisplay(QLabel):
    """数显管样式的数字显示组件"""
    def __init__(self, digits=2, parent=None):
        super().__init__(parent)
        self.digits = digits
        self.value = 0
        
        # 设置固定大小
        self.setFixedSize(80, 40)
        self.setAlignment(Qt.AlignCenter)
        
        # 设置数显管样式
        self.setStyleSheet("""
            QLabel {
                background-color: #000000;
                color: #00FF00;
                border: 2px solid #333333;
                border-radius: 5px;
                font-family: 'Courier New', monospace;
                font-size: 18px;
                font-weight: bold;
                padding: 5px;
            }
        """)
        
        self.update_display()
        
    def set_value(self, value):
        """设置显示值"""
        if isinstance(value, (int, float)):
            self.value = int(value)
            self.update_display()
    
    def update_display(self):
        """更新显示内容"""
        # 限制值在有效范围内
        max_value = 10 ** self.digits - 1
        display_value = max(0, min(self.value, max_value))
        
        # 格式化为指定位数，前面补0
        format_str = f"{{:0{self.digits}d}}"
        display_text = format_str.format(display_value)
        
        self.setText(display_text)
        
        # 设置工具提示
        self.setToolTip(f"当前值: {self.value}")

class LEDIndicator(QLabel):
    """LED指示灯组件"""
    def __init__(self, bit_number, parent=None):
        super().__init__(parent)
        self.bit_number = bit_number
        self.state = 0  # 0为关闭，1为开启
        
        # 设置固定大小
        self.setFixedSize(30, 30)
        self.setAlignment(Qt.AlignCenter)
        
        # 设置样式
        self.update_appearance()
        
        # 设置工具提示
        self.setToolTip(f"位 {bit_number} - 自锁状态")
        
    def update_appearance(self):
        """更新LED外观"""
        if self.state == 1:
            # 开启状态 - 绿色LED带发光效果
            self.setStyleSheet("""
                QLabel {
                    background: qradialgradient(cx:0.5, cy:0.3, radius:0.8,
                        stop:0 #66FF66, stop:0.3 #4CAF50, stop:1 #2E7D32);
                    border: 2px solid #1B5E20;
                    border-radius: 15px;
                }
            """)
            self.setText("")
        else:
            # 关闭状态 - 暗灰色LED
            self.setStyleSheet("""
                QLabel {
                    background: qradialgradient(cx:0.5, cy:0.3, radius:0.8,
                        stop:0 #666666, stop:0.3 #424242, stop:1 #212121);
                    border: 2px solid #424242;
                    border-radius: 15px;
                }
            """)
            self.setText("")
    
    def set_state(self, state):
        """设置LED状态"""
        if self.state != state:
            self.state = state
            self.update_appearance()

class LEDStatusWindow(QWidget):
    """LED状态显示窗口"""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.led_indicators = {}  # 存储LED指示器
        self.latch_bits = []  # 存储自锁位列表
        
        self.setWindowTitle('LED状态显示')
        self.setGeometry(200, 200, 1050, 600)  # 增加宽度以适应侧边栏
        
        # 设置窗口属性
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)
        
        self.init_ui()
        self.setup_timer()
        self.init_digital_displays()
        
        # 设置初始监控状态
        self.set_axis_status('X', True)
        self.set_multiplier_status('x1', True)
        
    def init_ui(self):
        """初始化用户界面"""
        # 主布局
        main_layout = QVBoxLayout()
        
        # 标题
        title_label = QLabel('LED状态显示')
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)
        
        # 说明文字
        info_label = QLabel('')
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet('color: #666; margin: 10px;')
        main_layout.addWidget(info_label)
        
        # 控制面板
        control_layout = QHBoxLayout()
        
        # 置顶复选框
        self.stay_on_top_checkbox = QCheckBox('窗口置顶')
        self.stay_on_top_checkbox.stateChanged.connect(self.toggle_stay_on_top)
        
        control_layout.addStretch()
        control_layout.addWidget(self.stay_on_top_checkbox)
        main_layout.addLayout(control_layout)
        
        # 创建水平布局容器，包含主内容区域和侧边栏
        content_layout = QHBoxLayout()
        
        # 主内容区域
        main_content_widget = QWidget()
        main_content_layout = QVBoxLayout(main_content_widget)
        
        # 数显管显示区域
        digital_display_frame = QFrame()
        digital_display_frame.setFrameStyle(QFrame.StyledPanel)
        digital_display_frame.setStyleSheet('''
            QFrame {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin: 5px;
            }
        ''')
        
        digital_layout = QHBoxLayout(digital_display_frame)
        digital_layout.setSpacing(15)
        digital_layout.setContentsMargins(15, 10, 15, 10)
        
        # 数显管标题
        digital_title = QLabel('数据显示:')
        digital_title.setStyleSheet('font-weight: bold; color: #333;')
        digital_layout.addWidget(digital_title)
        
        # 创建两个数显管组件
        self.digital_display_1 = DigitalDisplay(digits=2)
        self.digital_display_1.setToolTip('数显管1 - 显示自定义数据')
        
        self.digital_display_2 = DigitalDisplay(digits=2)
        self.digital_display_2.setToolTip('数显管2 - 显示自定义数据')
        
        # 数显管标签
        display1_label = QLabel('1')
        display1_label.setAlignment(Qt.AlignCenter)
        display1_label.setStyleSheet('font-size: 10px; color: #666;')
        
        display2_label = QLabel('2')
        display2_label.setAlignment(Qt.AlignCenter)
        display2_label.setStyleSheet('font-size: 10px; color: #666;')
        
        # 创建数显管容器
        display1_container = QWidget()
        display1_layout = QVBoxLayout(display1_container)
        display1_layout.setSpacing(2)
        display1_layout.addWidget(display1_label)
        display1_layout.addWidget(self.digital_display_1)
        
        display2_container = QWidget()
        display2_layout = QVBoxLayout(display2_container)
        display2_layout.setSpacing(2)
        display2_layout.addWidget(display2_label)
        display2_layout.addWidget(self.digital_display_2)
        
        digital_layout.addWidget(display1_container)
        digital_layout.addWidget(display2_container)
        digital_layout.addStretch()
        
        main_content_layout.addWidget(digital_display_frame)
        
        # 轴选监控区域
        axis_control_frame = QFrame()
        axis_control_frame.setFrameStyle(QFrame.StyledPanel)
        axis_control_frame.setStyleSheet('''
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                margin: 5px;
            }
        ''')
        
        axis_main_layout = QVBoxLayout(axis_control_frame)
        axis_main_layout.setSpacing(10)
        axis_main_layout.setContentsMargins(15, 10, 15, 10)
        
        # 轴选标题
        axis_title = QLabel('轴选监控:')
        axis_title.setStyleSheet('font-weight: bold; color: #333; margin-bottom: 5px;')
        axis_main_layout.addWidget(axis_title)
        
        # 轴选和倍率的水平布局
        axis_controls_layout = QHBoxLayout()
        
        # 轴监控区域
        axis_selection_group = QWidget()
        axis_selection_layout = QVBoxLayout(axis_selection_group)
        axis_selection_layout.setSpacing(5)
        
        axis_label = QLabel('轴监控:')
        axis_label.setStyleSheet('font-size: 12px; color: #555; margin-bottom: 3px;')
        axis_selection_layout.addWidget(axis_label)
        
        # 轴监控布局
        axis_buttons_layout = QHBoxLayout()
        axis_buttons_layout.setSpacing(8)
        
        # 创建轴监控组件
        self.axis_options = ['X', 'Y', 'Z', '4', '5']
        self.current_axis = 'X'  # 默认监控X轴
        self.axis_indicators = {}
        
        for axis in self.axis_options:
            # 轴容器
            axis_container = QWidget()
            axis_container_layout = QVBoxLayout(axis_container)
            axis_container_layout.setSpacing(2)
            axis_container_layout.setContentsMargins(5, 5, 5, 5)
            
            # 轴标签（不可点击）
            axis_label = QLabel(axis)
            axis_label.setFixedSize(35, 25)
            axis_label.setStyleSheet('''
                QLabel {
                    background-color: #e9ecef;
                    border: 1px solid #ced4da;
                    border-radius: 3px;
                    font-weight: bold;
                    color: #495057;
                }
            ''')
            axis_label.setAlignment(Qt.AlignCenter)
            
            # 状态指示器
            indicator = QLabel()
            indicator.setFixedSize(8, 8)
            indicator.setStyleSheet('''
                QLabel {
                    background-color: #6c757d;
                    border-radius: 4px;
                }
            ''')
            indicator.setVisible(True)
            self.axis_indicators[axis] = indicator
            
            # 添加到容器
            axis_container_layout.addWidget(axis_label, alignment=Qt.AlignCenter)
            axis_container_layout.addWidget(indicator, alignment=Qt.AlignCenter)
            
            axis_buttons_layout.addWidget(axis_container)
        
        axis_selection_layout.addLayout(axis_buttons_layout)
        
        # 倍率监控区域
        multiplier_selection_group = QWidget()
        multiplier_selection_layout = QVBoxLayout(multiplier_selection_group)
        multiplier_selection_layout.setSpacing(5)
        
        multiplier_label = QLabel('倍率监控:')
        multiplier_label.setStyleSheet('font-size: 12px; color: #555; margin-bottom: 3px;')
        multiplier_selection_layout.addWidget(multiplier_label)
        
        # 倍率监控布局
        multiplier_buttons_layout = QHBoxLayout()
        multiplier_buttons_layout.setSpacing(8)
        
        # 创建倍率监控组件
        self.multiplier_options = ['x1', 'x10', 'x100']
        self.current_multiplier = 'x1'  # 默认监控x1
        self.multiplier_indicators = {}
        
        for multiplier in self.multiplier_options:
            # 倍率容器
            multiplier_container = QWidget()
            multiplier_container_layout = QVBoxLayout(multiplier_container)
            multiplier_container_layout.setSpacing(2)
            multiplier_container_layout.setContentsMargins(5, 5, 5, 5)
            
            # 倍率标签（不可点击）
            multiplier_label = QLabel(multiplier)
            multiplier_label.setFixedSize(40, 25)
            multiplier_label.setStyleSheet('''
                QLabel {
                    background-color: #e9ecef;
                    border: 1px solid #ced4da;
                    border-radius: 3px;
                    font-weight: bold;
                    color: #495057;
                }
            ''')
            multiplier_label.setAlignment(Qt.AlignCenter)
            
            # 状态指示器
            indicator = QLabel()
            indicator.setFixedSize(8, 8)
            indicator.setStyleSheet('''
                QLabel {
                    background-color: #6c757d;
                    border-radius: 4px;
                }
            ''')
            indicator.setVisible(True)
            self.multiplier_indicators[multiplier] = indicator
            
            # 添加到容器
            multiplier_container_layout.addWidget(multiplier_label, alignment=Qt.AlignCenter)
            multiplier_container_layout.addWidget(indicator, alignment=Qt.AlignCenter)
            
            multiplier_buttons_layout.addWidget(multiplier_container)
        
        multiplier_selection_layout.addLayout(multiplier_buttons_layout)
        
        # 添加轴选择和倍率选择到水平布局
        axis_controls_layout.addWidget(axis_selection_group)
        axis_controls_layout.addWidget(multiplier_selection_group)
        axis_controls_layout.addStretch()
        
        axis_main_layout.addLayout(axis_controls_layout)
        
        main_content_layout.addWidget(axis_control_frame)
        
        # LED网格容器
        self.led_container = QWidget()
        self.led_layout = QGridLayout(self.led_container)
        main_content_layout.addWidget(self.led_container)
        
        # 状态信息
        self.status_label = QLabel('等待映射配置加载...')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet('color: #888; margin: 10px;')
        main_content_layout.addWidget(self.status_label)
        
        main_content_layout.addStretch()
        
        # 添加主内容区域到水平布局
        content_layout.addWidget(main_content_widget, 3)  # 占3份空间
        
        # 创建侧边栏
        self.create_sidebar()
        content_layout.addWidget(self.sidebar_widget, 1)  # 占1份空间
        
        # 将水平布局添加到主布局
        main_layout.addLayout(content_layout)
        
        self.setLayout(main_layout)
        
    def create_sidebar(self):
        """创建侧边栏用于设置轴选信号I地址"""
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setFixedWidth(250)
        sidebar_layout = QVBoxLayout(self.sidebar_widget)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(10)
        
        # # 侧边栏标题
        # sidebar_title = QLabel('信号监控配置')
        # sidebar_title.setAlignment(Qt.AlignCenter)
        # sidebar_title.setStyleSheet('''
        #     QLabel {
        #         font-size: 14px;
        #         font-weight: bold;
        #         color: #333;
        #         background-color: #e9ecef;
        #         padding: 8px;
        #         border-radius: 5px;
        #         margin-bottom: 10px;
        #     }
        # ''')
        # sidebar_layout.addWidget(sidebar_title)
        
        # 轴选配置区域标题
        axis_section_title = QLabel('轴选信号配置')
        axis_section_title.setStyleSheet('color: #495057; font-size: 13px; font-weight: bold; margin-top: 5px; margin-bottom: 5px;')
        sidebar_layout.addWidget(axis_section_title)
        
        # # 说明文字
        # info_text = QLabel('设置各轴选信号对应的I地址:')
        # info_text.setStyleSheet('color: #666; font-size: 12px; margin-bottom: 5px;')
        # sidebar_layout.addWidget(info_text)
        
        # 创建表格配置区域
        table_frame = QFrame()
        table_frame.setFrameStyle(QFrame.StyledPanel)
        table_frame.setStyleSheet('''
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 5px;
            }
        ''')
        
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(5)
        
        # 表格标题行
        header_layout = QHBoxLayout()
        header_layout.setSpacing(5)
        
        axis_header = QLabel('轴')
        axis_header.setFixedWidth(30)
        axis_header.setAlignment(Qt.AlignCenter)
        axis_header.setStyleSheet('font-weight: bold; color: #495057; font-size: 11px;')
        
        address_header = QLabel('I地址')
        address_header.setFixedWidth(80)
        address_header.setAlignment(Qt.AlignCenter)
        address_header.setStyleSheet('font-weight: bold; color: #495057; font-size: 11px;')
        
        enable_header = QLabel('启用')
        enable_header.setFixedWidth(40)
        enable_header.setAlignment(Qt.AlignCenter)
        enable_header.setStyleSheet('font-weight: bold; color: #495057; font-size: 11px;')
        
        value_header = QLabel('当前值')
        value_header.setFixedWidth(50)
        value_header.setAlignment(Qt.AlignCenter)
        value_header.setStyleSheet('font-weight: bold; color: #495057; font-size: 11px;')
        
        header_layout.addWidget(axis_header)
        header_layout.addWidget(address_header)
        header_layout.addWidget(enable_header)
        header_layout.addWidget(value_header)
        header_layout.addStretch()
        
        table_layout.addLayout(header_layout)
        
        # 添加分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet('color: #dee2e6;')
        table_layout.addWidget(separator)
        
        # 初始化轴选信号配置
        self.axis_signal_config = {
            'X': {'address': '', 'enabled': False},
            'Y': {'address': '', 'enabled': False},
            'Z': {'address': '', 'enabled': False},
            '4': {'address': '', 'enabled': False},
            '5': {'address': '', 'enabled': False}
        }
        
        # 存储控件引用
        self.axis_address_inputs = {}
        self.axis_enable_checks = {}
        self.axis_value_labels = {}
        
        # 为每个轴创建配置行
        for axis in self.axis_options:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(5)
            
            # 轴标签
            axis_label = QLabel(f'{axis}')
            axis_label.setFixedWidth(30)
            axis_label.setAlignment(Qt.AlignCenter)
            axis_label.setStyleSheet('font-weight: bold; color: #333; font-size: 11px;')
            
            # I地址输入框
            address_input = QLineEdit()
            address_input.setFixedWidth(80)
            address_input.setPlaceholderText('I0.0')
            address_input.setStyleSheet('''
                QLineEdit {
                    padding: 3px;
                    border: 1px solid #ced4da;
                    border-radius: 3px;
                    font-size: 10px;
                }
                QLineEdit:focus {
                    border-color: #007bff;
                    outline: none;
                }
            ''')
            address_input.textChanged.connect(lambda text, ax=axis: self.on_axis_address_changed(ax, text))
            
            # 启用复选框
            enable_check = QCheckBox()
            enable_check.setFixedWidth(40)
            enable_check.setStyleSheet('QCheckBox { margin-left: 15px; }')
            enable_check.stateChanged.connect(lambda state, ax=axis: self.on_axis_enable_changed(ax, state))
            
            # 当前值标签
            value_label = QLabel('0')
            value_label.setFixedWidth(50)
            value_label.setAlignment(Qt.AlignCenter)
            value_label.setStyleSheet('''
                QLabel {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 3px;
                    padding: 3px;
                    font-size: 10px;
                    font-weight: bold;
                }
            ''')
            
            # 存储控件引用
            self.axis_address_inputs[axis] = address_input
            self.axis_enable_checks[axis] = enable_check
            self.axis_value_labels[axis] = value_label
            
            row_layout.addWidget(axis_label)
            row_layout.addWidget(address_input)
            row_layout.addWidget(enable_check)
            row_layout.addWidget(value_label)
            row_layout.addStretch()
            
            table_layout.addLayout(row_layout)
        
        sidebar_layout.addWidget(table_frame)
        
        # 倍率配置区域
        multiplier_section_title = QLabel('倍率信号配置')
        multiplier_section_title.setStyleSheet('color: #495057; font-size: 13px; font-weight: bold; margin-top: 15px; margin-bottom: 5px;')
        sidebar_layout.addWidget(multiplier_section_title)
        
        # # 倍率说明文字
        # multiplier_info_text = QLabel('设置各倍率信号对应的I地址:')
        # multiplier_info_text.setStyleSheet('color: #666; font-size: 12px; margin-bottom: 5px;')
        # sidebar_layout.addWidget(multiplier_info_text)
        
        # 创建倍率配置表格区域
        multiplier_table_frame = QFrame()
        multiplier_table_frame.setFrameStyle(QFrame.StyledPanel)
        multiplier_table_frame.setStyleSheet('''
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 5px;
            }
        ''')
        
        multiplier_table_layout = QVBoxLayout(multiplier_table_frame)
        multiplier_table_layout.setContentsMargins(10, 10, 10, 10)
        multiplier_table_layout.setSpacing(5)
        
        # 倍率表格标题行
        multiplier_header_layout = QHBoxLayout()
        multiplier_header_layout.setSpacing(5)
        
        mult_header = QLabel('倍率')
        mult_header.setFixedWidth(40)
        mult_header.setAlignment(Qt.AlignCenter)
        mult_header.setStyleSheet('font-weight: bold; color: #495057; font-size: 11px;')
        
        mult_address_header = QLabel('I地址')
        mult_address_header.setFixedWidth(80)
        mult_address_header.setAlignment(Qt.AlignCenter)
        mult_address_header.setStyleSheet('font-weight: bold; color: #495057; font-size: 11px;')
        
        mult_enable_header = QLabel('启用')
        mult_enable_header.setFixedWidth(40)
        mult_enable_header.setAlignment(Qt.AlignCenter)
        mult_enable_header.setStyleSheet('font-weight: bold; color: #495057; font-size: 11px;')
        
        mult_value_header = QLabel('当前值')
        mult_value_header.setFixedWidth(50)
        mult_value_header.setAlignment(Qt.AlignCenter)
        mult_value_header.setStyleSheet('font-weight: bold; color: #495057; font-size: 11px;')
        
        multiplier_header_layout.addWidget(mult_header)
        multiplier_header_layout.addWidget(mult_address_header)
        multiplier_header_layout.addWidget(mult_enable_header)
        multiplier_header_layout.addWidget(mult_value_header)
        multiplier_header_layout.addStretch()
        
        multiplier_table_layout.addLayout(multiplier_header_layout)
        
        # 添加倍率分隔线
        multiplier_separator = QFrame()
        multiplier_separator.setFrameShape(QFrame.HLine)
        multiplier_separator.setFrameShadow(QFrame.Sunken)
        multiplier_separator.setStyleSheet('color: #dee2e6;')
        multiplier_table_layout.addWidget(multiplier_separator)
        
        # 初始化倍率信号配置
        self.multiplier_signal_config = {
            'x1': {'address': '', 'enabled': False},
            'x10': {'address': '', 'enabled': False},
            'x100': {'address': '', 'enabled': False}
        }
        
        # 存储倍率控件引用
        self.multiplier_address_inputs = {}
        self.multiplier_enable_checks = {}
        self.multiplier_value_labels = {}
        
        # 为每个倍率创建配置行
        for multiplier in self.multiplier_options:
            mult_row_layout = QHBoxLayout()
            mult_row_layout.setSpacing(5)
            
            # 倍率标签
            mult_label = QLabel(f'{multiplier}')
            mult_label.setFixedWidth(40)
            mult_label.setAlignment(Qt.AlignCenter)
            mult_label.setStyleSheet('font-weight: bold; color: #333; font-size: 11px;')
            
            # I地址输入框
            mult_address_input = QLineEdit()
            mult_address_input.setFixedWidth(80)
            mult_address_input.setPlaceholderText('I0.0')
            mult_address_input.setStyleSheet('''
                QLineEdit {
                    padding: 3px;
                    border: 1px solid #ced4da;
                    border-radius: 3px;
                    font-size: 10px;
                }
                QLineEdit:focus {
                    border-color: #007bff;
                    outline: none;
                }
            ''')
            mult_address_input.textChanged.connect(lambda text, mult=multiplier: self.on_multiplier_address_changed(mult, text))
            
            # 启用复选框
            mult_enable_check = QCheckBox()
            mult_enable_check.setFixedWidth(40)
            mult_enable_check.setStyleSheet('QCheckBox { margin-left: 15px; }')
            mult_enable_check.stateChanged.connect(lambda state, mult=multiplier: self.on_multiplier_enable_changed(mult, state))
            
            # 当前值标签
            mult_value_label = QLabel('0')
            mult_value_label.setFixedWidth(50)
            mult_value_label.setAlignment(Qt.AlignCenter)
            mult_value_label.setStyleSheet('''
                QLabel {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 3px;
                    padding: 3px;
                    font-size: 10px;
                    font-weight: bold;
                }
            ''')
            
            # 存储倍率控件引用
            self.multiplier_address_inputs[multiplier] = mult_address_input
            self.multiplier_enable_checks[multiplier] = mult_enable_check
            self.multiplier_value_labels[multiplier] = mult_value_label
            
            mult_row_layout.addWidget(mult_label)
            mult_row_layout.addWidget(mult_address_input)
            mult_row_layout.addWidget(mult_enable_check)
            mult_row_layout.addWidget(mult_value_label)
            mult_row_layout.addStretch()
            
            multiplier_table_layout.addLayout(mult_row_layout)
        
        sidebar_layout.addWidget(multiplier_table_frame)
        
        # 底部按钮区域
        button_layout = QHBoxLayout()
        
        # 保存配置按钮
        save_button = QPushButton('保存配置')
        save_button.setStyleSheet('''
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        ''')
        save_button.clicked.connect(self.save_axis_config)
        
        # 重置配置按钮
        reset_button = QPushButton('重置')
        reset_button.setStyleSheet('''
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #545b62;
            }
            QPushButton:pressed {
                background-color: #3d4142;
            }
        ''')
        reset_button.clicked.connect(self.reset_axis_config)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(reset_button)
        sidebar_layout.addLayout(button_layout)
        
        # 加载已保存的配置
        self.load_axis_config()
        
    def on_axis_address_changed(self, axis, address):
        """轴选信号地址变更处理"""
        self.axis_signal_config[axis]['address'] = address.strip()

    def on_axis_enable_changed(self, axis, state):
        """轴选信号启用状态变更处理"""
        enabled = state == 2  # Qt.Checked
        self.axis_signal_config[axis]['enabled'] = enabled
        
        # 更新左边监控区域的显示状态
        self.update_axis_monitoring_display()
    
    def on_multiplier_address_changed(self, multiplier, address):
        """倍率信号地址变更处理"""
        self.multiplier_signal_config[multiplier]['address'] = address.strip()

    def on_multiplier_enable_changed(self, multiplier, state):
        """倍率信号启用状态变更处理"""
        enabled = state == 2  # Qt.Checked
        self.multiplier_signal_config[multiplier]['enabled'] = enabled
        
        # 更新左边监控区域的显示状态
        self.update_multiplier_monitoring_display()
        
    def save_axis_config(self):
        """保存信号配置（轴选和倍率）"""
        try:
            import json
            import os
            
            # 创建配置目录
            config_dir = os.path.join(os.path.dirname(__file__), 'config')
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            # 合并轴选和倍率配置
            combined_config = {
                'axis_signals': self.axis_signal_config,
                'multiplier_signals': self.multiplier_signal_config
            }
            
            # 保存配置文件
            config_file = os.path.join(config_dir, 'axis_signal_config.json')
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(combined_config, f, ensure_ascii=False, indent=2)
            
            # 显示保存成功消息
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, '保存成功', '信号配置已保存！')
            
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, '保存失败', f'保存配置时发生错误：{str(e)}')
    
    def reset_axis_config(self):
        """重置信号配置（轴选和倍率）"""
        from PyQt5.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(self, '确认重置', 
                                   '确定要重置所有信号配置吗？',
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 清空轴选配置
            for axis in self.axis_options:
                self.axis_signal_config[axis] = {'address': '', 'enabled': False}
                self.axis_address_inputs[axis].setText('')
                self.axis_enable_checks[axis].setChecked(False)
                self.axis_value_labels[axis].setText('0')
            
            # 清空倍率配置
            for multiplier in self.multiplier_options:
                self.multiplier_signal_config[multiplier] = {'address': '', 'enabled': False}
                self.multiplier_address_inputs[multiplier].setText('')
                self.multiplier_enable_checks[multiplier].setChecked(False)
                self.multiplier_value_labels[multiplier].setText('0')
            
            # 更新显示
            self.update_axis_monitoring_display()
            self.update_multiplier_monitoring_display()
    
    def load_axis_config(self):
        """加载信号配置（轴选和倍率）"""
        try:
            import json
            import os
            
            config_file = os.path.join(os.path.dirname(__file__), 'config', 'axis_signal_config.json')
            
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                
                # 检查是否为新格式（包含axis_signals和multiplier_signals）
                if 'axis_signals' in saved_config and 'multiplier_signals' in saved_config:
                    # 新格式：分别处理轴选和倍率配置
                    axis_config = saved_config['axis_signals']
                    multiplier_config = saved_config['multiplier_signals']
                    
                    # 加载轴选配置
                    for axis in self.axis_options:
                        if axis in axis_config:
                            address = axis_config[axis].get('address', '')
                            enabled = axis_config[axis].get('enabled', False)
                            
                            self.axis_signal_config[axis] = {'address': address, 'enabled': enabled}
                            self.axis_address_inputs[axis].setText(address)
                            self.axis_enable_checks[axis].setChecked(enabled)
                    
                    # 加载倍率配置
                    for multiplier in self.multiplier_options:
                        if multiplier in multiplier_config:
                            address = multiplier_config[multiplier].get('address', '')
                            enabled = multiplier_config[multiplier].get('enabled', False)
                            
                            self.multiplier_signal_config[multiplier] = {'address': address, 'enabled': enabled}
                            self.multiplier_address_inputs[multiplier].setText(address)
                            self.multiplier_enable_checks[multiplier].setChecked(enabled)
                else:
                    # 旧格式：只有轴选配置
                    for axis in self.axis_options:
                        if axis in saved_config:
                            # 兼容旧格式（字符串）和新格式（字典）
                            if isinstance(saved_config[axis], str):
                                # 旧格式，只有地址
                                address = saved_config[axis]
                                enabled = False
                            else:
                                # 新格式，包含地址和启用状态
                                address = saved_config[axis].get('address', '')
                                enabled = saved_config[axis].get('enabled', False)
                            
                            self.axis_signal_config[axis] = {'address': address, 'enabled': enabled}
                            self.axis_address_inputs[axis].setText(address)
                            self.axis_enable_checks[axis].setChecked(enabled)
                
                # 更新监控显示
                self.update_axis_monitoring_display()
                self.update_multiplier_monitoring_display()
                        
        except Exception as e:
            print(f'加载信号配置失败: {e}')
            # 使用默认配置
            for axis in self.axis_options:
                self.axis_signal_config[axis] = {'address': '', 'enabled': False}
            for multiplier in self.multiplier_options:
                self.multiplier_signal_config[multiplier] = {'address': '', 'enabled': False}
    
    def get_axis_signal_address(self, axis):
        """获取指定轴的信号地址"""
        config = self.axis_signal_config.get(axis, {'address': '', 'enabled': False})
        return config.get('address', '')
    
    def get_all_axis_signal_config(self):
        """获取所有轴选信号配置"""
        return self.axis_signal_config.copy()
    
    def update_axis_monitoring_display(self):
        """更新轴监控显示状态"""
        # 根据启用状态更新轴监控指示器的可见性或样式
        for axis in self.axis_options:
            if axis in self.axis_indicators:
                enabled = self.axis_signal_config[axis]['enabled']
                # 找到对应的轴标签容器
                axis_container = self.axis_indicators[axis].parent()
                if axis_container:
                    # 找到轴标签（第一个子控件）
                    axis_label = axis_container.layout().itemAt(0).widget()
                    if axis_label:
                        if enabled:
                            # 启用状态下，恢复默认样式，等待信号激活
                            axis_label.setStyleSheet('''
                                QLabel {
                                    background-color: #e9ecef;
                                    border: 1px solid #ced4da;
                                    border-radius: 3px;
                                    font-weight: bold;
                                    color: #495057;
                                }
                            ''')
                        else:
                            # 未启用状态下，标签显示为禁用样式
                            axis_label.setStyleSheet('''
                                QLabel {
                                    background-color: #dee2e6;
                                    border: 1px solid #adb5bd;
                                    border-radius: 3px;
                                    font-weight: bold;
                                    color: #6c757d;
                                }
                            ''')
                
                # 隐藏小指示器
                self.axis_indicators[axis].setVisible(False)
    
    def update_multiplier_monitoring_display(self):
        """更新倍率监控显示状态"""
        # 根据启用状态更新倍率监控指示器的可见性或样式
        for multiplier in self.multiplier_options:
            if multiplier in self.multiplier_indicators:
                enabled = self.multiplier_signal_config[multiplier]['enabled']
                # 找到对应的倍率标签容器
                multiplier_container = self.multiplier_indicators[multiplier].parent()
                if multiplier_container:
                    # 找到倍率标签（第一个子控件）
                    multiplier_label = multiplier_container.layout().itemAt(0).widget()
                    if multiplier_label:
                        if enabled:
                            # 启用状态下，恢复默认样式，等待信号激活
                            multiplier_label.setStyleSheet('''
                                QLabel {
                                    background-color: #e9ecef;
                                    border: 1px solid #ced4da;
                                    border-radius: 3px;
                                    font-weight: bold;
                                    color: #495057;
                                }
                            ''')
                        else:
                            # 未启用状态下，标签显示为禁用样式
                            multiplier_label.setStyleSheet('''
                                QLabel {
                                    background-color: #dee2e6;
                                    border: 1px solid #adb5bd;
                                    border-radius: 3px;
                                    font-weight: bold;
                                    color: #6c757d;
                                }
                            ''')
                
                # 隐藏小指示器
                self.multiplier_indicators[multiplier].setVisible(False)
    
    def update_main_axis_indicators(self, signal_values):
        """根据轴选信号值更新主界面的轴选指示器状态
        
        Args:
            signal_values (dict): 轴选信号的当前值，格式为 {axis: value}
        """
        # 首先重置所有轴选指示器为非激活状态
        for axis in self.axis_options:
            if axis in self.axis_indicators:
                self.set_axis_status(axis, False)
        
        # 根据信号值设置激活的轴
        for axis, value in signal_values.items():
            if value and axis in self.axis_indicators:
                self.set_axis_status(axis, True)
                break  # 只激活第一个检测到信号的轴
    
    def update_axis_signal_values_from_main(self):
        """从主窗口获取数据并更新轴选信号值"""
        if not hasattr(self, 'main_window') or not self.main_window:
            return
            
        # 获取主窗口的最新接收数据
        if hasattr(self.main_window, 'last_received_data') and self.main_window.last_received_data:
            data = self.main_window.last_received_data
            signal_values = {}
            
            # 解析每个启用的轴选信号
            for axis in self.axis_options:
                config = self.axis_signal_config[axis]
                
                if config['enabled'] and config['address']:
                    # 解析I地址格式 (如: I0.0, I1.5等) 或纯数字格式 (如: 71, 0.0等)
                    address = config['address'].strip().upper()
                    
                    # 自动添加I前缀（如果没有的话）
                    if not address.startswith('I'):
                        address = 'I' + address
                    
                    if address.startswith('I'):
                        try:
                            # 解析地址格式 I字节.位 或 I位号
                            addr_part = address[1:]  # 去掉'I'
                            if '.' in addr_part:
                                # 格式：I字节.位 (如 I0.0, I1.5)
                                byte_str, bit_str = addr_part.split('.')
                                byte_index = int(byte_str)
                                bit_index = int(bit_str)
                            else:
                                # 格式：I位号 (如 I71, I0)
                                bit_number = int(addr_part)
                                byte_index = bit_number // 8  # 计算字节索引
                                bit_index = 7 - (bit_number % 8)  # 计算位索引（I0是最高位，I7是最低位）
                                
                            # 检查数据长度和索引有效性
                            # 数据包格式：5A + 数据字节，需要跳过5A起始字节
                            if len(data) > byte_index + 1 and 0 <= bit_index <= 7:
                                # 获取指定字节的指定位（跳过5A起始字节）
                                byte_value = data[byte_index + 1]  # 跳过5A起始字节
                                bit_value = (byte_value >> bit_index) & 1
                                signal_values[axis] = bit_value
                            else:
                                signal_values[axis] = 0
                        except (ValueError, IndexError):
                            signal_values[axis] = 0
                    else:
                        signal_values[axis] = 0
                else:
                    signal_values[axis] = 0
            
            # 更新显示
            self.update_axis_signal_values(signal_values)
            
            # 根据信号值更新主界面的轴选指示器状态
            self.update_main_axis_indicators(signal_values)
            
            # 同时更新倍率信号值
            self.update_multiplier_signal_values_from_main()
    
    def update_axis_signal_values(self, signal_values):
        """更新轴选信号的当前值
        
        Args:
            signal_values (dict): 轴选信号的当前值，格式为 {axis: value}
        """
        for axis, value in signal_values.items():
            if axis in self.axis_value_labels:
                self.axis_value_labels[axis].setText(str(value))
                # 根据值更新样式
                if value:
                    self.axis_value_labels[axis].setStyleSheet('''
                        QLabel {
                            background-color: #d4edda;
                            border: 1px solid #c3e6cb;
                            border-radius: 3px;
                            padding: 3px;
                            font-size: 10px;
                            font-weight: bold;
                            color: #155724;
                        }
                    ''')
                else:
                    self.axis_value_labels[axis].setStyleSheet('''
                        QLabel {
                            background-color: #f8f9fa;
                            border: 1px solid #dee2e6;
                            border-radius: 3px;
                            padding: 3px;
                            font-size: 10px;
                            font-weight: bold;
                        }
                    ''')
        
    def setup_timer(self):
        """设置定时器用于实时更新LED状态"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_displays)
        self.update_timer.start(100)  # 每100ms更新一次
        
    def update_displays(self):
        """更新所有显示组件"""
        # 更新LED状态
        self.update_led_states()
        
        # 更新数显管显示（演示功能）
        self.update_digital_displays_demo()
        
        # 更新轴选信号值
        self.update_axis_signal_values_from_main()
        
    def init_digital_displays(self):
        """初始化数显管显示"""
        # 设置初始值
        self.digital_display_1.set_value(0)
        self.digital_display_2.set_value(0)
        
    def set_digital_display_value(self, display_number, value):
        """设置指定数显管的值
        
        Args:
            display_number (int): 数显管编号 (1 或 2)
            value (int): 要显示的值
        """
        if display_number == 1 and hasattr(self, 'digital_display_1'):
            self.digital_display_1.set_value(value)
        elif display_number == 2 and hasattr(self, 'digital_display_2'):
            self.digital_display_2.set_value(value)
        else:
            print(f"无效的数显管编号: {display_number}")
            
    def get_digital_display_value(self, display_number):
        """获取指定数显管的值
        
        Args:
            display_number (int): 数显管编号 (1 或 2)
            
        Returns:
            int: 数显管当前显示的值，如果无效则返回None
        """
        if display_number == 1 and hasattr(self, 'digital_display_1'):
            return self.digital_display_1.value
        elif display_number == 2 and hasattr(self, 'digital_display_2'):
            return self.digital_display_2.value
        else:
            print(f"无效的数显管编号: {display_number}")
            return None
            
    def update_digital_displays_demo(self):
        """演示数显管更新（可以根据实际需求修改）"""
        import time
        current_time = int(time.time()) % 100  # 获取当前时间的秒数部分
        
        # 示例：显示当前活跃的LED数量
        active_led_count = sum(1 for led in self.led_indicators.values() if led.state == 1)
        
        # 更新数显管
        self.set_digital_display_value(1, active_led_count)
        self.set_digital_display_value(2, current_time)
        
    def set_axis_status(self, axis, active):
        """设置轴的监控状态
        
        Args:
            axis (str): 轴名称 ('X', 'Y', 'Z', '4', '5')
            active (bool): 是否激活状态
        """
        if axis in self.axis_indicators:
            # 找到对应的轴标签容器
            axis_container = self.axis_indicators[axis].parent()
            if axis_container:
                # 找到轴标签（第一个子控件）
                axis_label = axis_container.layout().itemAt(0).widget()
                if axis_label:
                    if active:
                        # 激活状态：整个轴标签变绿色背景
                        axis_label.setStyleSheet('''
                            QLabel {
                                background-color: #28a745;
                                border: 1px solid #1e7e34;
                                border-radius: 3px;
                                font-weight: bold;
                                color: white;
                            }
                        ''')
                        self.current_axis = axis
                    else:
                        # 非激活状态：恢复默认样式
                        axis_label.setStyleSheet('''
                            QLabel {
                                background-color: #e9ecef;
                                border: 1px solid #ced4da;
                                border-radius: 3px;
                                font-weight: bold;
                                color: #495057;
                            }
                        ''')
            
            # 隐藏小指示器，因为现在用整个标签背景来表示状态
            self.axis_indicators[axis].setVisible(False)
            
    def set_multiplier_status(self, multiplier, active):
        """设置倍率的监控状态
        
        Args:
            multiplier (str): 倍率名称 ('x1', 'x10', 'x100')
            active (bool): 是否激活状态
        """
        if multiplier in self.multiplier_indicators:
            # 找到对应的倍率标签容器
            multiplier_container = self.multiplier_indicators[multiplier].parent()
            if multiplier_container:
                # 找到倍率标签（第一个子控件）
                multiplier_label = multiplier_container.layout().itemAt(0).widget()
                if multiplier_label:
                    if active:
                        # 激活状态：整个倍率标签变绿色背景
                        multiplier_label.setStyleSheet('''
                            QLabel {
                                background-color: #28a745;
                                border: 1px solid #1e7e34;
                                border-radius: 3px;
                                font-weight: bold;
                                color: white;
                            }
                        ''')
                        self.current_multiplier = multiplier
                    else:
                        # 非激活状态：恢复默认样式
                        multiplier_label.setStyleSheet('''
                            QLabel {
                                background-color: #e9ecef;
                                border: 1px solid #ced4da;
                                border-radius: 3px;
                                font-weight: bold;
                                color: #495057;
                            }
                        ''')
            
            # 隐藏小指示器，因为现在用整个标签背景来表示状态
            self.multiplier_indicators[multiplier].setVisible(False)
            
    def update_axis_multiplier_from_data(self, axis_data, multiplier_data):
        """根据外部数据更新轴选和倍率状态
        
        Args:
            axis_data (str): 当前激活的轴
            multiplier_data (str): 当前激活的倍率
        """
        # 重置所有指示器
        for ax in self.axis_indicators:
            self.set_axis_status(ax, False)
        for mult in self.multiplier_indicators:
            self.set_multiplier_status(mult, False)
        
        # 根据数据设置当前状态
        if axis_data in self.axis_indicators:
            self.set_axis_status(axis_data, True)
        if multiplier_data in self.multiplier_indicators:
            self.set_multiplier_status(multiplier_data, True)
            
    def get_current_axis(self):
        """获取当前监控的轴
        
        Returns:
            str: 当前监控的轴
        """
        return getattr(self, 'current_axis', 'X')
        
    def get_current_multiplier(self):
        """获取当前监控的倍率
        
        Returns:
            str: 当前监控的倍率
        """
        return getattr(self, 'current_multiplier', 'x1')
    
    def update_multiplier_signal_values_from_main(self):
        """从主窗口获取数据并更新倍率信号值"""
        if not hasattr(self, 'main_window') or not self.main_window:
            return
            
        # 获取主窗口的最新接收数据
        if hasattr(self.main_window, 'last_received_data') and self.main_window.last_received_data:
            data = self.main_window.last_received_data
            signal_values = {}
            
            # 解析每个启用的倍率信号
            for multiplier in self.multiplier_options:
                config = self.multiplier_signal_config[multiplier]
                
                if config['enabled'] and config['address']:
                    # 解析I地址格式 (如: I0.0, I1.5等) 或纯数字格式 (如: 71, 0.0等)
                    address = config['address'].strip().upper()
                    
                    # 自动添加I前缀（如果没有的话）
                    if not address.startswith('I'):
                        address = 'I' + address
                    
                    if address.startswith('I'):
                        try:
                            # 解析地址格式 I字节.位 或 I位号
                            addr_part = address[1:]  # 去掉'I'
                            if '.' in addr_part:
                                # 格式：I字节.位 (如 I0.0, I1.5)
                                byte_str, bit_str = addr_part.split('.')
                                byte_index = int(byte_str)
                                bit_index = int(bit_str)
                            else:
                                # 格式：I位号 (如 I71, I0)
                                bit_number = int(addr_part)
                                byte_index = bit_number // 8  # 计算字节索引
                                bit_index = 7 - (bit_number % 8)  # 计算位索引（I0是最高位，I7是最低位）
                                
                            # 检查数据长度和索引有效性
                            # 数据包格式：5A + 数据字节，需要跳过5A起始字节
                            if len(data) > byte_index + 1 and 0 <= bit_index <= 7:
                                # 获取指定字节的指定位（跳过5A起始字节）
                                byte_value = data[byte_index + 1]  # 跳过5A起始字节
                                bit_value = (byte_value >> bit_index) & 1
                                signal_values[multiplier] = bit_value
                            else:
                                signal_values[multiplier] = 0
                        except (ValueError, IndexError):
                            signal_values[multiplier] = 0
                    else:
                        signal_values[multiplier] = 0
                else:
                    signal_values[multiplier] = 0
            
            # 更新显示
            self.update_multiplier_signal_values(signal_values)
            
            # 根据信号值更新主界面的倍率指示器状态
            self.update_main_multiplier_indicators(signal_values)
    
    def update_multiplier_signal_values(self, signal_values):
        """更新倍率信号的当前值
        
        Args:
            signal_values (dict): 倍率信号的当前值，格式为 {multiplier: value}
        """
        for multiplier, value in signal_values.items():
            if multiplier in self.multiplier_value_labels:
                self.multiplier_value_labels[multiplier].setText(str(value))
                # 根据值更新样式
                if value:
                    self.multiplier_value_labels[multiplier].setStyleSheet('''
                        QLabel {
                            background-color: #d4edda;
                            border: 1px solid #c3e6cb;
                            border-radius: 3px;
                            padding: 3px;
                            font-size: 10px;
                            font-weight: bold;
                            color: #155724;
                        }
                    ''')
                else:
                    self.multiplier_value_labels[multiplier].setStyleSheet('''
                        QLabel {
                            background-color: #f8f9fa;
                            border: 1px solid #dee2e6;
                            border-radius: 3px;
                            padding: 3px;
                            font-size: 10px;
                            font-weight: bold;
                        }
                    ''')
    
    def update_main_multiplier_indicators(self, signal_values):
        """根据倍率信号值更新主界面的倍率指示器状态
        
        Args:
            signal_values (dict): 倍率信号的当前值，格式为 {multiplier: value}
        """
        # 首先重置所有倍率指示器为非激活状态
        for multiplier in self.multiplier_options:
            if multiplier in self.multiplier_indicators:
                self.set_multiplier_status(multiplier, False)
        
        # 根据信号值设置激活的倍率
        for multiplier, value in signal_values.items():
            if value and multiplier in self.multiplier_indicators:
                self.set_multiplier_status(multiplier, True)
                break  # 只激活第一个检测到信号的倍率
        
    def get_axis_control_state(self):
        """获取轴控制监控状态
        
        Returns:
            dict: 包含轴监控和倍率监控的状态字典
        """
        return {
            'current_axis': self.get_current_axis(),
            'current_multiplier': self.get_current_multiplier(),
            'axis_options': self.axis_options,
            'multiplier_options': self.multiplier_options
        }
        

        

        
    def toggle_stay_on_top(self, state):
        """切换窗口置顶状态"""
        if state == Qt.Checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()
        
    def load_latch_configuration(self):
        """加载自锁配置并创建LED指示器"""
        try:
            # 清除现有的LED指示器
            self.clear_led_indicators()
            
            # 检查主窗口是否有必要的属性
            if not hasattr(self.main_window, 'bit_mapping_latch'):
                self.status_label.setText('主窗口缺少自锁配置')
                return
            
            # 获取所有启用自锁的位
            self.latch_bits = []
            for bit_str, is_latch_enabled in self.main_window.bit_mapping_latch.items():
                if is_latch_enabled:
                    try:
                        self.latch_bits.append(int(bit_str))
                    except ValueError:
                        print(f"无效的位号: {bit_str}")
                        continue
            
            self.latch_bits.sort()  # 排序
            
            if not self.latch_bits:
                self.status_label.setText('没有启用自锁的位')
                return
                
            # 创建LED指示器
            self.create_led_indicators()
            self.status_label.setText(f'显示 {len(self.latch_bits)} 个自锁位的状态')
            
        except Exception as e:
            print(f"加载自锁配置时发生错误: {e}")
            self.status_label.setText(f'配置加载失败: {str(e)}')
        
    def clear_led_indicators(self):
        """清除所有LED指示器"""
        # 清除所有LED指示器
        for led in self.led_indicators.values():
            led.setParent(None)
            led.deleteLater()
        self.led_indicators.clear()
        
        # 清除布局中的所有子组件
        while self.led_layout.count():
            child = self.led_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
                child.widget().deleteLater()
        
    def create_led_indicators(self):
        """创建LED指示器"""
        cols = 8  # 每行8个LED
        
        for i, bit in enumerate(self.latch_bits):
            row = i // cols
            col = i % cols
            
            # 创建LED容器
            led_container = QWidget()
            led_container_layout = QVBoxLayout(led_container)
            led_container_layout.setSpacing(2)
            led_container_layout.setContentsMargins(5, 5, 5, 5)
            
            # 位标签
            bit_label = QLabel(f'位{bit}')
            bit_label.setAlignment(Qt.AlignCenter)
            bit_label.setStyleSheet('font-size: 10px; color: #333;')
            
            # LED指示器
            led = LEDIndicator(bit)
            self.led_indicators[bit] = led
            
            led_container_layout.addWidget(bit_label)
            led_container_layout.addWidget(led)
            
            self.led_layout.addWidget(led_container, row, col)
            
    def update_led_states(self):
        """更新LED状态"""
        try:
            if not hasattr(self.main_window, 'bit_mapping_latch_states'):
                # 如果主窗口没有状态数据，尝试初始化
                if hasattr(self.main_window, 'bit_mapping_latch'):
                    if not hasattr(self.main_window, 'bit_mapping_latch_states'):
                        self.main_window.bit_mapping_latch_states = {}
                    # 为所有自锁位初始化状态（如果不存在）
                    for bit_str, is_latch in self.main_window.bit_mapping_latch.items():
                        if is_latch and bit_str not in self.main_window.bit_mapping_latch_states:
                            self.main_window.bit_mapping_latch_states[bit_str] = 0
                else:
                    return
                
            updated_count = 0
            for bit, led in self.led_indicators.items():
                bit_str = str(bit)
                if bit_str in self.main_window.bit_mapping_latch_states:
                    state = self.main_window.bit_mapping_latch_states[bit_str]
                    old_state = led.state
                    led.set_state(state)
                    
                    # 状态标签已移除，不再更新
                    
                    # 统计状态变化
                    if old_state != state:
                        updated_count += 1
                else:
                    # 如果状态不存在，设置为默认值0
                    led.set_state(0)
                        
        except Exception as e:
            print(f"更新LED状态时发生错误: {e}")
        
        # 调试信息：在控制台输出更新信息（可选）
        # if updated_count > 0:
        #     print(f"LED状态更新: {updated_count} 个位状态发生变化")
                    
    def closeEvent(self, event):
        """窗口关闭事件"""
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        event.accept()

if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    
    # 创建一个模拟的主窗口对象用于测试
    class MockMainWindow:
        def __init__(self):
            self.bit_mapping_latch = {'0': True, '5': True, '10': True}
            self.bit_mapping_latch_states = {'0': 0, '5': 1, '10': 0}
    
    mock_main = MockMainWindow()
    window = LEDStatusWindow(mock_main)
    window.load_latch_configuration()
    window.show()
    
    sys.exit(app.exec_())