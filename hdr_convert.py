#!/usr/bin/env python3
"""
HDR PNG Converter
SDR画像をPQ HDR (16-bit) PNGに変換するツール

機能:
- SDR → HDR (PQ) 変換
- 輝度増幅オプション (--gain)
- 円周外側を明るくするオプション (--radial-boost)
- マスク画像で部分的に輝度を上げるオプション (--mask)
- ICCプロファイル埋め込み（flashbang-hdr.pngから抽出）

Usage:
    python hdr_convert.py input.png output.png
    python hdr_convert.py input.jpg output.png --gain 1.5
    python hdr_convert.py input.png output.png --radial-boost 100 --radial-gain 3.0
    python hdr_convert.py input.png output.png --mask mask.png --mask-gain 100
"""

import argparse
import struct
import zlib
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def extract_icc_profile(png_path):
    """PNGファイルからICCプロファイルを抽出"""
    with open(png_path, 'rb') as f:
        signature = f.read(8)
        if signature != b'\x89PNG\r\n\x1a\n':
            return None

        while True:
            length_data = f.read(4)
            if len(length_data) < 4:
                break
            length = struct.unpack('>I', length_data)[0]
            chunk_type = f.read(4).decode('ascii')
            data = f.read(length)
            f.read(4)  # CRC

            if chunk_type == 'iCCP':
                null_pos = data.index(b'\x00')
                profile_name = data[:null_pos].decode('latin-1')
                compressed_profile = data[null_pos + 2:]
                icc_data = zlib.decompress(compressed_profile)
                return {'name': profile_name, 'data': icc_data}

            if chunk_type == 'IEND':
                break
    return None


def srgb_to_linear(x):
    """sRGB → リニア変換 (ベクトル化)"""
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_pq(x):
    """リニア → PQ (SMPTE ST 2084) 変換"""
    # PQ定数
    m1 = 2610.0 / 16384.0
    m2 = 2523.0 / 4096.0 * 128.0
    c1 = 3424.0 / 4096.0
    c2 = 2413.0 / 4096.0 * 32.0
    c3 = 2392.0 / 4096.0 * 32.0

    x = np.clip(x, 0, 1)

    # PQ EOTF逆変換
    x_pow_m1 = np.power(x, m1)
    numerator = c1 + c2 * x_pow_m1
    denominator = 1 + c3 * x_pow_m1
    pq = np.power(numerator / denominator, m2)

    return pq


def create_radial_mask(width, height, radius, center=None, falloff=50):
    """
    円形マスクを作成（円の外側が1、内側が0）

    Args:
        width: 画像の幅
        height: 画像の高さ
        radius: 円の半径（ピクセル）
        center: 中心座標 (x, y)。Noneなら画像中央
        falloff: エッジのグラデーション幅（ピクセル）

    Returns:
        マスク配列 (0.0 - 1.0)
    """
    if center is None:
        center = (width // 2, height // 2)

    y, x = np.ogrid[:height, :width]
    dist = np.sqrt((x - center[0])**2 + (y - center[1])**2)

    # 半径から外側にfalloffピクセルでグラデーション
    if falloff > 0:
        mask = np.clip((dist - radius) / falloff, 0, 1)
    else:
        mask = (dist > radius).astype(np.float32)

    return mask.astype(np.float32)


def make_chunk(chunk_type, data):
    """PNGチャンクを作成"""
    if isinstance(chunk_type, str):
        chunk_type = chunk_type.encode('ascii')
    chunk = chunk_type + data
    crc = zlib.crc32(chunk) & 0xffffffff
    return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)


