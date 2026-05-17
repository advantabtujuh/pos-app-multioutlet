import sys
import sqlite3
import uuid
import os
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
                             QAbstractItemView, QHeaderView, QMessageBox, QDialog, 
                             QFormLayout, QDateEdit, QFileDialog, QMainWindow, QApplication)
from PyQt5.QtCore import Qt, QDate, QSizeF
from PyQt5.QtGui import QTextDocument, QColor
from widgets import get_font
from PyQt5.QtPrintSupport import QPrinter

DB_NAME = "pos_inventory.db"

def init_customer_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS master_customer (id BLOB PRIMARY KEY)")
    cursor.execute("PRAGMA table_info(master_customer)")
    kolom_master = [info[1] for info in cursor.fetchall()]
    
    if "kode_customer" not in kolom_master:
        cursor.execute("ALTER TABLE master_customer ADD COLUMN kode_customer TEXT NOT NULL DEFAULT ''")
    if "nama_customer" not in kolom_master:
        cursor.execute("ALTER TABLE master_customer ADD COLUMN nama_customer TEXT NOT NULL DEFAULT ''")
    if "alamat_customer" not in kolom_master:
        cursor.execute("ALTER TABLE master_customer ADD COLUMN alamat_customer TEXT NOT NULL DEFAULT ''")
    if "telepon_customer" not in kolom_master:
        cursor.execute("ALTER TABLE master_customer ADD COLUMN telepon_customer TEXT NOT NULL DEFAULT ''")
    if "ttl_hutang" not in kolom_master:
        cursor.execute("ALTER TABLE master_customer ADD COLUMN ttl_hutang REAL NOT NULL DEFAULT 0.0")
    if "status_hutang" not in kolom_master:
        cursor.execute("ALTER TABLE master_customer ADD COLUMN status_hutang TEXT NOT NULL DEFAULT 'LUNAS'")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dethut_customer (
            id BLOB PRIMARY KEY, customer_id BLOB NOT NULL, tanggal TEXT NOT NULL, jenis_transaksi TEXT NOT NULL,
            debet REAL NOT NULL DEFAULT 0.0, kredit REAL NOT NULL DEFAULT 0.0, total_hutang REAL NOT NULL DEFAULT 0.0,
            FOREIGN KEY(customer_id) REFERENCES master_customer(id)
        )
    """)
    conn.commit()
    conn.close()

class FormCustomerDialog(QDialog):
    def __init__(self, parent=None, data_edit=None):
        super().__init__(parent)
        self.data_edit = data_edit 
        self.init_ui()
        
    def init_ui(self):
        self.setFont(get_font(10, bold=False))
        self.setWindowTitle("✏️ Edit Data Customer" if self.data_edit else "➕ Tambah Customer Baru")
        self.resize(400, 280)
        self.setModal(True)
        
        self.setStyleSheet("background-color: #f4f6f9;")
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.input_kode = QLineEdit(self)
        self.input_nama = QLineEdit(self)
        self.input_alamat = QLineEdit(self)
        self.input_telp = QLineEdit(self)
        self.input_hutang_awal = QLineEdit(self)
        
        form_layout.addRow("🔑 Kode Customer:", self.input_kode)
        form_layout.addRow("👤 Nama Customer:", self.input_nama)
        form_layout.addRow("📍 Alamat:", self.input_alamat)
        form_layout.addRow("📞 No. Telepon:", self.input_telp)
        if not self.data_edit:
            form_layout.addRow("💰 Hutang Awal (Rp):", self.input_hutang_awal)
        layout.addLayout(form_layout)
        
        if self.data_edit:
            self.input_kode.setText(self.data_edit['kode_customer'])
            self.input_kode.setReadOnly(True) 
            self.input_nama.setText(self.data_edit['nama_customer'])
            self.input_alamat.setText(self.data_edit['alamat_customer'])
            self.input_telp.setText(self.data_edit['telepon_customer'])
            
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
        kode, nama, alamat, telp = self.input_kode.text().strip(), self.input_nama.text().strip(), self.input_alamat.text().strip(), self.input_telp.text().strip()
        if not kode or not nama:
            QMessageBox.warning(self, "Peringatan", "⚠️ Kode dan Nama Customer wajib diisi!")
            return
            
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        if self.data_edit:
            id_bin = self.data_edit['id']
            cursor.execute("UPDATE master_customer SET nama_customer=?, alamat_customer=?, telepon_customer=? WHERE id=?", (nama, alamat, telp, id_bin))
            self.saved_id = id_bin
        else:
            cursor.execute("SELECT id FROM master_customer WHERE kode_customer = ?", (kode,))
            if cursor.fetchone():
                QMessageBox.warning(self, "Peringatan", "⚠️ Kode Customer sudah terpakai!")
                conn.close()
                return
            hutang_str = self.input_hutang_awal.text().strip() or "0"
            try: hutang_awal = float(hutang_str)
            except ValueError:
                QMessageBox.warning(self, "Peringatan", "⚠️ Nilai hutang awal harus berupa angka!")
                conn.close()
                return
            id_bytes = uuid.uuid4().bytes
            self.saved_id = id_bytes
            status_awal = "BELUM LUNAS" if hutang_awal > 0 else "LUNAS"
            cursor.execute("INSERT INTO master_customer VALUES (?,?,?,?,?,?,?)", (id_bytes, kode, nama, alamat, telp, hutang_awal, status_awal))
            if hutang_awal > 0:
                cursor.execute("INSERT INTO dethut_customer VALUES (?,?,?,?,?,?,?)", (uuid.uuid4().bytes, id_bytes, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Hutang Awal", hutang_awal, 0.0, hutang_awal))
                
        conn.commit()
        conn.close()
        self.accept()

class DetailHutangDialog(QDialog):
    def __init__(self, parent, customer_id, nama_cust, kode_cust):
        super().__init__(parent)
        self.customer_id, self.nama_cust, self.kode_cust = customer_id, nama_cust, kode_cust
        self.init_ui()
        self.filter_data()
        
    def init_ui(self):
        self.setWindowTitle(f"📜 Riwayat Kartu Hutang - {self.nama_cust}")
        self.resize(750, 450)
        self.setFont(get_font(10, bold=False))
        self.setStyleSheet("background-color: #f4f6f9;")
        layout = QVBoxLayout(self)
        
        filter_layout = QHBoxLayout()
        self.date_mulai = QDateEdit(self)
        self.date_mulai.setCalendarPopup(True)
        self.date_mulai.setDate(QDate.currentDate().addMonths(-1)) 
        self.date_selesai = QDateEdit(self)
        self.date_selesai.setCalendarPopup(True)
        self.date_selesai.setDate(QDate.currentDate())
        
        self.btn_filter = QPushButton("🔍 Filter", self)
        self.btn_preview = QPushButton("👁️ Preview PDF", self)
        self.btn_filter.setStyleSheet("background-color: #34495e; color: white;")
        self.btn_preview.setStyleSheet("background-color: #9b59b6; color: white;")
        
        filter_layout.addWidget(QLabel("📅 Periode:"))
        filter_layout.addWidget(self.date_mulai)
        filter_layout.addWidget(QLabel("s/d"))
        filter_layout.addWidget(self.date_selesai)
        filter_layout.addWidget(self.btn_filter)
        filter_layout.addStretch()
        filter_layout.addWidget(self.btn_preview)
        layout.addLayout(filter_layout)
        
        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["📅 Tanggal", "📝 Keterangan Transaksi", "📥 Debet (+)", "📤 Kredit (-)", "⚖️ Sisa Hutang"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        self.btn_filter.clicked.connect(self.filter_data)
        self.btn_preview.clicked.connect(self.proses_pdf_pyqt)
        
    def filter_data(self):
        tgl_m = self.date_mulai.date().toString("yyyy-MM-dd") + " 00:00:00"
        tgl_s = self.date_selesai.date().toString("yyyy-MM-dd") + " 23:59:59"
        self.table.setRowCount(0)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT tanggal, jenis_transaksi, debet, kredit, total_hutang FROM dethut_customer WHERE customer_id=? AND tanggal BETWEEN ? AND ? ORDER BY tanggal ASC", (self.customer_id, tgl_m, tgl_s))
        self.raw_pdf_data = cursor.fetchall() 
        conn.close()
        
        for idx, (tgl, jenis, deb, kre, ttl) in enumerate(self.raw_pdf_data):
            self.table.insertRow(idx)
            self.table.setItem(idx, 0, QTableWidgetItem(str(tgl)))
            self.table.setItem(idx, 1, QTableWidgetItem(str(jenis)))
            self.table.setItem(idx, 2, QTableWidgetItem(f"Rp {deb:,.0f}"))
            self.table.setItem(idx, 3, QTableWidgetItem(f"Rp {kre:,.0f}"))
            self.table.setItem(idx, 4, QTableWidgetItem(f"Rp {ttl:,.0f}"))

    def pdf_print_callback(self, printer):
        self.pdf_document.print_(printer)

    def proses_pdf_pyqt(self):
        if not self.raw_pdf_data: return
        html_content = f"""
        <html><head><style>
            @page {{ size: A4; margin: 1.5cm; }}
            body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #2c3e50; }}
            h2 {{ border-bottom: 3px solid #2c3e50; padding-bottom: 8px; }}
            .meta-table {{ width: 100%; margin-bottom: 25px; }}
            .data-table {{ width: 100%; border-collapse: collapse; }}
            .data-table th {{ background-color: #2c3e50; color: white; padding: 10px; }}
            .data-table td {{ padding: 10px; border-bottom: 1px solid #dcdde1; }}
            .text-right {{ text-align: right; }}
        </style></head><body>
            <h2>KARTU RIWAYAT PIUTANG/HUTANG CUSTOMER</h2>
            <table class="meta-table">
                <tr><td><b>🔑 Kode Customer :</b> {self.kode_cust}</td><td style="text-align:right;"><b>📅 Periode :</b> {self.date_mulai.date().toString('dd/MM/yyyy')} s/d {self.date_selesai.date().toString('dd/MM/yyyy')}</td></tr>
                <tr><td><b>👤 Nama Customer :</b> {self.nama_cust}</td><td style="text-align:right;"><b>🖨️ Tanggal Cetak :</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}</td></tr>
            </table>
            <table class="data-table"><thead><tr><th>Tanggal</th><th>Keterangan</th><th class="text-right">Debet (+)</th><th class="text-right">Kredit (-)</th><th class="text-right">Sisa Hutang</th></tr></thead><tbody>
        """
        for tgl, jenis, deb, kre, ttl in self.raw_pdf_data:
            html_content += f"<tr><td>{tgl}</td><td>{jenis}</td><td class='text-right'>Rp {deb:,.0f}</td><td class='text-right'>Rp {kre:,.0f}</td><td class='text-right'>Rp {ttl:,.0f}</td></tr>"
        html_content += "</tbody></table></body></html>"

        self.pdf_document = QTextDocument()
        self.pdf_document.setHtml(html_content)
        from PyQt5.QtPrintSupport import QPrintPreviewDialog
        printer = QPrinter(QPrinter.ScreenResolution)
        printer.setPageSize(QPrinter.A4)
        preview_dialog = QPrintPreviewDialog(printer, self)
        preview_dialog.resize(1000, 750)
        preview_dialog.paintRequested.connect(self.pdf_print_callback)
        preview_dialog.exec_()

class CustomerWidget(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.init_ui()
        self.muat_data_dari_db()
        
    def init_ui(self):
        self.setStyleSheet("background-color: #f4f6f9;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        header_label = QLabel("👥 Manajemen Master Data Customer", self)
        header_label.setFont(get_font(16, bold=True))
        layout.addWidget(header_label)
        
        kontrol_layout = QHBoxLayout()
        self.btn_tambah = QPushButton("➕ Tambah Customer", self)
        self.btn_edit = QPushButton("✏️ Edit Data", self)
        self.btn_hapus = QPushButton("🗑️ Hapus Data", self)
        self.btn_detail = QPushButton("📜 Detail Kartu Hutang", self)
        
        tombol_styles = {
            self.btn_tambah: "background-color: #3498db; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_edit: "background-color: #f1c40f; color: black; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_hapus: "background-color: #e74c3c; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;",
            self.btn_detail: "background-color: #9b59b6; color: white; font-weight: bold; padding: 8px 15px; border-radius: 6px;"
        }
        for btn, style in tombol_styles.items():
            btn.setStyleSheet(style)
            kontrol_layout.addWidget(btn)
            
        kontrol_layout.addStretch()
        self.input_cari = QLineEdit(self)
        self.input_cari.setPlaceholderText("Ketik Nama / Kode...")
        self.btn_cari = QPushButton("Cari", self)
        kontrol_layout.addWidget(QLabel("🔍 Cari:"))
        kontrol_layout.addWidget(self.input_cari)
        kontrol_layout.addWidget(self.btn_cari)
        layout.addLayout(kontrol_layout)
        
        self.table = QTableWidget(self)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID Hidden", "🔑 Kode", "👤 Nama Customer", "📍 Alamat", "📞 No. Telepon", "💰 Total Hutang", "📌 Status"])
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
        
        self.table.setColumnWidth(1, 90)   # Kode
        self.table.setColumnWidth(2, 220)  # Nama Customer
        self.table.setColumnWidth(3, 260)  # Alamat (Bebas memanjang memicu scrollbar bawah)
        self.table.setColumnWidth(4, 110)  # No. Telepon
        self.table.setColumnWidth(5, 110)  # Total Hutang
        self.table.setColumnWidth(6, 100)  # Status
        
        layout.addWidget(self.table)
        
        self.btn_tambah.clicked.connect(self.aksi_tambah)
        self.btn_edit.clicked.connect(self.aksi_edit)
        self.btn_hapus.clicked.connect(self.aksi_hapus)
        self.btn_detail.clicked.connect(self.aksi_detail)
        self.btn_cari.clicked.connect(self.muat_data_dari_db)
        self.input_cari.returnPressed.connect(self.muat_data_dari_db)
        
    def muat_data_dari_db(self, target_highlight_id=None):
        self.table.setRowCount(0)
        keyword = self.input_cari.text().strip()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        if keyword:
            cursor.execute("SELECT id, kode_customer, nama_customer, alamat_customer, telepon_customer, ttl_hutang, status_hutang FROM master_customer WHERE nama_customer LIKE ? OR kode_customer LIKE ?", (f"%{keyword}%", f"%{keyword}%"))
        else:
            cursor.execute("SELECT id, kode_customer, nama_customer, alamat_customer, telepon_customer, ttl_hutang, status_hutang FROM master_customer")
        rows = cursor.fetchall()
        conn.close()
        
        baris_target_idx = -1
        for idx, (id_bin, kode, nama, alamat, telp, hutang, status) in enumerate(rows):
            self.table.insertRow(idx)
            item_id = QTableWidgetItem()
            item_id.setData(Qt.UserRole, id_bin)
            
            item_kode = QTableWidgetItem(str(kode))
            item_nama = QTableWidgetItem(str(nama))
            item_alamat = QTableWidgetItem(str(alamat))
            item_telp = QTableWidgetItem(str(telp))
            
            item_hutang = QTableWidgetItem(f"Rp {hutang:,.0f}")
            item_hutang.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            status_sebenarnya = "BELUM LUNAS" if hutang > 0 else "LUNAS"
            item_status = QTableWidgetItem(status_sebenarnya)
            item_status.setTextAlignment(Qt.AlignCenter)
            item_status.setForeground(QColor("#e74c3c" if hutang > 0 else "#2ecc71"))
            item_status.setFont(get_font(10, bold=True))
            
            self.table.setItem(idx, 0, item_id)
            self.table.setItem(idx, 1, item_kode)
            self.table.setItem(idx, 2, item_nama)
            self.table.setItem(idx, 3, item_alamat)
            self.table.setItem(idx, 4, item_telp)
            self.table.setItem(idx, 5, item_hutang)
            self.table.setItem(idx, 6, item_status)
            
            if target_highlight_id and id_bin == target_highlight_id: baris_target_idx = idx

        if baris_target_idx != -1:
            self.table.setCurrentCell(baris_target_idx, 1)

    def aksi_tambah(self):
        dialog = FormCustomerDialog(self)
        if dialog.exec_() == QDialog.Accepted: self.muat_data_dari_db(target_highlight_id=dialog.saved_id)

    def aksi_edit(self):
        b = self.table.currentRow()
        if b == -1: return
        id_bin = self.table.item(b, 0).data(Qt.UserRole)
        data_edit = {'id': id_bin, 'kode_customer': self.table.item(b, 1).text(), 'nama_customer': self.table.item(b, 2).text(), 'alamat_customer': self.table.item(b, 3).text(), 'telepon_customer': self.table.item(b, 4).text()}
        dialog = FormCustomerDialog(self, data_edit=data_edit)
        if dialog.exec_() == QDialog.Accepted: self.muat_data_dari_db(target_highlight_id=dialog.saved_id)

    def aksi_hapus(self):
        b = self.table.currentRow()
        if b == -1: return
        if self.table.item(b, 6).text() == "BELUM LUNAS":
            QMessageBox.critical(self, "Aksi Ditolak!", "⚠️ Customer ini statusnya masih BELUM LUNAS! Selesaikan piutang dulu.")
            return
        id_bin = self.table.item(b, 0).data(Qt.UserRole)
        if QMessageBox.question(self, "Konfirmasi", f"❓ Hapus master data customer '{self.table.item(b,2).text()}'?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM dethut_customer WHERE customer_id = ?", (id_bin,))
            cursor.execute("DELETE FROM master_customer WHERE id = ?", (id_bin,))
            conn.commit()
            conn.close()
            self.muat_data_dari_db()

    def aksi_detail(self):
        b = self.table.currentRow()
        if b == -1: return
        dialog = DetailHutangDialog(self, self.table.item(b, 0).data(Qt.UserRole), self.table.item(b, 2).text(), self.table.item(b, 1).text())
        dialog.exec_()