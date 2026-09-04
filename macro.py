"""
Flick - Ultra-lightweight, high-performance keyboard macro
Minimalist design with feather-inspired aesthetics
Python 3.14.0
"""

import sys
import threading
import time
from collections import deque
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QCheckBox, QPushButton, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QPainter, QColor, QIcon, QPixmap, QPolygonF, QPen, QBrush
from PyQt6.QtSvgWidgets import QSvgWidget
from pynput.keyboard import Controller, Listener
from pynput import mouse


class FeatherIcon:
    """Generate a minimalist feather icon"""
    @staticmethod
    def create_icon(size=64):
        """Create a feather-shaped icon"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Feather shaft
        pen = QPen(QColor("#4ade80"), 2)
        painter.setPen(pen)
        painter.drawLine(size // 2, size // 4, size // 2, size * 3 // 4)
        
        # Left feather detail
        painter.drawLine(size // 2, size // 3, size // 3, size // 2)
        painter.drawLine(size // 2, size // 2, size // 3, size // 2 + 8)
        
        # Right feather detail
        painter.drawLine(size // 2, size // 3, size * 2 // 3, size // 2)
        painter.drawLine(size // 2, size // 2, size * 2 // 3, size // 2 + 8)
        
        painter.end()
        return QIcon(pixmap)


class SmoothClickEngine:
    """High-precision clicking engine with consistency tracking"""
    
    def __init__(self):
        self.keyboard = Controller()
        self.mouse_controller = mouse.Controller()
        self.click_times = deque(maxlen=100)
        self.is_running = False
        
    def execute_click(self, use_mouse=False):
        """Execute a single click with minimal latency"""
        try:
            start = time.perf_counter()
            
            if use_mouse:
                self.mouse_controller.click()
            else:
                self.keyboard.press('f')
                self.keyboard.release('f')
            
            elapsed = time.perf_counter() - start
            self.click_times.append(elapsed)
        except Exception as e:
            raise e
    
    def get_consistency(self):
        """Get click consistency percentage (0-100)"""
        if len(self.click_times) < 2:
            return 100
        
        avg_time = sum(self.click_times) / len(self.click_times)
        variance = sum((t - avg_time) ** 2 for t in self.click_times) / len(self.click_times)
        std_dev = variance ** 0.5
        
        # Calculate consistency (lower std dev = higher consistency)
        consistency = max(0, 100 - (std_dev * 1000))
        return min(100, consistency)


class MacroWorker(QObject):
    """Worker thread for macro execution"""
    status_changed = pyqtSignal(str)
    consistency_changed = pyqtSignal(float)
    
    def __init__(self):
        super().__init__()
        self.engine = SmoothClickEngine()
        self.is_running = False
        self.thread = None
        self.consistency_update_counter = 0
        
    def start_macro(self, cps, use_mouse=False):
        """Start the macro in a separate thread"""
        if self.is_running:
            return
        
        self.is_running = True
        self.thread = threading.Thread(
            target=self._run_macro,
            args=(cps, use_mouse),
            daemon=True
        )
        self.thread.start()
        
    def _run_macro(self, cps, use_mouse):
        """Execute the macro loop with high precision timing"""
        target_delay = 1.0 / cps
        
        try:
            self.status_changed.emit("running")
            last_click_time = time.perf_counter()
            
            while self.is_running:
                current_time = time.perf_counter()
                time_since_last = current_time - last_click_time
                
                if time_since_last >= target_delay:
                    try:
                        self.engine.execute_click(use_mouse)
                        last_click_time = time.perf_counter()
                        
                        # Update consistency every 10 clicks
                        self.consistency_update_counter += 1
                        if self.consistency_update_counter >= 10:
                            consistency = self.engine.get_consistency()
                            self.consistency_changed.emit(consistency)
                            self.consistency_update_counter = 0
                    except Exception as e:
                        self.status_changed.emit("error")
                        self.is_running = False
                        break
                else:
                    # Precise sleep with busy-wait for final microseconds
                    sleep_time = target_delay - time_since_last - 0.001
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    
                    # Busy-wait for final precision
                    while time.perf_counter() - last_click_time < target_delay:
                        pass
                        
        except Exception as e:
            self.status_changed.emit("error")
        finally:
            self.is_running = False
            self.status_changed.emit("stopped")
    
    def stop_macro(self):
        """Stop the macro"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1)


