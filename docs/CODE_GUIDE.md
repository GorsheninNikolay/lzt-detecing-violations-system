# Путеводитель по коду

| Задача | Модуль | Сущности и API | Проверки |
| --- | --- | --- | --- |
| Запуск, готовность, HTTP-лимиты | [main.py](../backend/app/main.py), [config.py](../backend/app/config.py) | `/health/*`, `/runs/*` | [test_startup.py](../backend/tests/test_startup.py) |
| Согласие, декодирование и защита повторных запросов | [submission.py](../backend/app/application/submission.py) | `submission_requests`, `run_inputs`, `publication_intents` | [test_deepseek.py](../backend/tests/test_deepseek.py) |
| Мультимодальная модель, строгие схемы, EXIF | [deepseek.py](../backend/app/profiles/deepseek.py), [cloud.py](../backend/app/shared/cloud.py) | наблюдения и общий разбор | [test_deepseek.py](../backend/tests/test_deepseek.py) |
| Исполнение, резервации и история | [deepseek_runtime.py](../backend/app/application/deepseek_runtime.py), [executor.py](../backend/app/application/executor.py) | `deepseek_calls`, `deepseek_results`, lease | [test_deepseek.py](../backend/tests/test_deepseek.py) |
| Хранилище, история, старые результаты | [postgres.py](../backend/app/adapters/postgres.py), [artifacts.py](../backend/app/adapters/artifacts.py) | `analysis_runs`, `observer_profiles`, `result_projections`, `artifact_metadata` | [test_single_image.py](../backend/tests/test_single_image.py) |
| Каталог, проекты, план | [site.py](../backend/app/application/site.py) | `/catalog/works`, `/projects`, `/zones/{id}/plan` | [test_site_workflow_db.py](../backend/tests/test_site_workflow_db.py) |
| Сигналы и подтверждение человека | [signals.py](../backend/app/application/signals.py) | `/signals`, `/runs/{id}/confirm-stage` | [test_site_analysis.py](../backend/tests/test_site_analysis.py) |
| Исправления и экспорт | [annotations.py](../backend/app/application/annotations.py) | `annotation_proposals`, `annotation_versions`, `/admin/annotations/export` | [test_annotations.py](../backend/tests/test_annotations.py) |
| Обратная связь и владелец | [engagement.py](../backend/app/application/engagement.py), [admin_password.py](../backend/app/application/admin_password.py) | `/feedback`, `/admin/*`, `/analytics/events` | [test_engagement.py](../backend/tests/test_engagement.py) |
| Русская документация API | [api_docs.py](../backend/app/api_docs.py) | `/redoc`, `/docs`, `/openapi.json` | схемы генерируются из зарегистрированных маршрутов |
| Интерфейс | [App.tsx](../web/src/App.tsx), [AiAssessment.tsx](../web/src/AiAssessment.tsx), [EvidenceViewer.tsx](../web/src/EvidenceViewer.tsx), [Annotations.tsx](../web/src/Annotations.tsx) | согласие, свободные объекты, основания выводов, ручная проверка | [App.test.tsx](../web/src/App.test.tsx), [EvidenceViewer.test.tsx](../web/src/EvidenceViewer.test.tsx) |
| Развёртывание | [compose.yaml](../infra/deploy/compose.yaml), [init.py](../infra/deploy/init.py), [nginx.conf](../infra/deploy/nginx.conf) | миграции, каталог, приватный S3, proxy prefix | локальная Compose/config/build проверка |

[Миграция 0022](../backend/migrations/versions/0022_deepseek.py) добавляет записи ответов нового адаптера и допускает null в score/box; предыдущие миграции не переписываются. Исторические модули профилей сохранены ради форматов и аудита, но новые анализы через них запрещены. JSON с исходным ответом хранится в PostgreSQL, исходные изображения хранятся в S3 с хешем содержимого. Ни один сырой ответ не содержит ключа API.

[API-примеры](API_EXAMPLES.md), [архитектура](../Architecture.md), [Обучение на Windows](../training/windows/README.md).

Живая документация локального Compose: [ReDoc](http://127.0.0.1:8096/api/redoc). `API_ROOT_PATH=/api` задаётся в Compose, а прямые `/redoc`, `/docs`, `/openapi.json` сохраняются.

## Потоки данных

1. Запуск. Compose `init.py` применяет миграции и импортирует XLSX. Затем `main.lifespan` проверяет последнюю миграцию, чтение/запись PostgreSQL, приватность S3, незавершённые публикации и истёкшие права исполнителя (lease). Только после этого проверка готовности возвращает true и начинается `ClaimLoop`.
2. Загрузка. HTTP-обработчик ограничивает размер до разбора JSON. `submission.validate_images` проверяет согласие, JPEG/PNG, контекст и защищённые наборы. Байты публикуются через `publication_intents` с SHA-256. Транзакция связывает неизменяемый контекст, профиль, порядок кадров и `Idempotency-Key`; модель внутри HTTP-запроса не вызывается.
3. Анализ. `deepseek_runtime.reserve` фиксирует уникальный вызов до отправки. `DeepSeek.call` ориентирует изображение и проверяет ответ. `save_result` сохраняет исходный и нормализованный JSON без возможности UPDATE/DELETE. После кадров `freeze_context` выбирает привязанный план и ограниченную историю; выполняется один аналитический вызов.
4. Завершение и ошибки. Успешный `complete` одной транзакцией сохраняет объекты, состояния классов, сигналы плана и проекцию. Неопределённый или невалидный вызов оставляет доказательства, но не создаёт успешную проекцию. Каждый переход проверяет владельца и срок права исполнителя; автоматического повтора нет.
5. История и основания. `GET /runs` возвращает страницу истории; `GET /runs/{id}` читает снимки и доказательства в согласованной транзакции. Старые анализы не обязаны иметь `ai_assessment`. Файловый маршрут получает метаданные только для указанного анализа и повторно проверяет байты S3 по хешу.
6. Исправления. Предложение разметки сохраняет исходные объекты и новую версию. Администратор отдельно проверяет весь кадр, сопоставляет классы и одобряет версию. Экспорт принимает только такие версии и повторно исключает зарезервированные источники. Исходный ответ модели не редактируется; подтверждение этапа также хранится отдельно.

Фактические результаты проверок и история очистки устаревшего набора: [DEEPSEEK_VERIFICATION.md](DEEPSEEK_VERIFICATION.md).
