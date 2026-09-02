"""
MatGraphia Plotly プロット単体デモ生成スクリプト (scripts/demo_plotly_plots.py)
MatGraphia アプリを介さずに、matgraphia_plot.py を用いて全測定タイプの学術グラフを独立生成・ファイル出力します。
"""
import os
import sys
import numpy as np
import pandas as pd

# ルートディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from matgraphia_plot import (
    create_academic_line_chart,
    create_xrd_plotly_figure,
    create_multi_trace_chart,
    apply_academic_style
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "demo_plots")

def generate_demo_plots():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("🎨 matgraphia_plot.py による単体デモプロット生成を開始します...")

    # 1. XRD パターン (実測 ＋ CIF スティック重畳)
    print("📊 1. XRD プロット生成中...")
    tth = np.linspace(10, 80, 1000)
    intensity = 10 + 90 * np.exp(-((tth - 27.5)**2)/0.2) + 60 * np.exp(-((tth - 38.2)**2)/0.15) + 40 * np.exp(-((tth - 52.1)**2)/0.3)
    sim_peaks = [
        {"material_name": "Bi2Te3 (Theoretical)", "peaks": [
            {"two_theta": 27.48, "intensity": 100, "hkls": [{"hkl": [0, 1, 5]}]},
            {"two_theta": 38.15, "intensity": 65, "hkls": [{"hkl": [1, 0, 10]}]},
            {"two_theta": 52.05, "intensity": 45, "hkls": [{"hkl": [1, 1, 0]}]}
        ]}
    ]
    fig_xrd = create_xrd_plotly_figure(
        exp_tth=tth,
        exp_int=intensity,
        sim_results_list=sim_peaks,
        title=r"XRD Pattern - Bi₂Te₃ (Exp. vs Simulated Stick)",
        remove_bg=False
    )
    xrd_html_path = os.path.join(OUTPUT_DIR, "01_xrd_demo.html")
    fig_xrd.write_html(xrd_html_path)
    print(f"  └─ {xrd_html_path} 出力完了")

    # 2. Raman スペクトル (Raman Shift [cm⁻¹] vs Intensity)
    print("📊 2. Raman プロット生成中...")
    shift = np.linspace(100, 800, 800)
    raman_int = 50 + 200 * np.exp(-((shift - 135)**2)/50) + 450 * np.exp(-((shift - 520)**2)/40) + 120 * np.exp(-((shift - 650)**2)/80)
    fig_raman = create_academic_line_chart(
        x_data=shift,
        y_data=raman_int,
        title=r"Raman Spectrum - Si / MoS₂ Heterostructure",
        x_title=r"Raman Shift [cm⁻¹]",
        y_title=r"Intensity [a.u.]",
        line_name=r"Raman Peak",
        line_color="#d62728",
        show_legend=True
    )
    raman_html_path = os.path.join(OUTPUT_DIR, "02_raman_demo.html")
    fig_raman.write_html(raman_html_path)
    print(f"  └─ {raman_html_path} 出力完了")

    # 3. PPMS 輸送特性 (温度 T [K] vs 抵抗率 ρ [Ω·cm], 超伝導転移)
    print("📊 3. PPMS 4端子 R-T プロット生成中...")
    temp_k = np.linspace(2, 300, 600)
    res_ohm_cm = np.where(temp_k < 9.2, 1e-8, 1e-4 * (1 + 0.003 * (temp_k - 9.2)))
    fig_rt = create_academic_line_chart(
        x_data=temp_k,
        y_data=res_ohm_cm,
        title=r"PPMS Transport R-T Profile (NbN Thin Film, $T_\mathrm{c} = 9.2\ \mathrm{K}$)",
        x_title=r"Temperature $T$ [K]",
        y_title=r"Resistivity $\rho$ [$\Omega\cdot\mathrm{cm}$]",
        line_name=r"Zero Field ($H = 0\ \mathrm{T}$)",
        line_color="#1f77b4",
        show_legend=True
    )
    rt_html_path = os.path.join(OUTPUT_DIR, "03_ppms_rt_demo.html")
    fig_rt.write_html(rt_html_path)
    print(f"  └─ {rt_html_path} 出力完了")

    # 4. MPMS 磁気特性 (M-T FC/ZFC ペア, 磁化モーメント μB/f.u.)
    print("📊 4. MPMS M-T FC/ZFC ペアプロット生成中...")
    temp_m = np.linspace(5, 300, 300)
    mag_zfc = 0.5 * (1 - np.exp(-temp_m/50)) + 0.1 * np.exp(-((temp_m - 120)**2)/400)
    mag_fc = 0.5 + 0.8 * np.exp(-temp_m/80)
    traces_mpms = [
        {"x": temp_m, "y": mag_fc, "name": r"FC (Field-Cooled, $H = 1000\ \mathrm{Oe}$)", "color": "#d62728"},
        {"x": temp_m, "y": mag_zfc, "name": r"ZFC (Zero-Field-Cooled)", "color": "#1f77b4"}
    ]
    fig_mpms = create_multi_trace_chart(
        traces=traces_mpms,
        title=r"MPMS M-T Susceptibility - FeSe Single Crystal",
        x_title=r"Temperature $T$ [K]",
        y_title=r"Magnetization $M$ [$\mu_\mathrm{B}/\mathrm{f.u.}$]",
        show_legend=True
    )
    mpms_html_path = os.path.join(OUTPUT_DIR, "04_mpms_mt_demo.html")
    fig_mpms.write_html(mpms_html_path)
    print(f"  └─ {mpms_html_path} 出力完了")

    print("🎉 すべてのデモプロット HTML の生成・ファイル出力が完了いたしました！")

if __name__ == "__main__":
    generate_demo_plots()
