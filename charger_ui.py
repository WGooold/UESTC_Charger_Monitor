"""
charger_ui.py — 灵动岛充电桩 UI

数据格式（update_data 入参）：
  { "站点名": [ {"serial": int, "status": int}, ... ], ... }

交互逻辑：
  - 左键点击胶囊：展开 / 收起详情面板
  - 胶囊任意状态下右键：弹出菜单（拖动模式 / 关闭）
  - 拖动模式：
      · 进入后胶囊显示蓝色提示，鼠标变十字
      · 按住左键拖动即可移动窗口
      · 松开后仍在拖动模式
      · 右键再次弹出菜单，可选"退出拖动模式"恢复正常
  - 展开面板内：顶部搜索栏过滤站点名，显示匹配数量
"""

import math
from PyQt5.QtWidgets import (
    QWidget, QScrollArea, QFrame, QSizePolicy,
    QMenu, QAction, QLineEdit, QLabel, QApplication
)
from PyQt5.QtCore import Qt, QTimer, QRect, QRectF, QPoint
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QPainterPath,
    QPen, QLinearGradient, QRegion
)

# ══════════════════════════════════════════════════════════
#  颜色 & 布局常量
# ══════════════════════════════════════════════════════════
def ac(color: QColor, alpha: int) -> QColor:
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

STATUS_COLOR = {1: C_GREEN, 2: C_RED, 3: C_YELLOW}
STATUS_LABEL = {1: "空  闲", 2: "占  用", 3: "损  坏"}

ISLAND_W   = 360
CAPSULE_H  = 46
PANEL_GAP  = 10          # 胶囊与展开面板的间距
PANEL_Y    = CAPSULE_H + PANEL_GAP

# 展开面板内部布局
SEARCH_TOP  = 14         # 搜索栏距面板顶部
SEARCH_H    = 42         # 搜索栏高度
COUNT_H     = 28         # 站点计数标签高度
# 滚动区起始 Y（相对于面板顶部），多加 8px 让第一张卡片顶部圆角不被裁切
SCROLL_TOP  = SEARCH_TOP + SEARCH_H + 6 + COUNT_H + 8
EXPANDED_H  = 520        # 展开面板总高度

PAD      = 12
ROW_GAP  = 5
CARD_GAP = 8


# ══════════════════════════════════════════════════════════
#  插座行
# ══════════════════════════════════════════════════════════
class OutletRow(QWidget):
    H = 36

    def __init__(self, outlet: dict, parent=None):
        super().__init__(parent)
        self.o = outlet
        self.setFixedHeight(self.H)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        sc = STATUS_COLOR.get(self.o["status"], C_GREY)

        bg = QPainterPath()
        bg.addRoundedRect(QRectF(0, 3, w, h - 6), 7, 7)
        p.fillPath(bg, ac(sc, 22))

        bar = QPainterPath()
        bar.addRoundedRect(QRectF(0, 5, 3, h - 10), 1.5, 1.5)
        p.fillPath(bar, sc)

        p.setPen(C_WHITE)
        p.setFont(QFont("Arial", 11, QFont.Medium))
        p.drawText(QRect(13, 0, w - 90, h), Qt.AlignVCenter,
                   f"插座 {self.o['serial']}")

        p.setPen(ac(sc, 230))
        p.setFont(QFont("Arial", 11, QFont.Bold))
        p.drawText(QRect(0, 0, w - 12, h),
                   Qt.AlignVCenter | Qt.AlignRight,
                   STATUS_LABEL.get(self.o["status"], "未知"))


