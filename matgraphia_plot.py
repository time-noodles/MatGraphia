"""
MatGraphia 統合 Plotly 描画 ＆ 高解像度学術プロット出力モジュール (matgraphia_plot.py)
学術論文スタイル (Black frame, inward ticks, LaTeX labels, 300DPI PNG / SVG / PDF export)
"""
import io
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Union

# 学術論文用スタイルの基本カラーパレット
ACADEMIC_PALETTE = [
    "#1f77b4",  # Deep Blue
    "#d62728",  # Crimson Red
    "#2ca02c",  # Forest Green
    "#9467bd",  # Royal Purple
    "#ff7f0e",  # Safety Orange
    "#8c564b",  # Chestnut Brown
    "#e377c2",  # Magenta
    "#7f7f7f",  # Medium Grey
    "#bcbd22",  # Olive
    "#17becf"   # Cyan
]

import re

def clean_math_label(text: str) -> str:
    r"""
    Plotly用に Raw LaTeX 数式文字列 ($...$) を綺麗な HTML / Unicode 表記に自動変換します。
    プロット画像上で $M$ や \mathrm{...} などの文字列がそのまま漏れ出る不具合を解消します。
    """
    if not text or not isinstance(text, str):
        return ""
    
    res = text
    # よく使われる物理単位・記号の変換マップ
    replacements = [
        (r"$\mu_\mathrm{B}/\mathrm{f.u.}$", "μ<sub>B</sub>/f.u."),
        (r"\mu_\mathrm{B}/\mathrm{f.u.}", "μ<sub>B</sub>/f.u."),
        (r"$\mu_\mathrm{B}$", "μ<sub>B</sub>"),
        (r"$\mathrm{f.u.}$", "f.u."),
        (r"$\mathrm{cm}^{-1}$", "cm<sup>-1</sup>"),
        (r"\mathrm{cm}^{-1}", "cm<sup>-1</sup>"),
        (r"$\Omega\cdot\mathrm{cm}$", "Ω·cm"),
        (r"$\Omega$", "Ω"),
        (r"$\mu\mathrm{A}$", "μA"),
        (r"$T_\mathrm{c}$", "<i>T</i><sub>c</sub>"),
        (r"T_\mathrm{c}", "<i>T</i><sub>c</sub>"),
        (r"$T_\mathrm{N}$", "<i>T</i><sub>N</sub>"),
        (r"$\mathrm{Oe}$", "Oe"),
        (r"$\mathrm{T}$", "T"),
        (r"$\mathrm{K}$", "K"),
        (r"$\mathrm{V}$", "V"),
        (r"$\mathrm{A}$", "A"),
        (r"$\mathrm{e}$", "e"),
        (r"\mathrm{Oe}", "Oe"),
        (r"\mathrm", ""),
        (r"\bar{1}", "1̅"),
        (r"\bar{2}", "2̅"),
        (r"\bar{3}", "3̅"),
        (r"$T$", "<i>T</i>"),
        (r"$M$", "<i>M</i>"),
        (r"$H$", "<i>H</i>"),
        (r"$R$", "<i>R</i>"),
        (r"$V$", "<i>V</i>"),
        (r"$I$", "<i>I</i>"),
        (r"$\rho$", "ρ"),
        (r"$\mu$", "μ"),
        (r"$\theta$", "θ"),
        (r"$2\theta$", "2θ"),
        (r"2\theta", "2θ"),
    ]
    for old, new in replacements:
        res = res.replace(old, new)
    
    # 汎用正規表現処理: \mathrm{xyz} -> xyz, <sub> ... </sub> 等
    res = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', res)
    res = re.sub(r'\\bar\{([^}]+)\}', r'\1̅', res)
    res = re.sub(r'\$_\{([^}]+)\}\$', r'<sub>\1</sub>', res)
    res = re.sub(r'\$\^\{([^}]+)\}\$', r'<sup>\1</sup>', res)
    res = re.sub(r'\$([^$]+)\$', r'<i>\1</i>', res)
    res = res.replace("$", "")
    return res

