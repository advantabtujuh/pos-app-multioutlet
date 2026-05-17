import sqlite3
import uuid
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QDialog,
    QLineEdit, QFormLayout, QMessageBox, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

DB_NAME = "pos_inventory.db"


def init_kategori_database():
    """Inisialisasi database kategori dan migrasi kolom baru otomatis."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kategori_satuan (
            id BLOB PRIMARY KEY
        )
    """)

    cursor.execute("PRAGMA table_info(kategori_satuan)")
    kolom_saat_ini = [info[1] for info in cursor.fetchall()]

    if "kode_kategori" not in kolom_saat_ini:
        cursor.execute("ALTER TABLE kategori_satuan ADD COLUMN kode_kategori TEXT NOT NULL DEFAULT ''")
    if "nama_kategori" not in kolom_saat_ini:
        cursor.execute("ALTER TABLE kategori_satuan ADD COLUMN nama_kategori TEXT NOT NULL DEFAULT ''")
    if "satuan" not in kolom_saat_ini:
        cursor.execute("ALTER TABLE kategori_satuan ADD COLUMN satuan TEXT NOT NULL DEFAULT ''")
    if "isi_satuan" not in kolom_saat_ini:
        cursor.execute("ALTER TABLE kategori_satuan ADD COLUMN isi_satuan INTEGER NOT NULL DEFAULT 1")

    conn.commit()
    conn.close()


def get_font(size, bold=False):
    """Return QFont dengan fallback universal untuk semua OS."""
    weight = QFont.Bold if bold else QFont.Normal
    for family in ["Arial", "Helvetica", "DejaVu Sans", "Liberation Sans", "Noto Sans"]:
        font = QFont(family, size, weight)
        if QFont(family).exactMatch() or font.exactMatch():
            return font
    return QFont("sans-serif", size, weight)


class FormKategoriDialog(QDialog):
    def __init__(self, parent=None, data_edit=None):
        super().__init__(parent)
        self.data_edit = data_edit
        self.init_ui()

    def init_ui(self):
        self.setFont(get_font(10))
        self.setWindowTitle("✏️ Edit Kategori & Satuan" if self.data_edit else "➕ Tambah Kategori & Satuan")
        self.resize(380, 260)
        self.setModal(True)
        self.setStyleSheet("background-color: #f4f6f9;")
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.input_kode = QLineEdit(self)
        self.input_nama = QLineEdit(self)
        self.input_satuan = QLineEdit(self)
        self.input_isi = QLineEdit(self)
        self.input_kode.setPlaceholderText("Contoh: KUD01, 101")
        self.input_nama.setPlaceholderText("Contoh: Susu Sapi Segar")
        self.input_satuan.setPlaceholderText("Contoh: CTN, Lusin, Pcs")
        self.input_isi.setPlaceholderText("Contoh: 40 (Jika CTN), 12 (Jika Lusin)")

        form_layout.addRow("🔑 Kode Kategori:", self.input_kode)
        form_layout.addRow("📁 Nama Kategori:", self.input_nama)
        form_layout.addRow("⚖️ Nama Satuan:", self.input_satuan)
        form_layout.addRow("🔢 Isi Satuan (Qty):", self.input_isi)
        layout.addLayout(form_layout)

        if self.data_edit:
            self.input_kode.setText(self.data_edit['kode_kategori'])
            self.input_kode.setReadOnly(True)
            self.input_nama.setText(self.data_edit['nama_kategori'])
            self.input_satuan.setText(self.data_edit['satuan'])
            self.input_isi.setText(str(self.data_edit['isi_satuan']))

        btn_layout = QHBoxLayout()
        self.btn_simpan = QPushButton("💾 Simpan", self)
        self.btn_batal = QPushButton("❌ Batal", self)
        self.btn_simpan.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 6px;")
        self.btn_batal.setStyleSheet("background-color: #e74c3c; color: white; padding: 6px;")
        btn_layout.addWidget(self.btn_simpan)
        btn_layout.addWidget(self.btn_batal)
        layout.addLayout(btn_layout)

        self.btn_simpan.clicked.connect(self.proses_simpan)
        self.btn_batal.clicked.connect(self.reject)

    def proses_simpan(self):
        kode = self.input_kode.text().strip()
        nama = self.input_nama.text().strip()
        satuan = self.input_satuan.text().strip()
        isi_str = self.input_isi.text().strip()
        if not kode or not nama or not satuan or not isi_str:
            QMessageBox.warning(self, "Peringatan", "⚠️ Semua field data harus diisi!")
            return
        try:
            isi_angka = int(isi_str)
            if isi_angka <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Peringatan", "⚠️ Isi Satuan harus berupa angka bulat positif!")
            return
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        if self.data_edit:
            id_bin = self.data_edit['id']
            cursor.execute(
                "UPDATE kategori_satuan SET kode_kategori = ?, nama_kategori = ?, satuan = ?, isi_satuan = ? WHERE id = ?",
                (kode, nama, satuan, isi_angka, id_bin)
            )
            self.saved_id = id_bin
        else:
            cursor.execute("SELECT id FROM kategori_satuan WHERE kode_kategori = ?", (kode,))
            if cursor.fetchone():
                QMessageBox.warning(self, "Peringatan", "⚠️ Kode Kategori sudah terpakai!")
                conn.close()
                return
            id_bytes = uuid.uuid4().bytes
            cursor.execute(
                "INSERT INTO kategori_satuan (id, kode_kategori, nama_kategori, satuan, isi_satuan) VALUES (?, ?, ?, ?, ?)",
                (id_bytes, kode, nama, satuan, isi_angka)
            )
            self.saved_id = id_bytes
        conn.commit()
        conn.close()
        self.accept()


