"""
charger_ui.py — 灵动岛充电桩 UI

数据格式（update_data 入参）：
  {
    "站点名": [
      {"serial": int, "outletNo": str, "status": int,
       "power_w": int|None, "fee": float|None, "used_min": int|None},
      ...
    ],
    ...
  }

排序键（全局，作用于所有站点卡片）：
  SORT_SERIAL   — 按插座序号（默认）
  SORT_POWER    — 按充电功率降序
  SORT_FEE      — 按累计费用降序
  SORT_DURATION — 按已充时长降序
"""

import math
from typing import Optional
from PyQt5.QtWidgets import (
    QWidget, QScrollArea, QFrame, QSizePolicy,
    QMenu, QAction, QLineEdit, QLabel, QApplication, QPushButton
)
from PyQt5.QtCore import Qt, QTimer, QRect, QRectF, QPoint
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QPainterPath, QFontMetrics,
    QPen, QLinearGradient, QRegion, QPixmap, QIcon
)

# ══════════════════════════════════════════════════════════
#  排序常量
# ══════════════════════════════════════════════════════════
SORT_SERIAL   = 0
SORT_POWER    = 1
SORT_FEE      = 2
SORT_DURATION = 3

SORT_LABELS = {
    SORT_SERIAL:   ("序号", "插座序号"),
    SORT_POWER:    ("功率", "充电功率"),
    SORT_FEE:      ("费用", "累计费用"),
    SORT_DURATION: ("时长", "充电时长"),
}

# ══════════════════════════════════════════════════════════
#  颜色 & 布局常量
# ══════════════════════════════════════════════════════════
def ac(color, alpha):
    c = QColor(color)
    c.setAlpha(max(0, min(255, alpha)))
    return c

C_ISL    = QColor(18, 18, 18)
C_ISL_H  = QColor(28, 28, 28)
C_CARD   = QColor(26, 26, 28)
C_SEP    = QColor(55, 55, 60)
C_WHITE  = QColor(255, 255, 255)
C_GREY   = QColor(130, 130, 135)
C_DARK   = QColor(70, 70, 75)
C_GREEN  = QColor(48, 209, 88)
C_RED    = QColor(255, 69, 58)
C_YELLOW = QColor(255, 214, 10)
C_BLUE   = QColor(10, 132, 255)
C_PURPLE = QColor(191, 90, 242)
C_ORANGE = QColor(255, 159, 10)

STATUS_COLOR = {1: C_GREEN, 2: C_RED, 3: C_YELLOW}
STATUS_LABEL = {1: "空  闲", 2: "占  用", 3: "损  坏"}

ISLAND_W   = 380
CAPSULE_H  = 46
PANEL_GAP  = 10
PANEL_Y    = CAPSULE_H + PANEL_GAP

# 展开面板内部布局
SEARCH_TOP = 12
SEARCH_H   = 36
TOOLBAR_H  = 32          # 计数 + 排序工具栏高度
SCROLL_TOP = SEARCH_TOP + SEARCH_H + 6 + TOOLBAR_H + 6
EXPANDED_H = 520

PAD      = 12
ROW_GAP  = 5
CARD_GAP = 8


# ══════════════════════════════════════════════════════════
#  排序工具函数
# ══════════════════════════════════════════════════════════
def _sort_key(outlet, mode):
    """返回排序键，None 值始终排在最后。"""
    if mode == SORT_POWER:
        v = outlet.get("power_w")
        return (0, -(v or 0)) if v is not None else (1, 0)
    if mode == SORT_FEE:
        v = outlet.get("fee")
        return (0, -(v or 0.0)) if v is not None else (1, 0)
    if mode == SORT_DURATION:
        v = outlet.get("used_min")
        return (0, -(v or 0)) if v is not None else (1, 0)
    # SORT_SERIAL（默认）
    return (0, outlet.get("serial", 0))

