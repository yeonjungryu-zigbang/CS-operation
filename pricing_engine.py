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


def _to_krw(amount: float, currency: str, rates: dict, override_rate: Optional[float] = None) -> float:
    currency = currency.strip().upper()
    if currency == 'KRW':
        return amount
    if currency == 'USD':
        rate = override_rate if override_rate else rates['USD']
        return amount * rate
    if currency == 'CNY':
        rate = override_rate if override_rate else rates['CNY']
        return amount * rate
    return amount


def _normalize(s: str) -> str:
    return re.sub(r'[\s\-_]', '', s).upper()


def _find_model(rows: list, model_name: str) -> Optional[list]:
    query = _normalize(model_name)
    for row in rows[3:]:
        if len(row) <= COL_MODEL:
            continue
        cell = _normalize(str(row[COL_MODEL]))
        if query in cell or cell in query:
            return row
    return None


def _find_models_by_prefix(rows: list, prefix: str) -> list:
    """부분 코드로 일치하는 모든 모델 반환"""
    query = _normalize(prefix.rstrip('*').rstrip())
    result = []
    seen = set()
    for row in rows[3:]:
        if len(row) <= COL_MODEL:
            continue
        cell = _normalize(str(row[COL_MODEL]))
        if cell.startswith(query) and cell not in seen:
            result.append(row)
            seen.add(cell)
    return result


def _calc_row(row: list, rates: dict, new_rate: Optional[float] = None):
    """행에서 사입가/출고가/공헌이익 계산. dict 반환"""
    purchase = _to_number(row[COL_PURCHASE]) if len(row) > COL_PURCHASE else None
    sale = _to_number(row[COL_SALE]) if len(row) > COL_SALE else None
    sale_currency = (row[7] if len(row) > 7 else 'KRW').strip().upper()
    purchase_currency = (row[9] if len(row) > 9 else 'KRW').strip().upper()

    p_krw = None
    s_krw = None
    margin = None
    margin_rate = None

    if purchase is not None:
        p_krw = _to_krw(purchase, purchase_currency, rates,
                         new_rate if purchase_currency != 'KRW' else None)
    if sale is not None:
        s_krw = _to_krw(sale, sale_currency, rates)
    if p_krw is not None and s_krw is not None and s_krw != 0:
        margin = s_krw - p_krw
        margin_rate = (margin / s_krw) * 100

    return {
        'model': row[COL_MODEL],
        'purchase_raw': purchase,
        'purchase_currency': purchase_currency,
        'p_krw': p_krw,
        's_krw': s_krw,
        'margin': margin,
        'margin_rate': margin_rate,
    }


def _parse_question(question: str) -> dict:
    result = {'model': None, 'exchange_rate': None, 'query_type': None, 'is_prefix': False}

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
    else:
        # 질문 유형 없으면 전체 요약 출력
        result['query_type'] = '전체'

    # * 포함 여부 확인
    if '*' in question:
        result['is_prefix'] = True

    candidates = re.findall(r'[A-Za-z][A-Za-z0-9가-힣\-\*]+', question)
    skip = {'purchase', 'price', 'model', 'usd', 'cny'}
    for c in candidates:
        if c.lower() not in skip and len(c) >= 3:
            result['model'] = c
            break

    return result


def _format_summary_table(rows_data: list, new_rate: Optional[float], rates: dict) -> str:
    """여러 모델 전체 요약 테이블"""
    rate_info = f"  (환율 {_fmt(new_rate)}원 적용)" if new_rate else f"  (기준환율 USD {_fmt(rates['USD'])}원)"
    lines = [f"*모델 가격 요약*{rate_info}", ""]

    for d in rows_data:
        model = d['model']
        lines.append(f"*{model}*")
        if d['p_krw'] is not None:
            if d['purchase_currency'] != 'KRW':
                lines.append(f"  • 사입가: {d['purchase_currency']} {_fmt(d['purchase_raw'])} → *{_fmt(d['p_krw'])}원*")
            else:
                lines.append(f"  • 사입가: *{_fmt(d['p_krw'])}원*")
        else:
            lines.append(f"  • 사입가: 데이터 없음")

        if d['s_krw'] is not None:
            lines.append(f"  • 출고가: *{_fmt(d['s_krw'])}원*")
        else:
            lines.append(f"  • 출고가: 데이터 없음")

        if d['margin'] is not None:
            lines.append(f"  • 공헌이익: *{_fmt(d['margin'])}원*  |  공헌이익율: *{d['margin_rate']:.1f}%*")
        else:
            lines.append(f"  • 공헌이익: 계산 불가")
        lines.append("")

    return '\n'.join(lines).rstrip()


