import sqlite3, uuid
from datetime import datetime, date, timedelta
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QMessageBox, QDialog, QLineEdit, QFormLayout, QComboBox,
    QDateEdit, QCheckBox, QSplitter, QFrame, QGridLayout,
    QDoubleSpinBox, QSpinBox, QApplication, QCompleter, QTextEdit
)
from PyQt5.QtCore import Qt, QDate, QStringListModel, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtGui import QTextDocument
from widgets import get_font

DB = "pos_inventory.db"


# ─────────────────────────────────────────────
# DB INIT
# ─────────────────────────────────────────────
def init_pembelian_database():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS faktur_beli (
        id BLOB PRIMARY KEY, no_faktur TEXT NOT NULL, no_faktur_supplier TEXT NOT NULL DEFAULT '',
        supplier_id BLOB, kode_supplier TEXT NOT NULL DEFAULT '', nama_supplier TEXT NOT NULL DEFAULT '',
        alamat_supplier TEXT NOT NULL DEFAULT '', tanggal_beli TEXT NOT NULL,
        tanggal_jatuh_tempo TEXT NOT NULL DEFAULT '', cara_bayar TEXT NOT NULL DEFAULT 'CASH',
        ppn_persen REAL NOT NULL DEFAULT 0.0, ppn_included TEXT NOT NULL DEFAULT 'NO',
        diskon_rp REAL NOT NULL DEFAULT 0.0, subtotal REAL NOT NULL DEFAULT 0.0,
        ppn_rp REAL NOT NULL DEFAULT 0.0, total REAL NOT NULL DEFAULT 0.0,
        total_qty_item INTEGER NOT NULL DEFAULT 0, status_faktur TEXT NOT NULL DEFAULT 'DRAFT',
        keterangan TEXT NOT NULL DEFAULT '', user_input TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS detil_beli (
        id BLOB PRIMARY KEY, faktur_id BLOB NOT NULL,
        kode_barang TEXT NOT NULL DEFAULT '', kode_barcode TEXT NOT NULL DEFAULT '',
        nama_barang TEXT NOT NULL DEFAULT '', kode_kategori TEXT NOT NULL DEFAULT '',
        nama_kategori TEXT NOT NULL DEFAULT '', satuan TEXT NOT NULL DEFAULT '',
        isi_satuan INTEGER NOT NULL DEFAULT 1,
        input_qty_satuan INTEGER NOT NULL DEFAULT 0, input_qty_ecer INTEGER NOT NULL DEFAULT 0,
        total_qty_masuk INTEGER NOT NULL DEFAULT 0,
        harga_beli_satuan REAL NOT NULL DEFAULT 0.0, harga_beli_ecer REAL NOT NULL DEFAULT 0.0,
        diskon_item_persen REAL NOT NULL DEFAULT 0.0, diskon_item_rp REAL NOT NULL DEFAULT 0.0,
        subtotal_item REAL NOT NULL DEFAULT 0.0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS approve_beli (
        id BLOB PRIMARY KEY, faktur_id BLOB NOT NULL, no_faktur TEXT NOT NULL DEFAULT '',
        action TEXT NOT NULL, user_input TEXT NOT NULL DEFAULT '',
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP, catatan TEXT NOT NULL DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS stok_kartu (
        id BLOB PRIMARY KEY, kode_barang TEXT NOT NULL DEFAULT '',
        nama_barang TEXT NOT NULL DEFAULT '', satuan TEXT NOT NULL DEFAULT '',
        isi_satuan INTEGER NOT NULL DEFAULT 1, tanggal TEXT NOT NULL,
        jenis TEXT NOT NULL, qty_masuk INTEGER NOT NULL DEFAULT 0,
        qty_keluar INTEGER NOT NULL DEFAULT 0, harga_satuan REAL NOT NULL DEFAULT 0.0,
        nilai_masuk REAL NOT NULL DEFAULT 0.0, nilai_keluar REAL NOT NULL DEFAULT 0.0,
        saldo_qty INTEGER NOT NULL DEFAULT 0, saldo_nilai REAL NOT NULL DEFAULT 0.0,
        harga_rata_rata REAL NOT NULL DEFAULT 0.0, referensi_no TEXT NOT NULL DEFAULT '',
        referensi_jenis TEXT NOT NULL DEFAULT '', user_input TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS dethut_supplier (
        id BLOB PRIMARY KEY, supplier_id BLOB NOT NULL,
        kode_supplier TEXT NOT NULL DEFAULT '', nama_supplier TEXT NOT NULL DEFAULT '',
        tanggal TEXT NOT NULL, jenis_transaksi TEXT NOT NULL,
        debet REAL NOT NULL DEFAULT 0.0, kredit REAL NOT NULL DEFAULT 0.0,
        total_hutang REAL NOT NULL DEFAULT 0.0, referensi_no TEXT NOT NULL DEFAULT '',
        keterangan TEXT NOT NULL DEFAULT ''
    )""")

    # Migrate master_barang & master_supplier
    for col, defv in [("harga_rata_rata", "REAL NOT NULL DEFAULT 0.0")]:
        c.execute("PRAGMA table_info(master_barang)")
        if col not in [r[1] for r in c.fetchall()]:
            c.execute(f"ALTER TABLE master_barang ADD COLUMN {col} {defv}")

    for col, defv in [("ttl_hutang", "REAL NOT NULL DEFAULT 0.0"),
                      ("status_hutang", "TEXT NOT NULL DEFAULT 'LUNAS'")]:
        c.execute("PRAGMA table_info(master_supplier)")
        if col not in [r[1] for r in c.fetchall()]:
            c.execute(f"ALTER TABLE master_supplier ADD COLUMN {col} {defv}")

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────
def _gen_no_faktur():
    now = datetime.now()
    prefix = f"PB-{now.strftime('%Y%m')}-"
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT no_faktur FROM faktur_beli WHERE no_faktur LIKE ? ORDER BY no_faktur DESC LIMIT 1", (f"{prefix}%",))
    row = c.fetchone()
    conn.close()
    urut = int(row[0].split('-')[-1]) + 1 if row else 1
    return f"{prefix}{urut:04d}"

def _fmt_rp(v):
    return f"Rp {v:,.0f}"

def _conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────
# DIALOG FORM FAKTUR (TAMBAH / EDIT)
# ─────────────────────────────────────────────
class FormPembelianDialog(QDialog):
    def __init__(self, parent, user_data, data_edit=None):
        super().__init__(parent)
        self.user_data = user_data
        self.data_edit = data_edit
        self.items = []       # list dict item detil
        self.saved_id = None
        self._block_calc = False
        self.resize(1000, 680)
        self.setModal(True)
        self.setWindowTitle("✏️ Edit Faktur Pembelian" if data_edit else "➕ Faktur Pembelian Baru")
        self.setStyleSheet("background:#f4f6f9;")
        self._build_ui()
        self._load_suppliers()
        if data_edit:
            self._fill_edit()
        else:
            self.inp_no_faktur.setText(_gen_no_faktur())
            self.inp_tgl.setDate(QDate.currentDate())

    # ── UI BUILD ──
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)

        # ── HEADER SECTION ──
        hdr = QFrame(); hdr.setStyleSheet("background:white; border-radius:8px; border:1px solid #e2e8f0;")
        hdr_lay = QGridLayout(hdr); hdr_lay.setContentsMargins(15, 12, 15, 12); hdr_lay.setSpacing(8)

        self.inp_no_faktur   = QLineEdit(); self.inp_no_faktur.setReadOnly(True)
        self.inp_no_faktur.setStyleSheet("background:#f1f2f6; font-weight:bold;")
        self.inp_no_supp     = QLineEdit(); self.inp_no_supp.setPlaceholderText("No. faktur dari supplier")
        self.combo_supplier  = QComboBox(); self.combo_supplier.setEditable(True)
        self.combo_supplier.setInsertPolicy(QComboBox.NoInsert)
        self.combo_supplier.currentIndexChanged.connect(self._on_supplier_changed)
        self.inp_tgl         = QDateEdit(); self.inp_tgl.setCalendarPopup(True)
        self.inp_jt          = QDateEdit(); self.inp_jt.setCalendarPopup(True)
        self.inp_jt.setEnabled(False)
        self.combo_bayar     = QComboBox(); self.combo_bayar.addItems(["CASH", "TEMPO"])
        self.combo_bayar.currentTextChanged.connect(self._on_bayar_changed)
        self.inp_diskon      = QDoubleSpinBox(); self.inp_diskon.setRange(0, 999999999); self.inp_diskon.setGroupSeparatorShown(True)
        self.inp_ppn         = QDoubleSpinBox(); self.inp_ppn.setRange(0, 100); self.inp_ppn.setSuffix(" %")
        self.chk_ppn_inc     = QCheckBox("Harga sudah termasuk PPN")
        self.inp_ket         = QLineEdit(); self.inp_ket.setPlaceholderText("Keterangan opsional")
        self.inp_diskon.valueChanged.connect(self._hitung_total)
        self.inp_ppn.valueChanged.connect(self._hitung_total)

        lbl = lambda t: QLabel(t)
        r = 0
        for lbl_t, w in [
            ("No. Faktur Kita:", self.inp_no_faktur), ("No. Faktur Supplier:", self.inp_no_supp),
            ("Supplier:", self.combo_supplier), ("Tanggal Beli:", self.inp_tgl),
            ("Cara Bayar:", self.combo_bayar), ("Jatuh Tempo:", self.inp_jt),
            ("Diskon Global (Rp):", self.inp_diskon), ("PPN %:", self.inp_ppn),
        ]:
            col = (r % 2) * 2
            row = r // 2
            hdr_lay.addWidget(QLabel(lbl_t), row, col)
            hdr_lay.addWidget(w, row, col + 1)
            r += 1
        hdr_lay.addWidget(self.chk_ppn_inc, 4, 2, 1, 2)
        hdr_lay.addWidget(QLabel("Keterangan:"), 5, 0)
        hdr_lay.addWidget(self.inp_ket, 5, 1, 1, 3)
        root.addWidget(hdr)

        # ── SEARCH BARANG ──
        src_lay = QHBoxLayout()
        self.inp_search = QLineEdit(); self.inp_search.setPlaceholderText("🔍 Ketik kode / nama / barcode → Enter untuk tambah item")
        self.inp_search.setStyleSheet("padding:8px; border:2px solid #3498db; border-radius:6px; font-size:13px;")
        self.inp_search.returnPressed.connect(self._search_and_add)
        btn_add = QPushButton("➕ Add Item"); btn_add.setStyleSheet("background:#3498db; color:white; padding:8px 15px; border-radius:6px; font-weight:bold;")
        btn_add.clicked.connect(self._search_and_add)
        src_lay.addWidget(QLabel("Cari Barang:")); src_lay.addWidget(self.inp_search, 1); src_lay.addWidget(btn_add)
        root.addLayout(src_lay)

        # ── TABEL DETAIL ITEM ──
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(12)
        self.tbl.setHorizontalHeaderLabels([
            "Kode Barang", "Nama Barang", "Satuan", "Isi",
            "Qty Satuan", "Qty Ecer", "Total Pcs",
            "Hrg/Satuan", "Hrg/Pcs", "Diskon%", "Subtotal Item", "Aksi"
        ])
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl.setColumnWidth(0, 90); self.tbl.setColumnWidth(1, 200)
        self.tbl.setColumnWidth(2, 70); self.tbl.setColumnWidth(3, 50)
        self.tbl.setColumnWidth(4, 80); self.tbl.setColumnWidth(5, 80)
        self.tbl.setColumnWidth(6, 80); self.tbl.setColumnWidth(7, 110)
        self.tbl.setColumnWidth(8, 100); self.tbl.setColumnWidth(9, 70)
        self.tbl.setColumnWidth(10, 110); self.tbl.setColumnWidth(11, 60)
        self.tbl.setStyleSheet("""
            QTableWidget{background:#fff;alternate-background-color:#f8f9fa;gridline-color:#dcdde1;font-size:12px;border:1px solid #e2e8f0;border-radius:6px;}
            QHeaderView::section{background:#2c3e50;color:white;font-weight:bold;padding:6px;border:1px solid #34495e;}
            QTableWidget::item:selected{background:#3b82f6;color:white;}
        """)
        root.addWidget(self.tbl, 1)

        # ── FOOTER TOTAL ──
        ftr = QFrame(); ftr.setStyleSheet("background:white; border-radius:8px; border:1px solid #e2e8f0;")
        ftr_lay = QHBoxLayout(ftr); ftr_lay.setContentsMargins(15, 10, 15, 10)
        self.lbl_subtotal = QLabel("Subtotal: Rp 0")
        self.lbl_diskon   = QLabel("Diskon: Rp 0")
        self.lbl_ppn      = QLabel("PPN: Rp 0")
        self.lbl_total    = QLabel("TOTAL: Rp 0"); self.lbl_total.setFont(get_font(14, bold=True))
        self.lbl_total.setStyleSheet("color:#2ecc71;")
        for w in [self.lbl_subtotal, self.lbl_diskon, self.lbl_ppn, self.lbl_total]:
            ftr_lay.addWidget(w)
        ftr_lay.addStretch()
        root.addWidget(ftr)

        # ── TOMBOL SIMPAN / BATAL ──
        btn_lay = QHBoxLayout()
        btn_lay.addStretch()
        self.btn_simpan = QPushButton("💾 Simpan Faktur")
        self.btn_simpan.setStyleSheet("background:#2ecc71;color:white;font-weight:bold;padding:10px 25px;border-radius:6px;font-size:13px;")
        self.btn_simpan.clicked.connect(self._simpan)
        btn_batal = QPushButton("❌ Batal")
        btn_batal.setStyleSheet("background:#e74c3c;color:white;padding:10px 20px;border-radius:6px;")
        btn_batal.clicked.connect(self.reject)
        btn_lay.addWidget(self.btn_simpan); btn_lay.addWidget(btn_batal)
        root.addLayout(btn_lay)

    # ── LOAD SUPPLIERS ──
    def _load_suppliers(self):
        self.combo_supplier.blockSignals(True)
        self.combo_supplier.clear()
        self._supp_list = []
        conn = _conn()
        rows = conn.execute("SELECT id, kode_supplier, nama_supplier, alamat_supplier, pembayaran_tempo, jatuh_tempo_hari FROM master_supplier ORDER BY nama_supplier").fetchall()
        conn.close()
        for r in rows:
            self.combo_supplier.addItem(f"{r['kode_supplier']} - {r['nama_supplier']}")
            self._supp_list.append(dict(r))
        self.combo_supplier.blockSignals(False)

    def _on_supplier_changed(self, idx):
        if idx < 0 or idx >= len(self._supp_list): return
        s = self._supp_list[idx]
        if s['pembayaran_tempo'] == 'YES':
            self.combo_bayar.setCurrentText('TEMPO')
            jt = date.today() + timedelta(days=s['jatuh_tempo_hari'])
            self.inp_jt.setDate(QDate(jt.year, jt.month, jt.day))

    def _on_bayar_changed(self, v):
        self.inp_jt.setEnabled(v == 'TEMPO')

    # ── SEARCH & ADD ITEM ──
    def _search_and_add(self):
        kw = self.inp_search.text().strip()
        if not kw: return
        conn = _conn()
        rows = conn.execute("""
            SELECT id, kode_barang, kode_barcode, nama_barang, kode_kategori, nama_kategori,
                   satuan, isi_satuan, harga_beli_1, harga_beli_2, harga_rata_rata, stok_isi
            FROM master_barang
            WHERE kode_barang LIKE ? OR nama_barang LIKE ? OR kode_barcode = ?
            LIMIT 20
        """, (f"%{kw}%", f"%{kw}%", kw)).fetchall()
        conn.close()

        if not rows:
            QMessageBox.information(self, "Info", "⚠️ Barang tidak ditemukan!"); return
        if len(rows) == 1:
            self._add_item_dialog(dict(rows[0]))
        else:
            dlg = _PilihBarangDialog(self, rows)
            if dlg.exec_() == QDialog.Accepted:
                self._add_item_dialog(dlg.selected)
        self.inp_search.clear(); self.inp_search.setFocus()

    def _add_item_dialog(self, barang):
        # cek duplikat
        for it in self.items:
            if it['kode_barang'] == barang['kode_barang']:
                QMessageBox.warning(self, "Duplikat", f"⚠️ {barang['nama_barang']} sudah ada di daftar!"); return
        dlg = _InputQtyHargaDialog(self, barang)
        if dlg.exec_() == QDialog.Accepted:
            self.items.append(dlg.result_item)
            self._refresh_tabel()
            self._hitung_total()

    def _refresh_tabel(self):
        self.tbl.setRowCount(0)
        for i, it in enumerate(self.items):
            self.tbl.insertRow(i)
            vals = [it['kode_barang'], it['nama_barang'], it['satuan'], str(it['isi_satuan']),
                    str(it['input_qty_satuan']), str(it['input_qty_ecer']),
                    str(it['total_qty_masuk']),
                    _fmt_rp(it['harga_beli_satuan']), _fmt_rp(it['harga_beli_ecer']),
                    f"{it['diskon_item_persen']:.1f}%", _fmt_rp(it['subtotal_item'])]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if j >= 4 else Qt.AlignLeft | Qt.AlignVCenter)
                self.tbl.setItem(i, j, item)
            btn_del = QPushButton("🗑️")
            btn_del.setStyleSheet("background:#e74c3c;color:white;border-radius:3px;padding:2px;")
            btn_del.clicked.connect(lambda _, idx=i: self._hapus_item(idx))
            self.tbl.setCellWidget(i, 11, btn_del)

    def _hapus_item(self, idx):
        self.items.pop(idx)
        self._refresh_tabel()
        self._hitung_total()

    def _hitung_total(self):
        if self._block_calc: return
        subtotal = sum(it['subtotal_item'] for it in self.items)
        diskon   = self.inp_diskon.value()
        ppn_pct  = self.inp_ppn.value()
        base     = subtotal - diskon
        if self.chk_ppn_inc.isChecked():
            ppn_rp = base - (base / (1 + ppn_pct / 100)) if ppn_pct > 0 else 0
        else:
            ppn_rp = base * (ppn_pct / 100)
        total = base + (0 if self.chk_ppn_inc.isChecked() else ppn_rp)
        self.lbl_subtotal.setText(f"Subtotal: {_fmt_rp(subtotal)}")
        self.lbl_diskon.setText(f"Diskon: {_fmt_rp(diskon)}")
        self.lbl_ppn.setText(f"PPN ({ppn_pct:.0f}%): {_fmt_rp(ppn_rp)}")
        self.lbl_total.setText(f"TOTAL: {_fmt_rp(total)}")
        self._cur_subtotal = subtotal
        self._cur_ppn_rp   = ppn_rp
        self._cur_total     = total

    # ── FILL EDIT MODE ──
    def _fill_edit(self):
        d = self.data_edit
        self.inp_no_faktur.setText(d['no_faktur'])
        self.inp_no_supp.setText(d['no_faktur_supplier'])
        self.inp_tgl.setDate(QDate.fromString(d['tanggal_beli'], "yyyy-MM-dd"))
        self.combo_bayar.setCurrentText(d['cara_bayar'])
        if d['tanggal_jatuh_tempo']:
            self.inp_jt.setDate(QDate.fromString(d['tanggal_jatuh_tempo'], "yyyy-MM-dd"))
        self._block_calc = True
        self.inp_diskon.setValue(d['diskon_rp'])
        self.inp_ppn.setValue(d['ppn_persen'])
        self.chk_ppn_inc.setChecked(d['ppn_included'] == 'YES')
        self._block_calc = False
        self.inp_ket.setText(d['keterangan'])
        # set supplier
        for i, s in enumerate(self._supp_list):
            if s['kode_supplier'] == d['kode_supplier']:
                self.combo_supplier.setCurrentIndex(i); break
        # load items
        conn = _conn()
        rows = conn.execute("SELECT * FROM detil_beli WHERE faktur_id=?", (d['id'],)).fetchall()
        conn.close()
        self.items = [dict(r) for r in rows]
        self._refresh_tabel()
        self._hitung_total()

    # ── SIMPAN ──
    def _simpan(self):
        if not self.items:
            QMessageBox.warning(self, "Peringatan", "⚠️ Belum ada item barang!"); return
        idx = self.combo_supplier.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, "Peringatan", "⚠️ Pilih supplier terlebih dahulu!"); return

        s    = self._supp_list[idx]
        tgl  = self.inp_tgl.date().toString("yyyy-MM-dd")
        jt   = self.inp_jt.date().toString("yyyy-MM-dd") if self.combo_bayar.currentText() == 'TEMPO' else ''
        now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        subtotal = getattr(self, '_cur_subtotal', 0.0)
        ppn_rp   = getattr(self, '_cur_ppn_rp', 0.0)
        total    = getattr(self, '_cur_total', 0.0)
        total_qty = sum(it['total_qty_masuk'] for it in self.items)

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        try:
            if self.data_edit:
                fid = self.data_edit['id']
                c.execute("""UPDATE faktur_beli SET no_faktur_supplier=?, kode_supplier=?, nama_supplier=?,
                    alamat_supplier=?, tanggal_beli=?, tanggal_jatuh_tempo=?, cara_bayar=?,
                    ppn_persen=?, ppn_included=?, diskon_rp=?, subtotal=?, ppn_rp=?, total=?,
                    total_qty_item=?, keterangan=? WHERE id=?""",
                    (self.inp_no_supp.text().strip(), s['kode_supplier'], s['nama_supplier'],
                     s['alamat_supplier'], tgl, jt, self.combo_bayar.currentText(),
                     self.inp_ppn.value(), 'YES' if self.chk_ppn_inc.isChecked() else 'NO',
                     self.inp_diskon.value(), subtotal, ppn_rp, total, total_qty,
                     self.inp_ket.text().strip(), fid))
                c.execute("DELETE FROM detil_beli WHERE faktur_id=?", (fid,))
                self.saved_id = fid
            else:
                fid = uuid.uuid4().bytes
                self.saved_id = fid
                c.execute("""INSERT INTO faktur_beli VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (fid, self.inp_no_faktur.text(), self.inp_no_supp.text().strip(),
                     s['id'], s['kode_supplier'], s['nama_supplier'], s['alamat_supplier'],
                     tgl, jt, self.combo_bayar.currentText(),
                     self.inp_ppn.value(), 'YES' if self.chk_ppn_inc.isChecked() else 'NO',
                     self.inp_diskon.value(), subtotal, ppn_rp, total, total_qty,
                     'DRAFT', self.inp_ket.text().strip(),
                     self.user_data.get('username', ''), now))
                c.execute("INSERT INTO approve_beli VALUES (?,?,?,?,?,?,?)",
                    (uuid.uuid4().bytes, fid, self.inp_no_faktur.text(),
                     'DRAFT_SAVED', self.user_data.get('username', ''), now, 'Faktur disimpan sebagai DRAFT'))

            # insert detil
            for it in self.items:
                c.execute("""INSERT INTO detil_beli VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (uuid.uuid4().bytes, fid,
                     it['kode_barang'], it.get('kode_barcode',''), it['nama_barang'],
                     it.get('kode_kategori',''), it.get('nama_kategori',''),
                     it['satuan'], it['isi_satuan'],
                     it['input_qty_satuan'], it['input_qty_ecer'], it['total_qty_masuk'],
                     it['harga_beli_satuan'], it['harga_beli_ecer'],
                     it['diskon_item_persen'], it['diskon_item_rp'], it['subtotal_item']))

            conn.commit()
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"❌ Gagal simpan: {e}")
        finally:
            conn.close()


# ─────────────────────────────────────────────
# DIALOG PILIH BARANG (multi hasil search)
# ─────────────────────────────────────────────
class _PilihBarangDialog(QDialog):
    def __init__(self, parent, rows):
        super().__init__(parent)
        self.selected = None
        self.setWindowTitle("Pilih Barang"); self.resize(650, 350); self.setModal(True)
        lay = QVBoxLayout(self)
        tbl = QTableWidget(len(rows), 5)
        tbl.setHorizontalHeaderLabels(["Kode", "Barcode", "Nama Barang", "Satuan", "Stok"])
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for i, r in enumerate(rows):
            r = dict(r)
            for j, v in enumerate([r['kode_barang'], r['kode_barcode'], r['nama_barang'], r['satuan'], str(r['stok_isi'])]):
                tbl.setItem(i, j, QTableWidgetItem(v))
            tbl.item(i, 0).setData(Qt.UserRole, r)
        tbl.doubleClicked.connect(lambda idx: self._pick(tbl, idx.row()))
        lay.addWidget(tbl)
        btn = QPushButton("✅ Pilih"); btn.clicked.connect(lambda: self._pick(tbl, tbl.currentRow()))
        lay.addWidget(btn)
        self._tbl = tbl

    def _pick(self, tbl, row):
        if row < 0: return
        self.selected = tbl.item(row, 0).data(Qt.UserRole)
        self.accept()


# ─────────────────────────────────────────────
# DIALOG INPUT QTY & HARGA PER ITEM
# ─────────────────────────────────────────────
class _InputQtyHargaDialog(QDialog):
    def __init__(self, parent, barang):
        super().__init__(parent)
        self.barang = barang
        self.result_item = None
        self.setWindowTitle(f"Input Qty & Harga — {barang['nama_barang']}")
        self.resize(420, 340); self.setModal(True)
        self.setStyleSheet("background:#f4f6f9;")
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        info = QLabel(f"📦 <b>{self.barang['nama_barang']}</b> | {self.barang['kode_barang']} | Stok: {self.barang['stok_isi']} Pcs")
        info.setStyleSheet("background:#3498db;color:white;padding:8px;border-radius:6px;")
        lay.addWidget(info)

        frm = QFormLayout(); frm.setSpacing(10)
        isi = self.barang['isi_satuan'] or 1

        self.sp_qty_sat  = QSpinBox(); self.sp_qty_sat.setRange(0, 999999)
        self.sp_qty_ecer = QSpinBox(); self.sp_qty_ecer.setRange(0, 999999)
        self.lbl_total   = QLabel("= 0 Pcs"); self.lbl_total.setStyleSheet("font-weight:bold; color:#2ecc71;")
        self.sp_hrg_sat  = QDoubleSpinBox(); self.sp_hrg_sat.setRange(0, 999999999); self.sp_hrg_sat.setGroupSeparatorShown(True)
        self.sp_hrg_sat.setValue(self.barang['harga_beli_1'])
        self.lbl_hrg_pcs = QLabel(_fmt_rp(self.barang['harga_beli_2'])); self.lbl_hrg_pcs.setStyleSheet("color:#e67e22; font-weight:bold;")
        self.sp_diskon   = QDoubleSpinBox(); self.sp_diskon.setRange(0, 100); self.sp_diskon.setSuffix(" %")
        self.lbl_subtotal = QLabel("Subtotal: Rp 0"); self.lbl_subtotal.setStyleSheet("font-weight:bold; color:#2c3e50; font-size:13px;")

        self.sp_qty_sat.valueChanged.connect(self._hitung)
        self.sp_qty_ecer.valueChanged.connect(self._hitung)
        self.sp_hrg_sat.valueChanged.connect(self._hitung)
        self.sp_diskon.valueChanged.connect(self._hitung)

        frm.addRow(f"Qty Satuan ({self.barang['satuan']}):", self.sp_qty_sat)
        frm.addRow(f"Qty Ecer (Pcs, isi={isi}):", self.sp_qty_ecer)
        frm.addRow("Total Masuk Stok:", self.lbl_total)
        frm.addRow(f"Harga Beli/{self.barang['satuan']}:", self.sp_hrg_sat)
        frm.addRow("Harga Beli/Pcs (auto):", self.lbl_hrg_pcs)
        frm.addRow("Diskon Item:", self.sp_diskon)
        frm.addRow("", self.lbl_subtotal)
        lay.addLayout(frm)

        bl = QHBoxLayout(); bl.addStretch()
        ok = QPushButton("✅ Tambah Item"); ok.setStyleSheet("background:#2ecc71;color:white;font-weight:bold;padding:8px 20px;border-radius:6px;")
        ok.clicked.connect(self._ok)
        batal = QPushButton("❌ Batal"); batal.setStyleSheet("background:#e74c3c;color:white;padding:8px 15px;border-radius:6px;")
        batal.clicked.connect(self.reject)
        bl.addWidget(ok); bl.addWidget(batal)
        lay.addLayout(bl)

    def _hitung(self):
        isi     = self.barang['isi_satuan'] or 1
        q_sat   = self.sp_qty_sat.value()
        q_ecer  = self.sp_qty_ecer.value()
        total   = q_sat * isi + q_ecer
        hrg_sat = self.sp_hrg_sat.value()
        hrg_pcs = hrg_sat / isi if isi > 0 else 0
        diskon  = self.sp_diskon.value()
        # subtotal berdasarkan qty satuan + qty ecer masing2
        bruto   = (q_sat * hrg_sat) + (q_ecer * hrg_pcs)
        dis_rp  = bruto * (diskon / 100)
        sub     = bruto - dis_rp
        self.lbl_total.setText(f"= {total} Pcs")
        self.lbl_hrg_pcs.setText(_fmt_rp(hrg_pcs))
        self.lbl_subtotal.setText(f"Subtotal: {_fmt_rp(sub)}")

    def _ok(self):
        isi     = self.barang['isi_satuan'] or 1
        q_sat   = self.sp_qty_sat.value()
        q_ecer  = self.sp_qty_ecer.value()
        if q_sat == 0 and q_ecer == 0:
            QMessageBox.warning(self, "Peringatan", "⚠️ Qty tidak boleh 0!"); return
        hrg_sat = self.sp_hrg_sat.value()
        hrg_pcs = hrg_sat / isi if isi > 0 else 0
        diskon  = self.sp_diskon.value()
        total   = q_sat * isi + q_ecer
        bruto   = (q_sat * hrg_sat) + (q_ecer * hrg_pcs)
        dis_rp  = bruto * (diskon / 100)
        sub     = bruto - dis_rp
        self.result_item = {
            **self.barang,
            'input_qty_satuan': q_sat, 'input_qty_ecer': q_ecer,
            'total_qty_masuk': total, 'harga_beli_satuan': hrg_sat,
            'harga_beli_ecer': hrg_pcs, 'diskon_item_persen': diskon,
            'diskon_item_rp': dis_rp, 'subtotal_item': sub
        }
        self.accept()


# ─────────────────────────────────────────────
# MAIN WIDGET
# ─────────────────────────────────────────────
class PembelianWidget(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.user_data     = getattr(parent_window, 'current_user', {})
        self.role          = self.user_data.get('role', 'KASIR')
        self._raw_faktur   = []
        self._raw_detil    = []
        self._init_ui()
        self.muat_data_dari_db()

    def _init_ui(self):
        self.setStyleSheet("background:#f4f6f9;")
        root = QVBoxLayout(self); root.setContentsMargins(15, 15, 15, 15)

        # Header
        hdr = QLabel("🛒 Manajemen Pembelian Barang — Faktur & Stok")
        hdr.setFont(get_font(15, bold=True))
        root.addWidget(hdr)

        # Toolbar
        tb = QHBoxLayout()
        self.btn_tambah  = QPushButton("➕ Tambah Faktur")
        self.btn_edit    = QPushButton("✏️ Edit")
        self.btn_hapus   = QPushButton("🗑️ Hapus")
        self.btn_posting = QPushButton("📮 POSTING")
        self.btn_cetak   = QPushButton("🖨️ Cetak PDF")
        btn_styles = {
            self.btn_tambah:  "background:#3498db;color:white;font-weight:bold;padding:8px 14px;border-radius:6px;",
            self.btn_edit:    "background:#f1c40f;color:black;font-weight:bold;padding:8px 14px;border-radius:6px;",
            self.btn_hapus:   "background:#e74c3c;color:white;font-weight:bold;padding:8px 14px;border-radius:6px;",
            self.btn_posting: "background:#8e44ad;color:white;font-weight:bold;padding:8px 18px;border-radius:6px;font-size:13px;",
            self.btn_cetak:   "background:#1abc9c;color:white;font-weight:bold;padding:8px 14px;border-radius:6px;",
        }
        for btn, st in btn_styles.items():
            btn.setStyleSheet(st); btn.setCursor(Qt.PointingHandCursor); tb.addWidget(btn)
        tb.addStretch()

        # Filter
        self.combo_filter = QComboBox()
        self.combo_filter.addItems(["Semua", "DRAFT", "POSTED"])
        self.combo_filter.currentIndexChanged.connect(self.muat_data_dari_db)
        self.inp_cari = QLineEdit(); self.inp_cari.setPlaceholderText("Cari no.faktur / supplier...")
        self.inp_cari.setStyleSheet("padding:7px;border:1px solid #dcdde1;border-radius:4px;background:white;")
        btn_cari = QPushButton("🔍"); btn_cari.setStyleSheet("padding:7px 12px;background:#34495e;color:white;border-radius:4px;")
        btn_cari.clicked.connect(self.muat_data_dari_db)
        self.inp_cari.returnPressed.connect(self.muat_data_dari_db)
        tb.addWidget(QLabel("Filter:")); tb.addWidget(self.combo_filter)
        tb.addWidget(QLabel("Cari:")); tb.addWidget(self.inp_cari); tb.addWidget(btn_cari)
        root.addLayout(tb)

        # Splitter
        splitter = QSplitter(Qt.Vertical)

        # ── Panel Atas: List Faktur ──
        top = QWidget()
        top_lay = QVBoxLayout(top); top_lay.setContentsMargins(0,0,0,0)
        top_lay.addWidget(QLabel("📋 Daftar Faktur Pembelian", styleSheet="font-weight:bold; color:#2c3e50; padding:4px;"))
        self.tbl_faktur = QTableWidget()
        self.tbl_faktur.setColumnCount(10)
        self.tbl_faktur.setHorizontalHeaderLabels([
            "ID", "No. Faktur", "No. Fakt. Supp", "Supplier",
            "Tanggal", "Jatuh Tempo", "Cara Bayar",
            "Total Item (Pcs)", "Grand Total", "Status"
        ])
        self.tbl_faktur.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_faktur.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl_faktur.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_faktur.setAlternatingRowColors(True)
        self.tbl_faktur.setColumnHidden(0, True)
        self.tbl_faktur.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl_faktur.setColumnWidth(1, 150); self.tbl_faktur.setColumnWidth(2, 140)
        self.tbl_faktur.setColumnWidth(3, 200); self.tbl_faktur.setColumnWidth(4, 100)
        self.tbl_faktur.setColumnWidth(5, 100); self.tbl_faktur.setColumnWidth(6, 90)
        self.tbl_faktur.setColumnWidth(7, 110); self.tbl_faktur.setColumnWidth(8, 130)
        self.tbl_faktur.setColumnWidth(9, 85)
        self.tbl_faktur.setStyleSheet(self._tbl_style())
        self.tbl_faktur.currentItemChanged.connect(self._on_faktur_selected)
        self.tbl_faktur.doubleClicked.connect(self._aksi_edit)
        top_lay.addWidget(self.tbl_faktur)
        splitter.addWidget(top)

        # ── Panel Bawah: Detail ──
        bot = QWidget()
        bot_lay = QVBoxLayout(bot); bot_lay.setContentsMargins(0,0,0,0)

        # info header faktur terpilih
        self.frm_info = QFrame()
        self.frm_info.setStyleSheet("background:white;border-radius:6px;border:1px solid #e2e8f0;")
        info_lay = QGridLayout(self.frm_info); info_lay.setContentsMargins(12,8,12,8)
        self.lbl_info = [QLabel("—") for _ in range(8)]
        labels = ["No. Faktur:", "Supplier:", "Tanggal:", "Cara Bayar:",
                  "No. Fakt. Supp:", "Jatuh Tempo:", "PPN:", "Keterangan:"]
        for i, (lbl, val) in enumerate(zip(labels, self.lbl_info)):
            info_lay.addWidget(QLabel(f"<b>{lbl}</b>"), i // 4, (i % 4) * 2)
            info_lay.addWidget(val, i // 4, (i % 4) * 2 + 1)
        bot_lay.addWidget(self.frm_info)

        bot_lay.addWidget(QLabel("📦 Detail Item Faktur Terpilih", styleSheet="font-weight:bold; color:#2c3e50; padding:4px;"))
        self.tbl_detil = QTableWidget()
        self.tbl_detil.setColumnCount(11)
        self.tbl_detil.setHorizontalHeaderLabels([
            "Kode", "Nama Barang", "Satuan", "Isi",
            "Qty Sat", "Qty Ecer", "Total Pcs",
            "Hrg/Satuan", "Hrg/Pcs", "Diskon%", "Subtotal"
        ])
        self.tbl_detil.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_detil.setAlternatingRowColors(True)
        self.tbl_detil.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl_detil.setColumnWidth(1, 200); self.tbl_detil.setColumnWidth(7, 120); self.tbl_detil.setColumnWidth(10, 120)
        self.tbl_detil.setStyleSheet(self._tbl_style())
        bot_lay.addWidget(self.tbl_detil, 1)

        # footer total detail
        self.lbl_footer = QLabel()
        self.lbl_footer.setStyleSheet("background:white;border-radius:6px;padding:8px 15px;border:1px solid #e2e8f0;font-size:13px;")
        bot_lay.addWidget(self.lbl_footer)
        splitter.addWidget(bot)

        splitter.setSizes([280, 380])
        root.addWidget(splitter, 1)

        # Connect buttons
        self.btn_tambah.clicked.connect(self._aksi_tambah)
        self.btn_edit.clicked.connect(self._aksi_edit)
        self.btn_hapus.clicked.connect(self._aksi_hapus)
        self.btn_posting.clicked.connect(self._aksi_posting)
        self.btn_cetak.clicked.connect(self._aksi_cetak)

        # Role filter
        if self.role == 'GUDANG':
            self.btn_posting.setEnabled(False)
            self.btn_posting.setToolTip("Hanya ADMIN/MANAGER yang dapat melakukan POSTING")
            self.btn_posting.setStyleSheet(self.btn_posting.styleSheet() + "opacity:0.5;")

    def _tbl_style(self):
        return """QTableWidget{background:#fff;alternate-background-color:#f8f9fa;gridline-color:#dcdde1;
            font-size:12px;border:1px solid #e2e8f0;border-radius:6px;}
            QHeaderView::section{background:#2c3e50;color:white;font-weight:bold;padding:7px;border:1px solid #34495e;}
            QTableWidget::item:selected{background:#3b82f6;color:white;}"""

    # ── LOAD DATA ──
    def muat_data_dari_db(self, target_id=None):
        self.tbl_faktur.setRowCount(0)
        kw = self.inp_cari.text().strip()
        f  = self.combo_filter.currentText()
        conn = _conn()
        q = "SELECT * FROM faktur_beli WHERE 1=1"
        p = []
        if f != "Semua": q += " AND status_faktur=?"; p.append(f)
        if kw: q += " AND (no_faktur LIKE ? OR nama_supplier LIKE ? OR no_faktur_supplier LIKE ?)"; p += [f"%{kw}%"]*3
        rows = conn.execute(q + " ORDER BY created_at DESC", p).fetchall()
        conn.close()
        self._raw_faktur = [dict(r) for r in rows]
        target_idx = -1
        for i, r in enumerate(self._raw_faktur):
            self.tbl_faktur.insertRow(i)
            item_id = QTableWidgetItem(); item_id.setData(Qt.UserRole, r['id'])
            self.tbl_faktur.setItem(i, 0, item_id)
            for j, v in enumerate([r['no_faktur'], r['no_faktur_supplier'], r['nama_supplier'],
                                    r['tanggal_beli'], r['tanggal_jatuh_tempo'] or '-',
                                    r['cara_bayar'], str(r['total_qty_item']), _fmt_rp(r['total'])]):
                it = QTableWidgetItem(v)
                if j in (6, 7): it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tbl_faktur.setItem(i, j+1, it)
            st = r['status_faktur']
            it_st = QTableWidgetItem(st); it_st.setTextAlignment(Qt.AlignCenter)
            it_st.setForeground(QColor("#2ecc71" if st == 'POSTED' else "#e67e22"))
            it_st.setFont(get_font(10, bold=True))
            self.tbl_faktur.setItem(i, 9, it_st)
            if target_id and r['id'] == target_id: target_idx = i
        if target_idx >= 0: self.tbl_faktur.setCurrentCell(target_idx, 1)
        self._clear_detil()

    def _on_faktur_selected(self):
        row = self.tbl_faktur.currentRow()
        if row < 0 or row >= len(self._raw_faktur):
            self._clear_detil(); return
        r = self._raw_faktur[row]
        infos = [r['no_faktur'], r['nama_supplier'], r['tanggal_beli'], r['cara_bayar'],
                 r['no_faktur_supplier'] or '-', r['tanggal_jatuh_tempo'] or '-',
                 f"{r['ppn_persen']:.0f}% ({'inc' if r['ppn_included']=='YES' else 'exc'})",
                 r['keterangan'] or '-']
        for lbl, v in zip(self.lbl_info, infos): lbl.setText(str(v))
        # load detil
        conn = _conn()
        detil = conn.execute("SELECT * FROM detil_beli WHERE faktur_id=? ORDER BY rowid", (r['id'],)).fetchall()
        conn.close()
        self._raw_detil = [dict(d) for d in detil]
        self.tbl_detil.setRowCount(0)
        for i, d in enumerate(self._raw_detil):
            self.tbl_detil.insertRow(i)
            for j, v in enumerate([d['kode_barang'], d['nama_barang'], d['satuan'], str(d['isi_satuan']),
                                    str(d['input_qty_satuan']), str(d['input_qty_ecer']),
                                    str(d['total_qty_masuk']),
                                    _fmt_rp(d['harga_beli_satuan']), _fmt_rp(d['harga_beli_ecer']),
                                    f"{d['diskon_item_persen']:.1f}%", _fmt_rp(d['subtotal_item'])]):
                it = QTableWidgetItem(v)
                if j >= 4: it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tbl_detil.setItem(i, j, it)
        self.lbl_footer.setText(
            f"  Subtotal: <b>{_fmt_rp(r['subtotal'])}</b>  |  "
            f"Diskon: <b>{_fmt_rp(r['diskon_rp'])}</b>  |  "
            f"PPN: <b>{_fmt_rp(r['ppn_rp'])}</b>  |  "
            f"<span style='color:#2ecc71; font-size:14px;'>TOTAL: <b>{_fmt_rp(r['total'])}</b></span>"
        )
        self.lbl_footer.setTextFormat(Qt.RichText)

    def _clear_detil(self):
        for l in self.lbl_info: l.setText("—")
        self.tbl_detil.setRowCount(0)
        self.lbl_footer.setText("Pilih faktur di atas untuk melihat detail item.")

    def _get_selected(self):
        row = self.tbl_faktur.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Peringatan", "⚠️ Pilih faktur terlebih dahulu!")
            return None
        return self._raw_faktur[row]

    # ── AKSI ──
    def _aksi_tambah(self):
        dlg = FormPembelianDialog(self, self.user_data)
        if dlg.exec_() == QDialog.Accepted:
            self.muat_data_dari_db(target_id=dlg.saved_id)

    def _aksi_edit(self):
        r = self._get_selected()
        if not r: return
        if r['status_faktur'] == 'POSTED':
            QMessageBox.warning(self, "Ditolak", "❌ Faktur POSTED tidak dapat diedit!"); return
        dlg = FormPembelianDialog(self, self.user_data, data_edit=r)
        if dlg.exec_() == QDialog.Accepted:
            self.muat_data_dari_db(target_id=dlg.saved_id)

    def _aksi_hapus(self):
        r = self._get_selected()
        if not r: return
        if r['status_faktur'] == 'POSTED':
            QMessageBox.warning(self, "Ditolak", "❌ Faktur POSTED tidak dapat dihapus!"); return
        if QMessageBox.question(self, "Konfirmasi", f"❓ Hapus faktur <b>{r['no_faktur']}</b>?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes: return
        conn = sqlite3.connect(DB)
        try:
            conn.execute("DELETE FROM detil_beli WHERE faktur_id=?", (r['id'],))
            conn.execute("DELETE FROM approve_beli WHERE faktur_id=?", (r['id'],))
            conn.execute("DELETE FROM faktur_beli WHERE id=?", (r['id'],))
            conn.commit()
        except Exception as e:
            conn.rollback(); QMessageBox.critical(self, "Error", str(e))
        finally:
            conn.close()
        self.muat_data_dari_db()

    def _aksi_posting(self):
        r = self._get_selected()
        if not r: return
        if r['status_faktur'] == 'POSTED':
            QMessageBox.warning(self, "Info", "ℹ️ Faktur sudah POSTED!"); return
        if r['total_qty_item'] == 0:
            QMessageBox.warning(self, "Peringatan", "⚠️ Faktur tidak memiliki item!"); return

        rep = QMessageBox.question(self, "Konfirmasi POSTING",
            f"⚠️ POSTING faktur <b>{r['no_faktur']}</b>?\n\n"
            "Tindakan ini akan:\n"
            "• Update stok & harga barang di master\n"
            "• Catat kartu stok (moving average)\n"
            "• Faktur tidak dapat diedit setelah POSTED\n\n"
            "Yakin lanjutkan?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if rep != QMessageBox.Yes: return

        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        try:
            detil = c.execute("SELECT * FROM detil_beli WHERE faktur_id=?", (r['id'],)).fetchall()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user = self.user_data.get('username', 'SYSTEM')

            for d in detil:
                d = dict(d)
                # ambil data master barang sekarang
                mb = c.execute("""SELECT stok_isi, harga_rata_rata, harga_beli_1, harga_beli_2,
                                  satuan, isi_satuan FROM master_barang WHERE kode_barang=?""",
                               (d['kode_barang'],)).fetchone()
                if not mb: continue
                mb = dict(mb)

                stok_lama   = mb['stok_isi']
                avg_lama    = mb['harga_rata_rata'] if mb['harga_rata_rata'] > 0 else mb['harga_beli_2']
                qty_masuk   = d['total_qty_masuk']
                hrg_pcs_baru = d['harga_beli_ecer']

                # Moving Average
                stok_baru = stok_lama + qty_masuk
                if stok_baru > 0:
                    avg_baru = ((stok_lama * avg_lama) + (qty_masuk * hrg_pcs_baru)) / stok_baru
                else:
                    avg_baru = hrg_pcs_baru
                nilai_persediaan = stok_baru * avg_baru

                # Saldo kartu stok sebelumnya
                prev = c.execute("""SELECT saldo_qty, saldo_nilai FROM stok_kartu
                                    WHERE kode_barang=? ORDER BY created_at DESC LIMIT 1""",
                                 (d['kode_barang'],)).fetchone()
                saldo_qty_prev   = prev['saldo_qty'] if prev else stok_lama
                saldo_nilai_prev = prev['saldo_nilai'] if prev else (stok_lama * avg_lama)

                # Insert stok_kartu
                c.execute("""INSERT INTO stok_kartu VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (uuid.uuid4().bytes, d['kode_barang'], d['nama_barang'], d['satuan'], d['isi_satuan'],
                     r['tanggal_beli'], 'MASUK', qty_masuk, 0,
                     hrg_pcs_baru, qty_masuk * hrg_pcs_baru, 0,
                     saldo_qty_prev + qty_masuk,
                     saldo_nilai_prev + (qty_masuk * hrg_pcs_baru),
                     avg_baru, r['no_faktur'], 'PEMBELIAN', user, now))

                # Update master_barang (semua field relevan)
                c.execute("""UPDATE master_barang SET
                    stok_isi=?, harga_rata_rata=?, nilai_persediaan=?,
                    harga_beli_1=?, harga_beli_2=?,
                    satuan=?, isi_satuan=?
                    WHERE kode_barang=?""",
                    (stok_baru, avg_baru, nilai_persediaan,
                     d['harga_beli_satuan'], d['harga_beli_ecer'],
                     d['satuan'], d['isi_satuan'], d['kode_barang']))

            # Update status faktur
            c.execute("UPDATE faktur_beli SET status_faktur='POSTED' WHERE id=?", (r['id'],))

            # Catat hutang supplier jika TEMPO
            if r['cara_bayar'] == 'TEMPO':
                sup = c.execute("SELECT ttl_hutang FROM master_supplier WHERE kode_supplier=?",
                                (r['kode_supplier'],)).fetchone()
                hutang_lama = sup['ttl_hutang'] if sup else 0.0
                hutang_baru = hutang_lama + r['total']
                c.execute("UPDATE master_supplier SET ttl_hutang=?, status_hutang='BELUM LUNAS' WHERE kode_supplier=?",
                          (hutang_baru, r['kode_supplier']))
                c.execute("""INSERT INTO dethut_supplier VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (uuid.uuid4().bytes, r['supplier_id'], r['kode_supplier'], r['nama_supplier'],
                     r['tanggal_beli'], f"Pembelian - {r['no_faktur']}",
                     r['total'], 0.0, hutang_baru, r['no_faktur'], r['keterangan']))

            # Approve log
            c.execute("INSERT INTO approve_beli VALUES (?,?,?,?,?,?,?)",
                (uuid.uuid4().bytes, r['id'], r['no_faktur'],
                 'POSTED', user, now, f"Faktur di-POSTING oleh {user}"))

            conn.commit()
            QMessageBox.information(self, "Sukses", f"✅ Faktur {r['no_faktur']} berhasil di-POSTING!\nStok & data barang telah diperbarui.")
            self.muat_data_dari_db(target_id=r['id'])

        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error POSTING", f"❌ Gagal POSTING:\n{e}")
        finally:
            conn.close()

    # ── CETAK PDF ──
    def _aksi_cetak(self):
        r = self._get_selected()
        if not r: return
        conn = _conn()
        detil = conn.execute("SELECT * FROM detil_beli WHERE faktur_id=?", (r['id'],)).fetchall()
        conn.close()
        rows_html = ""
        for d in detil:
            rows_html += f"""<tr>
                <td>{d['kode_barang']}</td><td>{d['nama_barang']}</td>
                <td class='c'>{d['satuan']}</td><td class='c'>{d['isi_satuan']}</td>
                <td class='c'>{d['input_qty_satuan']} sat + {d['input_qty_ecer']} pcs = {d['total_qty_masuk']} pcs</td>
                <td class='r'>{_fmt_rp(d['harga_beli_satuan'])}</td>
                <td class='r'>{_fmt_rp(d['harga_beli_ecer'])}</td>
                <td class='c'>{d['diskon_item_persen']:.1f}%</td>
                <td class='r'>{_fmt_rp(d['subtotal_item'])}</td></tr>"""
        html = f"""<html><head><style>
            @page{{size:A4 landscape;margin:1.5cm}}
            body{{font-family:Arial,sans-serif;color:#2c3e50;font-size:11px}}
            h2{{border-bottom:3px solid #2c3e50;padding-bottom:6px}}
            .meta{{width:100%;margin-bottom:15px}}
            table{{width:100%;border-collapse:collapse}}
            th{{background:#2c3e50;color:white;padding:7px}}
            td{{padding:7px;border:1px solid #dcdde1}}
            .r{{text-align:right}}.c{{text-align:center}}
            .total-row{{background:#f8f9fa;font-weight:bold}}
        </style></head><body>
        <h2>FAKTUR PEMBELIAN — {r['no_faktur']}</h2>
        <table class="meta"><tr>
            <td><b>Supplier:</b> {r['nama_supplier']}</td>
            <td><b>No. Fakt. Supp:</b> {r['no_faktur_supplier'] or '-'}</td>
            <td><b>Tanggal:</b> {r['tanggal_beli']}</td>
            <td><b>Status:</b> {r['status_faktur']}</td>
        </tr><tr>
            <td><b>Cara Bayar:</b> {r['cara_bayar']}</td>
            <td><b>Jatuh Tempo:</b> {r['tanggal_jatuh_tempo'] or '-'}</td>
            <td><b>Cetak:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}</td>
            <td></td>
        </tr></table>
        <table><thead><tr>
            <th>Kode</th><th>Nama Barang</th><th>Satuan</th><th>Isi</th>
            <th>Qty</th><th>Hrg/Sat</th><th>Hrg/Pcs</th><th>Diskon%</th><th>Subtotal</th>
        </tr></thead><tbody>{rows_html}</tbody>
        <tfoot><tr class="total-row">
            <td colspan="8" class="r">Subtotal</td><td class="r">{_fmt_rp(r['subtotal'])}</td></tr>
        <tr class="total-row"><td colspan="8" class="r">Diskon</td><td class="r">({_fmt_rp(r['diskon_rp'])})</td></tr>
        <tr class="total-row"><td colspan="8" class="r">PPN {r['ppn_persen']:.0f}%</td><td class="r">{_fmt_rp(r['ppn_rp'])}</td></tr>
        <tr style="background:#2c3e50;color:white;"><td colspan="8" class="r"><b>GRAND TOTAL</b></td>
            <td class="r"><b>{_fmt_rp(r['total'])}</b></td></tr>
        </tfoot></table></body></html>"""

        self._pdf_doc = QTextDocument()
        self._pdf_doc.setHtml(html)
        from PyQt5.QtPrintSupport import QPrintPreviewDialog
        printer = QPrinter(QPrinter.ScreenResolution)
        printer.setPageSize(QPrinter.A4); printer.setOrientation(QPrinter.Landscape)
        prev = QPrintPreviewDialog(printer, self); prev.resize(1100, 750)
        prev.paintRequested.connect(lambda p: self._pdf_doc.print_(p))
        prev.exec_()