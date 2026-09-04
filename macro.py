"""
Flick - Ultra-compact, high-performance keyboard macro
Minimalist design with premium aesthetics
Python 3.14.0
"""

import sys
import threading
import time
from collections import deque
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QCheckBox, QPushButton, QLineEdit, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QFont, QColor, QIcon, QPixmap, QPainter, QPen
from pynput.keyboard import Controller, Listener
from pynput import mouse


class SmoothClickEngine:
    """High-precision clicking engine with consistency tracking"""
    
    def __init__(self):
        self.keyboard = Controller()
        self.mouse_controller = mouse.Controller()
        self.click_times = deque(maxlen=100)
        self.is_running = False
        self.total_clicks = 0
        
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
            self.total_clicks += 1
        except Exception as e:
            raise e
    
    def get_consistency(self):
        """Get click consistency percentage (0-100)"""
        if len(self.click_times) < 2:
            return 100
        
        avg_time = sum(self.click_times) / len(self.click_times)
        variance = sum((t - avg_time) ** 2 for t in self.click_times) / len(self.click_times)
        std_dev = variance ** 0.5
        
        consistency = max(0, 100 - (std_dev * 1000))
        return min(100, consistency)
    
    def reset_stats(self):
        """Reset statistics"""
        self.click_times.clear()
        self.total_clicks = 0


class MacroWorker(QObject):
    """Worker thread for macro execution"""
    status_changed = pyqtSignal(str)
    consistency_changed = pyqtSignal(float)
    clicks_changed = pyqtSignal(int)
    
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
                        self.clicks_changed.emit(self.engine.total_clicks)
                        
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
                    sleep_time = target_delay - time_since_last - 0.001
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    
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
    
    def reset_stats(self):
        """Reset click counter"""
        self.engine.reset_stats()
        self.clicks_changed.emit(0)


