"""Presentation translations; original model labels and catalog membership stay unchanged."""
import json
from pathlib import Path
import re

LABELS = json.loads((Path(__file__).resolve().parents[2] / 'shared/display-labels.ru.json').read_text())


def equipment_label(name):
    normalized = re.sub(r'\s+', ' ', re.sub(r'[_-]+', ' ', name.strip().lower()))
    return (LABELS['equipment'].get(name) or LABELS['source_equipment'].get(normalized)
            or (name if re.search('^[^a-zа-яё]*[а-яё]', name, re.I)
                else 'Неопределённая техника'))
