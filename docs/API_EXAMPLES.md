# Примеры API

Все команды ниже предназначены для локального сервиса. Никакой реальный облачный вызов не нужен для проверки схемы и чтения документации. Запуск с настоящим профилем и ключом расходует квоту; для автоматических проверок используйте [mock-тест](../backend/tests/test_deepseek.py).

```sh
curl --fail http://127.0.0.1:8096/api/openapi.json
curl --fail http://127.0.0.1:8096/api/projects
curl --fail -H 'Content-Type: application/json' \
  --data '{"name":"Демонстрационная площадка","timezone":"Europe/Moscow"}' \
  http://127.0.0.1:8096/api/projects
```

Подготовка запроса из локального JPEG/PNG (фото не печатается в терминал):

```sh
python3 - photo.png > request.json <<'PY'
import base64, json, sys
from pathlib import Path
print(json.dumps({"intent":"observation_only","cloud_processing_consent":True,
 "scenario":"Обзор площадки","observation_area":"Северный участок",
 "period":"2026-09-26T12:00:00+03:00",
 "requested_classes":["excavator","dump_truck"],
 "image_base64":base64.b64encode(Path(sys.argv[1]).read_bytes()).decode()}))
PY
curl --fail-with-body -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: example-upload-20260926-001' \
  --data-binary @request.json http://127.0.0.1:8096/api/runs/single-image
```

При потере ответа сохраняйте `request.json` и ключ до установления результата. Для другого фото нужен новый ключ. Удалите файл после проверки, если локальное хранение копии фото больше не нужно.

Серия использует `/runs/series` и `images_base64` (2–8 элементов), сохраняя остальные поля. Для привязки к участку нужны вместе `project_id`, `zone_id`, `capture_times`; `plan_revision_id` опционален. Времена содержат UTC-смещение и соответствуют порядку кадров. Нельзя привязать участок чужого проекта.

Ответ принятия: `202 {"run_id":"…","state":"queued"}`. Фактический состав включает идентификатор и состояние согласно OpenAPI. Чтение: `GET /api/runs/{run_id}`. Основные поля:

```json
{
  "state": "succeeded",
  "cloud_processing_consent": true,
  "ai_assessment": {
    "summary": "В кадре видна строительная техника.",
    "stage_hypothesis": {"stage": "unknown", "reason": "Недостаточно признаков сцены."},
    "risks": [],
    "recommendations": ["Проверить организацию работ на месте."],
    "limitations": ["План не привязан: данных для вывода об отставании нет."]
  }
}
```

Это иллюстрация формы ответа, не фактический вывод модели. `ai_evidence` содержит raw provider response, usage, версию инструкции/схемы и frozen context. Для старого run `ai_assessment: null`. `objects[].details.type_ru` — свободное название; `class_name: "unknown"` не входит в учебный каталог. `score: null` и `box: null` допустимы; не заменяйте их нулевой уверенностью или выдуманной рамкой.

| Статус | Пример кода | Действие |
| --- | --- | --- |
| 400 | `cloud_consent_required`, `invalid_image_file`, `profile_retired` | Исправить запрос; облачный вызов не повторять |
| 401/403 | `authentication_required`, `invalid_csrf` (в `detail`) | Проверить сессию, Origin и CSRF |
| 404 | `run_not_found` | Проверить идентификатор |
| 409 | `idempotency_key_conflict`, `retry_ineligible` | Не менять тело под существующим ключом |
| 413 | `request_too_large` | Уменьшить набор фото |
| 503 | `service_not_ready`, `profile_unauthorized` | Проверить readiness и конфигурацию |

Административный login возвращает CSRF-токен и cookie `owner_session`. Передавайте cookie, точный `Origin` и `X-CSRF-Token` для изменений. Не вставляйте реальные пароли/токены в shell history. `/admin/annotations/export` принимает `{"version_ids":["UUID"]}` и возвращает ZIP только для одобренных версий с проверенным целым кадром. Согласие на анализ не разрешает экспорт зарезервированных кадров.

## Связанный сценарий с mock-провайдером

После запуска локального тестового сервиса с подменённым provider transport (без настоящего ключа) можно последовательно выполнить приведённые запросы. `RUN_ID`, `INPUT_ID` и `SHA` берутся из фактического ответа, а `JPG` — путь к собственному синтетическому изображению. Идентификаторы не следует копировать из чужого анализа.

