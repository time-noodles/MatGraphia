import os
import io
import sys
import tempfile
from typing import Any

import numpy as np


SCHEMA = {
    "type": "XRD",
    "fields": [
        {
            "name": "simulation_mode",
            "type": "select",
            "label": "シミュレーション種別",
            "options": ["Powder", "TMDC c-axis Oriented"],
            "default": "Powder"
        },
        {
            "name": "target",
            "type": "select",
            "label": "X-ray Target",
            "options": ["CuKa", "MoKa", "CoKa", "FeKa"],
            "default": "CuKa"
        },
        {"name": "two_theta_min", "type": "float", "label": "2theta min", "default": 5.0},
        {"name": "two_theta_max", "type": "float", "label": "2theta max", "default": 90.0},
        {"name": "profile_step", "type": "float", "label": "Profile step", "default": 0.02},
        {"name": "peak_width", "type": "float", "label": "Peak width (FWHM)", "default": 0.15}
    ]
}


def _find_material_for_sample(sample_id: str, samples: list[dict], events_dict: dict, materials: list[dict]) -> dict | None:
    sample = next((s for s in samples if s.get("sample_id") == sample_id), None)
    if not sample:
        return None

    event = events_dict.get(sample.get("source_event_id"))
    if not event:
        return None

    target_material_name = str(event.get("target_material") or "").strip()
    if not target_material_name:
        return None

    for m in materials:
        if str(m.get("name") or "").strip() == target_material_name and m.get("cif_file_path"):
            return m
    return None


def _is_00l_reflection(hkl_entry: Any) -> bool:
    hkl = hkl_entry.get("hkl") if isinstance(hkl_entry, dict) else None
    if not hkl:
        return False
    if len(hkl) >= 4:
        # 4-index (h k i l) notation for hexagonal systems
        h, k, i, l = int(hkl[0]), int(hkl[1]), int(hkl[2]), int(hkl[3])
        return h == 0 and k == 0 and i == 0 and l != 0
    if len(hkl) >= 3:
        h, k, l = int(hkl[0]), int(hkl[1]), int(hkl[2])
        return h == 0 and k == 0 and l != 0
    return False


def _simulate_profile(peak_x: list[float], peak_y: list[float], x_min: float, x_max: float, step: float, fwhm: float):
    x = np.arange(x_min, x_max + step, step)
    y = np.zeros_like(x)
    sigma = max(fwhm, 1e-6) / 2.355

    for px, py in zip(peak_x, peak_y):
        y += py * np.exp(-0.5 * ((x - px) / sigma) ** 2)

    y_max = float(np.max(y)) if len(y) else 0.0
    if y_max > 0:
        y = (y / y_max) * 100.0
    return x, y


def _ensure_symple_plot_importable() -> None:
    current_dir = os.path.dirname(__file__)
    libs_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
    custom_lib_dir = os.path.join(libs_dir, "custom_lib")
    if os.path.isdir(custom_lib_dir) and custom_lib_dir not in sys.path:
        sys.path.insert(0, custom_lib_dir)


