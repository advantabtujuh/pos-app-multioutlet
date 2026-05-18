"""
main.py — M4-COMPACT POS & Inventory System
"""
import sys
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QMessageBox, QStackedWidget, QScrollArea,
    QFrame, QSizePolicy, QToolButton
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from db_manager import db
from config_manager import config
from login_dialog import run_login_flow
from widgets import AdminLTECard, get_font

# Master data
from kategori   import init_kategori_database,  KategoriSatuanWidget
from barangdata import init_barang_database,    BarangDataWidget
from supplier   import init_supplier_database,  SupplierWidget
from customer   import init_customer_database,  CustomerWidget
from membership import init_member_database,    MemberWidget
from user       import UserWidget
from outlet     import OutletWidget

# Transaksi
from pembelian  import init_pembelian_database, PembelianWidget
from mutasi import init_mutasi_database, MutasiStokWidget

# Settings
from settings   import SettingsWidget, check_and_run_wizard


# ─────────────────────────────────────────────
# ROLE-BASED MENU PERMISSIONS
# ─────────────────────────────────────────────
MENU_PERMISSIONS = {
    "ADMIN": [
        "DASHBOARD",
        "KATEGORI", "BARANG", "SUPPLIER",
        "CUSTOMER", "MEMBER", "USER", "OUTLET",
        "MUTASI", "PEMBELIAN", "JUAL GROSIR", "POS KASIR",
        "BYR HUTANG SUPP", "BYR HUTANG MEMB", "BYR HUTANG CUST",
        "RETUR JUAL GROSIR", "RETUR PEMBELIAN",
        "LAP. PEMBELIAN", "LAP. JUAL GROSIR", "LAP. JUAL POS",
        "LAP. MEMBER", "LAP. KEUANGAN",
        "SETTINGS", "LOGOUT", "EXIT",
    ],
    "MANAGER": [
        "DASHBOARD",
        "KATEGORI", "BARANG", "SUPPLIER",
        "CUSTOMER", "MEMBER",
        "MUTASI", "PEMBELIAN", "JUAL GROSIR", "POS KASIR",
        "BYR HUTANG SUPP", "BYR HUTANG MEMB", "BYR HUTANG CUST",
        "RETUR JUAL GROSIR", "RETUR PEMBELIAN",
        "LAP. PEMBELIAN", "LAP. JUAL GROSIR", "LAP. JUAL POS",
        "LAP. MEMBER", "LAP. KEUANGAN",
        "SETTINGS", "LOGOUT", "EXIT",
    ],
    "GUDANG": [
        "DASHBOARD",
        "KATEGORI", "BARANG", "SUPPLIER",
        "MUTASI", "PEMBELIAN",   # POSTING di-disable by role di widget
        "RETUR PEMBELIAN",
        "LAP. PEMBELIAN",
        "LOGOUT", "EXIT",
    ],
    "KASIR": [
        "DASHBOARD",
        "CUSTOMER", "MEMBER",
        "POS KASIR",
        "BYR HUTANG MEMB", "BYR HUTANG CUST",
        "LAP. JUAL POS", "LAP. MEMBER",
        "LOGOUT", "EXIT",
    ],
}