```sh
python3 - <<'PY'
from PIL import Image
Image.new('RGB', (64, 48), 'white').save('synthetic.png')
PY
python3 - <<'PY' > series.json
import base64, json
from pathlib import Path
image = base64.b64encode(Path('synthetic.png').read_bytes()).decode()
print(json.dumps({'intent':'observation_only','cloud_processing_consent':True,
 'scenario':'Mock smoke','observation_area':'Synthetic zone',
 'period':'2026-09-26T12:00:00+03:00','images_base64':[image,image],
 'requested_classes':['excavator','dump_truck']}))
PY
curl --fail-with-body -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: synthetic-series-001' --data-binary @series.json \
  http://127.0.0.1:8096/api/runs/series > accepted.json
RUN_ID=$(python3 -c 'import json; print(json.load(open("accepted.json"))["run_id"])')
curl --fail "http://127.0.0.1:8096/api/runs/$RUN_ID" > result.json
```

Повторяйте только `GET` до `state=succeeded` или `failed`; это polling, он не вызывает модель. `GET /runs?offset=0` возвращает историю, `GET /runs?project_id=UUID` — историю проекта.

```sh
curl --fail http://127.0.0.1:8096/api/runs?offset=0
python3 - <<'PY'
import json
r=json.load(open('result.json'))
print(json.dumps({'equipment':r['objects'],'assessment':r['ai_assessment'],
                  'evidence':r['ai_evidence']},ensure_ascii=False,indent=2))
PY
INPUT_ID=$(python3 -c 'import json; print(json.load(open("result.json"))["inputs"][0]["input_id"])')
ARTIFACT_ID=$(python3 -c 'import json; print(json.load(open("result.json"))["inputs"][0]["artifact_id"])')
curl --fail "http://127.0.0.1:8096/api/runs/$RUN_ID/artifacts/$ARTIFACT_ID" > evidence.png
curl --fail "http://127.0.0.1:8096/api/runs/$RUN_ID/frames/$INPUT_ID/annotations"
```

Для синтетического полностью пустого кадра можно предложить пустую исправленную разметку. Это ещё не одобрение и не включение в обучение:

```sh
python3 - <<'PY' > correction.json
import json
r=json.load(open('result.json'))
print(json.dumps({'input_sha256':r['inputs'][0]['sha256'],'objects':[]}))
PY
curl --fail-with-body -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: 14cb3dba-17ca-4d25-94b4-c16fc2e845a6' \
  --data-binary @correction.json \
  "http://127.0.0.1:8096/api/runs/$RUN_ID/frames/$INPUT_ID/annotations"
curl --fail-with-body -H 'Content-Type: application/json' \
  --data '{"stage":"preparation","comment":"Ручное подтверждение для синтетического smoke"}' \
  "http://127.0.0.1:8096/api/runs/$RUN_ID/confirm-stage"
```

Последний запрос сохраняет самостоятельное решение человека, не меняет оценку мультимодальной модели и не исправляет план. Для настоящего кадра пустая разметка допустима лишь после проверки, что все объекты действительно отсутствуют. Для свободной гипотезы человек должен явно выбрать класс и корректную рамку; экспорт без admin review запрещён.

## Hybrid fields and current quality

`GET /hybrid-readiness` is the current profile's quality report. `GET /readiness` remains historical and cannot qualify the new YOLO/«Мультимодальная модель» flow. The current report returns `status: "blocked"`; absent/stale evidence is never treated as zero errors.

For a hybrid run, `GET /runs/{id}` adds compatible evidence fields. Historical responses may omit these fields or contain empty arrays:

- `result_projection.hybrid_frames`: frame SHA/capture time, usability, class assessability, reconciled observations and separate `detectors.models` for APOCE/Kaggle.
- Each raw detection: `id`, `input_id`, `model_id`, `raw_class`, nullable `catalog_class`, `score` and normalized oriented-image `box`.
- `detection_dispositions`: one accepted/dismissed/unresolved reason per raw detection. Accepted associates a physical object; a corrected class may disagree with the raw label.
- `ai_assessment.activity`: `working_signs`, `possible_idle` or `insufficient_data`, with frame/observation references, visible grounds and uncertainty. A one-frame request cannot offer idle; unsupported missing/excluded-equipment causes are removed from the request schema before the provider call. Server validation remains mandatory.
- `ai_assessment.stage_hypotheses`: frame/observation references and an optional applicable work entry. An unknown stage may identify the work being checked without confirming its planned stage.
- `result_projection.created_signals`: persisted signal ID, state and cause. Same evidence can refer to an existing closed signal; processing does not reopen it.

Signals now permit `revision_id: null` for source-bound process/safety cases with a required zone. Plan risks still require a frozen revision and applicable work. Risk basis retains affected work, source frames/observations, impact, recommended check and limitations. Signal state/comment mutations continue through the existing `PATCH /signals/{id}` API; immutable evidence cannot be overwritten.

The [actual HTTP records](../evaluation/hybrid/results/) provide complete response examples, including failure/rejection evidence. [The demonstration manifest](../evaluation/hybrid/http-demonstration.json) identifies current successful cases and makes its simulated plan/time explicit.
