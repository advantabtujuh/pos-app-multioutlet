# ── 1. Tambah import di bagian atas (setelah from outlet import ...) ──
from pembelian import init_pembelian_database, PembelianWidget

# ── 2. Update MENU_PERMISSIONS — hapus PEMBELIAN dari GUDANG ──
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
        "MUTASI",
        # "PEMBELIAN" ← DIHAPUS: GUDANG bisa akses tapi tidak bisa POSTING
        # → solusi: GUDANG tetap ada di sini, POSTING di-disable by role di PembelianWidget
        "PEMBELIAN",        # akses UI ada, tombol POSTING di-disable di widget
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

# ── 3. Tambah nav_pembelian di NAV_MAP (sudah ada "PEMBELIAN": "_ph_pembelian") ──
# Ganti "_ph_pembelian" menjadi "_nav_pembelian" di NAV_MAP:
NAV_MAP = {
    # ... (semua entry lain tetap sama) ...
    "PEMBELIAN": "_nav_pembelian",   # ← UBAH dari "_ph_pembelian"
    # ...
}

# ── 4. Tambah method _nav_pembelian di class MainWindowPOS ──
def _nav_pembelian(self):
    self._open_widget(PembelianWidget)

# ── 5. Update _init_databases() — tambah init_pembelian_database() ──
def _init_databases():
    db.init_all_databases()
    init_kategori_database()
    init_customer_database()
    init_member_database()
    init_supplier_database()
    init_barang_database()
    init_pembelian_database()   # ← TAMBAH INI

# ── 6. Fix logout loop di run_app() ──
# Ganti blok run_app() yang lama dengan ini:
def run_app():
    app = QApplication(sys.argv)
    app.setFont(get_font(10))
    app.setStyle("Fusion")
    _init_databases()

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

        # Kalau window ditutup via tombol X (bukan logout), keluar loop
        if not logout_flag['fired']:
            break
        # Kalau logout → loop lanjut, tampilkan login lagi

    sys.exit(0)