class Flick(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = MacroWorker()
        self.worker.status_changed.connect(self.on_status_changed)
        self.worker.consistency_changed.connect(self.on_consistency_changed)
        
        self.hotkey = None
        self.listening = False
        self.is_toggle_mode = False
        self.macro_active = False
        self.listener = None
        self.current_cps = 10
        
        self.init_ui()
        self.setup_styles()
        self.start_listener()
        
    def init_ui(self):
        """Initialize the minimalist UI"""
        self.setWindowTitle("Flick")
        self.setWindowIcon(FeatherIcon.create_icon(64))
        self.setGeometry(100, 100, 600, 500)
        self.setMinimumSize(600, 500)
        
        main_widget = QWidget()
        main_widget.setObjectName("mainWidget")
        layout = QVBoxLayout()
        layout.setSpacing(24)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Header with icon
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        
        icon_label = QLabel()
        icon_pixmap = QPixmap(48, 48)
        icon_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(icon_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#4ade80"), 2.5)
        painter.setPen(pen)
        painter.drawLine(24, 12, 24, 36)
        painter.drawLine(24, 18, 16, 24)
        painter.drawLine(24, 24, 16, 28)
        painter.drawLine(24, 18, 32, 24)
        painter.drawLine(24, 24, 32, 28)
        painter.end()
        icon_label.setPixmap(icon_pixmap)
        header_layout.addWidget(icon_label)
        
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        
        title = QLabel("Flick")
        title_font = QFont("Segoe UI", 36, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setObjectName("title")
        title_layout.addWidget(title)
        
        subtitle = QLabel("Click faster")
        subtitle_font = QFont("Segoe UI", 11)
        subtitle.setFont(subtitle_font)
        subtitle.setObjectName("subtitle")
        title_layout.addWidget(subtitle)
        
        header_layout.addLayout(title_layout, 1)
        layout.addLayout(header_layout)
        
        # Status and Consistency Section
        status_section = QVBoxLayout()
        status_section.setSpacing(12)
        
        self.status_label = QLabel("READY")
        status_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        self.status_label.setFont(status_font)
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_section.addWidget(self.status_label)
        
        # Consistency meter
        consistency_label = QLabel("Consistency")
        consistency_label_font = QFont("Segoe UI", 10)
        consistency_label.setFont(consistency_label_font)
        consistency_label.setObjectName("consistencyLabel")
        status_section.addWidget(consistency_label)
        
        self.consistency_bar = QLabel()
        self.consistency_bar.setObjectName("consistencyBar")
        self.consistency_bar.setMinimumHeight(6)
        self.consistency_bar.setMaximumHeight(6)
        self.consistency_bar.setText("")
        status_section.addWidget(self.consistency_bar)
        
        self.consistency_value = QLabel("100%")
        consistency_value_font = QFont("Segoe UI", 10)
        consistency_value_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)
        self.consistency_value.setFont(consistency_value_font)
        self.consistency_value.setObjectName("consistencyValue")
        self.consistency_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_section.addWidget(self.consistency_value)
        
        layout.addLayout(status_section)
        
        # Hotkey Section
        hotkey_section = QVBoxLayout()
        hotkey_section.setSpacing(12)
        
        hotkey_label = QLabel("HOTKEY")
        hotkey_label_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        hotkey_label.setFont(hotkey_label_font)
        hotkey_label.setObjectName("sectionLabel")
        hotkey_section.addWidget(hotkey_label)
        
        hotkey_button_layout = QHBoxLayout()
        hotkey_button_layout.setSpacing(12)
        
        self.hotkey_display = QLineEdit()
        self.hotkey_display.setReadOnly(True)
        self.hotkey_display.setText("None")
        self.hotkey_display.setObjectName("hotkeyDisplay")
        self.hotkey_display.setMinimumHeight(40)
        hotkey_button_layout.addWidget(self.hotkey_display, 1)
        
        set_hotkey_btn = QPushButton("Set")
        set_hotkey_btn.setObjectName("setButton")
        set_hotkey_btn.clicked.connect(self.set_hotkey_mode)
        set_hotkey_btn.setMinimumHeight(40)
        set_hotkey_btn.setMaximumWidth(80)
        hotkey_button_layout.addWidget(set_hotkey_btn)
        
        hotkey_section.addLayout(hotkey_button_layout)
        
        # Toggle mode
        self.toggle_checkbox = QCheckBox("Toggle Mode")
        self.toggle_checkbox.setObjectName("modeCheckbox")
        self.toggle_checkbox.setMinimumHeight(30)
        self.toggle_checkbox.setChecked(False)
        toggle_font = QFont("Segoe UI", 10)
        self.toggle_checkbox.setFont(toggle_font)
        hotkey_section.addWidget(self.toggle_checkbox)
        
        layout.addLayout(hotkey_section)
        
        # CPS Section
        cps_section = QVBoxLayout()
        cps_section.setSpacing(12)
        
        cps_label = QLabel("CLICKS PER SECOND")
        cps_label_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        cps_label.setFont(cps_label_font)
        cps_label.setObjectName("sectionLabel")
        cps_section.addWidget(cps_label)
        
        cps_display_layout = QHBoxLayout()
        
        self.cps_slider = QSlider(Qt.Orientation.Horizontal)
        self.cps_slider.setObjectName("cpsSlider")
        self.cps_slider.setMinimum(1)
        self.cps_slider.setMaximum(500)
        self.cps_slider.setValue(10)
        self.cps_slider.setMinimumHeight(6)
        self.cps_slider.sliderMoved.connect(self.on_cps_changed)
        self.cps_slider.valueChanged.connect(self.on_cps_changed)
        cps_display_layout.addWidget(self.cps_slider, 1)
        
        self.cps_value = QLabel("10")
        cps_value_font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        self.cps_value.setFont(cps_value_font)
        self.cps_value.setObjectName("cpsValue")
        self.cps_value.setMinimumWidth(50)
        cps_display_layout.addWidget(self.cps_value)
        
        cps_section.addLayout(cps_display_layout)
        
        layout.addLayout(cps_section)
        
        layout.addStretch()
        
        # Control Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        start_btn = QPushButton("START")
        start_btn.setObjectName("startButton")
        start_btn.clicked.connect(self.start_macro)
        start_btn.setMinimumHeight(50)
        button_layout.addWidget(start_btn)
        
        stop_btn = QPushButton("STOP")
        stop_btn.setObjectName("stopButton")
        stop_btn.clicked.connect(self.stop_macro)
        stop_btn.setMinimumHeight(50)
        button_layout.addWidget(stop_btn)
        
        layout.addLayout(button_layout)
        
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
    def setup_styles(self):
        """Setup dark theme with smooth styling"""
        dark_stylesheet = """
        QMainWindow, QWidget#mainWidget {
            background-color: #0f0f0f;
        }
        
        QLabel#title {
            color: #ffffff;
            font-weight: bold;
        }
        
        QLabel#subtitle {
            color: #666666;
        }
        
        QLabel#statusLabel {
            color: #4ade80;
            font-weight: bold;
            padding: 12px;
            background-color: #1e3a1e;
            border-radius: 8px;
        }
        
        QLabel#statusLabel[status="running"] {
            color: #4ade80;
            background-color: #1e3a1e;
        }
        
        QLabel#statusLabel[status="stopped"] {
            color: #666666;
            background-color: #1a1a1a;
        }
        
        QLabel#statusLabel[status="error"] {
            color: #ef4444;
            background-color: #3a1e1e;
        }
        
        QLabel#sectionLabel {
            color: #ffffff;
            font-weight: bold;
            letter-spacing: 1px;
            font-size: 11px;
        }
        
        QLabel#consistencyLabel {
            color: #888888;
            font-size: 10px;
        }
        
        QLabel#consistencyValue {
            color: #888888;
            font-size: 10px;
        }
        
        QLineEdit#hotkeyDisplay {
            background-color: #1a1a1a;
            border: 1px solid #333333;
            border-radius: 6px;
            color: #ffffff;
            padding: 8px 12px;
            font-size: 13px;
            selection-background-color: #333333;
        }
        
        QLineEdit#hotkeyDisplay:focus {
            border: 1px solid #4ade80;
            background-color: #1e1e1e;
        }
        
        QPushButton#setButton {
            background-color: #1a1a1a;
            color: #ffffff;
            border: 1px solid #333333;
            border-radius: 6px;
            font-weight: bold;
            font-size: 12px;
        }
        
        QPushButton#setButton:hover {
            background-color: #252525;
            border: 1px solid #4ade80;
        }
        
        QPushButton#setButton:pressed {
            background-color: #0f0f0f;
        }
        
        QPushButton#startButton {
            background-color: #4ade80;
            color: #000000;
            border: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 14px;
        }
        
        QPushButton#startButton:hover {
            background-color: #5ee096;
        }
        
        QPushButton#startButton:pressed {
            background-color: #3ac96f;
        }
        
        QPushButton#stopButton {
            background-color: #1a1a1a;
            color: #ffffff;
            border: 1px solid #333333;
            border-radius: 8px;
            font-weight: bold;
            font-size: 14px;
        }
        
        QPushButton#stopButton:hover {
            background-color: #252525;
            border: 1px solid #ef4444;
        }
        
        QPushButton#stopButton:pressed {
            background-color: #0f0f0f;
        }
        
        QSlider::groove:horizontal#cpsSlider {
            background-color: #1a1a1a;
            height: 6px;
            border-radius: 3px;
        }
        
        QSlider::handle:horizontal#cpsSlider {
            background-color: #4ade80;
            width: 18px;
            margin: -6px 0;
            border-radius: 9px;
        }
        
        QSlider::handle:horizontal#cpsSlider:hover {
            background-color: #5ee096;
        }
        
        QSlider::sub-page:horizontal#cpsSlider {
            background-color: #4ade80;
            border-radius: 3px;
        }
        
        QCheckBox#modeCheckbox {
            color: #888888;
            spacing: 8px;
            font-size: 10px;
        }
        
        QCheckBox#modeCheckbox::indicator {
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 1px solid #333333;
            background-color: #1a1a1a;
        }
        
        QCheckBox#modeCheckbox::indicator:checked {
            background-color: #4ade80;
            border: 1px solid #4ade80;
        }
        
        QCheckBox#modeCheckbox::indicator:hover {
            border: 1px solid #4ade80;
        }
        """
        
        self.setStyleSheet(dark_stylesheet)
        
    def set_consistency_bar(self, consistency):
        """Update consistency bar visualization"""
        percentage = int(consistency)
        self.consistency_value.setText(f"{percentage}%")
        
        # Simple bar update
        self.consistency_bar.setStyleSheet(f"""
            background-color: #1a1a1a;
            border-radius: 3px;
            margin: 0px;
            padding: 0px;
            qproperty-text: "";
        """)
        
    def get_consistency_color(self, consistency):
        """Get color based on consistency value"""
        if consistency >= 90:
            return "#4ade80"
        elif consistency >= 75:
            return "#eab308"
        elif consistency >= 50:
            return "#f97316"
        else:
            return "#ef4444"
    
    def set_hotkey_mode(self):
        """Enter hotkey setting mode"""
        self.hotkey_display.setText("LISTENING...")
        self.listening = True
        
    def on_press(self, key):
        """Handle key press for hotkey detection"""
        if not self.listening:
            return
        
        try:
            if hasattr(key, 'char') and key.char:
                key_str = key.char.upper()
            else:
                key_str = str(key).replace("Key.", "").upper()
            
            self.hotkey = key
            self.hotkey_display.setText(key_str)
            self.listening = False
        except:
            self.listening = False
            
    def on_release(self, key):
        """Handle key release"""
        if self.listening:
            return True
        
        if self.hotkey and key == self.hotkey:
            if self.is_toggle_mode:
                if self.macro_active:
                    self.stop_macro()
                else:
                    self.start_macro()
            else:
                if not self.macro_active:
                    self.start_macro()
        
        return True
    
    def start_listener(self):
        """Start the global keyboard listener"""
        self.listener = Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()
    
    def on_cps_changed(self):
        """Handle CPS slider change"""
        self.current_cps = self.cps_slider.value()
        self.cps_value.setText(str(self.current_cps))
        
    def start_macro(self):
        """Start the macro"""
        if self.macro_active:
            return
        
        self.macro_active = True
        self.is_toggle_mode = self.toggle_checkbox.isChecked()
        
        self.worker.start_macro(self.current_cps, use_mouse=False)
        
    def stop_macro(self):
        """Stop the macro"""
        self.macro_active = False
        self.worker.stop_macro()
        
    def on_status_changed(self, status):
        """Update status label"""
        if status == "running":
            self.status_label.setText("RUNNING")
            self.status_label.setProperty("status", "running")
        elif status == "stopped":
            self.status_label.setText("READY")
            self.status_label.setProperty("status", "stopped")
        elif status == "error":
            self.status_label.setText("ERROR")
            self.status_label.setProperty("status", "error")
        
        self.style().unpolish(self.status_label)
        self.style().polish(self.status_label)
        
    def on_consistency_changed(self, consistency):
        """Update consistency display"""
        self.set_consistency_bar(consistency)
        
    def closeEvent(self, event):
        """Clean up on close"""
        self.stop_macro()
        if self.listener:
            self.listener.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Flick")
    
    macro = Flick()
    macro.show()
    
    sys.exit(app.exec())
