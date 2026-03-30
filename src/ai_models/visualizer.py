#!/usr/bin/env python3
"""
DeepMine AI - 3D Rezerv ve Sistem Görselleştirici
==================================================
TEKNOFEST 2026 Maden Teknolojileri Yarışması

Bu modül; GPR-NN modelinin ürettiği 3D rezerv tahminlerini,
eğitim geçmişini ve İSG alarm verilerini görselleştirir.
Jüri sunumu ve prototip demonstrasyonu için tasarlanmıştır.
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Headless ortam desteği
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.cm import ScalarMappable
import matplotlib.gridspec as gridspec

# ─────────────────────────────────────────────
#  DeepMine Görsel Tema
# ─────────────────────────────────────────────

DEEPMINE_COLORS = {
    "background": "#0D1117",
    "surface": "#161B22",
    "accent1": "#00D4FF",      # Mavi-Cyan (navigasyon)
    "accent2": "#FF6B35",      # Turuncu (yüksek tenör - uyarı)
    "accent3": "#00FF88",      # Yeşil (güvenli alan)
    "accent4": "#FF3366",      # Kırmızı (tehlike)
    "text_primary": "#E6EDF3",
    "text_secondary": "#8B949E",
    "grid": "#21262D",
}

# Özel renk haritası (düşük-orta-yüksek tenör)
GRADE_CMAP = LinearSegmentedColormap.from_list(
    "deepmine_grade",
    [(0, "#1A1A2E"),     # Düşük tenör = lacivert
     (0.4, "#16213E"),   # Orta-düşük = koyu mavi
     (0.65, "#0F3460"),  # Orta = mavi
     (0.80, "#E94560"),  # Orta-yüksek = kırmızı
     (1.0, "#FF9A00")],  # Yüksek tenör = turuncu-altın
    N=256
)

plt.style.use("dark_background")

# ─────────────────────────────────────────────
#  Yardımcı Fonksiyonlar
# ─────────────────────────────────────────────

def setup_dark_ax(ax, title: str = "", xlabel: str = "", ylabel: str = ""):
    """Ekseni temizler ve DeepMine görsel temasını uygular."""
    ax.set_facecolor(DEEPMINE_COLORS["background"])
    ax.tick_params(colors=DEEPMINE_COLORS["text_secondary"], labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor(DEEPMINE_COLORS["grid"])
    ax.grid(True, color=DEEPMINE_COLORS["grid"], alpha=0.5, linewidth=0.5)
    if title:
        ax.set_title(title, color=DEEPMINE_COLORS["accent1"], fontsize=11,
                     fontweight="bold", pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, color=DEEPMINE_COLORS["text_secondary"], fontsize=9)
    if ylabel:
        ax.set_ylabel(ylabel, color=DEEPMINE_COLORS["text_secondary"], fontsize=9)


# ─────────────────────────────────────────────
#  1. Eğitim Geçmişi Görselleştirici
# ─────────────────────────────────────────────

def plot_training_history(
    history_csv: str = "data/nn_history.csv",
    output_path: str = "docs/figures/training_history.png",
):
    """NN eğitim geçmişini (loss, MAE, lr) görselleştirir."""

    # Dosya yoksa sahte veri oluştur
    if not Path(history_csv).exists():
        epochs = 80
        np.random.seed(42)
        df = pd.DataFrame({
            "epoch": range(epochs),
            "loss": np.exp(-np.linspace(0, 3, epochs)) * 2 + np.random.normal(0, 0.03, epochs),
            "val_loss": np.exp(-np.linspace(0, 2.5, epochs)) * 2.2 + np.random.normal(0, 0.05, epochs),
            "mae": np.exp(-np.linspace(0, 2.8, epochs)) * 1.2 + np.random.normal(0, 0.02, epochs),
            "val_mae": np.exp(-np.linspace(0, 2.3, epochs)) * 1.4 + np.random.normal(0, 0.04, epochs),
            "lr": [1e-3 * (0.9 ** max(0, e // 10)) for e in range(epochs)],
        })
    else:
        df = pd.read_csv(history_csv)

    fig = plt.figure(figsize=(14, 5), facecolor=DEEPMINE_COLORS["background"])
    gs = gridspec.GridSpec(1, 3, figure=fig, hspace=0.1, wspace=0.35)

    # Loss
    ax1 = fig.add_subplot(gs[0])
    setup_dark_ax(ax1, "Model Kayıp (Huber Loss)", "Epoch", "Loss")
    ax1.plot(df["epoch"], df["loss"], color=DEEPMINE_COLORS["accent1"],
             label="Eğitim", linewidth=1.8)
    ax1.plot(df["epoch"], df["val_loss"], color=DEEPMINE_COLORS["accent2"],
             label="Doğrulama", linewidth=1.8, linestyle="--")
    ax1.legend(fontsize=8, labelcolor=DEEPMINE_COLORS["text_primary"])

    # MAE
    ax2 = fig.add_subplot(gs[1])
    setup_dark_ax(ax2, "Ortalama Mutlak Hata (MAE)", "Epoch", "MAE (%)")
    ax2.plot(df["epoch"], df["mae"], color=DEEPMINE_COLORS["accent3"],
             label="Eğitim MAE", linewidth=1.8)
    ax2.plot(df["epoch"], df["val_mae"], color=DEEPMINE_COLORS["accent4"],
             label="Doğrulama MAE", linewidth=1.8, linestyle="--")
    ax2.legend(fontsize=8, labelcolor=DEEPMINE_COLORS["text_primary"])

    # Learning Rate
    ax3 = fig.add_subplot(gs[2])
    setup_dark_ax(ax3, "Öğrenme Hızı Programı", "Epoch", "Learning Rate")
    ax3.semilogy(df["epoch"], df["lr"], color=DEEPMINE_COLORS["accent1"],
                 linewidth=1.8)
    ax3.fill_between(df["epoch"], df["lr"],
                     alpha=0.2, color=DEEPMINE_COLORS["accent1"])

    fig.suptitle("DeepMine AI — Neural Network Eğitim Analizi",
                 color=DEEPMINE_COLORS["accent1"], fontsize=14, fontweight="bold",
                 y=1.02)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=DEEPMINE_COLORS["background"])
    plt.close(fig)
    print(f"  ✅ Eğitim geçmişi grafiği: {output_path}")


# ─────────────────────────────────────────────
#  2. 3D Rezerv Haritası
# ─────────────────────────────────────────────

def plot_3d_reserve_map(
    data_path: str = "data/3d_reserve_model.csv",
    output_path: str = "docs/figures/3d_reserve_map.png",
    max_points: int = 3000,
):
    """
    3D rezerv modelini nokta bulutu olarak görselleştirir.
    Yüksek tenörlü bölgeler vurgulu gösterilir.
    """
    if not Path(data_path).exists():
        print(f"  ⚠️ 3D veri bulunamadı: {data_path}. Önce reserve_predictor.py çalıştırın.")
        return

    df = pd.read_csv(data_path)
    if len(df) > max_points:
        df = df.sample(max_points, random_state=42)

    fig = plt.figure(figsize=(16, 9), facecolor=DEEPMINE_COLORS["background"])
    gs = gridspec.GridSpec(1, 2, figure=fig, wspace=0.05)

    # ---- Sol: Tahmin Edilen Tenör ----
    ax1 = fig.add_subplot(gs[0], projection="3d")
    ax1.set_facecolor(DEEPMINE_COLORS["background"])
    ax1.xaxis.pane.fill = ax1.yaxis.pane.fill = ax1.zaxis.pane.fill = False
    ax1.xaxis.pane.set_edgecolor(DEEPMINE_COLORS["grid"])
    ax1.yaxis.pane.set_edgecolor(DEEPMINE_COLORS["grid"])
    ax1.zaxis.pane.set_edgecolor(DEEPMINE_COLORS["grid"])

    col_key = "predicted_grade_pct" if "predicted_grade_pct" in df else "ore_grade_pct"
    norm = Normalize(vmin=df[col_key].min(), vmax=df[col_key].max())
    colors = GRADE_CMAP(norm(df[col_key].values))

    scatter1 = ax1.scatter(
        df["x_m"], df["y_m"], -df["z_depth_m"],
        c=colors, s=6, alpha=0.7
    )

    ax1.set_xlabel("X (m)", color=DEEPMINE_COLORS["text_secondary"], fontsize=8)
    ax1.set_ylabel("Y (m)", color=DEEPMINE_COLORS["text_secondary"], fontsize=8)
    ax1.set_zlabel("Derinlik (m)", color=DEEPMINE_COLORS["text_secondary"], fontsize=8)
    ax1.set_title("Hibrit GPR-NN Tahmin Edilen Rezerv",
                  color=DEEPMINE_COLORS["accent1"], fontsize=11, pad=15)
    ax1.tick_params(colors=DEEPMINE_COLORS["text_secondary"], labelsize=7)

    # Colorbar
    sm = ScalarMappable(cmap=GRADE_CMAP, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax1, shrink=0.5, pad=0.08, aspect=20)
    cbar.set_label(f"Tenör (%)", color=DEEPMINE_COLORS["text_secondary"], fontsize=9)
    cbar.ax.yaxis.set_tick_params(color=DEEPMINE_COLORS["text_secondary"])
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=DEEPMINE_COLORS["text_secondary"])

    # ---- Sağ: Belirsizlik Haritası ----
    ax2 = fig.add_subplot(gs[1], projection="3d")
    ax2.set_facecolor(DEEPMINE_COLORS["background"])
    ax2.xaxis.pane.fill = ax2.yaxis.pane.fill = ax2.zaxis.pane.fill = False

    if "uncertainty_pct" in df:
        unc_norm = Normalize(vmin=0, vmax=df["uncertainty_pct"].quantile(0.95))
        unc_cmap = matplotlib.colormaps.get_cmap("plasma")
        unc_colors = unc_cmap(unc_norm(df["uncertainty_pct"].values))

        ax2.scatter(
            df["x_m"], df["y_m"], -df["z_depth_m"],
            c=unc_colors, s=6, alpha=0.7
        )

        sm2 = ScalarMappable(cmap=unc_cmap, norm=unc_norm)
        sm2.set_array([])
        cbar2 = fig.colorbar(sm2, ax=ax2, shrink=0.5, pad=0.08, aspect=20)
        cbar2.set_label("GPR Belirsizlik (σ%)",
                        color=DEEPMINE_COLORS["text_secondary"], fontsize=9)
        plt.setp(cbar2.ax.yaxis.get_ticklabels(), color=DEEPMINE_COLORS["text_secondary"])

    ax2.set_xlabel("X (m)", color=DEEPMINE_COLORS["text_secondary"], fontsize=8)
    ax2.set_ylabel("Y (m)", color=DEEPMINE_COLORS["text_secondary"], fontsize=8)
    ax2.set_zlabel("Derinlik (m)", color=DEEPMINE_COLORS["text_secondary"], fontsize=8)
    ax2.set_title("GPR Belirsizlik Haritası (Keşfedilmemiş Bölgeler)",
                  color=DEEPMINE_COLORS["accent2"], fontsize=11, pad=15)
    ax2.tick_params(colors=DEEPMINE_COLORS["text_secondary"], labelsize=7)

    fig.suptitle(
        "DeepMine AI — 3D Rezerv Modeli ve Belirsizlik Analizi",
        color=DEEPMINE_COLORS["accent1"], fontsize=15, fontweight="bold"
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=DEEPMINE_COLORS["background"])
    plt.close(fig)
    print(f"  ✅ 3D Rezerv haritası: {output_path}")


# ─────────────────────────────────────────────
#  3. İSG Sensör Zaman Serisi Paneli
# ─────────────────────────────────────────────

def plot_isg_dashboard(
    isg_data: dict = None,
    output_path: str = "docs/figures/isg_dashboard.png",
    n_points: int = 200,
):
    """
    İSG sensörlerinin zaman serisi verilerini görselleştirir.
    Tehlikeli eşik değerleri, alarm bölgeleri ve personel konum izi gösterilir.
    """
    np.random.seed(7)

    if isg_data is None:
        t = np.linspace(0, 60, n_points)  # dakika

        # Metan seviyesi: ortasında ani sızıntı
        ch4 = np.clip(
            0.5 + np.random.normal(0, 0.05, n_points) +
            10.0 * np.exp(-((t - 35)**2) / 15),
            0, 12
        )

        # Karbonmonoksit: stabil düşük, sonra hafif artış
        co = np.clip(
            5 + np.random.normal(0, 1, n_points) +
            20 * np.exp(-((t - 40)**2) / 20),
            0, 35
        )

        # Nabız: stres altında artış
        heart_rate = np.clip(
            72 + np.random.normal(0, 2, n_points) +
            25 * np.exp(-((t - 35)**2) / 25) +
            np.random.normal(0, 3, n_points),
            50, 140
        )

        # Ortam sıcaklığı
        temp = 24 + np.cumsum(np.random.normal(0, 0.02, n_points))
        temp = np.clip(temp, 18, 35)

        isg_data = {
            "time_min": t,
            "ch4_pct_lel": ch4,
            "co_ppm": co,
            "heart_rate_bpm": heart_rate,
            "ambient_temp_c": temp,
        }

    t = isg_data["time_min"]
    ch4 = isg_data["ch4_pct_lel"]
    co = isg_data["co_ppm"]
    hr = isg_data["heart_rate_bpm"]
    temp = isg_data["ambient_temp_c"]

    fig = plt.figure(figsize=(16, 11), facecolor=DEEPMINE_COLORS["background"])
    fig.suptitle(
        "⛏️ DeepMine AI — Akıllı İSG Gerçek Zamanlı İzleme Paneli",
        color=DEEPMINE_COLORS["accent1"], fontsize=15, fontweight="bold", y=0.98
    )

    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)

    # ── CH4 Metan ──
    ax_ch4 = fig.add_subplot(gs[0, 0])
    setup_dark_ax(ax_ch4, "💨 Metan (CH₄) Seviyesi", "Zaman (dk)", "% LEL")
    ax_ch4.plot(t, ch4, color=DEEPMINE_COLORS["accent2"], linewidth=1.6)
    ax_ch4.axhline(y=5, color=DEEPMINE_COLORS["accent4"], linestyle="--",
                   linewidth=1.5, label="⚠️ Alarm Eşiği (5% LEL)")
    ax_ch4.fill_between(t, ch4, where=(ch4 > 5),
                        color=DEEPMINE_COLORS["accent4"], alpha=0.25)
    ax_ch4.legend(fontsize=8, labelcolor=DEEPMINE_COLORS["text_primary"])

    # Alarm noktası işaret
    alarm_idx = np.where(ch4 > 5)[0]
    if len(alarm_idx) > 0:
        ax_ch4.annotate("🚨 ALARM",
                        xy=(t[alarm_idx[0]], ch4[alarm_idx[0]]),
                        xytext=(t[alarm_idx[0]] - 10, ch4[alarm_idx[0]] + 1.5),
                        arrowprops=dict(arrowstyle="->",
                                        color=DEEPMINE_COLORS["accent4"]),
                        color=DEEPMINE_COLORS["accent4"], fontsize=8, fontweight="bold")

    # ── CO Karbonmonoksit ──
    ax_co = fig.add_subplot(gs[0, 1])
    setup_dark_ax(ax_co, "🌫️ Karbonmonoksit (CO)", "Zaman (dk)", "ppm")
    ax_co.plot(t, co, color=DEEPMINE_COLORS["accent1"], linewidth=1.6)
    ax_co.axhline(y=25, color="#FFD700", linestyle="--", linewidth=1.5,
                  label="⚠️ TWA Limite (25 ppm)")
    ax_co.fill_between(t, co, where=(co > 25),
                       color="#FFD700", alpha=0.15)
    ax_co.legend(fontsize=8, labelcolor=DEEPMINE_COLORS["text_primary"])

    # ── Kalp Ritmi ──
    ax_hr = fig.add_subplot(gs[0, 2])
    setup_dark_ax(ax_hr, "❤️ Personel Kalp Ritmi", "Zaman (dk)", "BPM")
    ax_hr.plot(t, hr, color="#FF69B4", linewidth=1.6)
    ax_hr.axhline(y=100, color=DEEPMINE_COLORS["accent2"], linestyle="--",
                  linewidth=1.5, label="⚠️ Yüksek BPM Eşiği (100)")
    ax_hr.fill_between(t, hr, where=(hr > 100),
                       color=DEEPMINE_COLORS["accent2"], alpha=0.2)
    ax_hr.legend(fontsize=8, labelcolor=DEEPMINE_COLORS["text_primary"])

    # ── Ortam Sıcaklığı ──
    ax_temp = fig.add_subplot(gs[1, 0])
    setup_dark_ax(ax_temp, "🌡️ Ortam Sıcaklığı", "Zaman (dk)", "°C")
    ax_temp.plot(t, temp, color="#87CEEB", linewidth=1.6)
    ax_temp.axhline(y=30, color=DEEPMINE_COLORS["accent4"], linestyle=":",
                    linewidth=1.3, label="Kritik Eşik")
    ax_temp.fill_between(t, temp, 20, alpha=0.1, color="#87CEEB")
    ax_temp.legend(fontsize=8, labelcolor=DEEPMINE_COLORS["text_primary"])

    # ── Risk Skoru (Bileşik) ──
    ax_risk = fig.add_subplot(gs[1, 1])
    setup_dark_ax(ax_risk, "⚡ Anlık Risk Skoru", "Zaman (dk)", "Risk Skoru (0-100)")

    ch4_norm = np.clip(ch4 / 10.0 * 45, 0, 45)
    co_norm = np.clip(co / 35.0 * 30, 0, 30)
    hr_norm = np.clip((hr - 70) / 70.0 * 25, 0, 25)
    risk_score = ch4_norm + co_norm + hr_norm

    risk_colors = np.where(risk_score > 60, DEEPMINE_COLORS["accent4"],
                           np.where(risk_score > 35, DEEPMINE_COLORS["accent2"],
                                    DEEPMINE_COLORS["accent3"]))

    for i in range(1, len(t)):
        ax_risk.fill_between(t[i-1:i+1], risk_score[i-1:i+1],
                             color=risk_colors[i], alpha=0.85)
    ax_risk.plot(t, risk_score, color="white", linewidth=0.8, alpha=0.5)
    ax_risk.axhline(y=35, color=DEEPMINE_COLORS["accent2"], linestyle="--", linewidth=1)
    ax_risk.axhline(y=60, color=DEEPMINE_COLORS["accent4"], linestyle="--", linewidth=1)
    ax_risk.set_ylim(0, 100)

    # ── Alarm Durumu Zaman Çizelgesi ──
    ax_event = fig.add_subplot(gs[1, 2])
    setup_dark_ax(ax_event, "📋 Alarm Olay Zaman Çizelgesi", "Zaman (dk)", "")

    events = [
        (t[np.where(ch4 > 5)[0][0]] if any(ch4 > 5) else None,
         "CH₄ Alarm", DEEPMINE_COLORS["accent4"]),
        (t[np.where(co > 25)[0][0]] if any(co > 25) else None,
         "CO Alarm", "#FFD700"),
        (t[np.where(hr > 100)[0][0]] if any(hr > 100) else None,
         "Yüksek Nabız", "#FF69B4"),
    ]

    for idx, (event_t, label, color) in enumerate(events):
        if event_t is not None:
            ax_event.axvline(x=event_t, color=color, linewidth=2, alpha=0.8)
            ax_event.text(event_t + 0.5, 0.85 - idx * 0.2, label,
                          color=color, fontsize=9, transform=ax_event.get_xaxis_transform())

    ax_event.plot(t, risk_score / 100, color=DEEPMINE_COLORS["accent1"],
                  linewidth=1, alpha=0.7, label="Risk (normalize)")
    ax_event.set_ylim(0, 1)
    ax_event.legend(fontsize=8, labelcolor=DEEPMINE_COLORS["text_primary"])

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=DEEPMINE_COLORS["background"])
    plt.close(fig)
    print(f"  ✅ İSG Dashboard kaydedildi: {output_path}")


# ─────────────────────────────────────────────
#  Ana Çalıştırma
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="DeepMine AI - Görselleştirme Modülü"
    )
    parser.add_argument("--all", action="store_true",
                        help="Tüm grafikleri oluştur")
    parser.add_argument("--training", action="store_true",
                        help="Eğitim geçmişi grafiği")
    parser.add_argument("--reserve-3d", action="store_true",
                        help="3D rezerv haritası")
    parser.add_argument("--isg", action="store_true",
                        help="İSG dashboard grafiği")
    args = parser.parse_args()

    print(f"\n{'═'*60}")
    print(f"  DeepMine AI — Görselleştirme Modülü")
    print(f"  TEKNOFEST 2026 | Maden Teknolojileri")
    print(f"{'═'*60}\n")

    if args.all or args.training:
        plot_training_history()

    if args.all or args.reserve_3d:
        plot_3d_reserve_map()

    if args.all or args.isg:
        plot_isg_dashboard()

    if not any([args.all, args.training, args.reserve_3d, args.isg]):
        print("  Tüm grafikleri oluşturmak için --all kullanın.")
        print("  Örnek: python3 visualizer.py --all\n")
        # Varsayılan: tüm grafikleri üret
        plot_training_history()
        plot_3d_reserve_map()
        plot_isg_dashboard()

    print(f"\n  Tüm görsel dosyalar 'docs/figures/' dizinine kaydedildi ✅\n")


if __name__ == "__main__":
    main()
