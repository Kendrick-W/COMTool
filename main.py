import sys
import os
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
import logging
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QComboBox, QPushButton, QTextEdit, QCheckBox, QStatusBar,
                             QGroupBox, QGridLayout, QMessageBox, QAction, QMenuBar, QFileDialog,
                             QSpinBox, QTabWidget, QListWidget, QSplitter, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QTimer
from PyQt5.QtGui import QFont, QTextCursor, QColor


class SerialThread(QThread):
    """串口读取线程"""
    data_received = pyqtSignal(bytes)

    def __init__(self, serial_port):
        super().__init__()
        self.serial_port = serial_port
        self.running = False

    def run(self):
        self.running = True
        while self.running and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    self.data_received.emit(data)
                time.sleep(0.001)  # 减少延迟，提高响应速度
            except Exception as e:
                print(f"读取数据错误: {str(e)}")
                break

    def stop(self):
        self.running = False
        self.wait()


class AdvancedSerialTool(QMainWindow):
    def __init__(self):
        super().__init__()

        # 设置中文字体
        font = QFont()
        font.setFamily("SimHei")
        font.setPointSize(10)
        self.setFont(font)

        # 串口对象和读取线程
        self.ser = None
        self.serial_thread = None

        # 数据统计
        self.rx_count = 0
        self.tx_count = 0

        # 发送历史
        self.send_history = []
        self.history_index = -1

        # 定时发送
        self.timer = QTimer()
        self.timer.timeout.connect(self.send_data)
        
        # 定时更新启用映射列表
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_enabled_mappings_list)
        self.update_timer.start(1000)  # 每1000毫秒（1秒）执行一次

        # 数据映射配置（I/O位映射）
        self.bit_mapping = {}
        self.bit_mapping_enabled = {}  # 存储每个映射是否启用
        for i in range(192):  # 24字节 * 8位，对应D0~D23
            self.bit_mapping[str(i)] = i  # 默认一一对应，使用字符串键
            self.bit_mapping_enabled[str(i)] = False  # 默认禁用所有映射，使用字符串键

        # 初始化 command_list
        self.command_list = QListWidget()

        self.crc16_label = QLabel("0")

        # 初始化UI
        self.initUI()

        # 初始化串口列表
        self.update_port_list()

    def toggle_stay_on_top(self, window, state):
        """切换窗口置顶状态"""
        if state == Qt.Checked:
            window.setWindowFlags(window.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            window.setWindowFlags(window.windowFlags() & ~Qt.WindowStaysOnTopHint)
        window.show()  # 重新显示窗口以应用更改

    def initUI(self):
        # 设置窗口标题和大小
        self.setWindowTitle("新代测试")
        self.setGeometry(100, 100, 900, 700)
        
        # 自动加载窗口布局
        self.load_window_layout()

        # 创建菜单栏
        self.create_menu_bar()

        # 创建工具栏
        self.create_toolbar()

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)

        # 添加窗口置顶复选框到主布局的顶部
        self.stay_on_top_checkbox_main = QCheckBox('窗口置顶')
        self.stay_on_top_checkbox_main.stateChanged.connect(lambda state: self.toggle_stay_on_top(self, state))
        # 创建一个水平布局来容纳复选框并使其靠右
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addStretch() # 将拉伸添加到复选框之前，使其靠右
        top_bar_layout.addWidget(self.stay_on_top_checkbox_main)

        main_layout.addLayout(top_bar_layout)

        # 串口配置组
        config_group = QGroupBox("串口配置")
        config_layout = QGridLayout(config_group)
        config_layout.setHorizontalSpacing(10)  # 设置水平间距为10像素，使布局更紧凑

        # 串口选择
        config_layout.addWidget(QLabel("串口:"), 0, 0)
        self.port_combo = QComboBox()
        config_layout.addWidget(self.port_combo, 0, 1)

        # 刷新串口按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.update_port_list)
        config_layout.addWidget(self.refresh_btn, 0, 2)

        # 波特率选择
        config_layout.addWidget(QLabel("波特率:"), 0, 3)
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["9600", "115200", "57600", "38400", "19200", "4800",
                                      "2400", "460800", "921600"])
        self.baudrate_combo.setCurrentText("115200")
        config_layout.addWidget(self.baudrate_combo, 0, 4)

        # 数据位选择
        config_layout.addWidget(QLabel("数据位:"), 1, 0)
        self.databits_combo = QComboBox()
        self.databits_combo.addItems(["5", "6", "7", "8"])
        self.databits_combo.setCurrentText("8")
        config_layout.addWidget(self.databits_combo, 1, 1)

        # 停止位选择
        config_layout.addWidget(QLabel("停止位:"), 1, 2)
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.addItems(["1", "1.5", "2"])
        self.stopbits_combo.setCurrentText("1")
        config_layout.addWidget(self.stopbits_combo, 1, 3)

        # 校验位选择
        config_layout.addWidget(QLabel("校验位:"), 1, 4)
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["None", "Odd", "Even", "Mark", "Space"])
        self.parity_combo.setCurrentText("None")
        config_layout.addWidget(self.parity_combo, 1, 5)

        # 流量控制
        config_layout.addWidget(QLabel("流控:"), 0, 5)
        self.flow_combo = QComboBox()
        self.flow_combo.addItems(["None", "RTS/CTS", "XON/XOFF"])
        self.flow_combo.setCurrentText("None")
        config_layout.addWidget(self.flow_combo, 0, 6)

        # 连接按钮
        self.connect_btn = QPushButton("打开串口")
        self.connect_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.connect_btn.clicked.connect(self.toggle_serial)
        config_layout.addWidget(self.connect_btn, 0, 7, 2, 1)

        # 添加配置组到主布局
        main_layout.addWidget(config_group)

        # 创建分割器
        splitter = QSplitter(Qt.Vertical)

        # 接收区组
        receive_group = QGroupBox("接收区")
        receive_layout = QVBoxLayout(receive_group)

        # 接收文本框
        self.receive_text = QTextEdit()
        self.receive_text.setReadOnly(True)
        receive_layout.addWidget(self.receive_text)

        # 接收区工具栏
        recv_tool_layout = QHBoxLayout()

        self.hex_recv_check = QCheckBox("十六进制显示")
        self.hex_recv_check.setChecked(True)
        self.hex_recv_check.stateChanged.connect(self.update_display_mode)
        recv_tool_layout.addWidget(self.hex_recv_check)

        self.timestamp_check = QCheckBox("显示时间戳")
        self.timestamp_check.setChecked(True)
        recv_tool_layout.addWidget(self.timestamp_check)

        self.auto_scroll_check = QCheckBox("自动滚屏")
        self.auto_scroll_check.setChecked(True)
        recv_tool_layout.addWidget(self.auto_scroll_check)

        self.clear_recv_btn = QPushButton("清空接收区")
        self.clear_recv_btn.clicked.connect(self.clear_receive)
        recv_tool_layout.addWidget(self.clear_recv_btn)

        # 保存接收数据按钮
        self.save_recv_btn = QPushButton("保存接收数据")
        self.save_recv_btn.clicked.connect(self.save_receive_data)
        recv_tool_layout.addWidget(self.save_recv_btn)

        receive_layout.addLayout(recv_tool_layout)

        # 接收统计
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("接收字节:"))
        self.rx_count_label = QLabel("0")
        stats_layout.addWidget(self.rx_count_label)
        stats_layout.addStretch()
        stats_layout.addWidget(QLabel("发送字节:"))
        self.tx_count_label = QLabel("0")
        stats_layout.addWidget(self.tx_count_label)
        stats_layout.addStretch()
        self.reset_stats_btn = QPushButton("重置统计")
        self.reset_stats_btn.clicked.connect(self.reset_stats)
        stats_layout.addWidget(self.reset_stats_btn)

        receive_layout.addLayout(stats_layout)

        splitter.addWidget(receive_group)

        # 发送区组
        send_group = QGroupBox("发送区")
        send_layout = QVBoxLayout(send_group)

        # 创建标签页
        self.send_tabs = QTabWidget()

        # 默认发送框
        default_send_widget = QWidget()
        default_send_layout = QVBoxLayout(default_send_widget)

        # 添加映射配置标签页
        mapping_widget = QWidget()
        mapping_layout = QVBoxLayout(mapping_widget)

        # 添加映射规则说明
        rules_group = QGroupBox("映射规则说明")
        rules_layout = QVBoxLayout(rules_group)

        rules_text = (
            "一、PC应用程序到设备数据格式（输出地址控制及其它控制）：\n"
        )
        rules_label = QLabel(rules_text)
        rules_label.setWordWrap(True)
        rules_layout.addWidget(rules_label)
        mapping_layout.addWidget(rules_group)

        # 添加映射配置表格
        mapping_group = QGroupBox("I/O位映射配置")
        mapping_grid = QGridLayout(mapping_group)

        # 添加表头
        mapping_grid.addWidget(QLabel("输入位(I)"), 0, 0)
        mapping_grid.addWidget(QLabel("输出位(O)"), 0, 1)
        mapping_grid.addWidget(QLabel("启用"), 0, 2)

        # 添加映射配置行
        for i in range(192):  # 24字节 * 8位 = 192位 (D0~D23)
            row = i + 1
            byte_num = i // 8
            bit_num = i % 8
            input_label = QLabel(f"I{i} (D{byte_num}.{bit_num})")
            output_spin = QSpinBox()
            output_spin.setObjectName(f"output_spin_{i}")
            output_spin.setRange(0, 191)  # 输出位范围0-191
            output_spin.setValue(self.bit_mapping[str(i)])
            output_spin.setEnabled(self.bit_mapping_enabled[str(i)])  # 设置初始可编辑状态
            output_spin.valueChanged.connect(lambda value, bit=i: self.update_bit_mapping(bit, value))

            # 添加启用/禁用复选框
            enable_check = QCheckBox()
            enable_check.setObjectName(f"enable_check_{i}")
            enable_check.setChecked(self.bit_mapping_enabled[str(i)])
            enable_check.stateChanged.connect(lambda state, bit=i, spin=output_spin: self.toggle_mapping(bit, state == Qt.Checked, spin))

            mapping_grid.addWidget(input_label, row, 0)
            mapping_grid.addWidget(output_spin, row, 1)
            mapping_grid.addWidget(enable_check, row, 2)

        mapping_scroll = QScrollArea()
        mapping_scroll.setWidget(mapping_group)
        mapping_scroll.setWidgetResizable(True)
        mapping_layout.addWidget(mapping_scroll)

        # 添加保存和加载配置按钮
        button_layout = QHBoxLayout()
        save_mapping_btn = QPushButton("保存映射配置")
        save_mapping_btn.clicked.connect(self.save_mapping_config)
        load_mapping_btn = QPushButton("加载映射配置")
        load_mapping_btn.clicked.connect(self.load_mapping_config)
        button_layout.addWidget(save_mapping_btn)
        button_layout.addWidget(load_mapping_btn)
        mapping_layout.addLayout(button_layout)

        ##self.send_tabs.addTab(mapping_widget, "映射配置")

        # 默认发送框

        # 发送文本框和自动生成选项
        send_text_layout = QVBoxLayout()
        text_options_layout = QHBoxLayout()

        self.send_text = QTextEdit()
        self.send_text.setPlainText("A5 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01")
        self.send_text.setMaximumHeight(100)

        self.auto_generate_check = QCheckBox("自动生成指令")
        self.auto_generate_check.setToolTip("选中后将自动显示转换后的数据")
        text_options_layout.addWidget(self.auto_generate_check)
        text_options_layout.addStretch()

        send_text_layout.addWidget(self.send_text)
        send_text_layout.addLayout(text_options_layout)
        default_send_layout.addLayout(send_text_layout)

        # 发送区工具栏
        send_tool_layout = QHBoxLayout()

        self.hex_send_check = QCheckBox("十六进制发送")
        self.hex_send_check.setChecked(True)
        send_tool_layout.addWidget(self.hex_send_check)

        self.crc16_check = QCheckBox("添加CRC16校验位")
        self.crc16_check.setChecked(True)
        send_tool_layout.addWidget(self.crc16_check)

        self.crlf_check = QCheckBox("自动添加换行")
        self.crlf_check.setChecked(False)
        send_tool_layout.addWidget(self.crlf_check)

        # 定时发送
        send_tool_layout.addWidget(QLabel("定时发送(ms):"))
        self.timer_spin = QSpinBox()
        self.timer_spin.setRange(1, 60000)
        self.timer_spin.setValue(1000)
        send_tool_layout.addWidget(self.timer_spin)

        self.timer_btn = QPushButton("开始定时")
        self.timer_btn.setStyleSheet("background-color: #2196F3; color: white;")
        self.timer_btn.clicked.connect(self.toggle_timer)
        send_tool_layout.addWidget(self.timer_btn)

        # 发送按钮
        self.send_btn = QPushButton("发送数据")
        self.send_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.send_btn.clicked.connect(self.send_data)
        send_tool_layout.addWidget(self.send_btn)

        default_send_layout.addLayout(send_tool_layout)

        self.send_tabs.addTab(default_send_widget, "发送区")

        send_layout.addWidget(self.send_tabs)

        splitter.addWidget(send_group)

        # 设置分割器比例
        splitter.setSizes([400, 200])

        # 添加分割器到主布局
        main_layout.addWidget(splitter)

        # 创建状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        # 保存配置
        save_config_action = QAction("保存配置", self)
        save_config_action.triggered.connect(self.save_config)
        file_menu.addAction(save_config_action)

        # 加载配置
        load_config_action = QAction("加载配置", self)
        load_config_action.triggered.connect(self.load_config)
        file_menu.addAction(load_config_action)

        # 退出
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 工具菜单
        tool_menu = menubar.addMenu("工具")

        # 信号检测菜单项
        signal_detection_action = QAction("信号检测", self)
        signal_detection_action.triggered.connect(self.open_signal_detection_window)
        tool_menu.addAction(signal_detection_action)
        
        # 映射配置菜单项
        mapping_config_action = QAction("映射配置", self)
        mapping_config_action.triggered.connect(self.create_mapping_config_window)
        tool_menu.addAction(mapping_config_action)
        
        # 多命令发送菜单项
        multi_command_action = QAction("多命令发送", self)
        multi_command_action.triggered.connect(self.open_multi_command_window)
        tool_menu.addAction(multi_command_action)
        
        # 指令生成菜单项
        command_generator_action = QAction("指令生成", self)
        command_generator_action.triggered.connect(self.open_command_generator_window)
        tool_menu.addAction(command_generator_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        # 关于
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        """创建工具栏"""
        toolbar = self.addToolBar('主工具栏')
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        
        # 可以在这里添加其他工具栏按钮
        pass

    def update_port_list(self):
        """更新串口列表"""
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        current_port = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(port_list)

        # 如果之前选择的端口还在列表中，重新选中它
        if current_port in port_list:
            self.port_combo.setCurrentText(current_port)

    def open_signal_detection_window(self):
        # 创建信号检测窗口类
        class SignalDetectionWindow(QWidget):
            data_received = pyqtSignal(bytes)
            def __init__(self):
                super().__init__()
                self.setWindowTitle('信号检测')
                self.setGeometry(200, 200, 890, 618)
                self.init_ui()
                
            def init_ui(self):
                layout = QVBoxLayout()
                
                # 添加起始字节检测状态
                status_layout = QHBoxLayout()
                self.start_byte_label = QLabel('起始字节(5A)状态：')
                self.start_byte_status = QLabel('未检测到')
                self.start_byte_status.setStyleSheet('color: red')
                status_layout.addWidget(self.start_byte_label)
                status_layout.addWidget(self.start_byte_status)

                layout.addLayout(status_layout)
                
                # 创建表格
                self.table = QTableWidget()
                self.table.setRowCount(24)  # D0-D23
                self.table.setColumnCount(9)  # 8位数据 + 1列字节值
                
                # 设置表头
                headers = ['Bit7', 'Bit6', 'Bit5', 'Bit4', 'Bit3', 'Bit2', 'Bit1', 'Bit0', '字节值(HEX)']
                self.table.setHorizontalHeaderLabels(headers)
                
                # 设置垂直表头（D0-D23）和I标签说明
                v_headers = []
                for i in range(24):
                    v_headers.append(f'D{i} (I{i*8}-I{i*8+7})')
                self.table.setVerticalHeaderLabels(v_headers)
                
                # 初始化表格内容
                for i in range(24):
                    for j in range(9):
                        item = QTableWidgetItem('0')
                        item.setTextAlignment(Qt.AlignCenter)
                        self.table.setItem(i, j, item)
                
                # 设置表格样式
                self.table.setStyleSheet('QTableWidget {gridline-color: #d0d0d0}')
                for i in range(8):
                    self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
                self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Stretch)
                self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
                
                # 自动调整列宽
                self.table.resizeColumnsToContents()
                
                layout.addWidget(self.table)
                self.setLayout(layout)
                self.data_received.connect(self.update_table)
                
            def update_table(self, data):
                if not data:
                    return
                    
                # 检查起始字节
                if data[0] == 0x5A:
                    if self.start_byte_status.text() != '已检测到':
                        self.start_byte_status.setText('已检测到')
                        self.start_byte_status.setStyleSheet('color: green')
                else:
                    if self.start_byte_status.text() != '未检测到':
                        self.start_byte_status.setText('未检测到')
                        self.start_byte_status.setStyleSheet('color: red')
                    return
                
                # 批量更新表格数据，减少重绘次数
                self.table.setUpdatesEnabled(False)  # 暂停更新
                
                for i in range(min(24, len(data)-1)):  # 跳过起始字节5A
                    byte_data = data[i+1]  # 数据从第二个字节开始
                    
                    # 更新8个位的值
                    for j in range(8):
                        bit_value = (byte_data >> (7-j)) & 1  # 从高位到低位
                        current_item = self.table.item(i, j)
                        
                        # 只在值发生变化时更新
                        if current_item is None or current_item.text() != str(bit_value):
                            item = QTableWidgetItem(str(bit_value))
                            item.setTextAlignment(Qt.AlignCenter)
                            if bit_value == 1:
                                item.setBackground(Qt.green)
                            else:
                                item.setBackground(Qt.white)
                            self.table.setItem(i, j, item)
                    
                    # 更新字节值（十六进制）
                    hex_str = f'{byte_data:02X}'
                    current_hex_item = self.table.item(i, 8)
                    if current_hex_item is None or current_hex_item.text() != hex_str:
                        hex_value = QTableWidgetItem(hex_str)
                        hex_value.setTextAlignment(Qt.AlignCenter)
                        self.table.setItem(i, 8, hex_value)
                
                self.table.setUpdatesEnabled(True)  # 恢复更新
                    
        self.signal_detection_window = SignalDetectionWindow()
        
        # 为信号检测窗口添加布局记忆
        self.load_sub_window_layout(self.signal_detection_window, 'signal_detection_window')
        
        # 添加关闭事件处理
        def closeEvent(event):
            self.save_sub_window_layout(self.signal_detection_window, 'signal_detection_window')
            event.accept()
        self.signal_detection_window.closeEvent = closeEvent
        
        self.signal_detection_window.show()
        
        # 连接数据接收信号
        if hasattr(self, 'serial_thread') and self.serial_thread:
            self.serial_thread.data_received.connect(self.signal_detection_window.data_received)

    def toggle_serial(self):
        """打开或关闭串口"""
        if self.ser and self.ser.is_open:
            self.close_serial()
        else:
            self.open_serial()

    def open_serial(self):
        """打开串口"""
        port = self.port_combo.currentText()
        if not port:
            QMessageBox.warning(self, "警告", "请选择串口")
            return

        try:
            baudrate = int(self.baudrate_combo.currentText())
            databits = int(self.databits_combo.currentText())

            # 映射停止位
            stopbits_mapping = {'1': serial.STOPBITS_ONE,
                                '1.5': serial.STOPBITS_ONE_POINT_FIVE,
                                '2': serial.STOPBITS_TWO}
            stopbits = stopbits_mapping.get(self.stopbits_combo.currentText(), serial.STOPBITS_ONE)

            # 映射校验位
            parity_mapping = {'None': serial.PARITY_NONE,
                              'Odd': serial.PARITY_ODD,
                              'Even': serial.PARITY_EVEN,
                              'Mark': serial.PARITY_MARK,
                              'Space': serial.PARITY_SPACE}
            parity = parity_mapping.get(self.parity_combo.currentText(), serial.PARITY_NONE)

            # 映射流控
            rtscts = False
            xonxoff = False
            flow_control = self.flow_combo.currentText()
            if flow_control == "RTS/CTS":
                rtscts = True
            elif flow_control == "XON/XOFF":
                xonxoff = True

            # 打开串口
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=databits,
                parity=parity,
                stopbits=stopbits,
                timeout=1,
                rtscts=rtscts,
                xonxoff=xonxoff
            )

            if self.ser.is_open:
                self.statusBar.showMessage(f"串口 {port} 已打开")
                self.connect_btn.setText("关闭串口")
                self.connect_btn.setStyleSheet("background-color: #f44336; color: white;")

                # 禁用配置控件
                self.port_combo.setEnabled(False)
                self.baudrate_combo.setEnabled(False)
                self.databits_combo.setEnabled(False)
                self.stopbits_combo.setEnabled(False)
                self.parity_combo.setEnabled(False)
                self.flow_combo.setEnabled(False)
                self.refresh_btn.setEnabled(False)

                # 启动读取线程
                self.serial_thread = SerialThread(self.ser)
                self.serial_thread.data_received.connect(self.update_receive_text)
                self.serial_thread.start()
            else:
                self.statusBar.showMessage(f"无法打开串口 {port}")
                QMessageBox.critical(self, "错误", f"无法打开串口 {port}")

        except Exception as e:
            self.statusBar.showMessage(f"打开串口错误: {str(e)}")
            QMessageBox.critical(self, "错误", f"打开串口错误: {str(e)}")

    def close_serial(self):
        """关闭串口"""
        # 停止定时发送
        if self.timer.isActive():
            self.toggle_timer()

        if self.serial_thread and self.serial_thread.isRunning():
            self.serial_thread.stop()
            self.serial_thread = None

        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                self.statusBar.showMessage("串口已关闭")
                self.connect_btn.setText("打开串口")
                self.connect_btn.setStyleSheet("background-color: #4CAF50; color: white;")

                # 启用配置控件
                self.port_combo.setEnabled(True)
                self.baudrate_combo.setEnabled(True)
                self.databits_combo.setEnabled(True)
                self.stopbits_combo.setEnabled(True)
                self.parity_combo.setEnabled(True)
                self.flow_combo.setEnabled(True)
                self.refresh_btn.setEnabled(True)
            except Exception as e:
                self.statusBar.showMessage(f"关闭串口错误: {str(e)}")

    def create_mapping_config_window(self):
        """创建映射配置窗口"""
        self.mapping_window = QWidget()
        self.mapping_window.setWindowTitle('映射配置')
        self.mapping_window.setGeometry(100, 100, 1000, 600) # Increased width for the new list
        
        # 为映射配置窗口添加布局记忆
        self.load_sub_window_layout(self.mapping_window, 'mapping_window')

        # 创建置顶复选框
        self.stay_on_top_checkbox_mapping = QCheckBox('窗口置顶')
        self.stay_on_top_checkbox_mapping.stateChanged.connect(
            lambda state: self.toggle_stay_on_top(self.mapping_window, state)
        )
        # 创建一个顶部栏布局来放置置顶复选框
        top_bar_mapping_layout = QHBoxLayout()
        top_bar_mapping_layout.addStretch() # 将拉伸添加到复选框之前，使其靠右
        top_bar_mapping_layout.addWidget(self.stay_on_top_checkbox_mapping)


        # 主布局，先添加顶部栏，再添加原来的左右分栏
        overall_main_layout = QVBoxLayout(self.mapping_window) # Set this as the main layout for mapping_window
        overall_main_layout.addLayout(top_bar_mapping_layout)

        main_horizontal_layout = QHBoxLayout() # This will be added to overall_main_layout
        overall_main_layout.addLayout(main_horizontal_layout)

        left_column_layout = QVBoxLayout()
        right_column_layout = QVBoxLayout()

        # Right column for enabled mappings list
        enabled_header_layout = QHBoxLayout()
        enabled_header_layout.addWidget(QLabel('已启用映射:'))
        
        # 添加更新按钮
        refresh_btn = QPushButton('🔄')
        refresh_btn.setToolTip('手动更新启用映射列表')
        refresh_btn.setMaximumWidth(30)
        refresh_btn.clicked.connect(self.update_enabled_mappings_list)
        enabled_header_layout.addWidget(refresh_btn)
        
        right_column_layout.addLayout(enabled_header_layout)
        self.enabled_mappings_list = QListWidget()
        right_column_layout.addWidget(self.enabled_mappings_list)

        main_horizontal_layout.addLayout(left_column_layout, 2) # Give more space to left column
        main_horizontal_layout.addLayout(right_column_layout, 1)

        # self.mapping_window.setLayout(main_horizontal_layout) # overall_main_layout is already set

        # Original layout for mapping configuration will go into the left_column_layout
        layout = QVBoxLayout() # This 'layout' is now for the left part
        left_column_layout.addLayout(layout)
        
        # 添加说明标签
        desc_label = QLabel('配置数据映射规则：')
        layout.addWidget(desc_label)
        
        # 创建映射内容区域
        mapping_content_widget = QWidget()
        self.mapping_grid_layout = QGridLayout(mapping_content_widget)
        self.mapping_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.mapping_grid_layout.setSpacing(10)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(mapping_content_widget)
        layout.addWidget(scroll_area)

        # 初始化映射项
        for i in range(192):
            # 创建单个映射项的布局
            item_layout = QHBoxLayout()
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(5)

            # 输入位
            input_label = QLabel(f'I{i}')
            input_label.setFixedWidth(50) # Increased width for longer text
            item_layout.addWidget(input_label)

            # 输出位
            output_spin = QSpinBox()
            output_spin.setRange(0, 191)
            output_spin.setValue(i)
            output_spin.valueChanged.connect(lambda v, row=i: self.update_mapping(row, v))
            output_spin.setFixedWidth(50)
            item_layout.addWidget(output_spin)

            # 启用复选框
            enable_check = QCheckBox('启用')
            enable_check.setChecked(False)
            enable_check.stateChanged.connect(lambda state, row=i: (
                self.toggle_mapping(row, state),
                self.update_enabled_mappings_list()
            ))
            item_layout.addWidget(enable_check)

            # 当前值
            value_label = QLabel('0')
            value_label.setFixedWidth(30)
            value_label.setAlignment(Qt.AlignCenter)
            item_layout.addWidget(value_label)

            # 将映射项添加到网格布局中
            col = (i % 2) * 4  # 两列，每列4个控件
            row = i // 2
            self.mapping_grid_layout.addLayout(item_layout, row, col, 1, 4) # 跨4列以容纳所有控件

        # 存储对当前值标签的引用，以便后续更新
        self.mapping_value_labels = []
        for i in range(192):
            # 找到对应的QLabel
            label = self.mapping_grid_layout.itemAtPosition(i // 2, (i % 2) * 4 + 3).widget()
            self.mapping_value_labels.append(label)

        
        # 添加定时发送控制
        timer_group = QGroupBox('定时发送设置')
        timer_layout = QHBoxLayout()
        
        self._is_auto_sending = False  # Track auto send state
        self.timer_enable_btn = QPushButton('启用定时发送')
        self.timer_enable_btn.setStyleSheet('background-color: red; color: white;')
        self.timer_enable_btn.clicked.connect(self.toggle_auto_send_status)

        
        self.timer_interval = QSpinBox()
        self.timer_interval.setRange(1, 10000)  # 100ms到10s
        self.timer_interval.setValue(1000)  # 默认1秒
        self.timer_interval.setSuffix('ms')
        
        timer_layout.addWidget(self.timer_enable_btn)
        timer_layout.addWidget(QLabel('发送间隔：'))
        timer_layout.addWidget(self.timer_interval)
        timer_layout.addStretch()
        
        timer_group.setLayout(timer_layout)
        layout.addWidget(timer_group)
        
        # 添加按钮组
        button_layout = QHBoxLayout()
        save_btn = QPushButton('保存配置')
        load_btn = QPushButton('加载配置')
        save_btn.clicked.connect(self.save_mapping_config)
        load_btn.clicked.connect(self.load_mapping_config)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(load_btn)
        layout.addLayout(button_layout)
        
        # self.mapping_window.setLayout(layout) # Main layout is already set
        
        # 添加关闭事件处理
        def closeEvent(event):
            self.save_sub_window_layout(self.mapping_window, 'mapping_window')
            event.accept()
        self.mapping_window.closeEvent = closeEvent
        
        self.mapping_window.show()
        
    def update_mapping(self, input_bit, output_bit):
        """更新位映射配置"""
        self.bit_mapping[str(input_bit)] = output_bit

    def update_bit_mapping(self, bit, value):
        """更新位映射配置并刷新已启用列表"""
        self.bit_mapping[str(bit)] = value
        # 如果该位已启用，更新已启用映射列表
        if self.bit_mapping_enabled.get(str(bit), False):
            self.update_enabled_mappings_list()

    def toggle_mapping(self, bit, enabled, spin_box=None):
        """切换映射启用状态"""
        self.bit_mapping_enabled[str(bit)] = enabled
        if spin_box:
            spin_box.setEnabled(enabled)
        # 更新已启用映射列表
        self.update_enabled_mappings_list()

    def update_enabled_mappings_list(self):
        """更新已启用映射列表"""
        if not hasattr(self, 'enabled_mappings_list'): # Ensure the list widget exists
            return
        self.enabled_mappings_list.clear()
        for bit, enabled in self.bit_mapping_enabled.items():
            if enabled:
                # Find the corresponding output bit from self.bit_mapping
                output_bit = self.bit_mapping.get(str(bit), bit) # Default to input bit if not found
                self.enabled_mappings_list.addItem(f'I{bit} -> O{output_bit}')
        
    def toggle_auto_send_status(self):
        """切换定时发送按钮状态并执行相应操作"""
        self._is_auto_sending = not self._is_auto_sending
        self.update_auto_send_button_style()
        self.perform_auto_send_action()

    def update_auto_send_button_style(self):
        """更新定时发送按钮的文本和样式"""
        if self._is_auto_sending:
            self.timer_enable_btn.setText('禁用定时发送')
            self.timer_enable_btn.setStyleSheet('background-color: green; color: white;')
        else:
            self.timer_enable_btn.setText('启用定时发送')
            self.timer_enable_btn.setStyleSheet('background-color: red; color: white;')

    def perform_auto_send_action(self):
        """根据当前状态启动或停止定时发送"""
        if self._is_auto_sending:
            # 启动定时器
            interval = self.timer_interval.value()
            if not hasattr(self, 'send_timer') or not self.send_timer:
                self.send_timer = QTimer(self)
                self.send_timer.timeout.connect(self.auto_send_data)
            self.send_timer.start(interval)
        else:
            # 停止定时器
            if hasattr(self, 'send_timer') and self.send_timer:
                self.send_timer.stop()
                
    def auto_send_data(self):
        """定时发送数据"""
        if hasattr(self, 'last_received_data') and self.last_received_data:
            # 处理数据并发送
            processed_data = self.convert_data(self.last_received_data)
            if processed_data:
                self.ser.write(processed_data)
                # 更新映射表格中的当前值
                self.update_mapping_values(processed_data)

    def save_mapping_config(self):
        """保存映射配置到文件"""
        file_name, _ = QFileDialog.getSaveFileName(self, "保存映射配置", "", "JSON文件 (*.json)")
        if file_name:
            import json
            try:
                config = {
                    'mapping': self.bit_mapping,
                    'enabled': self.bit_mapping_enabled
                }
                with open(file_name, 'w') as f:
                    json.dump(config, f)
                QMessageBox.information(self, "成功", "映射配置已保存")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")

    def load_mapping_config(self):
        """从文件加载映射配置"""
        file_name, _ = QFileDialog.getOpenFileName(self, "加载映射配置", "", "JSON文件 (*.json)")
        if file_name:
            import json
            try:
                with open(file_name, 'r') as f:
                    config = json.load(f)
                    self.bit_mapping = config.get('mapping', {})
                    self.bit_mapping_enabled = config.get('enabled', {})

                # 更新UI
                for i in range(192):
                    row = i + 1
                    # 更新SpinBox的值
                    spin_box = self.findChild(QSpinBox, f"output_spin_{i}")
                    if spin_box:
                        spin_box.setValue(self.bit_mapping.get(str(i), i))
                    # 更新CheckBox的状态
                    check_box = self.findChild(QCheckBox, f"enable_check_{i}")
                    if check_box:
                        check_box.setChecked(self.bit_mapping_enabled.get(str(i), True))

                QMessageBox.information(self, "成功", "映射配置已加载")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载配置失败: {str(e)}")

    def convert_data(self, input_data):
        """根据映射配置转换数据"""
        if len(input_data) == 0:
            return bytearray()

        # 创建输出数据，第一个字节为A5
        output_data = bytearray([0xA5])

        # 处理剩余字节
        remaining_data = input_data[1:]

        # 将输入数据转换为位列表
        input_bits = []
        for byte_index, byte in enumerate(remaining_data):
            for bit_index in range(8):
                # 计算全局位索引（从左到右递增）
                global_bit_index = byte_index * 8 + (7 - bit_index)
                input_bits.append((byte >> (7 - bit_index)) & 1)

        # 创建输出字节列表（24个字节，对应D0-D23）
        output_bytes = [0] * 24

        # 根据映射关系设置输出字节的位值
        for input_pos, output_pos in self.bit_mapping.items():
            if isinstance(input_pos, str):
                input_pos = int(input_pos)
            if isinstance(output_pos, str):
                output_pos = int(output_pos)

            # 确保输入位在有效范围内
            if (input_pos < len(input_bits) and
                self.bit_mapping_enabled.get(str(input_pos), True)):
                # 计算对应的字节索引和位索引
                byte_index = output_pos // 8
                bit_index = output_pos % 8
                
                # 如果字节索引在有效范围内
                if 0 <= byte_index < 24:
                    # 设置对应位的值
                    if input_pos < len(input_bits):
                        if input_bits[input_pos] == 1:
                            output_bytes[byte_index] |= (1 << (7 - bit_index))
                        else:
                            output_bytes[byte_index] &= ~(1 << (7 - bit_index))

        # 将输出字节添加到输出数据中
        output_data.extend(output_bytes)

        # 添加测试状态字节（B24）
        output_data.append(0x01)

        # 计算并添加CRC16校验（C25-C26）
        crc = self.crc16(output_data)
        output_data.extend([crc >> 8, crc & 0xFF])

        return output_data

    def update_mapping_values(self, data):
        """更新映射表格中的当前值"""
        if not hasattr(self, 'mapping_table'):
            return
            
        # 将数据转换为位列表
        bits = []
        for byte in data[1:]:  # 跳过起始字节
            for i in range(8):
                bits.append((byte >> (7-i)) & 1)
                
        # 更新表格中的当前值
        for i in range(min(len(bits), 192)):
            value_item = self.mapping_table.item(i, 3)
            if value_item:
                value_item.setText(str(bits[i]))
                if bits[i] == 1:
                    value_item.setBackground(Qt.green)
                else:
                    value_item.setBackground(Qt.white)
    
    def update_receive_text(self, data):
        """更新接收文本框"""
        # 保存最后接收到的数据用于定时发送
        self.last_received_data = data
        
        # 更新接收计数
        self.rx_count += len(data)
        self.rx_count_label.setText(str(self.rx_count))

        # 添加时间戳和标记
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        if self.hex_recv_check.isChecked():
            # 十六进制显示
            hex_list = [f"{byte:02X}" for byte in data]
            # 构建带时间戳的完整HTML文本
            html_text = f"[{timestamp}] [接收] "
            for hex_byte in hex_list:
                if hex_byte == "5A":
                    html_text += f'<span style="color: green;">{hex_byte}</span> '
                elif hex_byte == "EB":
                    html_text += f'<span style="color: red;">{hex_byte}</span> '
                else:
                    html_text += f"{hex_byte} "
            html_text += "<br>"
            
            # 更新显示
            self.receive_text.moveCursor(QTextCursor.End)
            self.receive_text.insertHtml(html_text)
        else:
            # 字符串显示
            try:
                text = data.decode('utf-8', errors='replace')
            except:
                text = str(data)
            
            text = f"[{timestamp}] [接收] {text}\n"
            
            # 更新显示
            self.receive_text.moveCursor(QTextCursor.End)
            self.receive_text.insertPlainText(text)

        # 自动滚屏
        if self.auto_scroll_check.isChecked():
            self.receive_text.moveCursor(QTextCursor.End)

    def update_display_mode(self):
        """更新显示模式"""
        # 清空接收区以应用新的显示模式
        if not self.receive_text.toPlainText().strip():
            return

        # 询问用户是否清空接收区
        reply = QMessageBox.question(self, '确认',
                                     '切换显示模式将清空接收区，是否继续？',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.clear_receive()

    def clear_receive(self):
        """清空接收区"""
        self.receive_text.clear()

    def crc16(self, data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return ((crc & 0xFF) << 8) | ((crc >> 8) & 0xFF)

    def send_data(self):
        logging.basicConfig(level=logging.DEBUG)
        logging.debug('开始执行 send_data 方法')
        """发送数据"""
        if not self.ser or not self.ser.is_open:
            QMessageBox.warning(self, "警告", "串口未打开")
            return

        # 获取当前标签页的内容
        current_index = self.send_tabs.currentIndex()

        if current_index == 0:  # 默认发送区
            if self.auto_generate_check.isChecked():
                # 如果选中了自动生成，使用接收到的数据进行转换
                text = self.receive_text.toPlainText().strip()
                if not text:
                    QMessageBox.warning(self, "警告", "接收区没有数据")
                    return
                # 获取最后一次接收到的数据
                lines = text.split('\n')
                for line in reversed(lines):
                    if '[接收]' in line:
                        # 提取十六进制数据
                        hex_data = ''.join(c for c in line if c.isalnum())
                        try:
                            input_data = bytes.fromhex(hex_data)
                            converted_data = self.convert_data(input_data)
                            text = converted_data.hex().upper()
                            # 更新输入框显示
                            self.send_text.setPlainText(text)
                            break
                        except ValueError:
                            continue
                else:
                    QMessageBox.warning(self, "警告", "没有找到有效的接收数据")
                    return
            else:
                # 使用用户输入的数据
                text = self.send_text.toPlainText().strip()
                if not text:
                    return

            # 保存到历史记录
            self.save_to_history(text)

            try:
                logging.debug('开始处理十六进制发送')
                # 处理十六进制发送
                if self.hex_send_check.isChecked():
                    # 移除空格并转换为字节
                    hex_text = text.replace(' ', '')
                    data = bytes.fromhex(hex_text)
                    # 根据复选框状态计算CRC16
                    if self.crc16_check.isChecked():
                        crc = self.crc16(data)
                        crc_bytes = crc.to_bytes(2, byteorder='little')
                        data += crc_bytes
                        print(data)
                        text = data.hex().upper()
                        self.crc16_label.setText(f"CRC16: {crc:04X}")
                else:
                    # 普通文本发送
                    # 根据复选框状态计算CRC16
                    if self.crc16_check.isChecked():
                        crc = self.crc16(text.encode('utf-8'))
                        crc_bytes = crc.to_bytes(2, byteorder='little')
                        data = text.encode('utf-8') + crc_bytes
                        self.crc16_label.setText(f"CRC16: {crc:04X}")
                    else:
                        data = text.encode('utf-8')

                # 添加换行符
                if self.crlf_check.isChecked():
                    data += b'\r\n'

                # 发送数据前打印要发送的数据
                print(f"即将发送的数据: {data}")
                # 发送数据
                self.ser.write(data)

                # 更新状态栏
                self.statusBar.showMessage(f"已发送 {len(data)} 字节")

                # 更新发送计数
                self.tx_count += len(data)
                self.tx_count_label.setText(str(self.tx_count))

                # 回显发送内容
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self.receive_text.moveCursor(QTextCursor.End)
                self.receive_text.insertPlainText(f"[{timestamp}] [发送] {text}\r\n")

                # 自动滚屏
                if self.auto_scroll_check.isChecked():
                    self.receive_text.moveCursor(QTextCursor.End)

            except Exception as e:
                logging.error(f'发送数据时出现异常: {str(e)}')
                self.statusBar.showMessage(f'发送数据错误: {str(e)}')
                QMessageBox.critical(self, '错误', f'发送数据错误: {str(e)}')

    def save_to_history(self, text):
        """保存发送内容到历史记录"""
        if text and (not self.send_history or self.send_history[-1] != text):
            self.send_history.append(text)
            self.history_index = len(self.send_history)

    def toggle_timer(self):
        """开始或停止定时发送"""
        try:
            # 检查串口状态
            if not self.ser or not self.ser.is_open:
                QMessageBox.warning(self, "警告", "请先打开串口")
                return
                
            if self.timer.isActive():
                self.timer.stop()
                self.timer_btn.setText("开始定时")
                self.timer_btn.setStyleSheet("background-color: #2196F3; color: white;")
                self.statusBar.showMessage("定时发送已停止")
            else:
                interval = self.timer_spin.value()
                self.timer.start(interval)
                self.timer_btn.setText("停止定时")
                self.timer_btn.setStyleSheet("background-color: #f44336; color: white;")
                self.statusBar.showMessage(f"定时发送已启动，间隔 {interval}ms")
        except Exception as e:
            import logging
            logging.error(f'定时发送功能出错: {str(e)}')
            self.statusBar().showMessage(f'定时发送出错: {str(e)}')

    def timer_send(self):
        """定时发送数据"""
        if not self.ser or not self.ser.is_open:
            self.statusBar.showMessage("串口未打开")
            self.toggle_timer()
            return
            
        try:
            # 获取当前标签页的内容
            current_index = self.send_tabs.currentIndex()
            
            if current_index == 0:  # 默认发送区
                text = self.send_text.toPlainText().strip()
                if not text:
                    self.statusBar.showMessage("发送内容为空，已停止定时发送")
                    self.toggle_timer()
                    return
                    
                # 处理十六进制发送
                if self.hex_send_check.isChecked():
                    # 移除空格并转换为字节
                    hex_text = text.replace(' ', '')
                    try:
                        data = bytes.fromhex(hex_text)
                    except ValueError:
                        self.statusBar.showMessage("请输入有效的十六进制字符串")
                        self.toggle_timer()
                        return
                else:
                    # 普通文本发送
                    data = text.encode('utf-8')
                
                # 如果启用了映射配置，处理数据
                if hasattr(self, 'mapping_window') and self.mapping_window.timer_enable.isChecked():
                    data = self.convert_data(data)
                
                # 添加CRC16校验
                if self.crc16_check.isChecked():
                    crc = self.crc16(data)
                    data += crc.to_bytes(2, byteorder='little')
                
                # 添加换行符
                if self.crlf_check.isChecked():
                    data += b'\r\n'
                
                # 发送数据
                self.ser.write(data)
                
                # 更新发送计数
                self.tx_count += len(data)
                self.tx_count_label.setText(str(self.tx_count))
                
                # 更新映射表格中的当前值
                if hasattr(self, 'mapping_window'):
                    self.update_mapping_values(data)
                
        except Exception as e:
            self.statusBar.showMessage(f"定时发送错误: {str(e)}")
            self.toggle_timer()

    def add_command(self):
        """添加命令到命令列表"""
        text, ok = QMessageBox.getText(self, '添加命令', '输入要添加的命令:')
        if ok and text:
            self.command_list.addItem(text)

    def remove_command(self):
        """从命令列表中删除选中的命令"""
        current_item = self.command_list.currentItem()
        if current_item:
            row = self.command_list.row(current_item)
            self.command_list.takeItem(row)

    def example_tool_function(self):
        """示例工具函数"""
        QMessageBox.information(self, "示例工具", "这是一个示例工具的功能。")

    def send_selected_command(self):
        """发送选中的命令"""
        current_item = self.command_list.currentItem()
        if current_item:
            text = current_item.text()
            if text:
                try:
                    # 处理十六进制发送
                    if self.hex_send_check.isChecked():
                        # 移除空格并转换为字节
                        hex_text = text.replace(' ', '')
                        data = bytes.fromhex(hex_text)
                    else:
                        # 普通文本发送
                        data = text.encode('utf-8')

                    # 添加换行符
                    if self.crlf_check.isChecked():
                        data += b'\r\n'

                    # 发送数据
                    self.ser.write(data)

                    # 更新状态栏
                    self.statusBar.showMessage(f"已发送命令: {text}")

                    # 更新发送计数
                    self.tx_count += len(data)
                    self.tx_count_label.setText(str(self.tx_count))

                    # 回显发送内容
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    self.receive_text.moveCursor(QTextCursor.End)
                    self.receive_text.insertPlainText(f"[{timestamp}] [发送] {text}\r\n")

                    # 自动滚屏
                    if self.auto_scroll_check.isChecked():
                        self.receive_text.moveCursor(QTextCursor.End)

                except Exception as e:
                    self.statusBar.showMessage(f"发送命令错误: {str(e)}")
                    QMessageBox.critical(self, "错误", f"发送命令错误: {str(e)}")

    def save_receive_data(self):
        """保存接收数据到文件"""
        text = self.receive_text.toPlainText()
        if not text:
            QMessageBox.information(self, "提示", "接收区没有数据可保存")
            return

        filename, _ = QFileDialog.getSaveFileName(self, "保存接收数据", "", "文本文件 (*.txt);;所有文件 (*)")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(text)
                QMessageBox.information(self, "成功", f"数据已保存到 {filename}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存文件错误: {str(e)}")

    def save_config(self):
        """保存配置"""
        filename, _ = QFileDialog.getSaveFileName(self, "保存配置", "", "配置文件 (*.ini);;所有文件 (*)")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"port={self.port_combo.currentText()}\n")
                    f.write(f"baudrate={self.baudrate_combo.currentText()}\n")
                    f.write(f"databits={self.databits_combo.currentText()}\n")
                    f.write(f"stopbits={self.stopbits_combo.currentText()}\n")
                    f.write(f"parity={self.parity_combo.currentText()}\n")
                    f.write(f"flow={self.flow_combo.currentText()}\n")
                    f.write(f"hex_recv={1 if self.hex_recv_check.isChecked() else 0}\n")
                    f.write(f"timestamp={1 if self.timestamp_check.isChecked() else 0}\n")
                    f.write(f"auto_scroll={1 if self.auto_scroll_check.isChecked() else 0}\n")
                    f.write(f"hex_send={1 if self.hex_send_check.isChecked() else 0}\n")
                    f.write(f"crlf={1 if self.crlf_check.isChecked() else 0}\n")
                    f.write(f"timer_interval={self.timer_spin.value()}\n")
                    
                    # 保存窗口布局
                    geometry = self.geometry()
                    f.write(f"window_x={geometry.x()}\n")
                    f.write(f"window_y={geometry.y()}\n")
                    f.write(f"window_width={geometry.width()}\n")
                    f.write(f"window_height={geometry.height()}\n")
                    f.write(f"window_maximized={1 if self.isMaximized() else 0}\n")

                    # 保存命令列表
                    f.write("[commands]\n")
                    for i in range(self.command_list.count()):
                        f.write(f"{self.command_list.item(i).text()}\n")

                QMessageBox.information(self, "成功", f"配置已保存到 {filename}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存配置错误: {str(e)}")

    def load_config(self):
        """加载配置"""
        filename, _ = QFileDialog.getOpenFileName(self, "加载配置", "", "配置文件 (*.ini);;所有文件 (*)")
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                config = {}
                commands_section = False
                commands = []

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith('[') and line.endswith(']'):
                        if line == '[commands]':
                            commands_section = True
                        else:
                            commands_section = False
                        continue

                    if commands_section:
                        commands.append(line)
                    else:
                        key, value = line.split('=', 1)
                        config[key] = value

                # 应用配置
                if 'port' in config and config['port'] in [self.port_combo.itemText(i) for i in
                                                           range(self.port_combo.count())]:
                    self.port_combo.setCurrentText(config['port'])

                if 'baudrate' in config and config['baudrate'] in [self.baudrate_combo.itemText(i) for i in
                                                                   range(self.baudrate_combo.count())]:
                    self.baudrate_combo.setCurrentText(config['baudrate'])

                if 'databits' in config and config['databits'] in [self.databits_combo.itemText(i) for i in
                                                                   range(self.databits_combo.count())]:
                    self.databits_combo.setCurrentText(config['databits'])

                if 'stopbits' in config and config['stopbits'] in [self.stopbits_combo.itemText(i) for i in
                                                                   range(self.stopbits_combo.count())]:
                    self.stopbits_combo.setCurrentText(config['stopbits'])

                if 'parity' in config and config['parity'] in [self.parity_combo.itemText(i) for i in
                                                               range(self.parity_combo.count())]:
                    self.parity_combo.setCurrentText(config['parity'])

                if 'flow' in config and config['flow'] in [self.flow_combo.itemText(i) for i in
                                                           range(self.flow_combo.count())]:
                    self.flow_combo.setCurrentText(config['flow'])

                if 'hex_recv' in config:
                    self.hex_recv_check.setChecked(config['hex_recv'] == '1')

                if 'timestamp' in config:
                    self.timestamp_check.setChecked(config['timestamp'] == '1')

                if 'auto_scroll' in config:
                    self.auto_scroll_check.setChecked(config['auto_scroll'] == '1')

                if 'hex_send' in config:
                    self.hex_send_check.setChecked(config['hex_send'] == '1')

                if 'crlf' in config:
                    self.crlf_check.setChecked(config['crlf'] == '1')

                if 'timer_interval' in config:
                    try:
                        self.timer_spin.setValue(int(config['timer_interval']))
                    except:
                        pass

                # 加载窗口布局
                if all(key in config for key in ['window_x', 'window_y', 'window_width', 'window_height']):
                    try:
                        x = int(config['window_x'])
                        y = int(config['window_y'])
                        width = int(config['window_width'])
                        height = int(config['window_height'])
                        self.setGeometry(x, y, width, height)
                        
                        if 'window_maximized' in config and config['window_maximized'] == '1':
                            self.showMaximized()
                    except ValueError:
                        pass  # 如果转换失败，保持默认窗口大小

                # 加载命令列表
                self.command_list.clear()
                for cmd in commands:
                    self.command_list.addItem(cmd)

                QMessageBox.information(self, "成功", f"配置已从 {filename} 加载")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载配置错误: {str(e)}")

    def reset_stats(self):
        """重置统计数据"""
        self.rx_count = 0
        self.tx_count = 0
        self.rx_count_label.setText("0")
        self.tx_count_label.setText("0")
        self.statusBar.showMessage("统计数据已重置")

    def open_multi_command_window(self):
        """打开多命令发送独立窗口"""
        # 创建多命令发送窗口
        self.multi_command_window = QWidget()
        self.multi_command_window.setWindowTitle('多命令发送')
        self.multi_command_window.setGeometry(200, 200, 800, 600)
        
        # 创建主布局
        layout = QVBoxLayout()
        
        # 创建命令管理区域
        command_group = QGroupBox("命令管理")
        command_layout = QVBoxLayout(command_group)
        
        # 创建命令表格
        self.command_table = QTableWidget()
        self.command_table.setColumnCount(3)
        self.command_table.setHorizontalHeaderLabels(["命令内容", "间隔(ms)", "启用"])
        
        # 设置列宽
        self.command_table.setColumnWidth(0, 500)  # 命令内容列（更宽）
        self.command_table.setColumnWidth(1, 80)   # 间隔列
        self.command_table.setColumnWidth(2, 60)   # 启用列
        
        # 设置列的调整模式
        self.command_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.command_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.command_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        command_layout.addWidget(self.command_table)
        
        # 命令操作按钮
        button_layout = QHBoxLayout()
        
        self.add_cmd_btn = QPushButton("添加命令")
        self.add_cmd_btn.clicked.connect(self.add_multi_command)
        button_layout.addWidget(self.add_cmd_btn)
        
        self.remove_cmd_btn = QPushButton("删除命令")
        self.remove_cmd_btn.clicked.connect(self.remove_multi_command)
        button_layout.addWidget(self.remove_cmd_btn)
        
        self.clear_cmd_btn = QPushButton("清空命令")
        self.clear_cmd_btn.clicked.connect(self.clear_multi_commands)
        button_layout.addWidget(self.clear_cmd_btn)
        
        # 添加保存和导入按钮
        self.save_cmd_btn = QPushButton("保存命令")
        self.save_cmd_btn.clicked.connect(self.save_multi_commands)
        button_layout.addWidget(self.save_cmd_btn)
        
        self.import_cmd_btn = QPushButton("导入命令")
        self.import_cmd_btn.clicked.connect(self.import_multi_commands)
        button_layout.addWidget(self.import_cmd_btn)
        
        button_layout.addStretch()
        command_layout.addLayout(button_layout)
        layout.addWidget(command_group)
        
        # 创建发送控制区域
        control_group = QGroupBox("发送控制")
        control_layout = QHBoxLayout(control_group)
        
        control_layout.addWidget(QLabel("总循环间隔:"))
        self.cycle_interval_spin = QSpinBox()
        self.cycle_interval_spin.setRange(1, 60000)
        self.cycle_interval_spin.setValue(1000)
        self.cycle_interval_spin.setSuffix(" ms")
        control_layout.addWidget(self.cycle_interval_spin)
        
        control_layout.addStretch()
        
        self.start_multi_btn = QPushButton("开始发送")
        self.start_multi_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.start_multi_btn.clicked.connect(self.start_multi_command_send)
        control_layout.addWidget(self.start_multi_btn)
        
        self.stop_multi_btn = QPushButton("停止发送")
        self.stop_multi_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.stop_multi_btn.clicked.connect(self.stop_multi_command_send)
        control_layout.addWidget(self.stop_multi_btn)
        
        layout.addWidget(control_group)
        
        # 创建选项区域
        options_group = QGroupBox("发送选项")
        options_layout = QHBoxLayout(options_group)
        
        self.multi_hex_check = QCheckBox("十六进制发送")
        self.multi_hex_check.setChecked(True)  # 默认勾选
        options_layout.addWidget(self.multi_hex_check)
        
        self.multi_crc_check = QCheckBox("自动添加CRC16")
        self.multi_crc_check.setChecked(True)  # 默认勾选
        options_layout.addWidget(self.multi_crc_check)
        
        self.multi_crlf_check = QCheckBox("添加换行符")
        options_layout.addWidget(self.multi_crlf_check)
        
        options_layout.addStretch()
        layout.addWidget(options_group)
        
        self.multi_command_window.setLayout(layout)
        
        # 初始化多命令发送定时器
        self.multi_command_timer = QTimer()
        self.multi_command_timer.timeout.connect(self.send_next_multi_command)
        self.current_command_index = 0
        
        # 为多命令发送窗口添加布局记忆
        self.load_sub_window_layout(self.multi_command_window, 'multi_command_window')
        
        # 添加关闭事件处理
        def closeEvent(event):
            self.save_sub_window_layout(self.multi_command_window, 'multi_command_window')
            event.accept()
        self.multi_command_window.closeEvent = closeEvent
        
        # 显示窗口
        self.multi_command_window.show()
    
    def add_multi_command(self):
        """添加多命令"""
        text, ok = QInputDialog.getMultiLineText(self.multi_command_window, '添加命令', '输入要添加的命令:')
        if ok and text:
            row_count = self.command_table.rowCount()
            self.command_table.insertRow(row_count)
            
            # 命令内容
            self.command_table.setItem(row_count, 0, QTableWidgetItem(text))
            # 间隔时间
            interval_item = QTableWidgetItem("1000")
            self.command_table.setItem(row_count, 1, interval_item)
            # 启用状态
            enable_check = QCheckBox()
            enable_check.setChecked(True)
            
            # 创建一个容器widget来居中显示复选框
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(enable_check)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            
            self.command_table.setCellWidget(row_count, 2, checkbox_widget)
    
    def remove_multi_command(self):
        """删除选中的多命令"""
        current_row = self.command_table.currentRow()
        if current_row >= 0:
            self.command_table.removeRow(current_row)
    
    def clear_multi_commands(self):
        """清空所有多命令"""
        self.command_table.setRowCount(0)
    
    def start_multi_command_send(self):
        """开始多命令发送"""
        if not self.ser or not self.ser.is_open:
            QMessageBox.warning(self, "警告", "请先打开串口")
            return
        
        if self.command_table.rowCount() == 0:
            QMessageBox.warning(self, "警告", "请先添加命令")
            return
        
        self.current_command_index = 0
        interval = self.cycle_interval_spin.value()
        self.multi_command_timer.start(interval)
        
        self.start_multi_btn.setEnabled(False)
        self.stop_multi_btn.setEnabled(True)
        
        self.statusBar.showMessage("多命令发送已开始")
    
    def stop_multi_command_send(self):
        """停止多命令发送"""
        self.multi_command_timer.stop()
        
        self.start_multi_btn.setEnabled(True)
        self.stop_multi_btn.setEnabled(False)
        
        self.statusBar.showMessage("多命令发送已停止")
    
    def send_next_multi_command(self):
        """发送下一个多命令"""
        if self.command_table.rowCount() == 0:
            self.stop_multi_command_send()
            return
        
        # 查找下一个启用的命令
        start_index = self.current_command_index
        checked_count = 0
        
        while checked_count < self.command_table.rowCount():
            if self.current_command_index >= self.command_table.rowCount():
                self.current_command_index = 0
            
            # 检查当前命令是否启用
            enable_widget = self.command_table.cellWidget(self.current_command_index, 2)
            if enable_widget:
                 # 从容器widget中获取复选框
                 checkbox = enable_widget.findChild(QCheckBox)
                 if checkbox and checkbox.isChecked():
                     # 发送当前命令
                     command_item = self.command_table.item(self.current_command_index, 0)
                     if command_item:
                         command_text = command_item.text()
                         self.send_multi_command_data(command_text)
                     # 移动到下一个命令准备下次发送
                     self.current_command_index += 1
                     return
            
            self.current_command_index += 1
            checked_count += 1
        
        # 如果遍历了所有命令都没有启用的，停止发送
        self.stop_multi_command_send()
        QMessageBox.information(self, "提示", "没有启用的命令")
    
    def send_multi_command_data(self, command_text):
        """发送多命令数据"""
        try:
            # 处理十六进制发送
            if self.multi_hex_check.isChecked():
                hex_text = command_text.replace(' ', '')
                data = bytes.fromhex(hex_text)
            else:
                data = command_text.encode('utf-8')
            
            # 添加CRC16校验
            if self.multi_crc_check.isChecked():
                crc = self.calculate_crc16(data)
                data += crc.to_bytes(2, byteorder='little')
            
            # 添加换行符
            if self.multi_crlf_check.isChecked():
                data += b'\r\n'
            
            # 发送数据
            self.ser.write(data)
            
            # 更新发送计数
            self.tx_count += len(data)
            self.tx_count_label.setText(str(self.tx_count))
            
            self.statusBar.showMessage(f"已发送命令: {command_text}")
            
        except Exception as e:
            self.statusBar.showMessage(f"发送命令错误: {str(e)}")
    
    def calculate_crc16(self, data):
        """计算CRC16校验码"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    def save_multi_commands(self):
        """保存多命令到文件"""
        if self.command_table.rowCount() == 0:
            QMessageBox.information(self, "提示", "没有命令可保存")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self.multi_command_window, 
            "保存命令文件", 
            "", 
            "JSON文件 (*.json);;所有文件 (*)"
        )
        
        if file_path:
            try:
                import json
                commands = []
                for row in range(self.command_table.rowCount()):
                    # 获取命令内容
                    command_item = self.command_table.item(row, 0)
                    command_text = command_item.text() if command_item else ""
                    
                    # 获取间隔时间
                    interval_item = self.command_table.item(row, 1)
                    interval = interval_item.text() if interval_item else "1000"
                    
                    # 获取启用状态
                    enable_widget = self.command_table.cellWidget(row, 2)
                    enabled = False
                    if enable_widget:
                        checkbox = enable_widget.findChild(QCheckBox)
                        if checkbox:
                            enabled = checkbox.isChecked()
                    
                    commands.append({
                        "command": command_text,
                        "interval": interval,
                        "enabled": enabled
                    })
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(commands, f, ensure_ascii=False, indent=2)
                
                QMessageBox.information(self, "成功", f"命令已保存到: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
    
    def import_multi_commands(self):
        """从文件导入多命令"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.multi_command_window,
            "导入命令文件",
            "",
            "JSON文件 (*.json);;所有文件 (*)"
        )
        
        if file_path:
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    commands = json.load(f)
                
                # 清空现有命令
                self.command_table.setRowCount(0)
                
                # 导入命令
                for cmd_data in commands:
                    row_count = self.command_table.rowCount()
                    self.command_table.insertRow(row_count)
                    
                    # 设置命令内容
                    command_text = cmd_data.get("command", "")
                    self.command_table.setItem(row_count, 0, QTableWidgetItem(command_text))
                    
                    # 设置间隔时间
                    interval = cmd_data.get("interval", "1000")
                    self.command_table.setItem(row_count, 1, QTableWidgetItem(str(interval)))
                    
                    # 设置启用状态
                    enabled = cmd_data.get("enabled", True)
                    enable_check = QCheckBox()
                    enable_check.setChecked(enabled)
                    
                    # 创建容器widget来居中显示复选框
                    checkbox_widget = QWidget()
                    checkbox_layout = QHBoxLayout(checkbox_widget)
                    checkbox_layout.addWidget(enable_check)
                    checkbox_layout.setAlignment(Qt.AlignCenter)
                    checkbox_layout.setContentsMargins(0, 0, 0, 0)
                    
                    self.command_table.setCellWidget(row_count, 2, checkbox_widget)
                
                QMessageBox.information(self, "成功", f"已导入 {len(commands)} 条命令")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败: {str(e)}")
    
    def show_multi_command_tab(self):
        """切换到多命令发送标签页"""
        if hasattr(self, 'multi_command_tab_index'):
            self.send_tabs.setCurrentIndex(self.multi_command_tab_index)
        else:
            # 如果没有索引，尝试通过标签文本查找
            for i in range(self.send_tabs.count()):
                if self.send_tabs.tabText(i) == "多命令发送":
                    self.send_tabs.setCurrentIndex(i)
                    break
    
    def open_command_generator_window(self):
        """打开指令生成窗口"""
        # 创建指令生成窗口类
        class CommandGeneratorWindow(QWidget):
            def __init__(self):
                super().__init__()
                self.setWindowTitle('指令生成器')
                self.setGeometry(200, 200, 900, 700)
                self.init_ui()
                
            def init_ui(self):
                layout = QVBoxLayout()
                
                # 添加说明标签
                info_label = QLabel('PC应用程序到设备数据格式：A5 D0 D1 D2 D3 D4 D5 D6 D7 D8 D9 D10 D11 D12 D13 D14 D15 D16 D17 D18 D19 D20 D21 D22 D23 B24')
                info_label.setWordWrap(True)
                info_label.setStyleSheet('font-weight: bold; color: blue; padding: 10px;')
                layout.addWidget(info_label)
                
                # 添加说明
                desc_label = QLabel('A5：起始字节\nD0~D23：对应O0~O191，D0=O0~O7，D1=O8~15，以此类推\n请在下表中设置各位的值（0或1）：')
                desc_label.setStyleSheet('padding: 5px;')
                layout.addWidget(desc_label)
                
                # 创建表格
                self.table = QTableWidget()
                self.table.setRowCount(24)  # D0-D23
                self.table.setColumnCount(9)  # 8位数据 + 1列字节值
                
                # 设置表头
                headers = ['Bit7', 'Bit6', 'Bit5', 'Bit4', 'Bit3', 'Bit2', 'Bit1', 'Bit0', '字节值(HEX)']
                self.table.setHorizontalHeaderLabels(headers)
                
                # 设置行标签
                row_labels = [f'D{i} (O{i*8}-O{i*8+7})' for i in range(24)]
                self.table.setVerticalHeaderLabels(row_labels)
                
                # 初始化表格数据
                for i in range(24):
                    for j in range(8):
                        item = QTableWidgetItem('0')
                        item.setTextAlignment(Qt.AlignCenter)
                        self.table.setItem(i, j, item)
                    # 字节值列
                    hex_item = QTableWidgetItem('00')
                    hex_item.setTextAlignment(Qt.AlignCenter)
                    hex_item.setFlags(Qt.ItemIsEnabled)  # 只读
                    hex_item.setBackground(QColor('#f0f0f0'))
                    self.table.setItem(i, 8, hex_item)
                
                # 连接单元格变化事件
                self.table.itemChanged.connect(self.on_cell_changed)
                
                # 设置列宽
                for i in range(8):
                    self.table.setColumnWidth(i, 60)
                self.table.setColumnWidth(8, 100)
                
                layout.addWidget(self.table)
                
                # 按钮区域
                button_layout = QHBoxLayout()
                
                # 全部置0按钮
                clear_btn = QPushButton('全部置0')
                clear_btn.clicked.connect(self.clear_all)
                button_layout.addWidget(clear_btn)
                
                # 全部置1按钮
                set_all_btn = QPushButton('全部置1')
                set_all_btn.clicked.connect(self.set_all)
                button_layout.addWidget(set_all_btn)
                
                button_layout.addStretch()
                
                # 生成指令按钮
                generate_btn = QPushButton('生成指令')
                generate_btn.setStyleSheet('background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;')
                generate_btn.clicked.connect(self.generate_command)
                button_layout.addWidget(generate_btn)
                
                # 复制指令按钮
                copy_btn = QPushButton('复制指令')
                copy_btn.setStyleSheet('background-color: #2196F3; color: white; font-weight: bold; padding: 10px;')
                copy_btn.clicked.connect(self.copy_command)
                button_layout.addWidget(copy_btn)
                
                layout.addLayout(button_layout)
                
                # 生成的指令显示区域
                self.command_text = QTextEdit()
                self.command_text.setMaximumHeight(100)
                self.command_text.setPlaceholderText('生成的指令将显示在这里...')
                self.command_text.setStyleSheet('font-family: Consolas, monospace; font-size: 12px;')
                layout.addWidget(self.command_text)
                
                self.setLayout(layout)
                
            def on_cell_changed(self, item):
                """单元格内容改变时的处理"""
                if item.column() < 8:  # 只处理位数据列
                    # 限制输入只能是0或1
                    text = item.text()
                    if text not in ['0', '1']:
                        item.setText('0')
                    
                    # 更新对应行的字节值
                    self.update_byte_value(item.row())
            
            def update_byte_value(self, row):
                """更新指定行的字节值"""
                byte_value = 0
                for col in range(8):
                    bit_item = self.table.item(row, col)
                    if bit_item and bit_item.text() == '1':
                        byte_value |= (1 << (7 - col))  # Bit7在最左边
                
                hex_item = self.table.item(row, 8)
                if hex_item:
                    hex_item.setText(f'{byte_value:02X}')
            
            def clear_all(self):
                """全部置0"""
                for i in range(24):
                    for j in range(8):
                        item = self.table.item(i, j)
                        if item:
                            item.setText('0')
                    self.update_byte_value(i)
            
            def set_all(self):
                """全部置1"""
                for i in range(24):
                    for j in range(8):
                        item = self.table.item(i, j)
                        if item:
                            item.setText('1')
                    self.update_byte_value(i)
            
            def generate_command(self):
                """生成指令"""
                command_bytes = ['A5']  # 起始字节
                
                # 添加D0-D23字节
                for i in range(24):
                    hex_item = self.table.item(i, 8)
                    if hex_item:
                        command_bytes.append(hex_item.text())
                
                # 添加B24（设为01）
                command_bytes.extend(['01'])
                
                # 生成最终指令
                command = ' '.join(command_bytes)
                self.command_text.setPlainText(command)
            
            def copy_command(self):
                """复制指令到剪贴板"""
                command = self.command_text.toPlainText()
                if command:
                    clipboard = QApplication.clipboard()
                    clipboard.setText(command)
                    QMessageBox.information(self, '提示', '指令已复制到剪贴板！')
                else:
                    QMessageBox.warning(self, '警告', '请先生成指令！')
        
        # 创建并显示窗口
        self.command_generator_window = CommandGeneratorWindow()
        
        # 为指令生成窗口添加布局记忆
        self.load_sub_window_layout(self.command_generator_window, 'command_generator_window')
        
        # 添加关闭事件处理
        def closeEvent(event):
            self.save_sub_window_layout(self.command_generator_window, 'command_generator_window')
            event.accept()
        self.command_generator_window.closeEvent = closeEvent
        
        self.command_generator_window.show()

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于",
                          "东莞市海沛自动化设备有限公司")

    def load_window_layout(self):
        """加载窗口布局设置"""
        try:
            import os
            config_file = os.path.join(os.path.dirname(__file__), 'window_layout.ini')
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                config = {}
                for line in lines:
                    line = line.strip()
                    if line and '=' in line:
                        key, value = line.split('=', 1)
                        config[key] = value
                
                # 应用窗口布局
                if all(key in config for key in ['window_x', 'window_y', 'window_width', 'window_height']):
                    try:
                        x = int(config['window_x'])
                        y = int(config['window_y'])
                        width = int(config['window_width'])
                        height = int(config['window_height'])
                        
                        # 确保窗口在屏幕范围内
                        from PyQt5.QtWidgets import QApplication
                        screen = QApplication.desktop().screenGeometry()
                        if x < 0 or y < 0 or x > screen.width() - 100 or y > screen.height() - 100:
                            x, y = 100, 100  # 重置到默认位置
                        if width < 400 or height < 300:
                            width, height = 900, 700  # 重置到默认大小
                        
                        self.setGeometry(x, y, width, height)
                        
                        if 'window_maximized' in config and config['window_maximized'] == '1':
                            self.showMaximized()
                    except ValueError:
                        pass  # 如果转换失败，保持默认窗口大小
        except Exception as e:
            print(f"加载窗口布局失败: {str(e)}")
    
    def save_window_layout(self):
        """保存窗口布局设置"""
        try:
            import os
            config_file = os.path.join(os.path.dirname(__file__), 'window_layout.ini')
            
            with open(config_file, 'w', encoding='utf-8') as f:
                geometry = self.geometry()
                f.write(f"window_x={geometry.x()}\n")
                f.write(f"window_y={geometry.y()}\n")
                f.write(f"window_width={geometry.width()}\n")
                f.write(f"window_height={geometry.height()}\n")
                f.write(f"window_maximized={1 if self.isMaximized() else 0}\n")
        except Exception as e:
             print(f"保存窗口布局失败: {str(e)}")
    
    def load_sub_window_layout(self, window, window_name):
        """加载子窗口布局设置"""
        try:
            import os
            config_file = os.path.join(os.path.dirname(__file__), f'{window_name}_layout.ini')
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                config = {}
                for line in lines:
                    line = line.strip()
                    if line and '=' in line:
                        key, value = line.split('=', 1)
                        config[key] = value
                
                # 应用窗口布局
                if all(key in config for key in ['window_x', 'window_y', 'window_width', 'window_height']):
                    try:
                        x = int(config['window_x'])
                        y = int(config['window_y'])
                        width = int(config['window_width'])
                        height = int(config['window_height'])
                        
                        # 确保窗口在屏幕范围内
                        from PyQt5.QtWidgets import QApplication
                        screen = QApplication.desktop().screenGeometry()
                        if x < 0 or y < 0 or x > screen.width() - 100 or y > screen.height() - 100:
                            x, y = 100, 100  # 重置到默认位置
                        if width < 300 or height < 200:
                            width, height = 800, 600  # 重置到默认大小
                        
                        window.setGeometry(x, y, width, height)
                        
                        if 'window_maximized' in config and config['window_maximized'] == '1':
                            window.showMaximized()
                    except ValueError:
                        pass  # 如果转换失败，保持默认窗口大小
        except Exception as e:
            print(f"加载{window_name}窗口布局失败: {str(e)}")
    
    def save_sub_window_layout(self, window, window_name):
        """保存子窗口布局设置"""
        try:
            import os
            config_file = os.path.join(os.path.dirname(__file__), f'{window_name}_layout.ini')
            
            with open(config_file, 'w', encoding='utf-8') as f:
                geometry = window.geometry()
                f.write(f"window_x={geometry.x()}\n")
                f.write(f"window_y={geometry.y()}\n")
                f.write(f"window_width={geometry.width()}\n")
                f.write(f"window_height={geometry.height()}\n")
                f.write(f"window_maximized={1 if window.isMaximized() else 0}\n")
        except Exception as e:
            print(f"保存{window_name}窗口布局失败: {str(e)}")

    def closeEvent(self, event):
        """关闭窗口时的处理"""
        self.close_serial()
        self.save_window_layout()  # 自动保存窗口布局
        event.accept()


