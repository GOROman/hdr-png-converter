#!/usr/bin/env python3
"""
PNG HDR Format Analyzer
PNGファイルのHDR関連メタデータを解析して表示するツール
"""

import struct
import zlib
import sys
from pathlib import Path


def read_png_chunks(filepath):
    """PNGファイルからチャンクを読み取る"""
    chunks = []
    with open(filepath, 'rb') as f:
        # PNGシグネチャ確認
        signature = f.read(8)
        if signature != b'\x89PNG\r\n\x1a\n':
            raise ValueError("Not a valid PNG file")

        while True:
            # チャンク長（4バイト）
            length_data = f.read(4)
            if len(length_data) < 4:
                break
            length = struct.unpack('>I', length_data)[0]

            # チャンクタイプ（4バイト）
            chunk_type = f.read(4).decode('ascii')

            # チャンクデータ
            data = f.read(length)

            # CRC（4バイト）
            crc = f.read(4)

            chunks.append({
                'type': chunk_type,
                'length': length,
                'data': data,
                'crc': struct.unpack('>I', crc)[0]
            })

            if chunk_type == 'IEND':
                break

    return chunks


def parse_ihdr(data):
    """IHDRチャンクを解析"""
    width, height = struct.unpack('>II', data[:8])
    bit_depth = data[8]
    color_type = data[9]
    compression = data[10]
    filter_method = data[11]
    interlace = data[12]

    color_type_names = {
        0: 'Grayscale',
        2: 'RGB (Truecolor)',
        3: 'Indexed-color (Palette)',
        4: 'Grayscale with Alpha',
        6: 'RGBA (Truecolor with Alpha)'
    }

    return {
        'width': width,
        'height': height,
        'bit_depth': bit_depth,
        'color_type': color_type,
        'color_type_name': color_type_names.get(color_type, 'Unknown'),
        'compression': compression,
        'filter_method': filter_method,
        'interlace': interlace
    }


def parse_gama(data):
    """gAMAチャンクを解析"""
    gamma_int = struct.unpack('>I', data)[0]
    gamma = gamma_int / 100000.0
    return {'gamma': gamma, 'raw_value': gamma_int}


def parse_chrm(data):
    """cHRMチャンクを解析（色度情報）"""
    values = struct.unpack('>IIIIIIII', data)
    return {
        'white_point_x': values[0] / 100000.0,
        'white_point_y': values[1] / 100000.0,
        'red_x': values[2] / 100000.0,
        'red_y': values[3] / 100000.0,
        'green_x': values[4] / 100000.0,
        'green_y': values[5] / 100000.0,
        'blue_x': values[6] / 100000.0,
        'blue_y': values[7] / 100000.0
    }


def parse_srgb(data):
    """sRGBチャンクを解析"""
    rendering_intent = data[0]
    intent_names = {
        0: 'Perceptual',
        1: 'Relative colorimetric',
        2: 'Saturation',
        3: 'Absolute colorimetric'
    }
    return {
        'rendering_intent': rendering_intent,
        'intent_name': intent_names.get(rendering_intent, 'Unknown')
    }