def _format_hkl_label(hkls_entry: Any) -> str:
    if isinstance(hkls_entry, list) and hkls_entry:
        def _fmt_index(v: Any) -> str:
            iv = int(v)
            if iv < 0:
                return rf"\bar{{{abs(iv)}}}"
            return str(iv)

        # TMDC向けに、まず00l候補を優先してラベル化する
        candidates = [e for e in hkls_entry if isinstance(e, dict)]
        for e in candidates:
            hkl = e.get("hkl")
            if not isinstance(hkl, (list, tuple)):
                continue
            if len(hkl) >= 4:
                h, k, i, l = int(hkl[0]), int(hkl[1]), int(hkl[2]), int(hkl[3])
                if h == 0 and k == 0 and i == 0 and l != 0:
                    parts = [_fmt_index(h), _fmt_index(k), _fmt_index(l)]
                    return rf"${''.join(parts)}$"
            elif len(hkl) >= 3:
                h, k, l = int(hkl[0]), int(hkl[1]), int(hkl[2])
                if h == 0 and k == 0 and l != 0:
                    parts = [_fmt_index(h), _fmt_index(k), _fmt_index(l)]
                    return rf"${''.join(parts)}$"

        # 一般ケース: 先頭候補を3指数表示（4指数なら h,k,l(4th) を採用）
        first = candidates[0] if candidates else None
        if isinstance(first, dict):
            hkl = first.get("hkl")
            if isinstance(hkl, (list, tuple)) and len(hkl) >= 4:
                parts = [_fmt_index(hkl[0]), _fmt_index(hkl[1]), _fmt_index(hkl[3])]
                return rf"${''.join(parts)}$"
            if isinstance(hkl, (list, tuple)) and len(hkl) >= 3:
                parts = [_fmt_index(v) for v in hkl[:3]]
                return rf"${''.join(parts)}$"
    return ""


def render_simulated_xrd_plot_png(sim_result: dict):
    create_symple_plots = None
    plt = None
    try:
        # まずは pip でインストール済みの symple_plot を優先して使う
        from symple_plot import create_symple_plots as _create_symple_plots
        import matplotlib.pyplot as _plt
        create_symple_plots = _create_symple_plots
        plt = _plt
    except Exception:
        try:
            # ローカル custom_lib 版へフォールバック
            _ensure_symple_plot_importable()
            from symple_plot import create_symple_plots as _create_symple_plots
            import matplotlib.pyplot as _plt
            create_symple_plots = _create_symple_plots
            plt = _plt
        except Exception as e:
            return None, f"symple_plot の読み込みに失敗しました: {e}"

    try:
        profile = sim_result.get("profile") or {}
        x = np.array(profile.get("two_theta") or [], dtype=float)
        y = np.array(profile.get("intensity") or [], dtype=float)
        if len(x) == 0 or len(y) == 0:
            return None, "シミュレーションプロファイルが空のため、グラフを作成できません。"

        y = y - np.nanmin(y)
        y_max = float(np.nanmax(y)) if len(y) else 0.0
        if y_max > 0:
            y = y / y_max

        target = str(sim_result.get("target") or "CuKa")
        x_min = float(sim_result.get("two_theta_min") or np.nanmin(x))
        x_max = float(sim_result.get("two_theta_max") or np.nanmax(x))

        fig, sp = create_symple_plots(nrows=1, ncols=1, figsize=(8.5, 5.0), style="paper")
        sp.plot(
            x,
            y,
            alab=[r'$\mathrm{2}\theta\ [\mathrm{deg., Cu}K\alpha]$', "Intensity [a.u.]"],
            lab=f"{sim_result.get('material_name', 'Unknown')} / {sim_result.get('mode', 'Powder')}",
            cx=[x_min, x_max],
            nony=True,
        )

        peaks = sim_result.get("peaks") or []
        if peaks:
            peak_int = np.array([float(p.get("intensity") or 0.0) for p in peaks], dtype=float)
            pmax = float(np.nanmax(peak_int)) if len(peak_int) else 0.0
            if pmax > 0:
                for p in peaks:
                    px = float(p.get("two_theta") or 0.0)
                    py = float(p.get("intensity") or 0.0) / pmax
                    if py < 0.12:
                        continue
                    label = _format_hkl_label(p.get("hkls"))
                    if not label:
                        continue
                    y_profile = float(np.interp(px, x, y)) if len(x) > 1 else py
                    sp.ax.text(px, min(1.02, y_profile + 0.04), label, rotation=90, ha="center", va="bottom", fontsize=10)

        sp.ax.legend(frameon=False, loc="upper right", fontsize=12)

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=220)
        plt.close(fig)
        return buf.getvalue(), None
    except Exception as e:
        return None, f"symple_plot描画に失敗しました: {e}"


