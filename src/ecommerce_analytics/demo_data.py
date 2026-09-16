from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

import pandas as pd


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


def generate_orders(rows: int = 3000, seed: int = 20240601) -> pd.DataFrame:
    """Generate intentionally messy synthetic orders for pipeline testing."""
    rng = random.Random(seed)
    _advance_rng_for_companion_user_table(rng)
    orders: list[dict[str, object]] = []

    for i in range(1, rows + 1):
        order_id = f"DD2024{i:05d}"
        product_id, product_name, _, _, price = rng.choice(PRODUCTS)

        date_roll = rng.random()
        if date_roll < 0.02:
            date_value = None
        else:
            date = dt.date(2024, 1, 1) + dt.timedelta(days=rng.randint(0, 364))
            if date_roll < 0.17:
                date_value = f"{date.year}/{date.month}/{date.day}"
            elif date_roll < 0.27:
                date_value = date.strftime("%Y-%m-%d")
            elif date_roll < 0.32:
                date_value = date.strftime("%Y%m%d")
            else:
                date_value = date.isoformat()

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

        status = rng.choices(STATUSES, weights=[0.55, 0.15, 0.10, 0.10, 0.10], k=1)[0]
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

        channel = rng.choices(CHANNELS, weights=[0.35, 0.25, 0.2, 0.12, 0.08], k=1)[0] \
            if rng.random() > 0.01 else None
        user_id = f"U{rng.randint(1, 200):04d}" if rng.random() > 0.02 else None
        province = rng.choice(PROVINCES) if rng.random() > 0.01 else None
        product_id_value = product_id if rng.random() > 0.02 else None

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
        })

    duplicates = rng.sample(orders, k=int(rows * 0.03))
    orders.extend(dict(row) for row in duplicates)
    rng.shuffle(orders)
    return pd.DataFrame(orders)


def write_demo(output: Path, rows: int = 3000, seed: int = 20240601) -> dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)
    frame = generate_orders(rows=rows, seed=seed)
    frame.to_csv(output, index=False, encoding="utf-8-sig")
    manifest = {
        "dataset": "synthetic e-commerce orders",
        "seed": seed,
        "base_unique_orders": rows,
        "rows_with_duplicates": len(frame),
        "duplicate_rows": int(frame["订单号"].duplicated().sum()),
        "notice": "Synthetic practice data. Not real company or customer data.",
    }
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest
