import sys
import sqlite3
import uuid
import os
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
                             QAbstractItemView, QHeaderView, QMessageBox, QDialog, 
                             QFormLayout, QFileDialog, QComboBox, QMainWindow, QApplication)
from PyQt5.QtCore import Qt, QSizeF
from PyQt5.QtGui import QTextDocument, QColor
from widgets import get_font
from PyQt5.QtPrintSupport import QPrinter

DB_NAME = "pos_inventory.db"

def init_supplier_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS master_supplier (id BLOB PRIMARY KEY)")
    cursor.execute("PRAGMA table_info(master_supplier)")
    kolom_master = [info[1] for info in cursor.fetchall()]

    if "kode_supplier" not in kolom_master:
        cursor.execute("ALTER TABLE master_supplier ADD COLUMN kode_supplier TEXT NOT NULL DEFAULT ''")
    if "nama_supplier" not in kolom_master:
        cursor.execute("ALTER TABLE master_supplier ADD COLUMN nama_supplier TEXT NOT NULL DEFAULT ''")
    if "alamat_supplier" not in kolom_master:
        cursor.execute("ALTER TABLE master_supplier ADD COLUMN alamat_supplier TEXT NOT NULL DEFAULT ''")
    if "nama_sales" not in kolom_master:
        cursor.execute("ALTER TABLE master_supplier ADD COLUMN nama_sales TEXT NOT NULL DEFAULT ''")
    if "telepon_sales" not in kolom_master:
        cursor.execute("ALTER TABLE master_supplier ADD COLUMN telepon_sales TEXT NOT NULL DEFAULT ''")
    if "pembayaran_cash" not in kolom_master:
        cursor.execute("ALTER TABLE master_supplier ADD COLUMN pembayaran_cash TEXT NOT NULL DEFAULT 'YES'")
    if "pembayaran_tempo" not in kolom_master:
        cursor.execute("ALTER TABLE master_supplier ADD COLUMN pembayaran_tempo TEXT NOT NULL DEFAULT 'NO'")
    if "jatuh_tempo_hari" not in kolom_master:
        cursor.execute("ALTER TABLE master_supplier ADD COLUMN jatuh_tempo_hari INTEGER NOT NULL DEFAULT 0")
    if "keterangan" not in kolom_master:
        cursor.execute("ALTER TABLE master_supplier ADD COLUMN keterangan TEXT NOT NULL DEFAULT ''")
    conn.commit()
    conn.close()

