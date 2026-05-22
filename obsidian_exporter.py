import os
import json
import zipfile
import io
import re
import shutil
from datetime import datetime
from typing import List, Dict, Any

def sanitize_tag(name: str) -> str:
    if not name: return "unknown"
    s = re.sub(r"[^a-zA-Z0-9\u4e00-\u9faf\u3040-\u309f\u30a0-\u30ff]", "", name)
    return s if s else "unknown"

def sanitize_filename(name: str) -> str:
    if not name: return "unnamed"
    s = re.sub(r'[\\/:*?"<>|]', "_", name)
    return s[:100]

class ObsidianExporter:
    def __init__(self, db):
        self.db = db
        self.file_map = {} # (type, id) -> relative path without .md
        self.measurement_plot_map = {} # measurement_id -> embedded image file name in vault/zip

    def _prepare_file_map(self):
        # 1. Literature
        for r in self.db.fetch_all_literatures():
            t = r["title"] or r["doi"] or "lit"
            year = r.get("publication_year") or "0000"
            self.file_map[("Literature", r["literature_id"])] = f"Literature/({year}) {sanitize_filename(t)} ({r['literature_id'][:4]})"
        # 2. Event
        for r in self.db.fetch_all_events():
            n = f"{r['event_type']} - {r['target_material']}"
            date = r["created_at"][:10]
            self.file_map[("Event", r["event_id"])] = f"Event/{date} - {sanitize_filename(n)} ({r['event_id'][:4]})"
        # 3. Sample
        for r in self.db.fetch_all_samples():
            n = f"{r['human_id']} ({r['form']})"
            date = r["created_at"][:10]
            self.file_map[("Sample", r["sample_id"])] = f"Sample/{date} - {sanitize_filename(n)} ({r['sample_id'][:4]})"
        # 4. Measurement
        for r in self.db.fetch_all_measurements():
            n = f"{r['measurement_type']} ({r['operator']})"
            date = r["measured_at"][:10]
            self.file_map[("Measurement", r["measurement_id"])] = f"Measurement/{date} - {sanitize_filename(n)} ({r['measurement_id'][:4]})"
        # 5. Material
        for r in self.db.fetch_all_materials():
            self.file_map[("Material", r["material_id"])] = f"Material/{sanitize_filename(r['name'])} ({r['material_id'][:4]})"

    def _get_link(self, etype: str, eid: str) -> str:
        path = self.file_map.get((etype, eid))
        if not path: return f"[[Unknown_{eid}]]"
        return f"[[{os.path.basename(path)}]]"

    def export_all(self) -> bytes:
        self._prepare_file_map()
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            self._collect_measurement_assets_for_zip(zip_file)
            for (etype, eid), rel_path in self.file_map.items():
                content = self._format_entity(etype, eid)
                zip_file.writestr(f"{rel_path}.md", content)
        return zip_buffer.getvalue()

    def export_to_directory(self, base_path: str):
        self._prepare_file_map()
        if not os.path.exists(base_path):
            os.makedirs(base_path, exist_ok=True)
        self._collect_measurement_assets_for_directory(base_path)
        
        # 今回の同期で作る全ファイルパスのセット (重複整理用)
        written_files = set()
        for (etype, eid), rel_path in self.file_map.items():
            full_path = os.path.join(base_path, f"{rel_path}.md")
            written_files.add(os.path.abspath(full_path))
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            content = self._format_entity(etype, eid)
            try:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except PermissionError:
                # ファイルが別のアプリで開かれている場合はスキップ（または手動同期時に警告）
                pass

        # 同期対象外となった古いファイルを削除 (orphaned files)
        for sub in ["Literature", "Event", "Sample", "Measurement", "Material"]:
            p = os.path.join(base_path, sub)
            if not os.path.exists(p): continue
            for root, dirs, files in os.walk(p):
                for f_name in files:
                    if not f_name.endswith(".md"): continue
                    f_path = os.path.abspath(os.path.join(root, f_name))
                    if f_path not in written_files:
                        try:
                            os.remove(f_path)
                        except PermissionError:
                            pass

    def _format_entity(self, etype: str, eid: str) -> str:
        if etype == "Literature":
            rows = self.db.fetch_all_literatures()
            target = next((r for r in rows if r["literature_id"] == eid), None)
            return self._format_lit(target) if target else ""
        elif etype == "Event":
            rows = self.db.fetch_all_events()
            target = next((r for r in rows if r["event_id"] == eid), None)
            return self._format_evt(target) if target else ""
        elif etype == "Sample":
            rows = self.db.fetch_all_samples()
            target = next((r for r in rows if r["sample_id"] == eid), None)
            return self._format_smp(target) if target else ""
        elif etype == "Measurement":
            rows = self.db.fetch_all_measurements()
            target = next((r for r in rows if r["measurement_id"] == eid), None)
            return self._format_msr(target) if target else ""
        elif etype == "Material":
            rows = self.db.fetch_all_materials()
            target = next((r for r in rows if r["material_id"] == eid), None)
            return self._format_mat(target) if target else ""
        return ""

    def _parse_json_dict(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def _collect_measurement_assets_for_directory(self, base_path: str):
        self.measurement_plot_map = {}
        assets_dir = os.path.join(base_path, "_assets")
        os.makedirs(assets_dir, exist_ok=True)

        for r in self.db.fetch_all_measurements():
            extracted = self._parse_json_dict(r.get("extracted_features") or "{}")
            rel_plot = extracted.get("xrd_plot_path")
            if not rel_plot:
                continue

            src_abs = os.path.join(os.getcwd(), "data", str(rel_plot))
            if not os.path.exists(src_abs):
                continue

            ext = os.path.splitext(src_abs)[1] or ".png"
            out_name = f"xrd_{r['measurement_id'][:8]}{ext}"
            dst_abs = os.path.join(assets_dir, out_name)
            try:
                shutil.copy2(src_abs, dst_abs)
                self.measurement_plot_map[r["measurement_id"]] = out_name
            except Exception:
                pass

    def _collect_measurement_assets_for_zip(self, zip_file: zipfile.ZipFile):
        self.measurement_plot_map = {}
        for r in self.db.fetch_all_measurements():
            extracted = self._parse_json_dict(r.get("extracted_features") or "{}")
            rel_plot = extracted.get("xrd_plot_path")
            if not rel_plot:
                continue

            src_abs = os.path.join(os.getcwd(), "data", str(rel_plot))
            if not os.path.exists(src_abs):
                continue

            ext = os.path.splitext(src_abs)[1] or ".png"
            out_name = f"xrd_{r['measurement_id'][:8]}{ext}"
            zip_rel = f"_assets/{out_name}"
            try:
                with open(src_abs, "rb") as f:
                    zip_file.writestr(zip_rel, f.read())
                self.measurement_plot_map[r["measurement_id"]] = out_name
            except Exception:
                pass

    def _format_hkls_for_md(self, hkls_val: Any) -> str:
        if not isinstance(hkls_val, list):
            return "-"
        labels = []
        for entry in hkls_val:
            if not isinstance(entry, dict):
                continue
            hkl = entry.get("hkl")
            if isinstance(hkl, (list, tuple)) and hkl:
                labels.append(" ".join(map(str, hkl)))
        return "; ".join(labels) if labels else "-"

    def _to_yaml(self, data: Dict) -> str:
        lines = []
        for k, v in data.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v: lines.append(f"  - {item}")
            elif v is None:
                lines.append(f"{k}: null")
            else:
                lines.append(f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}")
        return "\n".join(lines)

    def _format_value(self, v) -> str:
        if v is None or (isinstance(v, float) and str(v) == "nan"): return "-"
        if isinstance(v, list):
            if not v: return "[]"
            # 汎用的なカンマ区切り（複雑なものは _format_params_section 側でテーブル化）
            return ", ".join(map(str, v))
        if isinstance(v, dict):
            # 辞書は 1行の key: val 形式にして Markdown テーブルのセル内に収める
            return ", ".join([f"**{k}**: {self._format_value(val)}" for k, val in v.items()])
        return str(v)

    def _format_params_section(self, data: Dict, section_title: str = "Parameters") -> str:
        if not data: return f"## {section_title}\nNone\n"
        
        simple_params = {}
        complex_params = {}
        
        for k, v in data.items():
            if v is None or (isinstance(v, float) and str(v) == "nan"): continue
            # 辞書のリスト（仕込み表など）
            if isinstance(v, list) and v and all(isinstance(item, dict) for item in v):
                complex_params[k] = v
            else:
                simple_params[k] = v
        
        res = f"## {section_title}\n"
        if simple_params:
            res += self._dict_to_md_table(simple_params, "Property/Param") + "\n"
        
        for k, v in complex_params.items():
            res += f"### {k}\n"
            # リストから純粋な Markdown テーブルを生成
            keys = []
            for item in v:
                for sub_k in item.keys():
                    if sub_k not in keys: keys.append(sub_k)
            res += "| " + " | ".join(keys) + " |\n"
            res += "| " + " | ".join(["---"] * len(keys)) + " |\n"
            for item in v:
                row = [str(item.get(sub_k)) if item.get(sub_k) is not None else "-" for sub_k in keys]
                res += "| " + " | ".join(row) + " |\n"
            res += "\n"
        return res

    def _dict_to_md_table(self, data: Dict, title: str = "Parameter") -> str:
        if not data: return "None\n"
        lines = [f"| {title} | Value |", "| --- | --- |"]
        for k, v in data.items():
            lines.append(f"| {k} | {self._format_value(v)} |")
        return "\n".join(lines) + "\n"

    def _format_lit(self, r: Dict) -> str:
        tags = ["Literature", f"Literature/{sanitize_tag(r['literature_type'])}"]
        if r.get("venue"): tags.append(f"Venue/{sanitize_tag(r['venue'])}")
        fm = {
            "id": r["literature_id"], 
            "title": r["title"], 
            "authors": r["authors"], 
            "doi": r["doi"], 
            "year": r["publication_year"], 
            "date": r.get("publication_year"),
            "tags": tags
        }
        
        body = f"# {r['title'] or r['doi']}\n\n"
        body += f"- Authors: {r['authors']}\n- DOI: {r['doi']}\n- Venue: {r['venue']} ({r['publication_year']})\n\n"
        body += f"## Remarks\n{r['remarks'] or 'None'}\n\n"
        
        params = r.get("parameters")
        if params:
            if isinstance(params, str): params = json.loads(params)
            body += self._format_params_section(params)
        return f"---\n{self._to_yaml(fm)}\n---\n\n{body}"

    def _format_evt(self, r: Dict) -> str:
        tags = ["Event", f"Event/{sanitize_tag(r['event_type'])}", f"Material/{sanitize_tag(r['target_material'])}"]
        if r.get("project_id"): tags.append(f"Project/{sanitize_tag(r['project_id'])}")
        fm = {"id": r["event_id"], "type": r["event_type"], "material": r["target_material"], "date": r["created_at"][:10], "tags": tags}
        
        body = f"# Event: {r['event_type']} on {r['target_material']}\n\n"
        body += f"- Date: {r['created_at'][:10]}\n- Project: {r['project_id']}\n\n"
        body += f"## Motivation\n{r['motivation'] or 'None'}\n\n"
        body += f"## Remarks\n{r.get('remarks') or 'None'}\n\n"
        body += "## Relationships\n"
        
        for key, etype in [("reference_literature_ids", "Literature"), ("input_sample_ids", "Sample"), ("reference_event_ids", "Event")]:
            ids = []
            try: ids = json.loads(r.get(key) or "[]")
            except: 
                old_key = key.rstrip('s')
                if r.get(old_key): ids = [r[old_key]]
            if ids:
                body += f"- {key.replace('_', ' ').title()}:\n"
                for i in ids: body += f"  - {self._get_link(etype, i)}\n"

        params = r.get("parameters") or "{}"
        if isinstance(params, str): params = json.loads(params)
        body += self._format_params_section(params)
        return f"---\n{self._to_yaml(fm)}\n---\n\n{body}"

    def _format_smp(self, r: Dict) -> str:
        tags = ["Sample", f"Sample/Form/{sanitize_tag(r['form'])}"]
        fm = {"id": r["sample_id"], "human_id": r["human_id"], "form": r["form"], "date": r["created_at"][:10], "tags": tags}
        body = f"# Sample: {r['human_id']}\n\n- Form: {r['form']}\n- Location: {r['location'] or 'Unknown'}\n\n"
        body += "## Relationships\n"
        if r.get("source_event_id"): body += f"- Generated by: {self._get_link('Event', r['source_event_id'])}\n"
        params = r.get("parameters") or "{}"
        if isinstance(params, str): params = json.loads(params)
        body += self._format_params_section(params)
        return f"---\n{self._to_yaml(fm)}\n---\n\n{body}"

    def _format_msr(self, r: Dict) -> str:
        tags = ["Measurement", f"Measurement/{sanitize_tag(r['measurement_type'])}"]
        fm = {"id": r["measurement_id"], "type": r["measurement_type"], "operator": r["operator"], "date": r["measured_at"][:10], "tags": tags}
        body = f"# Measurement: {r['measurement_type']}\n\n- Date: {r['measured_at'][:10]}\n- Operator: {r['operator']}\n\n"
        body += "## Relationships\n"
        if r.get("sample_id"): body += f"- Measured Sample: {self._get_link('Sample', r['sample_id'])}\n"
        conds = r.get("conditions") or "{}"
        if isinstance(conds, str): conds = json.loads(conds)
        body += self._format_params_section(conds, "Conditions")

        body += f"## Remarks\n{r.get('remarks') or 'None'}\n\n"

        extracted = self._parse_json_dict(r.get("extracted_features") or "{}")
        xrd_sim = extracted.get("xrd_simulation") if isinstance(extracted, dict) else None

        if isinstance(xrd_sim, dict):
            summary = {
                "material_name": xrd_sim.get("material_name"),
                "mode": xrd_sim.get("mode"),
                "target": xrd_sim.get("target"),
                "two_theta_min": xrd_sim.get("two_theta_min"),
                "two_theta_max": xrd_sim.get("two_theta_max"),
                "peak_count": xrd_sim.get("peak_count"),
            }
            body += self._format_params_section(summary, "XRD Simulation")

            peaks = xrd_sim.get("peaks") if isinstance(xrd_sim.get("peaks"), list) else []
            if peaks:
                body += "### XRD Peaks (Top 30)\n"
                body += "| 2theta | Intensity | d_hkl | hkls |\n"
                body += "| --- | --- | --- | --- |\n"
                for p in peaks[:30]:
                    if not isinstance(p, dict):
                        continue
                    body += (
                        f"| {self._format_value(p.get('two_theta'))} "
                        f"| {self._format_value(p.get('intensity'))} "
                        f"| {self._format_value(p.get('d_hkl'))} "
                        f"| {self._format_hkls_for_md(p.get('hkls'))} |\n"
                    )
                body += "\n"

            plot_name = self.measurement_plot_map.get(r["measurement_id"])
            if plot_name:
                body += "### XRD Simulated Pattern\n"
                body += f"![[{plot_name}]]\n\n"
        elif str(r.get("measurement_type") or "").upper() == "XRD":
            body += "## XRD Simulation\n"
            body += "未生成（このMeasurementには xrd_simulation が保存されていません）\n\n"

        return f"---\n{self._to_yaml(fm)}\n---\n\n{body}"

    def _format_mat(self, r: Dict) -> str:
        tags = ["Material", f"Material/{sanitize_tag(r['name'])}"]
        fm = {"id": r["material_id"], "name": r["name"], "tags": tags}
        body = f"# Material: {r['name']}\n\n## Properties\n"
        props = r.get("properties") or "{}"
        if isinstance(props, str): props = json.loads(props)
        body += self._format_params_section(props, "Properties")
        body += "\n## Relationships\n"
        if r.get("reference_literature_id"): body += f"- Reference Literature: {self._get_link('Literature', r['reference_literature_id'])}\n"
        return f"---\n{self._to_yaml(fm)}\n---\n\n{body}"
