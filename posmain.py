"""
posmain.py - POS Kasir Modern (Keyboard-First, Minim Mouse)
Smart Input: angka=qty | 8+digit=barcode | huruf=kode/nama(LIKE→tabel pilih)
Harga: default harga_jual_2 (ecer), F11=mode harga_jual_1, F3=mode diskon item
Promo: auto-detect is_promo='YES' + tanggal berlaku → harga_jual_promo
"""

import sys
import sqlite3
import uuid
from datetime import datetime, date
from decimal import Decimal

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QDoubleSpinBox, QComboBox,
    QDialog, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QSplitter, QGroupBox, QShortcut,
    QKeySequenceEdit, QSizePolicy, QStackedWidget, QScrollArea,
    QGridLayout, QSpacerItem, QInputDialog, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QDate
from PyQt5.QtGui import QFont, QKeySequence, QColor, QBrush
from PyQt5.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PyQt5.QtGui import QTextDocument

from widgets import get_font
from db_manager import db

DB_NAME = "pos_inventory.db"


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE INIT POS
# ═══════════════════════════════════════════════════════════════════════════════
def init_pos_database():
    """Inisialisasi tabel POS Kasir"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Shift Kasir
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_kasir (
            id BLOB PRIMARY KEY,
            user_id BLOB NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            outlet_id BLOB,
            tgl_buka TEXT NOT NULL,
            saldo_awal REAL NOT NULL DEFAULT 0.0,
            tgl_tutup TEXT,
            saldo_akhir_fisik REAL DEFAULT 0.0,
            selisih REAL DEFAULT 0.0,
            total_penjualan REAL DEFAULT 0.0,
            total_transaksi INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'AKTIF'
        )
    """)

    # Faktur Jual POS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faktur_jual_pos (
            id BLOB PRIMARY KEY,
            no_faktur TEXT NOT NULL UNIQUE,
            shift_id BLOB,
            user_id BLOB NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            outlet_id BLOB,
            member_id BLOB,
            kode_member TEXT DEFAULT '',
            nama_member TEXT DEFAULT '',
            total_item INTEGER NOT NULL DEFAULT 0,
            total_qty REAL NOT NULL DEFAULT 0,
            subtotal REAL NOT NULL DEFAULT 0.0,
            diskon_global REAL NOT NULL DEFAULT 0.0,
            grand_total REAL NOT NULL DEFAULT 0.0,
            bayar REAL NOT NULL DEFAULT 0.0,
            kembalian REAL NOT NULL DEFAULT 0.0,
            metode_bayar TEXT NOT NULL DEFAULT 'CASH',
            status TEXT NOT NULL DEFAULT 'LUNAS',
            keterangan TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Detail Jual POS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detil_jual_pos (
            id BLOB PRIMARY KEY,
            faktur_id BLOB NOT NULL,
            barang_id BLOB NOT NULL,
            kode_barang TEXT NOT NULL DEFAULT '',
            nama_barang TEXT NOT NULL DEFAULT '',
            qty REAL NOT NULL DEFAULT 0,
            satuan TEXT NOT NULL DEFAULT 'PCS',
            harga_jual REAL NOT NULL DEFAULT 0.0,
            diskon_item REAL NOT NULL DEFAULT 0.0,
            subtotal REAL NOT NULL DEFAULT 0.0,
            mode_harga TEXT DEFAULT 'ECER'
        )
    """)

    # Draft Bill POS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS draft_bill_pos (
            id BLOB PRIMARY KEY,
            nomor_draft TEXT NOT NULL UNIQUE,
            kasir_id BLOB NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            items_json TEXT NOT NULL DEFAULT '',
            total REAL NOT NULL DEFAULT 0.0,
            member_id BLOB,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Kartu Stok (keluar untuk POS)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kartu_stok (
            id BLOB PRIMARY KEY,
            kode_barang TEXT NOT NULL DEFAULT '',
            nama_barang TEXT NOT NULL DEFAULT '',
            tanggal TEXT NOT NULL,
            jenis TEXT NOT NULL,
            qty_masuk INTEGER DEFAULT 0,
            qty_keluar INTEGER DEFAULT 0,
            harga_satuan REAL DEFAULT 0.0,
            saldo_qty INTEGER DEFAULT 0,
            referensi_no TEXT DEFAULT '',
            keterangan TEXT DEFAULT '',
            user_input TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def d(val):
    """Convert ke Decimal"""
    return Decimal(str(val)) if val is not None else Decimal('0')


def fmt_rp(v):
    """Format rupiah"""
    return f"Rp {float(v):,.0f}".replace(',', '.')


def gen_no_faktur_pos(outlet_kode):
    """Generate nomor faktur POS: POS/OUT001/20260517/001"""
    now = datetime.now()
    prefix = f"POS/{outlet_kode}/{now.strftime('%Y%m%d')}/"
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT no_faktur FROM faktur_jual_pos WHERE no_faktur LIKE ? ORDER BY no_faktur DESC LIMIT 1",
        (f"{prefix}%",)
    )
    row = cursor.fetchone()
    conn.close()
    urut = int(row[0].split('/')[-1]) + 1 if row else 1
    return f"{prefix}{urut:03d}"


def get_harga_jual(barang, qty=1, mode_harga='ECER'):
    """
    Hitung harga jual berdasarkan:
    1. Promo (kalau aktif & tanggal berlaku)
    2. Harga bertingkat (kalau aktif di settings)
    3. Mode harga (ECER=harga_jual_2, UNIT=harga_jual_1)
    """
    qty_dec = d(qty)
    today = date.today().isoformat()

    # Cek promo
    is_promo = barang.get('is_promo', 'NO')
    tgl_awal = barang.get('tanggal_awal_promo', '')
    tgl_akhir = barang.get('tanggal_akhir_promo', '')

    if is_promo == 'YES' and tgl_awal <= today <= tgl_akhir:
        return d(barang.get('harga_jual_promo', 0))

    # Cek harga bertingkat (kalau aktif)
    # Settings: harga_bertingkat_aktif = 'YES'
    # Ini akan dicek di level aplikasi, di sini kita cek qty threshold
    if qty_dec >= d(barang.get('qty_3', 0)) and d(barang.get('qty_3', 0)) > 0:
        return d(barang.get('harga_jual_bertingkat_3', 0))
    elif qty_dec >= d(barang.get('qty_2', 0)) and d(barang.get('qty_2', 0)) > 0:
        return d(barang.get('harga_jual_bertingkat_2', 0))
    elif qty_dec >= d(barang.get('qty_1', 0)) and d(barang.get('qty_1', 0)) > 0:
        return d(barang.get('harga_jual_bertingkat_1', 0))

    # Mode harga
    if mode_harga == 'UNIT':
        return d(barang.get('harga_jual_1', 0))
    else:  # ECER
        return d(barang.get('harga_jual_2', 0))


def cek_shift_aktif(user_id):
    """Cek apakah kasir punya shift aktif"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, tgl_buka, saldo_awal FROM shift_kasir WHERE user_id=? AND status='AKTIF' ORDER BY tgl_buka DESC LIMIT 1",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return {'id': row[0], 'tgl_buka': row[1], 'saldo_awal': row[2]} if row else None


def simpan_shift(user_id, username, outlet_id, saldo_awal):
    """Buka shift baru"""
    shift_id = uuid.uuid4().bytes
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO shift_kasir (id, user_id, username, outlet_id, tgl_buka, saldo_awal, status) VALUES (?,?,?,?,?,?,?)",
        (shift_id, user_id, username, outlet_id, datetime.now().isoformat(), saldo_awal, 'AKTIF')
    )
    conn.commit()
    conn.close()
    return shift_id


