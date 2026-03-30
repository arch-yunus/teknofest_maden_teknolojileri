#!/usr/bin/env python3
"""
DeepMine AI - Hibrit GPR-NN Rezerv Tahmin Modeli
=================================================
TEKNOFEST 2026 Maden Teknolojileri Yarışması
Tema 4.2.2: Yapay Zeka Destekli Arama ve Planlama Yazılımları

Şartname Uyumluluğu:
  ✅ Sondaj verilerini anlık işleyerek 3D cevher modellemesi yapan karar destek yazılımı
  ✅ Potansiyel rezerv alanlarını yüksek doğrulukla tahmin eden ML modeli
  ✅ Olası makine arızalarını önceden tahmin eden kestirimci analiz sistemi

Mimari:
  1. Neural Network (NN): TensorFlow/Keras ile geniş ölçekli jeolojik paternleri öğrenir.
  2. Gaussian Process Regression (GPR): Her tahmin için belirsizlik (uncertainty) üretir.
  3. Hibrit Birleştirme: ε(x) = y - f_NN(x) residual'ı GPR ile modellenir.
     Nihai tahmin: ŷ = f_NN(x) + μ_ε(x) ± σ_ε(x)

Matematiksel Temel:
  f(x) ∼ GP(m(x), k(x, x'))
  k(x, x') = σ²·exp(-||x - x'||² / (2ℓ²))  [RBF Kernel]
"""

import os
import sys
import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Sklearn: Veri ön işleme ve GPR
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel, Matern, ConstantKernel
from sklearn.model_selection import cross_val_score
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import joblib

# TensorFlow: Neural Network
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"  # TF log gürültüsünü azalt
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, regularizers, callbacks

# Veri üretici
from data_generator import generate_dataset, generate_3d_grid, REGION_PROFILES

# ─────────────────────────────────────────────
#  Sabitler
# ─────────────────────────────────────────────

FEATURE_COLS = [
    "depth_m",
    "magnetic_nT",
    "gravity_mGal",
    "resistivity_ohm",
    "chargeability_ms",
    "seismic_vp_ms",
    "rock_density_gcc",
    "alteration_idx",
]

TARGET_COL = "ore_grade_pct"

MODELS_DIR = Path("models")
DATA_DIR = Path("data")

tf.random.set_seed(42)
np.random.seed(42)


# ─────────────────────────────────────────────
#  Neural Network: Ana Tenör Tahmincisi
# ─────────────────────────────────────────────

def build_nn_model(input_dim: int, learning_rate: float = 1e-3) -> keras.Model:
    """
    Derin sinir ağı modeli oluşturur.
    Mimari: İnput → [Dense(256, ReLU) → BN → Dropout] × 3 → Dense(64) → Dense(1)

    Düzenleyiciler:
      - L2 regularization (overfit önleme)
      - Batch Normalization (eğitim kararlılığı)
      - Dropout (genelleme kapasitesi)
    """
    inputs = keras.Input(shape=(input_dim,), name="geophysics_input")

    # Blok 1
    x = layers.Dense(256, kernel_regularizer=regularizers.l2(1e-4),
                     name="dense_1")(inputs)
    x = layers.BatchNormalization(name="bn_1")(x)
    x = layers.Activation("swish", name="act_1")(x)
    x = layers.Dropout(0.25, name="drop_1")(x)

    # Blok 2
    x = layers.Dense(256, kernel_regularizer=regularizers.l2(1e-4),
                     name="dense_2")(x)
    x = layers.BatchNormalization(name="bn_2")(x)
    x = layers.Activation("swish", name="act_2")(x)
    x = layers.Dropout(0.25, name="drop_2")(x)

    # Blok 3
    x = layers.Dense(128, kernel_regularizer=regularizers.l2(1e-4),
                     name="dense_3")(x)
    x = layers.BatchNormalization(name="bn_3")(x)
    x = layers.Activation("swish", name="act_3")(x)
    x = layers.Dropout(0.15, name="drop_3")(x)

    # Blok 4
    x = layers.Dense(64, activation="swish", name="dense_4")(x)

    # Çıkış (tenör tahmini ≥ 0)
    output = layers.Dense(1, activation="softplus", name="grade_output")(x)

    model = keras.Model(inputs=inputs, outputs=output, name="DeepMine_NN")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
        loss="huber",           # Aykırı değerlere karşı dayanıklı kayıp
        metrics=["mae", "mse"]
    )
    return model