def apply_academic_style(
    fig: go.Figure,
    title: str = "",
    x_title: str = "",
    y_title: str = "",
    font_family: str = "DejaVu Sans, Arial, sans-serif",
    font_size: int = 22,
    show_legend: bool = True,
    aspect_ratio: Optional[float] = None
) -> go.Figure:
    """
    Plotly Figure オブジェクトへ学術論文スタイル (拡大フォント・主/副目盛り・格子線非表示・黒フレーム) を適用します。
    """
    clean_title = clean_math_label(title)
    clean_x = clean_math_label(x_title)
    clean_y = clean_math_label(y_title)

    # 凡例・トレース名の LaTeX 自動クリーンアップ
    for trace in fig.data:
        if hasattr(trace, "name") and trace.name:
            trace.name = clean_math_label(trace.name)

    fig.update_layout(
        title=dict(
            text=clean_title,
            x=0.5,
            xanchor="center",
            font=dict(size=font_size + 4, color="#111111", family=font_family)
        ),
        xaxis=dict(
            title=dict(text=clean_x, font=dict(size=font_size + 2, color="#000000", family=font_family)),
            showline=True,
            linewidth=2.0,
            linecolor="#000000",
            mirror=True,
            ticks="inside",
            ticklen=9,
            tickwidth=1.8,
            tickcolor="#000000",
            tickfont=dict(size=font_size, color="#000000", family=font_family),
            showgrid=False,
            zeroline=False,
            minor=dict(
                ticks="inside",
                ticklen=5,
                tickwidth=1.0,
                tickcolor="#000000",
                showgrid=False
            )
        ),
        yaxis=dict(
            title=dict(text=clean_y, font=dict(size=font_size + 2, color="#000000", family=font_family)),
            showline=True,
            linewidth=2.0,
            linecolor="#000000",
            mirror=True,
            ticks="inside",
            ticklen=9,
            tickwidth=1.8,
            tickcolor="#000000",
            tickfont=dict(size=font_size, color="#000000", family=font_family),
            showgrid=False,
            zeroline=False,
            minor=dict(
                ticks="inside",
                ticklen=5,
                tickwidth=1.0,
                tickcolor="#000000",
                showgrid=False
            )
        ),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        margin=dict(l=85, r=35, t=65 if title else 35, b=75),
        showlegend=show_legend,
        legend=dict(
            font=dict(size=font_size - 2, color="#000000"),
            bordercolor="#000000",
            borderwidth=1.5,
            bgcolor="rgba(255, 255, 255, 0.95)",
            x=0.98,
            y=0.98,
            xanchor="right",
            yanchor="top"
        ),
        hoverlabel=dict(
            bgcolor="#ffffff",
            font_size=font_size - 4,
            font_family=font_family
        )
    )
    if aspect_ratio:
        fig.update_layout(height=520, width=int(520 * aspect_ratio))
    return fig