def parse_cicp(data):
    """cICPチャンクを解析（HDR用カラー情報）"""
    color_primaries = data[0]
    transfer_characteristics = data[1]
    matrix_coefficients = data[2]
    video_full_range = data[3]

    # ITU-T H.273 / ISO/IEC 23091-2 による定義
    primaries_names = {
        1: 'BT.709 (sRGB)',
        4: 'BT.470M',
        5: 'BT.601 (625)',
        6: 'BT.601 (525)',
        7: 'SMPTE 240M',
        8: 'Generic film',
        9: 'BT.2020 / BT.2100',
        10: 'SMPTE ST 428-1 (XYZ)',
        11: 'SMPTE RP 431-2 (DCI-P3)',
        12: 'SMPTE EG 432-1 (Display P3)',
        22: 'EBU Tech 3213-E'
    }

    transfer_names = {
        1: 'BT.709 / BT.1361',
        4: 'BT.470M (Gamma 2.2)',
        5: 'BT.470BG (Gamma 2.8)',
        6: 'BT.601 / SMPTE 170M',
        7: 'SMPTE 240M',
        8: 'Linear',
        9: 'Logarithmic (100:1)',
        10: 'Logarithmic (100*sqrt(10):1)',
        11: 'IEC 61966-2-4',
        12: 'BT.1361 Extended',
        13: 'sRGB / sYCC',
        14: 'BT.2020 (10-bit)',
        15: 'BT.2020 (12-bit)',
        16: 'SMPTE ST 2084 (PQ / HDR10)',
        17: 'SMPTE ST 428-1',
        18: 'ARIB STD-B67 (HLG)'
    }

    matrix_names = {
        0: 'Identity (RGB)',
        1: 'BT.709',
        4: 'FCC',
        5: 'BT.470BG',
        6: 'BT.601',
        7: 'SMPTE 240M',
        8: 'YCgCo',
        9: 'BT.2020 non-constant luminance',
        10: 'BT.2020 constant luminance',
        11: 'SMPTE ST 2085',
        12: 'Chromaticity-derived non-constant luminance',
        13: 'Chromaticity-derived constant luminance',
        14: 'ICtCp'
    }

    return {
        'color_primaries': color_primaries,
        'color_primaries_name': primaries_names.get(color_primaries, f'Unknown ({color_primaries})'),
        'transfer_characteristics': transfer_characteristics,
        'transfer_name': transfer_names.get(transfer_characteristics, f'Unknown ({transfer_characteristics})'),
        'matrix_coefficients': matrix_coefficients,
        'matrix_name': matrix_names.get(matrix_coefficients, f'Unknown ({matrix_coefficients})'),
        'video_full_range': video_full_range,
        'full_range_name': 'Full range (0-255)' if video_full_range else 'Limited range (16-235)'
    }


def parse_iccp(data):
    """iCCPチャンクを解析（ICCプロファイル）"""
    # プロファイル名（null終端）
    null_pos = data.index(b'\x00')
    profile_name = data[:null_pos].decode('latin-1')
    compression_method = data[null_pos + 1]
    compressed_profile = data[null_pos + 2:]

    # zlibで解凍
    try:
        profile_data = zlib.decompress(compressed_profile)
        profile_size = len(profile_data)

        # ICCプロファイルヘッダーの解析
        icc_info = {}
        if len(profile_data) >= 128:
            icc_info['profile_size'] = struct.unpack('>I', profile_data[0:4])[0]
            icc_info['preferred_cmm'] = profile_data[4:8].decode('ascii', errors='ignore').strip('\x00')

            version_major = profile_data[8]
            version_minor = (profile_data[9] >> 4) & 0x0F
            version_bugfix = profile_data[9] & 0x0F
            icc_info['version'] = f'{version_major}.{version_minor}.{version_bugfix}'

            icc_info['device_class'] = profile_data[12:16].decode('ascii', errors='ignore').strip()
            icc_info['color_space'] = profile_data[16:20].decode('ascii', errors='ignore').strip()
            icc_info['pcs'] = profile_data[20:24].decode('ascii', errors='ignore').strip()

            # 作成日時
            year = struct.unpack('>H', profile_data[24:26])[0]
            month = struct.unpack('>H', profile_data[26:28])[0]
            day = struct.unpack('>H', profile_data[28:30])[0]
            hour = struct.unpack('>H', profile_data[30:32])[0]
            minute = struct.unpack('>H', profile_data[32:34])[0]
            second = struct.unpack('>H', profile_data[34:36])[0]
            icc_info['creation_date'] = f'{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}'

            # プロファイルシグネチャ
            icc_info['signature'] = profile_data[36:40].decode('ascii', errors='ignore')

            # プライマリプラットフォーム
            platform = profile_data[40:44].decode('ascii', errors='ignore').strip('\x00')
            platform_names = {
                'APPL': 'Apple',
                'MSFT': 'Microsoft',
                'SGI ': 'Silicon Graphics',
                'SUNW': 'Sun Microsystems',
                '': 'Unspecified'
            }
            icc_info['platform'] = platform_names.get(platform, platform)

            # レンダリングインテント
            rendering_intent = struct.unpack('>I', profile_data[64:68])[0]
            intent_names = {
                0: 'Perceptual',
                1: 'Relative colorimetric',
                2: 'Saturation',
                3: 'Absolute colorimetric'
            }
            icc_info['rendering_intent'] = intent_names.get(rendering_intent, f'Unknown ({rendering_intent})')

        return {
            'profile_name': profile_name,
            'compression_method': compression_method,
            'compressed_size': len(compressed_profile),
            'decompressed_size': profile_size,
            'icc_info': icc_info
        }
    except Exception as e:
        return {
            'profile_name': profile_name,
            'compression_method': compression_method,
            'error': str(e)
        }


