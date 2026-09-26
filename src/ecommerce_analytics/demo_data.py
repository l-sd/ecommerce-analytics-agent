"""Reproducible synthetic e-commerce data: orders, traffic, and product master.

Three files come out of :func:`write_demo`:

``synthetic_orders.csv``
    The order detail sheet, intentionally messy (mixed date formats, currency
    symbols, negative refund quantities, duplicated rows).
``synthetic_traffic.csv``
    Channel x day funnel counts (exposure, visitors, add-to-cart, orders). Its
    ``下单数`` column is *derived from the orders*, so the two tables reconcile
    by construction rather than by luck.
``synthetic_products.csv``
    The 50-row product master. It is the only legitimate denominator for the
    sell-through rate -- deriving that denominator from the order detail would
    make the metric a constant 100%.

Design note -- the random stream is frozen
------------------------------------------
``generate_orders`` consumes one strict ``random.Random(seed)`` stream. Every
call that existed before this module grew its extra columns is still made, in
the same order and under the same conditions, and its return value is simply
ignored where a column is now driven by a hash instead. That keeps the stream
byte-identical, so ``profile_raw``'s 14 data-quality counts do not move.

Two rules follow from that, and breaking either silently shifts the dataset:

1. Never turn ``A if cond else B`` into "call unconditionally, then decide" --
   that reorders evaluation. ``rng.random()`` is the *condition* in several
   places and must stay in front of the call it guards.
2. Never swap ``rng.choice`` for ``rng.choices(weights=...)`` -- they consume a
   different number of ``getrandbits`` calls.

Columns that need a distribution are therefore drawn from :func:`_q`, a
row-level CRC32 quantile that is independent of the stream and of row order.
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
import random
import zlib
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .pipeline import parse_date

PRODUCTS = [
    ("P001", "iPhone 15 128G", "手机数码", "Apple", 5999),
    ("P002", "iPhone 15 Pro 256G", "手机数码", "Apple", 8999),
    ("P003", "华为 Mate 60 Pro", "手机数码", "华为", 6999),
    ("P004", "小米 14 12+256G", "手机数码", "小米", 4299),
    ("P005", "荣耀 Magic6", "手机数码", "荣耀", 3999),
    ("P006", "Redmi K70", "手机数码", "小米", 2499),
    ("P007", "AirPods Pro 2", "手机数码", "Apple", 1899),
    ("P008", "索尼 WH-1000XM5 耳机", "手机数码", "索尼", 2399),
    ("P009", "小米手环8", "手机数码", "小米", 249),
    ("P010", "小米 充电宝20000mAh", "手机数码", "小米", 129),
    ("P011", "罗技 MX Master 3S 鼠标", "电脑办公", "罗技", 699),
    ("P012", "机械键盘 87键", "电脑办公", "雷柏", 199),
    ("P013", "戴尔 U2723QE 显示器", "电脑办公", "戴尔", 3499),
    ("P014", "联想小新 Pro16 笔记本", "电脑办公", "联想", 5799),
    ("P015", "华为平板 MatePad 11", "电脑办公", "华为", 2199),
    ("P016", "得力 A4 打印纸", "电脑办公", "得力", 29.9),
    ("P017", "得力 文件夹", "电脑办公", "得力", 15.9),
    ("P018", "美的 1.5匹空调", "家电", "美的", 2799),
    ("P019", "海尔 10kg 滚筒洗衣机", "家电", "海尔", 1899),
    ("P020", "格力 电风扇", "家电", "格力", 199),
    ("P021", "米家扫地机器人", "家电", "小米", 1599),
    ("P022", "苏泊尔电饭煲", "家电", "苏泊尔", 299),
    ("P023", "九阳破壁机", "家电", "九阳", 399),
    ("P024", "戴森 V12 吸尘器", "家电", "戴森", 3290),
    ("P025", "海尔冰箱 501L", "家电", "海尔", 3999),
    ("P026", "小米电视 65寸", "家电", "小米", 2999),
    ("P027", "优衣库 圆领T恤", "服饰", "优衣库", 79),
    ("P028", "李宁 跑步鞋", "服饰", "李宁", 399),
    ("P029", "阿迪达斯 运动外套", "服饰", "阿迪达斯", 599),
    ("P030", "南极人 棉袜5双装", "服饰", "南极人", 29.9),
    ("P031", "波司登 羽绒服", "服饰", "波司登", 1299),
    ("P032", "太平鸟 牛仔裤", "服饰", "太平鸟", 259),
    ("P033", "兰蔻 小黑瓶精华", "美妆个护", "兰蔻", 760),
    ("P034", "雅诗兰黛 小棕瓶", "美妆个护", "雅诗兰黛", 950),
    ("P035", "欧莱雅 洗面奶", "美妆个护", "欧莱雅", 129),
    ("P036", "云南白药 牙膏", "美妆个护", "云南白药", 39.9),
    ("P037", "海飞丝 洗发水", "美妆个护", "宝洁", 59.9),
    ("P038", "全棉时代 洗脸巾", "美妆个护", "全棉时代", 49.9),
    ("P039", "完美日记 口红", "美妆个护", "完美日记", 89),
    ("P040", "三只松鼠 坚果礼盒", "食品", "三只松鼠", 99),
    ("P041", "蒙牛 纯牛奶24盒", "食品", "蒙牛", 69.9),
    ("P042", "农夫山泉 矿泉水", "食品", "农夫山泉", 36),
    ("P043", "星巴克 咖啡豆", "食品", "星巴克", 128),
    ("P044", "良品铺子 零食大礼包", "食品", "良品铺子", 139),
    ("P045", "金龙鱼 食用油5L", "食品", "金龙鱼", 89.9),
    ("P046", "网易严选 保温杯", "家居日用", "网易严选", 99),
    ("P047", "全棉时代 浴巾", "家居日用", "全棉时代", 79),
    ("P048", "公牛 插线板", "家居日用", "公牛", 49.9),
    ("P049", "苏泊尔 炒锅", "家居日用", "苏泊尔", 159),
    ("P050", "宜家 收纳箱", "家居日用", "宜家", 69),
]

CHANNELS = ["天猫", "京东", "拼多多", "抖音", "微信小程序"]
PROVINCES = [
    "广东", "浙江", "江苏", "山东", "河南", "四川", "湖北", "湖南", "福建", "安徽",
    "河北", "北京", "上海", "陕西", "重庆", "辽宁", "江西", "天津", "广西", "云南",
    "贵州", "山西", "吉林", "黑龙江", "内蒙古", "新疆", "甘肃", "海南", "宁夏", "青海",
]
STATUSES = ["已完成", "已发货", "待发货", "已取消", "已退款"]

STATUS_WEIGHTS = [0.55, 0.15, 0.10, 0.10, 0.10]
CHANNEL_WEIGHTS = [0.35, 0.25, 0.20, 0.12, 0.08]
# 已退款订单走一套偏置权重，让退款率在渠道之间拉开差距（天猫低、抖音高）。
REFUND_CHANNEL_WEIGHTS = [0.09, 0.168, 0.20, 0.288, 0.112]

# 收货省份不再是均匀分布：电商订单集中在沿海与人口大省。
PROVINCE_WEIGHTS = [
    0.145, 0.105, 0.098, 0.072, 0.062, 0.055, 0.050, 0.046, 0.045, 0.040,
    0.038, 0.035, 0.034, 0.028, 0.026, 0.024, 0.022, 0.018, 0.017, 0.015,
    0.013, 0.012, 0.010, 0.010, 0.008, 0.007, 0.006, 0.005, 0.003, 0.002,
]

# 在售但窗口内零销量的 SKU。高价耐用品周转慢，滞销识别才有东西可看。
UNSOLD_PRODUCT_IDS = ["P013", "P014", "P024", "P025", "P031"]
CATALOG_COLUMNS = ["商品ID", "商品名称", "品类", "品牌", "单价", "在售状态"]

CARRIERS = ["顺丰", "京东物流", "中通", "圆通", "邮政"]
CARRIER_WEIGHTS = [0.28, 0.22, 0.20, 0.18, 0.12]
SHIPPED_STATUSES = {"已完成", "已发货"}

# 承诺发货时效（自下单起，天）
CARRIER_SHIP_PROMISE = {"顺丰": 1, "京东物流": 1, "中通": 2, "圆通": 2, "邮政": 3}
# 承诺送达时效（自发货起，天）
CARRIER_DELIVERY_PROMISE = {"顺丰": 3, "京东物流": 3, "中通": 4, "圆通": 4, "邮政": 6}
# 实际发货时效分布，右偏长尾：长尾那一段就是迟发订单。整体迟发率约 7.7%，
# 高于行业常设的 4% 考核线，且按 顺丰 < 京东物流 ≈ 中通 < 圆通 < 邮政 排序。
CARRIER_SHIP_LAG = {
    "顺丰": [(1, 0.960), (2, 0.035), (3, 0.005)],
    "京东物流": [(1, 0.930), (2, 0.060), (3, 0.010)],
    "中通": [(1, 0.380), (2, 0.550), (3, 0.060), (4, 0.010)],
    "圆通": [(1, 0.320), (2, 0.570), (3, 0.100), (4, 0.010)],
    "邮政": [(2, 0.420), (3, 0.440), (4, 0.120), (5, 0.020)],
}
# 实际签收时效分布（自发货起，天）
CARRIER_DELIVERY_LAG = {
    "顺丰": [(1, 0.30), (2, 0.52), (3, 0.15), (4, 0.03)],
    "京东物流": [(1, 0.26), (2, 0.50), (3, 0.19), (4, 0.05)],
    "中通": [(2, 0.24), (3, 0.48), (4, 0.21), (5, 0.06), (6, 0.01)],
    "圆通": [(2, 0.20), (3, 0.46), (4, 0.25), (5, 0.07), (6, 0.02)],
    "邮政": [(3, 0.18), (4, 0.34), (5, 0.28), (6, 0.14), (7, 0.05), (9, 0.01)],
}

REFUND_REASONS = ["七天无理由", "质量问题", "发错货", "物流太慢", "不想要了", "价格保护"]
REFUND_REASON_WEIGHTS = [0.38, 0.18, 0.08, 0.14, 0.14, 0.08]

# 各月订单量配额，合计 365。6 月（618）、11 月（双11）、12 月（双12）为脉冲月，
# 9 月为淡季。生成时把 rng.randint(0, 364) 的返回值当作这张保序表的索引。
MONTH_ORDER_COUNTS = [22, 25, 28, 25, 28, 40, 28, 25, 18, 26, 55, 45]

TRAFFIC_COLUMNS = ["日期", "渠道", "曝光数", "访客数", "加购数", "下单数"]
# 每个成交订单对应的访客数，即渠道转化效率的倒数：抖音靠流量、天猫靠转化。
CHANNEL_VISITORS_PER_ORDER = {
    "天猫": 22, "京东": 20, "拼多多": 26, "抖音": 55, "微信小程序": 30,
}
TRAFFIC_START = dt.date(2024, 1, 1)


# --- deterministic hash sampling (never touches the random stream) -----------


def _q(key: str, salt: str, buckets: int = 10_000) -> float:
    """Row-level deterministic quantile in ``[0, 1)``.

    Independent of the ``random.Random`` stream and of row order, so a column
    can be re-derived at any time without shifting every other column.
    """
    return (zlib.crc32(f"{key}|{salt}".encode()) % buckets) / buckets


def _pick(keys: list, weights: list[float], q: float):
    """Inverse-CDF sampling: turn a quantile into one of ``keys``."""
    exact_weights = [Decimal(str(weight)) for weight in weights]
    total = sum(exact_weights)
    if total <= 0:
        return keys[-1]
    target = Decimal(str(q)) * total
    accumulated = Decimal(0)
    for key, weight in zip(keys, exact_weights, strict=True):
        accumulated += weight
        if target <= accumulated:
            return key
    return keys[-1]


def _pick_weighted(pairs: list[tuple], q: float):
    """Inverse-CDF sampling over ``[(value, weight), ...]``."""
    return _pick([value for value, _ in pairs], [weight for _, weight in pairs], q)


def _build_day_table() -> list[dt.date]:
    """A sorted 365-day table whose month frequencies follow the promo calendar.

    Sorted so the mapping stays monotone: a later random draw never lands on an
    earlier date than a smaller one. Days repeat inside a busy month and drop
    out of a quiet one, which is exactly the pulse we want.
    """
    table: list[dt.date] = []
    for month, count in enumerate(MONTH_ORDER_COUNTS, start=1):
        last_day = calendar.monthrange(2024, month)[1]
        for index in range(count):
            table.append(dt.date(2024, month, min(1 + int(index * last_day / count), last_day)))
    table.sort()
    return table


DAY_TABLE = _build_day_table()


def _product_weights() -> list[float]:
    """Popularity weights for the catalogue.

    Deliberately independent of price: a weight derived from the price would
    either flatten the Pareto chart or (because ``PRODUCTS`` is sorted by price
    descending) inflate GMV several times over.
    """
    weights = []
    for product_id, *_rest in PRODUCTS:
        if product_id in UNSOLD_PRODUCT_IDS:
            weights.append(0.0)
        else:
            popularity = _q(product_id, "popularity")
            weights.append(0.5 + popularity**2)
    return weights


PRODUCT_WEIGHTS = _product_weights()

# 客户池。原实现只从 1..200 里取，而有效订单约 2,250 条 —— 每个客户必然复购，
# 复购率恒为 100%，指标失去意义。池子放大到 1,500 后复购率落回可解释区间。
USER_POOL_SIZE = 1500


def _user_index(order_id: str) -> int:
    """Uniform 1-based customer index.

    Uses the hash directly instead of :func:`_pick` because the pool is uniform
    and large: a linear CDF scan per order would cost more than the rest of the
    generator put together, and with equal weights the scan is just a floor.
    """
    return 1 + int(_q(order_id, "user") * USER_POOL_SIZE)


def _advance_rng_for_companion_user_table(rng: random.Random) -> None:
    cities = [
        "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆",
        "苏州", "天津", "长沙", "郑州", "青岛", "合肥", "福州", "厦门", "宁波", "无锡",
    ]
    levels = ["普通会员", "银卡会员", "金卡会员", "黑卡会员"]
    for _ in range(200):
        rng.randint(0, 730)
        rng.choice(["男", "女", "女", "女", "男"])
        rng.choice(cities)
        rng.choices(levels, weights=[0.6, 0.25, 0.12, 0.03], k=1)


def _format_date(value: dt.date | None, key: str, salt: str) -> str | None:
    """Emit a date in one of two formats, to exercise the mixed-format parser."""
    if value is None:
        return None
    if _q(key, salt) < 0.15:
        return f"{value.year}/{value.month}/{value.day}"
    return value.isoformat()


def generate_orders(rows: int = 3000, seed: int = 20240601) -> pd.DataFrame:
    """Generate intentionally messy synthetic orders for pipeline testing."""
    rng = random.Random(seed)
    _advance_rng_for_companion_user_table(rng)
    orders: list[dict[str, object]] = []

    for i in range(1, rows + 1):
        order_id = f"DD2024{i:05d}"
        # Placeholder: the draw is kept so the stream stays aligned, the value
        # comes from a hash so the catalogue can carry a popularity curve.
        rng.choice(PRODUCTS)
        product_id, product_name, category, brand, price = _pick(
            PRODUCTS, PRODUCT_WEIGHTS, _q(order_id, "product")
        )

        date_roll = rng.random()
        order_date: dt.date | None = None
        if date_roll < 0.02:
            date_value = None
        else:
            order_date = DAY_TABLE[rng.randint(0, 364)]
            if date_roll < 0.17:
                date_value = f"{order_date.year}/{order_date.month}/{order_date.day}"
            elif date_roll < 0.27:
                date_value = order_date.strftime("%Y-%m-%d")
            elif date_roll < 0.32:
                date_value = order_date.strftime("%Y%m%d")
            else:
                date_value = order_date.isoformat()

        name_roll = rng.random()
        if name_roll < 0.6:
            name = product_name
        elif name_roll < 0.75:
            name = product_name.lower()
        elif name_roll < 0.9:
            name = product_name.replace(" ", "")
        else:
            name = product_name + " "

        price_roll = rng.random()
        if price_roll < 0.05:
            price_value = None
        elif price_roll < 0.30:
            price_value = "¥" + (str(int(price)) if float(price).is_integer() else str(price))
        elif price_roll < 0.40:
            price_value = f"{int(price):,}" if float(price).is_integer() and price >= 1000 else price
        else:
            price_value = price

        status = rng.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
        qty_roll = rng.random()
        if qty_roll < 0.02:
            quantity = None
        elif qty_roll < 0.04:
            quantity = 0
        elif status == "已退款":
            quantity = -rng.randint(1, 3)
        else:
            quantity = rng.randint(1, 5)

        if price_value is None or quantity is None or quantity == 0:
            amount = None
        else:
            amount = price * quantity
            amount_roll = rng.random()
            if amount_roll < 0.025:
                amount = None
            elif amount_roll < 0.05:
                amount = round(price * quantity * 0.5, 2)

        # Condition first, then the draw -- reversing this shifts the stream.
        channel_kept = rng.random() > 0.01
        if channel_kept:
            rng.choices(CHANNELS, weights=CHANNEL_WEIGHTS, k=1)
        # Refunded orders draw from a channel-biased set, so the refund rate
        # differs by channel without touching the status draw above.
        channel_pool = REFUND_CHANNEL_WEIGHTS if status == "已退款" else CHANNEL_WEIGHTS
        channel = _pick(CHANNELS, channel_pool, _q(order_id, "channel")) if channel_kept else None

        # Placeholder again: drawing 1..200 keeps the stream aligned, but the
        # real pool is much larger. With only 200 customers for ~2,250 valid
        # orders every single customer repurchases by construction, which pins
        # the repeat rate at 100% and makes the metric meaningless.
        user_kept = rng.random() > 0.02
        if user_kept:
            rng.randint(1, 200)
        user_id = f"U{_user_index(order_id):04d}" if user_kept else None
        province_kept = rng.random() > 0.01
        if province_kept:
            rng.choice(PROVINCES)
        province = _pick(PROVINCES, PROVINCE_WEIGHTS, _q(order_id, "province")) if province_kept else None

        product_id_value = product_id if rng.random() > 0.02 else None

        # --- fulfilment columns: hash-driven, so the stream above is untouched
        carrier = _pick(CARRIERS, CARRIER_WEIGHTS, _q(order_id, "carrier")) if status in SHIPPED_STATUSES else None
        ship_lag = _pick_weighted(CARRIER_SHIP_LAG[carrier], _q(order_id, "ship_lag")) if carrier else None
        shipped_on = (
            order_date + dt.timedelta(days=ship_lag) if order_date is not None and ship_lag is not None else None
        )
        delivery_lag = (
            _pick_weighted(CARRIER_DELIVERY_LAG[carrier], _q(order_id, "delivery_lag"))
            if carrier and status == "已完成"
            else None
        )
        delivered_on = (
            shipped_on + dt.timedelta(days=delivery_lag)
            if shipped_on is not None and delivery_lag is not None
            else None
        )
        refund_reason = (
            _pick(REFUND_REASONS, REFUND_REASON_WEIGHTS, _q(order_id, "refund_reason"))
            if status == "已退款"
            else None
        )

        orders.append({
            "订单号": order_id,
            "日期": date_value,
            "渠道": channel,
            "商品ID": product_id_value,
            "商品名称": name,
            "单价": price_value,
            "数量": quantity,
            "金额": amount,
            "用户ID": user_id,
            "收货省份": province,
            "订单状态": status,
            "商品品类": category,
            "承诺发货时效": CARRIER_SHIP_PROMISE[carrier] if carrier else None,
            "物流商": carrier,
            "承诺送达时效": CARRIER_DELIVERY_PROMISE[carrier] if carrier else None,
            "发货时间": _format_date(shipped_on, order_id, "ship_format"),
            "签收时间": _format_date(delivered_on, order_id, "delivery_format"),
            "退款原因": refund_reason,
        })

    duplicates = rng.sample(orders, k=int(rows * 0.03))
    orders.extend(dict(row) for row in duplicates)
    rng.shuffle(orders)
    return pd.DataFrame(orders)


def generate_catalog() -> pd.DataFrame:
    """The product master: one row per SKU, including the ones that never sold."""
    return pd.DataFrame(
        [
            {
                "商品ID": product_id,
                "商品名称": product_name,
                "品类": category,
                "品牌": brand,
                "单价": price,
                "在售状态": "在售",
            }
            for product_id, product_name, category, brand, price in PRODUCTS
        ],
        columns=CATALOG_COLUMNS,
    )


def generate_traffic(orders: pd.DataFrame, days: int = 366) -> pd.DataFrame:
    """Channel x day funnel counts.

    ``下单数`` is counted from the orders themselves -- deduplicated the same
    way :func:`pipeline.clean_orders` deduplicates, and restricted to rows whose
    channel is known *and* whose date parses. That makes ``sum(下单数)``
    reconcile with the cleaned order table exactly, instead of approximately,
    which is what the conservation check in the validation layer asserts.
    """
    deduped = orders.drop_duplicates(subset=["订单号"], keep="first")
    parsed = deduped.assign(_date=deduped["日期"].map(parse_date))
    counted = (
        parsed[parsed["渠道"].notna() & parsed["_date"].notna()]
        .groupby(["渠道", "_date"])
        .size()
    )
    counts = {(str(channel), date.date()): int(size) for (channel, date), size in counted.items()}

    rows: list[dict[str, object]] = []
    for offset in range(days):
        day = TRAFFIC_START + dt.timedelta(days=offset)
        for channel in CHANNELS:
            key = f"{channel}|{day.isoformat()}"
            placed = counts.get((channel, day), 0)
            # A floor of organic visitors keeps exposure non-zero on days with no
            # orders, so the funnel still has a shape to show.
            base_visitors = 10 + int(_q(key, "base_visitors") * 40)
            visitors = base_visitors + placed * CHANNEL_VISITORS_PER_ORDER[channel]
            carts = max(placed, round(visitors * (0.20 + 0.15 * _q(key, "cart_rate"))))
            exposure = round(visitors * (4.0 + 3.0 * _q(key, "exposure")))
            rows.append({
                "日期": day.isoformat(),
                "渠道": channel,
                "曝光数": exposure,
                "访客数": visitors,
                "加购数": carts,
                "下单数": placed,
            })
    return pd.DataFrame(rows, columns=TRAFFIC_COLUMNS)


def read_traffic(path: Path) -> pd.DataFrame:
    """Read the traffic table, keeping only rows whose date parses."""
    frame = pd.read_csv(path, encoding="utf-8-sig")
    missing = [column for column in TRAFFIC_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing traffic columns: {', '.join(missing)}")
    frame = frame[TRAFFIC_COLUMNS].copy()
    frame["日期"] = frame["日期"].map(parse_date)
    for column in ["曝光数", "访客数", "加购数", "下单数"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype("int64")
    frame["渠道"] = frame["渠道"].fillna("未知")
    return frame[frame["日期"].notna()].reset_index(drop=True)


def read_catalog(path: Path) -> pd.DataFrame:
    """Read the product master."""
    frame = pd.read_csv(path, encoding="utf-8-sig")
    missing = [column for column in CATALOG_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing catalog columns: {', '.join(missing)}")
    frame = frame[CATALOG_COLUMNS].copy()
    frame["单价"] = pd.to_numeric(frame["单价"], errors="coerce")
    return frame


def write_demo(output: Path, rows: int = 3000, seed: int = 20240601) -> dict[str, object]:
    """Write the orders, traffic, and catalogue files, plus the manifest."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame = generate_orders(rows=rows, seed=seed)
    frame.to_csv(output, index=False, encoding="utf-8-sig")

    traffic = generate_traffic(frame)
    traffic_path = output.parent / "synthetic_traffic.csv"
    traffic.to_csv(traffic_path, index=False, encoding="utf-8-sig")

    catalog = generate_catalog()
    catalog_path = output.parent / "synthetic_products.csv"
    catalog.to_csv(catalog_path, index=False, encoding="utf-8-sig")

    manifest = {
        "dataset": "synthetic e-commerce orders",
        "seed": seed,
        "base_unique_orders": rows,
        "rows_with_duplicates": len(frame),
        "duplicate_rows": int(frame["订单号"].duplicated().sum()),
        "traffic_rows": len(traffic),
        "catalog_rows": len(catalog),
        "unsold_products": sorted(UNSOLD_PRODUCT_IDS),
        "notice": "Synthetic practice data. Not real company or customer data.",
    }
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest
