"""
F-Spam Macro - High-performance keyboard macro for rapid clicking
Python 3.14.0
"""

import sys
import threading
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSpinBox, QCheckBox, QPushButton, QLineEdit, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor
from pynput.keyboard import Key, Controller, Listener
from pynput import mouse


class MacroWorker(QObject):
    """Worker thread for macro execution"""
    status_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.keyboard = Controller()
        self.mouse_controller = mouse.Controller()
        self.is_running = False
        self.thread = None
        
    def start_macro(self, key_char, cps, use_mouse):
        """Start the macro in a separate thread"""
        if self.is_running:
            return
        
        self.is_running = True
        self.thread = threading.Thread(
            target=self._run_macro,
            args=(key_char, cps, use_mouse),
            daemon=True
        )
        self.thread.start()
        
    def _run_macro(self, key_char, cps, use_mouse):
        """Execute the macro loop"""
        delay = 1.0 / cps if cps > 0 else 0.001
        
        try:
            self.status_changed.emit("🟢 RUNNING")
            
            while self.is_running:
                try:
                    if use_mouse:
                        self.mouse_controller.click()
                    else:
                        self.keyboard.press(key_char)
                        self.keyboard.release(key_char)
                    
                    # High-precision sleep
                    time.sleep(delay)
                except Exception as e:
                    self.status_changed.emit(f"❌ Error: {str(e)}")
                    self.is_running = False
                    break
                    
        except Exception as e:
            self.status_changed.emit(f"❌ Error: {str(e)}")
        finally:
            self.is_running = False
            self.status_changed.emit("🔴 STOPPED")
    
    def stop_macro(self):
        """Stop the macro"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1)


class FSpamMacro(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = MacroWorker()
        self.worker.status_changed.connect(self.update_status)
        
        self.hotkey = None
        self.listening = False
        self.is_toggle_mode = False
        self.macro_active = False
        self.listener = None
        
        self.init_ui()
        self.start_listener()
        
    def init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle("F-Spam Macro - High Performance")
        self.setGeometry(100, 100, 500, 500)
        
        # Main widget
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("F-SPAM MACRO")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Hotkey Section
        hotkey_group = QGroupBox("Hotkey Settings")
        hotkey_layout = QVBoxLayout()
        
        hotkey_label = QLabel("Press desired hotkey (or click 'Set Hotkey' and press a key):")
        hotkey_layout.addWidget(hotkey_label)
        
        hotkey_button_layout = QHBoxLayout()
        self.hotkey_display = QLineEdit()
        self.hotkey_display.setReadOnly(True)
        self.hotkey_display.setText("Not Set")
        self.hotkey_display.setPlaceholderText("Press a key or click Set Hotkey")
        hotkey_button_layout.addWidget(QLabel("Current Hotkey:"))
        hotkey_button_layout.addWidget(self.hotkey_display)
        hotkey_layout.addLayout(hotkey_button_layout)
        
        set_hotkey_btn = QPushButton("Set Hotkey")
        set_hotkey_btn.clicked.connect(self.set_hotkey_mode)
        hotkey_layout.addWidget(set_hotkey_btn)
        
        hotkey_group.setLayout(hotkey_layout)
        layout.addWidget(hotkey_group)
        
        # Mode Section
        mode_group = QGroupBox("Mode Settings")
        mode_layout = QVBoxLayout()
        
        self.toggle_checkbox = QCheckBox("Toggle Mode (Press once to start, again to stop)")
        self.toggle_checkbox.setChecked(False)
        self.toggle_checkbox.stateChanged.connect(self.update_toggle_mode)
        mode_layout.addWidget(self.toggle_checkbox)
        
        self.mouse_checkbox = QCheckBox("Use Mouse Click instead of F key")
        self.mouse_checkbox.setChecked(False)
        mode_layout.addWidget(self.mouse_checkbox)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # CPS Section
        cps_group = QGroupBox("Performance Settings")
        cps_layout = QHBoxLayout()
        
        cps_label = QLabel("Clicks Per Second (CPS):")
        cps_layout.addWidget(cps_label)
        
        self.cps_spinbox = QSpinBox()
        self.cps_spinbox.setMinimum(1)
        self.cps_spinbox.setMaximum(1000)
        self.cps_spinbox.setValue(10)
        self.cps_spinbox.setToolTip("Higher values = faster clicking (1-1000 CPS)")
        cps_layout.addWidget(self.cps_spinbox)
        
        cps_group.setLayout(cps_layout)
        layout.addWidget(cps_group)
        
        # Status Section
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("🔴 STOPPED")
        status_font = QFont()
        status_font.setPointSize(14)
        status_font.setBold(True)
        self.status_label.setFont(status_font)
        status_layout.addWidget(self.status_label)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Control Buttons
        button_layout = QHBoxLayout()
        
        start_btn = QPushButton("Start")
        start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        start_btn.clicked.connect(self.start_macro)
        button_layout.addWidget(start_btn)
        
        stop_btn = QPushButton("Stop")
        stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 10px;")
        stop_btn.clicked.connect(self.stop_macro)
        button_layout.addWidget(stop_btn)
        
        layout.addLayout(button_layout)
        
        # Info
        info_label = QLabel(
            "💡 Info: Set a hotkey to toggle macro on/off during gameplay.\n"
            "🎮 Adjust CPS to your needs. Higher = faster clicking.\n"
            "⚡ Performance optimized for rapid clicking."
        )
        info_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
    def set_hotkey_mode(self):
        """Enter hotkey setting mode"""
        self.hotkey_display.setText("Listening... (Press any key)")
        self.listening = True
        
    def on_press(self, key):
        """Handle key press for hotkey detection"""
        if not self.listening:
            return
        
        try:
            # Try to get char representation
            if hasattr(key, 'char'):
                key_str = key.char.upper() if key.char else str(key)
            else:
                key_str = str(key).replace("Key.", "").upper()
            
            self.hotkey = key
            self.hotkey_display.setText(key_str)
            self.listening = False
        except Exception as e:
            self.hotkey_display.setText(f"Error: {str(e)}")
            self.listening = False
            
    def on_release(self, key):
        """Handle key release"""
        if self.listening:
            return True
        
        # Check if hotkey is pressed during macro operation
        if self.hotkey and key == self.hotkey:
            if self.is_toggle_mode:
                if self.macro_active:
                    self.stop_macro()
                else:
                    self.start_macro()
            else:
                if not self.macro_active:
                    self.start_macro()
                else:
                    self.stop_macro()
        
        return True
    
    def start_listener(self):
        """Start the global keyboard listener"""
        self.listener = Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()
        
    def start_macro(self):
        """Start the macro"""
        if self.macro_active:
            return
        
        self.macro_active = True
        use_mouse = self.mouse_checkbox.isChecked()
        cps = self.cps_spinbox.value()
        
        self.worker.start_macro('f', cps, use_mouse)
        
    def stop_macro(self):
        """Stop the macro"""
        self.macro_active = False
        self.worker.stop_macro()
        
    def update_status(self, status):
        """Update status label"""
        self.status_label.setText(status)
        
    def update_toggle_mode(self):
        """Update toggle mode"""
        self.is_toggle_mode = self.toggle_checkbox.isChecked()
        
    def closeEvent(self, event):
        """Clean up on close"""
        self.stop_macro()
        if self.listener:
            self.listener.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    macro = FSpamMacro()
    macro.show()
    sys.exit(app.exec())
