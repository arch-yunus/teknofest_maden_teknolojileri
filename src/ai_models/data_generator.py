#!/usr/bin/env python3
"""
DeepMine AI - Sentetik Maden Saha Verisi Üretici
=================================================
TEKNOFEST 2026 Maden Teknolojileri Yarışması
Tema 4.2.2: Yapay Zeka Destekli Arama ve Planlama Yazılımları

Bu modül; gerçekçi jeofizik ve sondaj verilerini simüle eden
sentetik veri seti üretir. GPR-NN Rezerv Tahmin modeli için
eğitim ve doğrulama verisi sağlar.

Üretilen özellikler (features):
  - depth_m          : Sondaj derinliği (metre)
  - magnetic_nT      : Manyetik anomali (nanoTesla)
  - gravity_mGal     : Yerçekimi anomalisi (miliGal)
  - resistivity_ohm  : Elektriksel özdirenç (Ohm·m)
  - chargeability_ms : Yükleme kapasitesi IP anomalisi (ms)
  - seismic_vp_ms    : P-dalgası hızı (m/s)
  - rock_density     : Kayaç yoğunluğu (g/cm³)
  - alteration_idx   : Alterasyon indisi (0-1)

Hedef (target):
  - ore_grade_pct    : Cevher tenörü (%)
"""

import numpy as np
import pandas as pd
import os
import argparse
from pathlib import Path

# ─────────────────────────────────────────────
#  Sabitler ve Bölge Parametreleri
# ─────────────────────────────────────────────

SEED = 42
np.random.seed(SEED)

# Türkiye'ye özgü jeolojik bölge parametreleri
REGION_PROFILES = {
    "bor_rich": {
        "description": "Bor-zengin tuz gölü havzası (Kırka/Emet tipi)",
        "depth_range": (20, 350),
        "grade_range": (5, 45),      # % B2O3
        "grade_mean": 28.0,
        "alteration_factor": 0.85,
    },
    "rare_earth": {
        "description": "Nadir toprak elementi yatağı (Kızılcaören tipi)",
        "depth_range": (50, 800),
        "grade_range": (0.05, 8.0),  # % TREE
        "grade_mean": 2.5,
        "alteration_factor": 0.70,
    },
    "copper_porphyry": {
        "description": "Porfiri bakır yatağı (Gediz tipi)",
        "depth_range": (100, 1000),
        "grade_range": (0.1, 2.5),   # % Cu
        "grade_mean": 0.6,
        "alteration_factor": 0.60,
    },
    "coal": {
        "description": "Linyit kömür yatağı (Soma/Tunçbilek tipi)",
        "depth_range": (10, 200),
        "grade_range": (15, 45),     # % uçucu madde (kCV)
        "grade_mean": 30.0,
        "alteration_factor": 0.40,
    },
}


