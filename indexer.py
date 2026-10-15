import os
import json
import re 
from pathlib import Path
from html.parser import HTMLParser

class SlideParser (HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {"title": "", "date": "1970-01-01", "course": "General", "tags": "", "description": "", }
        self.in_title = False 

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True
        elif tag == "meta":
            attr_dict = dict(attrs)
            name = attr_dict.get("name", "").lower()
            if name in self.meta:
                self.meta[name] = attr_dict.get("content", "")

    def handle_data(self, data):
        if self.in_title and not self.meta["title"]:
            self.meta["title"] = data.script()

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

def build_index(slides_dir="slides", output_file="presentaciones.json"):
    presentaciones[]
    base_path = Path(slides_dir)
    
    for html_file in base_path.rglob("*.html"):
        with open(html_file, "r", encoding="utf-8") as f:
            content f.read

        parser = SlideParser()
        parser.feed(content)

        #exraer texto plano básico del body para buscar por contenido de diapositiva
        body_match = re.search(r'<body.*?>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
        raw_text = re.sub(r'<[^>]+>', ' ', body_match.group(1)) if body_match else ""
        clean_text = " ".join(raw_text.split()).lower()

