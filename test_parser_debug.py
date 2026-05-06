from src.ingestion.parser import MarkdownParser
from pathlib import Path

parser = MarkdownParser()
file_path = r"C:\Users\ADMIN\Documents\Evangelista & Co\Evangelista & Co\Metodologias\Evangelista-Vault\Evangelista-Obsidian\evangelista-vault\benchmarks\benchmark-manufactura.md"
doc = parser.parse_file(file_path)
if doc:
    print(f"SUCCESS: {doc.id} - {doc.title}")
else:
    print("FAILED to parse")
