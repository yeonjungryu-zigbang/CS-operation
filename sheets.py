import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID = "1FQyGMK9ac8SUYdUxIjEMx_DTg45JnGbCyg9uhHUlpN0"
PRICING_SPREADSHEET_ID = "1vRHJoIBr8xHafpSwyVwj9htIXHRlw38N"
PRICING_SHEET_GID = 32118780
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _get_service():
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON 환경변수가 설정되지 않았습니다.")
    creds_info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def get_all_sheets() -> list[dict]:
    """스프레드시트의 모든 시트 목록 반환"""
    service = _get_service()
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    return [
        {"id": s["properties"]["sheetId"], "title": s["properties"]["title"]}
        for s in meta.get("sheets", [])
    ]


def get_sheet_data(sheet_name: str = None, gid: int = None) -> dict:
    """시트 데이터를 딕셔너리로 반환. sheet_name 또는 gid로 시트 지정."""
    service = _get_service()

    if gid is not None and sheet_name is None:
        meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        for s in meta.get("sheets", []):
            if s["properties"]["sheetId"] == gid:
                sheet_name = s["properties"]["title"]
                break

    range_name = f"'{sheet_name}'!A1:ZZ" if sheet_name else "A1:ZZ"

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=range_name)
        .execute()
    )
    rows = result.get("values", [])
    return {"sheet_name": sheet_name, "rows": rows, "total_rows": len(rows)}


def get_all_data_as_text() -> str:
    """모든 시트 데이터를 텍스트로 반환 (Claude 컨텍스트용)"""
    sheets = get_all_sheets()
    parts = []
    for sheet in sheets:
        try:
            data = get_sheet_data(sheet_name=sheet["title"])
            rows = data["rows"]
            if not rows:
                continue
            lines = [f"\n### 시트: {sheet['title']} ###"]
            for row in rows:
                lines.append("\t".join(str(cell) for cell in row))
            parts.append("\n".join(lines))
        except Exception as e:
            parts.append(f"\n### 시트: {sheet['title']} - 읽기 실패: {e} ###")
    return "\n\n".join(parts)


def get_pricing_data_as_text() -> str:
    """가격 스프레드시트(gid=32118780) 데이터를 텍스트로 반환"""
    service = _get_service()

    # gid로 시트명 찾기
    meta = service.spreadsheets().get(spreadsheetId=PRICING_SPREADSHEET_ID).execute()
    sheet_name = None
    for s in meta.get("sheets", []):
        if s["properties"]["sheetId"] == PRICING_SHEET_GID:
            sheet_name = s["properties"]["title"]
            break

    range_name = f"'{sheet_name}'!A1:ZZ" if sheet_name else "A1:ZZ"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=PRICING_SPREADSHEET_ID, range=range_name)
        .execute()
    )
    rows = result.get("values", [])
    if not rows:
        return "가격 데이터가 없습니다."

    lines = [f"### 시트: {sheet_name} ###"]
    for row in rows:
        lines.append("\t".join(str(cell) for cell in row))
    return "\n".join(lines)


def get_default_sheet_data_as_text() -> str:
    """기본 시트(gid=355262105) 데이터를 텍스트로 반환"""
    data = get_sheet_data(gid=355262105)
    rows = data["rows"]
    if not rows:
        return "데이터가 없습니다."
    lines = [f"### 시트: {data['sheet_name']} ###"]
    for row in rows:
        lines.append("\t".join(str(cell) for cell in row))
    return "\n".join(lines)
