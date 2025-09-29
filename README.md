# FLAC AutoFix

## English Version

`flac_autofix.py` is a Python tool to **recursively scan and repair problematic FLAC files**. It helps fix FLAC files that cannot be played by strict players (e.g., foobar2000, PotPlayer) but still work in more lenient ones (e.g., NetEase Music).

---

### Features
- **Recursive Scan**: Traverse all `.flac` files in the target directory and subdirectories.
- **Error Detection**:
  - UNKNOWN metadata blocks
  - Missing `is_last` flag
  - Oversized metadata (>8MB by default)
  - Oversized cover image (>1.5MB by default)
  - Decode failure
- **Repair Methods**:
  - **ffmpeg (Recommended)**: Lossless re-encode to FLAC.
  - **flac CLI**: Decode to WAV then re-encode.
  - **metaflac**: Strip or rewrite metadata.
- **Cover Handling**: Optionally keep cover image (requires `metaflac`) with size limit.
- **Cross-drive Safe**: Temp files created in same drive to avoid Windows `WinError 17`.
- **Atomic Replace**: Safely replace original file only after successful repair.
- **Multi-threaded**: Parallel processing with thread pool.
- **Backup & Report**: Support backup of originals and CSV report output.

---

### Installation
```bash
pip install soundfile
```

⚠️ **Make sure you have [ffmpeg](https://ffmpeg.org/download.html) installed**, as it is the recommended repair method.
- Windows: Install FFmpeg and add `ffmpeg.exe` to PATH.
- macOS: `brew install ffmpeg flac`
- Ubuntu/Debian: `sudo apt-get install ffmpeg flac`

---

### Usage
```bash
# Scan current directory and fix
python flac_autofix.py .

# Scan only (no changes)
python flac_autofix.py . --dry-run

# Keep cover image if <=1.5MB
python flac_autofix.py . --keep-cover --max-cover-mb 1.5

# Backup before fixing
python flac_autofix.py . --backup

# Multi-threaded with CSV report
python flac_autofix.py . --workers 8 --csv report.csv
```

**Options**:
- `root`: Root directory (default: current dir)
- `--workers`: Number of threads
- `--dry-run`: Dry-run (scan only)
- `--backup`: Backup originals
- `--backup-dir`: Backup directory (default: ./.flac_bak)
- `--keep-cover`: Try to keep cover
- `--max-cover-mb`: Max cover size (default 1.5MB)
- `--meta-threshold-mb`: Metadata threshold (default 8MB)
- `--csv`: Save CSV report
- `--use`: Preferred repair method (`ffmpeg` / `flac` / `auto`)

---

### How It Works
1. Parse header & detect anomalies.
2. Try decoding audio frames.
3. Decide repair method.
4. Generate temp file in same dir & verify.
5. Replace original safely.

---

### FAQ
- **WinError 17**: Fixed. Temp files created in same drive.
- **PermissionError**: File is in use. Close players and retry.
- **Missing cover**: ffmpeg does not keep cover by default. Use `--keep-cover` with `metaflac`.

---

### Suggested Workflow
1. Run `--dry-run` first to preview.
2. Then run with `--backup --keep-cover` to fix.
3. Check CSV report for results.

---

## 中文版本

`flac_autofix.py` 是一个用于 **递归扫描并修复异常 FLAC 文件** 的 Python 工具。它可以帮助修复那些在 foobar2000、PotPlayer 等严格播放器里无法播放，但在网易云音乐等宽松播放器里仍能播放的文件。

---

### 功能特点
- **递归扫描**：遍历指定目录及其子目录中的所有 `.flac` 文件。
- **异常检测**：
  - UNKNOWN 元数据块
  - 缺少 `is_last` 标记
  - 元数据区过大（默认 >8MB）
  - 封面图片过大（默认 >1.5MB）
  - 解码失败
- **修复方式**：
  - **ffmpeg（推荐）**：无损重封装为 FLAC。
  - **flac 官方工具**：解码为 WAV 再重新编码。
  - **metaflac**：清空或重写元数据。
- **封面处理**：可选保留封面（需 `metaflac`），并可限制大小。
- **跨盘安全**：临时文件在目标文件所在目录创建，避免 Windows `WinError 17`。
- **原子替换**：修复成功后安全替换原文件。
- **并发处理**：线程池并行加速。
- **备份与报告**：支持备份原文件并生成 CSV 报告。

---

### 安装依赖
```bash
pip install soundfile
```

⚠️ **请务必安装 [ffmpeg](https://ffmpeg.org/download.html)**，它是最推荐的修复方式。
- Windows: 安装 FFmpeg 并将 `ffmpeg.exe` 加入 PATH。
- macOS: `brew install ffmpeg flac`
- Ubuntu/Debian: `sudo apt-get install ffmpeg flac`

---

### 使用方法
```bash
# 扫描当前目录并修复
python flac_autofix.py .

# 只扫描不修改
python flac_autofix.py . --dry-run

# 修复时保留封面（大小 <=1.5MB）
python flac_autofix.py . --keep-cover --max-cover-mb 1.5

# 修复前备份原文件
python flac_autofix.py . --backup

# 多线程处理并输出 CSV 报告
python flac_autofix.py . --workers 8 --csv report.csv
```

**参数说明**：
- `root`：扫描根目录（默认：当前目录）
- `--workers`：并发线程数
- `--dry-run`：只扫描不修改
- `--backup`：修复前备份
- `--backup-dir`：备份目录（默认：./.flac_bak）
- `--keep-cover`：尽量保留封面
- `--max-cover-mb`：封面最大大小（默认 1.5MB）
- `--meta-threshold-mb`：元数据大小阈值（默认 8MB）
- `--csv`：保存 CSV 报告
- `--use`：优先修复方式（`ffmpeg` / `flac` / `auto`）

---

### 工作原理
1. 解析文件头，检测异常。
2. 尝试解码音频帧。
3. 决定修复方案。
4. 在同一目录生成临时文件并验证。
5. 替换原文件。

---

### 常见问题
- **WinError 17**：已修复，临时文件与目标文件同盘。
- **PermissionError**：文件被占用，请关闭播放器或其他程序后重试。
- **封面丢失**：ffmpeg 默认不保留封面。如需保留请加 `--keep-cover` 并安装 `metaflac`。

---

### 推荐流程
1. 先运行 `--dry-run` 预览。
2. 再运行 `--backup --keep-cover` 修复。
3. 检查 CSV 报告确认结果。

---

## License / 授权
自由使用、修改、分发 / Free to use, modify, distribute.