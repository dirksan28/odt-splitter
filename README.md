# odt-splitter

A Python tool to split OpenDocument Text (.odt) files by headings into separate text files.

## Usage

### From the command line:

```bash
# Basic usage - splits the ODT file using heading detection
odt-splitter.py datei.odt

# With custom output directory
odt-splitter.py datei.odt -o meine_ausgabe

# Disable table content extraction
odt-splitter.py datei.odt --no-tables
```

### Arguments:

| Switch | Description | Default |
|--------|-------------|---------|
| `odt_file` | Path to the `.odt` file (required) | - |
| `-o, --output` | Output directory for the split text files | `chapter_output` |
| `--no-tables` | Disable extraction of table content | (enabled by default) |

## How it works

The script reads the `.odt` file (which is a zip archive containing XML), extracts the content, and splits it into separate text files based on document headings. Each chapter/section becomes its own `.txt` file in the output directory.

### Features:

- **Heading-based splitting**: Automatically detects headings and creates separate files for each section
- **Table support**: By default, table cells are extracted as tab-separated rows within the chapter text
- **Hard hyphen cleanup**: Removes syllable hyphens at line ends (e.g., "Schreib-\nweise" becomes "Schreibweise")
- **Soft-hyphen removal**: Strips invisible soft-hyphen characters (`\xad`)
- **Custom output directory**: Specify with `-o` or `--output` flag

## Examples

```bash
# Split default ODT, output to chapter_output directory
odt-splitter.py bach.odt

# Specify custom output directory
odt-splitter.py bach.odt -o my_chapters

# Disable table content extraction
odt-splitter.py bach.odt --no-tables
```