def train_neural_network(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    epochs: int = 200,
    batch_size: int = 64,
) -> tuple:
    """
    Neural Network eğitir ve tarihçeyi döndürür.

    Returns:
        (model, history): Eğitilmiş model ve eğitim tarihçesi
    """
    model = build_nn_model(X_train.shape[1])

    print(f"\n  {'─'*50}")
    print(f"  Neural Network Mimarisi:")
    model.summary(print_fn=lambda x: print(f"    {x}"))
    print(f"  {'─'*50}\n")

    model_callbacks = [
        callbacks.EarlyStopping(
            monitor="val_loss",
            patience=25,
            restore_best_weights=True,
            verbose=1,
        ),
        callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=10,
            min_lr=1e-6,
            verbose=1,
        ),
        callbacks.ModelCheckpoint(
            filepath=str(MODELS_DIR / "nn_best_model.keras"),
            monitor="val_loss",
            save_best_only=True,
            verbose=0,
        ),
    ]

    print("  NN Eğitimi Başlıyor...")
    t_start = time.time()
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=model_callbacks,
        verbose=1,
    )
    t_elapsed = time.time() - t_start
    print(f"  ✅ NN Eğitimi tamamlandı [{t_elapsed:.1f}s]")
    return model, history


# ─────────────────────────────────────────────
#  GPR: Residual Modelleme ve Belirsizlik
# ─────────────────────────────────────────────

def train_gpr_on_residuals(
    X_train: np.ndarray,
    residuals: np.ndarray,
    n_restarts: int = 5,
) -> GaussianProcessRegressor:
    """
    NN residual'larını GPR ile modeller.

    Kernel:
      k(x, x') = C * Matern(ν=2.5) + WhiteKernel
      Matern ν=2.5: RBF'den daha az düzgün; gerçek jeolojik verilere uygun.

    Returns:
        Eğitilmiş GaussianProcessRegressor
    """
    print("\n  GPR Residual Modeli Eğitiliyor...")

    kernel = (
        ConstantKernel(1.0, (1e-3, 1e3)) *
        Matern(length_scale=1.0, length_scale_bounds=(1e-2, 10.0), nu=2.5) +
        WhiteKernel(noise_level=0.1, noise_level_bounds=(1e-5, 1.0))
    )

    # GPR için veri örneği (hesaplama maliyeti nedeniyle)
    max_gpr_samples = min(500, len(X_train))
    idx = np.random.choice(len(X_train), max_gpr_samples, replace=False)

    gpr = GaussianProcessRegressor(
        kernel=kernel,
        n_restarts_optimizer=n_restarts,
        normalize_y=True,
        alpha=1e-6,  # Sayısal kararlılık
    )

    t_start = time.time()
    gpr.fit(X_train[idx], residuals[idx])
    t_elapsed = time.time() - t_start
    print(f"  ✅ GPR eğitildi [{t_elapsed:.1f}s]")
    print(f"  GPR Kernel Parametreleri : {gpr.kernel_}")
    return gpr


# ─────────────────────────────────────────────
#  Hibrit Tahminleme Pipeline
# ─────────────────────────────────────────────

