# Проверка перехода на мультимодальную модель — 2026-09-26

После разрешённого удаления устаревших тестов все **257 backend-проверок** выполнены успешно. Основной запуск дал **256 passed, 1 skipped** за 45.08 s; пропущенная проверка затем отдельно прошла на локальном архиве с проверкой SHA-256 (**1 passed**, 10.16 s). Платных вызовов моделей, обучения и выкатки на действующий сервер не было.

## Очистка набора и исправления

- Удалены сценарии реального допуска/исполнения DINO и Qwen и неиспользуемые заглушки этих исполнителей. Проверки исторических сравнений, отчётов, разрешений на данные и целостности доказательств сохранены.
- Сценарии HTTP-загрузки, идемпотентности, сохранения активной загрузки при recovery и повторов до первого вызова переведены на мультимодальную модель. Отдельная проверка гарантирует: `[A,B]` с тем же ключом возвращает тот же run, а `[B,A]` получает `409`.
- Каждый модуль получает собственные мигрированные PostgreSQL и приватный S3 bucket; очищаются только созданные тестом ресурсы. Это устраняет каскадные ошибки startup/reconciliation без удаления соответствующих проверок.
- Исторические fixtures выбирают четыре настоящих exclusion inventory; файл pixel fingerprints не считается отдельным inventory. Тест повреждённых меток теперь меняет копию данных, не общий `EVALUATION`.
- Перенос проверки lease обнаружил ошибку в актуальном исполнителе: lease могла истечь под блокировкой транзакции завершения. Финальный UPDATE теперь повторно проверяет состояние, владельца и срок lease; при отказе все записи успешного результата откатываются. Регрессия воспроизводит конфликт блокировки, истечение lease, rollback и сохранение исходных ответов модели.
- Независимое ревью удаления выявило потерю проверки порядка серии; эта проверка восстановлена до общего прогона. Blanket skip/xfail не добавлены.

В тестовом окружении нужны права на создание/удаление временных БД и buckets. `TEST_DATABASE_URL` и `TEST_S3_BUCKET` должны отличаться от рабочих. Проверка большого исходного архива запускается дополнительно с `EVALUATION_ARCHIVE_PATH`, указывающим на локальный файл; архив не скачивается и не отправляется модели.

Frontend не менялся в этой очистке; предыдущий полный результат **197 passed / 197** и production build остаются проверкой ревизии перехода `1264066`. Ниже сохранена история первоначальной приёмки.

## Первоначальная приёмочная регрессия (1264066)

Каждая группа запускалась с отдельными чистыми PostgreSQL и приватным MinIO; вызовы модели заменены детерминированными ответами.

| Группа | Результат |
| --- | --- |
| Мультимодальная модель: формат, consent, reservation, assessment, history, plan, errors, transport, proxy dispatch | 35 passed |
| Startup, lease/recovery, S3 publication/reconciliation | 48 passed |
| Исправления, одобрение и экспорт разметки | 5 passed |
| Контекст участка и сравнение с планом | 6 passed |
| Каталог, проекты, версии планов | 3 passed |
| Обратная связь и административные операции | 23 passed |
| Исторические объекты и EXIF-координаты | 5 passed |
| Сохранённые правила и их нормализация | 23 passed; один тест старого исполнения исключён из этой целевой группы |
| **Всего backend в приёмочных группах** | **148 passed** |
| **Frontend, полный набор** | **197 passed / 197** |

Frontend production build и `compileall` backend/Windows Python-скриптов прошли. `git diff --check` не сообщает ошибок.

Проверены невалидные JSON/model/reasoning/usage/status/координаты, отсутствие согласия на входе и в runtime, неизвестная техника и null box/score, неизменяемость raw и context, два наблюдения плюс один assessment, сохранение отклонённых ответов, запрет повторного вызова, истёкшая lease и отказ renewal. SQL-история ограничена тремя более ранними успешными анализами того же участка. Отдельная проверка привязала план A, создала B и подтвердила использование A в исходящем контексте и сохранённом сигнале.

Регрессия согласия проверяет смену черновика и появление нового кадра во время асинхронной проверки: старое согласие не разрешает отправку изменённого набора. Основания рисков читаемы и открывают конкретный кадр; uncertain явно обозначен.

