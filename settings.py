import sqlite3
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFormLayout, QComboBox, QSpinBox, QTabWidget,
    QMessageBox, QFrame, QDialog, QTextEdit, QDoubleSpinBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from db_manager import db
from config_manager import config
from widgets import get_font

DB = "pos_inventory.db"


# ─────────────────────────────────────────────
# FIRST TIME SETUP WIZARD (Mode Pusat/Outlet)
# ─────────────────────────────────────────────
class SetupWizardDialog(QDialog):
    """Wizard awal: wajib diisi jika app_mode belum dikonfigurasi."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔧 Setup Awal Aplikasi")
        self.setModal(True); self.resize(480, 400)
        self.setStyleSheet("background:#f4f6f9;")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(30, 25, 30, 25); lay.setSpacing(15)

        hdr = QLabel("🚀 Selamat Datang — Setup Awal")
        hdr.setFont(get_font(16, bold=True)); hdr.setStyleSheet("color:#2c3e50;")
        hdr.setAlignment(Qt.AlignCenter); lay.addWidget(hdr)

        sub = QLabel("Lengkapi informasi dasar sebelum menggunakan aplikasi.\nData ini dapat diubah kapan saja melalui menu Settings.")
        sub.setFont(get_font(9)); sub.setStyleSheet("color:#64748b;")
        sub.setAlignment(Qt.AlignCenter); sub.setWordWrap(True); lay.addWidget(sub)

        line = QFrame(); line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background:#e2e8f0;"); line.setFixedHeight(1); lay.addWidget(line)

        frm = QFormLayout(); frm.setSpacing(12)
        self.inp_nama   = QLineEdit(); self.inp_nama.setPlaceholderText("Nama toko / koperasi")
        self.inp_alamat = QLineEdit(); self.inp_alamat.setPlaceholderText("Alamat lengkap")
        self.inp_telp   = QLineEdit(); self.inp_telp.setPlaceholderText("No. telepon")
        self.combo_mode = QComboBox(); self.combo_mode.addItems(["PUSAT", "OUTLET"])
        self.combo_mode.currentTextChanged.connect(self._on_mode)
        self.combo_outlet = QComboBox(); self.combo_outlet.setEnabled(False)
        self._load_outlets()

        for lbl, w in [("🏢 Nama Toko:", self.inp_nama), ("📍 Alamat:", self.inp_alamat),
                       ("📞 Telepon:", self.inp_telp), ("🌐 Mode App:", self.combo_mode),
                       ("🏪 Outlet (jika OUTLET):", self.combo_outlet)]:
            frm.addRow(lbl, w)
        lay.addLayout(frm); lay.addStretch()

        btn = QPushButton("💾 Simpan & Mulai")
        btn.setStyleSheet("background:#2ecc71;color:white;font-weight:bold;padding:12px;border-radius:6px;font-size:13px;")
        btn.clicked.connect(self._simpan); lay.addWidget(btn)

    def _load_outlets(self):
        self.combo_outlet.clear(); self._outlet_list = []
        rows = db.execute_local("SELECT id, kode_outlet, nama_outlet FROM master_outlet WHERE is_active=1", fetch_all=True)
        if rows:
            for r in rows:
                self.combo_outlet.addItem(f"{r['kode_outlet']} - {r['nama_outlet']}")
                self._outlet_list.append(dict(r))

    def _on_mode(self, v):
        self.combo_outlet.setEnabled(v == 'OUTLET')

    def _simpan(self):
        nama = self.inp_nama.text().strip()
        if not nama:
            QMessageBox.warning(self, "Peringatan", "⚠️ Nama toko wajib diisi!"); return
        mode = self.combo_mode.currentText()
        if mode == 'OUTLET' and not self._outlet_list:
            QMessageBox.warning(self, "Peringatan", "⚠️ Belum ada outlet terdaftar!\nTambah outlet dulu di menu Outlet."); return

        config.set('nama_toko',   nama)
        config.set('alamat_toko', self.inp_alamat.text().strip())
        config.set('telp_toko',   self.inp_telp.text().strip())
        config.set('app_mode',    mode)

        if mode == 'OUTLET' and self._outlet_list:
            idx = self.combo_outlet.currentIndex()
            ol  = self._outlet_list[idx]
            config.set('outlet_id',   db.uuid_to_hex(ol['id']))
            config.set('outlet_kode', ol['kode_outlet'])
        self.accept()


def check_and_run_wizard(parent=None):
    """Panggil di startup — jika nama_toko kosong, jalankan wizard."""
    if not config.get('nama_toko', '').strip():
        wiz = SetupWizardDialog(parent)
        wiz.exec_()


# ─────────────────────────────────────────────
# SETTINGS WIDGET (4 TAB)
# ─────────────────────────────────────────────
class SettingsWidget(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.setStyleSheet("background:#f4f6f9;")
        self._build()
        self._load_all()

    def _inp(self, ph=""):
        w = QLineEdit(); w.setPlaceholderText(ph)
        w.setStyleSheet("padding:8px;border:1px solid #dcdde1;border-radius:4px;background:white;font-size:12px;")
        return w

    def _combo(self, items):
        w = QComboBox()
        w.addItems(items)
        w.setStyleSheet("padding:8px;border:1px solid #dcdde1;border-radius:4px;background:white;font-size:12px;")
        return w

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(20, 20, 20, 20)
        hdr = QLabel("⚙️ Pengaturan Aplikasi"); hdr.setFont(get_font(15, bold=True))
        root.addWidget(hdr)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_profil(),    "🏢 Profil Toko")
        self.tabs.addTab(self._tab_koneksi(),   "🌐 Koneksi & Mode")
        self.tabs.addTab(self._tab_printer(),   "🖨️ Printer & Struk")
        self.tabs.addTab(self._tab_preferensi(),"⚙️ Preferensi")
        root.addWidget(self.tabs, 1)

        # Tombol simpan global
        btn_lay = QHBoxLayout(); btn_lay.addStretch()
        self.btn_simpan = QPushButton("💾 Simpan Semua Settings")
        self.btn_simpan.setStyleSheet("background:#2ecc71;color:white;font-weight:bold;padding:10px 30px;border-radius:6px;font-size:13px;")
        self.btn_simpan.clicked.connect(self._simpan_semua)
        btn_lay.addWidget(self.btn_simpan); root.addLayout(btn_lay)

    # ── TAB 1: PROFIL TOKO ──
    def _tab_profil(self):
        w = QWidget(); frm = QFormLayout(w); frm.setSpacing(12); frm.setContentsMargins(20,20,20,20)
        self.p_nama    = self._inp("Nama toko / koperasi")
        self.p_alamat  = self._inp("Alamat lengkap")
        self.p_kota    = self._inp("Kota / kabupaten")
        self.p_telp    = self._inp("No. telepon / WA")
        self.p_email   = self._inp("Email (opsional)")
        self.p_npwp    = self._inp("NPWP (opsional)")
        self.p_tagline = self._inp("Contoh: Terima kasih telah berbelanja!")
        for lbl, w2 in [("🏢 Nama Toko *:", self.p_nama), ("📍 Alamat:", self.p_alamat),
                        ("🏙️ Kota:", self.p_kota), ("📞 Telepon:", self.p_telp),
                        ("📧 Email:", self.p_email), ("🔢 NPWP:", self.p_npwp),
                        ("💬 Tagline Struk:", self.p_tagline)]:
            frm.addRow(lbl, w2)
        return w

    # ── TAB 2: KONEKSI & MODE ──
    def _tab_koneksi(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(20,20,20,20); lay.setSpacing(15)

        # Mode
        mode_frame = QFrame(); mode_frame.setStyleSheet("background:white;border-radius:8px;border:1px solid #e2e8f0;padding:5px;")
        mf = QFormLayout(mode_frame); mf.setSpacing(10); mf.setContentsMargins(15,12,15,12)
        mf.addRow(QLabel("<b>Mode Aplikasi</b>"))
        self.k_mode = self._combo(["PUSAT", "OUTLET"])
        self.k_mode.currentTextChanged.connect(self._on_mode_changed)
        self.k_outlet = self._combo([])
        self._load_outlet_combo()
        mf.addRow("🌐 Mode:", self.k_mode)
        mf.addRow("🏪 Outlet (jika OUTLET):", self.k_outlet)
        lay.addWidget(mode_frame)

        # MariaDB
        db_frame = QFrame(); db_frame.setStyleSheet("background:white;border-radius:8px;border:1px solid #e2e8f0;")
        df = QFormLayout(db_frame); df.setSpacing(10); df.setContentsMargins(15,12,15,12)
        df.addRow(QLabel("<b>Koneksi MariaDB (untuk sinkronisasi multi-outlet)</b>"))
        self.k_host = self._inp("Tailscale IP atau localhost")
        self.k_port = QSpinBox(); self.k_port.setRange(1, 65535); self.k_port.setValue(3306)
        self.k_port.setStyleSheet("padding:7px;border:1px solid #dcdde1;border-radius:4px;background:white;")
        self.k_user = self._inp("Username MariaDB")
        self.k_pass = self._inp("Password MariaDB")
        self.k_pass.setEchoMode(QLineEdit.Password)
        self.k_db   = self._inp("Nama database")
        for lbl, ww in [("🖥️ Host / IP:", self.k_host), ("🔌 Port:", self.k_port),
                        ("👤 Username:", self.k_user), ("🔒 Password:", self.k_pass),
                        ("🗄️ Database:", self.k_db)]:
            df.addRow(lbl, ww)

        # Test koneksi
        test_lay = QHBoxLayout()
        self.btn_test = QPushButton("🔌 Test Koneksi MariaDB")
        self.btn_test.setStyleSheet("background:#1abc9c;color:white;font-weight:bold;padding:8px 20px;border-radius:6px;")
        self.btn_test.clicked.connect(self._test_koneksi)
        self.lbl_test_result = QLabel("—")
        self.lbl_test_result.setStyleSheet("padding:6px; font-weight:bold; border-radius:4px;")
        test_lay.addWidget(self.btn_test); test_lay.addWidget(self.lbl_test_result); test_lay.addStretch()
        df.addRow("", test_lay)
        lay.addWidget(db_frame); lay.addStretch()
        return w

    def _load_outlet_combo(self):
        self.k_outlet.clear(); self._outlet_list = []
        rows = db.execute_local("SELECT id, kode_outlet, nama_outlet FROM master_outlet WHERE is_active=1", fetch_all=True)
        if rows:
            for r in rows:
                self.k_outlet.addItem(f"{r['kode_outlet']} - {r['nama_outlet']}")
                self._outlet_list.append(dict(r))

    def _on_mode_changed(self, v):
        self.k_outlet.setEnabled(v == 'OUTLET')

    def _test_koneksi(self):
        # Sementara apply config dulu ke db_manager lalu test
        db.set_mariadb_config(
            self.k_host.text().strip(), self.k_port.value(),
            self.k_user.text().strip(), self.k_pass.text(),
            self.k_db.text().strip()
        )
        if db.is_online():
            self.lbl_test_result.setText("✅ Koneksi berhasil!")
            self.lbl_test_result.setStyleSheet("padding:6px;font-weight:bold;color:white;background:#2ecc71;border-radius:4px;")
        else:
            self.lbl_test_result.setText("❌ Gagal terhubung")
            self.lbl_test_result.setStyleSheet("padding:6px;font-weight:bold;color:white;background:#e74c3c;border-radius:4px;")

    # ── TAB 3: PRINTER & STRUK ──
    def _tab_printer(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(20,20,20,20); lay.setSpacing(15)

        pr_frame = QFrame(); pr_frame.setStyleSheet("background:white;border-radius:8px;border:1px solid #e2e8f0;")
        pf = QFormLayout(pr_frame); pf.setSpacing(10); pf.setContentsMargins(15,12,15,12)
        pf.addRow(QLabel("<b>Konfigurasi Printer Thermal</b>"))
        self.pr_name  = self._inp("Nama printer (sesuai sistem OS)")
        self.pr_width = self._combo(["58mm", "80mm"])
        self.pr_usb_vid = self._inp("VID (hex, contoh: 04b8)")
        self.pr_usb_pid = self._inp("PID (hex, contoh: 0202)")
        for lbl, ww in [("🖨️ Nama Printer:", self.pr_name), ("📏 Lebar Kertas:", self.pr_width),
                        ("🔌 USB VID:", self.pr_usb_vid), ("🔌 USB PID:", self.pr_usb_pid)]:
            pf.addRow(lbl, ww)
        lay.addWidget(pr_frame)

        struk_frame = QFrame(); struk_frame.setStyleSheet("background:white;border-radius:8px;border:1px solid #e2e8f0;")
        sf = QFormLayout(struk_frame); sf.setSpacing(10); sf.setContentsMargins(15,12,15,12)
        sf.addRow(QLabel("<b>Kustomisasi Struk (Plain Text)</b>"))
        self.st_header1 = self._inp("Baris header 1 struk")
        self.st_header2 = self._inp("Baris header 2 struk")
        self.st_header3 = self._inp("Baris header 3 struk")
        self.st_footer1 = self._inp("Baris footer 1 struk")
        self.st_footer2 = self._inp("Baris footer 2 struk")
        self.st_footer3 = self._inp("Ucapan terima kasih, dll")
        for lbl, ww in [("📄 Header Baris 1:", self.st_header1), ("📄 Header Baris 2:", self.st_header2),
                        ("📄 Header Baris 3:", self.st_header3), ("📄 Footer Baris 1:", self.st_footer1),
                        ("📄 Footer Baris 2:", self.st_footer2), ("📄 Footer Baris 3:", self.st_footer3)]:
            sf.addRow(lbl, ww)

        # Preview struk
        self.btn_preview_struk = QPushButton("👁️ Preview Struk")
        self.btn_preview_struk.setStyleSheet("background:#9b59b6;color:white;padding:7px 15px;border-radius:6px;font-weight:bold;")
        self.btn_preview_struk.clicked.connect(self._preview_struk)
        sf.addRow("", self.btn_preview_struk)
        lay.addWidget(struk_frame); lay.addStretch()
        return w

    def _preview_struk(self):
        w = self.pr_width.currentText()
        char_w = 32 if w == "58mm" else 48
        sep = "=" * char_w
        nama = config.get('nama_toko', self.p_nama.text() or 'NAMA TOKO')
        h1 = self.st_header1.text() or nama
        h2 = self.st_header2.text() or config.get('alamat_toko','')
        h3 = self.st_header3.text() or config.get('telp_toko','')
        f1 = self.st_footer1.text(); f2 = self.st_footer2.text(); f3 = self.st_footer3.text()
        preview = f"""{sep}
{h1.center(char_w)}
{h2.center(char_w)}
{h3.center(char_w)}
{sep}
No  : TRX-20260518-0001
Tgl : 18/05/2026 10:30
Kasir: Admin
{sep}
Mie Instan Goreng  x2
  Rp 3.500     Rp 7.000
