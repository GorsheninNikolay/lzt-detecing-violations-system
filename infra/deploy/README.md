# Локальная Compose-сборка

Актуальный порядок установки, окружение, профиль и ограничения: [корневой README](../../README.md). Compose содержит PostgreSQL, приватный MinIO, одноразовый init, backend и web/nginx. Наружу опубликован только web-порт. `init` применяет миграции, создаёт бакет и подготавливает каталог XLSX.

Сначала соберите frontend: `npm --prefix web ci && npm --prefix web run build`. Затем из корня: `docker compose -f infra/deploy/compose.yaml build` и `docker compose -f infra/deploy/compose.yaml up -d`. Нужны `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`, `DEPLOY_PORT`. Реальные секреты передаются через окружение. Для анализа нужны отдельные `YANDEX_AI_STUDIO_API_KEY`, `YANDEX_CLOUD_FOLDER_ID`, `OBSERVER_PROFILE_ID`; создание профиля — `evidence-profile`, без платного probe.

`/api/` проксируется с удалением префикса и `X-Forwarded-Prefix: /api`. Документация: `/api/redoc`, `/api/docs`, `/api/openapi.json`. Прямые URL backend работают без префикса. S3 не публикуется; анонимное чтение запрещено. Не удаляйте persistent volumes. DINO/Qwen admission и local-model runtime выведены из активного пути.

Исключение HTTPS для loopback относится к прямому backend. В стандартном Compose nginx обращается из контейнерной сети: вход администратора по HTTP возвращает `403 https_required`, даже если web открыт через localhost. Для административного интерфейса через прокси нужен HTTPS и явно настроенное доверие к своему TLS-прокси; доверие ко всем входящим forwarded-заголовкам не включено.
