# MatGraphia バリデーションロジック
# 重複判定など
import json


def is_duplicate_event(new_evt,existing_events):
    """イベントの重複判定"""
    for e in existing_events:
        db_input_sample_ids=[]
        db_reference_event_ids=[]
        db_reference_literature_ids=[]
        try:
            db_input_sample_ids=json.loads(e.get("input_sample_ids") or "[]")
        except Exception:
            db_input_sample_ids=[]
        try:
            db_reference_event_ids=json.loads(e.get("reference_event_ids") or "[]")
        except Exception:
            db_reference_event_ids=[]
        try:
            db_reference_literature_ids=json.loads(e.get("reference_literature_ids") or "[]")
        except Exception:
            db_reference_literature_ids=[]

        # 後方互換: 旧単一カラムしか無いレコードを配列扱いへ寄せる
        if not db_input_sample_ids and e.get("input_sample_id"):
            db_input_sample_ids=[e.get("input_sample_id")]
        if not db_reference_event_ids and e.get("reference_event_id"):
            db_reference_event_ids=[e.get("reference_event_id")]
        if not db_reference_literature_ids and e.get("reference_literature_id"):
            db_reference_literature_ids=[e.get("reference_literature_id")]

        if (
            e["project_id"]==new_evt["project_id"]
            and e["target_material"]==new_evt["target_material"]
            and e["event_type"]==new_evt["event_type"]
            and sorted(db_input_sample_ids)==sorted(new_evt.get("input_sample_ids",[]))
            and sorted(db_reference_event_ids)==sorted(new_evt.get("reference_event_ids",[]))
            and sorted(db_reference_literature_ids)==sorted(new_evt.get("reference_literature_ids",[]))
        ):
            try:
                db_params=json.loads(e["parameters"])
                if db_params==new_evt["parameters"]:
                    return True
            except Exception:
                pass
    return False


def is_duplicate_sample(new_smp,existing_samples):
    """サンプルの重複判定"""
    for s in existing_samples:
        if (s["source_event_id"]==new_smp["source_event_id"] and
            s["human_id"]==new_smp["human_id"] and
            s["form"]==new_smp["form"]):
            return True
    return False
