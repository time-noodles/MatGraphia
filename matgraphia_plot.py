"""
MatGraphia 統合 Plotly 描画 ＆ 高解像度学術プロット出力モジュール (matgraphia_plot.py)
学術論文スタイル (Black frame, inward ticks, LaTeX labels, 300DPI PNG / SVG / PDF export)
"""
import io
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
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

def apply_academic_style(
    fig: go.Figure,
    title: str = "",
    x_title: str = "",
    y_title: str = "",
    font_family: str = "DejaVu Sans, Arial, sans-serif",
    font_size: int = 14,
    show_legend: bool = True,
    aspect_ratio: Optional[float] = None
) -> go.Figure:
    """
    Plotly Figure オブジェクトへ学術論文スタイル (黒フレーム・目盛り・LaTeXラベル) を全自動適用します。
    """
    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,
            xanchor="center",
            font=dict(size=font_size + 2, color="#111111", family=font_family)
        ),
        xaxis=dict(
            title=dict(text=x_title, font=dict(size=font_size, color="#000000", family=font_family)),
            showline=True,
            linewidth=1.5,
            linecolor="#000000",
            mirror=True,
            ticks="inside",
            ticklen=6,
            tickwidth=1.2,
            tickcolor="#000000",
            tickfont=dict(size=font_size - 2, color="#000000", family=font_family),
            gridcolor="#e0e0e0",
            gridwidth=0.5,
            zeroline=False
        ),
        yaxis=dict(
            title=dict(text=y_title, font=dict(size=font_size, color="#000000", family=font_family)),
            showline=True,
            linewidth=1.5,
            linecolor="#000000",
            mirror=True,
            ticks="inside",
            ticklen=6,
            tickwidth=1.2,
            tickcolor="#000000",
            tickfont=dict(size=font_size - 2, color="#000000", family=font_family),
            gridcolor="#e0e0e0",
            gridwidth=0.5,
            zeroline=False
        ),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        margin=dict(l=65, r=30, t=50 if title else 30, b=55),
        showlegend=show_legend,
        legend=dict(
            font=dict(size=font_size - 3, color="#000000"),
            bordercolor="#000000",
            borderwidth=1,
            bgcolor="rgba(255, 255, 255, 0.9)",
            x=0.98,
            y=0.98,
            xanchor="right",
            yanchor="top"
        ),
        hoverlabel=dict(
            bgcolor="#ffffff",
            font_size=13,
            font_family=font_family
        )
    )
    if aspect_ratio:
        fig.update_layout(height=480, width=int(480 * aspect_ratio))
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
        hovertemplate=f"{x_title}: %{{x}}<br>{y_title}: %{{y}}<extra></extra>"
    ))
    return apply_academic_style(fig, title=title, x_title=x_title, y_title=y_title, show_legend=show_legend)

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
            hovertemplate=f"<b>{t.get('name', '')}</b><br>{x_title}: %{{x}}<br>{y_title}: %{{y}}<extra></extra>"
        ))
    return apply_academic_style(fig, title=title, x_title=x_title, y_title=y_title, show_legend=show_legend)

def render_plotly_with_academic_export(
    fig: go.Figure,
    key_prefix: str = "plot",
    filename_base: str = "matgraphia_plot"
):
    """
    Streamlit 画面上に Plotly インタラクティブチャートを描画し、
    高解像度 PNG (300DPI) / SVG / PDF 論文用一括ダウンロードボタンを付与します。
    """
    # Plotly 描画
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
            st.caption("💡 (PNG エクスポートには kaleido パッケージが必要です)")
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
