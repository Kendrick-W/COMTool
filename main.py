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
                             QSpinBox, QTabWidget, QListWidget, QSplitter, QScrollArea, QTableWidget, QTableWidgetItem)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QTimer
from PyQt5.QtGui import QFont, QTextCursor


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
                time.sleep(0.01)  # 减少CPU占用
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

        # 数据映射配置（I/O位映射）
        self.bit_mapping = {}
        self.bit_mapping_enabled = {}  # 存储每个映射是否启用
        for i in range(192):  # 24字节 * 8位，对应D0~D23
            self.bit_mapping[i] = i  # 默认一一对应
            self.bit_mapping_enabled[i] = False  # 默认禁用所有映射

        # 初始化 command_list
        self.command_list = QListWidget()

        self.crc16_label = QLabel("0")

        # 初始化UI
        self.initUI()

        # 初始化串口列表
        self.update_port_list()

    def initUI(self):
        # 设置窗口标题和大小
        self.setWindowTitle("串口调试工具")
        self.setGeometry(100, 100, 900, 700)

        # 创建菜单栏
        self.create_menu_bar()

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)

        # 串口配置组
        config_group = QGroupBox("串口配置")
        config_layout = QGridLayout(config_group)

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
            output_spin.setValue(self.bit_mapping[i])
            output_spin.setEnabled(self.bit_mapping_enabled[i])  # 设置初始可编辑状态
            output_spin.valueChanged.connect(lambda value, bit=i: self.update_bit_mapping(bit, value))

            # 添加启用/禁用复选框
            enable_check = QCheckBox()
            enable_check.setObjectName(f"enable_check_{i}")
            enable_check.setChecked(self.bit_mapping_enabled[i])
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

        self.send_tabs.addTab(mapping_widget, "映射配置")

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
        self.timer_spin.setRange(100, 60000)
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

        # 示例工具菜单项
        example_tool_action = QAction("示例工具", self)
        example_tool_action.triggered.connect(self.example_tool_function)
        tool_menu.addAction(example_tool_action)

        # 新增信号检测菜单项
        signal_detection_action = QAction("信号检测", self)
        signal_detection_action.triggered.connect(self.open_signal_detection_window)
        tool_menu.addAction(signal_detection_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        # 关于
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

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
        # 创建信号检测窗口类（示例）
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
        self.signal_detection_window = SignalDetectionWindow()
        self.signal_detection_window.show()

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

    def update_bit_mapping(self, input_bit, output_bit):
        """更新位映射配置"""
        self.bit_mapping[input_bit] = output_bit

    def toggle_mapping(self, bit, enabled, spin_box):
        """切换映射启用状态"""
        self.bit_mapping_enabled[bit] = enabled
        spin_box.setEnabled(enabled)  # 设置输出位文本框的可编辑状态

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

        # 第一个字节保持不变
        output_data = bytearray([input_data[0]])

        # 处理剩余字节
        remaining_data = input_data[1:]

        # 将输入数据转换为位列表
        input_bits = []
        for byte_index, byte in enumerate(remaining_data):
            for bit_index in range(8):
                # 计算全局位索引，考虑到第一个字节已经被跳过
                global_bit_index = byte_index * 8 + bit_index
                input_bits.append((byte >> bit_index) & 1)

        # 创建输出位列表，长度为输入位列表的长度
        output_bits = [0] * len(input_bits)

        # 根据映射关系重新排列位，只处理启用的映射
        for input_pos, output_pos in self.bit_mapping.items():
            if isinstance(input_pos, str):
                input_pos = int(input_pos)
            if isinstance(output_pos, str):
                output_pos = int(output_pos)

            # 调整输入位和输出位的索引，考虑到第一个字节已经被跳过
            adjusted_input_pos = input_pos - 8
            adjusted_output_pos = output_pos - 8

            if (adjusted_input_pos >= 0 and
                adjusted_input_pos < len(input_bits) and
                adjusted_output_pos >= 0 and
                adjusted_output_pos < len(output_bits) and
                self.bit_mapping_enabled.get(input_pos, False)):
                output_bits[adjusted_output_pos] = input_bits[adjusted_input_pos]

        # 将位列表转换回字节
        for i in range(0, len(output_bits), 8):
            byte = 0
            for j in range(min(8, len(output_bits) - i)):
                byte |= output_bits[i + j] << j
            output_data.append(byte)

        return output_data

    def update_receive_text(self, data):
        """更新接收文本框"""
        # 更新接收计数
        self.rx_count += len(data)
        self.rx_count_label.setText(str(self.rx_count))

        if self.hex_recv_check.isChecked():
            # 十六进制显示
            hex_list = [f"{byte:02X}" for byte in data]
            html_text = ""
            for hex_byte in hex_list:
                if hex_byte == "5A":
                    html_text += f'<span style="color: green;">{hex_byte}</span> '
                elif hex_byte == "EB":
                    html_text += f'<span style="color: red;">{hex_byte}</span> '
                else:
                    html_text += f"{hex_byte} "
            self.receive_text.moveCursor(QTextCursor.End)
            self.receive_text.insertHtml(html_text)
            text = ""
        else:
            # 字符串显示
            try:
                text = converted_data.decode('utf-8', errors='replace')
            except:
                text = str(converted_data)

        # 添加时间戳和标记
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        if self.hex_recv_check.isChecked():
            text = f"[{timestamp}] [接收] {' '.join(hex_list)}\n"
        else:
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

        if current_index == 1:  # 默认发送区
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
        if self.ser and self.ser.is_open:
            # 获取当前标签页的内容
            current_index = self.send_tabs.currentIndex()

            if current_index == 0:  # 默认发送区
                text = self.send_text.toPlainText().strip()
                if not text:
                    self.statusBar.showMessage("发送内容为空，已停止定时发送")
                    self.toggle_timer()
                    return
                try:
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

                    # 添加换行符
                    if self.crlf_check.isChecked():
                        data += b'\r\n'

                    # 发送数据
                    self.ser.write(data)

                    # 更新发送计数
                    self.tx_count += len(data)
                    self.tx_count_label.setText(str(self.tx_count))

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

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于",
                          "东莞市海沛自动化设备有限公司")

    def closeEvent(self, event):
        """关闭窗口时的处理"""
        self.close_serial()
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

        # 第一个字节保持不变
        output_data = bytearray([input_data[0]])

        # 处理剩余字节
        remaining_data = input_data[1:]

        # 将输入数据转换为位列表
        input_bits = []
        for byte_index, byte in enumerate(remaining_data):
            for bit_index in range(8):
                # 计算全局位索引，考虑到第一个字节已经被跳过
                global_bit_index = byte_index * 8 + bit_index
                input_bits.append((byte >> bit_index) & 1)

        # 创建输出位列表，长度为输入位列表的长度
        output_bits = [0] * len(input_bits)

        # 根据映射关系重新排列位，只处理启用的映射
        for input_pos, output_pos in self.bit_mapping.items():
            if isinstance(input_pos, str):
                input_pos = int(input_pos)
            if isinstance(output_pos, str):
                output_pos = int(output_pos)

            # 调整输入位和输出位的索引，考虑到第一个字节已经被跳过
            adjusted_input_pos = input_pos - 8
            adjusted_output_pos = output_pos - 8

            if (adjusted_input_pos >= 0 and
                adjusted_input_pos < len(input_bits) and
                adjusted_output_pos >= 0 and
                adjusted_output_pos < len(output_bits) and
                self.bit_mapping_enabled.get(input_pos, False)):
                output_bits[adjusted_output_pos] = input_bits[adjusted_input_pos]

        # 将位列表转换回字节
        for i in range(0, len(output_bits), 8):
            byte = 0
            for j in range(min(8, len(output_bits) - i)):
                byte |= output_bits[i + j] << j
            output_data.append(byte)

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