def sorted_outlets(outlets, mode):
    return sorted(outlets, key=lambda o: _sort_key(o, mode))


# ══════════════════════════════════════════════════════════
#  插座行（含详情 chips）
# ══════════════════════════════════════════════════════════
class OutletRow(QWidget):
    H = 40   # 略高一点，容纳 chips

    def __init__(self, outlet, parent=None):
        super().__init__(parent)
        self.o = outlet
        self.setFixedHeight(self.H)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # ── 格式化辅助 ────────────────────────────────────────
    @staticmethod
    def _fmt_min(m):
        if m < 60:
            return f"{m}分"
        h, mn = divmod(m, 60)
        return f"{h}h{mn:02d}m" if mn else f"{h}h"

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h  = self.width(), self.height()
        o     = self.o
        sc    = STATUS_COLOR.get(o["status"], C_GREY)
        busy  = o["status"] == 2

        # 行背景
        bg = QPainterPath()
        bg.addRoundedRect(QRectF(0, 3, w, h - 6), 8, 8)
        p.fillPath(bg, ac(sc, 20))

        # 左彩条
        bar = QPainterPath()
        bar.addRoundedRect(QRectF(0, 5, 3, h - 10), 1.5, 1.5)
        p.fillPath(bar, sc)

        # 插座序号
        p.setPen(C_WHITE)
        p.setFont(QFont("Arial", 11, QFont.Medium))
        p.drawText(QRect(13, 0, 60, h), Qt.AlignVCenter, f"插座{o['serial']}")

        if busy and any(o.get(k) is not None for k in ("power_w", "fee", "used_min")):
            # ── 占用 + 有详情：显示 chips ─────────────────
            chips = []
            if o.get("power_w") is not None:
                chips.append((f"{o['power_w']}W", C_BLUE))
            if o.get("fee") is not None:
                chips.append((f"¥{o['fee']:.2f}", C_GREEN))
            if o.get("used_min") is not None:
                chips.append((self._fmt_min(o["used_min"]), C_PURPLE))

            p.setFont(QFont("Arial", 9, QFont.Bold))
            chip_h = 16
            chip_y = (h - chip_h) // 2
            cx     = 80   # 从此 x 开始排列 chips
            gap    = 5

            for txt, cc in chips:
                fm  = p.fontMetrics()
                cw  = fm.horizontalAdvance(txt) + 10
                cp  = QPainterPath()
                cp.addRoundedRect(QRectF(cx, chip_y, cw, chip_h), chip_h / 2, chip_h / 2)
                p.fillPath(cp, ac(cc, 30))
                p.setPen(ac(cc, 220))
                p.drawText(QRect(cx, chip_y, cw, chip_h), Qt.AlignCenter, txt)
                cx += cw + gap

            # 状态标签（右对齐）
            p.setPen(ac(sc, 200))
            p.setFont(QFont("Arial", 10, QFont.Bold))
            p.drawText(QRect(0, 0, w - 12, h),
                       Qt.AlignVCenter | Qt.AlignRight,
                       STATUS_LABEL.get(o["status"], ""))
        else:
            # ── 空闲 / 损坏 / 无详情：简洁显示 ──────────
            p.setPen(ac(sc, 220))
            p.setFont(QFont("Arial", 11, QFont.Bold))
            p.drawText(QRect(0, 0, w - 12, h),
                       Qt.AlignVCenter | Qt.AlignRight,
                       STATUS_LABEL.get(o["status"], "未知"))


# ══════════════════════════════════════════════════════════
#  站点卡片（字号自适应单行标题）
# ══════════════════════════════════════════════════════════
class StationCard(QWidget):
    TITLE_H  = 38
    FONT_MAX = 12
    FONT_MIN = 8

    def __init__(self, name, outlets, card_w,
                 sort_mode: int, parent=None):
        super().__init__(parent)
        self.name      = name
        self._card_w   = card_w
        self._sort     = sort_mode
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._set_outlets(outlets)

    def _set_outlets(self, outlets):
        self.outlets = sorted_outlets(outlets, self._sort)
        # 清除旧行
        for row in self.findChildren(OutletRow):
            row.deleteLater()
        n      = max(len(self.outlets), 1)
        rows_h = OutletRow.H * n + ROW_GAP * (n - 1)
        self.setFixedHeight(self.TITLE_H + 4 + rows_h + PAD)
        self._place_rows()

    def _place_rows(self):
        y       = self.TITLE_H + 4
        inner_w = self._card_w - PAD * 2
        for o in self.outlets:
            row = OutletRow(o, self)
            row.setGeometry(PAD, y, inner_w, OutletRow.H)
            row.show()
            y += OutletRow.H + ROW_GAP

    def resizeEvent(self, _):
        y = self.TITLE_H + 4
        for row in self.findChildren(OutletRow):
            row.setGeometry(PAD, y, self.width() - PAD * 2, OutletRow.H)
            y += OutletRow.H + ROW_GAP

    def _fit_font(self, text_w):
        for size in range(self.FONT_MAX, self.FONT_MIN - 1, -1):
            fm = QFontMetrics(QFont("Arial", size, QFont.Bold))
            if fm.horizontalAdvance(self.name) <= text_w:
                return size
        return self.FONT_MIN

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        th   = self.TITLE_H

        # 卡片背景
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 13, 13)
        p.fillPath(path, C_CARD)
        p.setPen(QPen(ac(C_SEP, 80), 0.8))
        p.drawPath(path)

        # badge
        fn  = sum(1 for o in self.outlets if o["status"] == 1)
        tot = len(self.outlets)
        sc  = C_GREEN if fn > 0 else C_RED
        p.setFont(QFont("Arial", 10, QFont.Bold))
        badge_txt = f" {fn}/{tot} "
        fm  = p.fontMetrics()
        bw  = fm.horizontalAdvance(badge_txt) + 10
        bh  = 20
        bx  = w - PAD - bw
        by  = (th - bh) // 2
        bp  = QPainterPath()
        bp.addRoundedRect(QRectF(bx, by, bw, bh), bh/2, bh/2)
        p.fillPath(bp, ac(sc, 38))
        p.setPen(ac(sc, 230))
        p.drawText(QRect(int(bx), int(by), int(bw), int(bh)), Qt.AlignCenter, badge_txt)

        # 站点名（字号自适应）
        text_w = int(bx) - PAD - 6
        p.setPen(ac(C_WHITE, 215))
        p.setFont(QFont("Arial", self._fit_font(text_w), QFont.Bold))
        p.drawText(QRect(PAD, 0, text_w, th), Qt.AlignVCenter | Qt.AlignLeft, self.name)

        # 分隔线
        p.setPen(QPen(ac(C_WHITE, 13), 1))
        p.drawLine(PAD, th, w - PAD, th)

        if not self.outlets:
            p.setPen(ac(C_GREY, 120))
            p.setFont(QFont("Arial", 10))
            p.drawText(QRect(PAD, th, w - PAD*2, h - th), Qt.AlignVCenter, "获取数据失败")


# ══════════════════════════════════════════════════════════
#  排序按钮（分段选择器风格）
# ══════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════
#  图标资源接口（Qt Resource System）
#
#  使用步骤：
#  1. 准备 PNG 图标（建议 32×32 或 48×48，背景透明）
#  2. 编写 icons.qrc，例如：
#
#       <!DOCTYPE RCC>
#       <RCC version="1.0">
#         <qresource prefix="/icons">
#           <file>sort_widget.png</file>
#           <file>sort_serial.png</file>
#           <file>sort_power.png</file>
#           <file>sort_fee.png</file>
#           <file>sort_duration.png</file>
#         </qresource>
#       </RCC>
#
#  3. 编译：pyrcc5 icons.qrc -o icons_rc.py
#  4. 在本文件顶部取消注释：import icons_rc
#
#  图标路径格式：":/icons/文件名.png"
#  留空字符串 "" 时自动回退到文字符号显示。
# ══════════════════════════════════════════════════════════