# ─────────────────────────────────────────────
# COLLAPSIBLE SIDEBAR SECTION
# ─────────────────────────────────────────────
class CollapsibleSection(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        root = QVBoxLayout(self); root.setSpacing(0); root.setContentsMargins(0,0,0,0)

        self._btn = QToolButton()
        self._btn.setCheckable(True); self._btn.setChecked(True)
        self._btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn.setArrowType(Qt.DownArrow)
        self._btn.setText(f"  {title}")
        self._btn.setFont(get_font(8, bold=True))
        self._btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._btn.setStyleSheet("""
            QToolButton { background-color:rgba(26,37,47,0.5); color:#7f8c8d;
                border:none; padding:10px 15px; text-align:left;
                font-weight:bold; letter-spacing:1px; }
            QToolButton:hover { color:#ecf0f1; }
        """)
        self._btn.clicked.connect(self._on_toggle)
        root.addWidget(self._btn)

        self._container = QWidget(); self._container.setStyleSheet("background:transparent;")
        self._inner = QVBoxLayout(self._container)
        self._inner.setSpacing(2); self._inner.setContentsMargins(5,5,5,5)
        root.addWidget(self._container)
        self._child_buttons = []

    def _on_toggle(self, checked):
        self._container.setVisible(checked)
        self._btn.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    def add_item(self, widget):
        self._inner.addWidget(widget)
        if isinstance(widget, QPushButton):
            self._child_buttons.append(widget)

    def set_expanded(self, expanded):
        self._btn.setChecked(expanded); self._on_toggle(expanded)

    def get_child_buttons(self): return self._child_buttons

    def allowed_item_count(self, allowed_set):
        return sum(1 for b in self._child_buttons if b in allowed_set)


# ─────────────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────────────
class MainWindowPOS(QMainWindow):
    logout_requested = pyqtSignal()

    SECTIONS_DEF = [
        ("DASHBOARD", [("DASHBOARD", "🏠  Dashboard")]),
        ("MASTER DATA", [
            ("KATEGORI",  "🏷️  Kategori"), ("BARANG",   "📦  Barang"),
            ("SUPPLIER",  "🏭  Supplier"), ("CUSTOMER", "👥  Customer"),
            ("MEMBER",    "🎫  Member"),   ("USER",     "👤  User"),
            ("OUTLET",    "🏪  Outlet"),
        ]),
        ("TRANSAKSI", [
            ("MUTASI",          "🚚  Mutasi"),
            ("PEMBELIAN",       "🛒  Pembelian"),
            ("JUAL GROSIR",     "📊  Jual Grosir"),
            ("POS KASIR",       "🧾  POS Kasir"),
            ("BYR HUTANG SUPP", "💵  Byr Hutang Supp"),
            ("BYR HUTANG MEMB", "💵  Byr Hutang Memb"),
            ("BYR HUTANG CUST", "💵  Byr Hutang Cust"),
        ]),
        ("RETUR", [
            ("RETUR JUAL GROSIR", "🔄  Retur Jual Grosir"),
            ("RETUR PEMBELIAN",   "🔄  Retur Pembelian"),
        ]),
        ("LAPORAN", [
            ("LAP. PEMBELIAN",   "📈  Lap. Pembelian"),
            ("LAP. JUAL GROSIR", "📈  Lap. Jual Grosir"),
            ("LAP. JUAL POS",    "📈  Lap. Jual POS"),
            ("LAP. MEMBER",      "📈  Lap. Member"),
            ("LAP. KEUANGAN",    "📈  Lap. Keuangan"),
        ]),
        ("UTILITY", [
            ("SETTINGS", "🔧  Settings"),
            ("LOGOUT",   "🚪  Logout"),
            ("EXIT",     "❌  Exit"),
        ]),
    ]

    # DI SINI PERBAIKANNYA: Menggunakan format dictionary {key: value} yang benar
    NAV_MAP = {
        "DASHBOARD":        "_nav_dashboard",
        "KATEGORI":         "_nav_kategori",
        "BARANG":           "_nav_barang",
        "SUPPLIER":         "_nav_supplier",
        "CUSTOMER":         "_nav_customer",
        "MEMBER":           "_nav_member",
        "USER":             "_nav_user",
        "OUTLET":           "_nav_outlet",
        "MUTASI":           "_nav_mutasi",
        "PEMBELIAN":        "_nav_pembelian",
        "JUAL GROSIR":      "_ph_jual_grosir",
        "POS KASIR":        "_ph_pos",
        "BYR HUTANG SUPP":  "_ph_bayar_supp",
        "BYR HUTANG MEMB":  "_ph_bayar_memb",
        "BYR HUTANG CUST":  "_ph_bayar_cust",
        "RETUR JUAL GROSIR":"_ph_retur_grosir",
        "RETUR PEMBELIAN":  "_ph_retur_beli",
        "LAP. PEMBELIAN":   "_ph_lap_beli",
        "LAP. JUAL GROSIR": "_ph_lap_grosir",
        "LAP. JUAL POS":    "_ph_lap_pos",
        "LAP. MEMBER":      "_ph_lap_member",
        "LAP. KEUANGAN":    "_ph_lap_keuangan",
        "SETTINGS":         "_nav_settings",
        "LOGOUT":           "_do_logout",
        "EXIT":             "close",
    }

    def __init__(self, user_data):
        super().__init__()
        raw_role = user_data.get("role", "KASIR") or "KASIR"
        self._role = str(raw_role).strip().upper()
        self.current_user = user_data

        if self._role not in MENU_PERMISSIONS:
            self._role = "KASIR"
            self.current_user["role"] = "KASIR"

        nama_toko = config.get('nama_toko', 'M4-COMPACT POS').upper()
        self.setWindowTitle(f"{nama_toko}  |  {user_data['nama_lengkap']}  [{self._role}]")
        self.showMaximized()
        self.setStyleSheet("QMainWindow { background-color:#f4f6f9; }")

        root = QWidget(); self.setCentralWidget(root)
        main_layout = QHBoxLayout(root)
        main_layout.setSpacing(0); main_layout.setContentsMargins(0,0,0,0)

        self._menu_buttons = []; self._sections = []
        sidebar = self._build_sidebar(); sidebar.setFixedWidth(260)
        main_layout.addWidget(sidebar)

        self.content = QStackedWidget()
        self.content.setObjectName("MainContent")
        self.content.setStyleSheet("#MainContent { background-color:#f4f6f9; border-left:1px solid #d2d6de; }")
        main_layout.addWidget(self.content, 1)

        self._build_dashboard()
        self._apply_role_filter()

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setStyleSheet("QFrame { background-color:#222d32; border:none; }")
        outer = QVBoxLayout(sidebar); outer.setSpacing(0); outer.setContentsMargins(0,0,0,0)
        outer.addWidget(self._build_sidebar_header())

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border:none; background:transparent; }
            QScrollBar:vertical { width:5px; background:transparent; }
            QScrollBar::handle:vertical { background:#374850; border-radius:2px; }
        """)
        menu_root = QWidget(); menu_root.setStyleSheet("background:transparent;")
        menu_layout = QVBoxLayout(menu_root)
        menu_layout.setSpacing(2); menu_layout.setContentsMargins(10,15,10,15)

        for sec_title, items in self.SECTIONS_DEF:
            sec = CollapsibleSection(sec_title); sec.set_expanded(True)
            for key, display in items:
                cb_name = self.NAV_MAP.get(key, "_nav_dashboard")
                if cb_name == "close":
                    callback = self.close
                else:
                    callback = getattr(self, cb_name)
                btn = self._make_menu_btn(key, display, callback)
                sec.add_item(btn); self._menu_buttons.append(btn)
            self._sections.append(sec)
            menu_layout.addWidget(sec)

        menu_layout.addStretch()
        scroll.setWidget(menu_root); outer.addWidget(scroll, 1)
        return sidebar

    def _build_sidebar_header(self):
        header = QWidget(); header.setFixedHeight(100)
        header.setStyleSheet("background-color:#1a2226;")
        layout = QVBoxLayout(header); layout.setContentsMargins(20,18,20,15); layout.setSpacing(6)

        nama_toko = config.get('nama_toko', 'NAMA TOKO').upper()
        lbl_toko = QLabel(nama_toko)
        lbl_toko.setFont(get_font(13, bold=True))
        lbl_toko.setStyleSheet("color:#f1f5f9; letter-spacing:1px;")
        lbl_toko.setWordWrap(True)
        layout.addWidget(lbl_toko)

        line = QFrame(); line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1); line.setStyleSheet("background-color:#374850;")
        layout.addWidget(line)

        role_colors = {"ADMIN":"#e74c3c","MANAGER":"#9b59b6","GUDANG":"#f39c12","KASIR":"#3498db"}
        lbl_user = QLabel(f"  {self.current_user['nama_lengkap']}  |  {self._role}")
        lbl_user.setFont(get_font(9, bold=True))
        lbl_user.setStyleSheet(f"color:{role_colors.get(self._role,'#3b82f6')};")
        lbl_user.setWordWrap(True)
        layout.addWidget(lbl_user)
        return header

    def _make_menu_btn(self, key, display, callback):
        btn = QPushButton(display)
        btn.setProperty("menu_key", key)
        btn.setFont(get_font(9)); btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setStyleSheet("""
            QPushButton { background-color:transparent; color:#b8c7ce;
                border:none; padding:10px 15px; text-align:left; }
            QPushButton:hover { background-color:#1e282c; color:#ffffff; }
            QPushButton:pressed { background-color:#3b82f6; color:white; }
        """)
        btn.clicked.connect(callback)
        return btn

    def _apply_role_filter(self):
        allowed = set(MENU_PERMISSIONS.get(self._role, MENU_PERMISSIONS["KASIR"]))
        self._allowed_buttons = set()
        for btn in self._menu_buttons:
            key = btn.property("menu_key")
            vis = key in allowed
            btn.setVisible(vis)
            if vis: self._allowed_buttons.add(btn)
        for sec in self._sections:
            sec.setVisible(sec.allowed_item_count(self._allowed_buttons) > 0)

    def _build_dashboard(self):
        page = QWidget(); page.setStyleSheet("background-color:#f4f6f9;")
        layout = QVBoxLayout(page); layout.setContentsMargins(25,25,25,25); layout.setSpacing(20)

        lbl_title = QLabel("📊 Dashboard Overview")
        lbl_title.setFont(get_font(22, bold=True)); lbl_title.setStyleSheet("color:#1e293b;")
        layout.addWidget(lbl_title)

        lbl_sub = QLabel(f"Selamat datang, {self.current_user['nama_lengkap']}  —  {datetime.now().strftime('%A, %d %B %Y')}")
        lbl_sub.setFont(get_font(10)); lbl_sub.setStyleSheet("color:#64748b;")
        layout.addWidget(lbl_sub)

        row1 = QHBoxLayout(); row1.setSpacing(15)
        self.card_barang    = AdminLTECard("Total Barang",       "0",    "blue",   "📦")
        self.card_stok      = AdminLTECard("Total Stok (Pcs)",   "0",    "green",  "📊")
        self.card_penjualan = AdminLTECard("Penjualan Hari Ini", "Rp 0", "yellow", "💰")
        self.card_member    = AdminLTECard("Total Member",        "0",    "purple", "🎫")
        for c in [self.card_barang, self.card_stok, self.card_penjualan, self.card_member]:
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed); row1.addWidget(c)
        layout.addLayout(row1)

        row2 = QHBoxLayout(); row2.setSpacing(15)
        self.card_hutang_member   = AdminLTECard("Hutang Member",   "Rp 0", "red",    "💳")
        self.card_hutang_supplier = AdminLTECard("Hutang Supplier", "Rp 0", "aqua",   "🏭")
        self.card_hutang_customer = AdminLTECard("Hutang Customer", "Rp 0", "maroon", "👥")
        for c in [self.card_hutang_member, self.card_hutang_supplier, self.card_hutang_customer]:
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed); row2.addWidget(c)
        layout.addLayout(row2)

        layout.addStretch()
        self.content.addWidget(page)

    # ── NAVIGASI MASTER DATA ──
    def _nav_dashboard(self): self.content.setCurrentIndex(0)
    def _nav_kategori(self):  self._open_widget(KategoriSatuanWidget)
    def _nav_barang(self):    self._open_widget(BarangDataWidget)
    def _nav_supplier(self):  self._open_widget(SupplierWidget)
    def _nav_customer(self):  self._open_widget(CustomerWidget)
    def _nav_member(self):    self._open_widget(MemberWidget)
    def _nav_user(self):      self._open_widget(UserWidget)
    def _nav_outlet(self):    self._open_widget(OutletWidget)

    # ── NAVIGASI TRANSAKSI ──
    def _nav_pembelian(self): self._open_widget(PembelianWidget)
    def _nav_settings(self):  self._open_widget(SettingsWidget)
    def _nav_mutasi(self):    self._open_widget(MutasiStokWidget)

    # ── PLACEHOLDER (modul belum dibuat) ──
    def _ph_jual_grosir(self):  self._open_placeholder("Penjualan Grosir")
    def _ph_pos(self):          self._open_placeholder("POS Kasir")
    def _ph_bayar_supp(self):   self._open_placeholder("Bayar Hutang Supplier")
    def _ph_bayar_memb(self):   self._open_placeholder("Bayar Hutang Member")
    def _ph_bayar_cust(self):   self._open_placeholder("Bayar Hutang Customer")
    def _ph_retur_grosir(self): self._open_placeholder("Retur Jual Grosir")
    def _ph_retur_beli(self):   self._open_placeholder("Retur Pembelian")
    def _ph_lap_beli(self):     self._open_placeholder("Laporan Pembelian")
    def _ph_lap_grosir(self):   self._open_placeholder("Laporan Jual Grosir")
    def _ph_lap_pos(self):      self._open_placeholder("Laporan Jual POS")
    def _ph_lap_member(self):   self._open_placeholder("Laporan Member")
    def _ph_lap_keuangan(self): self._open_placeholder("Laporan Keuangan")

    def _open_widget(self, widget_class):
        for i in range(self.content.count()):
            w = self.content.widget(i)
            if type(w) is widget_class:
                self.content.setCurrentIndex(i)
                if hasattr(w, 'muat_data_dari_db'): w.muat_data_dari_db()
                return
        w = widget_class(self)
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content.addWidget(w); self.content.setCurrentWidget(w)

    def _open_placeholder(self, title):
        for i in range(self.content.count()):
            w = self.content.widget(i)
            if w.property("ph_title") == title:
                self.content.setCurrentIndex(i); return
        page = QWidget(); page.setProperty("ph_title", title)
        page.setStyleSheet("background-color:#f4f6f9;")
        layout = QVBoxLayout(page); layout.setAlignment(Qt.AlignCenter)
        card = QFrame()
        card.setStyleSheet("QFrame { background-color:white; border-radius:16px; border:1px solid #e2e8f0; }")
        card.setFixedSize(420, 240)
        cl = QVBoxLayout(card); cl.setAlignment(Qt.AlignCenter); cl.setSpacing(12); cl.setContentsMargins(40,40,40,40)
        ico = QLabel("🚧"); ico.setFont(get_font(52)); ico.setAlignment(Qt.AlignCenter)
        lbl = QLabel(str(title)); lbl.setFont(get_font(16, bold=True))
        lbl.setStyleSheet("color:#1e293b;"); lbl.setAlignment(Qt.AlignCenter); lbl.setWordWrap(True)
        sub = QLabel("Modul dalam pengembangan"); sub.setFont(get_font(10))
        sub.setStyleSheet("color:#94a3b8;"); sub.setAlignment(Qt.AlignCenter)
        cl.addWidget(ico); cl.addWidget(lbl); cl.addWidget(sub)
        layout.addWidget(card)
        self.content.addWidget(page); self.content.setCurrentWidget(page)

    def _do_logout(self):
        reply = QMessageBox.question(self, "Konfirmasi Logout",
            f"Yakin logout?\n\nUser: {self.current_user['nama_lengkap']}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            db.log_activity(self.current_user["id"], self.current_user["username"],
                            "LOGOUT", "User logout dari sistem")
            self.logout_requested.emit()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
def _init_databases():
    db.init_all_databases()
    init_kategori_database()
    init_customer_database()
    init_member_database()
    init_supplier_database()
    init_barang_database()
    init_pembelian_database()
    init_mutasi_database()


def run_app():
    app = QApplication(sys.argv)
    app.setFont(get_font(10))
    app.setStyle("Fusion")

    _init_databases()
    check_and_run_wizard()

    while True:
        user_data = run_login_flow()
        if user_data is None:
            break

        role = str(user_data.get("role", "KASIR") or "KASIR").strip().upper()
        user_data["role"] = role

        if role not in MENU_PERMISSIONS:
            QMessageBox.critical(None, "Role Tidak Dikenal",
                f"Role '{role}' tidak terdaftar.\nHubungi Administrator.")
            continue

        window = MainWindowPOS(user_data)
        logout_flag = {'fired': False}

        def on_logout():
            logout_flag['fired'] = True
            window.close()

        window.logout_requested.connect(on_logout)
        window.show()
        app.exec_()

        if not logout_flag['fired']:
            break

    sys.exit(0)


if __name__ == "__main__":
    run_app()
