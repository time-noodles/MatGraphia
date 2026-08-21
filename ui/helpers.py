# MatGraphia UI ヘルパー関数
# ラベル生成, JSON処理, CIF正規化, 系統表示など共通ユーティリティ
import os
import re
import json
import file_manager as fm

# 元素周期表の原子量 (g/mol) テーブル (高速計算用)
ATOMIC_WEIGHTS={
    "H":1.008,"He":4.0026,"Li":6.94,"Be":9.0122,"B":10.81,"C":12.011,"N":14.007,"O":15.999,
    "F":18.998,"Ne":20.180,"Na":22.990,"Mg":24.305,"Al":26.982,"Si":28.085,"P":30.974,"S":32.06,
    "Cl":35.45,"Ar":39.948,"K":39.098,"Ca":40.078,"Sc":44.956,"Ti":47.867,"V":50.942,"Cr":51.996,
    "Mn":54.938,"Fe":55.845,"Co":58.933,"Ni":58.693,"Cu":63.546,"Zn":65.38,"Ga":69.723,"Ge":72.63,
    "As":74.922,"Se":78.971,"Br":79.904,"Kr":83.798,"Rb":85.468,"Sr":87.62,"Y":88.906,"Zr":91.224,
    "Nb":92.906,"Mo":95.95,"Tc":98.0,"Ru":101.07,"Rh":102.91,"Pd":106.42,"Ag":107.87,"Cd":112.41,
    "In":114.82,"Sn":118.71,"Sb":121.76,"Te":127.60,"I":126.90,"Xe":131.29,"Cs":132.91,"Ba":137.33,
    "La":138.91,"Ce":140.12,"Pr":140.91,"Nd":144.24,"Pm":145.0,"Sm":150.36,"Eu":151.96,"Gd":157.25,
    "Tb":158.93,"Dy":162.50,"Ho":164.93,"Er":167.26,"Tm":168.93,"Yb":173.05,"Lu":174.97,"Hf":178.49,
    "Ta":180.95,"W":183.84,"Re":186.21,"Os":190.23,"Ir":192.22,"Pt":195.08,"Au":196.97,"Hg":200.59,
    "Tl":204.38,"Pb":207.20,"Bi":208.98,"Po":209.0,"At":210.0,"Rn":222.0,"Fr":223.0,"Ra":226.0,
    "Ac":227.0,"Th":232.04,"Pa":231.04,"U":238.03,"Np":237.0,"Pu":244.0
}


def get_atomic_weight(symbol:str)->float|None:
    """単体元素の原子量を返す"""
    if not symbol:return None
    sym=symbol.strip()
    if sym in ATOMIC_WEIGHTS:
        return ATOMIC_WEIGHTS[sym]
    try:
        from pymatgen.core import Element
        return float(Element(sym).atomic_mass)
    except Exception:
        return None


def calc_molecular_weight(formula_str:str)->float|None:
    """化学式文字列から分子量を高速計算する"""
    if not formula_str or formula_str in ["(新規作成)","None","-"]:return None
    s=formula_str.strip()
    try:
        matches=re.findall(r"([A-Z][a-z]*)(\d*\.?\d*)",s)
        if matches and "".join(m[0]+m[1] for m in matches)==s:
            total=0.0
            for elem,count_str in matches:
                if elem not in ATOMIC_WEIGHTS:
                    raise ValueError(f"Unknown element: {elem}")
                count=float(count_str) if count_str else 1.0
                total+=ATOMIC_WEIGHTS[elem]*count
            return total
    except Exception:
        pass
    try:
        from pymatgen.core import Composition
        return float(Composition(s).weight)
    except Exception:
        return None



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