def _simulate_xrd_from_cif_path(cif_abs_path: str, conditions: dict, material_name: str = "Unknown"):
    try:
        from pymatgen.core import Structure
        from pymatgen.analysis.diffraction.xrd import XRDCalculator
    except Exception:
        return None, "pymatgen が未インストールのため、XRDシミュレーションを実行できません。"

    if not os.path.exists(cif_abs_path):
        return None, f"CIFファイルが見つかりません: {cif_abs_path}"

    mode = str(conditions.get("simulation_mode") or "Powder")
    target = str(conditions.get("target") or "CuKa")
    tth_min = float(conditions.get("two_theta_min") or 5.0)
    tth_max = float(conditions.get("two_theta_max") or 90.0)
    step = float(conditions.get("profile_step") or 0.02)
    fwhm = float(conditions.get("peak_width") or 0.15)
    if tth_max <= tth_min:
        tth_max = tth_min + 1.0

    structure = Structure.from_file(cif_abs_path)
    calculator = XRDCalculator(wavelength=target)
    pattern = calculator.get_pattern(structure, two_theta_range=(tth_min, tth_max))

    selected_indices = list(range(len(pattern.x)))
    if mode == "TMDC c-axis Oriented":
        selected_indices = []
        for i, hkls in enumerate(pattern.hkls):
            if any(_is_00l_reflection(hkl_entry) for hkl_entry in hkls):
                selected_indices.append(i)

    peak_x = [float(pattern.x[i]) for i in selected_indices]
    peak_y = [float(pattern.y[i]) for i in selected_indices]
    d_hkls = [float(pattern.d_hkls[i]) for i in selected_indices]
    hkls = [pattern.hkls[i] for i in selected_indices]

    profile_x, profile_y = _simulate_profile(peak_x, peak_y, tth_min, tth_max, step, fwhm)

    peaks = []
    for i, x in enumerate(peak_x):
        peaks.append(
            {
                "two_theta": x,
                "intensity": peak_y[i],
                "d_hkl": d_hkls[i],
                "hkls": hkls[i],
            }
        )

    result = {
        "material_name": material_name,
        "cif_file_path": cif_abs_path,
        "mode": mode,
        "target": target,
        "two_theta_min": tth_min,
        "two_theta_max": tth_max,
        "peak_count": len(peaks),
        "peaks": peaks,
        "profile": {
            "two_theta": profile_x.tolist(),
            "intensity": profile_y.tolist(),
        },
    }
    return result, None


def simulate_xrd_for_cif_bytes(cif_bytes: bytes, cif_name: str, conditions: dict, material_name: str = "Unknown"):
    if not cif_bytes:
        return None, "CIFデータが空のため、XRDシミュレーションを実行できません。"

    suffix = os.path.splitext(cif_name or "uploaded.cif")[1] or ".cif"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
            tf.write(cif_bytes)
            tmp_path = tf.name
        return _simulate_xrd_from_cif_path(tmp_path, conditions, material_name=material_name)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def simulate_xrd_for_sample(
    sample_id: str,
    conditions: dict,
    samples: list[dict],
    events_dict: dict,
    materials: list[dict],
    data_base_dir: str,
):
    material = _find_material_for_sample(sample_id, samples, events_dict, materials)
    if not material:
        return None, "対応する物質またはCIFが見つからないため、XRDシミュレーションをスキップしました。"

    cif_rel_path = material.get("cif_file_path")
    cif_abs_path = os.path.join(data_base_dir, str(cif_rel_path))
    return _simulate_xrd_from_cif_path(cif_abs_path, conditions, material_name=str(material.get("name") or "Unknown"))