class HybridGPRNN:
    """
    DeepMine AI Hibrit GPR-NN Rezerv Tahmin Sistemi

    Çalışma Prensibi:
      1. NN ile temel tenör tahmini: ŷ_NN = f_NN(x)
      2. Residual hesapla: ε = y - ŷ_NN
      3. GPR ile residual model: ε(x) ~ GP(0, k(x, x'))
      4. Hibrit tahmin: ŷ = ŷ_NN + μ_GPR_ε(x)
      5. Belirsizlik: σ = σ_GPR_ε(x)
    """

    def __init__(self):
        self.nn_model = None
        self.gpr_model = None
        self.feature_scaler = None
        self.target_scaler = None
        self.is_trained = False
        self.region = None
        self.training_metrics = {}

    def fit(
        self,
        df_train: pd.DataFrame,
        df_val: pd.DataFrame,
        region: str = "bor_rich",
        nn_epochs: int = 200,
    ):
        """
        Modeli eğit: NN + GPR residual birlikte.
        """
        self.region = region
        print(f"\n{'═'*60}")
        print(f"  DeepMine AI - Hibrit GPR-NN Model Eğitimi")
        print(f"  Bölge: {REGION_PROFILES[region]['description']}")
        print(f"{'═'*60}")

        # ---- Veri hazırlama ----
        X_train_raw = df_train[FEATURE_COLS].values
        y_train = df_train[TARGET_COL].values
        X_val_raw = df_val[FEATURE_COLS].values
        y_val = df_val[TARGET_COL].values

        # Özellik normalizasyonu (RobustScaler: aykırı değerlere dayanıklı)
        self.feature_scaler = RobustScaler()
        X_train = self.feature_scaler.fit_transform(X_train_raw)
        X_val = self.feature_scaler.transform(X_val_raw)

        print(f"\n  Eğitim Örnekleri : {len(X_train):,}")
        print(f"  Doğrulama Örnekleri: {len(X_val):,}")
        print(f"  Özellik Sayısı   : {X_train.shape[1]}")

        # ---- Faz 1: Neural Network Eğitimi ----
        MODELS_DIR.mkdir(exist_ok=True)
        print(f"\n  [Faz 1/3] Neural Network Eğitimi...")
        self.nn_model, history = train_neural_network(
            X_train, y_train, X_val, y_val, epochs=nn_epochs
        )

        # ---- Faz 2: Residual Hesaplama ----
        print(f"\n  [Faz 2/3] Residual Hesaplama...")
        y_pred_nn_train = self.nn_model.predict(X_train, verbose=0).flatten()
        residuals = y_train - y_pred_nn_train
        print(f"  Residual İstatistikleri:")
        print(f"  ├─ Ortalama : {residuals.mean():.4f}")
        print(f"  ├─ Std Dev  : {residuals.std():.4f}")
        print(f"  └─ RMSE     : {np.sqrt(np.mean(residuals**2)):.4f}")

        # ---- Faz 3: GPR Residual Modeli ----
        print(f"\n  [Faz 3/3] GPR Residual Modeli...")
        self.gpr_model = train_gpr_on_residuals(X_train, residuals)

        # ---- Doğrulama Metrikleri ----
        y_pred_hybrid, y_uncertainty = self.predict(df_val)
        rmse = np.sqrt(mean_squared_error(y_val, y_pred_hybrid))
        mae = mean_absolute_error(y_val, y_pred_hybrid)
        r2 = r2_score(y_val, y_pred_hybrid)

        self.training_metrics = {
            "rmse": rmse,
            "mae": mae,
            "r2": r2,
            "mean_uncertainty": float(y_uncertainty.mean()),
        }

        print(f"\n  {'─'*50}")
        print(f"  Hibrit Model Doğrulama Sonuçları:")
        print(f"  ├─ RMSE               : {rmse:.4f}%")
        print(f"  ├─ MAE                : {mae:.4f}%")
        print(f"  ├─ R² Skoru           : {r2:.4f}")
        print(f"  └─ Ort. Belirsizlik  : ±{y_uncertainty.mean():.4f}%")
        print(f"  {'─'*50}")

        self.is_trained = True
        return self

    def predict(
        self,
        df: pd.DataFrame,
        return_uncertainty: bool = True,
    ) -> tuple:
        """
        Hibrit tahmin: NN + GPR residual düzeltmesi.

        Returns:
            (y_pred, y_std): Tahmin ve belirsizlik (std)
        """
        if not self.is_trained:
            raise RuntimeError("Model henüz eğitilmedi. fit() metodunu çağırın.")

        X_raw = df[FEATURE_COLS].values
        X = self.feature_scaler.transform(X_raw)

        # NN tahmini
        y_nn = self.nn_model.predict(X, verbose=0).flatten()

        # GPR residual düzeltmesi
        mu_residual, sigma_residual = self.gpr_model.predict(X, return_std=True)

        # Hibrit nihai tahmin
        y_hybrid = y_nn + mu_residual
        y_hybrid = np.clip(y_hybrid, 0, None)  # Negatif tenör olmaz

        return y_hybrid, sigma_residual

    def save(self, save_dir: str = "models"):
        """Modeli diske kaydet."""
        if not self.is_trained:
            raise RuntimeError("Kaydedilecek model yok.")

        save_path = Path(save_dir)
        save_path.mkdir(exist_ok=True)

        # NN modeli
        self.nn_model.save(save_path / "nn_model.keras")

        # GPR modeli (joblib)
        joblib.dump(self.gpr_model, save_path / "gpr_model.pkl")

        # Scaler ve metadata
        joblib.dump(self.feature_scaler, save_path / "feature_scaler.pkl")

        # Metrikleri kaydet
        import json
        with open(save_path / "training_metrics.json", "w") as f:
            json.dump({
                "region": self.region,
                "features": FEATURE_COLS,
                "target": TARGET_COL,
                "metrics": self.training_metrics,
            }, f, indent=2)

        print(f"\n  ✅ Model kaydedildi: {save_path}/")

    @classmethod
    def load(cls, save_dir: str = "models") -> "HybridGPRNN":
        """Kaydedilmiş modeli yükle."""
        save_path = Path(save_dir)
        instance = cls()
        instance.nn_model = keras.models.load_model(save_path / "nn_model.keras")
        instance.gpr_model = joblib.load(save_path / "gpr_model.pkl")
        instance.feature_scaler = joblib.load(save_path / "feature_scaler.pkl")
        instance.is_trained = True
        print(f"  ✅ Model yüklendi: {save_path}/")
        return instance


