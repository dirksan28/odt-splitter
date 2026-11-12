#!/usr/bin/env python3
import os
import zipfile
import xml.etree.ElementTree as ET
import re

NS_TEXT = 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'
NS_STYLE = 'urn:oasis:names:tc:opendocument:xmlns:style:1.0'
NS_FO = 'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0'

def local_name(tag):
    return tag.split('}')[-1] if '}' in tag else tag

def element_text(element):
    """Return an element's text, preserving inline whitespace markers.

    Plain itertext() silently drops <text:tab/>, <text:s/> and
    <text:line-break/>, which glues TOC page numbers to the preceding word.
    """
    parts = []

    def recurse(el):
        tag = local_name(el.tag)
        if tag == 'tab':
            parts.append('\t')
        elif tag == 's':
            try:
                count = int(el.get(f'{{{NS_TEXT}}}c', '1'))
            except ValueError:
                count = 1
            parts.append(' ' * count)
        elif tag == 'line-break':
            parts.append('\n')
        else:
            if el.text:
                parts.append(el.text)
            for child in el:
                recurse(child)
                if child.tail:
                    parts.append(child.tail)

    recurse(element)
    return ''.join(parts)

def collect_style_info(style_roots):
    parents = {}
    margins = {}
    outline_levels = {}

    for root in style_roots:
        if root is None:
            continue
        for style in root.iter(f'{{{NS_STYLE}}}style'):
            if style.get(f'{{{NS_STYLE}}}family') != 'paragraph':
                continue
            name = style.get(f'{{{NS_STYLE}}}name')
            parents[name] = style.get(f'{{{NS_STYLE}}}parent-style-name')
            props = style.find(f'{{{NS_STYLE}}}paragraph-properties')
            if props is None:
                continue
            margin = props.get(f'{{{NS_FO}}}margin-left')
            if margin is not None:
                margins[name] = margin
            outline = props.get(f'{{{NS_TEXT}}}outline-level')
            if outline is not None:
                outline_levels[name] = outline

    def effective(name, values):
        seen = set()
        while name and name not in seen:
            seen.add(name)
            if name in values:
                return values[name]
            name = parents.get(name)
        return None

    return (
        lambda name: effective(name, margins),
        lambda name: effective(name, outline_levels),
    )

def remove_footnotes(root):
    """Detach footnote elements (including their bodies) from the tree.

    Footnote text lives inside <text:note><text:note-body>…</text:note-body>
    </text:note>. Removing the whole note element ensures neither the footnote
    text nor its citation leaks into the surrounding paragraph via itertext().
    """
    def recurse(element):
        for child in list(element):
            if local_name(child.tag) in ('note', 'footnote'):
                note_class = child.get(f'{{{NS_TEXT}}}note-class', 'footnote')
                if note_class == 'footnote':
                    element.remove(child)
                    continue
            recurse(child)

    recurse(root)

def walk_paragraphs(element, in_table=False):
    tag = local_name(element.tag)
    inside_table = in_table or tag in ('table', 'table-cell')
    for child in element:
        yield from walk_paragraphs(child, inside_table)
    if tag == 'p':
        yield element, in_table

