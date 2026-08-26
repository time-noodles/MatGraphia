SCHEMA = {
    "type": "SEM",
    "fields": [
        {"name": "instrument", "type": "str", "label": "装置名", "default": "JSM-IT700HR"},
        {"name": "accelerating_voltage_kv", "type": "float", "label": "加速電圧", "default": 20.0}
    ],
    "tables": [
        {
            "name": "at_percent_table",
            "label": "EDX組成 (At%)",
            "columns": [
                {"name": "element", "type": "str"},
                {"name": "at_percent", "type": "float"}
            ],
            "init_data": []
        }
    ]
}

import io
import re

try:
    import pdfplumber
except Exception:
    pdfplumber = None


def _is_number_token(token: str) -> bool:
    return bool(re.match(r"^[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?$", str(token).strip()))


def _split_table_line(line: str) -> list[str]:
    tokens = str(line).strip().split()
    if not tokens:
        return []
    first_num_idx = None
    for idx, token in enumerate(tokens):
        if _is_number_token(token):
            first_num_idx = idx
            break
    if first_num_idx is None or first_num_idx == 0:
        return []
    return [" ".join(tokens[:first_num_idx])] + tokens[first_num_idx:]


def _to_float_or_none(value: str):
    try:
        return float(value)
    except Exception:
        return None


def _extract_lines_from_pdf(pdf_bytes: bytes) -> tuple[list[str], str | None]:
    if pdfplumber is None:
        return [], "pdfplumber が未インストールのため PDF 解析できません。"

    lines = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text:
                    lines.extend(text.splitlines())
    except Exception as e:
        return [], f"PDF読み取りに失敗しました: {e}"
    return lines, None


def _extract_accelerating_voltage_kv(lines: list[str]) -> float | None:
    patterns = [
        r"(?:Acc(?:elerating)?\.?\s*V(?:oltage)?|Accelerating\s*Voltage)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(kV|KV|kv|V)?",
        r"\bHV\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(kV|KV|kv|V)?",
    ]

    for line in lines:
        text = str(line)
        for pat in patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if not m:
                continue

            value = _to_float_or_none(m.group(1))
            if value is None:
                continue

            unit = (m.group(2) or "kV").lower()
            if unit == "v":
                value = value / 1000.0

            if 0 < value < 1000:
                return value

    return None


def extract_at_percent_from_pdf(pdf_bytes: bytes) -> tuple[list[dict], str | None]:
    lines, err = _extract_lines_from_pdf(pdf_bytes)
    if err:
        return [], err

    return extract_at_percent_from_lines(lines)


def extract_at_percent_from_lines(lines: list[str]) -> tuple[list[dict], str | None]:
    if not lines:
        return [], "SEMの Element/Wt%/At% テーブルをPDFから検出できませんでした。"

    rows = []
    in_table = False
    for raw_line in lines:
        line = str(raw_line).strip()
        if not line:
            continue

        if ("Element" in line and "Wt" in line and "At" in line) or ("Element Wt" in line):
            in_table = True
            continue

        if in_table and "Total" in line:
            break

        if not in_table:
            continue

        parsed = _split_table_line(line)
        if len(parsed) < 2:
            continue

        element = parsed[0]
        # 標準は [Element, Wt%, At%, ...] のためAt%は3列目、Wt%が無い形式は2列目を採用
        at_token = parsed[2] if len(parsed) >= 3 else parsed[1]
        at_percent = _to_float_or_none(at_token)
        if at_percent is None:
            continue

        rows.append({
            "element": element,
            "at_percent": at_percent
        })

    if not rows:
        return [], "SEMの Element/Wt%/At% テーブルをPDFから検出できませんでした。"
    return rows, None


def prefill_from_upload(file_name: str, file_bytes: bytes) -> tuple[dict, list[str], list[str]]:
    initial_data = {}
    info_msgs = []
    warn_msgs = []

    if not str(file_name).lower().endswith(".pdf"):
        return initial_data, info_msgs, warn_msgs

    lines, line_err = _extract_lines_from_pdf(file_bytes)
    if line_err:
        warn_msgs.append(line_err)
        return initial_data, info_msgs, warn_msgs

    acc_kv = _extract_accelerating_voltage_kv(lines)
    if acc_kv is not None:
        initial_data["accelerating_voltage_kv"] = round(acc_kv, 4)
        info_msgs.append(f"SEM PDFから加速電圧を抽出しました: {acc_kv:.4g}")

    rows, err = extract_at_percent_from_lines(lines)
    if rows:
        initial_data["at_percent_table"] = rows
        info_msgs.append(f"SEM PDFから At% を {len(rows)} 行抽出しました。必要に応じて下表を編集してください。")
    elif err:
        warn_msgs.append(err)

    return initial_data, info_msgs, warn_msgs


def calculate_composition_ratio(
    at_percent_rows: list[dict],
    selected_elements: list[str],
    target_constant: float = 2.0
) -> tuple[list[dict], str, float, str | None]:
    """
    指定された元素リストの at% の和が target_constant になるように規格化スケールファクターを計算し、
    各元素の組成比（化学量論比）と算出化学式文字列を返す。
    """
    if not at_percent_rows:
        return [], "", 0.0, "EDX at% データが存在しません。"

    if not selected_elements:
        return [], "", 0.0, "組成比計算の対象とする元素を選択してください。"

    selected_at_sum = 0.0
    for r in at_percent_rows:
        elem = str(r.get("element") or "").strip()
        if elem in selected_elements:
            selected_at_sum += float(r.get("at_percent") or 0.0)

    if selected_at_sum <= 0:
        return [], "", 0.0, "選択された元素の at% の合計が 0 以下のため、計算できません。"

    factor = target_constant / selected_at_sum

    ratio_rows = []
    formula_parts = []
    for r in at_percent_rows:
        elem = str(r.get("element") or "").strip()
        at_val = float(r.get("at_percent") or 0.0)
        ratio_val = round(at_val * factor, 3)
        ratio_rows.append({
            "element": elem,
            "at_percent": at_val,
            "ratio": ratio_val,
            "is_selected": elem in selected_elements
        })
        if ratio_val > 0:
            if abs(ratio_val - round(ratio_val)) < 0.02:
                formatted_ratio = str(int(round(ratio_val)))
            else:
                formatted_ratio = f"{ratio_val:.2f}"
            formula_parts.append(f"{elem}{formatted_ratio}")

    formula_str = "".join(formula_parts)
    return ratio_rows, formula_str, factor, None

