# FLAC AutoFix / FLAC 自动修复工具

`flac_autofix.py` 是一个用于 **递归扫描并修复异常 FLAC 文件** 的 Python 工具。它可以帮助你修复那些在 foobar2000、PotPlayer 等严格播放器里无法播放，但在部分宽松播放器（如网易云音乐）仍能播放的 FLAC 文件。

---

## 功能特点 / Features

- **递归扫描 / Recursive Scan**：遍历指定目录及所有子目录中的 `.flac` 文件。
- **异常检测 / Error Detection**：
  - UNKNOWN 元数据块 / UNKNOWN metadata blocks
  - is_last 标记缺失 / Missing `is_last` flag
  - 元数据过大（默认 > 8MB）/ Oversized metadata (>8MB)
  - 封面图片过大（默认 > 1.5MB）/ Oversized cover image (>1.5MB)
  - 解码失败 / Decode failure
- **修复方式 / Repair Methods**：
  - **ffmpeg（推荐 / Recommended）**：无损重封装 FLAC / Lossless re-encode to FLAC.
  - **flac 官方工具 / flac CLI**：解码为 WAV 再转回 FLAC / Decode to WAV then re-encode.
  - **metaflac**：清空或重写元数据 / Strip or rewrite metadata.
- **封面处理 / Cover Handling**：可选择保留封面（需 `metaflac`），并可限制大小 / Optionally keep cover image (requires `metaflac`) with size limit.
- **跨盘安全 / Cross-drive Safe**：临时文件在目标文件所在目录创建，避免 Windows 上 `WinError 17` / Temporary files created in same drive to avoid `WinError 17`.
- **原子替换 / Atomic Replace**：修复成功后安全替换原文件 / Replace original file safely.
- **并发处理 / Multi-threaded**：线程池加速处理 / Parallel processing with thread pool.
- **备份与报告 / Backup & Report**：支持备份原文件并输出 CSV 报告 / Backup originals and generate CSV report.

---

## 安装依赖 / Installation

```bash
pip install soundfile
```

⚠️ **请务必安装 [ffmpeg](https://ffmpeg.org/download.html)**，它是最推荐的修复方式。  
⚠️ **Make sure you have [ffmpeg](https://ffmpeg.org/download.html) installed**, as it is the recommended repair method.

- Windows: 安装 FFmpeg 并将 `ffmpeg.exe` 加入 PATH / Install FFmpeg and add to PATH.
- macOS: `brew install ffmpeg flac`
- Ubuntu/Debian: `sudo apt-get install ffmpeg flac`

---

## 使用方法 / Usage

### 基本用法 / Basic Usage
```bash
# 扫描当前目录并修复 / Scan current directory and fix
python flac_autofix.py .

# 只扫描不修改 / Scan only (no changes)
python flac_autofix.py . --dry-run

# 修复时保留封面（限制 1.5MB）/ Keep cover image if <=1.5MB
python flac_autofix.py . --keep-cover --max-cover-mb 1.5

# 修复前备份原文件 / Backup before fixing
python flac_autofix.py . --backup

# 多线程处理并输出 CSV 报告 / Multi-threaded with CSV report
python flac_autofix.py . --workers 8 --csv report.csv
```

### 参数说明 / Options
- `root`：扫描根目录 / Root directory (default: current dir)
- `--workers`：并发线程数 / Number of threads
- `--dry-run`：只扫描不修改 / Dry-run (scan only)
- `--backup`：修复前备份 / Backup originals
- `--backup-dir`：备份目录 / Backup directory (default: ./.flac_bak)
- `--keep-cover`：尽量保留封面 / Try to keep cover
- `--max-cover-mb`：封面最大大小 / Max cover size (default 1.5MB)
- `--meta-threshold-mb`：元数据大小阈值 / Metadata threshold (default 8MB)
- `--csv`：保存 CSV 报告 / Save CSV report
- `--use`：优先修复方式 (`ffmpeg` / `flac` / `auto`) / Preferred repair method

---

## 工作原理 / How It Works

1. 解析文件头并检测异常 / Parse header & detect anomalies.
2. 尝试解码音频帧 / Try decoding audio frames.
3. 决定修复方案 / Decide repair method.
4. 在同一目录生成临时文件并验证 / Generate temp file in same dir & verify.
5. 替换原文件 / Replace original safely.

---

## 常见问题 / FAQ

- **WinError 17**：新版已修复，临时文件与目标文件同盘 / Fixed: temp files created in same drive.
- **PermissionError**：文件被播放器或系统占用，请关闭相关应用 / File in use, close players and retry.
- **封面丢失 / Missing cover**：ffmpeg 默认不保留封面，如需保留请加 `--keep-cover` 并安装 `metaflac` / By default, ffmpeg does not keep cover; use `--keep-cover` + `metaflac`.

---

## 推荐流程 / Suggested Workflow

1. 先跑一遍 `--dry-run` 看哪些文件需要修复 / Run `--dry-run` first to preview.
2. 再用 `--backup --keep-cover` 修复并保留封面 / Then run with backup & keep cover.
3. 检查 CSV 报告确认结果 / Check CSV report for results.

---

## License

自由使用、修改、分发 / Free to use, modify, distribute.