def tutup_shift(shift_id, saldo_fisik):
    """Tutup shift, hitung selisih"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Hitung total penjualan shift ini
    cursor.execute(
        "SELECT COALESCE(SUM(grand_total),0), COUNT(*) FROM faktur_jual_pos WHERE shift_id=?",
        (shift_id,)
    )
    total_jual, total_trx = cursor.fetchone()

    # Ambil saldo awal
    cursor.execute("SELECT saldo_awal FROM shift_kasir WHERE id=?", (shift_id,))
    saldo_awal = cursor.fetchone()[0]

    selisih = d(saldo_fisik) - d(saldo_awal) - d(total_jual)

    cursor.execute(
        "UPDATE shift_kasir SET tgl_tutup=?, saldo_akhir_fisik=?, selisih=?, total_penjualan=?, total_transaksi=?, status='TUTUP' WHERE id=?",
        (datetime.now().isoformat(), saldo_fisik, selisih, total_jual, total_trx, shift_id)
    )
    conn.commit()
    conn.close()
    return {'total_penjualan': total_jual, 'total_transaksi': total_trx, 'selisih': selisih}


# ═══════════════════════════════════════════════════════════════════════════════
# DIALOG BUKA SHIFT
# ═══════════════════════════════════════════════════════════════════════════════
class BukaShiftDialog(QDialog):
    def __init__(self, parent, user_data):
        super().__init__(parent)
        self.user_data = user_data
        self.shift_id = None
        self.setWindowTitle("🔓 Buka Shift Kasir")
        self.setModal(True)
        self.resize(400, 250)
        self.setStyleSheet("background-color: #f4f6f9;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        info = QLabel(f"Kasir: <b>{self.user_data.get('nama_lengkap', '')}</b><br>Username: {self.user_data.get('username', '')}")
        info.setStyleSheet("font-size: 12px; color: #2c3e50;")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(12)

        self.inp_saldo = QDoubleSpinBox()
        self.inp_saldo.setRange(0, 999999999)
        self.inp_saldo.setGroupSeparatorShown(True)
        self.inp_saldo.setStyleSheet("""
            QDoubleSpinBox {
                padding: 10px; font-size: 14pt;
                border: 2px solid #3498db; border-radius: 6px;
            }
        """)
        form.addRow("💰 Saldo Awal Kas (Rp):", self.inp_saldo)
        layout.addLayout(form)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_buka = QPushButton("🔓 BUKA SHIFT")
        btn_buka.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71; color: white;
                font-weight: bold; font-size: 12pt;
                padding: 12px 30px; border-radius: 6px;
            }
            QPushButton:hover { background-color: #27ae60; }
        """)
        btn_buka.clicked.connect(self.proses_buka)

        btn_batal = QPushButton("❌ Batal")
        btn_batal.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: white;
                padding: 10px 20px; border-radius: 6px;
            }
        """)
        btn_batal.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_buka)
        btn_layout.addWidget(btn_batal)
        layout.addLayout(btn_layout)

        self.inp_saldo.setFocus()

    def proses_buka(self):
        saldo = self.inp_saldo.value()
        outlet_id = self.user_data.get('outlet_id')
        self.shift_id = simpan_shift(
            self.user_data['id'],
            self.user_data['username'],
            outlet_id,
            saldo
        )
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════════
# DIALOG TUTUP SHIFT
# ═══════════════════════════════════════════════════════════════════════════════
class TutupShiftDialog(QDialog):
    def __init__(self, parent, shift_data):
        super().__init__(parent)
        self.shift_data = shift_data
        self.setWindowTitle("🔒 Tutup Shift Kasir")
        self.setModal(True)
        self.resize(450, 350)
        self.setStyleSheet("background-color: #f4f6f9;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(12)

        # Info shift
        info = QLabel(f"""
            <b>Shift ID:</b> {self.shift_data['id'].hex()[:16]}...<<br>
            <b>Buka:</b> {self.shift_data['tgl_buka'][:19]}<<br>
            <b>Saldo Awal:</b> {fmt_rp(self.shift_data['saldo_awal'])}
        """)
        info.setStyleSheet("font-size: 11px; color: #2c3e50; background: #eaf2f8; padding: 10px; border-radius: 6px;")
        layout.addWidget(info)

        form = QFormLayout()
        self.inp_fisik = QDoubleSpinBox()
        self.inp_fisik.setRange(0, 999999999)
        self.inp_fisik.setGroupSeparatorShown(True)
        self.inp_fisik.valueChanged.connect(self.hitung_selisih)
        form.addRow("💰 Saldo Fisik Akhir (Rp):", self.inp_fisik)
        layout.addLayout(form)

        self.lbl_preview = QLabel("Selisih: Rp 0")
        self.lbl_preview.setStyleSheet("font-size: 14pt; font-weight: bold; color: #2c3e50; padding: 10px;")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_preview)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_tutup = QPushButton("🔒 TUTUP SHIFT & CETAK")
        btn_tutup.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: white;
                font-weight: bold; font-size: 12pt;
                padding: 12px 30px; border-radius: 6px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        btn_tutup.clicked.connect(self.proses_tutup)

        btn_batal = QPushButton("❌ Batal")
        btn_batal.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6; color: white;
                padding: 10px 20px; border-radius: 6px;
            }
        """)
        btn_batal.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_tutup)
        btn_layout.addWidget(btn_batal)
        layout.addLayout(btn_layout)

    def hitung_selisih(self):
        # Preview sederhana
        pass

    def proses_tutup(self):
        saldo_fisik = self.inp_fisik.value()
        result = tutup_shift(self.shift_data['id'], saldo_fisik)
        QMessageBox.information(self, "Shift Ditutup", f"""
            ✅ Shift berhasil ditutup!
            
            Total Penjualan: {fmt_rp(result['total_penjualan'])}
            Total Transaksi: {result['total_transaksi']}
            Selisih: {fmt_rp(result['selisih'])}
        """)
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════════
# DIALOG HASIL PENCARIAN BARANG (LIKE)
# ═══════════════════════════════════════════════════════════════════════════════
class HasilPencarianDialog(QDialog):
    barang_selected = pyqtSignal(dict, float)  # barang_data, qty

    def __init__(self, parent, keyword, qty_default=1):
        super().__init__(parent)
        self.keyword = keyword
        self.qty_default = qty_default
        self.setWindowTitle(f"🔍 Hasil Pencarian: '{keyword}'")
        self.setModal(True)
        self.resize(650, 450)
        self.setStyleSheet("background-color: #f4f6f9;")
        self.init_ui()
        self.muat_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Hint
        hint = QLabel("↑↓ = Navigasi  |  Enter = Pilih  |  Esc = Batal")
        hint.setStyleSheet("color: #7f8c8d; font-size: 9pt;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        # Tabel
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(6)
        self.tbl.setHorizontalHeaderLabels(["Kode", "Nama Barang", "Satuan", "Stok", "Harga Ecer", "Harga Unit"])
        self.tbl.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #e0e0e0;
                border: 1px solid #d0d0d0;
                font-size: 11pt;
            }
            QTableWidget::item { padding: 8px; }
            QTableWidget::item:selected { background-color: #3498db; color: white; }
            QHeaderView::section {
                background-color: #2c3e50; color: white;
                padding: 8px; font-weight: bold;
            }
        """)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.horizontalHeader().setStretchLastSection(False)
        self.tbl.setColumnWidth(0, 100)
        self.tbl.setColumnWidth(1, 220)
        self.tbl.setColumnWidth(2, 70)
        self.tbl.setColumnWidth(3, 70)
        self.tbl.setColumnWidth(4, 100)
        self.tbl.setColumnWidth(5, 100)
        self.tbl.verticalHeader().setVisible(False)

        # Event: Enter pada tabel = pilih
        self.tbl.keyPressEvent = self._table_key_press

        layout.addWidget(self.tbl, 1)

        # Qty override
        qty_layout = QHBoxLayout()
        qty_layout.addWidget(QLabel("Qty:"))
        self.inp_qty = QDoubleSpinBox()
        self.inp_qty.setRange(0.01, 9999)
        self.inp_qty.setValue(self.qty_default)
        self.inp_qty.setDecimals(2)
        qty_layout.addWidget(self.inp_qty)
        qty_layout.addStretch()
        layout.addLayout(qty_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_pilih = QPushButton("✅ Pilih (Enter)")
        btn_pilih.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71; color: white;
                font-weight: bold; padding: 10px 25px;
                border-radius: 6px;
            }
        """)
        btn_pilih.clicked.connect(self.pilih_barang)

        btn_batal = QPushButton("❌ Batal (Esc)")
        btn_batal.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: white;
                padding: 10px 20px; border-radius: 6px;
            }
        """)
        btn_batal.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_pilih)
        btn_layout.addWidget(btn_batal)
        layout.addLayout(btn_layout)

    def _table_key_press(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.pilih_barang()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            QTableWidget.keyPressEvent(self.tbl, event)

    def muat_data(self):
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT kode_barang, nama_barang, satuan, stok_isi,
                   harga_jual_2, harga_jual_1, isi_satuan
            FROM master_barang
            WHERE (kode_barang LIKE ? OR nama_barang LIKE ? OR kode_barcode LIKE ?)
              AND stok_isi > 0
            ORDER BY nama_barang
            LIMIT 50
        """, (f"%{self.keyword}%", f"%{self.keyword}%", f"%{self.keyword}%"))
        rows = cursor.fetchall()
        conn.close()

        self.tbl.setRowCount(0)
        self._rows_data = []

        for idx, r in enumerate(rows):
            self.tbl.insertRow(idx)
            self._rows_data.append(dict(r))

            self.tbl.setItem(idx, 0, QTableWidgetItem(r['kode_barang']))
            self.tbl.setItem(idx, 1, QTableWidgetItem(r['nama_barang']))
            self.tbl.setItem(idx, 2, QTableWidgetItem(r['satuan']))

            stok_item = QTableWidgetItem(str(r['stok_isi']))
            stok_item.setTextAlignment(Qt.AlignCenter)
            self.tbl.setItem(idx, 3, stok_item)

            harga_ecer = QTableWidgetItem(fmt_rp(r['harga_jual_2']))
            harga_ecer.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl.setItem(idx, 4, harga_ecer)

            harga_unit = QTableWidgetItem(fmt_rp(r['harga_jual_1']))
            harga_unit.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl.setItem(idx, 5, harga_unit)

        if rows:
            self.tbl.setCurrentCell(0, 0)
            self.tbl.setFocus()

    def pilih_barang(self):
        row = self.tbl.currentRow()
        if row < 0 or row >= len(self._rows_data):
            return
        qty = self.inp_qty.value()
        self.barang_selected.emit(self._rows_data[row], qty)
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════════
# DIALOG BAYAR
# ═══════════════════════════════════════════════════════════════════════════════
class BayarDialog(QDialog):
    def __init__(self, parent, grand_total, current_bayar=0):
        super().__init__(parent)
        self.grand_total = d(grand_total)
        self.result = {'bayar': d(0), 'metode': 'CASH', 'kembalian': d(0)}
        self.setWindowTitle("💰 Pembayaran")
        self.setModal(True)
        self.resize(400, 350)
        self.setStyleSheet("background-color: #f4f6f9;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        # Grand Total
        lbl_total = QLabel(f"GRAND TOTAL:\n{fmt_rp(self.grand_total)}")
        lbl_total.setStyleSheet("font-size: 18pt; font-weight: bold; color: #e74c3c;")
        lbl_total.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_total)

        # Metode Bayar
        form = QFormLayout()
        self.combo_metode = QComboBox()
        self.combo_metode.addItems(["CASH", "QRIS", "TRANSFER", "DEBIT", "HUTANG"])
        self.combo_metode.currentTextChanged.connect(self.on_metode_changed)
        form.addRow("Metode:", self.combo_metode)

        # Bayar
        self.inp_bayar = QDoubleSpinBox()
        self.inp_bayar.setRange(0, 999999999)
        self.inp_bayar.setValue(float(self.grand_total))
        self.inp_bayar.setGroupSeparatorShown(True)
        self.inp_bayar.valueChanged.connect(self.hitung_kembalian)
        form.addRow("Bayar (Rp):", self.inp_bayar)

        layout.addLayout(form)

        # Kembalian
        self.lbl_kembali = QLabel("Kembalian: Rp 0")
        self.lbl_kembali.setStyleSheet("font-size: 14pt; font-weight: bold; color: #2ecc71;")
        self.lbl_kembali.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_kembali)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_bayar = QPushButton("✅ BAYAR (Enter)")
        btn_bayar.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71; color: white;
                font-weight: bold; font-size: 12pt;
                padding: 12px 30px; border-radius: 6px;
            }
        """)
        btn_bayar.clicked.connect(self.proses_bayar)

        btn_batal = QPushButton("❌ Batal (Esc)")
        btn_batal.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: white;
                padding: 10px 20px; border-radius: 6px;
            }
        """)
        btn_batal.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_bayar)
        btn_layout.addWidget(btn_batal)
        layout.addLayout(btn_layout)

        self.inp_bayar.setFocus()
        self.inp_bayar.selectAll()

    def on_metode_changed(self, metode):
        if metode == 'HUTANG':
            self.inp_bayar.setValue(0)
            self.inp_bayar.setEnabled(False)
            self.lbl_kembali.setText("HUTANG - Bayar: Rp 0")
            self.lbl_kembali.setStyleSheet("font-size: 14pt; font-weight: bold; color: #e67e22;")
        else:
            self.inp_bayar.setEnabled(True)
            if metode == 'CASH':
                self.inp_bayar.setValue(float(self.grand_total))
            self.hitung_kembalian()

    def hitung_kembalian(self):
        bayar = d(self.inp_bayar.value())
        kembalian = bayar - self.grand_total
        if kembalian >= 0:
            self.lbl_kembali.setText(f"Kembalian: {fmt_rp(kembalian)}")
            self.lbl_kembali.setStyleSheet("font-size: 14pt; font-weight: bold; color: #2ecc71;")
        else:
            self.lbl_kembali.setText(f"KURANG: {fmt_rp(abs(kembalian))}")
            self.lbl_kembali.setStyleSheet("font-size: 14pt; font-weight: bold; color: #e74c3c;")

    def proses_bayar(self):
        bayar = d(self.inp_bayar.value())
        metode = self.combo_metode.currentText()

        if metode != 'HUTANG' and bayar < self.grand_total:
            QMessageBox.warning(self, "Kurang", f"Bayar kurang!\nKurang: {fmt_rp(self.grand_total - bayar)}")
            return

        self.result = {
            'bayar': bayar,
            'metode': metode,
            'kembalian': bayar - self.grand_total if metode != 'HUTANG' else d(0)
        }
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════════
# DIALOG PILIH MEMBER
# ═══════════════════════════════════════════════════════════════════════════════
class PilihMemberDialog(QDialog):
    member_selected = pyqtSignal(dict)

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("🎫 Pilih Member")
        self.setModal(True)
        self.resize(550, 400)
        self.setStyleSheet("background-color: #f4f6f9;")
        self.init_ui()
        self.muat_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Search
        search_layout = QHBoxLayout()
        self.inp_cari = QLineEdit()
        self.inp_cari.setPlaceholderText("Ketik nama/kode member...")
        self.inp_cari.returnPressed.connect(self.muat_data)
        self.inp_cari.setStyleSheet("padding: 8px; border: 2px solid #3498db; border-radius: 4px;")
        search_layout.addWidget(self.inp_cari)

        btn_cari = QPushButton("🔍 Cari")
        btn_cari.setStyleSheet("background-color: #3498db; color: white; padding: 8px 15px; border-radius: 4px;")
        btn_cari.clicked.connect(self.muat_data)
        search_layout.addWidget(btn_cari)
        layout.addLayout(search_layout)

        # Tabel
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(5)
        self.tbl.setHorizontalHeaderLabels(["Kode", "Nama Member", "Alamat", "Telepon", "Hutang"])
        self.tbl.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #e0e0e0;
                font-size: 11pt;
            }
            QTableWidget::item:selected { background-color: #3498db; color: white; }
            QHeaderView::section {
                background-color: #2c3e50; color: white;
                padding: 8px; font-weight: bold;
            }
        """)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setColumnWidth(0, 80)
        self.tbl.setColumnWidth(1, 180)
        self.tbl.setColumnWidth(2, 150)
        self.tbl.setColumnWidth(3, 100)
        self.tbl.setColumnWidth(4, 100)
        self.tbl.verticalHeader().setVisible(False)

        # Override key press
        self.tbl.keyPressEvent = self._table_key_press

        layout.addWidget(self.tbl, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_pilih = QPushButton("✅ Pilih (Enter)")
        btn_pilih.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71; color: white;
                font-weight: bold; padding: 10px 20px; border-radius: 6px;
            }
        """)
        btn_pilih.clicked.connect(self.pilih)

        btn_batal = QPushButton("❌ Batal (Esc)")
        btn_batal.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: white;
                padding: 10px 20px; border-radius: 6px;
            }
        """)
        btn_batal.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_pilih)
        btn_layout.addWidget(btn_batal)
        layout.addLayout(btn_layout)

    def _table_key_press(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.pilih()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            QTableWidget.keyPressEvent(self.tbl, event)

    def muat_data(self):
        keyword = self.inp_cari.text().strip()
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if keyword:
            cursor.execute("""
                SELECT id, kode_member, nama_member, alamat_member, telepon_member, ttl_hutang
                FROM master_member
                WHERE nama_member LIKE ? OR kode_member LIKE ?
                ORDER BY nama_member
            """, (f"%{keyword}%", f"%{keyword}%"))
        else:
            cursor.execute("""
                SELECT id, kode_member, nama_member, alamat_member, telepon_member, ttl_hutang
                FROM master_member ORDER BY nama_member LIMIT 50
            """)

        rows = cursor.fetchall()
        conn.close()

        self.tbl.setRowCount(0)
        self._rows_data = []

        for idx, r in enumerate(rows):
            self.tbl.insertRow(idx)
            self._rows_data.append(dict(r))

            self.tbl.setItem(idx, 0, QTableWidgetItem(r['kode_member']))
            self.tbl.setItem(idx, 1, QTableWidgetItem(r['nama_member']))
            self.tbl.setItem(idx, 2, QTableWidgetItem(r['alamat_member'] or ''))
            self.tbl.setItem(idx, 3, QTableWidgetItem(r['telepon_member'] or ''))

            hutang = QTableWidgetItem(fmt_rp(r['ttl_hutang']))
            hutang.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if r['ttl_hutang'] > 0:
                hutang.setForeground(QColor("#e74c3c"))
            self.tbl.setItem(idx, 4, hutang)

        if rows:
            self.tbl.setCurrentCell(0, 0)
            self.tbl.setFocus()

    def pilih(self):
        row = self.tbl.currentRow()
        if row < 0 or row >= len(self._rows_data):
            return
        self.member_selected.emit(self._rows_data[row])
        self.accept()


# ═══════════════════════════════════════════════════════════════════════════════
# DIALOG DRAFT BILL
# ═══════════════════════════════════════════════════════════════════════════════
class DraftBillDialog(QDialog):
    draft_selected = pyqtSignal(str)  # nomor_draft

    def __init__(self, parent, kasir_id):
        super().__init__(parent)
        self.kasir_id = kasir_id
        self.setWindowTitle("📋 Recall Draft Bill")
        self.setModal(True)
        self.resize(500, 350)
        self.setStyleSheet("background-color: #f4f6f9;")
        self.init_ui()
        self.muat_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        self.tbl = QTableWidget()
        self.tbl.setColumnCount(4)
        self.tbl.setHorizontalHeaderLabels(["No Draft", "Waktu", "Item", "Total"])
        self.tbl.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #e0e0e0;
                font-size: 11pt;
            }
            QTableWidget::item:selected { background-color: #3498db; color: white; }
            QHeaderView::section {
                background-color: #2c3e50; color: white;
                padding: 8px; font-weight: bold;
            }
        """)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.keyPressEvent = self._table_key_press

        layout.addWidget(self.tbl, 1)

        btn_layout = QHBoxLayout()
        btn_pilih = QPushButton("✅ Pilih (Enter)")
        btn_pilih.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71; color: white;
                font-weight: bold; padding: 10px 20px; border-radius: 6px;
            }
        """)
        btn_pilih.clicked.connect(self.pilih)

        btn_hapus = QPushButton("🗑️ Hapus")
        btn_hapus.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: white;
                padding: 10px 20px; border-radius: 6px;
            }
        """)
        btn_hapus.clicked.connect(self.hapus_draft)

        btn_batal = QPushButton("❌ Batal (Esc)")
        btn_batal.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6; color: white;
                padding: 10px 20px; border-radius: 6px;
            }
        """)
        btn_batal.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_pilih)
        btn_layout.addWidget(btn_hapus)
        btn_layout.addWidget(btn_batal)
        layout.addLayout(btn_layout)

    def _table_key_press(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.pilih()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            QTableWidget.keyPressEvent(self.tbl, event)

    def muat_data(self):
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT nomor_draft, created_at, items_json, total
            FROM draft_bill_pos
            WHERE kasir_id = ?
            ORDER BY created_at DESC
        """, (self.kasir_id,))
        rows = cursor.fetchall()
        conn.close()

        self.tbl.setRowCount(0)
        self._rows_data = []

        for idx, r in enumerate(rows):
            self.tbl.insertRow(idx)
            self._rows_data.append(dict(r))

            self.tbl.setItem(idx, 0, QTableWidgetItem(r['nomor_draft']))
            self.tbl.setItem(idx, 1, QTableWidgetItem(r['created_at'][:16]))

            import json
            items = json.loads(r['items_json']) if r['items_json'] else []
            self.tbl.setItem(idx, 2, QTableWidgetItem(f"{len(items)} item"))

            total = QTableWidgetItem(fmt_rp(r['total']))
            total.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl.setItem(idx, 3, total)

        if rows:
            self.tbl.setCurrentCell(0, 0)

    def pilih(self):
        row = self.tbl.currentRow()
        if row < 0 or row >= len(self._rows_data):
            return
        self.draft_selected.emit(self._rows_data[row]['nomor_draft'])
        self.accept()

    def hapus_draft(self):
        row = self.tbl.currentRow()
        if row < 0:
            return
        nomor = self._rows_data[row]['nomor_draft']
        reply = QMessageBox.question(self, "Hapus", f"Hapus draft {nomor}?")
        if reply == QMessageBox.Yes:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM draft_bill_pos WHERE nomor_draft = ?", (nomor,))
            conn.commit()
            conn.close()
            self.muat_data()


