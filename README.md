# 充电桩灵动岛监控

一个仿苹果 Dynamic Island 风格的充电桩实时状态监控小工具，悬浮在桌面顶部，随时查看各站点插座状态。

---

## 目录结构

```
charger_monitor/
├── main.py               # 应用入口
├── charger_api.py        # 数据获取层
├── charger_ui.py         # UI 组件层
├── station.json          # 站点配置文件（名称 → ID 映射）
├── charger_monitor.spec  # PyInstaller 打包配置
├── requirements.txt      # Python 依赖
└── README.md
```

---

## 环境要求

- Python 3.10 或以上（使用了 `X | Y` 联合类型语法）
- Windows / macOS / Linux

---

## 安装依赖

```bash
pip install -r requirements.txt
```

---

## 配置站点

### 方式一：使用查询工具自动生成（推荐）

运行附带的查询工具：

```bash
python station_picker.py
```

输入你所在位置的经纬度，查询附近充电站，勾选需要监控的站点，点击**导出 station.json**，将生成的文件放在监控程序同目录下即可。

### 方式二：手动编辑

新建 `station.json`，格式为**站点名称 → 站点 ID** 的 JSON 字典：

```json
{
    "A区1号充电站": 177972,
    "A区2号充电站": 177970,
    "B区1号充电站": 177968
}
```

- **键**：任意站点名称，会直接显示在 UI 卡片标题上
- **值**：API 中的站点数字 ID

> **重要**：`station.json` 不内置在可执行文件中，需放在程序同目录下，程序启动时会自动读取。

---

## 配置 Token（如需鉴权）

打开 `charger_api.py`，找到 `HEADERS` 字典，取消 `token` 行的注释并填入有效值：

```python
HEADERS = {
    ...
    "token": "你的token值",   # ← 取消注释，填入实际 token
    ...
}
```

---

## 运行

```bash
python main.py
```

启动后，灵动岛胶囊会出现在屏幕顶部居中位置。

---

## 使用说明

| 操作 | 效果 |
|------|------|
| **左键单击胶囊** | 展开 / 收起站点详情面板 |
| **胶囊上右键** | 弹出菜单（拖动模式 / 关闭） |
| **搜索栏输入** | 按站点名称实时过滤 |
| **拖动模式下按住左键** | 拖动窗口到任意位置 |
| **拖动模式下右键** | 弹出菜单，可退出拖动模式 |

**插座状态颜色说明：**

| 颜色 | 状态 |
|------|------|
| 🟢 绿色 | 空闲（可使用） |
| 🔴 红色 | 占用中 |
| 🟡 黄色 | 损坏 |

胶囊指示灯：全局有空闲插座显示**绿色**，全部占用显示**红色**。

数据每 **30 秒**自动后台刷新一次，不阻塞 UI。

---

## 打包为可执行文件（PyInstaller）

### 1. 安装 PyInstaller

```bash
pip install pyinstaller
```

### 2. 可选：安装 UPX 压缩工具（减小体积约 30-50%）

- **Windows**：从 [upx.github.io](https://upx.github.io) 下载，将 `upx.exe` 放入系统 PATH
- **macOS**：`brew install upx`
- **Linux**：`sudo apt install upx` 或 `sudo yum install upx`

若不使用 UPX，打开 `charger_monitor.spec`，将 `upx=True` 改为 `upx=False`。

### 3. 执行打包

```bash
pyinstaller charger_monitor.spec
```

打包完成后，可执行文件位于：

```
dist/充电桩监控          # macOS / Linux
dist/充电桩监控.exe      # Windows
```

### 4. 分发

将整个 `dist/` 目录（或其中的单个可执行文件）复制到目标机器即可直接运行，无需安装 Python。

> **注意**：`station.json` 已打包进可执行文件内部，若需修改站点配置，需重新打包。
> 如果希望保持外部可编辑，可在 spec 文件的 `datas` 中调整路径，并在 `charger_api.py` 中使用 `sys._MEIPASS` 路径读取。

---

## 常见问题

**Q：启动后胶囊是透明的/看不见？**
A：确认系统开启了窗口合成（Windows 需 Win8+，Linux 需运行合成器如 Picom/Compiz）。

**Q：数据一直显示"正在获取数据…"？**
A：检查 `station.json` 中的站点 ID 是否正确，以及 `HEADERS` 中的 `token` 是否有效且未过期。

**Q：打包后运行闪退？**
A：以命令行方式运行 `dist/充电桩监控.exe`，查看报错信息。常见原因是缺少 Qt 平台插件，可将 `PyQt5/Qt5/plugins/platforms/` 目录复制到 `dist/` 同级目录。

**Q：如何修改刷新间隔？**
A：打开 `main.py`，修改顶部的 `REFRESH_INTERVAL_MS`（单位毫秒，默认 `30_000` = 30秒）。