def save_16bit_png_with_icc(img_array, output_path, icc_profile=None):
    """16-bit RGB PNGをICCプロファイル付きで保存"""
    height, width = img_array.shape[:2]

    # IHDR: bit_depth=16, color_type=2 (RGB)
    ihdr_data = struct.pack('>IIBBBBB', width, height, 16, 2, 0, 0, 0)

    # iCCP（ICCプロファイル）
    iccp_chunk = b''
    if icc_profile:
        profile_name = b'PQ HDR\x00'
        compression_method = b'\x00'
        compressed_profile = zlib.compress(icc_profile, 9)
        iccp_data = profile_name + compression_method + compressed_profile
        iccp_chunk = make_chunk(b'iCCP', iccp_data)

    # IDAT（画像データ）
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)  # フィルタータイプ: None
        for x in range(width):
            r, g, b = img_array[y, x]
            raw_data.extend(struct.pack('>HHH', r, g, b))

    compressed_data = zlib.compress(bytes(raw_data), 9)

    # IDATチャンクを8KBごとに分割
    idat_chunks = b''
    chunk_size = 8192
    for i in range(0, len(compressed_data), chunk_size):
        chunk_data = compressed_data[i:i + chunk_size]
        idat_chunks += make_chunk(b'IDAT', chunk_data)

    # PNGファイル構築
    png_signature = b'\x89PNG\r\n\x1a\n'

    with open(output_path, 'wb') as f:
        f.write(png_signature)
        f.write(make_chunk(b'IHDR', ihdr_data))
        if iccp_chunk:
            f.write(iccp_chunk)
        f.write(idat_chunks)
        f.write(make_chunk(b'IEND', b''))


def load_mask_image(mask_path, target_width, target_height):
    """
    マスク画像を読み込み、0-1の範囲に正規化

    Args:
        mask_path: マスク画像パス（グレースケール）
        target_width: 目標幅
        target_height: 目標高さ

    Returns:
        マスク配列 (0.0 - 1.0)。白=1.0、黒=0.0
    """
    mask_img = Image.open(mask_path).convert('L')  # グレースケールに変換

    # サイズが異なる場合はリサイズ
    if mask_img.size != (target_width, target_height):
        mask_img = mask_img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    mask = np.array(mask_img, dtype=np.float32) / 255.0
    return mask


def convert_to_hdr(
    input_path,
    output_path,
    gain=1.0,
    nits=10000.0,
    radial_boost=None,
    radial_gain=2.0,
    falloff=50,
    mask_path=None,
    mask_gain=100.0,
    reference_hdr=None
):
    """
    SDR画像をHDR PNGに変換

    Args:
        input_path: 入力画像パス
        output_path: 出力PNGパス
        gain: 全体の輝度増幅値 (1.0 = 変更なし)
        nits: SDR白をマッピングする輝度（cd/m²）。10000で最大輝度
        radial_boost: 円の半径（ピクセル）。指定すると外側が明るくなる
        radial_gain: 円の外側の追加輝度増幅値
        falloff: 円のエッジのグラデーション幅（ピクセル）
        mask_path: マスク画像パス（グレースケール）。白い部分の輝度を上げる
        mask_gain: マスクの白い部分の輝度増幅値
        reference_hdr: ICCプロファイルを抽出するHDR画像パス
    """
    print(f"{'='*50}")
    print(f"HDR Convert")
    print(f"{'='*50}")

    # 入力画像を読み込み
    img = Image.open(input_path)
    original_mode = img.mode

    # RGBA/RGBに変換
    if img.mode == 'RGBA':
        # アルファチャンネルは無視してRGBとして処理
        img_rgb = img.convert('RGB')
    elif img.mode != 'RGB':
        img_rgb = img.convert('RGB')
    else:
        img_rgb = img

    width, height = img_rgb.size
    print(f"Input:       {input_path}")
    print(f"Size:        {width} x {height}")
    print(f"Mode:        {original_mode}")
    print(f"Gain:        {gain}")
    print(f"Nits:        {nits}")

    # NumPy配列に変換（0-1の範囲）
    img_array = np.array(img_rgb, dtype=np.float64) / 255.0

    # sRGB → リニア
    linear = srgb_to_linear(img_array)

    # 輝度増幅
    linear = linear * gain

    # 円の外側を明るくする
    if radial_boost is not None:
        print(f"Radial:      radius={radial_boost}px, outer={radial_gain}x, falloff={falloff}px")
        mask = create_radial_mask(width, height, radial_boost, falloff=falloff)
        mask_3d = mask[:, :, np.newaxis]
        # 中心部は1.0倍、外側はradial_gain倍
        # mask=0（中心）→ 1.0倍、mask=1（外側）→ radial_gain倍
        linear = linear * (1.0 + mask_3d * (radial_gain - 1.0))

    # マスク画像で白い部分を明るくする
    if mask_path is not None:
        print(f"Mask:        {mask_path}, gain={mask_gain}x")
        mask = load_mask_image(mask_path, width, height)
        mask_3d = mask[:, :, np.newaxis]
        # mask=0（黒）→ 1.0倍、mask=1（白）→ mask_gain倍
        linear = linear * (1.0 + mask_3d * (mask_gain - 1.0))

    # 正規化（nitsを10000nitsに対する比率として適用）
    # nits=10000 でSDRの白が10000nits（PQ最大値）にマッピングされる
    linear = linear * (nits / 10000.0)

    # クリップ（1.0を超えると10000nits以上になる）
    linear = np.clip(linear, 0, 1)

    # リニア → PQ
    pq = linear_to_pq(linear)

    # 16-bit整数に変換
    img_16bit = (pq * 65535).astype(np.uint16)

    # ICCプロファイルを取得
    icc_profile = None
    if reference_hdr and Path(reference_hdr).exists():
        icc_data = extract_icc_profile(reference_hdr)
        if icc_data:
            icc_profile = icc_data['data']
            print(f"ICC Profile: {icc_data['name']}")

    # PNG保存
    save_16bit_png_with_icc(img_16bit, output_path, icc_profile)

    print(f"Output:      {output_path}")
    print(f"{'='*50}")
    print("Done!")