# ═══════════════════════════════════════════════════════════════════════════════
# DIALOG CETAK STRUK (PDF Preview sebagai fallback)
# ═══════════════════════════════════════════════════════════════════════════════
class CetakStrukDialog(QDialog):
    def __init__(self, parent, faktur_data, items, is_copy=False):
        super().__init__(parent)
        self.faktur_data = faktur_data
        self.items = items
        self.is_copy = is_copy
        self.setWindowTitle("🖨️ Preview Struk" + (" (COPY)" if is_copy else ""))
        self.setModal(True)
        self.resize(400, 600)
        self.setStyleSheet("background-color: white;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Build struk text
        struk_text = self.build_struk_text()
        lbl = QLabel(struk_text)
        lbl.setStyleSheet("font-family: 'Courier New', monospace; font-size: 10pt;")
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(lbl)

        btn_layout = QHBoxLayout()
        btn_print = QPushButton("🖨️ Cetak ke Printer")
        btn_print.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71; color: white;
                font-weight: bold; padding: 10px 20px; border-radius: 6px;
            }
        """)
        btn_print.clicked.connect(self.cetak_thermal)

        btn_close = QPushButton("❌ Tutup")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6; color: white;
                padding: 10px 20px; border-radius: 6px;
            }
        """)
        btn_close.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_print)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def build_struk_text(self):
        fd = self.faktur_data
        lines = []
        lines.append("=" * 32)
        lines.append("    KUD TANI MAKMUR POS")
        lines.append("    Jl. Raya No. 123")
        lines.append("=" * 32)
        lines.append(f"No  : {fd.get('no_faktur', '')}")
        lines.append(f"Tgl : {fd.get('tanggal', datetime.now().strftime('%d/%m/%Y %H:%M:%S'))}")
        lines.append(f"Ksr : {fd.get('kasir', '')}")
        if self.is_copy:
            lines.append("*** COPY STRUK ***")
        lines.append("-" * 32)

        for item in self.items:
            nama = item.get('nama_barang', '')[:32]
            qty = item.get('qty', 0)
            harga = item.get('harga_jual', 0)
            subtotal = item.get('subtotal', 0)
            lines.append(f"{nama}")
            lines.append(f"  {qty} x {fmt_rp(harga)} = {fmt_rp(subtotal)}")

        lines.append("-" * 32)
        lines.append(f"TOTAL:     {fmt_rp(fd.get('subtotal', 0))}")
        lines.append(f"DISKON:    {fmt_rp(fd.get('diskon_global', 0))}")
        lines.append(f"GRAND:     {fmt_rp(fd.get('grand_total', 0))}")
        lines.append(f"BAYAR:     {fmt_rp(fd.get('bayar', 0))}")
        lines.append(f"KEMBALI:   {fmt_rp(fd.get('kembalian', 0))}")
        lines.append("=" * 32)
        lines.append("    TERIMA KASIH")
        lines.append(" SELAMAT BELANJA KEMBALI")
        lines.append("=" * 32)

        return "\n".join(lines)

    def cetak_thermal(self):
        """Coba cetak ke thermal printer via escpos"""
        try:
            from escpos.printer import Usb
            # Baca config dari app_settings
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'printer_vid'")
            vid_row = cursor.fetchone()
            cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'printer_pid'")
            pid_row = conn.execute("SELECT setting_value FROM app_settings WHERE setting_key = 'printer_pid'")
            conn.close()

            if not vid_row or not pid_row:
                QMessageBox.warning(self, "Printer", "Setting printer VID/PID belum diatur!")
                return

            vid = int(vid_row[0], 16) if vid_row[0] else None
            pid = int(pid_row[0], 16) if pid_row[0] else None

            if vid and pid:
                p = Usb(vid, pid)
                for line in self.build_struk_text().split('\n'):
                    p.text(line + "\n")
                p.cut()
                p.close()
                QMessageBox.information(self, "Sukses", "Struk tercetak!")
            else:
                QMessageBox.warning(self, "Printer", "VID/PID tidak valid!")

        except ImportError:
            QMessageBox.warning(self, "Printer", "Library escpos tidak terinstall!\nInstall: pip install python-escpos")
        except Exception as e:
            QMessageBox.critical(self, "Error Printer", str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN POS WIDGET
# ═══════════════════════════════════════════════════════════════════════════════
class POSKasirWidget(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.user_data = getattr(parent_window, 'current_user', {})
        self.role = self.user_data.get('role', 'KASIR')
        self.shift_data = None

        # State transaksi
        self.items = []  # list of dict item
        self.current_member = None
        self.current_member_data = None
        self._diskon_global = d(0)
        self._bayar = d(0)
        self._kembalian = d(0)
        self._metode = 'CASH'
        self._status = 'LUNAS'

        # Mode flags
        self._mode_harga_unit = False  # F11 mode
        self._mode_diskon_item = False  # F3 mode
        self._qty_buffer = None  # Buffer qty dari input angka

        self.setup_ui()
        self.setup_shortcuts()
        self.cek_shift()

    # ── UI SETUP ──────────────────────────────────────────────────────────────
    def setup_ui(self):
        main_layout = QHBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ── PANEL KIRI (60%) ──────────────────────────────────────────────────
        left_panel = QWidget()
        left_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)
        left_layout.setContentsMargins(12, 12, 8, 12)

        # Header info bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)

        self.lbl_no_faktur = QLabel("POS/...")
        self.lbl_no_faktur.setStyleSheet("font-weight: bold; color: #2196F3; font-size: 11pt;")
        header_layout.addWidget(QLabel("No:"))
        header_layout.addWidget(self.lbl_no_faktur)
        header_layout.addSpacing(20)

        self.lbl_member = QLabel("UMUM")
        self.lbl_member.setStyleSheet("font-weight: bold; color: #2ecc71;")
        header_layout.addWidget(QLabel("Member:"))
        header_layout.addWidget(self.lbl_member)

        self.lbl_member_info = QLabel("")
        self.lbl_member_info.setStyleSheet("color: #e67e22; font-size: 9pt;")
        header_layout.addWidget(self.lbl_member_info)
        header_layout.addStretch()

        self.lbl_tanggal = QLabel(datetime.now().strftime("%d/%m/%Y %H:%M"))
        self.lbl_tanggal.setStyleSheet("color: #7f8c8d;")
        header_layout.addWidget(self.lbl_tanggal)

        self.lbl_shift = QLabel("🔴 NO SHIFT")
        self.lbl_shift.setStyleSheet("font-weight: bold; color: #e74c3c; padding: 2px 8px; background: #fdf2f2; border-radius: 4px;")
        header_layout.addWidget(self.lbl_shift)

        left_layout.addLayout(header_layout)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #ddd;")
        left_layout.addWidget(sep)

        # ── SMART INPUT BOX ───────────────────────────────────────────────────
        input_group = QGroupBox("Input Barang (angka=qty | 8+digit=barcode | huruf=kode/nama)")
        input_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #2196F3;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #2196F3;
                font-size: 9pt;
            }
        """)
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)

        self.txt_input = QLineEdit()
        self.txt_input.setPlaceholderText("Contoh: 5 | 8991234567890 | ABC123 | Kopi ABC")
        self.txt_input.setStyleSheet("""
            QLineEdit {
                font-size: 14pt;
                padding: 10px;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                background: #f8f9fa;
            }
            QLineEdit:focus {
                border: 2px solid #2196F3;
                background: white;
            }
        """)
        self.txt_input.returnPressed.connect(self.process_input)
        input_layout.addWidget(self.txt_input, 1)

        # Qty display
        self.lbl_qty_preview = QLabel("Qty: 1")
        self.lbl_qty_preview.setStyleSheet("""
            font-weight: bold; color: #e74c3c; font-size: 12pt;
            padding: 8px 12px; background: #fdf2f2;
            border-radius: 4px;
        """)
        input_layout.addWidget(self.lbl_qty_preview)

        # Mode indicators
        self.lbl_mode_harga = QLabel("")
        self.lbl_mode_harga.setStyleSheet("""
            font-weight: bold; color: white; font-size: 9pt;
            padding: 4px 8px; background: #9b59b6;
            border-radius: 4px;
        """)
        self.lbl_mode_harga.setVisible(False)
        input_layout.addWidget(self.lbl_mode_harga)

        self.lbl_mode_diskon = QLabel("")
        self.lbl_mode_diskon.setStyleSheet("""
            font-weight: bold; color: white; font-size: 9pt;
            padding: 4px 8px; background: #e67e22;
            border-radius: 4px;
        """)
        self.lbl_mode_diskon.setVisible(False)
        input_layout.addWidget(self.lbl_mode_diskon)

        input_group.setLayout(input_layout)
        left_layout.addWidget(input_group)

        # ── ITEM LIST TABLE ───────────────────────────────────────────────────
        list_label = QLabel("DAFTAR ITEM (Del=Hapus | Enter=Edit Qty | ↑↓=Navigasi)")
        list_label.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 9pt;")
        left_layout.addWidget(list_label)

        self.tbl_items = QTableWidget()
        self.tbl_items.setColumnCount(7)
        self.tbl_items.setHorizontalHeaderLabels(["#", "Kode", "Nama Barang", "Qty", "Sat", "Harga", "Subtotal"])
        self.tbl_items.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #e0e0e0;
                border: 1px solid #d0d0d0;
                font-size: 10pt;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e8e8e8;
            }
            QTableWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 8px;
                font-weight: bold;
            }
        """)
        self.tbl_items.horizontalHeader().setStretchLastSection(True)
        self.tbl_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tbl_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.tbl_items.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.tbl_items.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.tbl_items.setColumnWidth(0, 40)
        self.tbl_items.setColumnWidth(1, 100)
        self.tbl_items.setColumnWidth(3, 60)
        self.tbl_items.setColumnWidth(4, 50)
        self.tbl_items.verticalHeader().setVisible(False)
        self.tbl_items.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_items.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl_items.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_items.installEventFilter(self)

        left_layout.addWidget(self.tbl_items, 1)

        # Item count
        self.lbl_item_count = QLabel("0 item | 0 pcs")
        self.lbl_item_count.setStyleSheet("color: #7f8c8d; font-size: 9pt;")
        left_layout.addWidget(self.lbl_item_count)

        # Mode status bar
        mode_bar = QHBoxLayout()
        self.lbl_mode_status = QLabel("Mode: ECER | Promo: OFF")
        self.lbl_mode_status.setStyleSheet("""
            font-size: 9pt; color: #2c3e50;
            padding: 4px 10px; background: #eaf2f8;
            border-radius: 4px;
        """)
        mode_bar.addWidget(self.lbl_mode_status)
        mode_bar.addStretch()
        left_layout.addLayout(mode_bar)

        left_panel.setLayout(left_layout)

        # ── PANEL KANAN (40%) ─────────────────────────────────────────────────
        right_panel = QWidget()
        right_panel.setFixedWidth(380)
        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)
        right_layout.setContentsMargins(8, 12, 12, 12)
        right_panel.setStyleSheet("background-color: #f5f6fa;")

        # Title
        title = QLabel("💰 RINGKASAN")
        title.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 12pt;")
        title.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(title)

        # Summary card
        summary_frame = QFrame()
        summary_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }
        """)
        summary_layout = QVBoxLayout()
        summary_layout.setSpacing(12)
        summary_layout.setContentsMargins(15, 15, 15, 15)

        # Total
        total_layout = QHBoxLayout()
        total_layout.addWidget(QLabel("SUBTOTAL:"))
        total_layout.addStretch()
        self.lbl_subtotal = QLabel("Rp 0")
        self.lbl_subtotal.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 14pt;")
        total_layout.addWidget(self.lbl_subtotal)
        summary_layout.addLayout(total_layout)

        # Diskon
        diskon_layout = QHBoxLayout()
        diskon_layout.addWidget(QLabel("DISKON:"))
        diskon_layout.addStretch()
        self.lbl_diskon = QLabel("Rp 0")
        self.lbl_diskon.setStyleSheet("font-weight: bold; color: #e74c3c;")
        diskon_layout.addWidget(self.lbl_diskon)
        summary_layout.addLayout(diskon_layout)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("background-color: #e0e0e0;")
        summary_layout.addWidget(sep2)

        # Grand Total
        grand_layout = QHBoxLayout()
        grand_layout.addWidget(QLabel("GRAND TOTAL:"))
        grand_layout.addStretch()
        self.lbl_grand_total = QLabel("Rp 0")
        self.lbl_grand_total.setStyleSheet("font-weight: bold; color: #e74c3c; font-size: 18pt;")
        grand_layout.addWidget(self.lbl_grand_total)
        summary_layout.addLayout(grand_layout)

        # Bayar
        bayar_layout = QHBoxLayout()
        bayar_layout.addWidget(QLabel("BAYAR:"))
        bayar_layout.addStretch()
        self.lbl_bayar = QLabel("Rp 0")
        self.lbl_bayar.setStyleSheet("font-weight: bold; color: #2ecc71; font-size: 14pt;")
        bayar_layout.addWidget(self.lbl_bayar)
        summary_layout.addLayout(bayar_layout)

        # Kembali
        kembali_layout = QHBoxLayout()
        kembali_layout.addWidget(QLabel("KEMBALI:"))
        kembali_layout.addStretch()
        self.lbl_kembali = QLabel("Rp 0")
        self.lbl_kembali.setStyleSheet("font-weight: bold; color: #3498db; font-size: 14pt;")
        kembali_layout.addWidget(self.lbl_kembali)
        summary_layout.addLayout(kembali_layout)

        # Status
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("STATUS:"))
        status_layout.addStretch()
        self.lbl_status = QLabel("🟡 BELUM BAYAR")
        self.lbl_status.setStyleSheet("""
            font-weight: bold; color: #f39c12;
            padding: 4px 12px; background: #fef5e7;
            border-radius: 4px;
        """)
        status_layout.addWidget(self.lbl_status)
        summary_layout.addLayout(status_layout)

        summary_frame.setLayout(summary_layout)
        right_layout.addWidget(summary_frame)

        # Quick Action Buttons
        actions_label = QLabel("⌨️ TOMBOL CEPAT")
        actions_label.setStyleSheet("font-weight: bold; color: #7f8c8d; font-size: 9pt;")
        actions_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(actions_label)

        # Button grid
        btn_grid = QGridLayout()
        btn_grid.setSpacing(6)

        buttons = [
            ("F1\nFOKUS", "#3498db", self.focus_input),
            ("F2\nBAYAR", "#2ecc71", self.show_bayar_dialog),
            ("F3\nDISKON\nITEM", "#e67e22", self.toggle_diskon_item_mode),
            ("F4\nDISKON\nGLOBAL", "#9b59b6", self.show_diskon_global_dialog),
            ("F5\nHOLD", "#34495e", self.simpan_draft),
            ("F6\nRECALL", "#1abc9c", self.recall_draft),
            ("F7\nMEMBER", "#16a085", self.pilih_member),
            ("F8\nSIMPAN", "#2196F3", self.simpan_transaksi),
            ("F9\nREPRINT", "#8e44ad", self.reprint_struk),
            ("F10\nRETUR", "#c0392b", self.show_retur_dialog),
            ("F11\nHARGA 1", "#6c5ce7", self.toggle_harga_unit_mode),
            ("ESC\nBATAL", "#95a5a6", self.batal_transaksi),
        ]

        for i, (text, color, callback) in enumerate(buttons):
            btn = QPushButton(text)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    font-size: 8pt;
                    padding: 10px 6px;
                    border-radius: 6px;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {color};
                    opacity: 0.85;
                }}
                QPushButton:pressed {{
                    background-color: {color};
                    opacity: 0.7;
                }}
            """)
            btn.clicked.connect(callback)
            btn_grid.addWidget(btn, i // 2, i % 2)

        right_layout.addLayout(btn_grid)

        # Help text
        help_text = QLabel("Enter=Tambah | Del=Hapus | ↑↓=Navigasi | F11=Harga Unit | F3=Diskon Item")
        help_text.setStyleSheet("color: #95a5a6; font-size: 8pt;")
        help_text.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(help_text)

        right_layout.addStretch()
        right_panel.setLayout(right_layout)

        # ── SPLITTER ──────────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([600, 380])
        splitter.setHandleWidth(2)
        splitter.setStyleSheet("QSplitter::handle { background: #ddd; }")

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    # ── SHORTCUTS ─────────────────────────────────────────────────────────────
    def setup_shortcuts(self):
        shortcuts = [
            ("F1", self.focus_input),
            ("F2", self.show_bayar_dialog),
            ("F3", self.toggle_diskon_item_mode),
            ("F4", self.show_diskon_global_dialog),
            ("F5", self.simpan_draft),
            ("F6", self.recall_draft),
            ("F7", self.pilih_member),
            ("F8", self.simpan_transaksi),
            ("F9", self.reprint_struk),
            ("F10", self.show_retur_dialog),
            ("F11", self.toggle_harga_unit_mode),
            ("Esc", self.batal_transaksi),
        ]
        for key, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)

    # ── EVENT FILTER ──────────────────────────────────────────────────────────
    def eventFilter(self, obj, event):
        if obj == self.tbl_items and event.type() == event.KeyPress:
            key = event.key()
            if key == Qt.Key_Delete:
                self.hapus_item_terpilih()
                return True
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                self.edit_qty_item()
                return True
        return super().eventFilter(obj, event)

    # ── SHIFT MANAGEMENT ──────────────────────────────────────────────────────
    def cek_shift(self):
        shift = cek_shift_aktif(self.user_data.get('id'))
        if shift:
            self.shift_data = shift
            self.lbl_shift.setText("🟢 SHIFT AKTIF")
            self.lbl_shift.setStyleSheet("""
                font-weight: bold; color: #2ecc71;
                padding: 2px 8px; background: #eafaf1;
                border-radius: 4px;
            """)
            self.reset_form()
        else:
            self.lbl_shift.setText("🔴 NO SHIFT - BUKA DULU")
            self.lbl_shift.setStyleSheet("""
                font-weight: bold; color: #e74c3c;
                padding: 2px 8px; background: #fdf2f2;
                border-radius: 4px;
            """)
            # Auto buka shift dialog
            QTimer.singleShot(500, self.buka_shift_dialog)

    def buka_shift_dialog(self):
        dlg = BukaShiftDialog(self, self.user_data)
        if dlg.exec_() == QDialog.Accepted:
            self.cek_shift()
        else:
            # Kalau batal, kasih warning tapi tetap bisa lihat UI (tapi tidak bisa transaksi)
            pass

    # ── SMART INPUT ───────────────────────────────────────────────────────────
    def focus_input(self):
        self.txt_input.setFocus()
        self.txt_input.selectAll()

    def process_input(self):
        text = self.txt_input.text().strip()
        if not text:
            return

        # Deteksi: pure angka = qty buffer
        if text.isdigit():
            angka = int(text)
            if angka > 0 and len(text) < 8:  # Bukan barcode (kurang dari 8 digit)
                self._qty_buffer = float(angka)
                self.lbl_qty_preview.setText(f"Qty: {angka}")
                self.txt_input.clear()
                self.txt_input.setPlaceholderText(f"Qty: {angka} | Ketik kode/barang...")
                self.txt_input.setFocus()
                return

        # Deteksi: barcode (8+ digit pure number)
        if text.isdigit() and len(text) >= 8:
            self.cari_dan_tambah(text, is_barcode=True)
            return

        # Deteksi: kode atau nama
        self.cari_dan_tambah(text, is_barcode=False)

    def cari_dan_tambah(self, search_term, is_barcode=False, qty_override=None):
        """Cari barang dan tambah ke keranjang"""
        qty = qty_override or self._qty_buffer or 1.0

        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if is_barcode:
            cursor.execute("""
                SELECT * FROM master_barang
                WHERE kode_barcode = ? AND stok_isi > 0
            """, (search_term,))
        else:
            # Cari kode exact dulu
            cursor.execute("""
                SELECT * FROM master_barang
                WHERE kode_barang = ? AND stok_isi > 0
            """, (search_term,))
            if not cursor.fetchone():
                # Kalau tidak ketemu exact, cari LIKE → tabel pilih
                conn.close()
                self.show_pencarian_dialog(search_term, qty)
                return
            # Re-execute untuk ambil data
            cursor.execute("""
                SELECT * FROM master_barang
                WHERE kode_barang = ? AND stok_isi > 0
            """, (search_term,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            QMessageBox.warning(self, "Tidak Ditemukan", f"Barang '{search_term}' tidak ditemukan atau stok habis!")
            self.txt_input.selectAll()
            self.txt_input.setFocus()
            return

        barang = dict(row)
        self.tambah_ke_keranjang(barang, qty)

    def show_pencarian_dialog(self, keyword, qty_default=1):
        """Tampilkan dialog hasil LIKE search"""
        dlg = HasilPencarianDialog(self, keyword, qty_default)
        dlg.barang_selected.connect(self.on_barang_dipilih)
        dlg.exec_()

    def on_barang_dipilih(self, barang, qty):
        self.tambah_ke_keranjang(barang, qty)

    def tambah_ke_keranjang(self, barang, qty):
        """Tambah barang ke keranjang dengan mode aktif"""
        if not self.shift_data:
            QMessageBox.warning(self, "No Shift", "Buka shift dulu!")
            return

        qty_dec = d(qty)
        barang_id = barang['id']

        # Cek stok
        stok = d(barang.get('stok_isi', 0))
        if qty_dec > stok:
            QMessageBox.warning(self, "Stok Tidak Cukup",
                f"Stok tidak mencukupi!\nButuh: {qty_dec}\nStok: {stok}")
            self.txt_input.clear()
            self.txt_input.setFocus()
            return

        # Hitung harga
        mode_harga = 'UNIT' if self._mode_harga_unit else 'ECER'
        harga = get_harga_jual(barang, qty, mode_harga)

        # Cek mode diskon item
        diskon_item = d(0)
        if self._mode_diskon_item:
            diskon_val, ok = QInputDialog.getDouble(
                self, "Diskon Item",
                f"Diskon untuk {barang['nama_barang']}:\nHarga: {fmt_rp(harga)}\nQty: {qty}",
                0, 0, float(harga * qty_dec), 2
            )
            if ok:
                diskon_item = d(diskon_val)
            # Reset mode diskon item
            self._mode_diskon_item = False
            self.lbl_mode_diskon.setVisible(False)
            self.update_mode_status()

        subtotal = (qty_dec * harga) - diskon_item

        # Cek merge (barang sudah ada di keranjang)
        existing_idx = None
        for i, item in enumerate(self.items):
            if item['barang_id'] == barang_id and item['mode_harga'] == mode_harga and diskon_item == 0:
                existing_idx = i
                break

        if existing_idx is not None:
            # Merge qty
            item = self.items[existing_idx]
            new_qty = d(item['qty']) + qty_dec
            if new_qty > stok:
                QMessageBox.warning(self, "Stok Tidak Cukup",
                    f"Total stok tidak mencukupi!\nTotal butuh: {new_qty}\nStok: {stok}")
                return
            new_harga = get_harga_jual(barang, float(new_qty), mode_harga)
            new_subtotal = (new_qty * new_harga) - d(item.get('diskon_item', 0))

            item['qty'] = float(new_qty)
            item['harga_jual'] = float(new_harga)
            item['subtotal'] = float(new_subtotal)
        else:
            self.items.append({
                'barang_id': barang_id,
                'kode_barang': barang['kode_barang'],
                'nama_barang': barang['nama_barang'],
                'qty': float(qty_dec),
                'satuan': barang.get('satuan', 'PCS'),
                'harga_jual': float(harga),
                'diskon_item': float(diskon_item),
                'subtotal': float(subtotal),
                'mode_harga': mode_harga
            })

        # Reset buffer & mode
        self._qty_buffer = None
        self.lbl_qty_preview.setText("Qty: 1")

        # Reset mode harga unit (auto-reset setelah 1 item)
        if self._mode_harga_unit:
            self._mode_harga_unit = False
            self.lbl_mode_harga.setVisible(False)

        self.refresh_table()
        self.hitung_total()
        self.txt_input.clear()
        self.txt_input.setFocus()

    # ── TABLE OPERATIONS ──────────────────────────────────────────────────────
    def refresh_table(self):
        self.tbl_items.setRowCount(0)
        for i, item in enumerate(self.items, 1):
            row = self.tbl_items.rowCount
            self.tbl_items.insertRow(idx)

            # No
            no_item = QTableWidgetItem(str(i))
            no_item.setTextAlignment(Qt.AlignCenter)
            self.tbl_items.setItem(idx, 0, no_item)

            # Kode
            self.tbl_items.setItem(idx, 1, QTableWidgetItem(item['kode_barang']))

            # Nama
            nama = item['nama_barang']
            if item.get('mode_harga') == 'UNIT':
                nama += " [UNIT]"
            if item.get('diskon_item', 0) > 0:
                nama += " (-DISKON)"
            self.tbl_items.setItem(idx, 2, QTableWidgetItem(nama))

            # Qty
            qty_item = QTableWidgetItem(str(item['qty']))
            qty_item.setTextAlignment(Qt.AlignCenter)
            self.tbl_items.setItem(idx, 3, qty_item)

            # Satuan
            sat_item = QTableWidgetItem(item['satuan'])
            sat_item.setTextAlignment(Qt.AlignCenter)
            self.tbl_items.setItem(idx, 4, sat_item)

            # Harga
            harga_item = QTableWidgetItem(fmt_rp(item['harga_jual']))
            harga_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl_items.setItem(idx, 5, harga_item)

            # Subtotal
            subtotal_item = QTableWidgetItem(fmt_rp(item['subtotal']))
            subtotal_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl_items.setItem(idx, 6, subtotal_item)

            # Zebra striping
            if idx % 2 == 1:
                for col in range(7):
                    it = self.tbl_items.item(idx, col)
                    if it:
                        it.setBackground(QBrush(QColor(245, 245, 245)))

        total_pcs = sum(d(item['qty']) for item in self.items)
        self.lbl_item_count.setText(f"{len(self.items)} item | {total_pcs} pcs")

    def hapus_item_terpilih(self):
        row = self.tbl_items.currentRow()
        if row >= 0 and row < len(self.items):
            del self.items[row]
            self.refresh_table()
            self.hitung_total()
            self.txt_input.setFocus()

    def edit_qty_item(self):
        row = self.tbl_items.currentRow()
        if row < 0 or row >= len(self.items):
            return

        item = self.items[row]
        qty, ok = QInputDialog.getDouble(
            self, "Edit Qty",
            f"Qty untuk {item['nama_barang']}:",
            item['qty'], 0.01, 9999, 2
        )
        if ok:
            qty_dec = d(qty)

            # Cek stok
            conn = sqlite3.connect(DB_NAME)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT stok_isi FROM master_barang WHERE id = ?", (item['barang_id'],))
            row_data = cursor.fetchone()
            conn.close()

            stok = d(row_data['stok_isi']) if row_data else d(0)
            used = sum(d(i['qty']) for i in self.items if i['barang_id'] == item['barang_id'] and i != item)
            available = stok - used

            if qty_dec > available:
                QMessageBox.warning(self, "Stok Tidak Cukup",
                    f"Stok tidak mencukupi!\nTersedia: {available}")
                return

            # Recalculate harga
            conn = sqlite3.connect(DB_NAME)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM master_barang WHERE id = ?", (item['barang_id'],))
            barang = dict(cursor.fetchone())
            conn.close()

            harga = get_harga_jual(barang, float(qty_dec), item.get('mode_harga', 'ECER'))
            subtotal = (qty_dec * harga) - d(item.get('diskon_item', 0))

            item['qty'] = float(qty_dec)
            item['harga_jual'] = float(harga)
            item['subtotal'] = float(subtotal)

            self.refresh_table()
            self.hitung_total()

        self.txt_input.setFocus()

    # ── TOTAL CALCULATIONS ────────────────────────────────────────────────────
    def hitung_total(self):
        subtotal = sum(d(item['subtotal']) for item in self.items)
        diskon = self._diskon_global
        grand = subtotal - diskon

        self.lbl_subtotal.setText(fmt_rp(subtotal))
        self.lbl_diskon.setText(fmt_rp(diskon))
        self.lbl_grand_total.setText(fmt_rp(grand))

        self.lbl_bayar.setText(fmt_rp(self._bayar))
        kembalian = self._bayar - grand if self._status == 'LUNAS' else d(0)
        self.lbl_kembali.setText(fmt_rp(kembalian))

        # Update status label
        if self._status == 'LUNAS' and self._bayar >= grand:
            self.lbl_status.setText("✅ LUNAS")
            self.lbl_status.setStyleSheet("""
                font-weight: bold; color: #2ecc71;
                padding: 4px 12px; background: #eafaf1;
                border-radius: 4px;
            """)
        elif self._status == 'HUTANG':
            self.lbl_status.setText("💳 HUTANG")
            self.lbl_status.setStyleSheet("""
                font-weight: bold; color: #e67e22;
                padding: 4px 12px; background: #fef5e7;
                border-radius: 4px;
            """)
        else:
            self.lbl_status.setText("🟡 BELUM BAYAR")
            self.lbl_status.setStyleSheet("""
                font-weight: bold; color: #f39c12;
                padding: 4px 12px; background: #fef5e7;
                border-radius: 4px;
            """)

    # ── MODE TOGGLES ──────────────────────────────────────────────────────────
    def toggle_harga_unit_mode(self):
        """F11 - Mode Harga Jual 1 (unit)"""
        self._mode_harga_unit = not self._mode_harga_unit
        if self._mode_harga_unit:
            self.lbl_mode_harga.setText("MODE: HARGA UNIT (F11)")
            self.lbl_mode_harga.setVisible(True)
        else:
            self.lbl_mode_harga.setVisible(False)
        self.update_mode_status()
        self.txt_input.setFocus()

    def toggle_diskon_item_mode(self):
        """F3 - Mode Diskon Item"""
        self._mode_diskon_item = not self._mode_diskon_item
        if self._mode_diskon_item:
            self.lbl_mode_diskon.setText("MODE: DISKON ITEM (F3)")
            self.lbl_mode_diskon.setVisible(True)
        else:
            self.lbl_mode_diskon.setVisible(False)
        self.update_mode_status()
        self.txt_input.setFocus()

    def update_mode_status(self):
        modes = []
        if self._mode_harga_unit:
            modes.append("UNIT")
        else:
            modes.append("ECER")

        if self._mode_diskon_item:
            modes.append("DISKON-ITEM")

        self.lbl_mode_status.setText(f"Mode: {' | '.join(modes)}")

    # ── ACTIONS ───────────────────────────────────────────────────────────────
    def show_bayar_dialog(self):
        """F2 - Bayar"""
        if not self.items:
            QMessageBox.warning(self, "Kosong", "Tidak ada item untuk dibayar")
            return

        grand = sum(d(item['subtotal']) for item in self.items) - self._diskon_global
        dlg = BayarDialog(self, grand, float(self._bayar))
        if dlg.exec_() == QDialog.Accepted:
            self._bayar = dlg.result['bayar']
            self._metode = dlg.result['metode']
            self._kembalian = dlg.result['kembalian']
            self._status = 'HUTANG' if self._metode == 'HUTANG' else 'LUNAS'
            self.hitung_total()

            # Auto simpan kalau LUNAS
            if self._status == 'LUNAS':
                self.simpan_transaksi()

        self.txt_input.setFocus()

    def show_diskon_global_dialog(self):
        """F4 - Diskon Global"""
        if not self.items:
            QMessageBox.warning(self, "Kosong", "Tidak ada item")
            return

        diskon, ok = QInputDialog.getDouble(
            self, "Diskon Global",
            "Masukkan nominal diskon transaksi:",
            float(self._diskon_global), 0, 999999999, 2
        )
        if ok:
            self._diskon_global = d(diskon)
            self.hitung_total()
        self.txt_input.setFocus()

    def simpan_draft(self):
        """F5 - Hold/Draft Bill"""
        if not self.items:
            return

        import json
        nomor = f"DRAFT-{datetime.now().strftime('%H%M%S')}"
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO draft_bill_pos (id, nomor_draft, kasir_id, username, items_json, total, member_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            uuid.uuid4().bytes, nomor,
            self.user_data.get('id'), self.user_data.get('username', ''),
            json.dumps(self.items),
            float(sum(d(item['subtotal']) for item in self.items)),
            self.current_member
        ))
        conn.commit()
        conn.close()

        QMessageBox.information(self, "Draft Tersimpan", f"Bill disimpan sebagai {nomor}")
        self.reset_form()

    def recall_draft(self):
        """F6 - Recall Draft"""
        import json
        dlg = DraftBillDialog(self, self.user_data.get('id'))
        if dlg.exec_() == QDialog.Accepted and dlg.draft_selected:
            nomor = dlg.draft_selected
            conn = sqlite3.connect(DB_NAME)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM draft_bill_pos WHERE nomor_draft = ?
            """, (nomor,))
            row = cursor.fetchone()
            conn.close()

            if row:
                self.items = json.loads(row['items_json'])
                if row['member_id']:
                    # Restore member
                    conn = sqlite3.connect(DB_NAME)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM master_member WHERE id = ?", (row['member_id'],))
                    member = cursor.fetchone()
                    conn.close()
                    if member:
                        self.current_member = member['id']
                        self.current_member_data = dict(member)
                        self.lbl_member.setText(member['nama_member'][:20])
                        self.lbl_member_info.setText(f"Hutang: {fmt_rp(member['ttl_hutang'])}")

                self.refresh_table()
                self.hitung_total()

                # Hapus draft setelah di-recall
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM draft_bill_pos WHERE nomor_draft = ?", (nomor,))
                conn.commit()
                conn.close()

        self.txt_input.setFocus()

    def pilih_member(self):
        """F7 - Pilih Member"""
        dlg = PilihMemberDialog(self)
        dlg.member_selected.connect(self.set_member)
        dlg.exec_()

    def set_member(self, member_data):
        self.current_member = member_data['id']
        self.current_member_data = member_data
        self.lbl_member.setText(member_data['nama_member'][:20])
        self.lbl_member_info.setText(f"Hutang: {fmt_rp(member_data['ttl_hutang'])}")
        self.txt_input.setFocus()

    def simpan_transaksi(self):
        """F8 - Simpan Transaksi"""
        if not self.items:
            QMessageBox.warning(self, "Kosong", "Tidak ada item")
            return

        if not self.shift_data:
            QMessageBox.warning(self, "No Shift", "Buka shift dulu!")
            return

        subtotal = sum(d(item['subtotal']) for item in self.items)
        grand = subtotal - self._diskon_global

        # Validasi bayar untuk LUNAS
        if self._status == 'LUNAS' and self._bayar < grand:
            QMessageBox.warning(self, "Kurang",
                f"Bayar kurang!\nGrand: {fmt_rp(grand)}\nBayar: {fmt_rp(self._bayar)}")
            self.show_bayar_dialog()
            return

        # Validasi hutang: harus ada member
        if self._status == 'HUTANG' and not self.current_member:
            QMessageBox.warning(self, "Member Diperlukan", "Pilih member dulu untuk transaksi hutang (F7)")
            self.pilih_member()
            return

        # Generate no faktur
        outlet_kode = 'OUT001'  # Default, bisa dari config
        no_faktur = gen_no_faktur_pos(outlet_kode)

        # Simpan ke DB
        faktur_id = uuid.uuid4().bytes
        now = datetime.now().isoformat()
        total_qty = sum(d(item['qty']) for item in self.items)
        total_item = len(self.items)

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        try:
            # Insert faktur
            cursor.execute("""
                INSERT INTO faktur_jual_pos (
                    id, no_faktur, shift_id, user_id, username, outlet_id,
                    member_id, kode_member, nama_member,
                    total_item, total_qty, subtotal, diskon_global, grand_total,
                    bayar, kembalian, metode_bayar, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                faktur_id, no_faktur, self.shift_data['id'],
                self.user_data.get('id'), self.user_data.get('username', ''),
                self.user_data.get('outlet_id'),
                self.current_member,
                self.current_member_data.get('kode_member', '') if self.current_member_data else '',
                self.current_member_data.get('nama_member', '') if self.current_member_data else '',
                total_item, float(total_qty), float(subtotal), float(self._diskon_global),
                float(grand), float(self._bayar), float(self._kembalian),
                self._metode, self._status, now
            ))

            # Insert detail
            for item in self.items:
                detil_id = uuid.uuid4().bytes
                cursor.execute("""
                    INSERT INTO detil_jual_pos (
                        id, faktur_id, barang_id, kode_barang, nama_barang,
                        qty, satuan, harga_jual, diskon_item, subtotal, mode_harga
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    detil_id, faktur_id, item['barang_id'],
                    item['kode_barang'], item['nama_barang'],
                    item['qty'], item['satuan'],
                    item['harga_jual'], item['diskon_item'],
                    item['subtotal'], item.get('mode_harga', 'ECER')
                ))

                # Update stok
                cursor.execute("""
                    UPDATE master_barang SET stok_isi = stok_isi - ?
                    WHERE id = ?
                """, (item['qty'], item['barang_id']))

                # Kartu stok keluar
                kartu_id = uuid.uuid4().bytes
                cursor.execute("""
                    INSERT INTO kartu_stok (
                        id, kode_barang, nama_barang, tanggal, jenis,
                        qty_keluar, harga_satuan, saldo_qty, referensi_no, keterangan, user_input
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    kartu_id, item['kode_barang'], item['nama_barang'],
                    now[:10], 'KELUAR', item['qty'], item['harga_jual'],
                    0,  # Saldo akan dihitung trigger atau app layer
                    no_faktur, f"Penjualan POS - {self._metode}",
                    self.user_data.get('username', '')
                ))

            # Update hutang member kalau HUTANG
            if self._status == 'HUTANG' and self.current_member:
                hutang_baru = d(self.current_member_data.get('ttl_hutang', 0)) + grand
                cursor.execute("""
                    UPDATE master_member SET ttl_hutang = ?, status_hutang = ?
                    WHERE id = ?
                """, (float(hutang_baru), 'BELUM LUNAS', self.current_member))

                # Detail hutang member
                dethut_id = uuid.uuid4().bytes
                cursor.execute("""
                    INSERT INTO dethut_member (
                        id, member_id, tanggal, jenis_transaksi,
                        debet, kredit, total_hutang
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    dethut_id, self.current_member, now,
                    f"Penjualan POS - {no_faktur}",
                    float(grand), 0.0, float(hutang_baru)
                ))

            conn.commit()

            # Cetak struk
            faktur_data = {
                'no_faktur': no_faktur,
                'tanggal': now,
                'kasir': self.user_data.get('nama_lengkap', ''),
                'subtotal': float(subtotal),
                'diskon_global': float(self._diskon_global),
                'grand_total': float(grand),
                'bayar': float(self._bayar),
                'kembalian': float(self._kembalian),
                'metode': self._metode,
                'status': self._status
            }

            self.cetak_struk(faktur_data, self.items)

            QMessageBox.information(self, "Sukses",
                f"Transaksi tersimpan!\nNo: {no_faktur}\nTotal: {fmt_rp(grand)}")

            self.reset_form()

        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Gagal simpan transaksi:\n{str(e)}")
        finally:
            conn.close()

    def cetak_struk(self, faktur_data, items, is_copy=False):
        """Cetak struk via dialog preview (dengan opsi thermal printer)"""
        dlg = CetakStrukDialog(self, faktur_data, items, is_copy)
        dlg.exec_()

    def reprint_struk(self):
        """F9 - Reprint struk"""
        no_faktur, ok = QInputDialog.getText(self, "Reprint Struk", "No. Faktur:")
        if ok and no_faktur:
            conn = sqlite3.connect(DB_NAME)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM faktur_jual_pos WHERE no_faktur = ?", (no_faktur,))
            faktur = cursor.fetchone()
            if faktur:
                cursor.execute("""
                    SELECT * FROM detil_jual_pos WHERE faktur_id = ?
                """, (faktur['id'],))
                items = [dict(r) for r in cursor.fetchall()]
                conn.close()

                faktur_data = {
                    'no_faktur': faktur['no_faktur'],
                    'tanggal': faktur['created_at'],
                    'kasir': faktur['username'],
                    'subtotal': faktur['subtotal'],
                    'diskon_global': faktur['diskon_global'],
                    'grand_total': faktur['grand_total'],
                    'bayar': faktur['bayar'],
                    'kembalian': faktur['kembalian'],
                    'metode': faktur['metode_bayar'],
                    'status': faktur['status']
                }
                self.cetak_struk(faktur_data, items, is_copy=True)
            else:
                conn.close()
                QMessageBox.warning(self, "Tidak Ditemukan", f"Faktur {no_faktur} tidak ditemukan")

    def show_retur_dialog(self):
        """F10 - Retur (placeholder, bisa diimplementasi nanti)"""
        QMessageBox.information(self, "Retur", "Fitur retur POS akan diimplementasikan di update berikutnya.\nGunakan menu RETUR JUAL POS di sidebar.")

    def batal_transaksi(self):
        """ESC - Batal/Reset"""
        if self.items:
            reply = QMessageBox.question(
                self, "Batal", "Yakin batalkan transaksi ini?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                self.txt_input.setFocus()
                return
        self.reset_form()

    def reset_form(self):
        self.items = []
        self.current_member = None
        self.current_member_data = None
        self._diskon_global = d(0)
        self._bayar = d(0)
        self._kembalian = d(0)
        self._metode = 'CASH'
        self._status = 'LUNAS'
        self._qty_buffer = None
        self._mode_harga_unit = False
        self._mode_diskon_item = False

        self.lbl_mode_harga.setVisible(False)
        self.lbl_mode_diskon.setVisible(False)
        self.update_mode_status()

        self.lbl_member.setText("UMUM")
        self.lbl_member_info.setText("")

        outlet_kode = 'OUT001'
        self.lbl_no_faktur.setText(gen_no_faktur_pos(outlet_kode))
        self.lbl_tanggal.setText(datetime.now().strftime("%d/%m/%Y %H:%M"))

        self.refresh_table()
        self.hitung_total()
        self.txt_input.clear()
        self.txt_input.setPlaceholderText("Contoh: 5 | 8991234567890 | ABC123 | Kopi ABC")
        self.txt_input.setFocus()
