"""
user.py
User Management CRUD Module
"""

import sys
import sqlite3
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QDialog,
    QLineEdit, QFormLayout, QMessageBox, QHeaderView, QComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from db_manager import db
from widgets import get_font


# ==============================================================================
# FORM USER DIALOG
# ==============================================================================
class FormUserDialog(QDialog):
    """Dialog for Add/Edit user."""

    ROLES = ["ADMIN", "MANAGER", "GUDANG", "KASIR"]

    def __init__(self, parent=None, data_edit=None):
        super().__init__(parent)
        self.data_edit = data_edit
        self.saved_id = None
        self.init_ui()

    def init_ui(self):
        is_edit = self.data_edit is not None
        self.setWindowTitle("✏️ Edit User" if is_edit else "➕ Tambah User Baru")
        self.setModal(True)
        self.resize(420, 380)
        self.setStyleSheet("background-color: #f4f6f9;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(12)

        # Form
        form = QFormLayout()
        form.setSpacing(10)

        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("Username unik")
        self.input_username.setStyleSheet(self._input_style())

        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("Password" if not is_edit else "Kosongkan jika tidak diubah")
        self.input_password.setEchoMode(QLineEdit.Password)
        self.input_password.setStyleSheet(self._input_style())

        self.input_nama = QLineEdit()
        self.input_nama.setPlaceholderText("Nama lengkap")
        self.input_nama.setStyleSheet(self._input_style())

        self.combo_role = QComboBox()
        self.combo_role.addItems(self.ROLES)
        self.combo_role.setStyleSheet(self._combo_style())

        self.combo_status = QComboBox()
        self.combo_status.addItems(["Aktif", "Non-Aktif"])
        self.combo_status.setStyleSheet(self._combo_style())

        form.addRow("🔑 Username:", self.input_username)
        form.addRow("🔒 Password:", self.input_password)
        form.addRow("👤 Nama Lengkap:", self.input_nama)
        form.addRow("🎭 Role:", self.combo_role)
        form.addRow("📌 Status:", self.combo_status)
        layout.addLayout(form)

        # Fill data if editing
        if is_edit:
            self.input_username.setText(self.data_edit['username'])
            self.input_username.setReadOnly(True)
            self.input_username.setStyleSheet(self._input_style() + "background-color: #f1f2f6;")
            self.input_nama.setText(self.data_edit['nama_lengkap'])
            self.combo_role.setCurrentText(self.data_edit['role'])
            self.combo_status.setCurrentIndex(0 if self.data_edit['is_active'] == 1 else 1)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_simpan = QPushButton("💾 Simpan")
        self.btn_simpan.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #27ae60; }
        """)
        self.btn_simpan.clicked.connect(self.proses_simpan)

        self.btn_batal = QPushButton("❌ Batal")
        self.btn_batal.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        self.btn_batal.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_simpan)
        btn_layout.addWidget(self.btn_batal)
        layout.addLayout(btn_layout)

    def _input_style(self):
        return """
            QLineEdit {
                padding: 8px;
                border: 1px solid #dcdde1;
                border-radius: 4px;
                background-color: white;
                font-size: 12px;
            }
            QLineEdit:focus { border: 1px solid #3498db; }
        """

    def _combo_style(self):
        return """
            QComboBox {
                padding: 8px;
                border: 1px solid #dcdde1;
                border-radius: 4px;
                background-color: white;
                font-size: 12px;
            }
            QComboBox:focus { border: 1px solid #3498db; }
        """

    def proses_simpan(self):
        username = self.input_username.text().strip()
        password = self.input_password.text()
        nama = self.input_nama.text().strip()
        role = self.combo_role.currentText()
        is_active = 1 if self.combo_status.currentIndex() == 0 else 0

        if not username or not nama:
            QMessageBox.warning(self, "Peringatan", "⚠️ Username dan nama lengkap wajib diisi!")
            return

        if not self.data_edit and not password:
            QMessageBox.warning(self, "Peringatan", "⚠️ Password wajib diisi untuk user baru!")
            return

        if not self.data_edit and len(password) < 4:
            QMessageBox.warning(self, "Peringatan", "⚠️ Password minimal 4 karakter!")
            return

        conn = db.sqlite_conn()
        cursor = conn.cursor()
        try:
            if self.data_edit:
                # Edit mode
                if password:
                    cursor.execute(
                        "UPDATE master_user SET password=?, nama_lengkap=?, role=?, is_active=? WHERE id=?",
                        (password, nama, role, is_active, self.data_edit['id'])
                    )
                else:
                    cursor.execute(
                        "UPDATE master_user SET nama_lengkap=?, role=?, is_active=? WHERE id=?",
                        (nama, role, is_active, self.data_edit['id'])
                    )
                self.saved_id = self.data_edit['id']
            else:
                # Add mode - check duplicate username
                cursor.execute("SELECT id FROM master_user WHERE username=?", (username,))
                if cursor.fetchone():
                    QMessageBox.warning(self, "Peringatan", "⚠️ Username sudah terpakai!")
                    conn.close()
                    return

                user_id = db.generate_uuid()
                cursor.execute(
                    "INSERT INTO master_user (id, username, password, nama_lengkap, role, is_active) VALUES (?,?,?,?,?,?)",
                    (user_id, username, password, nama, role, is_active)
                )
                self.saved_id = user_id

            conn.commit()
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"❌ Gagal menyimpan: {str(e)}")
        finally:
            conn.close()


# ==============================================================================
# USER WIDGET
# ==============================================================================
class UserWidget(QWidget):
    """User management widget with table and CRUD buttons."""

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.init_ui()
        self.muat_data_dari_db()

    def init_ui(self):
        self.setStyleSheet("background-color: #f4f6f9;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header = QLabel("👤 Manajemen User & Hak Akses")
        header.setFont(get_font(16, bold=True))
        header.setStyleSheet("color: #2c3e50;")
        layout.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_tambah = QPushButton("➕ Tambah User")
        self.btn_edit = QPushButton("✏️ Edit User")
        self.btn_hapus = QPushButton("🗑️ Hapus User")
        self.btn_reset = QPushButton("🔄 Reset Password")

        styles = {
            self.btn_tambah: "background-color: #3498db; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_edit: "background-color: #f1c40f; color: black; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_hapus: "background-color: #e74c3c; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_reset: "background-color: #9b59b6; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
        }
        for btn, style in styles.items():
            btn.setStyleSheet(style)
            btn.setCursor(Qt.PointingHandCursor)
            toolbar.addWidget(btn)

        toolbar.addStretch()

        self.input_cari = QLineEdit()
        self.input_cari.setPlaceholderText("Cari username / nama...")
        self.input_cari.setStyleSheet("padding: 8px; border: 1px solid #dcdde1; border-radius: 4px; background: white;")
        self.btn_cari = QPushButton("🔍 Cari")
        self.btn_cari.setStyleSheet("padding: 8px 12px; background-color: #34495e; color: white; border-radius: 4px;")

        toolbar.addWidget(QLabel("Cari:"))
        toolbar.addWidget(self.input_cari)
        toolbar.addWidget(self.btn_cari)
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID Hidden", "🔑 Username", "👤 Nama Lengkap", "🎭 Role",
            "📌 Status", "📅 Dibuat", "🕐 Login Terakhir"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnHidden(0, True)

        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8f9fa;
                gridline-color: #dcdde1;
                font-size: 13px;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: white;
                font-weight: bold;
                padding: 8px;
                border: 1px solid #34495e;
            }
            QTableWidget::item:selected {
                background-color: #3b82f6;
                color: white;
            }
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(5, 130)
        self.table.setColumnWidth(6, 130)

        layout.addWidget(self.table)

        # Connections
        self.btn_tambah.clicked.connect(self.aksi_tambah)
        self.btn_edit.clicked.connect(self.aksi_edit)
        self.btn_hapus.clicked.connect(self.aksi_hapus)
        self.btn_reset.clicked.connect(self.aksi_reset_password)
        self.btn_cari.clicked.connect(self.muat_data_dari_db)
        self.input_cari.returnPressed.connect(self.muat_data_dari_db)

    def muat_data_dari_db(self, target_highlight_id=None):
        self.table.setRowCount(0)
        keyword = self.input_cari.text().strip()

        query = """SELECT id, username, nama_lengkap, role, is_active, created_at, last_login
                   FROM master_user WHERE 1=1"""
        params = []
        if keyword:
            query += " AND (username LIKE ? OR nama_lengkap LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        query += " ORDER BY created_at DESC"

        rows = db.execute_local(query, params, fetch_all=True)
        if not rows:
            return

        baris_target_idx = -1
        for idx, r in enumerate(rows):
            self.table.insertRow(idx)

            item_id = QTableWidgetItem()
            item_id.setData(Qt.UserRole, r['id'])
            self.table.setItem(idx, 0, item_id)

            self.table.setItem(idx, 1, QTableWidgetItem(str(r['username'])))
            self.table.setItem(idx, 2, QTableWidgetItem(str(r['nama_lengkap'])))

            item_role = QTableWidgetItem(str(r['role']))
            item_role.setTextAlignment(Qt.AlignCenter)
            role_colors = {
                'ADMIN': '#e74c3c',
                'MANAGER': '#9b59b6',
                'GUDANG': '#f39c12',
                'KASIR': '#3498db'
            }
            item_role.setForeground(QColor(role_colors.get(r['role'], '#2c3e50')))
            item_role.setFont(get_font(10, bold=True))
            self.table.setItem(idx, 3, item_role)

            is_active = r['is_active']
            status_text = "Aktif" if is_active == 1 else "Non-Aktif"
            item_status = QTableWidgetItem(status_text)
            item_status.setTextAlignment(Qt.AlignCenter)
            item_status.setForeground(QColor("#2ecc71" if is_active == 1 else "#e74c3c"))
            self.table.setItem(idx, 4, item_status)

            self.table.setItem(idx, 5, QTableWidgetItem(str(r['created_at'] or '-')))
            self.table.setItem(idx, 6, QTableWidgetItem(str(r['last_login'] or 'Belum pernah')))

            if target_highlight_id and r['id'] == target_highlight_id:
                baris_target_idx = idx

        if baris_target_idx != -1:
            self.table.setCurrentCell(baris_target_idx, 1)

    def _get_selected_user(self):
        row = self.table.currentRow()
        if row == -1:
            QMessageBox.warning(self, "Peringatan", "⚠️ Silakan pilih user terlebih dahulu!")
            return None
        return {
            'id': self.table.item(row, 0).data(Qt.UserRole),
            'username': self.table.item(row, 1).text(),
            'nama_lengkap': self.table.item(row, 2).text(),
            'role': self.table.item(row, 3).text(),
            'is_active': 1 if self.table.item(row, 4).text() == "Aktif" else 0
        }

    def aksi_tambah(self):
        dialog = FormUserDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.muat_data_dari_db(target_highlight_id=dialog.saved_id)

    def aksi_edit(self):
        data = self._get_selected_user()
        if not data:
            return
        dialog = FormUserDialog(self, data_edit=data)
        if dialog.exec_() == QDialog.Accepted:
            self.muat_data_dari_db(target_highlight_id=dialog.saved_id)

    def aksi_hapus(self):
        data = self._get_selected_user()
        if not data:
            return

        # Prevent deleting yourself
        current_user = getattr(self.parent_window, 'current_user', None)
        if current_user and data['id'] == current_user['id']:
            QMessageBox.critical(self, "Ditolak", "❌ Tidak bisa menghapus akun sendiri!")
            return

        reply = QMessageBox.question(
            self, "Konfirmasi",
            f"❓ Yakin hapus user '{data['username']}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            db.execute_local("DELETE FROM master_user WHERE id=?", (data['id'],))
            db.log_activity(
                current_user['id'] if current_user else None,
                current_user['username'] if current_user else 'SYSTEM',
                "DELETE_USER",
                f"Menghapus user {data['username']}"
            )
            self.muat_data_dari_db()

    def aksi_reset_password(self):
        data = self._get_selected_user()
        if not data:
            return

        from PyQt5.QtWidgets import QInputDialog
        new_pass, ok = QInputDialog.getText(
            self, "Reset Password",
            f"Masukkan password baru untuk '{data['username']}':",
            QLineEdit.Password
        )
        if ok and new_pass:
            if len(new_pass) < 4:
                QMessageBox.warning(self, "Peringatan", "⚠️ Password minimal 4 karakter!")
                return
            db.execute_local(
                "UPDATE master_user SET password=? WHERE id=?",
                (new_pass, data['id'])
            )
            current_user = getattr(self.parent_window, 'current_user', None)
            db.log_activity(
                current_user['id'] if current_user else None,
                current_user['username'] if current_user else 'SYSTEM',
                "RESET_PASSWORD",
                f"Reset password user {data['username']}"
            )
            QMessageBox.information(self, "Sukses", f"✅ Password '{data['username']}' berhasil direset!")
