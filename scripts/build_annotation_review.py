"""Build an offline human-review workspace from the checksum-bound source queue."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def build(output: Path, archive_path: Path, manifest_path: Path):
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    archive_hash = hashlib.sha256()
    with archive_path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            archive_hash.update(chunk)
    if archive_hash.hexdigest() != manifest['archive_sha256']:
        raise ValueError('Source archive checksum mismatch')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'images').mkdir(exist_ok=True)
    with ZipFile(archive_path) as archive:
        for item in manifest['images']:
            if not item['id'].isascii() or not all(c.isalnum() or c == '-' for c in item['id']):
                raise ValueError('Unsafe image identifier')
            data = archive.read(item['archive_member'])
            if hashlib.sha256(data).hexdigest() != item['sha256']:
                raise ValueError(f"Image checksum mismatch: {item['id']}")
            (output / 'images' / f"{item['id']}.png").write_bytes(data)
    payload = {**manifest, 'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest()}
    (output / 'dataset.js').write_text('const DATASET = ' + json.dumps(payload, ensure_ascii=False) + ';\n')
    shutil.copyfile(ROOT / 'scripts/annotation-review.html', output / 'index.html')
    for name in ('onest-cyrillic.woff2', 'onest-latin.woff2'):
        shutil.copyfile(ROOT / 'web/src/assets/fonts' / name, output / name)
    (output / 'README.md').write_text('''# Ручная разметка\n\nОткройте index.html самостоятельно в браузере. Интернет и сервер не нужны.\n\n1. Укажите имя проверяющего.\n2. Для каждого класса выберите присутствие, отсутствие, неуверенность или непригодность кадра.\n3. Для присутствующей техники нарисуйте рамки: выберите класс и протяните по фотографии. Ошибочную рамку удалите и нарисуйте заново. Координаты можно поправить численно.\n4. Машинные предложения выключены по умолчанию. Их можно показать и принять по одному после проверки; они никогда не становятся разметкой автоматически.\n5. Отметьте признаки сцены и этап; если этап не виден, выберите «Не установлен».\n6. Источник, камера и серия — только если известны. Не придумывайте эти сведения по похожести кадров.\n7. Нажмите «Подтвердить кадр и дальше». Необязательные сомнения запишите в заметке.\n8. Регулярно нажимайте «Экспорт JSON». Пришлите итоговый JSON в этот диалог. Частичный экспорт тоже допустим.\n\nПрогресс сохраняется только в этом браузере на этом компьютере; копия JSON надёжнее. Его можно импортировать на другом компьютере вместе с этим же набором. Фотографии никуда не отправляются.\n\nЭтот набор содержит 100 исходных фотографий организаторов, но не гарантирует присутствие всех восьми классов. Неизвестные группы происхождения остаются неизвестными и не позволяют автоматически объявить независимую приёмочную выборку. Разметка не выдаёт разрешение на облачную отправку.\n''')
    return len(manifest['images'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive', type=Path, default=ROOT / 'artifacts/dataset/Строительная_техника.zip')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'evaluation/expansion/draft-annotations.json')
    args = parser.parse_args()
    print(f'Prepared {build(args.output, args.archive, args.manifest)} checksum-verified images in {args.output}')