def main():
    parser = argparse.ArgumentParser(
        description='SDR画像をPQ HDR (16-bit) PNGに変換',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  # 基本的な変換（SDR白=10000nits、flashbang-hdr.pngと同等）
  python hdr_convert.py input.jpg output.png

  # 輝度を1.5倍に増幅
  python hdr_convert.py input.jpg output.png --gain 1.5

  # SDR白を1000nitsにマッピング（控えめなHDR）
  python hdr_convert.py input.jpg output.png --nits 1000

  # 半径100pxの円の外側を明るくする
  python hdr_convert.py input.jpg output.png --radial-boost 100

  # 円の外側を3倍の輝度で、グラデーション幅30pxで明るくする
  python hdr_convert.py input.jpg output.png -r 100 -rg 3.0 -f 30

  # マスク画像の白い部分を100倍の輝度で明るくする
  python hdr_convert.py input.jpg output.png --nits 100 --mask mask.png --mask-gain 100

  # 全オプション組み合わせ
  python hdr_convert.py input.jpg output.png -g 1.2 -r 80 -rg 4.0 -f 20
'''
    )

    parser.add_argument('input', help='入力画像ファイル (PNG, JPG, etc.)')
    parser.add_argument('output', help='出力HDR PNGファイル')
    parser.add_argument(
        '--gain', '-g',
        type=float,
        default=1.0,
        help='全体の輝度増幅値 (デフォルト: 1.0)'
    )
    parser.add_argument(
        '--nits', '-n',
        type=float,
        default=10000.0,
        help='SDR白をマッピングする輝度 cd/m² (デフォルト: 10000)'
    )
    parser.add_argument(
        '--radial-boost', '-r',
        type=int,
        default=None,
        metavar='RADIUS',
        help='円の半径（ピクセル）。指定すると円の外側が明るくなる'
    )
    parser.add_argument(
        '--radial-gain', '-rg',
        type=float,
        default=2.0,
        help='円の外側の輝度増幅値 (デフォルト: 2.0)'
    )
    parser.add_argument(
        '--falloff', '-f',
        type=int,
        default=50,
        help='円のエッジのグラデーション幅（ピクセル）(デフォルト: 50)'
    )
    parser.add_argument(
        '--mask', '-m',
        type=str,
        default=None,
        metavar='FILE',
        help='マスク画像（グレースケール）。白い部分の輝度を上げる'
    )
    parser.add_argument(
        '--mask-gain', '-mg',
        type=float,
        default=100.0,
        help='マスクの白い部分の輝度増幅値 (デフォルト: 100)'
    )
    parser.add_argument(
        '--reference', '-ref',
        type=str,
        default=None,
        help='ICCプロファイルを抽出するHDR画像パス'
    )

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    # デフォルトでflashbang-hdr.pngを参照として使用
    reference = args.reference
    if reference is None:
        script_dir = Path(__file__).parent
        default_ref = script_dir / 'flashbang-hdr.png'
        if default_ref.exists():
            reference = str(default_ref)

    convert_to_hdr(
        args.input,
        args.output,
        gain=args.gain,
        nits=args.nits,
        radial_boost=args.radial_boost,
        radial_gain=args.radial_gain,
        falloff=args.falloff,
        mask_path=args.mask,
        mask_gain=args.mask_gain,
        reference_hdr=reference
    )


if __name__ == '__main__':
    main()