def parse_mdcv(data):
    """mDCvチャンクを解析（HDRマスタリングディスプレイカラーボリューム）"""
    # SMPTE ST 2086
    values = struct.unpack('>HHHHHHHHII', data)
    return {
        'display_primaries_red_x': values[0] / 50000.0,
        'display_primaries_red_y': values[1] / 50000.0,
        'display_primaries_green_x': values[2] / 50000.0,
        'display_primaries_green_y': values[3] / 50000.0,
        'display_primaries_blue_x': values[4] / 50000.0,
        'display_primaries_blue_y': values[5] / 50000.0,
        'white_point_x': values[6] / 50000.0,
        'white_point_y': values[7] / 50000.0,
        'max_luminance': values[8] / 10000.0,  # cd/m²
        'min_luminance': values[9] / 10000.0   # cd/m²
    }


def parse_clli(data):
    """cLLiチャンクを解析（HDRコンテンツライトレベル情報）"""
    max_cll, max_fall = struct.unpack('>II', data)
    return {
        'max_content_light_level': max_cll,  # cd/m²
        'max_frame_average_light_level': max_fall  # cd/m²
    }


def analyze_png_hdr(filepath):
    """PNGファイルのHDR情報を解析"""
    print(f"\n{'='*60}")
    print(f"PNG HDR Format Analyzer")
    print(f"{'='*60}")
    print(f"File: {filepath}")
    print(f"{'='*60}\n")

    chunks = read_png_chunks(filepath)

    # チャンク一覧
    print("## Chunks Found:")
    print("-" * 40)
    for chunk in chunks:
        critical = "Critical" if chunk['type'][0].isupper() else "Ancillary"
        print(f"  {chunk['type']:6s} - {chunk['length']:8d} bytes ({critical})")
    print()

    # HDR関連情報
    hdr_info = {
        'has_hdr': False,
        'hdr_type': None
    }

    for chunk in chunks:
        chunk_type = chunk['type']
        data = chunk['data']

        if chunk_type == 'IHDR':
            print("## Image Header (IHDR):")
            print("-" * 40)
            ihdr = parse_ihdr(data)
            print(f"  Dimensions:    {ihdr['width']} x {ihdr['height']}")
            print(f"  Bit Depth:     {ihdr['bit_depth']}")
            print(f"  Color Type:    {ihdr['color_type']} ({ihdr['color_type_name']})")
            print(f"  Compression:   {ihdr['compression']}")
            print(f"  Filter:        {ihdr['filter_method']}")
            print(f"  Interlace:     {ihdr['interlace']}")

            # 16bitの場合、HDRの可能性あり
            if ihdr['bit_depth'] == 16:
                hdr_info['has_hdr'] = True
                hdr_info['high_bit_depth'] = True
            print()

        elif chunk_type == 'gAMA':
            print("## Gamma (gAMA):")
            print("-" * 40)
            gama = parse_gama(data)
            print(f"  Gamma Value:   {gama['gamma']:.5f}")
            print(f"  Raw Value:     {gama['raw_value']}")
            print()

        elif chunk_type == 'cHRM':
            print("## Chromaticity (cHRM):")
            print("-" * 40)
            chrm = parse_chrm(data)
            print(f"  White Point:   ({chrm['white_point_x']:.5f}, {chrm['white_point_y']:.5f})")
            print(f"  Red Primary:   ({chrm['red_x']:.5f}, {chrm['red_y']:.5f})")
            print(f"  Green Primary: ({chrm['green_x']:.5f}, {chrm['green_y']:.5f})")
            print(f"  Blue Primary:  ({chrm['blue_x']:.5f}, {chrm['blue_y']:.5f})")
            print()

        elif chunk_type == 'sRGB':
            print("## sRGB Rendering Intent:")
            print("-" * 40)
            srgb = parse_srgb(data)
            print(f"  Intent:        {srgb['rendering_intent']} ({srgb['intent_name']})")
            print()

        elif chunk_type == 'cICP':
            print("## Coding-Independent Code Points (cICP) [HDR]:")
            print("-" * 40)
            cicp = parse_cicp(data)
            print(f"  Color Primaries:          {cicp['color_primaries']} ({cicp['color_primaries_name']})")
            print(f"  Transfer Characteristics: {cicp['transfer_characteristics']} ({cicp['transfer_name']})")
            print(f"  Matrix Coefficients:      {cicp['matrix_coefficients']} ({cicp['matrix_name']})")
            print(f"  Video Full Range:         {cicp['video_full_range']} ({cicp['full_range_name']})")

            hdr_info['has_hdr'] = True
            hdr_info['cicp'] = cicp

            # HDRタイプの判定
            if cicp['transfer_characteristics'] == 16:
                hdr_info['hdr_type'] = 'HDR10 (PQ)'
            elif cicp['transfer_characteristics'] == 18:
                hdr_info['hdr_type'] = 'HLG'
            print()

        elif chunk_type == 'iCCP':
            print("## ICC Profile (iCCP):")
            print("-" * 40)
            iccp = parse_iccp(data)
            print(f"  Profile Name:     {iccp['profile_name']}")
            print(f"  Compression:      {iccp['compression_method']}")
            print(f"  Compressed Size:  {iccp.get('compressed_size', 'N/A')} bytes")
            print(f"  Decompressed:     {iccp.get('decompressed_size', 'N/A')} bytes")

            if 'icc_info' in iccp:
                icc = iccp['icc_info']
                print(f"  ICC Version:      {icc.get('version', 'N/A')}")
                print(f"  Device Class:     {icc.get('device_class', 'N/A')}")
                print(f"  Color Space:      {icc.get('color_space', 'N/A')}")
                print(f"  PCS:              {icc.get('pcs', 'N/A')}")
                print(f"  Creation Date:    {icc.get('creation_date', 'N/A')}")
                print(f"  Platform:         {icc.get('platform', 'N/A')}")
                print(f"  Rendering Intent: {icc.get('rendering_intent', 'N/A')}")
            print()

        elif chunk_type == 'mDCv':
            print("## Mastering Display Color Volume (mDCv) [HDR]:")
            print("-" * 40)
            mdcv = parse_mdcv(data)
            print(f"  Red Primary:      ({mdcv['display_primaries_red_x']:.4f}, {mdcv['display_primaries_red_y']:.4f})")
            print(f"  Green Primary:    ({mdcv['display_primaries_green_x']:.4f}, {mdcv['display_primaries_green_y']:.4f})")
            print(f"  Blue Primary:     ({mdcv['display_primaries_blue_x']:.4f}, {mdcv['display_primaries_blue_y']:.4f})")
            print(f"  White Point:      ({mdcv['white_point_x']:.4f}, {mdcv['white_point_y']:.4f})")
            print(f"  Max Luminance:    {mdcv['max_luminance']:.2f} cd/m²")
            print(f"  Min Luminance:    {mdcv['min_luminance']:.6f} cd/m²")

            hdr_info['has_hdr'] = True
            hdr_info['mdcv'] = mdcv
            print()

        elif chunk_type == 'cLLi':
            print("## Content Light Level Info (cLLi) [HDR]:")
            print("-" * 40)
            clli = parse_clli(data)
            print(f"  MaxCLL:           {clli['max_content_light_level']} cd/m²")
            print(f"  MaxFALL:          {clli['max_frame_average_light_level']} cd/m²")

            hdr_info['has_hdr'] = True
            hdr_info['clli'] = clli
            print()

    # HDRサマリー
    print("## HDR Summary:")
    print("-" * 40)
    if hdr_info['has_hdr']:
        print(f"  HDR Content:      YES")
        if hdr_info.get('hdr_type'):
            print(f"  HDR Type:         {hdr_info['hdr_type']}")
        if hdr_info.get('high_bit_depth'):
            print(f"  High Bit Depth:   16-bit")
        if 'cicp' in hdr_info:
            cicp = hdr_info['cicp']
            if cicp['color_primaries'] == 9:
                print(f"  Color Gamut:      BT.2020 (Wide Color Gamut)")
            elif cicp['color_primaries'] == 12:
                print(f"  Color Gamut:      Display P3")
    else:
        print(f"  HDR Content:      NO (Standard SDR)")
    print()

    return hdr_info


def main():
    if len(sys.argv) < 2:
        print("Usage: python png_hdr_analyzer.py <png_file>")
        print("Example: python png_hdr_analyzer.py image.png")
        sys.exit(1)

    filepath = sys.argv[1]
    if not Path(filepath).exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    try:
        analyze_png_hdr(filepath)
    except Exception as e:
        print(f"Error analyzing file: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
