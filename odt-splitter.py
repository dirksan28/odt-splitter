import os
import zipfile
import xml.etree.ElementTree as ET
import re

def split_odt_by_headings(odt_path, output_dir="kapitel_output"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    with zipfile.ZipFile(odt_path, 'r') as z:
        content_xml = z.read('content.xml')
        
    root = ET.fromstring(content_xml)
    
    namespaces = {
        'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'
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

    # Durchsuche das Dokument chronologisch
    for body in root.findall('.//text:heading-list', namespaces) or [root]:
        for element in root.iter():
            tag_local = element.tag.split('}')[-1] if '}' in element.tag else element.tag
            
            if tag_local == 'h':  
                save_chapter(file_counter, current_heading, current_content)
                file_counter += 1
                current_heading = "".join(element.itertext()).strip()
                current_content = []
                
            elif tag_local == 'p':  
                text = "".join(element.itertext()).strip()
                if text:  
                    current_content.append(text)

    # Letztes Kapitel abspeichern
    save_chapter(file_counter, current_heading, current_content)

# Anwendung:
# split_odt_by_headings("ihre_datei.odt")