def generate_geophysical_features(n_samples: int, profile: dict) -> dict:
    """
    Verilen bölge profiline göre gerçekçi jeofizik özellikleri üretir.
    Her özellik için fiziksel ilişkiler (korelasyonlar) simüle edilir.
    """
    depth_min, depth_max = profile["depth_range"]
    grade_min, grade_max = profile["grade_range"]
    grade_mean = profile["grade_mean"]
    alt_factor = profile["alteration_factor"]

    # Derinlik: lognormal dağılım (sığ yataklar daha olası)
    depth = np.random.lognormal(
        mean=np.log((depth_min + depth_max) / 2),
        sigma=0.5,
        size=n_samples
    ).clip(depth_min, depth_max)

    # Cevher tenörü: zengin zon anomalileri içeren karışık dağılım
    # Gerçek yataklarda %10 yüksek tenörlü, %90 düşük tenörlü bölge
    high_grade_mask = np.random.random(n_samples) < 0.12
    grade_base = np.random.beta(a=2, b=5, size=n_samples) * (grade_max - grade_min) + grade_min
    grade_high = np.random.beta(a=5, b=2, size=n_samples) * (grade_max - grade_min) + grade_min
    ore_grade = np.where(high_grade_mask, grade_high, grade_base)
    ore_grade = ore_grade.clip(grade_min, grade_max)

    # Manyetik anomali (nT): cevher tenörüyle pozitif korelasyon + gürültü
    magnetic_nT = (
        ore_grade * 15.0 +
        depth * (-0.1) +
        np.random.normal(0, 20, n_samples)
    ).clip(-100, 500)

    # Yerçekimi anomalisi (mGal): yüksek yoğunluklu cevherle korelasyon
    gravity_mGal = (
        ore_grade * 0.8 +
        depth * 0.002 +
        np.random.normal(0, 0.5, n_samples)
    ).clip(-5, 15)

    # Elektrik özdirenç (Ohm·m): sülfürler düşük direnç gösterir
    # Ters korelasyon (tenör arttıkça direnç düşer) + depth etkisi
    resistivity = (
        np.exp(-ore_grade / grade_max * 3) * 500 +
        depth * 0.8 +
        np.random.lognormal(3, 0.5, n_samples)
    ).clip(5, 5000)

    # Yükleme kapasitesi / IP (ms): sülfür mineralizasyonunu gösterir
    chargeability = (
        ore_grade / grade_max * 40 +
        np.random.exponential(5, n_samples)
    ).clip(0, 80)

    # Sismik P-dalgası hızı (m/s): sağlam kaya = yüksek hız
    seismic_vp = (
        4500 - depth * 0.5 - ore_grade * 25 +
        np.random.normal(0, 200, n_samples)
    ).clip(1500, 6500)

    # Kayaç yoğunluğu (g/cm³): tenörle hafif pozitif korelasyon
    rock_density = (
        2.65 + ore_grade / grade_max * 0.8 +
        np.random.normal(0, 0.1, n_samples)
    ).clip(2.2, 3.8)

    # Alterasyon indisi (0-1): cevher zonlarında yüksek
    alteration = (
        ore_grade / grade_max * alt_factor +
        np.random.beta(1, 4, n_samples) * (1 - alt_factor)
    ).clip(0, 1)

    # 3D koordinatlar (simüle edilmiş sondaj noktaları - 500x500 m saha)
    utm_x = np.random.uniform(0, 500, n_samples)
    utm_y = np.random.uniform(0, 500, n_samples)

    return {
        "utm_x_m": utm_x.round(2),
        "utm_y_m": utm_y.round(2),
        "depth_m": depth.round(2),
        "magnetic_nT": magnetic_nT.round(3),
        "gravity_mGal": gravity_mGal.round(4),
        "resistivity_ohm": resistivity.round(2),
        "chargeability_ms": chargeability.round(3),
        "seismic_vp_ms": seismic_vp.round(1),
        "rock_density_gcc": rock_density.round(4),
        "alteration_idx": alteration.round(4),
        "ore_grade_pct": ore_grade.round(4),
    }


def generate_dataset(
    n_samples: int = 2000,
    region: str = "bor_rich",
    output_dir: str = "data",
    train_split: float = 0.8,
    include_noise: bool = True,
) -> tuple:
    """
    Eğitim ve test veri setlerini üretip CSV olarak kaydeder.

    Returns:
        (df_train, df_test): pandas DataFrame tuple
    """
    if region not in REGION_PROFILES:
        raise ValueError(
            f"Bilinmeyen bölge: '{region}'. "
            f"Mevcut bölgeler: {list(REGION_PROFILES.keys())}"
        )

    profile = REGION_PROFILES[region]
    print(f"\n{'='*60}")
    print(f"  DeepMine AI - Sentetik Veri Üretici")
    print(f"{'='*60}")
    print(f"  Bölge    : {profile['description']}")
    print(f"  Örnek    : {n_samples:,}")
    print(f"  Eğitim   : {int(n_samples * train_split):,}")
    print(f"  Test     : {int(n_samples * (1 - train_split)):,}")
    print(f"{'='*60}\n")

    # Veriyi üret
    data = generate_geophysical_features(n_samples, profile)
    df = pd.DataFrame(data)

    # Sensör gürültüsü ekle (gerçekçi ölçüm hataları)
    if include_noise:
        noise_cols = {
            "magnetic_nT": 3.0,
            "gravity_mGal": 0.05,
            "resistivity_ohm": 15.0,
            "chargeability_ms": 1.5,
            "seismic_vp_ms": 50.0,
        }
        for col, sigma in noise_cols.items():
            df[col] += np.random.normal(0, sigma, n_samples)

    # Eğitim/test bölünme
    split_idx = int(n_samples * train_split)
    df_train = df.iloc[:split_idx].reset_index(drop=True)
    df_test = df.iloc[split_idx:].reset_index(drop=True)

    # Dosya kayıt
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    train_path = out_path / f"drill_data_{region}_train.csv"
    test_path = out_path / f"drill_data_{region}_test.csv"

    df_train.to_csv(train_path, index=False)
    df_test.to_csv(test_path, index=False)

    print(f"  ✅ Eğitim verisi kaydedildi : {train_path}")
    print(f"  ✅ Test verisi kaydedildi   : {test_path}")

    # Özet istatistikler
    print(f"\n  Tenör İstatistikleri (Hedef: ore_grade_pct):")
    print(f"  ├─ Ortalama : {df['ore_grade_pct'].mean():.3f}%")
    print(f"  ├─ Std Dev  : {df['ore_grade_pct'].std():.3f}%")
    print(f"  ├─ Min      : {df['ore_grade_pct'].min():.3f}%")
    print(f"  └─ Max      : {df['ore_grade_pct'].max():.3f}%\n")

    return df_train, df_test