# ─────────────────────────────────────────────
#  3D Rezerv Modellemesi
# ─────────────────────────────────────────────

def run_3d_reserve_modeling(
    model: HybridGPRNN,
    region: str = "bor_rich",
    grid_size: int = 15,
) -> pd.DataFrame:
    """
    3D ızgara üzerinde rezerv tahmini yapar.
    Sonuçları görselleştirme için CSV'ye kaydeder.
    """
    print("\n  3D Rezerv Modelleme Başlatılıyor...")
    df_grid = generate_3d_grid(
        grid_size=grid_size,
        region=region,
        output_path="data/3d_grid_raw.csv"
    )

    # Jeofizik özellikleri ekle (basit proxy değerler)
    profile = REGION_PROFILES[region]
    depth_max = profile["depth_range"][1]
    grade_max = profile["grade_range"][1]

    df_grid["magnetic_nT"] = df_grid["ore_grade_pct"] * 15.0 + np.random.normal(0, 10, len(df_grid))
    df_grid["gravity_mGal"] = df_grid["ore_grade_pct"] * 0.8 + np.random.normal(0, 0.3, len(df_grid))
    df_grid["resistivity_ohm"] = np.exp(-df_grid["ore_grade_pct"] / grade_max * 3) * 300
    df_grid["chargeability_ms"] = df_grid["ore_grade_pct"] / grade_max * 35
    df_grid["seismic_vp_ms"] = 4500 - df_grid["z_depth_m"] * 0.5
    df_grid["rock_density_gcc"] = 2.65 + df_grid["ore_grade_pct"] / grade_max * 0.7
    df_grid["alteration_idx"] = df_grid["ore_grade_pct"] / grade_max * 0.8
    df_grid["depth_m"] = df_grid["z_depth_m"]

    # Tahmin yap
    y_pred, y_uncertainty = model.predict(df_grid)
    df_grid["predicted_grade_pct"] = y_pred
    df_grid["uncertainty_pct"] = y_uncertainty
    df_grid["high_potential"] = (y_pred > df_grid["ore_grade_pct"].quantile(0.75)).astype(int)

    out_path = "data/3d_reserve_model.csv"
    df_grid.to_csv(out_path, index=False)
    print(f"  ✅ 3D Rezerv Modeli kaydedildi: {out_path}")

    # Yüksek potansiyel bölgeleri raporla
    high_pot = df_grid[df_grid["high_potential"] == 1]
    print(f"\n  Yüksek Potansiyel Bölgeler: {len(high_pot):,} nokta")
    print(f"  Ortalama Tahmin Tenörü: {high_pot['predicted_grade_pct'].mean():.3f}%")

    return df_grid


