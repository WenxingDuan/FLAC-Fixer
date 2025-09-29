# FLAC AutoFix

`flac_autofix.py` 是一个用于 **递归扫描并修复异常 FLAC 文件** 的 Python 工具，专门解决那些在 foobar2000、PotPlayer 等严格播放器里无法播放、但在部分宽松播放器（如网易云音乐）还能播的 FLAC 文件。

这些问题通常源于 **元数据块损坏或不规范**（如 UNKNOWN 块、未正确终止、超大封面图片），而非音频数据本身。

---

## 功能特点

- **递归扫描**：遍历指定目录及所有子目录中的 `.flac` 文件。
- **检测异常**：
  - UNKNOWN 元数据块
  - is_last 标记缺失
  - 元数据区异常大（默认 > 8MB）
  - 封面图片过大（默认 > 1.5MB）
  - 解码失败（libsndfile/soundfile 检测）
- **修复方式**：
  - **ffmpeg**（推荐）：无损重封装为规范 FLAC。
  - **flac 官方工具**：解码为 WAV 再转回 FLAC。
  - **metaflac**：清空或重新写元数据。
- **封面处理**：可选择保留封面（需 `metaflac`），并限制大小，避免兼容性问题。
- **原子替换**：修复成功后替换原文件，避免中途中断导致文件丢失。
- **跨盘安全**：所有临时文件在目标文件所在目录创建，避免 Windows 上 `WinError 17`。
- **并发处理**：多线程并行加速（可调节线程数）。
- **备份与报告**：支持备份原文件到 `.flac_bak`，支持输出 CSV 报告。

---

## 使用方法

### 安装依赖
```bash
pip install soundfile
# 推荐安装外部工具：
# Windows: 安装 ffmpeg，并将 ffmpeg.exe 加入 PATH
# macOS: brew install ffmpeg flac
# Ubuntu/Debian: sudo apt-get install ffmpeg flac
```

### 基本用法
```bash
# 扫描当前目录，实际修复
python flac_autofix.py .

# 扫描但不修改（干跑模式）
python flac_autofix.py . --dry-run

# 修复时保留封面（限制最大 1.5MB）
python flac_autofix.py . --keep-cover --max-cover-mb 1.5

# 修复前备份原文件到 ./.flac_bak
python flac_autofix.py . --backup

# 多线程处理并输出 CSV 报告
python flac_autofix.py . --workers 8 --csv report.csv
```

### 参数说明
- `root`：扫描根目录（默认：当前目录）。
- `--workers`：并发线程数（默认：CPU 核数）。
- `--dry-run`：只扫描不修改。
- `--backup`：修复前备份原文件。
- `--backup-dir`：备份目录（默认 `./.flac_bak`）。
- `--keep-cover`：尝试保留封面。
- `--max-cover-mb`：保留封面的最大大小（默认 1.5MB）。
- `--meta-threshold-mb`：元数据区大小阈值（默认 8MB）。
- `--csv`：保存扫描/修复结果为 CSV 文件。
- `--use`：优先使用的修复方式（`ffmpeg` / `flac` / `auto`）。

---

## 工作原理

1. **解析文件头**，读取元数据块，检查是否有异常。
2. **尝试解码**，检测是否能正常读出音频。
3. **决定修复方案**：
   - 如果检测到异常，优先用 **ffmpeg** 重封装。
   - 如果没有 ffmpeg，则尝试用 **flac** 官方工具。
   - 如果仅是元数据问题，则尝试用 **metaflac** 清理。
4. **生成临时文件**，验证能否解码。
5. **原子替换**，确保不会在失败时破坏原文件。

---

## 常见问题

- **WinError 17**：新版已修复，所有临时文件在目标文件所在分区生成。
- **PermissionError**：文件被播放器或系统占用，请先关闭相关应用。
- **封面丢失**：ffmpeg 默认不保留封面，如需保留请加 `--keep-cover` 并安装 `metaflac`。

---

## 推荐工作流程

1. 先跑一遍 `--dry-run`，确认哪些文件会被修复。
2. 若确认无误，再加上 `--backup` 和 `--keep-cover` 执行一次修复。
3. 检查生成的 CSV 报告，确保修复结果符合预期。

---

## 授权

自由使用、修改、分发。