class BitMapper:
    def __init__(self):
        # 初始化映射配置
        self.bit_mapping = {}
        self.bit_mapping_enabled = {}
        for i in range(192):  # 24字节 * 8位 = 192位
            self.bit_mapping[i] = i  # 默认一一对应
            self.bit_mapping_enabled[i] = False  # 默认禁用所有映射

    def convert_data(self, input_data):
        """根据映射配置转换数据"""
        if len(input_data) == 0:
            return bytearray()

        # 创建输出数据，第一个字节为A5
        output_data = bytearray([0xA5])

        # 处理剩余字节
        remaining_data = input_data[1:]

        # 将输入数据转换为位列表
        input_bits = []
        for byte_index, byte in enumerate(remaining_data):
            for bit_index in range(8):
                # 计算全局位索引（从左到右递增）
                global_bit_index = byte_index * 8 + (7 - bit_index)
                input_bits.append((byte >> (7 - bit_index)) & 1)

        # 创建输出字节列表（24个字节，对应D0-D23）
        output_bytes = [0] * 24

        # 根据映射关系设置输出字节的位值
        for input_pos, output_pos in self.bit_mapping.items():
            if isinstance(input_pos, str):
                input_pos = int(input_pos)
            if isinstance(output_pos, str):
                output_pos = int(output_pos)

            # 确保输入位在有效范围内
            if (input_pos < len(input_bits) and
                self.bit_mapping_enabled.get(str(input_pos), True)):
                # 计算对应的字节索引和位索引
                byte_index = output_pos // 8
                bit_index = output_pos % 8
                
                # 如果字节索引在有效范围内
                if 0 <= byte_index < 24:
                    # 设置对应位的值
                    if input_pos < len(input_bits):
                        if input_bits[input_pos] == 1:
                            output_bytes[byte_index] |= (1 << (7 - bit_index))
                        else:
                            output_bytes[byte_index] &= ~(1 << (7 - bit_index))

        # 将输出字节添加到输出数据中
        output_data.extend(output_bytes)

        # 添加测试状态字节（B24）
        output_data.append(0x01)

        # 计算并添加CRC16校验（C25-C26）
        crc = self.crc16(output_data)
        output_data.extend([crc >> 8, crc & 0xFF])

        return output_data

