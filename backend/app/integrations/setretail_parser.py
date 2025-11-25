import xml.etree.ElementTree as ET
from typing import List

from app.schemas.purchases import Purchase, PurchasePosition, PurchasePayment


def parse_purchases_xml(xml_bytes: bytes) -> List[Purchase]:
    """
    Парсит XML, который вернул SetRetail (purchases/purchase/positions/payments),
    и превращает его в список Pydantic-моделей Purchase.
    """
    root = ET.fromstring(xml_bytes)

    purchases: List[Purchase] = []

    for p_node in root.findall("purchase"):
        purchase_kwargs = {
            "tab_number": p_node.get("tabNumber", ""),
            "user_name": p_node.get("userName", ""),
            "operation_type": p_node.get("operationType", "true") == "true",
            "oper_day": p_node.get("operDay", ""),
            "shop": p_node.get("shop", ""),
            "cash": p_node.get("cash", ""),
            "shift": p_node.get("shift", ""),
            "number": p_node.get("number", ""),
            "sale_time": p_node.get("saletime", ""),
            "amount": float(p_node.get("amount", "0") or 0),
            "discount_amount": float(p_node.get("discountAmount", "0") or 0),
            "inn": p_node.get("inn", ""),
            "status": p_node.get("status", ""),
            "positions": [],
            "payments": [],
        }

        # Позиции чека
        positions_node = p_node.find("positions")
        if positions_node is not None:
            for pos_node in positions_node.findall("position"):
                position = PurchasePosition(
                    order=int(pos_node.get("order", "0") or 0),
                    goods_code=pos_node.get("goodsCode", ""),
                    bar_code=pos_node.get("barCode"),
                    count=float(pos_node.get("count", "0") or 0),
                    cost=float(pos_node.get("cost", "0") or 0),
                    nds=float(pos_node.get("nds", "0") or 0),
                    amount=float(pos_node.get("amount", "0") or 0),
                )
                purchase_kwargs["positions"].append(position)

        # Платежи по чеку
        payments_node = p_node.find("payments")
        if payments_node is not None:
            for pay_node in payments_node.findall("payment"):
                payment = PurchasePayment(
                    type_class=pay_node.get("typeClass", ""),
                    amount=float(pay_node.get("amount", "0") or 0),
                )
                purchase_kwargs["payments"].append(payment)

        purchases.append(Purchase(**purchase_kwargs))

    return purchases