import icons_rc   # ← 编译好 icons_rc.py 后取消此行注释

# 排序控件左侧的功能图标路径（表示"这是排序控件"）
SORT_WIDGET_ICON_PATH = ":/icons/sort_widget.png"          # 例：":/icons/sort_widget.png"

# 各排序模式的图标路径
SORT_ICON_PATH = {
    SORT_SERIAL:   ":/icons/sort_serial.png",              # 例：":/icons/sort_serial.png"
    SORT_POWER:    ":/icons/sort_power.png",              # 例：":/icons/sort_power.png"
    SORT_FEE:      ":/icons/sort_fee.png",              # 例：":/icons/sort_fee.png"
    SORT_DURATION: ":/icons/sort_duration.png",              # 例：":/icons/sort_duration.png"
}

# 文字回退符号（路径为空时使用）
SORT_ICON_FALLBACK = {
    SORT_SERIAL:   "№",
    SORT_POWER:    "W",
    SORT_FEE:      "¥",
    SORT_DURATION: "T",
}

def _path_to_pixmap(path, size=16):
    """从资源路径加载 QPixmap，失败或路径为空返回 None。"""
    if not path:
        return None
    pm = QPixmap(path)
    if pm.isNull():
        return None
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

# 图标在 QApplication 创建后才能加载，这里只占位
# DynamicIsland.__init__ 会调用 _ensure_pixmaps_loaded() 完成实际加载
_SORT_PIXMAPS        = {}
_SORT_WIDGET_PIXMAP  = None
_PIXMAPS_LOADED      = False

def _ensure_pixmaps_loaded():
    """在 QApplication 存在后调用一次，安全加载所有图标。"""
    global _SORT_WIDGET_PIXMAP, _PIXMAPS_LOADED
    if _PIXMAPS_LOADED:
        return
    _PIXMAPS_LOADED = True
    for mode, path in SORT_ICON_PATH.items():
        _SORT_PIXMAPS[mode] = _path_to_pixmap(path, size=28)
    _SORT_WIDGET_PIXMAP = _path_to_pixmap(SORT_WIDGET_ICON_PATH, size=20)