class FormSupplierDialog(QDialog):
    def __init__(self, parent=None, data_edit=None):
        super().__init__(parent)
        self.data_edit = data_edit 
        self.init_ui()

    def init_ui(self):
        is_edit = self.data_edit is not None
        self.setWindowTitle("✏️ Edit Data Supplier" if is_edit else "➕ Tambah Supplier Baru")
        self.setModal(True)
        self.resize(420, 380)
        self.setStyleSheet("background-color: #f4f6f9;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(12)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.input_kode = QLineEdit(self)
        self.input_kode.setPlaceholderText("Contoh: KSUP01")
        self.input_kode.setStyleSheet(self._input_style())
        self.input_nama = QLineEdit(self)
        self.input_nama.setPlaceholderText("Nama lengkap supplier")
        self.input_nama.setStyleSheet(self._input_style())
        self.input_alamat = QLineEdit(self)
        self.input_alamat.setPlaceholderText("Alamat lengkap supplier")
        self.input_alamat.setStyleSheet(self._input_style())
        self.input_sales = QLineEdit(self)
        self.input_sales.setPlaceholderText("Nama sales/marketing")
        self.input_sales.setStyleSheet(self._input_style())
        self.input_telp = QLineEdit(self)
        self.input_telp.setPlaceholderText("Nomor telepon sales")
        self.input_telp.setStyleSheet(self._input_style())
        self.combo_cash = QComboBox(self)
        self.combo_cash.addItems(["YES", "NO"])
        self.combo_cash.setStyleSheet(self._combo_style())
        self.combo_tempo = QComboBox(self)
        self.combo_tempo.addItems(["NO", "YES"])
        self.combo_tempo.setStyleSheet(self._combo_style())
        self.input_japo = QLineEdit("0", self)
        self.input_japo.setStyleSheet(self._input_style())
        self.input_ket = QLineEdit(self)
        self.input_ket.setPlaceholderText("Keterangan tambahan...")
        self.input_ket.setStyleSheet(self._input_style())

        form_layout.addRow("🔑 Kode Supplier (KSUP):", self.input_kode)
        form_layout.addRow("🏢 Nama Supplier (NSUP):", self.input_nama)
        form_layout.addRow("📍 Alamat Supplier (ALMT):", self.input_alamat)
        form_layout.addRow("🧑 Nama Sales/Marketing:", self.input_sales)
        form_layout.addRow("📞 No. Kontak (CP):", self.input_telp)
        form_layout.addRow("💵 Pembayaran Cash:", self.combo_cash)
        form_layout.addRow("⏳ Pembayaran Tempo:", self.combo_tempo)
        form_layout.addRow("📅 Masa Tempo (JAPO - Hari):", self.input_japo)
        form_layout.addRow("📝 Keterangan (KET):", self.input_ket)
        layout.addLayout(form_layout)

        self.combo_tempo.currentTextChanged.connect(self.on_combo_tempo_changed)
        self.input_japo.setReadOnly(True)
        self.input_japo.setStyleSheet("background-color: #f1f2f6; padding: 8px; border: 1px solid #dcdde1; border-radius: 4px;")

        if self.data_edit:
            self.input_kode.setText(self.data_edit['kode_supplier'])
            self.input_kode.setReadOnly(True) 
            self.input_kode.setStyleSheet(self._input_style() + "background-color: #f1f2f6;")
            self.input_nama.setText(self.data_edit['nama_supplier'])
            self.input_alamat.setText(self.data_edit['alamat_supplier'])
            self.input_sales.setText(self.data_edit['nama_sales'])
            self.input_telp.setText(self.data_edit['telepon_sales'])
            self.combo_cash.setCurrentText(self.data_edit['pembayaran_cash'])
            self.combo_tempo.setCurrentText(self.data_edit['pembayaran_tempo'])
            self.input_japo.setText(str(self.data_edit['jatuh_tempo_hari']))
            self.input_ket.setText(self.data_edit['keterangan'])

        layout.addStretch()

        btn_layout = QHBoxLayout()
        self.btn_simpan = QPushButton("💾 Simpan", self)
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
        self.btn_batal = QPushButton("❌ Batal", self)
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
        layout.addLayout(btn_layout)

        self.btn_simpan.clicked.connect(self.proses_simpan)
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

    def on_combo_tempo_changed(self, teks):
        if teks == "YES":
            self.input_japo.setReadOnly(False)
            self.input_japo.setStyleSheet(self._input_style())
        else:
            self.input_japo.setText("0")
            self.input_japo.setReadOnly(True)
            self.input_japo.setStyleSheet("background-color: #f1f2f6; padding: 8px; border: 1px solid #dcdde1; border-radius: 4px;")

    def proses_simpan(self):
        kode, nama, alamat, sales, telp = self.input_kode.text().strip(), self.input_nama.text().strip(), self.input_alamat.text().strip(), self.input_sales.text().strip(), self.input_telp.text().strip()
        cash, tempo, japo_str, ket = self.combo_cash.currentText(), self.combo_tempo.currentText(), self.input_japo.text().strip() or "0", self.input_ket.text().strip()

        if not kode or not nama:
            QMessageBox.warning(self, "Peringatan", "⚠️ Kode dan Nama Supplier wajib diisi!")
            return
        try: japo_angka = int(japo_str)
        except ValueError: return

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        if self.data_edit:
            cursor.execute(
                "UPDATE master_supplier SET nama_supplier=?, alamat_supplier=?, nama_sales=?, telepon_sales=?, pembayaran_cash=?, pembayaran_tempo=?, jatuh_tempo_hari=?, keterangan=? WHERE id=?",
                (nama, alamat, sales, telp, cash, tempo, japo_angka, ket, self.data_edit['id'])
            )
            self.saved_id = self.data_edit['id']
        else:
            cursor.execute("SELECT id FROM master_supplier WHERE kode_supplier = ?", (kode,))
            if cursor.fetchone():
                QMessageBox.warning(self, "Peringatan", "⚠️ Kode Supplier sudah terpakai!")
                conn.close()
                return
            id_bytes = uuid.uuid4().bytes
            self.saved_id = id_bytes
            # FIX: Explicit column names + 10 placeholders (was missing keterangan)
            cursor.execute(
                "INSERT INTO master_supplier (id, kode_supplier, nama_supplier, alamat_supplier, nama_sales, telepon_sales, pembayaran_cash, pembayaran_tempo, jatuh_tempo_hari, keterangan) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (id_bytes, kode, nama, alamat, sales, telp, cash, tempo, japo_angka, ket)
            )
        conn.commit()
        conn.close()
        self.accept()

class SupplierWidget(QWidget):
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

        header_label = QLabel("🚚 Manajemen Master Data Supplier", self)
        header_label.setFont(get_font(16, bold=True))
        header_label.setStyleSheet("color: #2c3e50;")
        layout.addWidget(header_label)

        kontrol_layout = QHBoxLayout()
        self.btn_tambah = QPushButton("➕ Tambah Supplier", self)
        self.btn_edit = QPushButton("✏️ Edit Data", self)
        self.btn_hapus = QPushButton("🗑️ Hapus Data", self)
        self.btn_cetak = QPushButton("👁️ Cetak Laporan (PDF)", self)

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
        self.input_cari = QLineEdit(self)
        self.input_cari.setPlaceholderText("Nama / Kode / Sales...")
        self.input_cari.setStyleSheet("padding: 8px; border: 1px solid #dcdde1; border-radius: 4px; background: white;")
        self.btn_cari = QPushButton("🔍 Cari", self)
        self.btn_cari.setStyleSheet("padding: 8px 12px; background-color: #34495e; color: white; border-radius: 4px;")
        kontrol_layout.addWidget(QLabel("🔍 Cari:"))
        kontrol_layout.addWidget(self.input_cari)
        kontrol_layout.addWidget(self.btn_cari)
        layout.addLayout(kontrol_layout)

        self.table = QTableWidget(self)
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(["ID Hidden", "🔑 Kode", "🏢 Nama Supplier", "📍 Alamat", "🧑 Nama Sales", "📞 Kontak (CP)", "💵 Cash", "⏳ Tempo", "📅 JAPO", "📝 Keterangan"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnHidden(0, True)

        # FIXED: Scrollbar internal diaktifkan penuh, tanpa desak-desakan kolom
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

        self.table.setColumnWidth(1, 80)   # Kode
        self.table.setColumnWidth(2, 180)  # Nama Supplier
        self.table.setColumnWidth(3, 260)  # Alamat (Bebas memanjang memicu scrollbar bawah)
        self.table.setColumnWidth(4, 110)  # Nama Sales
        self.table.setColumnWidth(5, 110)  # Kontak (CP)
        self.table.setColumnWidth(6, 60)   # Cash
        self.table.setColumnWidth(7, 60)   # Tempo
        self.table.setColumnWidth(8, 75)   # JAPO
        self.table.setColumnWidth(9, 110)  # Keterangan

        layout.addWidget(self.table)

        self.btn_tambah.clicked.connect(self.aksi_tambah)
        self.btn_edit.clicked.connect(self.aksi_edit)
        self.btn_hapus.clicked.connect(self.aksi_hapus)
        self.btn_cetak.clicked.connect(self.aksi_cetak_laporan)
        self.btn_cari.clicked.connect(self.muat_data_dari_db)
        self.input_cari.returnPressed.connect(self.muat_data_dari_db)

    def muat_data_dari_db(self, target_highlight_id=None):
        self.table.setRowCount(0)
        keyword = self.input_cari.text().strip()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        if keyword:
            cursor.execute("SELECT id, kode_supplier, nama_supplier, alamat_supplier, nama_sales, telepon_sales, pembayaran_cash, pembayaran_tempo, jatuh_tempo_hari, keterangan FROM master_supplier WHERE nama_supplier LIKE ? OR kode_supplier LIKE ? OR nama_sales LIKE ?", (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))
        else:
            cursor.execute("SELECT id, kode_supplier, nama_supplier, alamat_supplier, nama_sales, telepon_sales, pembayaran_cash, pembayaran_tempo, jatuh_tempo_hari, keterangan FROM master_supplier")
        rows = cursor.fetchall()
        conn.close()

        baris_target_idx = -1
        for idx, row in enumerate(rows):
            self.table.insertRow(idx)
            item_id = QTableWidgetItem()
            item_id.setData(Qt.UserRole, row[0])

            self.table.setItem(idx, 0, item_id)
            self.table.setItem(idx, 1, QTableWidgetItem(str(row[1])))
            self.table.setItem(idx, 2, QTableWidgetItem(str(row[2])))
            self.table.setItem(idx, 3, QTableWidgetItem(str(row[3])))
            self.table.setItem(idx, 4, QTableWidgetItem(str(row[4])))
            self.table.setItem(idx, 5, QTableWidgetItem(str(row[5])))
            self.table.setItem(idx, 6, QTableWidgetItem(str(row[6])))
            self.table.setItem(idx, 7, QTableWidgetItem(str(row[7])))

            item_japo = QTableWidgetItem(f"{row[8]} Hari")
            item_japo.setTextAlignment(Qt.AlignCenter)
            if row[7] == "YES":
                item_japo.setForeground(QColor("#e67e22"))
                item_japo.setFont(get_font(10, bold=True))
            self.table.setItem(idx, 8, item_japo)
            self.table.setItem(idx, 9, QTableWidgetItem(str(row[9])))

            if target_highlight_id and row[0] == target_highlight_id: baris_target_idx = idx
        if baris_target_idx != -1: self.table.setCurrentCell(baris_target_idx, 1)

    def aksi_tambah(self):
        dialog = FormSupplierDialog(self)
        if dialog.exec_() == QDialog.Accepted: self.muat_data_dari_db(target_highlight_id=dialog.saved_id)

    def aksi_edit(self):
        b = self.table.currentRow()
        if b == -1: return
        j_raw = self.table.item(b, 8).text().replace(" Hari", "")
        data_edit = {
            'id': self.table.item(b, 0).data(Qt.UserRole),
            'kode_supplier': self.table.item(b, 1).text(),
            'nama_supplier': self.table.item(b, 2).text(),
            'alamat_supplier': self.table.item(b, 3).text(),
            'nama_sales': self.table.item(b, 4).text(),
            'telepon_sales': self.table.item(b, 5).text(),
            'pembayaran_cash': self.table.item(b, 6).text(),
            'pembayaran_tempo': self.table.item(b, 7).text(),
            'jatuh_tempo_hari': int(j_raw),
            'keterangan': self.table.item(b, 9).text()
        }
        dialog = FormSupplierDialog(self, data_edit=data_edit)
        if dialog.exec_() == QDialog.Accepted: self.muat_data_dari_db(target_highlight_id=dialog.saved_id)

    def aksi_hapus(self):
        b = self.table.currentRow()
        if b == -1: return
        id_bin = self.table.item(b, 0).data(Qt.UserRole)
        if QMessageBox.question(self, "Konfirmasi", f"❓ Hapus master data supplier '{self.table.item(b,2).text()}'?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM master_supplier WHERE id = ?", (id_bin,))
            conn.commit()
            conn.close()
            self.muat_data_dari_db()

    def pdf_print_callback(self, printer):
        self.pdf_document.print_(printer)

    def aksi_cetak_laporan(self):
        jb = self.table.rowCount()
        if jb == 0: return
        html_content = f"""
        <html><head><style>
            @page {{ size: A4 landscape; margin: 1.5cm; }}
            body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #2c3e50; }}
            h2 {{ border-bottom: 3px solid #2c3e50; padding-bottom: 8px; }}
            .meta-table {{ width: 100%; margin-bottom: 20px; }}
            .data-table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
            .data-table th {{ background-color: #2c3e50; color: white; padding: 8px; }}
            .data-table td {{ padding: 8px; border: 1px solid #dcdde1; }}
            .text-center {{ text-align: center; }}
            .highlight-orange {{ color: #e67e22; font-weight: bold; }}
        </style></head><body>
            <h2>DAFTAR REKAP MASTER DATA SUPPLIER KUD</h2>
            <table class="meta-table"><tr><td><b>🏢 Unit Usaha:</b> Gudang Logistik</td><td style="text-align:right;"><b>🖨️ Cetak:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}</td></tr></table>
            <table class="data-table"><thead><tr><th>Kode</th><th>Nama Supplier</th><th>Alamat</th><th>Sales</th><th>CP</th><th>Cash</th><th>Tempo</th><th>JAPO</th></tr></thead><tbody>
        """
        for b in range(jb):
            style_t = "class='text-center highlight-orange'" if self.table.item(b, 7).text() == "YES" else "class='text-center'"
            html_content += f"<tr><td>{self.table.item(b,1).text()}</td><td>{self.table.item(b,2).text()}</td><td>{self.table.item(b,3).text()}</td><td>{self.table.item(b,4).text()}</td><td>{self.table.item(b,5).text()}</td><td class='text-center'>{self.table.item(b,6).text()}</td><td class='text-center'>{self.table.item(b,7).text()}</td><td {style_t}>{self.table.item(b,8).text()}</td></tr>"
        html_content += "</tbody></table></body></html>"

        self.pdf_document = QTextDocument()
        self.pdf_document.setHtml(html_content)
        from PyQt5.QtPrintSupport import QPrintPreviewDialog
        printer = QPrinter(QPrinter.ScreenResolution)
        printer.setPageSize(QPrinter.A4)
        printer.setOrientation(QPrinter.Landscape)
        preview_dialog = QPrintPreviewDialog(printer, self)
        preview_dialog.resize(1100, 750)
        preview_dialog.paintRequested.connect(self.pdf_print_callback)
        preview_dialog.exec_()