def test_specific_input():
    """测试特定输入数据的转换结果"""
    mapper = BitMapper()

    # 测试数据
    test_data = bytearray.fromhex("A5D0D0D0D0000000000000000000000000000000000000000001")

    # 默认情况下所有映射都是禁用的
    print("1. 默认I/O映射配置（所有映射禁用）:")
    output_data = mapper.convert_data(test_data)
    print("输入数据:", " ".join(f"{b:02X}" for b in test_data))
    print("输出数据:", " ".join(f"{b:02X}" for b in output_data))

    # 显示输出位
    output_bits = []
    for byte in output_data:
        for i in range(8):
            if (byte >> i) & 1:
                output_bits.append(i)
    if output_bits:
        print("输出位置:", " ".join(f"O{pos}" for pos in output_bits))
    else:
        print("输出位置: 无输出")

    print("\n2. 启用部分映射:")
    # 设置一些映射关系，从I8开始映射（对应第二个字节D0的开始）
    for i in range(8, 24):  # 映射第二个字节开始的16位
        mapper.bit_mapping[i] = i
        mapper.bit_mapping_enabled[i] = True

    print("已启用的映射:")
    for i in range(8, 24):
        print(f"I{i} -> O{mapper.bit_mapping[i]}")

    # 转换数据
    output_data = mapper.convert_data(test_data)
    print("\n输入数据:", " ".join(f"{b:02X}" for b in test_data))
    print("输出数据:", " ".join(f"{b:02X}" for b in output_data))

    # 显示输出位
    output_bits = []
    for byte in output_data:
        for i in range(8):
            if (byte >> i) & 1:
                output_bits.append(i)
    if output_bits:
        print("输出位置:", " ".join(f"O{pos}" for pos in output_bits))
    else:
        print("输出位置: 无输出")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_specific_input()
    else:
        app = QApplication(sys.argv)
        # 设置全局样式
        app.setStyle("Fusion")

        # 设置应用字体
        font = QFont()
        font.setFamily("SimHei")
        font.setPointSize(10)
        app.setFont(font)

        window = AdvancedSerialTool()
        window.show()
        sys.exit(app.exec_())


class SignalDetectionWindow(QWidget):
    data_received = pyqtSignal(bytes)
    def __init__(self):
        super().__init__()
        self.setWindowTitle('信号检测')
        self.setGeometry(200, 200, 800, 600)
        layout = QVBoxLayout()
        self.table = QTableWidget()
        self.table.setRowCount(24)
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([f'I{i*8}-I{i*8 + 7}' for i in range(8)])
        self.table.setVerticalHeaderLabels([f'D{i}' for i in range(24)])
        for i in range(24):
            for j in range(8):
                item = QTableWidgetItem('0')
                self.table.setItem(i, j, item)
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.data_received.connect(self.update_table)
    def update_table(self, data):
        # 假设数据格式正确，更新表格数据
        for i in range(min(24, len(data))):
            byte_data = data[i]
            for j in range(8):
                bit_value = (byte_data >> j) & 1
                item = QTableWidgetItem(str(bit_value))
                self.table.setItem(i, j, item)