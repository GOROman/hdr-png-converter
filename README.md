# HDR PNG Converter

SDR画像をPQ HDR (16-bit) PNGに変換するPythonツール

## 機能

- **SDR → HDR (PQ) 変換**: sRGBからPQ (SMPTE ST 2084) への変換
- **輝度増幅**: 全体の輝度を調整
- **円形ブースト**: 円の外側の輝度を上げる（アイコン用途など）
- **マスク画像対応**: グレースケールマスクで部分的に輝度を上げる
- **ノイズリダクション**: アニメ絵向けバイラテラルフィルタ
- **ICCプロファイル埋め込み**: PQ HDR ICCプロファイルを自動埋め込み

## 必要環境

```bash
pip install numpy pillow
pip install opencv-python  # ノイズリダクション用（オプション）
```

## 使い方

### 基本的な変換

```bash
# SDR白を10000nitsにマッピング（最大輝度）
python hdr_convert.py input.jpg output.png

# SDR白を100nitsにマッピング（控えめなHDR）
python hdr_convert.py input.jpg output.png --nits 100
```

### 輝度増幅

```bash
# 全体の輝度を1.5倍に
python hdr_convert.py input.jpg output.png --gain 1.5
```

### 円形ブースト（アイコン用途）

円の内側は通常輝度、外側をHDRで明るくする：

```bash
# 半径140pxの円の外側を100倍（10000nits）に
python hdr_convert.py input.jpg output.png --nits 100 -r 140 -rg 100 -f 30
```

| オプション | 説明 |
|-----------|------|
| `-r`, `--radial-boost` | 円の半径（ピクセル） |
| `-rg`, `--radial-gain` | 外側の輝度倍率 |
| `-f`, `--falloff` | 境界のグラデーション幅（ピクセル） |

### マスク画像で部分的に明るくする

グレースケールのマスク画像を使用し、白い部分の輝度を上げる：

```bash
python hdr_convert.py input.jpg output.png --nits 100 --mask mask.png --mask-gain 100
```

- **黒 (0)**: 輝度変更なし
- **白 (255)**: mask-gain倍の輝度
- **グレー**: 中間値（グラデーション対応）

### ノイズリダクション（アニメ絵向け）

```bash
# デフォルト強度（7）でノイズ除去
python hdr_convert.py input.jpg output.png --denoise

# 強度を調整（1-10）
python hdr_convert.py input.jpg output.png --denoise --denoise-strength 5
```

バイラテラルフィルタを使用し、エッジを保持しながら平坦な領域のノイズを除去します。

### 組み合わせ例

```bash
# ノイズ除去 + マスク + 円形ブースト
python hdr_convert.py input.jpg output.png \
  --nits 100 \
  --denoise \
  --mask eyemask.png --mask-gain 1000 \
  -r 130 -rg 10 -f 30
```

## オプション一覧

| オプション | 短縮 | デフォルト | 説明 |
|-----------|------|-----------|------|
| `--gain` | `-g` | 1.0 | 全体の輝度増幅値 |
| `--nits` | `-n` | 10000 | SDR白をマッピングする輝度 (cd/m²) |
| `--radial-boost` | `-r` | なし | 円の半径（ピクセル） |
| `--radial-gain` | `-rg` | 2.0 | 円の外側の輝度倍率 |
| `--falloff` | `-f` | 50 | 境界のグラデーション幅（ピクセル） |
| `--mask` | `-m` | なし | マスク画像（グレースケール） |
| `--mask-gain` | `-mg` | 100 | マスクの白い部分の輝度倍率 |
| `--denoise` | `-d` | なし | ノイズリダクションを有効化 |
| `--denoise-strength` | `-ds` | 7 | ノイズリダクション強度 (1-10) |
| `--reference` | `-ref` | flashbang-hdr.png | ICCプロファイル参照元 |

## 出力仕様

- **フォーマット**: PNG
- **ビット深度**: 16-bit RGB (48bit/pixel)
- **転送特性**: PQ (SMPTE ST 2084)
- **ICCプロファイル**: PQ HDR（iCCPチャンク埋め込み）

## 解析ツール

`png_hdr_analyzer.py` でHDR PNGのメタデータを解析できます：

```bash
python png_hdr_analyzer.py output.png
```

## ライセンス

MIT License