Susu UHT 1L    x1
  Rp 18.000    Rp 18.000
{sep}
Subtotal       Rp 25.000
Diskon              Rp 0
TOTAL          Rp 25.000
Bayar          Rp 30.000
Kembali         Rp 5.000
{sep}
{f1.center(char_w) if f1 else ''}
{f2.center(char_w) if f2 else ''}
{f3.center(char_w) if f3 else 'Terima kasih!'.center(char_w)}
{sep}"""
        dlg = QDialog(self); dlg.setWindowTitle("Preview Struk"); dlg.resize(380, 480)
        dlg.setStyleSheet("background:#f4f6f9;")
        vl = QVBoxLayout(dlg)
        txt = QTextEdit(); txt.setReadOnly(True)
        txt.setFont(get_font(9))
        txt.setStyleSheet("background:#1e1e1e;color:#00ff00;font-family:Courier New,monospace;padding:10px;border-radius:6px;")
        txt.setPlainText(preview)
        vl.addWidget(txt)
        btn = QPushButton("✅ Tutup"); btn.clicked.connect(dlg.accept)
        vl.addWidget(btn); dlg.exec_()

    # ── TAB 4: PREFERENSI ──
    def _tab_preferensi(self):
        w = QWidget(); frm = QFormLayout(w); frm.setSpacing(12); frm.setContentsMargins(20,20,20,20)
        frm.addRow(QLabel("<b>Pengaturan Transaksi</b>"))
        self.pref_ppn    = QDoubleSpinBox(); self.pref_ppn.setRange(0, 100); self.pref_ppn.setSuffix(" %")
        self.pref_ppn.setStyleSheet("padding:7px;border:1px solid #dcdde1;border-radius:4px;background:white;")
        self.pref_matauang = self._inp("Contoh: Rp")
        self.pref_sync_interval = QSpinBox(); self.pref_sync_interval.setRange(5, 300)
        self.pref_sync_interval.setSuffix(" detik"); self.pref_sync_interval.setValue(30)
        self.pref_sync_interval.setStyleSheet("padding:7px;border:1px solid #dcdde1;border-radius:4px;background:white;")
        frm.addRow("💹 Default PPN %:", self.pref_ppn)
        frm.addRow("💰 Mata Uang:", self.pref_matauang)

        frm.addRow(QLabel("<br><b>Sinkronisasi</b>"))
        frm.addRow("🔄 Auto-sync Interval:", self.pref_sync_interval)

        frm.addRow(QLabel("<br><b>Backup Data</b>"))
        btn_backup = QPushButton("🚧 Backup Data (Coming Soon)")
        btn_backup.setEnabled(False)
        btn_backup.setStyleSheet("background:#95a5a6;color:white;padding:8px 15px;border-radius:6px;")
        frm.addRow("", btn_backup)
        return w

    # ── LOAD & SIMPAN ──
    def _load_all(self):
        # Tab profil
        self.p_nama.setText(config.get('nama_toko',''))
        self.p_alamat.setText(config.get('alamat_toko',''))
        self.p_kota.setText(config.get('kota_toko',''))
        self.p_telp.setText(config.get('telp_toko',''))
        self.p_email.setText(config.get('email_toko',''))
        self.p_npwp.setText(config.get('npwp_toko',''))
        self.p_tagline.setText(config.get('tagline_struk',''))
        # Tab koneksi
        mode = config.get('app_mode','PUSAT')
        self.k_mode.setCurrentText(mode)
        self.k_outlet.setEnabled(mode == 'OUTLET')
        saved_kode = config.get('outlet_kode','')
        for i, ol in enumerate(getattr(self, '_outlet_list', [])):
            if ol['kode_outlet'] == saved_kode:
                self.k_outlet.setCurrentIndex(i); break
        self.k_host.setText(config.get('mariadb_host',''))
        self.k_port.setValue(config.get_int('mariadb_port', 3306))
        self.k_user.setText(config.get('mariadb_user',''))
        self.k_pass.setText(config.get('mariadb_pass',''))
        self.k_db.setText(config.get('mariadb_db',''))
        # Tab printer
        self.pr_name.setText(config.get('printer_name',''))
        pw = config.get('paper_width','58')
        self.pr_width.setCurrentText(f"{pw}mm" if 'mm' not in pw else pw)
        self.pr_usb_vid.setText(config.get('printer_vid',''))
        self.pr_usb_pid.setText(config.get('printer_pid',''))
        self.st_header1.setText(config.get('struk_header1',''))
        self.st_header2.setText(config.get('struk_header2',''))
        self.st_header3.setText(config.get('struk_header3',''))
        self.st_footer1.setText(config.get('struk_footer1',''))
        self.st_footer2.setText(config.get('struk_footer2',''))
        self.st_footer3.setText(config.get('struk_footer3',''))
        # Tab preferensi
        self.pref_ppn.setValue(config.get_int('ppn_default', 0))
        self.pref_matauang.setText(config.get('mata_uang','Rp'))
        self.pref_sync_interval.setValue(config.get_int('sync_interval', 30))

    def _simpan_semua(self):
        nama = self.p_nama.text().strip()
        if not nama:
            QMessageBox.warning(self, "Peringatan", "⚠️ Nama toko wajib diisi!"); return

        pairs = {
            'nama_toko': nama, 'alamat_toko': self.p_alamat.text().strip(),
            'kota_toko': self.p_kota.text().strip(), 'telp_toko': self.p_telp.text().strip(),
            'email_toko': self.p_email.text().strip(), 'npwp_toko': self.p_npwp.text().strip(),
            'tagline_struk': self.p_tagline.text().strip(),
            'app_mode': self.k_mode.currentText(),
            'mariadb_host': self.k_host.text().strip(), 'mariadb_port': str(self.k_port.value()),
            'mariadb_user': self.k_user.text().strip(), 'mariadb_pass': self.k_pass.text(),
            'mariadb_db': self.k_db.text().strip(),
            'printer_name': self.pr_name.text().strip(),
            'paper_width': self.pr_width.currentText().replace('mm',''),
            'printer_vid': self.pr_usb_vid.text().strip(), 'printer_pid': self.pr_usb_pid.text().strip(),
            'struk_header1': self.st_header1.text().strip(), 'struk_header2': self.st_header2.text().strip(),
            'struk_header3': self.st_header3.text().strip(), 'struk_footer1': self.st_footer1.text().strip(),
            'struk_footer2': self.st_footer2.text().strip(), 'struk_footer3': self.st_footer3.text().strip(),
            'ppn_default': str(int(self.pref_ppn.value())),
            'mata_uang': self.pref_matauang.text().strip() or 'Rp',
            'sync_interval': str(self.pref_sync_interval.value()),
        }

        # Outlet jika mode OUTLET
        if self.k_mode.currentText() == 'OUTLET' and hasattr(self, '_outlet_list') and self._outlet_list:
            ol = self._outlet_list[self.k_outlet.currentIndex()]
            pairs['outlet_id']   = db.uuid_to_hex(ol['id'])
            pairs['outlet_kode'] = ol['kode_outlet']

        # INSERT OR IGNORE missing keys dulu, lalu UPDATE semua
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        for k, v in pairs.items():
            c.execute("INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES (?,?)", (k, v))
            c.execute("UPDATE app_settings SET setting_value=?, updated_at=datetime('now') WHERE setting_key=?", (v, k))
        conn.commit(); conn.close()

        # Update MariaDB config di db_manager runtime
        db.set_mariadb_config(
            pairs['mariadb_host'], int(pairs['mariadb_port']),
            pairs['mariadb_user'], pairs['mariadb_pass'], pairs['mariadb_db']
        )

        QMessageBox.information(self, "Sukses", "✅ Semua settings berhasil disimpan!")
        # Update sidebar header nama toko jika ada
        if hasattr(self.parent_window, 'setWindowTitle'):
            u = getattr(self.parent_window, 'current_user', {})
            role = u.get('role','')
            nama_user = u.get('nama_lengkap','')
            self.parent_window.setWindowTitle(f"M4-COMPACT POS  |  {nama_user}  [{role}]  —  {nama}")

    def muat_data_dari_db(self):
        """Dipanggil ulang saat widget diaktifkan kembali."""
        self._load_outlets_koneksi()
        self._load_all()

    def _load_outlets_koneksi(self):
        self._load_outlet_combo()