## Интеграция и документация

- Backend/web-образы собираются через Podman. Используется доступный pinned MinIO из `infra/compose.yaml`; прежний Docker Hub tag развёртывания оказался недоступен и заменён тем же проверенным образом.
- Настоящие PostgreSQL и MinIO: подписанная запись проходит, анонимное чтение получает 403.
- Проверен переход **0021 → 0022** с синтетическим историческим профилем, проекцией, объектом и изображением: прежние поля и байты сохранились, новый reader возвращает `ai_assessment=null`.
- Настоящий HTTP-путь: нет consent → 400; одинаковый ключ → тот же run; queued/running/succeeded; отдельные frame calls + assessment; история; исправление разметки; подтверждение человеком.
- Headless через настоящий nginx: загрузка → consent → техника → этап/риски → читаемое основание → исходный кадр → подтверждение. Нет JavaScript-ошибок и горизонтального переполнения при ширине 390 px.
- Отдельно headless открыт синтетический результат, прочитанный после миграции: исходное фото и старый объект отображаются без блока AI-аналитики и без запуска новой обработки. Для этого UI-теста HTTP-ответ исторического run воспроизводился из сохранённого fixture.
- ReDoc и Swagger в headless-браузере действительно загрузили `/api/openapi.json`. HTML не подменён страницей frontend. Прямые `/docs`, `/redoc`, `/openapi.json` и proxy-варианты проверены; серия корректно маршрутизируется также с root_path.
- 39 операций OpenAPI и 326 встроенных примеров проверены JSON Schema; фактические ответы 10 маршрутов сверены со схемами. Локальные Markdown-ссылки проверены. Две Mermaid-схемы разобраны и отрисованы headless.
- Podman Compose 1.5.0 потребовал отдельного запуска графа тестовых контейнеров после успешного init; это особенность проверенной локальной среды. Docker CLI отсутствует, поэтому Docker Compose непосредственно не проверялся.
- Административный HTTP-доступ через контейнерный nginx закрыт `https_required`; loopback-исключение относится к прямому backend/dev-прокси. Это отражено в инструкции.

## Исторический общий прогон до очистки (1264066)

До очистки стандартный общий backend-прогон дал: **83 failed, 219 passed, 2 skipped**. Проверка исходного коммита `25ed8ccd5dfc1159b55f1d02bdf6e88613e769ff` в отдельной копии и чистом окружении дала **41 failed, 226 passed, 2 skipped**.

В прежнем наборе оставались ожидания исполнения/admission DINO и Qwen, старые callbacks, прежние сценарии сравнения и downgrade. Они противоречат явному выводу этих профилей из исполнения. Есть и предсуществующее расхождение corpus fixtures. Некоторые упавшие тесты оставляют намеренно незавершённые публикации в общей БД и вызывают каскадные ошибки: отдельный чистый startup-набор проходит все 48 проверок. Эти результаты не следует выдавать за зелёную общую регрессию.

Автоматическая проверка разрешений отклонила массовое удаление старых тестов. Удаление не выполнено; тесты сохранены, их fixtures и отдельные ожидания отказа обновлены точечно. После явного разрешения пользователя устаревшие тесты удалены, а актуальные сценарии перенесены и проверены. Прежнее ограничение закрыто.

## Не проверялось

- Точность мультимодальной модели, качество вывода о безопасности и фактический платный доступ к модели.
- Обучение, Windows/CUDA на RTX 3060 и YOLO inference на сервере.
- Развёртывание на действующем сервере.

Технический smoke не подтверждает ни точность модели, ни безопасность площадки.

## Исторический список ошибок до очистки

