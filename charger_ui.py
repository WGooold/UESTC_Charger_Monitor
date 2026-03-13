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
from PyQt5.QtCore import Qt, QTimer, QRect, QRectF, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal, pyqtProperty
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
#  插座行（含详情 chips + 左滑"我的插座"功能）
# ══════════════════════════════════════════════════════════
class OutletRow(QWidget):
    H          = 40
    BTN_W      = 88    # "我的插座"按钮宽度
    ANIM_MS    = 300   # 动画时长（ms）

    # 信号：用户点击了"我的插座"按钮，传出 outlet 数据
    my_outlet_clicked = pyqtSignal(dict)

    def __init__(self, outlet, parent=None):
        super().__init__(parent)
        self.o        = outlet
        self._slid    = False   # 是否已滑开
        self._slide_x = 0       # 当前内容区滑动偏移（0=正常, 负=向左滑）
        self.setFixedHeight(self.H)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor if outlet.get("status") == 2 else Qt.ArrowCursor)

        # "我的插座"按钮（初始在右侧隐藏区域外）
        self._btn = QPushButton("⚡ 我的插座", self)
        self._btn.setFixedSize(self.BTN_W, self.H - 10)
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setStyleSheet("""
            QPushButton {
                background: rgba(10, 10, 12, 0.92);
                color: rgb(48, 209, 88);
                font-size: 12px;
                font-weight: 800;
                border: 1.5px solid rgba(48, 209, 88, 0.85);
                border-radius: 8px;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: rgba(48, 209, 88, 0.18);
                border: 1.5px solid rgba(48, 209, 88, 1.0);
                color: rgb(80, 230, 110);
            }
            QPushButton:pressed {
                background: rgba(48, 209, 88, 0.30);
            }
        """)
        self._btn.move(self.width(), 5)   # 初始隐藏在右侧外
        self._btn.clicked.connect(self._on_my_outlet)
        self._btn.hide()

        # 滑动动画控制器（用整数属性驱动）
        self._anim = QPropertyAnimation(self, b"slide_offset")
        self._anim.setDuration(self.ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    # ── Qt property：slide_offset ─────────────────────────
    def _get_slide_offset(self):
        return self._slide_x

    def _set_slide_offset(self, val):
        self._slide_x = val
        # 同步按钮位置：从右边滑入
        btn_x = self.width() - self.BTN_W - 4 + (self.BTN_W + 4) + self._slide_x
        # _slide_x 从 0 到 -(BTN_W+4)，按钮从 width() 移到 width()-BTN_W-4
        self._btn.move(int(btn_x), 5)
        self.update()

    slide_offset = pyqtProperty(int, _get_slide_offset, _set_slide_offset)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # 保持按钮竖向居中，宽度固定
        if self._slid:
            self._btn.move(self.width() - self.BTN_W - 4, 5)
        else:
            self._btn.move(self.width(), 5)

    # ── 格式化辅助 ────────────────────────────────────────
    @staticmethod
    def _fmt_min(m):
        if m < 60:
            return f"{m}分"
        h, mn = divmod(m, 60)
        return f"{h}h{mn:02d}m" if mn else f"{h}h"

    # ── 点击逻辑 ─────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.o.get("status") == 2:
            if self._slid:
                self._slide_back()
            else:
                self._slide_open()

    def _slide_open(self):
        self._slid = True
        self._btn.show()
        target = -(self.BTN_W + 8)
        self._anim.stop()
        self._anim.setStartValue(self._slide_x)
        self._anim.setEndValue(target)
        self._anim.start()

    def _slide_back(self):
        self._anim.stop()
        self._anim.setStartValue(self._slide_x)
        self._anim.setEndValue(0)
        self._anim.finished.connect(self._on_slide_back_done)
        self._anim.start()

    def _on_slide_back_done(self):
        self._anim.finished.disconnect(self._on_slide_back_done)
        self._slid = False
        self._btn.hide()

    def _on_my_outlet(self):
        self.my_outlet_clicked.emit(self.o)

    # ── 绘制 ─────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h  = self.width(), self.height()
        o     = self.o
        sc    = STATUS_COLOR.get(o["status"], C_GREY)
        busy  = o["status"] == 2
        ox    = self._slide_x   # 内容水平偏移

        # 行背景（固定，不随偏移移动）
        bg = QPainterPath()
        bg.addRoundedRect(QRectF(0, 3, w, h - 6), 8, 8)
        p.fillPath(bg, ac(sc, 20))

        # 裁剪：内容区不超出行边界
        p.setClipRect(QRect(0, 0, w, h))

        # 左彩条（随偏移）
        bar = QPainterPath()
        bar.addRoundedRect(QRectF(ox, 5, 3, h - 10), 1.5, 1.5)
        p.fillPath(bar, sc)

        # 插座序号（始终可见，不随偏移）
        p.setPen(C_WHITE)
        p.setFont(QFont("Arial", 11, QFont.Medium))
        p.drawText(QRect(13, 0, 65, h), Qt.AlignVCenter, f"插座{o['serial']}")

        # 淡出系数：ox 从 0 → -(BTN_W+8)，内容随滑动线性淡出
        slide_target = -(self.BTN_W + 8)
        fade = max(0.0, min(1.0, 1.0 - ox / slide_target)) if slide_target != 0 else 1.0

        if busy and any(o.get(k) is not None for k in ("power_w", "fee", "used_min")):
            # ── 占用 + 有详情：chips 随偏移滑动并淡出 ────
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
            cx     = 80 + ox
            gap    = 5

            for txt, cc in chips:
                fm  = p.fontMetrics()
                cw  = fm.horizontalAdvance(txt) + 10
                cp  = QPainterPath()
                cp.addRoundedRect(QRectF(cx, chip_y, cw, chip_h), chip_h / 2, chip_h / 2)
                p.fillPath(cp, ac(cc, int(30 * fade)))
                p.setPen(ac(cc, int(220 * fade)))
                p.drawText(QRect(int(cx), chip_y, cw, chip_h), Qt.AlignCenter, txt)
                cx += cw + gap

            # 状态标签（随偏移淡出）
            p.setPen(ac(sc, int(200 * fade)))
            p.setFont(QFont("Arial", 10, QFont.Bold))
            p.drawText(QRect(ox, 0, w - 12, h),
                       Qt.AlignVCenter | Qt.AlignRight,
                       STATUS_LABEL.get(o["status"], ""))
        else:
            # ── 空闲 / 损坏 / 无详情（淡出）─────────────
            p.setPen(ac(sc, int(220 * fade)))
            p.setFont(QFont("Arial", 11, QFont.Bold))
            p.drawText(QRect(ox, 0, w - 12, h),
                       Qt.AlignVCenter | Qt.AlignRight,
                       STATUS_LABEL.get(o["status"], "未知"))

        p.setClipping(False)


# ══════════════════════════════════════════════════════════
#  站点卡片（字号自适应单行标题）
# ══════════════════════════════════════════════════════════
class StationCard(QWidget):
    TITLE_H  = 38
    FONT_MAX = 12
    FONT_MIN = 8

    my_outlet_clicked = pyqtSignal(dict)   # 向上冒泡给 DynamicIsland

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
            # 将"我的插座"信号向上冒泡到 StationCard
            row.my_outlet_clicked.connect(self.my_outlet_clicked)
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

# 充电监控模式胶囊左侧图标（表示充电中，如闪电图标）
# 留空则显示文字"⚡"作为回退
CHARGE_ICON_PATH = ""   # 例：":/icons/charge.png"

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

_CHARGE_PIXMAP = None

def _ensure_pixmaps_loaded():
    """在 QApplication 存在后调用一次，安全加载所有图标。"""
    global _SORT_WIDGET_PIXMAP, _PIXMAPS_LOADED, _CHARGE_PIXMAP
    if _PIXMAPS_LOADED:
        return
    _PIXMAPS_LOADED = True
    for mode, path in SORT_ICON_PATH.items():
        _SORT_PIXMAPS[mode] = _path_to_pixmap(path, size=28)
    _SORT_WIDGET_PIXMAP = _path_to_pixmap(SORT_WIDGET_ICON_PATH, size=20)
    _CHARGE_PIXMAP      = _path_to_pixmap(CHARGE_ICON_PATH, size=24)

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
        self._data       = {}
        self._filtered   = {}
        self._expanded   = False
        self._hover      = False
        self._phase      = 0.0
        self._sort_mode  = SORT_SERIAL

        # ── 充电模式状态 ──────────────────────────────────
        self._charging       = False    # 是否处于充电监控模式
        self._charge_outlet  = None     # 正在监控的 outlet dict
        self._charge_done    = False    # 是否已充电完成
        self._charge_phase   = 0.0     # 充电动画相位
        self._charge_anim_on = True     # 动态扫光效果开关

        # 拖动
        self._drag_mode  = False
        self._dragging   = False
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
        # 充电模式：用新数据更新当前监控插座
        if self._charging and self._charge_outlet:
            outlet_no = self._charge_outlet.get("outletNo")
            for outlets in data.values():
                for o in outlets:
                    if o.get("outletNo") == outlet_no:
                        self._charge_outlet = o
                        # 插座不再占用 → 充电完成
                        if o.get("status") != 2 and not self._charge_done:
                            self._charge_done = True
                        break
        self.update(0, 0, ISLAND_W, CAPSULE_H)

    def _on_my_outlet_clicked(self, outlet):
        """用户点击了'我的插座'按钮，进入充电监控模式。"""
        self._charging      = True
        self._charge_outlet = dict(outlet)
        self._charge_done   = False
        self._charge_phase  = 0.0
        # 收起面板
        if self._expanded:
            self._expanded = False
            self._search.clear()
            self._apply_size()
        self.update()

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
            card.my_outlet_clicked.connect(self._on_my_outlet_clicked)
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
        if self._charging and self._charge_anim_on:
            # 流光用线性推进，0.0→1.0 循环，每帧 +0.018（约 1.7s 一个周期）
            self._charge_phase = (self._charge_phase + 0.018) % 1.0
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

        # 充电模式：绿色边框脉冲
        if self._charging and not self._drag_mode:
            pulse = (math.sin(self._charge_phase) + 1) / 2
            border_alpha = int(120 + pulse * 135)
            p.setPen(QPen(ac(C_GREEN, border_alpha), 1.8))
        else:
            p.setPen(QPen(ac(C_BLUE, 200) if self._drag_mode else ac(C_SEP, 130),
                          1.5 if self._drag_mode else 0.8))
        p.drawPath(path)
        p.setOpacity(1.0)

        if self._drag_mode:
            p.setPen(ac(C_BLUE, 230))
            p.setFont(QFont("Arial", 11, QFont.Medium))
            p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, "✥  拖动模式  —  右键退出")
            return

        # ── 充电完成提示 ───────────────────────────────────
        if self._charging and self._charge_done:
            p.setPen(C_GREEN)
            p.setFont(QFont("Arial", 16, QFont.Bold))
            p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, "充电完成")
            return

        # ── 充电监控模式胶囊 ───────────────────────────────
        if self._charging and self._charge_outlet:
            self._draw_charging_capsule(p, w, h)
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

    def _draw_charging_capsule(self, p, w, h):
        """充电监控模式下的胶囊内容：充电图标 + 方形光斑扫光 + 功率 / 费用 / 时长。"""
        o = self._charge_outlet
        t = self._charge_phase   # 0.0 → 1.0 线性推进

        # ══ 方形光斑扫光 ════════════════════════════════════
        if self._charge_anim_on:
            spot_w = 100.0
            span   = w + spot_w
            x0     = t * span - spot_w

            gl = QLinearGradient(x0, 0, x0 + spot_w, 0)
            gl.setColorAt(0.00, ac(C_GREEN, 0))
            gl.setColorAt(0.25, ac(C_GREEN, 50))
            gl.setColorAt(0.50, ac(C_GREEN, 70))
            gl.setColorAt(0.75, ac(C_GREEN, 50))
            gl.setColorAt(1.00, ac(C_GREEN, 0))

            # 用胶囊圆角路径裁剪，防止矩形光斑在两端溢出圆角
            r = h / 2
            cap_path = QPainterPath()
            cap_path.addRoundedRect(QRectF(0, 0, w, h), r, r)
            p.setClipPath(cap_path)
            p.setPen(Qt.NoPen)
            p.setBrush(gl)
            p.drawRect(QRectF(x0, 0, spot_w, h))
            p.setClipping(False)
        # ══ 光斑结束 ════════════════════════════════════════

        # ── 左侧：充电图标（自定义或回退"⚡"文字）────────
        icon_sz = 22
        icon_x  = 10
        icon_y  = (h - icon_sz) // 2

        pm = _CHARGE_PIXMAP
        if pm and not pm.isNull():
            p.setOpacity(1.0)
            p.drawPixmap(icon_x, icon_y, pm)
        else:
            p.setPen(ac(C_GREEN, 230))
            p.setFont(QFont("Arial", 15, QFont.Bold))
            p.drawText(QRect(icon_x, 0, icon_sz, h),
                       Qt.AlignVCenter | Qt.AlignHCenter, "⚡")

        # 插座序号
        serial  = o.get("serial", "?")
        label_x = icon_x + icon_sz + 4
        p.setPen(ac(C_GREEN, 190))
        p.setFont(QFont("Arial", 9))
        p.drawText(QRect(label_x, 0, 28, h), Qt.AlignVCenter, f"#{serial}")

        # 三个数据项
        items = []
        if o.get("power_w") is not None:
            items.append((f"{o['power_w']}W", C_BLUE))
        if o.get("fee") is not None:
            items.append((f"¥{o['fee']:.2f}", C_GREEN))
        if o.get("used_min") is not None:
            mins = o["used_min"]
            if mins < 60:
                tstr = f"{mins}分"
            else:
                hh, mm = divmod(mins, 60)
                tstr = f"{hh}h{mm:02d}m" if mm else f"{hh}h"
            items.append((tstr, C_PURPLE))

        if items:
            p.setFont(QFont("Arial", 11, QFont.Bold))
            # 均匀分布在右侧区域
            area_x  = 66
            area_w  = w - area_x - 12
            item_w  = area_w // len(items)
            for i, (txt, cc) in enumerate(items):
                ix = area_x + i * item_w
                # 小背景 pill
                fm   = p.fontMetrics()
                tw   = fm.horizontalAdvance(txt)
                pill = QPainterPath()
                ph, pw = 20, tw + 12
                px = ix + (item_w - pw) // 2
                py = (h - ph) // 2
                pill.addRoundedRect(QRectF(px, py, pw, ph), ph/2, ph/2)
                p.fillPath(pill, ac(cc, 28))
                p.setPen(ac(cc, 230))
                p.drawText(QRect(px, py, pw, ph), Qt.AlignCenter, txt)
        else:
            # 没有详情数据时
            p.setPen(ac(C_GREY, 180))
            p.setFont(QFont("Arial", 11))
            p.drawText(QRect(66, 0, w - 78, h), Qt.AlignVCenter, "获取充电数据中…")

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
        if self._charging:
            menu.addSeparator()
            ec = QAction("  ⚡  退出充电模式", self)
            ec.triggered.connect(self._exit_charging)
            menu.addAction(ec)
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
    #  充电模式
    # ──────────────────────────────────────────────────────
    def _exit_charging(self):
        self._charging      = False
        self._charge_outlet = None
        self._charge_done   = False
        self.update()

    def _toggle_charge_anim(self):
        self._charge_anim_on = not self._charge_anim_on
        self.update()

    def _show_charging_menu(self, global_pos):
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
        title = QAction("  退出充电监控模式？", self)
        title.setEnabled(False)
        menu.addAction(title)
        menu.addSeparator()
        yes = QAction("  ✓  返回普通模式", self)
        yes.triggered.connect(self._exit_charging)
        menu.addAction(yes)
        no = QAction("  ✕  继续监控", self)
        menu.addAction(no)
        menu.addSeparator()
        anim_label = "  ◎  关闭动态效果" if self._charge_anim_on else "  ◎  开启动态效果"
        anim_act = QAction(anim_label, self)
        anim_act.triggered.connect(self._toggle_charge_anim)
        menu.addAction(anim_act)
        menu.exec_(global_pos)

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
            elif in_capsule and self._charging:
                # 充电模式：弹菜单询问是否返回普通模式
                self._show_charging_menu(e.globalPos())
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