def split_odt_by_headings(odt_path, output_dir="chapter_output", include_tables=True, heading_level=1, suppress_footnotes=True):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    with zipfile.ZipFile(odt_path, 'r') as z:
        content_xml = z.read('content.xml')
        try:
            styles_xml = z.read('styles.xml')
        except KeyError:
            styles_xml = None
        
    root = ET.fromstring(content_xml)
    if suppress_footnotes:
        remove_footnotes(root)
    styles_root = ET.fromstring(styles_xml) if styles_xml else None
    get_margin, get_outline_level = collect_style_info([styles_root, root])

    # Some ODT files (e.g. exported/edited documents) do not use real heading
    # elements at all. In that case fall back to numbered paragraphs such as
    # "1. Title" or "2.1 Subtitle" that are not indented (TOC entries and
    # numbered list items are usually indented).
    style_heading_levels = {}
    fallback_heading_levels = {}
    has_native_headings = any(local_name(e.tag) == 'h' for e in root.iter())

    for paragraph, in_table in walk_paragraphs(root):
        if in_table:
            continue
        style_name = paragraph.get(f'{{{NS_TEXT}}}style-name')
        outline = get_outline_level(style_name)
        if outline is not None:
            try:
                style_heading_levels[id(paragraph)] = int(outline)
            except ValueError:
                pass

    if not has_native_headings and not style_heading_levels:
        for paragraph, in_table in walk_paragraphs(root):
            if in_table:
                continue
            text = element_text(paragraph)
            match = re.match(r'^\s*(\d+(?:\.\d+)*)\.?\s+\S', text)
            if not match:
                continue
            if any(local_name(e.tag) == 'tab' for e in paragraph.iter()):
                continue
            margin = get_margin(paragraph.get(f'{{{NS_TEXT}}}style-name'))
            if margin not in (None, '0', '0cm', '0in', '0pt'):
                continue
            fallback_heading_levels[id(paragraph)] = match.group(1).count('.') + 1
    
    current_heading = ""
    current_content = []
    file_counter = 1
    
    def sanitize_filename(name):
        return re.sub(r'[\\/*?:\s<>|]', "", name).strip()

    def save_chapter(counter, heading, content_list):
        if not content_list and (heading == "00_Einleitung" or heading == ""):
            return 
            
        clean_title = sanitize_filename(heading)
        filename = f"{counter:02d}_{clean_title[:25]}.txt"
        filepath = os.path.join(output_dir, filename)
        
        # 1. Text zusammenfügen
        full_text = "\n".join(content_list)
        
        # 2. Unsichtbare weiche Trennstriche (Soft-Hyphens) entfernen
        full_text = full_text.replace('\xad', '')
        
        # 3. Harte Trennstriche am Zeilenende entfernen und Wörter zusammenfügen
        # Beispiel: "Schreib-\nweise" wird zu "Schreibweise"
        full_text = re.sub(r'-\n', '', full_text)
        
        # Optional: Falls Wörter durch Leerzeichen + Bindestrich getrennt wurden
        # full_text = re.sub(r'- \n', '', full_text)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"Gespeichert: {filename}")

    # Tabellen-Zustandsvariablen
    in_table = False
    current_row_cells = []

    # Durchsuche das Dokument chronologisch
    for element in root.iter():
        tag_local = local_name(element.tag)
        
        heading_outline_level = None
        if tag_local == 'h':
            # Check outline level - only create new chapter if heading level <= specified level
            outline_attr = element.get(f'{{{NS_TEXT}}}outline-level', '1')
            try:
                heading_outline_level = int(outline_attr)
            except ValueError:
                heading_outline_level = 1
        elif tag_local == 'p':
            heading_outline_level = (
                fallback_heading_levels.get(id(element))
                or style_heading_levels.get(id(element))
            )

        if heading_outline_level is not None:
            # Vorheriges Tabellenende sichern
            if in_table and current_row_cells:
                current_content.append("\t".join(current_row_cells))
                current_row_cells = []
            in_table = False
                
            # Only create new chapter if heading level is within the allowed range
            if heading_outline_level <= heading_level:
                save_chapter(file_counter, current_heading, current_content)
                file_counter += 1
                current_heading = element_text(element).strip()
                current_content = []
            else:
                # Heading level too deep - add its text as paragraph content
                text = element_text(element).strip()
                if text:  
                    current_content.append(text)
                # Keep current heading unchanged (sub-heading becomes part of current chapter)
            
        elif tag_local == 'p':  
            # Wenn in Tabelle: parallele p-Elemente sind Doppelte – überspringen
            # aber nicht den Tabellen-Zustand zurücksetzen
            if in_table:
                continue
                
            text = element_text(element).strip()
            if text:  
                current_content.append(text)
        
        elif tag_local == 'table-row' and include_tables:
            # Vorherige Zeile sichern
            if current_row_cells:
                current_content.append("\t".join(current_row_cells))
                current_row_cells = []
            in_table = True
            
        elif tag_local == 'table-cell' and include_tables:
            cell_text = element_text(element).strip()
            if cell_text:
                current_row_cells.append(cell_text)

    # Letztes Kapitel abspeichern
    save_chapter(file_counter, current_heading, current_content)

# Anwendung:
# split_odt_by_headings("ihre_datei.odt")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Split ODT file by headings into separate text files')
    parser.add_argument('odt_file', help='Path to the .odt file')
    parser.add_argument('-o', '--output', default='chapter_output', help='Output directory (default: chapter_output)')
    parser.add_argument('--no-tables', action='store_true', help='Disable table content extraction')
    parser.add_argument('--no-footnotes', action='store_true', help='Include footnote content in output (default: footnotes suppressed)')
    parser.add_argument('--heading-level', type=int, default=1, help='Only split on headings at this outline level or higher (default: 1)')
    args = parser.parse_args()
    split_odt_by_headings(args.odt_file, args.output, include_tables=not args.no_tables, heading_level=args.heading_level, suppress_footnotes=not args.no_footnotes)
