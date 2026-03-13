# 充电桩监控

一个仿苹果 Dynamic Island 风格的充电桩实时状态监控工具，悬浮在桌面顶部，随时查看附近充电站的插座占用情况。

---

## 软件包文件

| 文件 | 说明 |
|------|------|
| `充电桩监控.exe` | 主程序，桌面悬浮式充电桩实时监控 |
| `充电桩ID搜索器.exe` | 辅助工具，查询附近充电站并生成配置文件 |
| `station.json` | 站点配置文件，须与主程序放在同一目录下 |

---

## 首次使用

1. 运行 `充电桩ID搜索器.exe`，查询附近充电站
2. 勾选需要监控的站点，点击「导出 station.json」
3. 将导出的 `station.json` 放入与 `充电桩监控.exe` 相同的文件夹
4. 双击运行 `充电桩监控.exe`，屏幕顶部出现黑色胶囊即为启动成功

> `station.json` 必须与主程序在同一目录，否则启动时报错。

---

## 主要功能

- **胶囊状态**：绿色指示灯表示有空闲插座，红色表示全部占用，右侧显示空闲数/总数
- **详情面板**：单击胶囊展开，显示各站点全部插座状态及充电数据（功率/费用/时长）
- **搜索过滤**：面板顶部搜索栏，按站点名称实时过滤
- **排序**：工具栏右侧排序按钮，支持按序号/功率/费用/时长排列插座
- **我的插座**：点击占用中的插座行向左滑出按钮，标记为我的插座后进入充电监控模式，胶囊实时显示该插座数据，充电结束自动提示「充电完成」
- **充电模式菜单**：充电监控模式下左键点击胶囊弹出菜单，可切换动态扫光效果或返回普通模式
- **拖动**：右键胶囊 → 拖动模式，可将胶囊拖到任意位置

---

## 源码目录结构

```
charger_monitor/
├── main.py                 # 应用入口
├── charger_api.py          # 数据获取层
├── charger_ui.py           # UI 组件层
├── station_picker.py       # 站点查询工具
├── station.json            # 站点配置（运行时从外部读取）
├── icons.qrc               # Qt 图标资源描述（可选）
├── icons_rc.py             # 编译后的图标模块（可选，需自行生成）
├── charger_monitor.spec    # 主程序打包配置
├── station_picker.spec     # 搜索器打包配置
├── requirements.txt        # Python 依赖
└── README.md
```

---

## 开发环境

- Python 3.8+
- 依赖：`pip install -r requirements.txt`（PyQt5、requests）

---

## 打包

```bash
# 主程序 → 充电桩监控.exe
pyinstaller charger_monitor.spec

# 搜索器 → 充电桩ID搜索器.exe
pyinstaller station_picker.spec
```

打包产物在 `dist/` 目录，发布时将 `station.json` 放在 exe 同目录即可。

---

## 自定义图标（可选）

在 `charger_ui.py` 顶部填入图标路径常量，支持排序控件图标和充电模式图标。准备好 PNG 后用 `pyrcc5 icons.qrc -o icons_rc.py` 编译，路径留空时自动回退到文字符号，功能不受影响。

---

## 常见问题

**胶囊透明/不可见** — 开启系统透明效果（Windows：设置 → 个性化 → 颜色 → 透明效果）。

**一直显示「正在获取数据…」** — 检查网络连接及 `station.json` 中的站点 ID 是否有效。

**打包后闪退** — 命令行运行 exe 查看报错，常见原因是缺少 Qt 平台插件，将 `PyQt5/Qt5/plugins/platforms/` 复制到 exe 同目录下。

**修改刷新间隔** — 打开 `main.py`，修改 `REFRESH_INTERVAL_MS`（毫秒，默认 30000）。