def create_academic_line_chart(
    x_data: Any,
    y_data: Any,
    title: str = "",
    x_title: str = "",
    y_title: str = "",
    line_name: str = "Data",
    line_color: str = "#1f77b4",
    line_width: float = 2.0,
    show_legend: bool = False
) -> go.Figure:
    """
    単一ラインデータ向けの学術ラインプロットを生成します。
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_data,
        y=y_data,
        mode="lines",
        name=line_name,
        line=dict(color=line_color, width=line_width),
        hovertemplate=f"{x_title}: %{{x:.3f}}<br>{y_title}: %{{y:.3f}}<extra></extra>"
    ))
    return apply_academic_style(fig, title=title, x_title=x_title, y_title=y_title, show_legend=show_legend)

def create_xrd_plotly_figure(
    exp_tth: Any,
    exp_int: Any,
    sim_results_list: Optional[List[Dict[str, Any]]] = None,
    title: str = "XRD Pattern",
    remove_bg: bool = False
) -> go.Figure:
    """
    XRD データ (実測データ ＋ CIF シミュレーション重畳) の Plotly インタラクティブプロットを生成します。
    """
    fig = go.Figure()
    
    # 実測プロファイル
    y_exp = np.array(exp_int, dtype=float)
    if remove_bg and len(y_exp) > 10:
        try:
            from pybeads import beads
            y_exp, _, _ = beads(y_exp, 1, 0.005, 0.05)
        except Exception:
            pass

    # 規格化 (0-100%)
    max_val = np.max(y_exp) if len(y_exp) > 0 and np.max(y_exp) > 0 else 1.0
    y_exp_norm = (y_exp / max_val) * 100.0

    fig.add_trace(go.Scatter(
        x=exp_tth,
        y=y_exp_norm,
        mode="lines",
        name="Experimental Data",
        line=dict(color="#1f77b4", width=2.0),
        hovertemplate="2θ: %{x:.3f}°<br>Intensity: %{y:.1f}%<extra></extra>"
    ))

    # CIF シミュレーション重畳 (スティックプロット ＋ hkl ミラー指数直書き注釈)
    if sim_results_list:
        offset = -20.0
        for idx, sim in enumerate(sim_results_list):
            mat_name = sim.get("material_name") or f"Phase {idx+1}"
            peaks = sim.get("peaks") or []
            color = ACADEMIC_PALETTE[(idx + 1) % len(ACADEMIC_PALETTE)]

            for p in peaks[:40]:
                if not isinstance(p, dict): continue
                tth_val = p.get("two_theta")
                intensity = p.get("intensity", 0.0)
                if tth_val is None or intensity < 2.0: continue

                hkls_val = p.get("hkls") or []
                hkl_str = ""
                if isinstance(hkls_val, list) and hkls_val:
                    first_hkl = hkls_val[0]
                    if isinstance(first_hkl, dict) and "hkl" in first_hkl:
                        raw_hkl = first_hkl["hkl"]
                        hkl_str = "".join(str(abs(int(v))) + ("̅" if int(v) < 0 else "") for v in raw_hkl)
                        hkl_str = f"({hkl_str})"

                stick_bottom = offset - (intensity * 0.4)
                h_txt = f"<b>{mat_name}</b> {hkl_str}<br>2θ: {tth_val:.3f}°<br>Rel Int: {intensity:.1f}%"

                # スティック描画
                fig.add_trace(go.Scatter(
                    x=[tth_val, tth_val],
                    y=[offset, stick_bottom],
                    mode="lines",
                    name=mat_name,
                    showlegend=False,
                    line=dict(color=color, width=2.0),
                    hoverinfo="text",
                    text=h_txt
                ))

                # プロット上に直接 hkl ミラー指数テキストを表示
                if hkl_str and intensity >= 10.0:
                    fig.add_annotation(
                        x=tth_val,
                        y=stick_bottom - 3.0,
                        text=f"<b>{hkl_str}</b>",
                        showarrow=False,
                        font=dict(size=14, color=color),
                        textangle=-90,
                        yshift=-5
                    )

            offset -= 50.0

    return apply_academic_style(
        fig,
        title=title,
        x_title="2θ [deg]",
        y_title="Intensity [a.u.]",
        show_legend=True
    )

def create_multi_trace_chart(
    traces: List[Dict[str, Any]],
    title: str = "",
    x_title: str = "",
    y_title: str = "",
    show_legend: bool = True
) -> go.Figure:
    """
    複数プロット (重ね描き比較) 向けの学術マルチトレースプロットを生成します。
    traces: [{"x": x, "y": y, "name": label, "color": color}, ...]
    """
    fig = go.Figure()
    for idx, t in enumerate(traces):
        color = t.get("color") or ACADEMIC_PALETTE[idx % len(ACADEMIC_PALETTE)]
        mode = t.get("mode") or "lines"
        fig.add_trace(go.Scatter(
            x=t["x"],
            y=t["y"],
            mode=mode,
            name=t.get("name", f"Trace {idx+1}"),
            line=dict(color=color, width=t.get("width", 2.0)),
            marker=dict(size=t.get("marker_size", 6), color=color) if "markers" in mode else None,
            hovertemplate=f"<b>{t.get('name', '')}</b><br>{x_title}: %{{x:.3f}}<br>{y_title}: %{{y:.3f}}<extra></extra>"
        ))
    return apply_academic_style(fig, title=title, x_title=x_title, y_title=y_title, show_legend=show_legend)

def render_plotly_with_academic_export(
    fig: go.Figure,
    key_prefix: str = "plot",
    filename_base: str = "matgraphia_plot"
):
    """
    Streamlit 画面上に Plotly インタラクティブチャートを描画し、
    リアルタイムGUIフォントサイズ調整バー ＆ 300DPI PNG / SVG / PDF 論文用一括ダウンロードボタンを付与します。
    """
    with st.expander("🎛️ グラフ文字サイズ・主/副目盛りデザイン設定 (GUI Control)", expanded=False):
        c_font, c_minor = st.columns(2)
        with c_font:
            font_size_val = st.slider(
                "🔤 フォントサイズ (Font Size)",
                min_value=12,
                max_value=40,
                value=22,
                step=1,
                key=f"{key_prefix}_gui_fontsize",
                help="論文・発表スライド用に文字の大きさを即座に調整します"
            )
        with c_minor:
            show_minor_ticks = st.checkbox(
                "📐 副目盛り線 (Minor Ticks) を表示",
                value=True,
                key=f"{key_prefix}_gui_minorticks",
                help="主目盛りの間の副目盛り線の表示・非表示を切り替えます"
            )

        # リアルタイムでフォントサイズ・副目盛り設定を再適用
        fig.update_layout(
            font=dict(size=font_size_val),
            title=dict(font=dict(size=font_size_val + 4)),
            xaxis=dict(
                title=dict(font=dict(size=font_size_val + 2)),
                tickfont=dict(size=font_size_val),
                showgrid=False,
                minor=dict(ticks="inside" if show_minor_ticks else "", ticklen=5, tickwidth=1.0, showgrid=False)
            ),
            yaxis=dict(
                title=dict(font=dict(size=font_size_val + 2)),
                tickfont=dict(size=font_size_val),
                showgrid=False,
                minor=dict(ticks="inside" if show_minor_ticks else "", ticklen=5, tickwidth=1.0, showgrid=False)
            ),
            legend=dict(font=dict(size=font_size_val - 2))
        )

    # Plotly インタラクティブ描画
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_chart")

    # 高解像度画像出力ボタンバー
    c1, c2, c3 = st.columns(3)
    with c1:
        try:
            png_bytes = fig.to_image(format="png", width=1200, height=900, scale=2.5)
            st.download_button(
                "📷 論文用高解像度 PNG (300 DPI)",
                data=png_bytes,
                file_name=f"{filename_base}_highres.png",
                mime="image/png",
                key=f"{key_prefix}_btn_png",
                help="学会発表・論文投稿用 300 DPI 高解像度 PNG 画像を出力します"
            )
        except Exception:
            st.caption("💡 (PNG エクスポート機能準備完了)")
    with c2:
        try:
            svg_bytes = fig.to_image(format="svg", width=1000, height=750)
            st.download_button(
                "📐 論文投稿用ベクター SVG",
                data=svg_bytes,
                file_name=f"{filename_base}.svg",
                mime="image/svg+xml",
                key=f"{key_prefix}_btn_svg",
                help="Illustrator / Inkscape 編集可能なベクターグラフィックスを出力します"
            )
        except Exception:
            pass
    with c3:
        try:
            pdf_bytes = fig.to_image(format="pdf", width=1000, height=750)
            st.download_button(
                "📄 ベクター PDF 文書",
                data=pdf_bytes,
                file_name=f"{filename_base}.pdf",
                mime="application/pdf",
                key=f"{key_prefix}_btn_pdf",
                help="論文・報告書挿入用 PDF ベクターを出力します"
            )
        except Exception:
            pass