# =====================================================================
# 実測XRDデータ読込（Bruker RAW 4.00 / 汎用CSV/TXT対応）
# =====================================================================
def _parse_xrd_bytes(raw_bytes: bytes):
    """
    XRDデータのバイト列をパースし、(two_theta_array, intensity_array, error_msg)を返す。
    Bruker RAW 4.00フォーマット（[Data]セクション）と汎用CSV/TXTの両方に対応。
    """
    import io as _io
    import pandas as pd

    text = raw_bytes.decode("utf-8", errors="ignore")
    lines = text.splitlines()

    # Bruker RAW 4.00 フォーマット検出: [Data]セクションを探す
    data_start_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower() == "[data]":
            data_start_idx = i + 1
            break

    if data_start_idx is not None:
        # [Data]セクション以降をパース
        # ヘッダ行(Angle, PSD,等)をスキップ
        data_lines = []
        for line in lines[data_start_idx:]:
            stripped = line.strip()
            if not stripped:
                continue
            # 新しいセクション([...])が始まったら終了
            if stripped.startswith("["):
                break
            data_lines.append(stripped)

        if not data_lines:
            return None, None, "[Data]セクションにデータ行が見つかりませんでした。"

        # カンマ区切りでパース
        csv_text = "\n".join(data_lines)
        try:
            df = pd.read_csv(_io.StringIO(csv_text), sep=",", header=None, engine="python")
            col0 = pd.to_numeric(df.iloc[:, 0], errors="coerce")
            col1 = pd.to_numeric(df.iloc[:, 1], errors="coerce")
            mask = col0.notna() & col1.notna()
            two_theta = col0[mask].values.astype(float)
            intensity = col1[mask].values.astype(float)
            if len(two_theta) > 0:
                return two_theta, intensity, None
        except Exception:
            pass
        return None, None, "[Data]セクションの数値データのパースに失敗しました。"

    # 汎用CSV/TXTフォールバック
    df = None
    for sep in [",", r"\s+", "\t"]:
        try:
            tmp = pd.read_csv(_io.BytesIO(raw_bytes), sep=sep, header=None, comment="#", engine="python")
            if tmp.shape[1] >= 2:
                df = tmp
                break
        except Exception:
            continue

    if df is None or df.shape[1] < 2:
        return None, None, "2列以上のデータを検出できませんでした。"

    col0 = pd.to_numeric(df.iloc[:, 0], errors="coerce")
    col1 = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    mask = col0.notna() & col1.notna()
    two_theta = col0[mask].values.astype(float)
    intensity = col1[mask].values.astype(float)

    if len(two_theta) == 0:
        return None, None, "有効なデータ行が見つかりませんでした。"

    return two_theta, intensity, None


def parse_experimental_xrd(raw_data_path: str, data_base_dir: str):
    """
    アップロードされた実測XRDデータを読み込み、
    (two_theta_array, intensity_array, error_msg) を返す。
    Bruker RAW 4.00 / 汎用CSV/TXT両対応。
    """
    abs_path = os.path.join(data_base_dir, str(raw_data_path))
    if not os.path.exists(abs_path):
        return None, None, f"ファイルが見つかりません: {abs_path}"

    try:
        with open(abs_path, "rb") as f:
            raw_bytes = f.read()
        return _parse_xrd_bytes(raw_bytes)
    except Exception as e:
        return None, None, f"実測データの読み込みに失敗しました: {e}"