def answer_pricing_question(question: str, rows: list) -> str:
    parsed = _parse_question(question)
    new_rate = parsed['exchange_rate']
    rates = _get_base_rates(rows)

    if not parsed['model']:
        return "모델명을 찾을 수 없습니다.\n예시: `SHN-5380FA 사입가 알려줘` 또는 `SHP-P52* 전체 조회`"

    # ── 부분 코드(prefix) 검색 ────────────────────────────────────
    if parsed['is_prefix'] or parsed['query_type'] == '전체':
        prefix = parsed['model'].rstrip('*')
        matched = _find_models_by_prefix(rows, prefix)

        if not matched:
            # prefix 매칭 없으면 단일 모델 검색 시도
            row = _find_model(rows, parsed['model'])
            if row is None:
                return f"*{parsed['model']}* 로 시작하는 모델을 찾을 수 없습니다."
            matched = [row]

        rows_data = [_calc_row(r, rates, new_rate) for r in matched]
        return _format_summary_table(rows_data, new_rate, rates)

    # ── 단일 모델 조회 ────────────────────────────────────────────
    if not parsed['query_type']:
        return "질문 유형을 파악하지 못했습니다.\n`사입가`, `출고가`, `공헌이익` 중 하나를 포함해 질문해주세요."

    row = _find_model(rows, parsed['model'])
    if row is None:
        # 단일 모델 못 찾으면 prefix 검색으로 폴백
        matched = _find_models_by_prefix(rows, parsed['model'])
        if matched:
            rows_data = [_calc_row(r, rates, new_rate) for r in matched]
            return _format_summary_table(rows_data, new_rate, rates)
        return f"*{parsed['model']}* 모델을 찾을 수 없습니다. 제품코드를 확인해주세요."

    model_code = row[COL_MODEL]
    d = _calc_row(row, rates, new_rate)

    if parsed['query_type'] == '사입가':
        if d['p_krw'] is None:
            return f"*{model_code}* 사입가 데이터가 없습니다."
        if d['purchase_currency'] != 'KRW':
            rate_used = new_rate if new_rate else rates.get(d['purchase_currency'], 1)
            header = f"*{model_code}* 사입가"
            if new_rate:
                header += f"  (환율 {_fmt(new_rate)}원 적용)"
            return (
                f"{header}\n\n"
                f"• 원가: {d['purchase_currency']} {_fmt(d['purchase_raw'])}\n"
                f"• 적용 환율: {_fmt(rate_used)}원\n"
                f"• 사입가(KRW): *{_fmt(d['p_krw'])}원*"
            )
        return f"*{model_code}* 사입가\n\n• *{_fmt(d['p_krw'])}원*"

    if parsed['query_type'] == '출고가':
        if d['s_krw'] is None:
            return f"*{model_code}* 출고가 데이터가 없습니다."
        return f"*{model_code}* 출고가\n\n• *{_fmt(d['s_krw'])}원*"

    if parsed['query_type'] == '공헌이익':
        if d['p_krw'] is None or d['s_krw'] is None:
            return f"*{model_code}* 가격 데이터가 부족합니다.\n(출고가: {row[COL_SALE] if len(row) > COL_SALE else '없음'}, 사입가: {row[COL_PURCHASE] if len(row) > COL_PURCHASE else '없음'})"
        if d['s_krw'] == 0:
            return f"*{model_code}* 출고가가 0입니다."
        header = f"*{model_code}* 공헌이익"
        if new_rate:
            header += f"  (환율 {_fmt(new_rate)}원 적용)"
        rate_info = ""
        if d['purchase_currency'] != 'KRW':
            rate_used = new_rate if new_rate else rates.get(d['purchase_currency'], 1)
            rate_info = f"\n• 적용 환율: {_fmt(rate_used)}원 ({d['purchase_currency']})"
        return (
            f"{header}\n\n"
            f"• 출고가: {_fmt(d['s_krw'])}원\n"
            f"• 사입가: {_fmt(d['p_krw'])}원{rate_info}\n"
            f"• 공헌이익: *{_fmt(d['margin'])}원*\n"
            f"• 공헌이익율: *{d['margin_rate']:.1f}%*"
        )

    return "처리할 수 없는 질문입니다."
