# backend/app/schemas/purchases.py
from typing import List, Optional
from pydantic import BaseModel


class PurchasePosition(BaseModel):
    order: int                      # порядок в чеке
    goods_code: str                 # код товара
    bar_code: Optional[str] = None  # штрихкод
    count: float                    # количество
    cost: float                     # цена за единицу
    nds: Optional[float] = None     # ставка НДС
    amount: float                   # сумма по позиции


class PurchasePayment(BaseModel):
    type_class: str                 # тип платежа (CashPaymentEntity и т.п.)
    amount: float                   # сумма платежа


class Purchase(BaseModel):
    tab_number: str                 # табельный номер кассира
    user_name: str                  # имя кассира
    operation_type: bool            # true = продажа, false = возврат
    oper_day: str                   # операционный день
    shop: str                       # магазин
    cash: str                       # касса
    shift: str                      # смена
    number: str                     # номер чека
    sale_time: str                  # время продажи
    amount: float                   # сумма чека
    discount_amount: float          # сумма скидки
    inn: str                        # ИНН
    status: str                     # статус (REGISTERED и т.п.)

    positions: List[PurchasePosition] = []
    payments: List[PurchasePayment] = []
