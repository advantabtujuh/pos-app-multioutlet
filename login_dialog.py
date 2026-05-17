"""
login_dialog.py
Login Dialog + First Time Setup Wizard
"""

import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFormLayout, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from db_manager import db
from config_manager import config
from widgets import get_font


# ==============================================================================
# FIRST TIME SETUP WIZARD
# ==============================================================================
class FirstTimeSetupDialog(QDialog):
    """Wizard to create the first admin user when database is empty."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔧 First Time Setup - Buat Admin Pertama")
        self.setModal(True)
        self.resize(450, 380)
        self.setStyleSheet("background-color: #f4f6f9;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        # Header
        header = QLabel("🚀 Selamat Datang!")
        header.setFont(get_font(18, bold=True))
        header.setStyleSheet("color: #2c3e50;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        sub = QLabel("Database baru terdeteksi. Silakan buat akun admin pertama.")
        sub.setFont(get_font(10))
        sub.setStyleSheet("color: #64748b;")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #e2e8f0;")
        line.setFixedHeight(1)
        layout.addWidget(line)

        # Form
        form = QFormLayout()
        form.setSpacing(12)

        self.input_nama = QLineEdit()
        self.input_nama.setPlaceholderText("Nama lengkap admin")
        self.input_nama.setStyleSheet(self._input_style())

        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("Username login")
        self.input_username.setStyleSheet(self._input_style())

        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("Password")
        self.input_password.setEchoMode(QLineEdit.Password)
        self.input_password.setStyleSheet(self._input_style())

        self.input_confirm = QLineEdit()
        self.input_confirm.setPlaceholderText("Konfirmasi password")
        self.input_confirm.setEchoMode(QLineEdit.Password)
        self.input_confirm.setStyleSheet(self._input_style())

        form.addRow("👤 Nama Lengkap:", self.input_nama)
        form.addRow("🔑 Username:", self.input_username)
        form.addRow("🔒 Password:", self.input_password)
        form.addRow("🔒 Konfirmasi:", self.input_confirm)
        layout.addLayout(form)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_simpan = QPushButton("💾 Simpan & Lanjutkan")
        self.btn_simpan.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #27ae60; }
        """)
        self.btn_simpan.setCursor(Qt.PointingHandCursor)
        self.btn_simpan.clicked.connect(self.proses_simpan)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_simpan)
        layout.addLayout(btn_layout)

        # Auto-focus nama
        self.input_nama.setFocus()

    def _input_style(self):
        return """
            QLineEdit {
                padding: 8px;
                border: 1px solid #dcdde1;
                border-radius: 4px;
                background-color: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """

    def proses_simpan(self):
        nama = self.input_nama.text().strip()
        username = self.input_username.text().strip()
        password = self.input_password.text()
        confirm = self.input_confirm.text()

        if not nama or not username or not password:
            QMessageBox.warning(self, "Peringatan", "⚠️ Semua field wajib diisi!")
            return

        if password != confirm:
            QMessageBox.warning(self, "Peringatan", "⚠️ Password dan konfirmasi tidak cocok!")
            self.input_password.clear()
            self.input_confirm.clear()
            self.input_password.setFocus()
            return

        if len(password) < 4:
            QMessageBox.warning(self, "Peringatan", "⚠️ Password minimal 4 karakter!")
            return

        # Insert admin user
        user_id = db.generate_uuid()
        db.execute_local(
            """INSERT INTO master_user (id, username, password, nama_lengkap, role, is_active)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (user_id, username, password, nama, "ADMIN")
        )

        QMessageBox.information(self, "Sukses", "✅ Admin pertama berhasil dibuat!\nSilakan login.")
        self.accept()


# ==============================================================================
# LOGIN DIALOG
# ==============================================================================
class LoginDialog(QDialog):
    """Login screen. Returns user data on success."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.user_data = None
        self.setWindowTitle("🔐 Login POS")
        self.setModal(True)
        self.resize(400, 320)
        self.setStyleSheet("background-color: #f4f6f9;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 35, 35, 35)
        layout.setSpacing(15)

        # App title
        title = QLabel("🏪 KUD TANIMAKMUR POS APP")
        title.setFont(get_font(22, bold=True))
        title.setStyleSheet("color: #2c3e50;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("POS & Inventory System")
        subtitle.setFont(get_font(10))
        subtitle.setStyleSheet("color: #64748b;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #e2e8f0;")
        line.setFixedHeight(1)
        layout.addWidget(line)

        layout.addSpacing(10)

        # Form
        form = QFormLayout()
        form.setSpacing(12)

        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("Username")
        self.input_username.setStyleSheet(self._input_style())

        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("Password")
        self.input_password.setEchoMode(QLineEdit.Password)
        self.input_password.setStyleSheet(self._input_style())

        form.addRow("👤 Username:", self.input_username)
        form.addRow("🔒 Password:", self.input_password)
        layout.addLayout(form)

        layout.addSpacing(10)

        # Login button
        self.btn_login = QPushButton("🔐 Login")
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #1a5276; }
        """)
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.clicked.connect(self.proses_login)
        layout.addWidget(self.btn_login)

        # Info label
        self.lbl_info = QLabel("")
        self.lbl_info.setAlignment(Qt.AlignCenter)
        self.lbl_info.setStyleSheet("color: #e74c3c; font-size: 11px;")
        layout.addWidget(self.lbl_info)

        layout.addStretch()

        # Footer
        footer = QLabel("© 2026 KUD TANI MAKMUR ")
        footer.setFont(get_font(8))
        footer.setStyleSheet("color: #94a3b8;")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

        # Enter key shortcut
        self.input_password.returnPressed.connect(self.proses_login)
        self.input_username.returnPressed.connect(self.input_password.setFocus)

        # Auto-focus username
        self.input_username.setFocus()

    def _input_style(self):
        return """
            QLineEdit {
                padding: 10px;
                border: 1px solid #dcdde1;
                border-radius: 4px;
                background-color: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
        """

    def proses_login(self):
        username = self.input_username.text().strip()
        password = self.input_password.text()

        if not username or not password:
            self.lbl_info.setText("⚠️ Username dan password wajib diisi!")
            return

        # Validate against SQLite
        result = db.execute_local(
            """SELECT id, username, nama_lengkap, role, outlet_id, is_active
               FROM master_user WHERE username = ? AND password = ? AND is_active = 1""",
            (username, password), fetch_one=True
        )

        if result is None:
            self.lbl_info.setText("❌ Username atau password salah!")
            self.input_password.clear()
            self.input_password.setFocus()
            return

        # Update last login
        db.execute_local(
            "UPDATE master_user SET last_login = datetime('now') WHERE id = ?",
            (result['id'],)
        )

        # Log activity
        db.log_activity(result['id'], username, "LOGIN", "User berhasil login")

        # Build user data dict
        self.user_data = {
            'id': result['id'],
            'username': result['username'],
            'nama_lengkap': result['nama_lengkap'],
            'role': result['role'],
            'outlet_id': result['outlet_id'],
            'is_active': result['is_active']
        }

        self.accept()


# ==============================================================================
# PUBLIC API
# ==============================================================================
def run_login_flow(parent=None):
    """
    Run the complete login flow:
    1. Check if users exist
    2. If not, show FirstTimeSetupDialog
    3. Show LoginDialog
    4. Return user_data dict or None
    """
    # Step 1: Check if any user exists
    if not db.has_users():
        wizard = FirstTimeSetupDialog(parent)
        if wizard.exec_() != QDialog.Accepted:
            return None  # User cancelled setup

    # Step 2: Show login dialog
    login = LoginDialog(parent)
    if login.exec_() == QDialog.Accepted:
        return login.user_data
    return None