def generate_3d_grid(
    grid_size: int = 20,
    depth_levels: int = 10,
    region: str = "bor_rich",
    output_path: str = "data/3d_grid.csv",
) -> pd.DataFrame:
    """
    3D rezerv görselleştirmesi için ızgara veri seti üretir.
    X-Y-Z koordinatlarında jeofizik değerler içerir.
    """
    profile = REGION_PROFILES[region]
    depth_min, depth_max = profile["depth_range"]

    x_coords = np.linspace(0, 500, grid_size)
    y_coords = np.linspace(0, 500, grid_size)
    z_depths = np.linspace(depth_min, depth_max, depth_levels)

    rows = []
    for z in z_depths:
        for y in y_coords:
            for x in x_coords:
                # Basit tenör modeli: zengin bölge merkez civarında
                dist_to_center = np.sqrt((x - 250)**2 + (y - 250)**2)
                base_grade = profile["grade_mean"] * np.exp(-dist_to_center / 150)
                base_grade *= np.exp(-z / (depth_max * 0.7))
                noise = np.random.normal(0, base_grade * 0.2)
                grade = max(0, base_grade + noise)

                rows.append({
                    "x_m": round(x, 1),
                    "y_m": round(y, 1),
                    "z_depth_m": round(z, 1),
                    "ore_grade_pct": round(grade, 4),
                })

    df_grid = pd.DataFrame(rows)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df_grid.to_csv(output_path, index=False)
    print(f"  ✅ 3D ızgara verisi kaydedildi: {output_path} ({len(df_grid):,} nokta)")
    return df_grid


# ─────────────────────────────────────────────
#  CLI Arayüzü
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="DeepMine AI - Sentetik Maden Jeofizik Veri Üretici"
    )
    parser.add_argument("--samples", type=int, default=2000,
                        help="Üretilecek toplam örnek sayısı (varsayılan: 2000)")
    parser.add_argument("--region", type=str, default="bor_rich",
                        choices=list(REGION_PROFILES.keys()),
                        help="Jeolojik bölge profili")
    parser.add_argument("--output", type=str, default="data",
                        help="Çıktı dizini")
    parser.add_argument("--no-noise", action="store_true",
                        help="Sensör gürültüsünü devre dışı bırak")
    parser.add_argument("--generate-3d", action="store_true",
                        help="3D ızgara veri setini de üret")

    args = parser.parse_args()

    df_train, df_test = generate_dataset(
        n_samples=args.samples,
        region=args.region,
        output_dir=args.output,
        include_noise=not args.no_noise,
    )

    if args.generate_3d:
        generate_3d_grid(
            region=args.region,
            output_path=os.path.join(args.output, "3d_grid.csv"),
        )

    print("\n  [Data Generator] Veri üretimi tamamlandı.\n")
