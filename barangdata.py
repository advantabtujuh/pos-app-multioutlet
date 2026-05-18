import sys
import sqlite3
import uuid
import os
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
                             QAbstractItemView, QHeaderView, QMessageBox, QDialog, 
                             QFormLayout, QFileDialog, QComboBox, QCheckBox, QDateEdit,
                             QTabWidget, QMainWindow, QApplication)
from PyQt5.QtCore import Qt, QDate, QSizeF
from PyQt5.QtGui import QTextDocument, QColor
from widgets import get_font
from PyQt5.QtPrintSupport import QPrinter

DB_NAME = "pos_inventory.db"

def init_barang_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS master_barang (id BLOB PRIMARY KEY)")
    cursor.execute("PRAGMA table_info(master_barang)")
    kolom_master = [info[1] for info in cursor.fetchall()]

    fields = [
        ("kode_kategori", "TEXT"), ("nama_kategori", "TEXT"), ("kode_barang", "TEXT"), ("kode_barcode", "TEXT"),
        ("nama_barang", "TEXT"), ("satuan", "TEXT"), ("isi_satuan", "INTEGER"), ("harga_beli_1", "REAL"),
        ("margin_1", "REAL"), ("harga_jual_1", "REAL"), ("harga_beli_2", "REAL"), ("margin_2", "REAL"),
        ("harga_jual_2", "REAL"), ("qty_1", "INTEGER"), ("harga_jual_bertingkat_1", "REAL"),
        ("qty_2", "INTEGER"), ("harga_jual_bertingkat_2", "REAL"), ("qty_3", "INTEGER"),
        ("harga_jual_bertingkat_3", "REAL"), ("is_promo", "TEXT"), ("tanggal_awal_promo", "TEXT"),
        ("tanggal_akhir_promo", "TEXT"), ("harga_jual_promo", "REAL"), ("minimal_stok", "INTEGER"),
        ("stok_isi", "INTEGER"), ("nilai_persediaan", "REAL"), ("keterangan", "TEXT")
    ]
    for name, typ in fields:
        if name not in kolom_master:
            cursor.execute(f"ALTER TABLE master_barang ADD COLUMN {name} {typ} NOT NULL DEFAULT " + ("''" if typ == "TEXT" else "0" if typ == "INTEGER" else "0.0"))
    conn.commit()
    conn.close()