# =====================================================================
# 関連物質(不純物・多型)の保存済みシミュレーション収集
# =====================================================================
def collect_related_material_simulations(
    material: dict,
    materials_list: list[dict],
    conditions: dict,
):
    """
    対象Materialのimpurity_material_ids/polymorph_material_idsに
    設定されたMaterialの保存済みXRDシミュレーション結果を収集する。
    再計算は行わず、properties["xrd_simulation"]から読み込む。
    """
    import json

    results = []
    mat_dict = {}
    for m in materials_list:
        mat_dict[m.get("material_id")] = m

    # impurity_material_ids
    impurity_ids = material.get("impurity_material_ids") or []
    if isinstance(impurity_ids, str):
        try:
            impurity_ids = json.loads(impurity_ids)
        except Exception:
            impurity_ids = []

    for mid in impurity_ids:
        m = mat_dict.get(mid)
        if not m:
            continue
        props = m.get("properties") or {}
        if isinstance(props, str):
            try:
                props = json.loads(props)
            except Exception:
                continue
        sim = props.get("xrd_simulation")
        if sim:
            sim["relation_type"] = "impurity"
            sim["material_name"] = str(m.get("name") or "Unknown")
            # 表示モードに応じてピークをフィルタ
            mode = str(conditions.get("simulation_mode") or "Powder")
            if mode == "TMDC c-axis Oriented":
                sim = _filter_00l_from_saved(sim, conditions)
            results.append(sim)

    # polymorph_material_ids
    polymorph_ids = material.get("polymorph_material_ids") or []
    if isinstance(polymorph_ids, str):
        try:
            polymorph_ids = json.loads(polymorph_ids)
        except Exception:
            polymorph_ids = []

    for mid in polymorph_ids:
        m = mat_dict.get(mid)
        if not m:
            continue
        props = m.get("properties") or {}
        if isinstance(props, str):
            try:
                props = json.loads(props)
            except Exception:
                continue
        sim = props.get("xrd_simulation")
        if sim:
            sim["relation_type"] = "polymorph"
            sim["material_name"] = str(m.get("name") or "Unknown")
            mode = str(conditions.get("simulation_mode") or "Powder")
            if mode == "TMDC c-axis Oriented":
                sim = _filter_00l_from_saved(sim, conditions)
            results.append(sim)

    return results


def _filter_00l_from_saved(sim_result: dict, conditions: dict) -> dict:
    """
    保存済みPowderシミュレーション結果から00l反射のみをフィルタし、
    プロファイルを再生成して返す。
    """
    peaks = sim_result.get("peaks") or []
    filtered_peaks = []
    for p in peaks:
        hkls_list = p.get("hkls") or []
        if any(_is_00l_reflection(entry) for entry in hkls_list):
            filtered_peaks.append(p)

    if not filtered_peaks:
        return sim_result

    tth_min = float(conditions.get("two_theta_min") or sim_result.get("two_theta_min") or 5.0)
    tth_max = float(conditions.get("two_theta_max") or sim_result.get("two_theta_max") or 90.0)
    step = float(conditions.get("profile_step") or 0.02)
    fwhm = float(conditions.get("peak_width") or 0.15)

    peak_x = [float(p["two_theta"]) for p in filtered_peaks]
    peak_y = [float(p["intensity"]) for p in filtered_peaks]
    profile_x, profile_y = _simulate_profile(peak_x, peak_y, tth_min, tth_max, step, fwhm)

    new_result = dict(sim_result)
    new_result["peaks"] = filtered_peaks
    new_result["peak_count"] = len(filtered_peaks)
    new_result["mode"] = "TMDC c-axis Oriented"
    new_result["profile"] = {
        "two_theta": profile_x.tolist(),
        "intensity": profile_y.tolist(),
    }
    return new_result


