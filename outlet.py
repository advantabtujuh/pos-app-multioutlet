"""
outlet.py
Outlet Management CRUD Module
"""

import sys
import subprocess
import re
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QDialog,
    QLineEdit, QFormLayout, QMessageBox, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from db_manager import db
from widgets import get_font


# ==============================================================================
# FORM OUTLET DIALOG (TIDAK DISENTUH)
# ==============================================================================
class FormOutletDialog(QDialog):
    """Dialog for Add/Edit outlet."""

    def __init__(self, parent=None, data_edit=None):
        super().__init__(parent)
        self.data_edit = data_edit
        self.saved_id = None
        self.init_ui()

    def init_ui(self):
        is_edit = self.data_edit is not None
        self.setWindowTitle("✏️ Edit Outlet" if is_edit else "➕ Tambah Outlet Baru")
        self.setModal(True)
        self.resize(420, 350)
        self.setStyleSheet("background-color: #f4f6f9;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(12)

        # Form
        form = QFormLayout()
        form.setSpacing(10)

        self.input_kode = QLineEdit()
        self.input_kode.setPlaceholderText("Contoh: OL01, OL02")
        self.input_kode.setStyleSheet(self._input_style())

        self.input_nama = QLineEdit()
        self.input_nama.setPlaceholderText("Nama outlet")
        self.input_nama.setStyleSheet(self._input_style())

        self.input_alamat = QLineEdit()
        self.input_alamat.setPlaceholderText("Alamat lengkap outlet")
        self.input_alamat.setStyleSheet(self._input_style())

        self.input_ip = QLineEdit()
        self.input_ip.setPlaceholderText("Tailscale IP (contoh: 100.x.x.x)")
        self.input_ip.setStyleSheet(self._input_style())

        self.input_port = QLineEdit("3306")
        self.input_port.setPlaceholderText("Port MariaDB")
        self.input_port.setStyleSheet(self._input_style())

        form.addRow("🔑 Kode Outlet:", self.input_kode)
        form.addRow("🏪 Nama Outlet:", self.input_nama)
        form.addRow("📍 Alamat:", self.input_alamat)
        form.addRow("🌐 Tailscale IP:", self.input_ip)
        form.addRow("🔌 Port MariaDB:", self.input_port)
        layout.addLayout(form)

        # Fill data if editing
        if is_edit:
            self.input_kode.setText(self.data_edit['kode_outlet'])
            self.input_kode.setReadOnly(True)
            self.input_kode.setStyleSheet(self._input_style() + "background-color: #f1f2f6;")
            self.input_nama.setText(self.data_edit['nama_outlet'])
            self.input_alamat.setText(self.data_edit['alamat'])
            self.input_ip.setText(self.data_edit['tailscale_ip'])
            self.input_port.setText(str(self.data_edit['db_mariadb_port']))

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

    def proses_simpan(self):
        kode = self.input_kode.text().strip().upper()
        nama = self.input_nama.text().strip()
        alamat = self.input_alamat.text().strip()
        ip = self.input_ip.text().strip()
        port_str = self.input_port.text().strip() or "3306"

        if not kode or not nama:
            QMessageBox.warning(self, "Peringatan", "⚠️ Kode dan nama outlet wajib diisi!")
            return

        try:
            port = int(port_str)
        except ValueError:
            QMessageBox.warning(self, "Peringatan", "⚠️ Port harus berupa angka!")
            return

        conn = db.sqlite_conn()
        cursor = conn.cursor()
        try:
            if self.data_edit:
                cursor.execute(
                    "UPDATE master_outlet SET nama_outlet=?, alamat=?, tailscale_ip=?, db_mariadb_port=? WHERE id=?",
                    (nama, alamat, ip, port, self.data_edit['id'])
                )
                self.saved_id = self.data_edit['id']
            else:
                cursor.execute("SELECT id FROM master_outlet WHERE kode_outlet=?", (kode,))
                if cursor.fetchone():
                    QMessageBox.warning(self, "Peringatan", "⚠️ Kode outlet sudah terpakai!")
                    conn.close()
                    return

                outlet_id = db.generate_uuid()
                cursor.execute(
                    "INSERT INTO master_outlet (id, kode_outlet, nama_outlet, alamat, tailscale_ip, db_mariadb_port) VALUES (?,?,?,?,?,?)",
                    (outlet_id, kode, nama, alamat, ip, port)
                )
                self.saved_id = outlet_id

            conn.commit()
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"❌ Gagal menyimpan: {str(e)}")
        finally:
            conn.close()