class FormBarangDialog(QDialog):
    def __init__(self, parent=None, data_edit=None):
        super().__init__(parent)
        self.data_edit, self.list_kategori_data = data_edit, []
        self.init_ui()
        self.muat_kombobox_kategori()

    def init_ui(self):
        self.setFont(get_font(9, bold=False))
        self.setWindowTitle("✏️ Edit Spesifikasi Barang" if self.data_edit else "➕ Tambah Data Barang Baru")
        self.resize(550, 450)
        self.setModal(True)
        self.setStyleSheet("background-color: #f4f6f9;")

        layout_mutlak = QVBoxLayout(self)
        layout_mutlak.setContentsMargins(25, 25, 25, 25)
        layout_mutlak.setSpacing(12)
        self.tabs = QTabWidget(self)

        # TAB 1: DATA DASAR
        tab_dasar = QWidget()
        layout_tab1 = QFormLayout(tab_dasar)
        layout_tab1.setSpacing(10)
        self.combo_kategori = QComboBox(self)
        self.combo_kategori.setStyleSheet(self._combo_style())
        self.combo_kategori.currentIndexChanged.connect(self.on_kategori_changed)
        self.input_kb = QLineEdit(self)
        self.input_kb.setReadOnly(True)
        self.input_kb.setStyleSheet("background-color: #f1f2f6; font-weight: bold; padding: 8px; border: 1px solid #dcdde1; border-radius: 4px;")
        self.input_barcode, self.input_nb, self.input_satuan, self.input_isi = QLineEdit(self), QLineEdit(self), QLineEdit(self), QLineEdit(self)
        self.input_barcode.setStyleSheet(self._input_style())
        self.input_nb.setStyleSheet(self._input_style())
        self.input_satuan.setStyleSheet(self._input_style())
        self.input_isi.setStyleSheet(self._input_style())
        self.input_barcode.setPlaceholderText("Scan atau ketik barcode")
        self.input_nb.setPlaceholderText("Nama lengkap barang")
        self.input_satuan.setPlaceholderText("CTN, PCS, Lusin...")
        self.input_isi.setPlaceholderText("Jumlah isi per satuan")
        layout_tab1.addRow("📁 Pilih Kategori:", self.combo_kategori)
        layout_tab1.addRow("🔑 Kode Barang:", self.input_kb)
        layout_tab1.addRow("║║ Barcode:", self.input_barcode)
        layout_tab1.addRow("🏷️ Nama Barang:", self.input_nb)
        layout_tab1.addRow("⚖️ Satuan Unit:", self.input_satuan)
        layout_tab1.addRow("🔢 Isi Satuan (Qty):", self.input_isi)

        # TAB 2: SKEMA HARGA & GROSIR
        tab_harga = QWidget()
        layout_tab2 = QFormLayout(tab_harga)
        layout_tab2.setSpacing(10)
        self.input_hb1, self.input_m1, self.input_hj1 = QLineEdit(self), QLineEdit(self), QLineEdit(self)
        self.input_hb2 = QLineEdit(self)
        self.input_hb2.setReadOnly(True)
        self.input_hb2.setStyleSheet("background-color: #f1f2f6; padding: 8px; border: 1px solid #dcdde1; border-radius: 4px;")
        self.input_m2, self.input_hj2 = QLineEdit(self), QLineEdit(self)

        self.input_isi.textChanged.connect(self.hitung_level_2_otomatis)
        self.input_hb1.textChanged.connect(self.hitung_level_1_via_margin)
        self.input_hb1.textChanged.connect(self.hitung_level_2_otomatis)
        self.input_m1.textChanged.connect(self.hitung_level_1_via_margin)
        self.input_hj1.textChanged.connect(self.hitung_level_1_via_harga_jual)
        self.input_m2.textChanged.connect(self.hitung_level_2_via_margin)
        self.input_hj2.textChanged.connect(self.hitung_level_2_via_harga_jual)

        self.input_hb1.setStyleSheet(self._input_style())
        self.input_m1.setStyleSheet(self._input_style())
        self.input_hj1.setStyleSheet(self._input_style())
        self.input_m2.setStyleSheet(self._input_style())
        self.input_hj2.setStyleSheet(self._input_style())
        self.input_hb1.setPlaceholderText("0")
        self.input_m1.setPlaceholderText("0")
        self.input_hj1.setPlaceholderText("0")
        self.input_m2.setPlaceholderText("0")
        self.input_hj2.setPlaceholderText("0")

        layout_tab2.addRow(QLabel("<b>[HARGA UNIT UTAMA]</b>"))
        layout_tab2.addRow("📥 Harga Beli (HB1):", self.input_hb1)
        layout_tab2.addRow("📈 Margin % (M1):", self.input_m1)
        layout_tab2.addRow("💵 Harga Jual (HJ1):", self.input_hj1)
        layout_tab2.addRow(QLabel("<b>[HARGA ECERAN PCS]</b>"))
        layout_tab2.addRow("📥 Harga Beli Ecer (HB2):", self.input_hb2)
        layout_tab2.addRow("📈 Margin Ecer % (M2):", self.input_m2)
        layout_tab2.addRow("💵 Harga Jual Ecer (HJ2):", self.input_hj2)

        self.input_qty1, self.input_hjb1, self.input_qty2, self.input_hjb2, self.input_qty3, self.input_hjb3 = QLineEdit("0", self), QLineEdit("0", self), QLineEdit("0", self), QLineEdit("0", self), QLineEdit("0", self), QLineEdit("0", self)
        self.input_qty1.setStyleSheet(self._input_style())
        self.input_hjb1.setStyleSheet(self._input_style())
        self.input_qty2.setStyleSheet(self._input_style())
        self.input_hjb2.setStyleSheet(self._input_style())
        self.input_qty3.setStyleSheet(self._input_style())
        self.input_hjb3.setStyleSheet(self._input_style())
        h1, h2, h3 = QHBoxLayout(), QHBoxLayout(), QHBoxLayout()
        h1.addWidget(QLabel("Min Qty 1:")); h1.addWidget(self.input_qty1); h1.addWidget(QLabel("Harga JHB1:")); h1.addWidget(self.input_hjb1)
        h2.addWidget(QLabel("Min Qty 2:")); h2.addWidget(self.input_qty2); h2.addWidget(QLabel("Harga JHB2:")); h2.addWidget(self.input_hjb2)
        h3.addWidget(QLabel("Min Qty 3:")); h3.addWidget(self.input_qty3); h3.addWidget(QLabel("Harga JHB3:")); h3.addWidget(self.input_hjb3)
        layout_tab2.addRow("📋 Level 1:", h1); layout_tab2.addRow("📋 Level 2:", h2); layout_tab2.addRow("📋 Level 3:", h3)

        # TAB 3: PROMO & STOK
        tab_promo_stok = QWidget()
        layout_tab3 = QFormLayout(tab_promo_stok)
        layout_tab3.setSpacing(10)
        self.check_promo = QCheckBox("Aktifkan Skema Harga Promo POS", self)
        self.check_promo.toggled.connect(self.on_check_promo_toggled)
        self.date_awal, self.date_akhir = QDateEdit(QDate.currentDate(), self), QDateEdit(QDate.currentDate(), self)
        self.date_awal.setCalendarPopup(True); self.date_akhir.setCalendarPopup(True)
        self.input_hjpromo = QLineEdit("0", self)
        self.input_minstok, self.input_stok, self.input_persediaan = QLineEdit("0", self), QLineEdit("0", self), QLineEdit("0", self)
        self.input_persediaan.setReadOnly(True); self.input_persediaan.setStyleSheet("background-color: #f1f2f6; font-weight: bold; padding: 8px; border: 1px solid #dcdde1; border-radius: 4px;")
        self.input_ket = QLineEdit(self)
        self.input_hjpromo.setStyleSheet(self._input_style())
        self.input_minstok.setStyleSheet(self._input_style())
        self.input_stok.setStyleSheet(self._input_style())
        self.input_ket.setStyleSheet(self._input_style())
        self.input_ket.setPlaceholderText("Keterangan tambahan...")

        self.input_stok.textChanged.connect(self.hitung_nilai_persediaan_gudang)
        self.input_hb1.textChanged.connect(self.hitung_nilai_persediaan_gudang)

        h_tgl = QHBoxLayout()
        h_tgl.addWidget(QLabel("TGL1:")); h_tgl.addWidget(self.date_awal); h_tgl.addWidget(QLabel("s/d TGL2:")); h_tgl.addWidget(self.date_akhir)
        layout_tab3.addRow(self.check_promo)
        layout_tab3.addRow("📅 Masa Promo:", h_tgl)
        layout_tab3.addRow("💰 Harga Promo:", self.input_hjpromo)
        layout_tab3.addRow("⚠️ Min Stok:", self.input_minstok)
        layout_tab3.addRow("📦 Total Stok Pcs:", self.input_stok)
        layout_tab3.addRow("💎 Nilai Aset:", self.input_persediaan)
        layout_tab3.addRow("📝 Keterangan:", self.input_ket)

        self.tabs.addTab(tab_dasar, "📁 Data Dasar")
        self.tabs.addTab(tab_harga, "💰 Harga & Grosir")
        self.tabs.addTab(tab_promo_stok, "⏳ Promo & Stok")
        layout_mutlak.addWidget(self.tabs)

        btn_layout = QHBoxLayout()
        self.btn_simpan, self.btn_batal = QPushButton("💾 Simpan", self), QPushButton("❌ Batal", self)
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
        self.btn_batal.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_simpan)
        btn_layout.addWidget(self.btn_batal)
        layout_mutlak.addLayout(btn_layout)

        self.btn_simpan.clicked.connect(self.proses_simpan_barang)
        self.btn_batal.clicked.connect(self.reject)

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

    def muat_kombobox_kategori(self):
        self.combo_kategori.blockSignals(True)
        self.combo_kategori.clear()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT kode_kategori, nama_kategori, satuan, isi_satuan FROM kategori_satuan")
        for k_kod, k_nam, k_sat, k_isi in cursor.fetchall():
            self.combo_kategori.addItem(f"{k_kod} - {k_nam}")
            self.list_kategori_data.append({'kode': k_kod, 'nama': k_nam, 'satuan': k_sat, 'isi': k_isi})
        conn.close()
        self.combo_kategori.blockSignals(False)

        if self.data_edit:
            for idx, item in enumerate(self.list_kategori_data):
                if item['kode'] == self.data_edit['kode_kategori']:
                    self.combo_kategori.setCurrentIndex(idx)
                    break
            self.input_kb.setText(self.data_edit['kode_barang'])
            self.input_barcode.setText(self.data_edit['kode_barcode'])
            self.input_nb.setText(self.data_edit['nama_barang'])
            self.input_satuan.setText(self.data_edit['satuan'])
            self.input_isi.setText(str(self.data_edit['isi_satuan']))
            self.input_hb1.setText(str(self.data_edit['harga_beli_1']))
            self.input_m1.setText(str(self.data_edit['margin_1']))
            self.input_hj1.setText(str(self.data_edit['harga_jual_1']))
            self.input_hb2.setText(str(self.data_edit['harga_beli_2']))
            self.input_m2.setText(str(self.data_edit['margin_2']))
            self.input_hj2.setText(str(self.data_edit['harga_jual_2']))
            self.input_qty1.setText(str(self.data_edit['qty_1']))
            self.input_hjb1.setText(str(self.data_edit['harga_jual_bertingkat_1']))
            self.input_qty2.setText(str(self.data_edit['qty_2']))
            self.input_hjb2.setText(str(self.data_edit['harga_jual_bertingkat_2']))
            self.input_qty3.setText(str(self.data_edit['qty_3']))
            self.input_hjb3.setText(str(self.data_edit['harga_jual_bertingkat_3']))
            if self.data_edit['is_promo'] == "YES":
                self.check_promo.setChecked(True)
                self.date_awal.setDate(QDate.fromString(self.data_edit['tanggal_awal_promo'], "yyyy-MM-dd"))
                self.date_akhir.setDate(QDate.fromString(self.data_edit['tanggal_akhir_promo'], "yyyy-MM-dd"))
                self.input_hjpromo.setText(str(self.data_edit['harga_jual_promo']))
            self.input_minstok.setText(str(self.data_edit['minimal_stok']))
            self.input_stok.setText(str(self.data_edit['stok_isi']))
            self.input_ket.setText(self.data_edit['keterangan'])
        else: self.on_kategori_changed(self.combo_kategori.currentIndex())

    def on_kategori_changed(self, index):
        if index < 0 or index >= len(self.list_kategori_data) or self.data_edit: return
        kat = self.list_kategori_data[index]
        self.input_satuan.setText(kat['satuan']); self.input_isi.setText(str(kat['isi']))

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT kode_barang FROM master_barang WHERE kode_kategori = ? ORDER BY kode_barang DESC LIMIT 1", (kat['kode'],))
        row = cursor.fetchone()
        conn.close()
        kb_baru = f"{kat['kode']}{(int(row[0][len(kat['kode']):]) + 1):04d}" if row else f"{kat['kode']}0001"
        self.input_kb.setText(kb_baru)

    def on_check_promo_toggled(self, aktif):
        self.date_awal.setEnabled(aktif); self.date_akhir.setEnabled(aktif); self.input_hjpromo.setEnabled(aktif)

    def hitung_level_1_via_margin(self):
        if self.input_hj1.signalsBlocked(): return
        try:
            hb1, m1 = float(self.input_hb1.text() or 0), float(self.input_m1.text() or 0)
            self.input_hj1.blockSignals(True)
            self.input_hj1.setText(f"{(hb1 + (hb1 * (m1 / 100.0))):.2f}")
            self.input_hj1.blockSignals(False)
        except ValueError: pass

    def hitung_level_1_via_harga_jual(self):
        if self.input_m1.signalsBlocked(): return
        try:
            hb1, hj1 = float(self.input_hb1.text() or 0), float(self.input_hj1.text() or 0)
            if hb1 > 0:
                self.input_m1.blockSignals(True)
                self.input_m1.setText(f"{(((hj1 - hb1) / hb1) * 100.0):.2f}")
                self.input_m1.blockSignals(False)
        except ValueError: pass

    def hitung_level_2_otomatis(self):
        try:
            hb1, isi = float(self.input_hb1.text() or 0), float(self.input_isi.text() or 1)
            hb2 = hb1 / (isi if isi > 0 else 1)
            self.input_hb2.setText(f"{hb2:.2f}")
            self.hitung_level_2_via_margin()
        except ValueError: pass

    def hitung_level_2_via_margin(self):
        if self.input_hj2.signalsBlocked(): return
        try:
            hb2, m2 = float(self.input_hb2.text() or 0), float(self.input_m2.text() or 0)
            self.input_hj2.blockSignals(True)
            self.input_hj2.setText(f"{(hb2 + (hb2 * (m2 / 100.0))):.2f}")
            self.input_hj2.blockSignals(False)
        except ValueError: pass

    def hitung_level_2_via_harga_jual(self):
        if self.input_m2.signalsBlocked(): return
        try:
            hb2, hj2 = float(self.input_hb2.text() or 0), float(self.input_hj2.text() or 0)
            if hb2 > 0:
                self.input_m2.blockSignals(True)
                self.input_m2.setText(f"{(((hj2 - hb2) / hb2) * 100.0):.2f}")
                self.input_m2.blockSignals(False)
        except ValueError: pass

    def hitung_nilai_persediaan_gudang(self):
        try:
            hb1, isi, stok = float(self.input_hb1.text() or 0), float(self.input_isi.text() or 1), float(self.input_stok.text() or 0)
            self.input_persediaan.setText(f"{( (hb1 / (isi if isi > 0 else 1)) * stok ):.2f}")
        except ValueError: pass

    def proses_simpan_barang(self):
        idx = self.combo_kategori.currentIndex()
        if idx < 0 or not self.input_nb.text().strip(): return
        kat = self.list_kategori_data[idx]
        try:
            isi, hb1, m1, hj1 = int(self.input_isi.text() or 1), float(self.input_hb1.text() or 0), float(self.input_m1.text() or 0), float(self.input_hj1.text() or 0)
            hb2, m2, hj2 = float(self.input_hb2.text() or 0), float(self.input_m2.text() or 0), float(self.input_hj2.text() or 0)
            qty1, hjb1, qty2, hjb2, qty3, hjb3 = int(self.input_qty1.text() or 0), float(self.input_hjb1.text() or 0), int(self.input_qty2.text() or 0), float(self.input_hjb2.text() or 0), int(self.input_qty3.text() or 0), float(self.input_hjb3.text() or 0)
            is_p, t1, t2, hjp = "YES" if self.check_promo.isChecked() else "NO", self.date_awal.date().toString("yyyy-MM-dd"), self.date_akhir.date().toString("yyyy-MM-dd"), float(self.input_hjpromo.text() or 0)
            min_s, stk = int(self.input_minstok.text() or 0), int(self.input_stok.text() or 0)
            psd = hb2 * stk
        except ValueError: return

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        if self.data_edit:
            cursor.execute("UPDATE master_barang SET kode_kategori=?, nama_kategori=?, kode_barcode=?, nama_barang=?, satuan=?, isi_satuan=?, harga_beli_1=?, margin_1=?, harga_jual_1=?, harga_beli_2=?, margin_2=?, harga_jual_2=?, qty_1=?, harga_jual_bertingkat_1=?, qty_2=?, harga_jual_bertingkat_2=?, qty_3=?, harga_jual_bertingkat_3=?, is_promo=?, tanggal_awal_promo=?, tanggal_akhir_promo=?, harga_jual_promo=?, minimal_stok=?, stok_isi=?, nilai_persediaan=?, keterangan=? WHERE id=?", (kat['kode'], kat['nama'], self.input_barcode.text().strip(), self.input_nb.text().strip(), self.input_satuan.text().strip(), isi, hb1, m1, hj1, hb2, m2, hj2, qty1, hjb1, qty2, hjb2, qty3, hjb3, is_p, t1, t2, hjp, min_s, stk, psd, self.input_ket.text().strip(), self.data_edit['id']))
            self.saved_id = self.data_edit['id']
        else:
            id_b = uuid.uuid4().bytes; self.saved_id = id_b
            cursor.execute("INSERT INTO master_barang VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (id_b, kat['kode'], kat['nama'], self.input_kb.text(), self.input_barcode.text().strip(), self.input_nb.text().strip(), self.input_satuan.text().strip(), isi, hb1, m1, hj1, hb2, m2, hj2, qty1, hjb1, qty2, hjb2, qty3, hjb3, is_p, t1, t2, hjp, min_s, stk, psd, self.input_ket.text().strip()))
        conn.commit(); conn.close(); self.accept()

class BarangDataWidget(QWidget):
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

        header_label = QLabel("🏷️ Logistik Gudang: Manajemen Data Barang & Stok", self)
        header_label.setFont(get_font(16, bold=True))
        header_label.setStyleSheet("color: #2c3e50;")
        layout.addWidget(header_label)

        kontrol_layout = QHBoxLayout()
        self.btn_tambah = QPushButton("➕ Tambah Barang", self)
        self.btn_edit = QPushButton("✏️ Edit Barang", self)
        self.btn_hapus = QPushButton("🗑️ Hapus Barang", self)
        self.btn_cetak = QPushButton("👁️ Cetak Laporan (Landscape)", self)

        tombol_styles = {
            self.btn_tambah: "background-color: #3498db; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_edit: "background-color: #f1c40f; color: black; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_hapus: "background-color: #e74c3c; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_cetak: "background-color: #9b59b6; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;"
        }
        for btn, style in tombol_styles.items():
            btn.setStyleSheet(style)
            btn.setCursor(Qt.PointingHandCursor)
            kontrol_layout.addWidget(btn)

        kontrol_layout.addStretch()
        self.combo_filter_stok = QComboBox(self)
        self.combo_filter_stok.addItems(["Semua Barang", "Stok Menipis (<= Min)", "Stok Kosong (=0)", "Barang Promo Aktif"])
        self.combo_filter_stok.currentIndexChanged.connect(self.muat_data_dari_db)
        self.input_cari = QLineEdit(self)
        self.input_cari.setPlaceholderText("Nama / Kode...")
        self.input_cari.setStyleSheet("padding: 8px; border: 1px solid #dcdde1; border-radius: 4px; background: white;")
        self.btn_cari = QPushButton("🔍 Cari", self)
        self.btn_cari.setStyleSheet("padding: 8px 12px; background-color: #34495e; color: white; border-radius: 4px;")
        kontrol_layout.addWidget(self.combo_filter_stok)
        kontrol_layout.addWidget(self.input_cari)
        kontrol_layout.addWidget(self.btn_cari)
        layout.addLayout(kontrol_layout)

        # 11 KOLOM KASIR UTAMA (FIXED COMPACT HYBRID LOGIC)
        self.table = QTableWidget(self)
        self.table.setColumnCount(12) 
        self.table.setHorizontalHeaderLabels(["ID Hidden", "🔑 KB", "║║ Barcode", "🏷️ Nama Barang", "📥 HB1", "📈 M1", "💵 HJ1", "📥 HB2", "📈 M2", "💵 HJ2", "📦 STOK", "📌 PROMO"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnHidden(0, True)

        # Aktifkan Scrollbar agar interface utama main.py tidak terdorong keluar layar
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

        # REQ FIXED: Mengubah semua ke Interactive agar scrollbar horizontal aktif di bawah tabel!
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)

        self.table.setColumnWidth(1, 80)   # KB
        self.table.setColumnWidth(2, 100)  # Barcode
        self.table.setColumnWidth(3, 220)  # Nama Barang (Bebas memanjang memicu scrollbar bawah)
        self.table.setColumnWidth(4, 90)   # HB1
        self.table.setColumnWidth(5, 60)   # M1
        self.table.setColumnWidth(6, 90)   # HJ1
        self.table.setColumnWidth(7, 90)   # HB2
        self.table.setColumnWidth(8, 60)   # M2
        self.table.setColumnWidth(9, 90)   # HJ2
        self.table.setColumnWidth(10, 75)  # STOK
        self.table.setColumnWidth(11, 75)  # PROMO

        layout.addWidget(self.table)
        self.btn_tambah.clicked.connect(self.aksi_tambah)
        self.btn_edit.clicked.connect(self.aksi_edit)
        self.btn_hapus.clicked.connect(self.aksi_hapus)
        self.btn_cetak.clicked.connect(self.aksi_cetak_landscape)
        self.btn_cari.clicked.connect(self.muat_data_dari_db)
        self.input_cari.returnPressed.connect(self.muat_data_dari_db)

    def muat_data_dari_db(self, target_highlight_id=None):
        self.table.setRowCount(0)
        keyword, f_stok = self.input_cari.text().strip(), self.combo_filter_stok.currentIndex()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        query = "SELECT id, kode_kategori, nama_kategori, kode_barang, kode_barcode, nama_barang, satuan, isi_satuan, harga_beli_1, margin_1, harga_jual_1, harga_beli_2, margin_2, harga_jual_2, qty_1, harga_jual_bertingkat_1, qty_2, harga_jual_bertingkat_2, qty_3, harga_jual_bertingkat_3, is_promo, tanggal_awal_promo, tanggal_akhir_promo, harga_jual_promo, minimal_stok, stok_isi, nilai_persediaan, keterangan FROM master_barang WHERE 1=1"
        p = []
        if keyword:
            query += " AND (nama_barang LIKE ? OR kode_barang LIKE ? OR kode_barcode LIKE ?)"
            p.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
        if f_stok == 1: query += " AND stok_isi <= minimal_stok"
        elif f_stok == 2: query += " AND stok_isi = 0"
        elif f_stok == 3: query += " AND is_promo = 'YES'"
        cursor.execute(query + " ORDER BY kode_barang ASC", p)
        self.raw_rows_data = cursor.fetchall()
        conn.close()

        baris_target_idx = -1
        for idx, r in enumerate(self.raw_rows_data):
            self.table.insertRow(idx)
            item_id = QTableWidgetItem()
            item_id.setData(Qt.UserRole, r[0])
            self.table.setItem(idx, 0, item_id)
            self.table.setItem(idx, 1, QTableWidgetItem(str(r[3])))
            self.table.setItem(idx, 2, QTableWidgetItem(str(r[4])))
            self.table.setItem(idx, 3, QTableWidgetItem(str(r[5])))

            for c_i, val in [(4, f"Rp {r[8]:,.0f}"), (6, f"Rp {r[10]:,.0f}"), (7, f"Rp {r[11]:,.0f}"), (9, f"Rp {r[13]:,.0f}")]:
                it = QTableWidgetItem(val); it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter); self.table.setItem(idx, c_i, it)

            for c_i, val in [(5, f"{r[9]:.1f}%"), (8, f"{r[12]:.1f}%")]:
                it = QTableWidgetItem(val); it.setTextAlignment(Qt.AlignCenter); self.table.setItem(idx, c_i, it)

            item_stok = QTableWidgetItem(str(r[25])); item_stok.setTextAlignment(Qt.AlignCenter)
            if r[25] <= r[24]:
                item_stok.setForeground(QColor("#e74c3c")); item_stok.setFont(get_font(10, bold=True))
            self.table.setItem(idx, 10, item_stok)

            item_promo = QTableWidgetItem(str(r[20])); item_promo.setTextAlignment(Qt.AlignCenter)
            if r[20] == "YES":
                item_promo.setForeground(QColor("#2ecc71")); item_promo.setFont(get_font(10, bold=True))
            self.table.setItem(idx, 11, item_promo)

            if target_highlight_id and r[0] == target_highlight_id: baris_target_idx = idx
        if baris_target_idx != -1: self.table.setCurrentCell(baris_target_idx, 3)

    def aksi_tambah(self):
        dialog = FormBarangDialog(self)
        if dialog.exec_() == QDialog.Accepted: self.muat_data_dari_db(target_highlight_id=dialog.saved_id)

    def aksi_edit(self):
        b = self.table.currentRow()
        if b == -1: return
        id_bin = self.table.item(b, 0).data(Qt.UserRole)
        dm = next((r for r in self.raw_rows_data if r[0] == id_bin), None)
        if not dm: return
        keys = ['id', 'kode_kategori', 'nama_kategori', 'kode_barang', 'kode_barcode', 'nama_barang', 'satuan', 'isi_satuan', 'harga_beli_1', 'margin_1', 'harga_jual_1', 'harga_beli_2', 'margin_2', 'harga_jual_2', 'qty_1', 'harga_jual_bertingkat_1', 'qty_2', 'harga_jual_bertingkat_2', 'qty_3', 'harga_jual_bertingkat_3', 'is_promo', 'tanggal_awal_promo', 'tanggal_akhir_promo', 'harga_jual_promo', 'minimal_stok', 'stok_isi', 'nilai_persediaan', 'keterangan']
        dialog = FormBarangDialog(self, data_edit=dict(zip(keys, dm)))
        if dialog.exec_() == QDialog.Accepted: self.muat_data_dari_db(target_highlight_id=dialog.saved_id)

    def aksi_hapus(self):
        b = self.table.currentRow()
        if b == -1: return
        if QMessageBox.question(self, "Konfirmasi", f"❓ Hapus produk '{self.table.item(b,3).text()}'?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM master_barang WHERE id = ?", (self.table.item(b, 0).data(Qt.UserRole),))
            conn.commit(); conn.close(); self.muat_data_dari_db()

    def pdf_print_callback(self, printer):
        self.pdf_document.print_(printer)

    def aksi_cetak_landscape(self):
        if not hasattr(self, 'raw_rows_data') or not self.raw_rows_data: return
        html_content = f"""
        <html><head><style>
            @page {{ size: A4 landscape; margin: 1.5cm; }}
            body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #2c3e50; margin: 0; padding: 0; }}
            h2 {{ color: #2c3e50; border-bottom: 3px solid #2c3e50; padding-bottom: 8px; margin-bottom: 15px; font-size: 22px; }}
            .meta-table {{ width: 100%; margin-bottom: 15px; font-size: 13px; }}
            .data-table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
            .data-table th {{ background-color: #2c3e50; color: white; padding: 8px; }}
            .data-table td {{ padding: 8px; border: 1px solid #dcdde1; }}
            .text-center {{ text-align: center; }}
            .text-right {{ text-align: right; }}
            .text-danger {{ color: #e74c3c; font-weight: bold; }}
        </style></head><body>
            <h2>LAPORAN REKAPITULASI STOK & KATALOG BARANG</h2>
            <table class="meta-table"><tr><td><b>🏢 Unit Kerja:</b> Logistik Gudang Pusat KUD Tani Makmur</td><td style="text-align: right;"><b>🖨️ Tanggal Penarikan:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}</td></tr></table>
            <table class="data-table"><thead><tr><th>Kode Barang</th><th>Barcode</th><th>Nama Barang</th><th>Kategori</th><th>Satuan</th><th>Isi</th><th>Harga Beli</th><th>Harga Jual</th><th>Stok</th><th>Promo</th></tr></thead><tbody>
        """
        for r in self.raw_rows_data:
            style_s = "class='text-center text-danger'" if r[25] <= r[24] else "class='text-center'"
            html_content += f"<tr><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td>{r[2]}</td><td class='text-center'>{r[6]}</td><td class='text-center'>{r[7]}</td><td class='text-right'>Rp {r[8]:,.0f}</td><td class='text-right'>Rp {r[10]:,.0f}</td><td {style_s}>{r[25]}</td><td class='text-center'>{r[20]}</td></tr>"
        html_content += "</tbody></table></body></html>"

        self.pdf_document = QTextDocument()
        self.pdf_document.setHtml(html_content)
        from PyQt5.QtPrintSupport import QPrintPreviewDialog
        printer = QPrinter(QPrinter.ScreenResolution)
        printer.setPageSize(QPrinter.A4)
        printer.setOrientation(QPrinter.Landscape)
        printer.setPageMargins(15, 15, 15, 15, QPrinter.Millimeter)
        preview_dialog = QPrintPreviewDialog(printer, self)
        preview_dialog.resize(1100, 750)
        preview_dialog.paintRequested.connect(self.pdf_print_callback)
        preview_dialog.exec_()
