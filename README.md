# 充电桩灵动岛监控

一个仿苹果 Dynamic Island 风格的充电桩实时状态监控小工具，悬浮在桌面顶部，随时查看各站点插座占用情况。

---

## 目录结构

```
charger_monitor/
├── main.py               # 应用入口
├── charger_api.py        # 数据获取层
├── charger_ui.py         # UI 组件层
├── station_picker.py     # 附近站点查询 & 导出工具
├── station.json          # 站点配置文件（名称 → ID 映射）
├── icons.qrc             # Qt 图标资源描述文件
├── icons_rc.py           # pyrcc5 编译后的图标资源（需自行生成）
├── charger_monitor.spec  # PyInstaller 打包配置
├── requirements.txt      # Python 依赖
└── README.md
```

---

## 环境要求

- Python 3.8 或以上
- Windows / macOS / Linux（Windows 推荐）

---

## 安装依赖

```bash
pip install -r requirements.txt
```

---

## 配置站点

### 方式一：使用查询工具自动生成（推荐）

```bash
python station_picker.py
```

程序启动后自动查询附近充电站，勾选需要监控的站点，点击**导出 station.json**，将生成的文件放在监控程序同目录下即可。

### 方式二：手动编辑

新建 `station.json`，格式为**站点名称 → 站点 ID** 的 JSON 字典：

```json
{
    "A区1号充电站": 177972,
    "A区2号充电站": 177970,
    "B区1号充电站": 177968
}
```

> **重要**：`station.json` 不内置在可执行文件中，需放在程序同目录下，程序启动时自动读取。

---

## 配置 Token（如需鉴权）

打开 `charger_api.py`，找到 `HEADERS` 字典，取消 `token` 行的注释并填入有效值：

```python
"token": "你的token值",
```

---

## 配置图标（可选）

图标使用 Qt Resource System，步骤如下：

**1. 准备 PNG 图标**（32×32px，背景透明）：

| 文件名 | 用途 |
|--------|------|
| `sort_widget.png` | 排序控件左侧功能图标 |
| `sort_serial.png` | 按序号排序 |
| `sort_power.png`  | 按功率排序 |
| `sort_fee.png`    | 按费用排序 |
| `sort_duration.png` | 按时长排序 |

**2. 编译资源文件：**

```bash
pyrcc5 icons.qrc -o icons_rc.py
```

**3. 在 `charger_ui.py` 顶部取消注释：**

```python
import icons_rc
```

**4. 填入资源路径：**

```python
SORT_WIDGET_ICON_PATH = ":/icons/sort_widget.png"
SORT_ICON_PATH = {
    SORT_SERIAL:   ":/icons/sort_serial.png",
    SORT_POWER:    ":/icons/sort_power.png",
    SORT_FEE:      ":/icons/sort_fee.png",
    SORT_DURATION: ":/icons/sort_duration.png",
}
```

不配置图标时，自动回退到文字符号显示，功能不受影响。

---

## 运行

```bash
python main.py
```

启动后，灵动岛胶囊出现在屏幕顶部居中位置。

---

## 打包为可执行文件（PyInstaller）

### 1. 安装 PyInstaller

```bash
pip install pyinstaller
```

### 2. 可选：安装 UPX 压缩（减小体积约 30–50%）

- **Windows**：从 [upx.github.io](https://upx.github.io) 下载，将 `upx.exe` 放入系统 PATH
- **macOS**：`brew install upx`
- **Linux**：`sudo apt install upx`

不使用 UPX 时，将 `charger_monitor.spec` 中的 `upx=True` 改为 `upx=False`。

### 3. 执行打包

```bash
pyinstaller charger_monitor.spec
```

打包完成后，可执行文件位于 `dist/` 目录。将 `station.json` 放在可执行文件同目录下即可分发。

---

## 常见问题

**Q：胶囊透明 / 看不见？**
确认系统开启了窗口合成（Windows 需 Win8+，Linux 需运行合成器如 Picom）。

**Q：一直显示"正在获取数据…"？**
检查 `station.json` 中的站点 ID 是否正确，以及 `token` 是否有效。

**Q：加载图标路径后程序崩溃（exit code -1073740791）？**
图标加载必须在 `QApplication` 创建之后执行，当前代码已通过懒加载处理，请确认使用的是最新版 `charger_ui.py`，且 `import icons_rc` 写在文件顶部而非函数内部。

**Q：打包后运行闪退？**
以命令行运行可执行文件查看报错。常见原因是缺少 Qt 平台插件，将 `PyQt5/Qt5/plugins/platforms/` 目录复制到 `dist/` 同级目录即可。

**Q：如何修改刷新间隔？**
打开 `main.py`，修改 `REFRESH_INTERVAL_MS`（单位毫秒，默认 `30000`）。
