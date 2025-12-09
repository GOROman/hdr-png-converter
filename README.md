# HDR PNG Converter

[日本語版 README](README_ja.md)

A Python tool to convert SDR images to PQ HDR (16-bit) PNG format.

## Features

- **SDR → HDR (PQ) Conversion**: Convert from sRGB to PQ (SMPTE ST 2084)
- **Brightness Amplification**: Adjust overall luminance
- **Radial Boost**: Increase luminance outside a circular area (for icons, etc.)
- **Mask Image Support**: Selectively increase luminance using grayscale masks
- **Noise Reduction**: Bilateral filter optimized for anime-style images
- **ICC Profile Embedding**: Automatic PQ HDR ICC profile embedding

## Requirements

```bash
pip install numpy pillow
pip install opencv-python  # Optional, for noise reduction
```

## Usage

### Basic Conversion

```bash
# Map SDR white to 10000 nits (maximum luminance)
python hdr_convert.py input.jpg output.png

# Map SDR white to 100 nits (moderate HDR)
python hdr_convert.py input.jpg output.png --nits 100
```

### Brightness Amplification

```bash
# Increase overall brightness by 1.5x
python hdr_convert.py input.jpg output.png --gain 1.5
```

### Radial Boost (for Icons)

Keep the center at normal luminance while making the outside HDR-bright:

```bash
# Make outside of 140px radius circle 100x brighter (10000 nits)
python hdr_convert.py input.jpg output.png --nits 100 -r 140 -rg 100 -f 30
```

| Option | Description |
|--------|-------------|
| `-r`, `--radial-boost` | Circle radius (pixels) |
| `-rg`, `--radial-gain` | Outside luminance multiplier |
| `-f`, `--falloff` | Edge gradient width (pixels) |

### Selective Brightness with Mask Images

Use a grayscale mask image to increase luminance in white areas:

```bash
python hdr_convert.py input.jpg output.png --nits 100 --mask mask.png --mask-gain 100
```

- **Black (0)**: No luminance change
- **White (255)**: mask-gain multiplier applied
- **Gray**: Intermediate values (gradient support)

### Noise Reduction (for Anime Images)

```bash
# Apply noise reduction with default strength (7)
python hdr_convert.py input.jpg output.png --denoise

# Adjust strength (1-10)
python hdr_convert.py input.jpg output.png --denoise --denoise-strength 5
```

Uses bilateral filter to remove noise in flat areas while preserving edges.

### Combined Example

```bash
# Noise reduction + Mask + Radial boost
python hdr_convert.py input.jpg output.png \
  --nits 100 \
  --denoise \
  --mask eyemask.png --mask-gain 1000 \
  -r 130 -rg 10 -f 30
```

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--gain` | `-g` | 1.0 | Overall brightness multiplier |
| `--nits` | `-n` | 10000 | Luminance to map SDR white to (cd/m²) |
| `--radial-boost` | `-r` | None | Circle radius (pixels) |
| `--radial-gain` | `-rg` | 2.0 | Outside luminance multiplier |
| `--falloff` | `-f` | 50 | Edge gradient width (pixels) |
| `--mask` | `-m` | None | Mask image (grayscale) |
| `--mask-gain` | `-mg` | 100 | White area luminance multiplier |
| `--denoise` | `-d` | None | Enable noise reduction |
| `--denoise-strength` | `-ds` | 7 | Noise reduction strength (1-10) |
| `--reference` | `-ref` | flashbang-hdr.png | ICC profile source |

## Output Specifications

- **Format**: PNG
- **Bit Depth**: 16-bit RGB (48 bits/pixel)
- **Transfer Function**: PQ (SMPTE ST 2084)
- **ICC Profile**: PQ HDR (embedded in iCCP chunk)

## Analysis Tool

Use `png_hdr_analyzer.py` to analyze HDR PNG metadata:

```bash
python png_hdr_analyzer.py output.png
```

## License

MIT License