# ==============================================================================
# OUTLET WIDGET
# ==============================================================================
class OutletWidget(QWidget):
    """Outlet management widget with table and CRUD buttons."""

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
        header = QLabel("🏪 Manajemen Outlet / Cabang")
        header.setFont(get_font(16, bold=True))
        header.setStyleSheet("color: #2c3e50;")
        layout.addWidget(header)

        sub = QLabel("Daftar outlet dengan koneksi Tailscale untuk monitoring pusat")
        sub.setFont(get_font(9))
        sub.setStyleSheet("color: #64748b;")
        layout.addWidget(sub)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_tambah = QPushButton("➕ Tambah Outlet")
        self.btn_edit = QPushButton("✏️ Edit Outlet")
        self.btn_hapus = QPushButton("🗑️ Hapus Outlet")
        self.btn_test = QPushButton("🔌 Test Koneksi")
        self.btn_refresh_status = QPushButton("🔄 Refresh Status") # Tombol baru

        styles = {
            self.btn_tambah: "background-color: #3498db; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_edit: "background-color: #f1c40f; color: black; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_hapus: "background-color: #e74c3c; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_test: "background-color: #1abc9c; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_refresh_status: "background-color: #9b59b6; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;", # Warna unung biar beda
        }
        for btn, style in styles.items():
            btn.setStyleSheet(style)
            btn.setCursor(Qt.PointingHandCursor)
            toolbar.addWidget(btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        # Kolom status diganti nama
        self.table.setHorizontalHeaderLabels([
            "ID Hidden", "🔑 Kode", "🏪 Nama Outlet", "📍 Alamat",
            "🌐 Tailscale IP", "🔌 Port", "📡 Status Koneksi"
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
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(3, 250)
        self.table.setColumnWidth(4, 140)
        self.table.setColumnWidth(5, 70)
        self.table.setColumnWidth(6, 120) # Diperlebar sedikit untuk teks status

        layout.addWidget(self.table)

        # Connections
        self.btn_tambah.clicked.connect(self.aksi_tambah)
        self.btn_edit.clicked.connect(self.aksi_edit)
        self.btn_hapus.clicked.connect(self.aksi_hapus)
        self.btn_test.clicked.connect(self.aksi_test_koneksi)
        self.btn_refresh_status.clicked.connect(self.aksi_refresh_status) # Konek tombol baru

    # --- METHOD DARI TAILSCALE.PY YANG DIADAPTASI ---
    
    def run_command(self, cmd):
        """Menjalankan perintah terminal dan mengembalikan outputnya"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None

    def get_tailscale_status_map(self):
        """Mengambil status tailscale dan memetakan IP -> Status dalam dictionary"""
        status_output = self.run_command("tailscale status")
        ip_status_map = {}
        
        if not status_output:
            return ip_status_map

        lines = status_output.split('\n')
        for line in lines:
            if not line.strip():
                continue
            
            parts = re.split(r'\s{2,}', line.strip())
            
            # Format output tailscale status: IP | Name | User | OS | Status
            if len(parts) >= 4:
                ip = parts[0]
                # parts[4] adalah status (idle, active), jika tidak ada berarti dia sendiri (local node) anggap active
                status = parts[4] if len(parts) > 4 else "active" 
                ip_status_map[ip] = status
                
        return ip_status_map

    # --- METHOD MODIFIKASI ---

    def muat_data_dari_db(self, target_highlight_id=None):
        self.table.setRowCount(0)

        # Auto-refresh: Ambil mapping status tailscale terlebih dahulu
        ts_status_map = self.get_tailscale_status_map()

        rows = db.execute_local(
            "SELECT id, kode_outlet, nama_outlet, alamat, tailscale_ip, db_mariadb_port, is_active FROM master_outlet ORDER BY kode_outlet",
            fetch_all=True
        )
        if not rows:
            return

        baris_target_idx = -1
        for idx, r in enumerate(rows):
            self.table.insertRow(idx)

            item_id = QTableWidgetItem()
            item_id.setData(Qt.UserRole, r['id'])
            self.table.setItem(idx, 0, item_id)

            self.table.setItem(idx, 1, QTableWidgetItem(str(r['kode_outlet'])))
            self.table.setItem(idx, 2, QTableWidgetItem(str(r['nama_outlet'])))
            self.table.setItem(idx, 3, QTableWidgetItem(str(r['alamat'])))
            
            ip_outlet = str(r['tailscale_ip'] or '-')
            self.table.setItem(idx, 4, QTableWidgetItem(ip_outlet))

            item_port = QTableWidgetItem(str(r['db_mariadb_port']))
            item_port.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 5, item_port)

            # --- LOGICA STATUS KONEKSI BARU ---
            if ip_outlet == '-':
                status_text = "No IP"
                color = "#95a5a6" # Abu-abu
            else:
                # Cocokkan IP outlet dengan hasil tailscale status
                status_text = ts_status_map.get(ip_outlet, "Offline")
                if "offline" in status_text.lower():
                    color = "#e74c3c" # Merah
                else:
                    color = "#2ecc71" # Hijau

            item_status = QTableWidgetItem(status_text.capitalize())
            item_status.setTextAlignment(Qt.AlignCenter)
            item_status.setForeground(QColor(color))
            item_status.setFont(get_font(10, bold=True))
            self.table.setItem(idx, 6, item_status)

            if target_highlight_id and r['id'] == target_highlight_id:
                baris_target_idx = idx

        if baris_target_idx != -1:
            self.table.setCurrentCell(baris_target_idx, 1)

    # --- METHOD TAMBAHAN ---

    def aksi_refresh_status(self):
        """Fungsi untuk refresh tabel (sekaligus auto-cek tailscale status) 
        dan mempertahankan posisi seleksi baris jika ada"""
        selected = self._get_selected_outlet(silent=True)
        target_id = selected['id'] if selected else None
        self.muat_data_dari_db(target_highlight_id=target_id)

    # --- METHOD BAWAAN YANG TIDAK DISENTUH ---

    def _get_selected_outlet(self, silent=False):
        row = self.table.currentRow()
        if row == -1:
            if not silent:
                QMessageBox.warning(self, "Peringatan", "⚠️ Silakan pilih outlet terlebih dahulu!")
            return None
        return {
            'id': self.table.item(row, 0).data(Qt.UserRole),
            'kode_outlet': self.table.item(row, 1).text(),
            'nama_outlet': self.table.item(row, 2).text(),
            'alamat': self.table.item(row, 3).text(),
            'tailscale_ip': self.table.item(row, 4).text(),
            'db_mariadb_port': int(self.table.item(row, 5).text())
        }

    def aksi_tambah(self):
        dialog = FormOutletDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.muat_data_dari_db(target_highlight_id=dialog.saved_id)

    def aksi_edit(self):
        data = self._get_selected_outlet()
        if not data:
            return
        dialog = FormOutletDialog(self, data_edit=data)
        if dialog.exec_() == QDialog.Accepted:
            self.muat_data_dari_db(target_highlight_id=dialog.saved_id)

    def aksi_hapus(self):
        data = self._get_selected_outlet()
        if not data:
            return

        reply = QMessageBox.question(
            self, "Konfirmasi",
            f"❓ Yakin hapus outlet '{data['kode_outlet']} - {data['nama_outlet']}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            db.execute_local("DELETE FROM master_outlet WHERE id=?", (data['id'],))
            current_user = getattr(self.parent_window, 'current_user', None)
            db.log_activity(
                current_user['id'] if current_user else None,
                current_user['username'] if current_user else 'SYSTEM',
                "DELETE_OUTLET",
                f"Menghapus outlet {data['kode_outlet']}"
            )
            self.muat_data_dari_db()

    def aksi_test_koneksi(self):
        data = self._get_selected_outlet()
        if not data:
            return

        ip = data['tailscale_ip']
        port = data['db_mariadb_port']

        if not ip:
            QMessageBox.warning(self, "Peringatan", "⚠️ Outlet ini belum memiliki Tailscale IP!")
            return

        QMessageBox.information(
            self, "Info",
            f"🔌 Test koneksi ke {ip}:{port}\n\n"
            f"(Fitur test koneksi penuh akan diimplementasikan saat MariaDB layer aktif)"
        )