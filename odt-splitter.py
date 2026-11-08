#!/usr/bin/env python3
import os
import zipfile
import xml.etree.ElementTree as ET
import re

def split_odt_by_headings(odt_path, output_dir="chapter_output", include_tables=True):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    with zipfile.ZipFile(odt_path, 'r') as z:
        content_xml = z.read('content.xml')
        
    root = ET.fromstring(content_xml)
    
    namespaces = {
        'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
        'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0'
    }
    
    current_heading = "00_Einleitung"
    current_content = []
    file_counter = 1
    
    def sanitize_filename(name):
        return re.sub(r'[\\/*?:"<>|]', "", name).strip()

    def save_chapter(counter, heading, content_list):
        if not content_list and heading == "00_Einleitung":
            return 
            
        clean_title = sanitize_filename(heading)
        filename = f"{counter:02d}_{clean_title[:50]}.txt"
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
    for body in root.findall('.//text:heading-list', namespaces) or [root]:
        for element in root.iter():
            tag_local = element.tag.split('}')[-1] if '}' in element.tag else element.tag
            
            if tag_local == 'h':  
                # Vorheriges Tabellenende sichern
                if in_table and current_row_cells:
                    current_content.append("\t".join(current_row_cells))
                    current_row_cells = []
                in_table = False
                    
                save_chapter(file_counter, current_heading, current_content)
                file_counter += 1
                current_heading = "".join(element.itertext()).strip()
                current_content = []
                
            elif tag_local == 'p':  
                # Wenn in Tabelle: parallele p-Elemente sind Doppelte – überspringen
                # aber nicht den Tabellen-Zustand zurücksetzen
                if in_table:
                    continue
                
                # Vorheriges Tabellenende sichern (außerhalb von Tabellen)
                if in_table and current_row_cells:
                    current_content.append("\t".join(current_row_cells))
                    current_row_cells = []
                in_table = False
                    
                text = "".join(element.itertext()).strip()
                if text:  
                    current_content.append(text)
            
            elif tag_local == 'table-row' and include_tables:
                # Vorherige Zeile sichern
                if current_row_cells:
                    current_content.append("\t".join(current_row_cells))
                    current_row_cells = []
                in_table = True
                
            elif tag_local == 'table-cell' and include_tables:
                cell_text = "".join(element.itertext()).strip()
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
    args = parser.parse_args()
    split_odt_by_headings(args.odt_file, args.output, include_tables=not args.no_tables)
