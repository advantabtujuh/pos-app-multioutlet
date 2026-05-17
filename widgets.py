from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


def get_font(size, bold=False):
    """Return QFont dengan fallback universal untuk semua OS."""
    weight = QFont.Bold if bold else QFont.Normal
    for family in ["Arial", "Helvetica", "DejaVu Sans", "Liberation Sans", "Noto Sans"]:
        font = QFont(family, size, weight)
        if QFont(family).exactMatch() or font.exactMatch():
            return font
    return QFont("sans-serif", size, weight)


class AdminLTECard(QFrame):
    """Card bergaya AdminLTE dengan gradient, icon, dan shadow."""

    GRADIENTS = {
        "blue":   ("#3c8dbc", "#367fa9"),
        "green":  ("#00a65a", "#008d4c"),
        "yellow": ("#f39c12", "#e08e0b"),
        "red":    ("#dd4b39", "#d73925"),
        "purple": ("#605ca8", "#545096"),
        "aqua":   ("#00c0ef", "#00acd6"),
        "maroon": ("#d81b60", "#ca195a"),
    }

    def __init__(self, title, value, color_key, icon_text, parent=None):
        super().__init__(parent)
        self.color_key = color_key
        self.icon_text = icon_text
        self._setup_ui(title, value)

    def _setup_ui(self, title, value):
        top_color, bottom_color = self.GRADIENTS.get(self.color_key, self.GRADIENTS["blue"])

        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {top_color}, stop:1 {bottom_color});
                border-radius: 3px;
                border: none;
            }}
        """)
        self.setMinimumHeight(130)
        self.setMaximumHeight(130)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(0)

        # Left: Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(5)
        text_layout.setAlignment(Qt.AlignVCenter)

        self.value_label = QLabel(str(value))
        self.value_label.setFont(get_font(28, bold=True))
        self.value_label.setStyleSheet("color: white;")

        self.title_label = QLabel(title)
        self.title_label.setFont(get_font(11))
        self.title_label.setStyleSheet("color: rgba(255,255,255,0.9);")

        text_layout.addWidget(self.value_label)
        text_layout.addWidget(self.title_label)
        text_layout.addStretch()

        # Right: Icon
        icon_label = QLabel(self.icon_text)
        icon_label.setFont(get_font(48))
        icon_label.setStyleSheet("color: rgba(0,0,0,0.15);")
        icon_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addLayout(text_layout, 1)
        layout.addWidget(icon_label, 0, Qt.AlignRight | Qt.AlignVCenter)

    def set_value(self, value):
        self.value_label.setText(str(value))
