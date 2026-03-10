"""
charger_api.py — 充电桩数据获取层

站点配置从 station.json 读取，格式：
  { "站点名称": station_id, ... }

插座状态（currentChargingRecordId）：
  1 → 空闲
  2 → 占用
  3 → 损坏
"""

import json
import requests
from pathlib import Path
from typing import Optional

# ══════════════════════════════════════════════════════════
#  站点配置（从 station.json 读取）
# ══════════════════════════════════════════════════════════
PROXIES = {"http": None, "https": None}
TIMEOUT = 10
SLEEP_BETWEEN = 1.5
def _find_station_json() -> Path:
    """
    查找 station.json：
      - 打包后（PyInstaller）：在可执行文件同目录下
      - 开发时直接运行：在脚本同目录下
    """
    import sys
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    return base / "station.json"

def load_stations():
    """读取 station.json，返回 {name: station_id} 字典。"""
    path = _find_station_json()
    if not path.exists():
        raise FileNotFoundError(
            f"找不到 station.json，请将其放在程序同目录下：{path}"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# ══════════════════════════════════════════════════════════
#  请求头
# ══════════════════════════════════════════════════════════

HEADERS = {
    "sec-ch-ua-platform": "\"Android\"",
    "sec-ch-ua": "\"Chromium\";v=\"142\", \"Android WebView\";v=\"142\", \"Not_A Brand\";v=\"99\"",
    "systemphone": "Android 16",
    "sec-ch-ua-mobile": "?1",
    "brands": "2407FRK8EC",
    "user-agent": (
        "Mozilla/5.0 (Linux; Android 16; 2407FRK8EC Build/BP2A.250605.031.A3; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36"
    ),
    "content-type": "application/json;charset=utf-8",
    # "token": "YOUR_TOKEN_HERE",   # ← 填入有效 token
    "accept": "*/*",
    "origin": "https://api.issks.com",
    "x-requested-with": "com.tencent.mm",
    "sec-fetch-site": "same-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "referer": "https://api.issks.com/",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "priority": "u=1, i",
}

TIMEOUT = 10

# ──────────────────────────────────────────────────────────
#  状态常量
# ──────────────────────────────────────────────────────────
STATUS_FREE   = 1
STATUS_BUSY   = 2
STATUS_BROKEN = 3
KNOWN_STATUSES = (STATUS_FREE, STATUS_BUSY, STATUS_BROKEN)


# ══════════════════════════════════════════════════════════
#  单站查询
# ══════════════════════════════════════════════════════════

def fetch_station(station_id: int):
    """
    查询单个站点所有插座，返回：
      [ {"serial": int, "status": int}, ... ]
    失败返回 None。
    """
    url = f"https://wemp.issks.com/charge/v1/outlet/station/outlets/{station_id}"
    try:
        resp = requests.get(url, headers=HEADERS, proxies=PROXIES, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if str(data.get("code")) != "1":
            return None

        result = []
        for outlet in data.get("data", []):
            raw = outlet.get("currentChargingRecordId")
            status = raw if raw in KNOWN_STATUSES else STATUS_BROKEN
            result.append({
                "serial": outlet.get("outletSerialNo", 0),
                "status": status,
            })
        return result

    except Exception as e:
        print(f"[API] 站点 {station_id} 请求失败: {e}")
        return None


# ══════════════════════════════════════════════════════════
#  全量查询
# ══════════════════════════════════════════════════════════

def fetch_all_stations():
    """
    读取 station.json，查询所有站点，返回：
      {
        "A区1号充电站": [ {"serial": 1, "status": 1}, ... ],
        "A区2号充电站": [ ... ],
        ...
      }
    站点请求失败时对应值为空列表。
    """
    stations = load_stations()
    result = {}
    for name, sid in stations.items():
        outlets = fetch_station(sid)
        result[name] = outlets if outlets is not None else []
        print(f"[API] {name}({sid}): {'失败' if outlets is None else f'{len(outlets)} 个插座'}")
    return result