```text
FAILED tests/test_admission.py::test_incomplete_manifest_has_no_database_effect
FAILED tests/test_admission.py::test_failed_run_retains_reservation_and_rejects_draft
FAILED tests/test_admission.py::test_invocation_completion_requires_exact_identity_and_live_fence
FAILED tests/test_admission.py::test_offline_cpu_admission_publishes_and_authorizes
FAILED tests/test_admission.py::test_failure_retains_four_failed_runs_without_secret[observer]
FAILED tests/test_admission.py::test_failure_retains_four_failed_runs_without_secret[snapshot]
FAILED tests/test_admission.py::test_failure_retains_four_failed_runs_without_secret[decode]
FAILED tests/test_cloud_profile.py::test_admission_missing_gate_keeps_draft_and_sends_nothing
FAILED tests/test_cloud_profile.py::test_no_image_probe_failure_keeps_draft_and_sends_no_image
FAILED tests/test_cloud_profile.py::test_probe_or_key_scope_rejects_before_image[extra0-cloud_model_probe_invalid-1]
FAILED tests/test_cloud_profile.py::test_probe_or_key_scope_rejects_before_image[extra1-cloud_key_scope_invalid-0]
FAILED tests/test_cloud_profile.py::test_missing_held_out_authorization_keeps_draft_and_sends_nothing
FAILED tests/test_cloud_profile.py::test_extra_evidence_cannot_persist_credentials
FAILED tests/test_cloud_profile.py::test_admission_canary_reads_private_artifacts_and_enables_successor
FAILED tests/test_cloud_profile.py::test_failed_canary_stays_draft_without_fallback[response0-False-observer_timeout]
FAILED tests/test_cloud_profile.py::test_failed_canary_stays_draft_without_fallback[response1-False-observation_normalization_failed]
FAILED tests/test_cloud_profile.py::test_failed_canary_stays_draft_without_fallback[response2-False-observation_normalization_failed]
FAILED tests/test_cloud_profile.py::test_failed_canary_stays_draft_without_fallback[None-True-artifact_integrity_failed]
FAILED tests/test_comparison_campaign.py::test_criterion_report_matrix_and_literal_populations
FAILED tests/test_comparison_campaign.py::test_latest_provider_comparison_reads_frozen_cells_without_mutation
FAILED tests/test_comparison_campaign.py::test_changed_request_gets_distinct_revision_without_rewriting_prior
FAILED tests/test_comparison_campaign.py::test_expired_cloud_evidence_is_rejected_by_real_gate
FAILED tests/test_comparison_campaign.py::test_downgrade_refuses_planned_campaign_and_keeps_evidence
FAILED tests/test_comparison_campaign.py::test_real_admitted_pair_freezes_complete_campaign
FAILED tests/test_comparison_campaign.py::test_real_cloud_scope_missing_frame_rejected
FAILED tests/test_comparison_campaign.py::test_successful_freeze_campaign_cli_uses_real_admission
FAILED tests/test_comparison_campaign.py::test_complete_execution_keeps_every_cell_and_distinct_inputs[False]
FAILED tests/test_comparison_campaign.py::test_complete_execution_keeps_every_cell_and_distinct_inputs[True]
FAILED tests/test_comparison_campaign.py::test_archive_late_member_mismatch_uploads_nothing
FAILED tests/test_comparison_campaign.py::test_comparison_claim_and_success_require_complete_evidence
FAILED tests/test_comparison_campaign.py::test_comparison_claim_rejects_partial_multiframe_fixture
FAILED tests/test_comparison_campaign.py::test_completed_invocation_is_immutable_while_campaign_still_running
FAILED tests/test_comparison_campaign.py::test_reserved_call_recovers_as_failed_without_reusing_cell
FAILED tests/test_comparison_campaign.py::test_revocation_before_publication_sends_no_bytes
FAILED tests/test_comparison_campaign.py::test_reserved_call_finishes_after_authorization_revocation[0]
FAILED tests/test_comparison_campaign.py::test_reserved_call_finishes_after_authorization_revocation[1]
FAILED tests/test_comparison_campaign.py::test_ordinary_maintenance_ignores_running_campaign_and_pending_input
FAILED tests/test_comparison_campaign.py::test_executor_session_loss_cannot_overlap_reserved_call[False]
FAILED tests/test_comparison_campaign.py::test_executor_session_loss_cannot_overlap_reserved_call[True]
FAILED tests/test_comparison_campaign.py::test_execute_cli_missing_archive_is_safe_json
FAILED tests/test_comparison_campaign.py::test_runtime_identity_drift_rejects_frozen_campaign_before_upload[adapter]
FAILED tests/test_comparison_campaign.py::test_runtime_identity_drift_rejects_frozen_campaign_before_upload[lock]
FAILED tests/test_comparison_campaign.py::test_runtime_identity_drift_rejects_frozen_campaign_before_upload[snapshot]
FAILED tests/test_comparison_campaign.py::test_authorization_change_during_preparation_is_attributable[state = 'revoked'-profile_unauthorized]
FAILED tests/test_comparison_campaign.py::test_authorization_change_during_preparation_is_attributable[revision = revision + 1-authorization_revision_changed]
FAILED tests/test_comparison_campaign.py::test_empty_execution_downgrade_restores_planned_guard
FAILED tests/test_comparison_campaign.py::test_partial_input_publication_failure_quarantines_only_unattached_intent
FAILED tests/test_comparison_campaign.py::test_renewal_failure_stops_later_calls_and_evidence[provider]
FAILED tests/test_comparison_campaign.py::test_renewal_failure_stops_later_calls_and_evidence[native_upload]
FAILED tests/test_comparison_campaign.py::test_provider_cancellation_drains_before_releasing_execution_lock
FAILED tests/test_evaluation_set.py::test_valid_freeze_evidence_and_missing_archive_stays_closed
FAILED tests/test_ordered_series.py::test_stage_summary_separates_projection_and_newer_lifecycle
FAILED tests/test_ordered_series.py::test_failed_retry_is_linear_and_keeps_source[single]
FAILED tests/test_ordered_series.py::test_failed_retry_is_linear_and_keeps_source[series]
FAILED tests/test_ordered_series.py::test_ordered_series_http_postgres_s3 - A...
FAILED tests/test_rule_intent.py::test_rule_intent_survives_publication_execution_and_readback
FAILED tests/test_single_image.py::test_runtime_recovery_preserves_active_submission[single-pre-claim]
FAILED tests/test_single_image.py::test_runtime_recovery_preserves_active_submission[single-post-execution]
FAILED tests/test_single_image.py::test_runtime_recovery_preserves_active_submission[series-pre-claim]
FAILED tests/test_single_image.py::test_runtime_recovery_preserves_active_submission[series-post-execution]
FAILED tests/test_single_image.py::test_http_submission_and_guarded_execution
FAILED tests/test_single_image.py::test_admitted_profile_http_background_cpu
FAILED tests/test_single_image.py::test_expired_lease_fences_completion_during_recovery
FAILED tests/test_startup.py::test_database_head_smoke_and_reconciliation - a...
FAILED tests/test_startup.py::test_reconciliation_quarantines_interrupted_states_without_touching_bytes
FAILED tests/test_startup.py::test_startup_reconciliation_fails_interrupted_submission
FAILED tests/test_startup.py::test_reconciliation_integrity_failure_blocks_gate[missing-object_published-startup]
FAILED tests/test_startup.py::test_reconciliation_integrity_failure_blocks_gate[missing-object_published-runtime]
FAILED tests/test_startup.py::test_reconciliation_integrity_failure_blocks_gate[mismatched-object_published-startup]
FAILED tests/test_startup.py::test_reconciliation_integrity_failure_blocks_gate[mismatched-object_published-runtime]
FAILED tests/test_startup.py::test_reconciliation_integrity_failure_blocks_gate[mismatched-content_verified-startup]
FAILED tests/test_startup.py::test_reconciliation_integrity_failure_blocks_gate[mismatched-content_verified-runtime]
FAILED tests/test_startup.py::test_reconciliation_integrity_failure_blocks_gate[unattributed-object_published-startup]
FAILED tests/test_startup.py::test_reconciliation_integrity_failure_blocks_gate[unattributed-object_published-runtime]
FAILED tests/test_startup.py::test_reconciliation_rejects_wrong_temporary_creator
FAILED tests/test_startup.py::test_reconciliation_s3_outage_blocks_readiness
FAILED tests/test_startup.py::test_duplicate_content_keeps_first_creator - ap...
FAILED tests/test_startup.py::test_reconciliation_attaches_verified_deduplicated_reference
FAILED tests/test_startup.py::test_reconciliation_preserves_live_owner_before_recovery
FAILED tests/test_startup.py::test_startup_reconciles_lease_that_expires_after_first_pass
FAILED tests/test_startup.py::test_idle_claim_loop_recovers_later_expiry - as...
FAILED tests/test_startup.py::test_process_death_during_reserved_provider_call
FAILED tests/test_startup.py::test_ready_health - assert False
```
