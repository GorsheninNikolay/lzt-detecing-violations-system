"""Create a local visual adjudication packet; never approves proposed labels."""
import argparse
import hashlib
import re
import base64
from html import escape
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from display_labels import equipment_label

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('/private/tmp/lzt-yolo-training-extracted/lzt-yolo-training-kit')
OUTPUT = ROOT / 'output/hybrid-quality/human-review'


def preview(payload, boxes):
    with Image.open(io.BytesIO(payload)) as original:
        image = ImageOps.exif_transpose(original).convert('RGB')
        width, height = image.size
        image.thumbnail((1000, 650))
        draw = ImageDraw.Draw(image)
        for box in boxes:
            x, y, w, h = box
            bounds = (x / width * image.width, y / height * image.height,
                      (x+w) / width * image.width, (y+h) / height * image.height)
            draw.rectangle(bounds, outline='#fbd24b', width=3)
        stream = io.BytesIO()
        image.save(stream, format='JPEG', quality=90)
        return 'data:image/jpeg;base64,' + base64.b64encode(stream.getvalue()).decode()


def main(output=OUTPUT, source=SOURCE, external_review=ROOT / 'output/hybrid-quality/external-candidates/review-candidates.json'):
    cards = []
    samples = json.loads((source / 'metadata/source-class-samples.json').read_text())
    manifest = json.loads((source / 'manifests/kaggle.json').read_text())
    paths = {row['source_path']: row['image'] for row in manifest['pairs']}
    for row in samples:
        if row['profile'] != 'kaggle' or row['class_name'] not in ('Roller', 'Crane manipulator', 'Autocran'):
            continue
        path = source / paths[row['source_image']]
        with Image.open(path) as image:
            width, height = image.size
        cx, cy, bw, bh = row['normalized_box']
        box = [(cx-bw/2)*width, (cy-bh/2)*height, bw*width, bh*height]
        cards.append((row['class_name'], path, [box], 'Образец train/val для проверки смысла класса. В финальный контроль не включать.',
                      row['image_sha256']))
    external = json.loads(external_review.read_text())
    for row in external['images']:
        labels = ', '.join(label['class'] for label in row['original_labels'])
        cards.append((labels, ROOT / row['image'], [label['publisher_annotation']['bbox'] for label in row['original_labels']],
                      'Открытый тестовый кандидат, CC BY 4.0. Камера и время не подтверждены. Исходная разметка сохранена; оценки действий и сигналов ещё не подтверждены.', row['image_sha256']))
    output.mkdir(parents=True, exist_ok=True)
    approval_path = ROOT / 'evaluation/hybrid/human-review-cards-2026-09-27.json'
    approval = json.loads(approval_path.read_text()) if approval_path.is_file() else {}
    archived = OUTPUT / 'review.en-original.html'
    original_previews = []
    if archived.is_file() and hashlib.sha256(archived.read_bytes()).hexdigest() == approval.get('reviewed_html_sha256'):
        original_previews = re.findall(r'<img src="([^"]+)"', archived.read_text())
    page = ['<!doctype html><html lang="ru"><meta charset="utf-8"><title>Проверка классов</title><style>body{font:18px system-ui;background:#211331;color:#f7f4f9;max-width:1100px;margin:40px auto;padding:20px}article{border-top:1px solid #b984e0;padding:28px 0}img{max-width:100%}code{font-size:12px;overflow-wrap:anywhere}p{line-height:1.5}a{color:#d7a8f6}</style><h1>Проверка классов и кандидатов</h1><p>Жёлтая рамка — предложение из исходной разметки. Для каждого кадра подтвердите физический тип машины и рамку или укажите исправление. Присутствие машины не доказывает работу или простой.</p><p>Отдельно требуется утвердить полный контроль: земляные, бетонные, дорожные работы × норма, обоснованный риск, неоднозначность, непригодные данные. Эти карточки ещё не покрывают всю матрицу.</p>']
    receipt = []
    for i, (name, path, boxes, note, sha) in enumerate(cards, 1):
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != sha:
            raise ValueError('source_image_hash_mismatch')
        rendered = preview(payload, boxes)
        approved = (i <= len(original_previews) and i <= len(approval.get('reviewed_cards', []))
                    and rendered == original_previews[i-1]
                    and approval['reviewed_cards'][i-1]['raw_class'] == name
                    and approval['reviewed_cards'][i-1]['sha256'] == sha)
        review_note = 'Класс и рамки подтверждены владельцем.' if approved else 'Решение: класс / рамка / видимые признаки действия / что нельзя определить.'
        page.append(f'<article id="card-{i}"><h2>{i}. Исходная метка: {escape(', '.join(equipment_label(part) for part in name.split(', ')))}</h2><img src="{rendered}" alt="Кандидат {i} с исходными рамками"><p>{escape(note)}</p><p><a href="{escape(path.as_uri())}">Исходное фото</a></p><code>SHA256 {sha}</code><p>{review_note}</p></article>')
        receipt.append({'card': i, 'raw_class': name, 'path': str(path), 'sha256': sha, 'status': 'approved_classes_and_boxes' if approved else 'pending_human_adjudication'})
    if receipt and all(row['status'] == 'approved_classes_and_boxes' for row in receipt):
        page[0] = page[0].replace('Для каждого кадра подтвердите физический тип машины и рамку или укажите исправление.',
                                f'Классы и рамки этих {len(receipt)} карточек подтверждены владельцем.')
    page.append('<p>Источник внешних кадров: Capstone LKZGQ, Construction Vehicle Detection v2, CC BY 4.0. Полная исходная разметка и ссылки — в external-candidates/sources.json. Кран-манипулятор и достоверные временные серии ещё не обеспечены.</p></html>')
    with (output / 'review.html').open('x') as stream:
        stream.write('\n'.join(page))
    with (output / 'cards.json').open('x') as stream:
        json.dump({'status': 'approved_classes_and_boxes' if approved else 'pending_human_adjudication','cards':receipt},stream,ensure_ascii=False,indent=2)
    print(output / 'review.html')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--external-review', type=Path, default=ROOT / 'output/hybrid-quality/external-candidates/review-candidates.json')
    args = parser.parse_args()
    main(args.output, args.source, args.external_review)
