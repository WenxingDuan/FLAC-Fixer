#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flac_autofix.py — 递归扫描并修复异常 FLAC（Windows 跨盘安全版）

更新要点：
- **Windows 跨盘安全**：所有临时文件在目标文件**同一目录**创建，避免 WinError 17。
- **atomic_replace 更健壮**：若目标被占用会尝试 .old 回退路径。
- 无损重封装（ffmpeg 优先），可选 flac 官方工具，支持保留封面（需 metaflac，且可限大小）。
- 并发/CSV/备份/干跑。

依赖：pip install soundfile；工具建议安装 ffmpeg（强烈推荐），可选 flac/metaflac。
"""
from __future__ import annotations
import argparse
import csv
import os
import sys
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

# ---------------------------- 基础工具 ----------------------------

def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)

def human_bytes(n: int) -> str:
    v = float(n)
    for unit in ['B','KB','MB','GB']:
        if v < 1024 or unit == 'GB':
            return f"{v:.1f}{unit}" if unit != 'B' else f"{int(v)}B"
        v /= 1024
    return f"{v}B"

# ---------------------------- FLAC 解析 ----------------------------

@dataclass
class MetaBlock:
    type: int
    length: int
    offset: int
    is_last: bool

TYPE_NAMES = {0:'STREAMINFO',1:'PADDING',2:'APPLICATION',3:'SEEKTABLE',4:'VORBIS_COMMENT',5:'CUESHEET',6:'PICTURE'}

@dataclass
class StreamInfo:
    sample_rate: int
    channels: int
    bits_per_sample: int
    total_samples: int

@dataclass
class FlacProbe:
    ok: bool
    reason: str
    is_flac: bool
    blocks: List[MetaBlock]
    streaminfo: Optional[StreamInfo]
    total_meta_bytes_with_headers: int
    picture_bytes_total: int
    unknown_block_count: int
    last_block_marked: bool

def parse_flac(path: Path) -> FlacProbe:
    blocks: List[MetaBlock] = []
    is_flac = False
    streaminfo: Optional[StreamInfo] = None
    total_meta = 0
    picture_bytes = 0
    unknown_cnt = 0
    last_marked = False

    with path.open('rb') as f:
        head = f.read(4)
        if head != b'fLaC':
            return FlacProbe(False,'Not native FLAC (missing fLaC magic)',False,[],None,0,0,0,False)
        is_flac = True
        while True:
            hdr = f.read(4)
            if len(hdr) < 4:
                break
            b0,b1,b2,b3 = hdr
            is_last = (b0 & 0x80) != 0
            btype = (b0 & 0x7F)
            length = (b1<<16)|(b2<<8)|b3
            offset = f.tell() - 4
            blocks.append(MetaBlock(btype,length,offset,is_last))
            total_meta += length + 4
            if btype == 6:
                picture_bytes += length
            if btype not in TYPE_NAMES:
                unknown_cnt += 1
            if btype == 0 and length == 34:
                data = f.read(34)
                a = data[10:18]
                x = int.from_bytes(a, 'big')
                sr = (x >> (3+5+36)) & ((1<<20)-1)
                ch = ((x >> (5+36)) & 0b111) + 1
                bps = ((x >> 36) & 0b11111) + 1
                total = x & ((1<<36)-1)
                streaminfo = StreamInfo(sr,ch,bps,total)
            else:
                f.seek(length,1)
            if is_last:
                last_marked = True
                break
    return FlacProbe(True,'OK',is_flac,blocks,streaminfo,total_meta,picture_bytes,unknown_cnt,last_marked)

# ---------------------------- 解码验证 ----------------------------

def soundfile_decode_ok(path: Path, chunk_frames: int = 65536) -> Tuple[bool,str]:
    try:
        import soundfile as sf
    except Exception as e:
        return False, f"soundfile import failed: {e}"
    try:
        with sf.SoundFile(str(path), 'r') as f:
            while True:
                data = f.read(frames=chunk_frames, dtype='int16', always_2d=False)
                if len(data) == 0:
                    break
        return True, 'OK (soundfile)'
    except Exception as e:
        return False, f"DECODE_FAIL (soundfile): {e.__class__.__name__}: {e}"

# ---------------------------- 判定与修复策略 ----------------------------

@dataclass
class FixPlan:
    needs_fix: bool
    reasons: List[str]
    action: str  # 'ffmpeg' | 'flac' | 'metaflac' | 'skip'
    keep_cover: bool

def decide_fix(probe: FlacProbe, decode_ok: bool, keep_cover: bool, meta_threshold_mb: float, max_cover_bytes: int) -> FixPlan:
    reasons: List[str] = []
    if not decode_ok:
        reasons.append('解码失败/播放器拒绝播放')
    if probe.unknown_block_count > 0:
        reasons.append(f'存在 UNKNOWN 元数据块: {probe.unknown_block_count} 个')
    if not probe.last_block_marked:
        reasons.append('元数据未标记终止 is_last=false')
    if probe.total_meta_bytes_with_headers > int(meta_threshold_mb*1024*1024):
        reasons.append(f'元数据过大: {human_bytes(probe.total_meta_bytes_with_headers)}')
    if probe.picture_bytes_total > max_cover_bytes:
        reasons.append(f'封面过大: {human_bytes(probe.picture_bytes_total)} > {human_bytes(max_cover_bytes)}')

    needs_fix = len(reasons) > 0
    action = 'skip'
    if needs_fix:
        if which('ffmpeg'):
            action = 'ffmpeg'
        elif which('flac'):
            action = 'flac'
        else:
            action = 'metaflac' if which('metaflac') else 'skip'

    if needs_fix and '封面过大' in ' '.join(reasons) and which('metaflac') and not which('ffmpeg') and not which('flac'):
        action = 'metaflac'

    if keep_cover and probe.picture_bytes_total > max_cover_bytes:
        keep_cover = False

    return FixPlan(needs_fix, reasons, action, keep_cover)

# ---------------------------- 外部命令封装 ----------------------------

def run(cmd: List[str]) -> Tuple[int,str,str]:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr

def export_cover_with_metaflac(src: Path, tmpdir: Path) -> Optional[Path]:
    if not which('metaflac'):
        return None
    out = tmpdir / 'cover.export'
    code, _, _ = run(['metaflac', f'--export-picture-to={out}', str(src)])
    if code == 0 and out.exists():
        return out
    return None

def import_cover_with_metaflac(dst: Path, cover_path: Path) -> bool:
    if not which('metaflac'):
        return False
    code, _, _ = run(['metaflac', f'--import-picture-from={cover_path}', str(dst)])
    return code == 0

def strip_all_metadata_with_metaflac(path: Path) -> bool:
    if not which('metaflac'):
        return False
    code, _, _ = run(['metaflac', '--remove-all', '--dont-use-padding', str(path)])
    return code == 0

# ---------------------------- 重封装实现 ----------------------------

def reencode_with_ffmpeg(src: Path, dst: Path) -> bool:
    cmd = ['ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(src),'-map_metadata','0','-vn','-sn','-c:a','flac','-compression_level','5',str(dst)]
    code, _, _ = run(cmd)
    return code == 0

def reencode_with_flac_cli(src: Path, dst: Path) -> bool:
    # 在与目标同一目录创建临时文件，避免跨盘移动
    with tempfile.TemporaryDirectory(dir=src.parent) as td:
        wav = Path(td) / 'tmp.wav'
        code, _, _ = run(['flac','-d','-f','-o',str(wav),str(src)])
        if code != 0 or not wav.exists():
            return False
        code, _, _ = run(['flac','-f','-o',str(dst),str(wav)])
        return code == 0 and dst.exists()

# ---------------------------- 文件替换 ----------------------------

def atomic_replace(src: Path, dst: Path):
    """在同一分区原子替换；若被占用，尝试 .old 回退。"""
    try:
        if dst.exists():
            dst.unlink()
        src.replace(dst)
    except PermissionError:
        bak = dst.with_suffix(dst.suffix + '.old')
        try:
            if dst.exists():
                dst.rename(bak)
            shutil.move(str(src), str(dst))
            if bak.exists():
                try:
                    bak.unlink()
                except Exception:
                    pass
        except Exception as e:
            if not dst.exists() and bak.exists():
                try:
                    bak.rename(dst)
                except Exception:
                    pass
            raise e

# ---------------------------- 核心处理 ----------------------------

def process_one(path: Path, args) -> Dict[str,Any]:
    result = {'file':str(path),'status':'SKIP','reasons':'','action':'','message':''}
    try:
        probe = parse_flac(path)
        if not probe.is_flac:
            result['status']='SKIP'; result['message']=probe.reason; return result
        dec_ok, dec_msg = soundfile_decode_ok(path)
        plan = decide_fix(probe, dec_ok, args.keep_cover, args.meta_threshold_mb, int(args.max_cover_mb*1024*1024))
        result['reasons'] = '; '.join(plan.reasons) if plan.reasons else '（无）'
        result['action'] = plan.action
        if not plan.needs_fix:
            result['status']='OK'; result['message']=dec_msg; return result
        if args.dry_run:
            result['status']='DRYRUN'; result['message']=f"将执行: {plan.action}"; return result

        # 备份
        if args.backup:
            bak_dir = Path(args.backup_dir); bak_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, bak_dir / path.name)

        # 同目录临时文件，避免跨盘
        with tempfile.TemporaryDirectory(dir=path.parent) as td:
            tmpdir = Path(td)
            cover_tmp: Optional[Path] = None
            if plan.keep_cover and which('metaflac'):
                cover_tmp = export_cover_with_metaflac(path, tmpdir)
            out_tmp = tmpdir / (path.stem + '.__fixed__.flac')

            ok = False
            if plan.action == 'ffmpeg':
                ok = reencode_with_ffmpeg(path, out_tmp)
            elif plan.action == 'flac':
                ok = reencode_with_flac_cli(path, out_tmp)
            elif plan.action == 'metaflac':
                ok = strip_all_metadata_with_metaflac(path)
                if ok:
                    dec2_ok, _ = soundfile_decode_ok(path)
                    result['status'] = 'FIXED' if dec2_ok else 'FAIL'
                    result['message'] = 'metaflac 清空元数据后验证' if dec2_ok else 'metaflac 清空后仍不可读'
                    return result
            else:
                result['status']='FAIL'; result['message']='无可用修复工具（请安装 ffmpeg 或 flac）'; return result

            if not ok or not out_tmp.exists():
                result['status']='FAIL'; result['message']=f'{plan.action} 生成失败'; return result

            if plan.keep_cover and cover_tmp and which('metaflac'):
                import_ok = import_cover_with_metaflac(out_tmp, cover_tmp)
                if not import_ok:
                    result['message'] += '（封面导入失败）'

            dec2_ok, dec2_msg = soundfile_decode_ok(out_tmp)
            if not dec2_ok:
                result['status']='FAIL'; result['message']=f'修复后验证失败: {dec2_msg}'; return result

            atomic_replace(out_tmp, path)
            result['status']='FIXED'; result['message']=f'完成 {plan.action} 修复并验证成功'
            return result

    except Exception as e:
        result['status']='ERROR'; result['message']=f'{e.__class__.__name__}: {e}'
        return result

# ---------------------------- 扫描与主程序 ----------------------------

def find_flacs(root: Path) -> List[Path]:
    files: List[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for n in filenames:
            if n.lower().endswith('.flac'):
                files.append(Path(dirpath) / n)
    return files

def main():
    ap = argparse.ArgumentParser(description='递归扫描并修复异常 FLAC 文件')
    ap.add_argument('root', nargs='?', default='.', help='扫描根目录（默认：当前目录）')
    ap.add_argument('--workers', type=int, default=max(4, os.cpu_count() or 4), help='并发线程数')
    ap.add_argument('--dry-run', action='store_true', help='只显示将要执行的操作，不实际修改')
    ap.add_argument('--backup', action='store_true', help='修复前备份原文件到指定目录')
    ap.add_argument('--backup-dir', type=str, default='./.flac_bak', help='备份目录（配合 --backup 使用）')
    ap.add_argument('--keep-cover', action='store_true', help='尽量保留封面（若太大则自动丢弃）')
    ap.add_argument('--max-cover-mb', type=float, default=1.5, help='保留封面的最大大小（MB）')
    ap.add_argument('--meta-threshold-mb', type=float, default=8.0, help='元数据大小阈值（超过则视为异常）')
    ap.add_argument('--csv', type=str, default='', help='输出 CSV 报告路径')
    ap.add_argument('--use', choices=['ffmpeg','flac','auto'], default='auto', help='优先使用的修复方式（默认 auto）')

    args = ap.parse_args()

    if args.use in ('auto','ffmpeg') and not which('ffmpeg'):
        print('[警告] 未检测到 ffmpeg，建议安装。', file=sys.stderr)
    if args.use == 'flac' and not which('flac'):
        print('[警告] 未检测到 flac，将退化为其它方式。', file=sys.stderr)
    if args.keep_cover and not which('metaflac'):
        print('[提示] 要保留封面建议安装 metaflac，否则封面可能丢失。', file=sys.stderr)

    root = Path(args.root).resolve()
    files = find_flacs(root)
    if not files:
        print('未找到 .flac 文件。'); return

    print(f'发现 {len(files)} 个 FLAC 文件，开始扫描...\n')

    results: List[Dict[str,Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(process_one, f, args): f for f in files}
        for fut in as_completed(futures):
            f = futures[fut]
            res = fut.result()
            results.append(res)
            print(f"[{res['status']}] {f}\n  -> {res['reasons'] or ''}\n  => {res['message']}")

    total = len(results)
    ok = sum(1 for r in results if r['status'] in ('OK','DRYRUN'))
    fixed = sum(1 for r in results if r['status']=='FIXED')
    fail = sum(1 for r in results if r['status'] in ('FAIL','ERROR'))
    print('\n=== Summary ===')
    print(f'Total: {total} | OK/DRY: {ok} | FIXED: {fixed} | FAIL/ERROR: {fail}')

    if args.csv:
        csv_path = Path(args.csv)
        with csv_path.open('w', newline='', encoding='utf-8') as fp:
            w = csv.DictWriter(fp, fieldnames=['file','status','reasons','action','message'])
            w.writeheader()
            w.writerows(results)
        print(f'CSV 报告写入: {csv_path.resolve()}')

if __name__ == '__main__':
    main()