# ─────────────────────────────────────────────
#  Ana Çalıştırma Bloğu
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="DeepMine AI - Hibrit GPR-NN Rezerv Tahmin Sistemi"
    )
    parser.add_argument("--region", type=str, default="bor_rich",
                        choices=list(REGION_PROFILES.keys()),
                        help="Jeolojik bölge profili")
    parser.add_argument("--samples", type=int, default=2000,
                        help="Eğitim veri seti boyutu")
    parser.add_argument("--epochs", type=int, default=150,
                        help="NN maksimum epoch sayısı")
    parser.add_argument("--load-model", action="store_true",
                        help="Kaydedilmiş modeli yükle (yeniden eğitme)")
    parser.add_argument("--predict-3d", action="store_true",
                        help="3D rezerv modellemesi yap")

    args = parser.parse_args()

    # ---- Veri üret ----
    print(f"\n{'═'*60}")
    print(f"  DeepMine AI | TEKNOFEST 2026 Maden Teknolojileri")
    print(f"  Hibrit GPR-NN Rezerv Tahmin Sistemi")
    print(f"{'═'*60}")

    if args.load_model and (MODELS_DIR / "nn_model.keras").exists():
        model = HybridGPRNN.load()
        # Test için veri gerekli
        _, df_test = generate_dataset(
            n_samples=400, region=args.region,
            output_dir=str(DATA_DIR), train_split=0.0
        )
    else:
        df_train, df_test = generate_dataset(
            n_samples=args.samples,
            region=args.region,
            output_dir=str(DATA_DIR),
        )

        # Eğitim/doğrulama bölünmesi
        val_split = int(len(df_train) * 0.85)
        df_val = df_train.iloc[val_split:].reset_index(drop=True)
        df_train_final = df_train.iloc[:val_split].reset_index(drop=True)

        # Model eğit
        model = HybridGPRNN()
        model.fit(df_train_final, df_val, region=args.region, nn_epochs=args.epochs)
        model.save()

    # ---- Test Değerlendirmesi ----
    print("\n  Test Seti Değerlendirmesi...")
    y_pred, y_std = model.predict(df_test)
    y_true = df_test[TARGET_COL].values

    test_rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    test_r2 = r2_score(y_true, y_pred)
    test_mae = mean_absolute_error(y_true, y_pred)

    print(f"\n  {'─'*50}")
    print(f"  Test Seti Sonuçları:")
    print(f"  ├─ Test RMSE     : {test_rmse:.4f}%")
    print(f"  ├─ Test MAE      : {test_mae:.4f}%")
    print(f"  ├─ Test R²       : {test_r2:.4f}")
    print(f"  └─ Ort. Belirsizlik: ±{y_std.mean():.4f}%")
    print(f"  {'─'*50}")

    # Sonuçları kaydet
    results_df = df_test.copy()
    results_df["predicted_grade"] = y_pred
    results_df["uncertainty"] = y_std
    results_df["error"] = np.abs(y_true - y_pred)
    results_df.to_csv(DATA_DIR / "test_predictions.csv", index=False)
    print(f"  ✅ Test tahminleri kaydedildi: data/test_predictions.csv")

    # ---- 3D Rezerv Modellemesi ----
    if args.predict_3d:
        run_3d_reserve_modeling(model, region=args.region)

    print(f"\n{'═'*60}")
    print(f"  DeepMine AI - Hibrit GPR-NN Analizi Tamamlandı")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    main()