# =====================================================================
# 実測 vs シミュレーション 比較グラフ PNG 生成
# =====================================================================
def render_comparison_xrd_plot_png(
    experimental_data: dict | None,
    sim_results_list: list[dict],
    conditions: dict,
    remove_bg: bool = True,
):
    """
    実測XRDパターンと複数のシミュレーション結果を重ね描きするPNG画像を生成。
    - 実測: 上向き(正方向)に正規化描画
    - シミュレーション: 下向き(負方向)に反転して描画
    - hklラベルを主要ピーク位置に表示
    """
    create_symple_plots = None
    remove_background_fn = None
    plt = None
    try:
        from symple_plot import create_symple_plots as _csp
        import matplotlib.pyplot as _plt
        create_symple_plots = _csp
        plt = _plt
        try:
            from symple_plot import remove_background as _rb
            remove_background_fn = _rb
        except ImportError:
            pass
    except Exception:
        try:
            _ensure_symple_plot_importable()
            from symple_plot import create_symple_plots as _csp
            import matplotlib.pyplot as _plt
            create_symple_plots = _csp
            plt = _plt
            try:
                from symple_plot import remove_background as _rb
                remove_background_fn = _rb
            except ImportError:
                pass
        except Exception as e:
            return None, f"symple_plot の読み込みに失敗しました: {e}"

    try:
        # 描画するデータ系列を収集
        all_x, all_y = [], []
        all_colors = []

        target = str(conditions.get("target") or "CuKa")
        x_min = float(conditions.get("two_theta_min") or 5.0)
        x_max = float(conditions.get("two_theta_max") or 90.0)

        # 実測データ (上向き=正方向)
        has_exp = False
        if experimental_data:
            ex = np.array(experimental_data.get("two_theta") or [], dtype=float)
            ey = np.array(experimental_data.get("intensity") or [], dtype=float)
            if len(ex) > 0 and len(ey) > 0:
                # バックグラウンド除去
                if remove_bg and remove_background_fn is not None:
                    try:
                        ey = remove_background_fn(ey, auto_opt=True)
                    except Exception:
                        pass
                # 正規化 (0-1)
                ey = ey - np.nanmin(ey)
                ey_max = float(np.nanmax(ey))
                if ey_max > 0:
                    ey = ey / ey_max
                all_x.append(ex)
                all_y.append(ey)
                has_exp = True

        # シミュレーション系列数を数える
        n_sim = len(sim_results_list)

        # 各シミュレーション (下向き=負方向)
        sim_vertical_offsets = []
        for idx, sim in enumerate(sim_results_list):
            profile = sim.get("profile") or {}
            sx = np.array(profile.get("two_theta") or [], dtype=float)
            sy = np.array(profile.get("intensity") or [], dtype=float)
            if len(sx) == 0 or len(sy) == 0:
                continue
            # 正規化
            sy = sy - np.nanmin(sy)
            sy_max = float(np.nanmax(sy))
            if sy_max > 0:
                sy = sy / sy_max
            # 下向きに反転、オフセット適用
            offset = -(idx + 1) * 1.15
            sim_vertical_offsets.append(offset)
            sy = -sy + offset
            all_x.append(sx)
            all_y.append(sy)

        if not all_x:
            return None, "描画可能なデータがありません。"

        # 全体の描画範囲
        total_series = len(all_x)
        fig_height = max(5.0, 2.5 + n_sim * 1.5)
        fig, sp = create_symple_plots(nrows=1, ncols=1, figsize=(8.5, fig_height), style="paper")

        # 色の生成
        cmap = plt.get_cmap("tab10")
        legend_handles = []

        series_idx = 0
        # 実測データ描画
        if has_exp:
            col = (0, 0, 0)
            sp.plot(
                all_x[series_idx], all_y[series_idx],
                col=col,
                alab=[rf'$\mathrm{{2}}\theta\ [\mathrm{{deg.,\ {target}}}]$', "Intensity [a.u.]"],
                cx=[x_min, x_max],
                nony=True,
                lab="Exp.",
            )
            series_idx += 1

        # シミュレーション描画
        for sim_idx, sim in enumerate(sim_results_list):
            if series_idx >= len(all_x):
                break
            mat_name = str(sim.get("material_name") or "Unknown")
            rel_type = sim.get("relation_type") or ""
            mode_text = str(sim.get("mode") or "Powder")

            label = f"Sim. {mat_name}"
            if rel_type == "impurity":
                label += " (impurity)"
            elif rel_type == "polymorph":
                label += " (polymorph)"

            col_rgba = cmap(sim_idx % 10)
            col = col_rgba[:3]
            sp.plot(
                all_x[series_idx], all_y[series_idx],
                col=col,
                nony=True,
                lab=label,
            )

            # hklラベル
            peaks = sim.get("peaks") or []
            if peaks:
                peak_int = np.array([float(p.get("intensity") or 0.0) for p in peaks], dtype=float)
                pmax = float(np.nanmax(peak_int)) if len(peak_int) else 0.0
                offset = sim_vertical_offsets[sim_idx] if sim_idx < len(sim_vertical_offsets) else 0.0
                if pmax > 0:
                    for p in peaks:
                        py_rel = float(p.get("intensity") or 0.0) / pmax
                        if py_rel < 0.12:
                            continue
                        lbl = _format_hkl_label(p.get("hkls"))
                        if not lbl:
                            continue
                        px = float(p.get("two_theta") or 0.0)
                        sp.ax.text(
                            px, offset - py_rel - 0.06,
                            lbl, rotation=90, ha="center", va="top", fontsize=7, color=col,
                        )

            series_idx += 1

        sp.ax.legend(frameon=False, loc="upper right", fontsize=10)
        sp.ax.tick_params(axis="y", labelleft=False, left=False)

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=220)
        plt.close(fig)
        return buf.getvalue(), None
    except Exception as e:
        return None, f"比較グラフの描画に失敗しました: {e}"