class SortButton(QWidget):
    """胶囊按钮，点击弹出菜单选择排序方式。"""
    H        = 32
    ICON_SZ  = 28   # 图标尺寸
    PAD_H    = 10   # 水平内边距

    def __init__(self, parent=None, on_change=None):
        super().__init__(parent)
        self._mode     = SORT_SERIAL
        self._hover    = False
        self._callback = on_change
        self.setFixedSize(110, self.H)
        self.setCursor(Qt.PointingHandCursor)

    def mode(self):
        return self._mode

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._show_menu(e.globalPos())

    def _show_menu(self, pos):
        menu = QMenu(self)
        menu.setWindowFlags(
            menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        )
        menu.setAttribute(Qt.WA_TranslucentBackground)
        menu.setStyleSheet("""
            QMenu {
                background: rgba(28,28,30,252);
                border: 1px solid rgba(255,255,255,0.13);
                border-radius: 12px;
                padding: 5px 0;
                color: white;
                font-size: 13px;
            }
            QMenu::item {
                padding: 9px 20px 9px 14px;
                border-radius: 7px;
                margin: 1px 5px;
            }
            QMenu::item:selected { background: rgba(255,255,255,0.11); }
        """)
        for mode, (short, full) in SORT_LABELS.items():
            checked = "  ✓" if mode == self._mode else ""
            label   = "{}{}".format(full, checked)
            pm      = _SORT_PIXMAPS.get(mode)
            if pm and not pm.isNull():
                act = QAction(QIcon(pm), label, self)
            else:
                fb  = SORT_ICON_FALLBACK[mode]
                act = QAction("{}  {}".format(fb, label), self)
            act.triggered.connect(lambda _, m=mode: self._set_mode(m))
            menu.addAction(act)
        menu.exec_(pos)

    def _set_mode(self, mode):
        self._mode = mode
        self.update()
        if self._callback:
            self._callback(mode)

    def enterEvent(self, _):
        self._hover = True;  self.update()
    def leaveEvent(self, _):
        self._hover = False; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h  = self.width(), self.height()
        icsz  = self.ICON_SZ
        padh  = self.PAD_H
        iy    = (h - icsz) // 2   # 图标垂直居中 y

        # 背景：与搜索栏一致的深黑色
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), h/2, h/2)
        bg_alpha = int(0.85 * 255) if self._hover else int(0.75 * 255)
        p.fillPath(path, QColor(0, 0, 0, bg_alpha))
        p.setPen(QPen(QColor(255, 255, 255, 46), 1))
        p.drawPath(path)

        p.setFont(QFont("Arial", 11, QFont.Medium))
        p.setPen(ac(C_WHITE, 210))
        fm   = p.fontMetrics()
        cx   = padh  # 当前绘制 x 光标

        # ── 排序项图标（可选）+ 短标签 + 下拉箭头 ────────
        short = SORT_LABELS[self._mode][0]
        pm    = _SORT_PIXMAPS.get(self._mode)
        if pm and not pm.isNull():
            p.setOpacity(210 / 255)
            p.drawPixmap(cx, iy, pm)
            p.setOpacity(1.0)
            cx += icsz + 4
            lbl = "{} ".format(short)
        else:
            fb  = SORT_ICON_FALLBACK[self._mode]
            lbl = "{}  {} ".format(fb, short)

        lbl_w = fm.horizontalAdvance(lbl)
        p.drawText(QRect(cx, 0, lbl_w + 2, h), Qt.AlignVCenter, lbl)