class Flick(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = MacroWorker()
        self.worker.status_changed.connect(self.on_status_changed)
        self.worker.consistency_changed.connect(self.on_consistency_changed)
        self.worker.clicks_changed.connect(self.on_clicks_changed)
        
        self.hotkey = None
        self.listening = False
        self.is_toggle_mode = False
        self.macro_active = False
        self.listener = None
        self.current_cps = 10
        self.session_time = 0
        self.session_timer = QTimer()
        self.session_timer.timeout.connect(self.update_session_time)
        
        self.init_ui()
        self.setup_styles()
        self.start_listener()
        
    def init_ui(self):
        """Initialize the compact UI"""
        self.setWindowTitle("Flick")
        self.setGeometry(100, 100, 480, 560)
        self.setMinimumSize(480, 560)
        self.setMaximumSize(520, 600)
        
        # Set window properties for rounded corners on Windows
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        
        main_widget = QWidget()
        main_widget.setObjectName("mainWidget")
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header (Compact)
        header_widget = QWidget()
        header_widget.setObjectName("headerWidget")
        header_widget.setMaximumHeight(70)
        header_layout = QVBoxLayout()
        header_layout.setSpacing(8)
        header_layout.setContentsMargins(24, 16, 24, 16)
        
        title = QLabel("flick")
        title_font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setObjectName("title")
        header_layout.addWidget(title)
        
        header_widget.setLayout(header_layout)
        layout.addWidget(header_widget)
        
        # Content
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(16)
        content_layout.setContentsMargins(24, 20, 24, 24)
        
        # Status Indicator
        self.status_label = QLabel("READY")
        status_font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        self.status_label.setFont(status_font)
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMaximumHeight(36)
        content_layout.addWidget(self.status_label)
        
        # Stats Row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
        
        # Consistency
        consistency_group = QVBoxLayout()
        consistency_group.setSpacing(4)
        consistency_label = QLabel("Consistency")
        consistency_label.setObjectName("statLabel")
        consistency_label.setFont(QFont("Segoe UI", 9))
        self.consistency_value = QLabel("100%")
        self.consistency_value.setObjectName("statValue")
        self.consistency_value.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        consistency_group.addWidget(consistency_label)
        consistency_group.addWidget(self.consistency_value)
        stats_layout.addLayout(consistency_group, 1)
        
        # Clicks
        clicks_group = QVBoxLayout()
        clicks_group.setSpacing(4)
        clicks_label = QLabel("Clicks")
        clicks_label.setObjectName("statLabel")
        clicks_label.setFont(QFont("Segoe UI", 9))
        self.clicks_value = QLabel("0")
        self.clicks_value.setObjectName("statValue")
        self.clicks_value.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        clicks_group.addWidget(clicks_label)
        clicks_group.addWidget(self.clicks_value)
        stats_layout.addLayout(clicks_group, 1)
        
        # Session Time
        time_group = QVBoxLayout()
        time_group.setSpacing(4)
        time_label = QLabel("Time")
        time_label.setObjectName("statLabel")
        time_label.setFont(QFont("Segoe UI", 9))
        self.time_value = QLabel("0s")
        self.time_value.setObjectName("statValue")
        self.time_value.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        time_group.addWidget(time_label)
        time_group.addWidget(self.time_value)
        stats_layout.addLayout(time_group, 1)
        
        content_layout.addLayout(stats_layout)
        
        # CPS Section
        cps_section = QVBoxLayout()
        cps_section.setSpacing(8)
        
        cps_label = QLabel("CPS")
        cps_label.setObjectName("sectionLabel")
        cps_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        cps_section.addWidget(cps_label)
        
        cps_layout = QHBoxLayout()
        cps_layout.setSpacing(8)
        
        self.cps_spinbox = QSpinBox()
        self.cps_spinbox.setObjectName("cpsSpinBox")
        self.cps_spinbox.setMinimum(1)
        self.cps_spinbox.setMaximum(500)
        self.cps_spinbox.setValue(10)
        self.cps_spinbox.valueChanged.connect(self.on_cps_changed)
        self.cps_spinbox.setMinimumHeight(32)
        self.cps_spinbox.setMaximumWidth(80)
        cps_layout.addWidget(self.cps_spinbox)
        
        self.cps_slider = QSlider(Qt.Orientation.Horizontal)
        self.cps_slider.setObjectName("cpsSlider")
        self.cps_slider.setMinimum(1)
        self.cps_slider.setMaximum(500)
        self.cps_slider.setValue(10)
        self.cps_slider.setMinimumHeight(4)
        self.cps_slider.sliderMoved.connect(self.on_slider_moved)
        self.cps_slider.valueChanged.connect(self.sync_spinbox)
        cps_layout.addWidget(self.cps_slider, 1)
        
        cps_section.addLayout(cps_layout)
        content_layout.addLayout(cps_section)
        
        # Hotkey Section
        hotkey_section = QVBoxLayout()
        hotkey_section.setSpacing(8)
        
        hotkey_label = QLabel("HOTKEY")
        hotkey_label.setObjectName("sectionLabel")
        hotkey_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        hotkey_section.addWidget(hotkey_label)
        
        hotkey_layout = QHBoxLayout()
        hotkey_layout.setSpacing(8)
        
        self.hotkey_display = QLineEdit()
        self.hotkey_display.setReadOnly(True)
        self.hotkey_display.setText("None")
        self.hotkey_display.setObjectName("hotkeyDisplay")
        self.hotkey_display.setMinimumHeight(32)
        hotkey_layout.addWidget(self.hotkey_display, 1)
        
        set_hotkey_btn = QPushButton("Set")
        set_hotkey_btn.setObjectName("setButton")
        set_hotkey_btn.clicked.connect(self.set_hotkey_mode)
        set_hotkey_btn.setMinimumHeight(32)
        set_hotkey_btn.setMaximumWidth(60)
        hotkey_layout.addWidget(set_hotkey_btn)
        
        hotkey_section.addLayout(hotkey_layout)
        
        # Mode Options
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(12)
        
        self.toggle_checkbox = QCheckBox("Toggle")
        self.toggle_checkbox.setObjectName("modeCheckbox")
        self.toggle_checkbox.setFont(QFont("Segoe UI", 9))
        mode_layout.addWidget(self.toggle_checkbox)
        
        reset_btn = QPushButton("Reset Stats")
        reset_btn.setObjectName("resetButton")
        reset_btn.clicked.connect(self.reset_stats)
        reset_btn.setFont(QFont("Segoe UI", 9))
        reset_btn.setMaximumWidth(100)
        reset_btn.setMinimumHeight(28)
        mode_layout.addWidget(reset_btn)
        
        mode_layout.addStretch()
        
        hotkey_section.addLayout(mode_layout)
        content_layout.addLayout(hotkey_section)
        
        # MISC Features
        misc_section = QVBoxLayout()
        misc_section.setSpacing(8)
        
        misc_label = QLabel("MISC")
        misc_label.setObjectName("sectionLabel")
        misc_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        misc_section.addWidget(misc_label)
        
        misc_options = QVBoxLayout()
        misc_options.setSpacing(6)
        
        self.mouse_click_checkbox = QCheckBox("Mouse Click")
        self.mouse_click_checkbox.setObjectName("miscCheckbox")
        self.mouse_click_checkbox.setFont(QFont("Segoe UI", 9))
        misc_options.addWidget(self.mouse_click_checkbox)
        
        self.visual_feedback_checkbox = QCheckBox("Visual Feedback")
        self.visual_feedback_checkbox.setObjectName("miscCheckbox")
        self.visual_feedback_checkbox.setFont(QFont("Segoe UI", 9))
        self.visual_feedback_checkbox.setChecked(True)
        misc_options.addWidget(self.visual_feedback_checkbox)
        
        self.auto_stop_checkbox = QCheckBox("Auto-stop on deactivate")
        self.auto_stop_checkbox.setObjectName("miscCheckbox")
        self.auto_stop_checkbox.setFont(QFont("Segoe UI", 9))
        self.auto_stop_checkbox.setChecked(False)
        misc_options.addWidget(self.auto_stop_checkbox)
        
        misc_section.addLayout(misc_options)
        content_layout.addLayout(misc_section)
        
        content_layout.addStretch()
        
        # Control Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        start_btn = QPushButton("START")
        start_btn.setObjectName("startButton")
        start_btn.clicked.connect(self.start_macro)
        start_btn.setMinimumHeight(40)
        start_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        button_layout.addWidget(start_btn)
        
        stop_btn = QPushButton("STOP")
        stop_btn.setObjectName("stopButton")
        stop_btn.clicked.connect(self.stop_macro)
        stop_btn.setMinimumHeight(40)
        stop_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        button_layout.addWidget(stop_btn)
        
        content_layout.addLayout(button_layout)
        
        content_widget.setLayout(content_layout)
        layout.addWidget(content_widget)
        
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
    def setup_styles(self):
        """Setup dark theme with smooth styling"""
        dark_stylesheet = """
        QMainWindow {
            background-color: #0d0d0d;
        }
        
        QWidget#mainWidget {
            background-color: #0d0d0d;
        }
        
        QWidget#headerWidget {
            background-color: #1a1a1a;
            border-radius: 0px;
        }
        
        QLabel#title {
            color: #ffffff;
            font-weight: bold;
        }
        
        QLabel#statusLabel {
            color: #4ade80;
            font-weight: bold;
            padding: 8px;
            background-color: #1a1a1a;
            border-radius: 6px;
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
        
        QLabel#statLabel {
            color: #888888;
            font-size: 9px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        QLabel#statValue {
            color: #4ade80;
            font-weight: bold;
        }
        
        QLabel#sectionLabel {
            color: #ffffff;
            font-weight: bold;
            letter-spacing: 1px;
            text-transform: uppercase;
        }
        
        QLineEdit#hotkeyDisplay {
            background-color: #1a1a1a;
            border: 1px solid #333333;
            border-radius: 4px;
            color: #ffffff;
            padding: 6px 10px;
            font-size: 12px;
        }
        
        QLineEdit#hotkeyDisplay:focus {
            border: 1px solid #4ade80;
            background-color: #1f1f1f;
        }
        
        QSpinBox#cpsSpinBox {
            background-color: #1a1a1a;
            border: 1px solid #333333;
            border-radius: 4px;
            color: #4ade80;
            padding: 4px;
            font-weight: bold;
        }
        
        QSpinBox#cpsSpinBox:focus {
            border: 1px solid #4ade80;
        }
        
        QSpinBox#cpsSpinBox::up-button, QSpinBox#cpsSpinBox::down-button {
            background-color: #333333;
            border: none;
        }
        
        QPushButton#setButton {
            background-color: #1a1a1a;
            color: #ffffff;
            border: 1px solid #333333;
            border-radius: 4px;
            font-weight: bold;
            font-size: 11px;
        }
        
        QPushButton#setButton:hover {
            background-color: #252525;
            border: 1px solid #4ade80;
        }
        
        QPushButton#setButton:pressed {
            background-color: #0f0f0f;
        }
        
        QPushButton#resetButton {
            background-color: #1a1a1a;
            color: #ffffff;
            border: 1px solid #333333;
            border-radius: 4px;
            font-weight: bold;
            font-size: 9px;
        }
        
        QPushButton#resetButton:hover {
            background-color: #252525;
            border: 1px solid #666666;
        }
        
        QPushButton#startButton {
            background-color: #4ade80;
            color: #000000;
            border: none;
            border-radius: 6px;
            font-weight: bold;
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
            border-radius: 6px;
            font-weight: bold;
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
            height: 4px;
            border-radius: 2px;
        }
        
        QSlider::handle:horizontal#cpsSlider {
            background-color: #4ade80;
            width: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }
        
        QSlider::handle:horizontal#cpsSlider:hover {
            background-color: #5ee096;
        }
        
        QSlider::sub-page:horizontal#cpsSlider {
            background-color: #4ade80;
            border-radius: 2px;
        }
        
        QCheckBox#modeCheckbox {
            color: #aaaaaa;
            spacing: 6px;
            font-size: 10px;
        }
        
        QCheckBox#modeCheckbox::indicator {
            width: 16px;
            height: 16px;
            border-radius: 3px;
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
        
        QCheckBox#miscCheckbox {
            color: #aaaaaa;
            spacing: 6px;
            font-size: 9px;
        }
        
        QCheckBox#miscCheckbox::indicator {
            width: 14px;
            height: 14px;
            border-radius: 2px;
            border: 1px solid #333333;
            background-color: #1a1a1a;
        }
        
        QCheckBox#miscCheckbox::indicator:checked {
            background-color: #4ade80;
            border: 1px solid #4ade80;
        }
        
        QCheckBox#miscCheckbox::indicator:hover {
            border: 1px solid #4ade80;
        }
        """
        
        self.setStyleSheet(dark_stylesheet)
        
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
        """Handle CPS spinbox change"""
        self.current_cps = self.cps_spinbox.value()
        self.cps_slider.blockSignals(True)
        self.cps_slider.setValue(self.current_cps)
        self.cps_slider.blockSignals(False)
    
    def on_slider_moved(self):
        """Handle CPS slider move"""
        self.cps_spinbox.blockSignals(True)
        self.cps_spinbox.setValue(self.cps_slider.value())
        self.cps_spinbox.blockSignals(False)
        self.current_cps = self.cps_slider.value()
    
    def sync_spinbox(self):
        """Sync spinbox with slider"""
        self.cps_spinbox.blockSignals(True)
        self.cps_spinbox.setValue(self.cps_slider.value())
        self.cps_spinbox.blockSignals(False)
        self.current_cps = self.cps_slider.value()
        
    def start_macro(self):
        """Start the macro"""
        if self.macro_active:
            return
        
        self.macro_active = True
        self.is_toggle_mode = self.toggle_checkbox.isChecked()
        self.session_timer.start(1000)
        
        use_mouse = self.mouse_click_checkbox.isChecked()
        self.worker.start_macro(self.current_cps, use_mouse=use_mouse)
        
    def stop_macro(self):
        """Stop the macro"""
        self.macro_active = False
        self.session_timer.stop()
        self.worker.stop_macro()
        
    def update_session_time(self):
        """Update session time"""
        self.session_time += 1
        mins = self.session_time // 60
        secs = self.session_time % 60
        if mins > 0:
            self.time_value.setText(f"{mins}m {secs}s")
        else:
            self.time_value.setText(f"{secs}s")
        
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
        percentage = int(consistency)
        self.consistency_value.setText(f"{percentage}%")
    
    def on_clicks_changed(self, clicks):
        """Update clicks display"""
        if clicks >= 1000:
            self.clicks_value.setText(f"{clicks // 1000}K")
        else:
            self.clicks_value.setText(str(clicks))
    
    def reset_stats(self):
        """Reset all statistics"""
        self.worker.reset_stats()
        self.consistency_value.setText("100%")
        self.clicks_value.setText("0")
        self.session_time = 0
        self.time_value.setText("0s")
        
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