# ══════════════════════════════════════════════════════════
#  站点卡片（标题单行，字号自适应缩小以显示完整名称）
# ══════════════════════════════════════════════════════════
class StationCard(QWidget):
    TITLE_H   = 38          # 固定标题行高，不随内容变化
    BADGE_W   = 72          # badge 最大宽度预留
    FONT_MAX  = 12          # 最大字号
    FONT_MIN  = 6           # 最小字号（再小就不可读了）

    def __init__(self, name: str, outlets: list, card_w: int, parent=None):
        super().__init__(parent)
        self.name    = name
        self.outlets = outlets
        self._card_w = card_w
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        n      = max(len(outlets), 1)
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

    def _fit_font_size(self, text_w: int) -> int:
        """从 FONT_MAX 往下找第一个能让名字放进 text_w 的字号。"""
        from PyQt5.QtGui import QFontMetrics
        for size in range(self.FONT_MAX, self.FONT_MIN - 1, -1):
            fm = QFontMetrics(QFont("Arial", size, QFont.Bold))
            if fm.horizontalAdvance(self.name) <= text_w:
                return size
        return self.FONT_MIN   # 实在太长，最小字号截断

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

        # ── badge ─────────────────────────────────────────
        fn  = sum(1 for o in self.outlets if o["status"] == 1) if self.outlets else 0
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
        bp.addRoundedRect(QRectF(bx, by, bw, bh), bh / 2, bh / 2)
        p.fillPath(bp, ac(sc, 38))
        p.setPen(ac(sc, 230))
        p.drawText(QRect(int(bx), int(by), int(bw), int(bh)), Qt.AlignCenter, badge_txt)

        # ── 站点名称（单行，字号自动收缩）────────────────
        text_w = int(bx) - PAD - 6
        fsize  = self._fit_font_size(text_w)
        p.setPen(ac(C_WHITE, 215))
        p.setFont(QFont("Arial", fsize, QFont.Bold))
        p.drawText(QRect(PAD, 0, text_w, th), Qt.AlignVCenter | Qt.AlignLeft, self.name)

        # ── 分隔线 ────────────────────────────────────────
        p.setPen(QPen(ac(C_WHITE, 13), 1))
        p.drawLine(PAD, th, w - PAD, th)

        if not self.outlets:
            p.setPen(ac(C_GREY, 120))
            p.setFont(QFont("Arial", 10))
            p.drawText(QRect(PAD, th, w - PAD * 2, h - th),
                       Qt.AlignVCenter, "获取数据失败")


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

        # ── 数据状态 ────────────────────────────────────────
        self._data:     dict  = {}
        self._filtered: dict  = {}
        self._expanded: bool  = False
        self._hover:    bool  = False
        self._phase:    float = 0.0

        # ── 拖动状态 ────────────────────────────────────────
        # drag_mode=True 时，按住左键可拖动；右键菜单可退出
        self._drag_mode:  bool          = False
        self._dragging:   bool          = False   # 当前是否正在按住拖动
        self._drag_start: QPoint | None = None    # 拖动起始锚点

        # ── 脉冲计时器 ──────────────────────────────────────
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._on_pulse)
        self._pulse_timer.start(33)

        # ── 搜索栏 ──────────────────────────────────────────
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("🔍  搜索站点名称…")
        self._search.setFixedHeight(SEARCH_H)
        self._search.setStyleSheet("""
            QLineEdit {
                background: rgba(0,0,0,0.75);
                border: 1px solid rgba(255,255,255,0.18);
                border-radius: 13px;
                color: rgba(255,255,255,0.95);
                font-size: 15px;
                padding: 0 16px;
                selection-background-color: rgba(10,132,255,0.5);
            }
            QLineEdit:focus {
                border: 1px solid rgba(10,132,255,0.80);
                background: rgba(0,0,0,0.85);
            }
        """)
        self._search.textChanged.connect(self._on_search)
        self._search.hide()

        # ── 站点计数标签 ────────────────────────────────────
        self._count_lbl = QLabel(self)
        self._count_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._count_lbl.setFixedHeight(COUNT_H)
        self._count_lbl.setStyleSheet("""
            color: rgba(255,255,255,0.75);
            font-size: 14px;
            font-weight: 600;
            background: transparent;
        """)
        self._count_lbl.hide()

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
    def update_data(self, data: dict):
        self._data = data
        self._apply_filter()
        self.update(0, 0, ISLAND_W, CAPSULE_H)

    # ──────────────────────────────────────────────────────
    #  搜索
    # ──────────────────────────────────────────────────────
    def _on_search(self, text: str):
        self._apply_filter()

    def _apply_filter(self):
        kw = self._search.text().strip().lower()
        if kw:
            self._filtered = {k: v for k, v in self._data.items()
                              if kw in k.lower()}
        else:
            self._filtered = dict(self._data)

        self._update_count_label()
        if self._expanded:
            self._rebuild_scroll()

    def _update_count_label(self):
        total  = len(self._data)
        shown  = len(self._filtered)
        kw     = self._search.text().strip()
        if kw:
            self._count_lbl.setText(f"  找到 {shown} / {total} 个站点")
        else:
            self._count_lbl.setText(f"  共 {total} 个站点")

    # ──────────────────────────────────────────────────────
    #  尺寸 & 子控件布局
    # ──────────────────────────────────────────────────────
    def _apply_size(self):
        if self._expanded:
            total_h = PANEL_Y + EXPANDED_H
            self.setFixedSize(ISLAND_W, total_h)

            inner_x = PAD
            inner_w = ISLAND_W - PAD * 2

            # 搜索栏
            self._search.setGeometry(
                inner_x,
                PANEL_Y + SEARCH_TOP,
                inner_w,
                SEARCH_H
            )
            self._search.show()

            # 计数标签
            count_y = PANEL_Y + SEARCH_TOP + SEARCH_H + 6
            self._count_lbl.setGeometry(inner_x, count_y, inner_w, COUNT_H)
            self._count_lbl.show()
            self._update_count_label()

            # 滚动区
            scroll_y = PANEL_Y + SCROLL_TOP
            scroll_h = EXPANDED_H - SCROLL_TOP - 8
            self._scroll.setGeometry(0, scroll_y, ISLAND_W, scroll_h)
            self._scroll.show()
            self._rebuild_scroll()

        else:
            self.setFixedSize(ISLAND_W, CAPSULE_H)
            self._search.hide()
            self._count_lbl.hide()
            self._scroll.hide()

    # ──────────────────────────────────────────────────────
    #  滚动内容
    # ──────────────────────────────────────────────────────
    def _rebuild_scroll(self):
        card_w    = ISLAND_W - PAD * 2
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        y = PAD   # 顶部留出完整内边距，确保第一张卡片圆角完全可见

        source = self._filtered

        if not source:
            lbl = QLabel("无匹配站点", container)
            lbl.setStyleSheet(
                "color: rgba(255,255,255,0.28); font-size: 13px; background: transparent;"
            )
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setGeometry(0, 16, ISLAND_W, 32)
            container.setFixedSize(ISLAND_W, 60)
            self._scroll.setWidget(container)
            return

        for name, outlets in source.items():
            card = StationCard(name, outlets, card_w, container)
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

    def _draw_capsule(self, p: QPainter):
        w, h = ISLAND_W, CAPSULE_H
        r    = h / 2

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), r, r)

        if self._drag_mode:
            p.setOpacity(0.70)

        bg = C_ISL_H if (self._hover and not self._drag_mode) else C_ISL
        p.fillPath(path, bg)

        gl = QLinearGradient(0, 0, 0, h * 0.55)
        gl.setColorAt(0, ac(C_WHITE, 22))
        gl.setColorAt(1, ac(C_WHITE, 0))
        p.fillPath(path, gl)

        if self._drag_mode:
            p.setPen(QPen(ac(C_BLUE, 200), 1.5))
        else:
            p.setPen(QPen(ac(C_SEP, 130), 0.8))
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
        p.drawText(QRect(40, 0, 140, h), Qt.AlignVCenter | Qt.AlignLeft,
                   "有空闲插座" if any_free else "全部占用")

        p.setPen(ac(sc, 215))
        p.setFont(QFont("Arial", 10, QFont.Bold))
        p.drawText(QRect(0, 0, w - 26, h), Qt.AlignVCenter | Qt.AlignRight,
                   f"{fn}/{tot}")

        p.setPen(ac(C_DARK, 210))
        p.setFont(QFont("Arial", 8))
        p.drawText(QRect(0, 0, w - 10, h), Qt.AlignVCenter | Qt.AlignRight,
                   "▲" if self._expanded else "▼")

    def _draw_panel_bg(self, p: QPainter):
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, PANEL_Y, ISLAND_W, EXPANDED_H), 22, 22)
        p.fillPath(path, C_ISL)

        gl = QLinearGradient(0, PANEL_Y, 0, PANEL_Y + 44)
        gl.setColorAt(0, ac(C_WHITE, 14))
        gl.setColorAt(1, ac(C_WHITE, 0))
        p.fillPath(path, gl)

        p.setPen(QPen(ac(C_SEP, 110), 0.8))
        p.drawPath(path)
        # 注意：不对 _scroll 设置 mask，避免裁切第一张卡片的顶部圆角

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
                background: rgba(30, 30, 32, 245);
                border: 1px solid rgba(255,255,255,0.13);
                border-radius: 12px;
                padding: 5px 0px;
                color: white;
                font-size: 13px;
            }
            QMenu::item {
                padding: 9px 22px 9px 16px;
                border-radius: 7px;
                margin: 1px 5px;
            }
            QMenu::item:selected {
                background: rgba(255,255,255,0.11);
            }
            QMenu::separator {
                height: 1px;
                background: rgba(255,255,255,0.10);
                margin: 4px 12px;
            }
        """)

        if self._drag_mode:
            exit_drag = QAction("  ✓  退出拖动模式", self)
            exit_drag.triggered.connect(self._exit_drag_mode)
            menu.addAction(exit_drag)
        else:
            drag_action = QAction("  ✥  拖动模式", self)
            drag_action.triggered.connect(self._enter_drag_mode)
            menu.addAction(drag_action)

        menu.addSeparator()

        quit_action = QAction("  ✕  关闭", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)

        menu.exec_(global_pos)

    # ──────────────────────────────────────────────────────
    #  拖动模式切换
    # ──────────────────────────────────────────────────────
    def _enter_drag_mode(self):
        self._drag_mode = True
        # 进入拖动模式时收起面板，避免遮挡
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

        # ── 右键：任何时候在胶囊上右键都弹菜单 ────────────
        if e.button() == Qt.RightButton and in_capsule:
            self._show_context_menu(e.globalPos())
            return

        # ── 左键 ────────────────────────────────────────────
        if e.button() == Qt.LeftButton:
            if self._drag_mode:
                # 拖动模式：记录拖动起点，开始拖动
                self._dragging   = True
                self._drag_start = e.globalPos() - self.frameGeometry().topLeft()
            elif in_capsule:
                # 普通模式：点胶囊展开/收起
                self._expanded = not self._expanded
                if not self._expanded:
                    self._search.clear()
                self._apply_size()
                self.update()
            else:
                # 展开面板区域按住可拖动窗口
                self._dragging   = True
                self._drag_start = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._dragging and self._drag_start is not None:
            if e.buttons() & Qt.LeftButton:
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
