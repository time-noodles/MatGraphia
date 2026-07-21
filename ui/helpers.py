# MatGraphia UI ヘルパー関数
# ラベル生成, JSON処理, CIF正規化, 系統表示など共通ユーティリティ
import os
import re
import json
import file_manager as fm


def _json_or_raw(value):
    """JSON文字列をパースして返す。失敗したら元の値を返す"""
    if isinstance(value,str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _resolve_data_abs_path(rel_path):
    """相対パスをdata/以下の絶対パスに解決する"""
    if not rel_path:
        return None
    p=os.path.join(str(fm.BASE_DIR),str(rel_path))
    return p if os.path.exists(p) else None


def get_sample_ancestry(sample_id,samples_list,events_dict,current_depth=0):
    """サンプルの系統(親子関係)を文字列として構築する"""
    if current_depth>5:
        return "..."
    s=next((x for x in samples_list if x["sample_id"]==sample_id),None)
    if not s:
        return ""
    e=events_dict.get(s["source_event_id"])
    if not e:
        return s["human_id"]

    parent_sample_id=e.get("input_sample_id")
    current_node=f"{s['human_id']}({s['form']})"
    if parent_sample_id:
        parent_str=get_sample_ancestry(parent_sample_id,samples_list,events_dict,current_depth+1)
        return f"{current_node} <- [{e['event_type']} / {e['target_material']}] <- {parent_str}"
    else:
        return f"{current_node} <- [{e['event_type']} on {e['target_material']}]"


def _normalize_cif_fraction_tokens(cif_bytes):
    """CIF内の分数表記(例: 1/3)を小数表記に正規化する"""
    try:
        text=cif_bytes.decode("utf-8")
    except Exception:
        return cif_bytes

    def frac_to_decimal(token):
        m=re.fullmatch(r"([+-]?\d+)\s*/\s*(\d+)",token)
        if not m:
            return token
        den=int(m.group(2))
        if den==0:
            return token
        num=int(m.group(1))
        return f"{num/den:.10f}".rstrip("0").rstrip(".")

    out_lines=[]
    for line in text.splitlines():
        stripped=line.strip()
        if not stripped or stripped.startswith("#"):
            out_lines.append(line)
            continue
        # クォートされたシンメトリ操作はそのまま
        if "'" in line or '"' in line:
            out_lines.append(line)
            continue

        parts=re.split(r"(\s+)",line)
        fixed=[frac_to_decimal(p) if p and not p.isspace() else p for p in parts]
        out_lines.append("".join(fixed))

    try:
        return ("\n".join(out_lines)+"\n").encode("utf-8")
    except Exception:
        return cif_bytes


# --------------------------------------------------
# ラベル生成関数 (要件6: 備考・結果等を表示)
# --------------------------------------------------
def build_event_label(e,samples_dict=None):
    """イベント選択用のリッチラベルを生成する
    [日付] イベント種別 on 物質名 | 備考:xxx | #ID
    """
    parts=[f"[{e['created_at'][:10]}]",f"{e['event_type']} on {e['target_material']}"]
    if e.get("remarks"):
        # 備考の先頭30文字を表示
        remarks_short=str(e["remarks"])[:30].replace("\n"," ")
        parts.append(f"| 備考:{remarks_short}")
    parts.append(f"#{e['event_id'][:4]}")
    return " ".join(parts)


def build_sample_label(s,events_dict=None,samples_list=None):
    """サンプル選択用のリッチラベルを生成する
    [日付] 系統表示 | 場所:xxx | 備考:xxx | #ID
    """
    if samples_list and events_dict:
        ancestry=get_sample_ancestry(s["sample_id"],samples_list,events_dict)
    else:
        ancestry=s["human_id"]
    parts=[f"[{s['created_at'][:10]}]",ancestry]
    if s.get("location"):
        parts.append(f"| 場所:{str(s['location'])[:20]}")
    if s.get("remarks"):
        remarks_short=str(s["remarks"])[:30].replace("\n"," ")
        parts.append(f"| 備考:{remarks_short}")
    parts.append(f"#{s['sample_id'][:4]}")
    return " ".join(parts)


def build_literature_label(l):
    """文献選択用のリッチラベルを生成する
    [タイプ] タイトルorDOI | 備考:xxx | #ID
    """
    disp=l["title"] if l["title"] else l["doi"]
    parts=[f"[{l['literature_type']}]",disp]
    if l.get("remarks"):
        remarks_short=str(l["remarks"])[:30].replace("\n"," ")
        parts.append(f"| 備考:{remarks_short}")
    parts.append(f"#{l['literature_id'][:4]}")
    return " ".join(parts)


def build_measurement_label(m,samples_dict=None):
    """測定選択用のリッチラベルを生成する
    [日付] 測定タイプ | サンプル:xxx | 測定者:xxx | 備考:xxx | #ID
    """
    parts=[f"[{m['measured_at'][:10]}]",m["measurement_type"]]
    if samples_dict and m.get("sample_id"):
        sname=samples_dict.get(m["sample_id"])
        if sname:
            parts.append(f"| {sname}")
    if m.get("operator"):
        parts.append(f"| {m['operator']}")
    if m.get("remarks"):
        remarks_short=str(m["remarks"])[:30].replace("\n"," ")
        parts.append(f"| 備考:{remarks_short}")
    parts.append(f"#{m['measurement_id'][:4]}")
    return " ".join(parts)


def log_errors(page_name:str):
    def decorator(func):
        import functools
        @functools.wraps(func)
        def wrapper(*args,**kwargs):
            try:
                return func(*args,**kwargs)
            except Exception as e:
                import traceback
                import uuid
                import database as db
                import streamlit as st
                tb_str=traceback.format_exc()
                log_id=str(uuid.uuid4())
                try:
                    db.insert_developer_log(
                        log_id=log_id,
                        log_type="Error",
                        title=f"Error in {page_name}: {type(e).__name__}",
                        content=tb_str,
                        page_name=page_name
                    )
                except Exception:
                    pass
                st.exception(e)
        return wrapper
    return decorator
