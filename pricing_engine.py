"""
규칙 기반 가격 조회 엔진

시트 구조:
  Row0: ..., 기준환율(USD), 1,470
  Row1: ..., 기준환율(CNY), 201
  Row2: 헤더 (Category, Vendor, Logo, Region, Model, Description, Currency, Sales Price, Currency, Purchase Price, ...)
  Row3~: 데이터

컬럼 인덱스:
  [5]  : Model
  [7]  : Currency (Sales)
  [8]  : Sales Price (출고가)
  [9]  : Currency (Purchase)
  [10] : Purchase Price (사입가)
  [11] : 환율값 (Row0=USD, Row1=CNY)
"""

import re
from typing import Optional

COL_MODEL = 5
COL_SALE = 8
COL_PURCHASE = 10

_USD_ROW, _USD_COL = 0, 11
_CNY_ROW, _CNY_COL = 1, 11


def _to_number(s) -> Optional[float]:
    try:
        return float(str(s).replace(',', '').replace('%', '').replace('원', '').strip())
    except Exception:
        return None


def _fmt(n: float) -> str:
    return f"{int(round(n)):,}"


def _get_base_rates(rows: list) -> dict:
    rates = {'USD': 1470.0, 'CNY': 201.0}
    try:
        usd = _to_number(rows[_USD_ROW][_USD_COL])
        if usd:
            rates['USD'] = usd
    except Exception:
        pass
    try:
        cny = _to_number(rows[_CNY_ROW][_CNY_COL])
        if cny:
            rates['CNY'] = cny
    except Exception:
        pass
    return rates


def _find_model(rows: list, model_name: str) -> Optional[list]:
    query = re.sub(r'[\s\-_]', '', model_name).upper()
    for row in rows[3:]:
        if len(row) <= COL_MODEL:
            continue
        cell = re.sub(r'[\s\-_]', '', str(row[COL_MODEL])).upper()
        if query in cell or cell in query:
            return row
    return None


def _parse_question(question: str) -> dict:
    result = {'model': None, 'exchange_rate': None, 'query_type': None}

    m = re.search(r'환율\s*[:\s]?\s*([\d,]+)', question)
    if not m:
        m = re.search(r'([\d,]{4,})\s*원', question)
    if m:
        result['exchange_rate'] = _to_number(m.group(1))

    if '공헌이익' in question:
        result['query_type'] = '공헌이익'
    elif '사입가' in question or 'purchase' in question.lower():
        result['query_type'] = '사입가'
    elif '출고가' in question or '판매가' in question:
        result['query_type'] = '출고가'

    candidates = re.findall(r'[A-Za-z][A-Za-z0-9가-힣\-]+', question)
    skip = {'purchase', 'price', 'model', 'usd', 'cny'}
    for c in candidates:
        if c.lower() not in skip and len(c) >= 3:
            result['model'] = c
            break

    return result


def answer_pricing_question(question: str, rows: list) -> str:
    parsed = _parse_question(question)

    if not parsed['model']:
        return "모델명을 찾을 수 없습니다.\n예시: `SHN-5380FA 사입가 알려줘`"
    if not parsed['query_type']:
        return "질문 유형을 파악하지 못했습니다.\n`사입가`, `출고가`, `공헌이익` 중 하나를 포함해 질문해주세요."

    row = _find_model(rows, parsed['model'])
    if row is None:
        return f"*{parsed['model']}* 모델을 찾을 수 없습니다. 제품코드를 확인해주세요."

    model_code = row[COL_MODEL]
    purchase = _to_number(row[COL_PURCHASE]) if len(row) > COL_PURCHASE else None
    sale = _to_number(row[COL_SALE]) if len(row) > COL_SALE else None
    sale_currency = row[7] if len(row) > 7 else 'KRW'
    purchase_currency = row[9] if len(row) > 9 else 'KRW'

    new_rate = parsed['exchange_rate']
    base_usd = _get_base_rates(rows)['USD']

    if parsed['query_type'] == '사입가':
        if purchase is None:
            return f"*{model_code}* 사입가 데이터가 없습니다."
        if new_rate:
            foreign = purchase / base_usd
            converted = foreign * new_rate
            return (
                f"*{model_code}* 사입가  (환율 {_fmt(new_rate)}원 적용)\n\n"
                f"• 기준 사입가: {_fmt(purchase)}{purchase_currency}\n"
                f"• 재환산 사입가: *{_fmt(converted)}원*  (${foreign:,.1f} × {_fmt(new_rate)})"
            )
        return f"*{model_code}* 사입가\n\n• *{_fmt(purchase)}{purchase_currency}*"

    if parsed['query_type'] == '출고가':
        if sale is None:
            return f"*{model_code}* 출고가 데이터가 없습니다."
        return f"*{model_code}* 출고가\n\n• *{_fmt(sale)}{sale_currency}*"

    if parsed['query_type'] == '공헌이익':
        if purchase is None or sale is None or sale == 0:
            return f"*{model_code}* 가격 데이터가 부족합니다."
        p_krw = (purchase / base_usd) * new_rate if new_rate else purchase
        margin = sale - p_krw
        margin_rate = (margin / sale) * 100
        header = f"*{model_code}* 공헌이익"
        if new_rate:
            header += f"  (환율 {_fmt(new_rate)}원 적용)"
        return (
            f"{header}\n\n"
            f"• 출고가: {_fmt(sale)}{sale_currency}\n"
            f"• 사입가: {_fmt(p_krw)}원\n"
            f"• 공헌이익: *{_fmt(margin)}원*\n"
            f"• 공헌이익율: *{margin_rate:.1f}%*"
        )

    return "처리할 수 없는 질문입니다."
