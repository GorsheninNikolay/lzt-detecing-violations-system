import hashlib
import json
from pathlib import Path

from PIL import Image
import pytest

from display_labels import equipment_label
from review_cards import main


def test_shared_presentation_cases():
    root = Path(__file__).resolve().parents[2]
    for row in json.loads((root / 'shared/display-label-cases.ru.json').read_text()):
        assert equipment_label(row['input']) == row['expected']


def test_changed_image_cannot_be_rendered_under_its_old_review_hash(tmp_path):
    source = tmp_path / 'source'
    (source / 'metadata').mkdir(parents=True);(source / 'manifests').mkdir()
    image = source / 'source.png'
    Image.new('RGB',(20,20),'white').save(image)
    expected = hashlib.sha256(image.read_bytes()).hexdigest()
    (source / 'metadata/source-class-samples.json').write_text(json.dumps([{
        'profile':'kaggle','class_name':'Roller','source_image':'original.png',
        'normalized_box':[.5,.5,.4,.4],'image_sha256':expected}]))
    (source / 'manifests/kaggle.json').write_text(json.dumps({'pairs':[{'source_path':'original.png','image':'source.png'}]}))
    external = tmp_path / 'external.json';external.write_text(json.dumps({'images':[]}))
    Image.new('RGB',(20,20),'black').save(image)
    with pytest.raises(ValueError,match='source_image_hash_mismatch'):
        main(tmp_path/'review',source,external)
    assert not (tmp_path/'review/cards.json').exists()