class KategoriSatuanWidget(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.init_ui()
        self.muat_data_dari_db()

    def init_ui(self):
        self.setStyleSheet("background-color: #f4f6f9;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        header_label = QLabel("📁 Manajemen Kategori & Satuan Barang", self)
        header_label.setFont(get_font(16, bold=True))
        header_label.setStyleSheet("color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(header_label)

        toolbar_layout = QHBoxLayout()
        self.btn_tambah = QPushButton("➕ Tambah Data", self)
        self.btn_edit = QPushButton("✏️ Edit Data", self)
        self.btn_hapus = QPushButton("🗑️ Hapus Data", self)
        tombol_styles = {
            self.btn_tambah: "background-color: #3498db; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_edit: "background-color: #f1c40f; color: black; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_hapus: "background-color: #e74c3c; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;"
        }
        for btn, style in tombol_styles.items():
            btn.setStyleSheet(style)
            toolbar_layout.addWidget(btn)
        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID Hidden", "🔑 Kode Kategori", "📁 Nama Kategori", "⚖️ Nama Satuan", "🔢 Isi Satuan"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnHidden(0, True)
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
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        self.btn_tambah.clicked.connect(self.aksi_tambah)
        self.btn_edit.clicked.connect(self.aksi_edit)
        self.btn_hapus.clicked.connect(self.aksi_hapus)

    def muat_data_dari_db(self, target_highlight_id=None):
        self.table.setRowCount(0)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, kode_kategori, nama_kategori, satuan, isi_satuan FROM kategori_satuan")
        rows = cursor.fetchall()
        conn.close()
        baris_target_idx = -1
        for idx, (id_bin, kode, nama, satuan, isi) in enumerate(rows):
            self.table.insertRow(idx)
            item_id = QTableWidgetItem()
            item_id.setData(Qt.UserRole, id_bin)
            item_kode = QTableWidgetItem(kode)
            item_nama = QTableWidgetItem(nama)
            item_satuan = QTableWidgetItem(satuan)
            item_isi = QTableWidgetItem(str(isi))
            item_isi.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 0, item_id)
            self.table.setItem(idx, 1, item_kode)
            self.table.setItem(idx, 2, item_nama)
            self.table.setItem(idx, 3, item_satuan)
            self.table.setItem(idx, 4, item_isi)
            if target_highlight_id and id_bin == target_highlight_id:
                baris_target_idx = idx
        if baris_target_idx != -1:
            self.table.setCurrentCell(baris_target_idx, 1)
            self.table.scrollToItem(self.table.item(baris_target_idx, 1), QAbstractItemView.PositionAtCenter)

    def aksi_tambah(self):
        dialog = FormKategoriDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.muat_data_dari_db(target_highlight_id=dialog.saved_id)

    def aksi_edit(self):
        baris_pilihan = self.table.currentRow()
        if baris_pilihan == -1:
            QMessageBox.warning(self, "Peringatan", "⚠️ Silahkan pilih baris data di tabel yang ingin diedit!")
            return
        id_bin = self.table.item(baris_pilihan, 0).data(Qt.UserRole)
        kode = self.table.item(baris_pilihan, 1).text()
        nama = self.table.item(baris_pilihan, 2).text()
        satuan = self.table.item(baris_pilihan, 3).text()
        isi = int(self.table.item(baris_pilihan, 4).text())
        data_edit = {'id': id_bin, 'kode_kategori': kode, 'nama_kategori': nama, 'satuan': satuan, 'isi_satuan': isi}
        dialog = FormKategoriDialog(self, data_edit=data_edit)
        if dialog.exec_() == QDialog.Accepted:
            self.muat_data_dari_db(target_highlight_id=dialog.saved_id)

    def aksi_hapus(self):
        baris_pilihan = self.table.currentRow()
        if baris_pilihan == -1:
            QMessageBox.warning(self, "Peringatan", "⚠️ Silahkan pilih baris data di tabel yang ingin dihapus!")
            return
        id_bin = self.table.item(baris_pilihan, 0).data(Qt.UserRole)
        nama = self.table.item(baris_pilihan, 2).text()
        konfirmasi = QMessageBox.question(self, "Konfirmasi Hapus", f"❓ Apakah Anda yakin ingin menghapus kategori '{nama}'?", QMessageBox.Yes | QMessageBox.No)
        if konfirmasi == QMessageBox.Yes:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM kategori_satuan WHERE id = ?", (id_bin,))
            conn.commit()
            conn.close()
            self.muat_data_dari_db()
