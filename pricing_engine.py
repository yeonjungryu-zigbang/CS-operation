"""
규칙 기반 가격 조회 엔진 (Claude API 불필요)

시트 구조 (시트7 기준):
  Row 0: 시트7, ..., USD, 1350, ...
  Row 1: ..., CNY, 187.26, ...
  Row 2: 헤더 (제품분류, 채널, 제품코드, 판매수량, ..., 사입가, ..., 판매가, ...)
  Row 3: 월 헤더 (9월, 10월, 11월, 12월, 1월, 2월, 3월 × 5개 그룹)
  Row 4~: 데이터

컬럼 인덱스:
  [0]  : (공백)
  [1]  : 제품분류
  [2]  : 채널
  [3]  : 제품코드
  [4~10] : 판매수량 (7개월)
  [11~17]: 사입가 (7개월)
  [18~24]: 판매가 (7개월)
  [25~31]: 매출
  [32~38]: 매출원가
  [39~45]: 매출원가율
  [46]   : 비고
"""

import re
from typing import Optional

MONTHS = ['9월', '10월', '11월', '12월', '1월', '2월', '3월']

COL_MODEL = 3
COL_PURCHASE_START = 11
COL_PURCHASE_END = 18   # exclusive
COL_SALE_START = 18
COL_SALE_END = 25       # exclusive

# 시트에 기재된 기준 환율 위치
_USD_ROW, _USD_COL = 0, 5   # "1,350"
_CNY_ROW, _CNY_COL = 1, 5   # "187.26"


def _to_number(s) -> Optional[float]:
    try:
        return float(str(s).replace(',', '').replace('%', '').replace('원', '').strip())
    except Exception:
        return None


def _fmt(n: float) -> str:
    return f"{int(round(n)):,}"


def _get_base_rates(rows: list) -> dict:
    """시트 상단에서 기준 환율 읽기"""
    rates = {'USD': 1350.0, 'CNY': 187.26}
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
    """모델명으로 데이터 행 찾기 (대소문자/하이픈/공백 무시)"""
    query = re.sub(r'[\s\-_]', '', model_name).upper()
    for row in rows[4:]:   # 데이터는 5번째 행(인덱스 4)부터
        if len(row) <= COL_MODEL:
            continue
        cell = re.sub(r'[\s\-_]', '', str(row[COL_MODEL])).upper()
        if query in cell or cell in query:
            return row
    return None


def _extract(row: list, start: int, end: int) -> list:
    """행에서 숫자 값 추출 (None 포함)"""
    result = []
    for i in range(start, end):
        result.append(_to_number(row[i]) if i < len(row) else None)
    return result


def _parse_question(question: str) -> dict:
    """질문에서 모델명·환율·질문유형 추출"""
    result = {'model': None, 'exchange_rate': None, 'query_type': None}

    # 환율 추출: "환율 1,380", "1380원", "1380 원"
    m = re.search(r'환율\s*[:\s]?\s*([\d,]+)', question)
    if not m:
        m = re.search(r'([\d,]{4,})\s*원', question)
    if m:
        result['exchange_rate'] = _to_number(m.group(1))

    # 질문 유형
    if '공헌이익' in question:
        result['query_type'] = '공헌이익'
    elif '사입가' in question or 'purchase' in question.lower():
        result['query_type'] = '사입가'
    elif '출고가' in question or '판매가' in question:
        result['query_type'] = '출고가'

    # 모델명 추출: 영문+숫자 조합 (예: SHP-DP960SG, ZD-R90-지문)
    # 환율 숫자와 구분하기 위해 알파벳 포함 필수
    candidates = re.findall(r'[A-Za-z][A-Za-z0-9가-힣\-]+', question)
    skip = {'purchase', 'price', 'model', 'usd', 'cny'}
    for c in candidates:
        if c.lower() not in skip and len(c) >= 3:
            result['model'] = c
            break

    return result


def answer_pricing_question(question: str, rows: list) -> str:
    """규칙 기반으로 가격 질문에 답변"""
    parsed = _parse_question(question)

    if not parsed['model']:
        return (
            "모델명을 찾을 수 없습니다.\n"
            "예시: `SHP-DP960SG 사입가 알려줘`"
        )
    if not parsed['query_type']:
        return (
            "질문 유형을 파악하지 못했습니다.\n"
            "`사입가`, `출고가`, `공헌이익` 중 하나를 포함해 질문해주세요."
        )

    row = _find_model(rows, parsed['model'])
    if row is None:
        return f"*{parsed['model']}* 모델을 찾을 수 없습니다. 제품코드를 확인해주세요."

    model_code = row[COL_MODEL]
    purchases = _extract(row, COL_PURCHASE_START, COL_PURCHASE_END)
    sales = _extract(row, COL_SALE_START, COL_SALE_END)

    new_rate = parsed['exchange_rate']
    base_rates = _get_base_rates(rows)
    base_usd = base_rates['USD']

    # ── 사입가 조회 ───────────────────────────────────────────────
    if parsed['query_type'] == '사입가':
        header = f"*{model_code}* 사입가"
        if new_rate:
            header += f"  (환율 {_fmt(new_rate)}원 적용)"
        lines = [header, ""]
        for m, v in zip(MONTHS, purchases):
            if v is None:
                continue
            if new_rate:
                # 기준 환율로 역산 → 외화 금액 → 새 환율 적용
                foreign = v / base_usd
                converted = foreign * new_rate
                lines.append(
                    f"• {m}: {_fmt(v)}원 → *{_fmt(converted)}원*"
                    f"  (${foreign:,.1f} × {_fmt(new_rate)})"
                )
            else:
                lines.append(f"• {m}: *{_fmt(v)}원*")
        return '\n'.join(lines)

    # ── 출고가 조회 ───────────────────────────────────────────────
    if parsed['query_type'] == '출고가':
        lines = [f"*{model_code}* 출고가", ""]
        for m, v in zip(MONTHS, sales):
            if v is None:
                continue
            lines.append(f"• {m}: *{_fmt(v)}원*")
        return '\n'.join(lines)

    # ── 공헌이익 / 공헌이익율 ─────────────────────────────────────
    if parsed['query_type'] == '공헌이익':
        header = f"*{model_code}* 공헌이익 / 공헌이익율"
        if new_rate:
            header += f"  (환율 {_fmt(new_rate)}원 적용)"
        lines = [header, ""]
        for m, p, s in zip(MONTHS, purchases, sales):
            if p is None or s is None or s == 0:
                continue
            if new_rate:
                p_krw = (p / base_usd) * new_rate
            else:
                p_krw = p
            margin = s - p_krw
            margin_rate = (margin / s) * 100
            lines.append(
                f"• {m}: 공헌이익 *{_fmt(margin)}원* | 공헌이익율 *{margin_rate:.1f}%*"
            )
        return '\n'.join(lines)

    return "처리할 수 없는 질문입니다."