# =====================================================================
# 比較データCSV生成（ダウンロード用）
# =====================================================================
def build_comparison_csv(
    experimental_data: dict | None,
    sim_results_list: list[dict],
    remove_bg: bool = True,
):
    """
    実測 + シミュレーションデータを統合したCSV用DataFrameを生成。
    ユーザーが別のフォーマットでグラフを描画できるようにする。
    """
    import pandas as pd

    remove_background_fn = None
    if remove_bg:
        try:
            from symple_plot import remove_background as _rb
            remove_background_fn = _rb
        except ImportError:
            try:
                _ensure_symple_plot_importable()
                from symple_plot import remove_background as _rb
                remove_background_fn = _rb
            except ImportError:
                pass

    data_dict = {}
    max_len = 0

    # 実測データ
    if experimental_data:
        ex = np.array(experimental_data.get("two_theta") or [], dtype=float)
        ey = np.array(experimental_data.get("intensity") or [], dtype=float)
        if len(ex) > 0:
            if remove_bg and remove_background_fn is not None:
                try:
                    ey = remove_background_fn(ey, auto_opt=True)
                except Exception:
                    pass
            ey = ey - np.nanmin(ey)
            ey_max = float(np.nanmax(ey))
            if ey_max > 0:
                ey = ey / ey_max
            data_dict["two_theta_exp"] = ex
            data_dict["intensity_exp"] = ey
            max_len = max(max_len, len(ex))

    # シミュレーション
    for idx, sim in enumerate(sim_results_list):
        mat_name = str(sim.get("material_name") or "Unknown")
        rel_type = sim.get("relation_type") or "main"
        suffix = f"{mat_name}_{rel_type}"

        profile = sim.get("profile") or {}
        sx = np.array(profile.get("two_theta") or [], dtype=float)
        sy = np.array(profile.get("intensity") or [], dtype=float)
        if len(sx) > 0:
            sy = sy - np.nanmin(sy)
            sy_max = float(np.nanmax(sy))
            if sy_max > 0:
                sy = sy / sy_max
            data_dict[f"two_theta_sim_{suffix}"] = sx
            data_dict[f"intensity_sim_{suffix}"] = sy
            max_len = max(max_len, len(sx))

    if not data_dict:
        return None

    # 長さを揃えてDataFrame生成
    for k, v in data_dict.items():
        if len(v) < max_len:
            data_dict[k] = np.pad(v, (0, max_len - len(v)), constant_values=np.nan)

    return pd.DataFrame(data_dict)