# ══════════════════════════════════════════════════════════
#  灵动岛主窗口
# ══════════════════════════════════════════════════════════
class DynamicIsland(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        # 图标懒加载（QApplication 已存在，此时安全）
        _ensure_pixmaps_loaded()

        # 数据 & UI 状态
        self._data:      dict  = {}
        self._filtered:  dict  = {}
        self._expanded:  bool  = False
        self._hover:     bool  = False
        self._phase:     float = 0.0
        self._sort_mode   = SORT_SERIAL

        # 拖动
        self._drag_mode:  bool          = False
        self._dragging:   bool          = False
        self._drag_start = None  # type: Optional[QPoint]

        # 脉冲
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._on_pulse)
        self._pulse_timer.start(33)

        # ── 搜索栏 ──────────────────────────────────────────
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("搜索站点名称…")
        self._search.setFixedHeight(SEARCH_H)
        self._search.setStyleSheet("""
            QLineEdit {
                background: rgba(0,0,0,0.75);
                border: 1px solid rgba(255,255,255,0.18);
                border-radius: 11px;
                color: rgba(255,255,255,0.95);
                font-size: 14px;
                padding: 0 14px;
                selection-background-color: rgba(10,132,255,0.5);
            }
            QLineEdit:focus {
                border: 1px solid rgba(10,132,255,0.80);
                background: rgba(0,0,0,0.85);
            }
        """)
        self._search.textChanged.connect(self._on_search)
        self._search.hide()

        # ── 工具栏：计数标签 + 排序按钮 ────────────────────
        self._count_lbl = QLabel(self)
        self._count_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._count_lbl.setStyleSheet(
            "color: rgba(0,0,0,0.82); font-size: 18px; font-weight: 600; background: transparent;"
        )
        self._count_lbl.hide()

        self._sort_btn = SortButton(self, on_change=self._on_sort_change)
        self._sort_btn.hide()

        # sort_widget icon：独立 QLabel，不在黑色胶囊内
        self._sort_widget_lbl = QLabel(self)
        self._sort_widget_lbl.setFixedSize(32, 32)
        self._sort_widget_lbl.setAlignment(Qt.AlignCenter)
        self._sort_widget_lbl.setStyleSheet("background: transparent;")
        self._sort_widget_lbl.hide()

        # ── 滚动区 ──────────────────────────────────────────
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea, QScrollArea > QWidget > QWidget {
                background: transparent; border: none;
            }
            QScrollBar:vertical { width: 4px; background: transparent; }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.20);
                border-radius: 2px; min-height: 20px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
        """)
        self._scroll.hide()
        self._apply_size()

    # ──────────────────────────────────────────────────────
    #  公开接口
    # ──────────────────────────────────────────────────────
    def update_data(self, data):
        self._data = data
        self._apply_filter()
        self.update(0, 0, ISLAND_W, CAPSULE_H)

    # ──────────────────────────────────────────────────────
    #  搜索 & 排序
    # ──────────────────────────────────────────────────────
    def _on_search(self, _=None):
        self._apply_filter()

    def _on_sort_change(self, mode):
        self._sort_mode = mode
        self._rebuild_scroll()

    def _apply_filter(self):
        kw = self._search.text().strip().lower()
        self._filtered = (
            {k: v for k, v in self._data.items() if kw in k.lower()}
            if kw else dict(self._data)
        )
        self._update_toolbar()
        if self._expanded:
            self._rebuild_scroll()

    def _update_toolbar(self):
        total = len(self._data)
        shown = len(self._filtered)
        kw    = self._search.text().strip()
        self._count_lbl.setText(
            f"  {shown} / {total} 个站点" if kw else f"  共 {total} 个站点"
        )

    # ──────────────────────────────────────────────────────
    #  尺寸 & 子控件布局
    # ──────────────────────────────────────────────────────
    def _apply_size(self):
        if self._expanded:
            self.setFixedSize(ISLAND_W, PANEL_Y + EXPANDED_H)

            ix, iw = PAD, ISLAND_W - PAD * 2

            # 搜索栏
            self._search.setGeometry(ix, PANEL_Y + SEARCH_TOP, iw, SEARCH_H)
            self._search.show()

            # 工具栏（计数标签 | sort_widget图标 + 排序按钮）
            tb_y    = PANEL_Y + SEARCH_TOP + SEARCH_H + 6
            btn_w   = self._sort_btn.width()
            btn_h   = self._sort_btn.H    # 32px
            wi_sz   = 32                  # sort_widget icon 尺寸
            wi_gap  = 4                   # icon 与 sort_btn 间距
            # 右侧整体宽度：widget_icon + gap + sort_btn
            right_w = wi_sz + wi_gap + btn_w
            # 计数标签占剩余左侧空间
            self._count_lbl.setGeometry(ix, tb_y, iw - right_w - 8, TOOLBAR_H)
            self._count_lbl.show()
            # sort_widget icon（垂直居中于工具栏行）
            wi_x = ix + iw - right_w
            wi_y = tb_y + (TOOLBAR_H - wi_sz) // 2
            self._sort_widget_lbl.setGeometry(wi_x, wi_y, wi_sz, wi_sz)
            # 更新图标（每次展开时刷新，防止懒加载后首次为空）
            wpm = _SORT_WIDGET_PIXMAP
            if wpm and not wpm.isNull():
                self._sort_widget_lbl.setPixmap(wpm)
            else:
                self._sort_widget_lbl.clear()
            self._sort_widget_lbl.show()
            # sort_btn 紧跟 widget icon 右侧，垂直居中
            btn_y = tb_y + (TOOLBAR_H - btn_h) // 2
            self._sort_btn.setGeometry(wi_x + wi_sz + wi_gap, btn_y, btn_w, btn_h)
            self._sort_btn.show()
            self._update_toolbar()

            # 滚动区
            scroll_y = PANEL_Y + SCROLL_TOP
            self._scroll.setGeometry(0, scroll_y, ISLAND_W, EXPANDED_H - SCROLL_TOP - 8)
            self._scroll.show()
            self._rebuild_scroll()
        else:
            self.setFixedSize(ISLAND_W, CAPSULE_H)
            self._search.hide()
            self._count_lbl.hide()
            self._sort_widget_lbl.hide()
            self._sort_btn.hide()
            self._scroll.hide()

    # ──────────────────────────────────────────────────────
    #  滚动内容
    # ──────────────────────────────────────────────────────
    def _rebuild_scroll(self):
        card_w    = ISLAND_W - PAD * 2
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        y = PAD

        if not self._filtered:
            lbl = QLabel("无匹配站点", container)
            lbl.setStyleSheet(
                "color: rgba(255,255,255,0.28); font-size: 13px; background: transparent;"
            )
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setGeometry(0, 16, ISLAND_W, 32)
            container.setFixedSize(ISLAND_W, 60)
            self._scroll.setWidget(container)
            return

        for name, outlets in self._filtered.items():
            card = StationCard(name, outlets, card_w, self._sort_mode, container)
            card.setGeometry(PAD, y, card_w, card.height())
            y += card.height() + CARD_GAP

        container.setFixedSize(ISLAND_W, y)
        self._scroll.setWidget(container)

    # ──────────────────────────────────────────────────────
    #  胶囊状态
    # ──────────────────────────────────────────────────────
    def _calc(self):
        fn  = sum(o["status"] == 1 for outs in self._data.values() for o in outs)
        tot = sum(len(outs) for outs in self._data.values())
        return fn > 0, fn, tot

    def _on_pulse(self):
        self._phase = (self._phase + 0.07) % (2 * math.pi)
        self.update(0, 0, ISLAND_W, CAPSULE_H)

    # ──────────────────────────────────────────────────────
    #  绘制
    # ──────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self._draw_capsule(p)
        if self._expanded:
            self._draw_panel_bg(p)

    def _draw_capsule(self, p):
        w, h = ISLAND_W, CAPSULE_H
        r    = h / 2
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), r, r)

        if self._drag_mode:
            p.setOpacity(0.70)

        p.fillPath(path, C_ISL_H if (self._hover and not self._drag_mode) else C_ISL)

        gl = QLinearGradient(0, 0, 0, h * 0.55)
        gl.setColorAt(0, ac(C_WHITE, 22))
        gl.setColorAt(1, ac(C_WHITE, 0))
        p.fillPath(path, gl)

        p.setPen(QPen(ac(C_BLUE, 200) if self._drag_mode else ac(C_SEP, 130),
                      1.5 if self._drag_mode else 0.8))
        p.drawPath(path)
        p.setOpacity(1.0)

        if self._drag_mode:
            p.setPen(ac(C_BLUE, 230))
            p.setFont(QFont("Arial", 11, QFont.Medium))
            p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, "✥  拖动模式  —  右键退出")
            return

        any_free, fn, tot = self._calc()
        if tot == 0:
            p.setPen(ac(C_GREY, 180))
            p.setFont(QFont("Arial", 11))
            p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, "正在获取数据…")
            return

        sc    = C_GREEN if any_free else C_RED
        pulse = (math.sin(self._phase) + 1) / 2
        cx, cy = 24, h // 2

        gr = int(8 + pulse * 4)
        p.setBrush(ac(sc, int(60 - pulse * 30)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - gr, cy - gr, gr * 2, gr * 2)
        p.setBrush(sc)
        p.drawEllipse(cx - 5, cy - 5, 10, 10)

        p.setPen(C_WHITE)
        p.setFont(QFont("Arial", 12, QFont.Medium))
        p.drawText(QRect(40, 0, 160, h), Qt.AlignVCenter | Qt.AlignLeft,
                   "有空闲插座" if any_free else "全部占用")

        p.setPen(ac(sc, 215))
        p.setFont(QFont("Arial", 10, QFont.Bold))
        p.drawText(QRect(0, 0, w - 26, h), Qt.AlignVCenter | Qt.AlignRight, f"{fn}/{tot}")

        p.setPen(ac(C_DARK, 210))
        p.setFont(QFont("Arial", 8))
        p.drawText(QRect(0, 0, w - 10, h), Qt.AlignVCenter | Qt.AlignRight,
                   "▲" if self._expanded else "▼")

    def _draw_panel_bg(self, p):
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, PANEL_Y, ISLAND_W, EXPANDED_H), 22, 22)
        p.fillPath(path, C_ISL)

        gl = QLinearGradient(0, PANEL_Y, 0, PANEL_Y + 44)
        gl.setColorAt(0, ac(C_WHITE, 14))
        gl.setColorAt(1, ac(C_WHITE, 0))
        p.fillPath(path, gl)

        p.setPen(QPen(ac(C_SEP, 110), 0.8))
        p.drawPath(path)

    # ──────────────────────────────────────────────────────
    #  右键菜单
    # ──────────────────────────────────────────────────────
    def _show_context_menu(self, global_pos):
        menu = QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint |
                            Qt.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        menu.setStyleSheet("""
            QMenu {
                background: rgba(30,30,32,245);
                border: 1px solid rgba(255,255,255,0.13);
                border-radius: 12px;
                padding: 5px 0;
                color: white; font-size: 13px;
            }
            QMenu::item {
                padding: 9px 22px 9px 16px;
                border-radius: 7px; margin: 1px 5px;
            }
            QMenu::item:selected { background: rgba(255,255,255,0.11); }
            QMenu::separator {
                height: 1px; background: rgba(255,255,255,0.10);
                margin: 4px 12px;
            }
        """)

        if self._drag_mode:
            a = QAction("  ✓  退出拖动模式", self)
            a.triggered.connect(self._exit_drag_mode)
        else:
            a = QAction("  ✥  拖动模式", self)
            a.triggered.connect(self._enter_drag_mode)
        menu.addAction(a)
        menu.addSeparator()
        q = QAction("  ✕  关闭", self)
        q.triggered.connect(QApplication.instance().quit)
        menu.addAction(q)
        menu.exec_(global_pos)

    # ──────────────────────────────────────────────────────
    #  拖动模式
    # ──────────────────────────────────────────────────────
    def _enter_drag_mode(self):
        self._drag_mode = True
        if self._expanded:
            self._expanded = False
            self._search.clear()
            self._apply_size()
        self.setCursor(Qt.SizeAllCursor)
        self.update()

    def _exit_drag_mode(self):
        self._drag_mode  = False
        self._dragging   = False
        self._drag_start = None
        self.setCursor(Qt.ArrowCursor)
        self.update()

    # ──────────────────────────────────────────────────────
    #  鼠标事件
    # ──────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        in_capsule = e.pos().y() <= CAPSULE_H
        if e.button() == Qt.RightButton and in_capsule:
            self._show_context_menu(e.globalPos())
            return
        if e.button() == Qt.LeftButton:
            if self._drag_mode:
                self._dragging   = True
                self._drag_start = e.globalPos() - self.frameGeometry().topLeft()
            elif in_capsule:
                self._expanded = not self._expanded
                if not self._expanded:
                    self._search.clear()
                self._apply_size()
                self.update()
            else:
                self._dragging   = True
                self._drag_start = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._dragging and self._drag_start and e.buttons() & Qt.LeftButton:
            self.move(e.globalPos() - self._drag_start)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragging   = False
            self._drag_start = None

    def enterEvent(self, _):
        self._hover = True
        self.update(0, 0, ISLAND_W, CAPSULE_H)

    def leaveEvent(self, _):
        self._hover = False
        self.update(0, 0, ISLAND_W, CAPSULE_H)
