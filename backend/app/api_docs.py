"""Russian OpenAPI metadata for endpoints that parse size-limited request bodies manually."""
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.routing import APIRoute
from app.application.annotations import CLASSES


def field(kind, description, **extra):
    return {'type': kind, 'description': description, **extra}


def obj(properties, required=()):
    return {'type': 'object', 'properties': properties, 'required': list(required)}


UUID = field('string', 'Идентификатор UUID.', format='uuid')
TEXT = field('string', 'Текст на русском языке.')
TIME = field('string', 'Время ISO 8601 с обязательным часовым смещением.', format='date-time')
BOX = field('array', 'Рамка на ориентированном по EXIF изображении: x1,y1,x2,y2 от 0 до 1.',
            minItems=4, maxItems=4, items={'type': 'number', 'minimum': 0, 'maximum': 1})
CORRECTION = obj({'id': UUID, 'class_name': field('string', 'Явное сопоставление человеком с одним из восьми классов.', enum=list(CLASSES)), 'box': BOX}, ('id','class_name','box'))
OBJECTS = field('array', 'Исправленные человеком объекты; свободные гипотезы требуют явного сопоставления.', items=CORRECTION, maxItems=300)
SUBMISSION = obj({
    'intent': field('string', 'Новый анализ наблюдений и контекста.', enum=['observation_only']),
    'cloud_processing_consent': field('boolean', 'Явное согласие отправить эти фотографии и контекст в Yandex AI Studio. Без true облачных вызовов нет.', const=True),
    'scenario': field('string', 'Цель наблюдения.', minLength=1, maxLength=256),
    'observation_area': field('string', 'Название участка наблюдения.', minLength=1, maxLength=256),
    'period': TIME, 'stage': field('string', 'Заданный пользователем контекст, не вывод модели.', enum=['excavation','other']),
    'stage_id': field('string', 'Исторический алиас stage=excavation; не должен противоречить stage.', enum=['excavation']),
    'requested_classes': field('array', 'Уникальные идентификаторы классов (Python isidentifier); неподдержанные помечаются not_analyzed.', items={'type':'string','minLength':1,'maxLength':64}, minItems=1, maxItems=32, uniqueItems=True),
    'project_id': UUID, 'zone_id': UUID, 'plan_revision_id': UUID,
    'capture_times': field('array', 'Время каждого кадра в порядке загрузки. Для истории нужны участок и надёжные возрастающие времена.', items=TIME),
}, ('intent','cloud_processing_consent','scenario','observation_area','period'))
SUBMISSION['dependentRequired'] = {key:[other for other in ('project_id','zone_id','capture_times') if other != key]
                                   for key in ('project_id','zone_id','capture_times','plan_revision_id')}
ENTRY = obj({'catalog_work_id': UUID, 'start_at': TIME, 'end_at': TIME,
             'state': field('string','Состояние работы.',enum=['planned','active','completed']),
             'stage_key': field(['string','null'],'Этап: excavation, concreting, roadwork или null.'),
             **{name: field('array', desc, items={'type':'string'}) for name,desc in (
                 ('expected_equipment','Ожидаемая техника.'),('allowed_equipment','Допустимая техника.'),('excluded_equipment','Явно исключённая техника.'))}}, ('catalog_work_id','start_at','end_at'))
BODIES = {
    'create_project': obj({'name': field('string','Непустое название проекта.',minLength=1,maxLength=200),'timezone':field('string','Часовой пояс IANA.',example='Europe/Moscow')}, ('name','timezone')),
    'create_zone': obj({'name':field('string','Непустое имя, уникальное в проекте.',minLength=1,maxLength=200)},('name',)),
    'replace_zone_plan': obj({'expected_revision':field('integer','Текущая ревизия; 0 для первого плана.',minimum=0), 'entries':field('array','Работы новой неизменяемой ревизии.',items=ENTRY)},('expected_revision','entries')),
    'update_signal': obj({'state':field('string','Статус ручного разбора.',enum=['new','in_progress','closed']),'comment':TEXT},('state',)),
    'confirm_stage': obj({'stage':field('string','Подтверждённый человеком этап.',enum=['preparation','demolition','excavation','concreting','installation','roadwork','utilities','landscaping']),'comment':TEXT},('stage',)),
    'login': obj({'login':field('string','Логин владельца.',example='gorshenin-nik'),'password':field('string','Пароль владельца. Не журналируется.',format='password')},('login','password')),
    'change_password': obj({'current_password':field('string','Текущий пароль.',format='password'),'new_password':field('string','Новый пароль, 8–1024 символа.',format='password',minLength=8,maxLength=1024,example='Synthetic-Example-Only-123')},('current_password','new_password')),
    'submit_feedback': obj({'category':field('string','Категория обратной связи.',enum=['problem','idea','praise','other']),'message':field('string','Сообщение, до 5000 символов.',maxLength=5000),'context':obj({'pathname':TEXT,'project_id':UUID,'analysis_id':UUID}), 'attachments':field('array','До пяти изображений, каждое до 5 МБ, вместе до 15 МБ.',items=obj({'data':field('string','Изображение JPEG/PNG/WEBP в base64.')}),maxItems=5)},('category','message')),
    'analytics_event': obj({'browser_id':UUID,'event_id':UUID,'kind':field('string','Анонимное событие.',enum=['visit','wizard_started','wizard_completed','wizard_skipped'])},('browser_id','event_id','kind')),
    'propose': obj({'input_sha256':field('string','SHA-256 исходного кадра. Изменение источника даёт 409.'),'objects':OBJECTS},('input_sha256','objects')),
    'review': obj({'expected_revision':field('integer','Ревизия, которую проверяет администратор.'),'objects':OBJECTS,'status':field('string','Решение.',enum=['pending','approved','rejected']), 'whole_frame_verified':field('boolean','Проверен весь кадр; обязательно true для approved.'),'reason':TEXT},('expected_revision','objects','status','whole_frame_verified')),
    'export': obj({'version_ids':field('array','Одобренные версии с проверенным кадром. Зарезервированные источники для оценки качества исключены.',items=UUID,minItems=1,maxItems=32)},('version_ids',)),
}
SUMMARIES = {
    'live':'Проверить работоспособность процесса', 'ready':'Проверить готовность БД, S3 и исполнителя',
    'analysis_choices':'Доступные сценарии анализа', 'submit_single_image':'Загрузить кадры и создать анализ',
    'stage_summary':'Сводка этапов', 'read_readiness':'Исторический отчёт готовности',
    'read_hybrid_readiness':'Качество текущего гибридного профиля: несовпавший или отсутствующий отчёт блокирует готовность',
    'read_provider_comparison':'Историческое сравнение выведенных из исполнения моделей',
    'read_run':'Прочитать анализ, исходные данные и неизменяемую аналитику', 'list_runs':'История анализов',
    'retry_run':'Явный повтор допустимого сбоя до первого облачного вызова', 'read_run_artifact':'Прочитать проверенный по SHA-256 артефакт',
    'list_catalog':'Каталог строительных работ', 'create_project':'Создать проект', 'list_projects':'Список проектов',
    'create_zone':'Создать участок проекта', 'list_zones':'Участки проекта', 'replace_zone_plan':'Сохранить новую ревизию плана',
    'read_zone_plan':'Прочитать ревизию плана участка', 'list_signals':'Список сигналов для ручной проверки',
    'update_signal':'Изменить статус разбора сигнала', 'confirm_stage':'Отдельно подтвердить этап человеком',
    'login':'Войти в кабинет владельца', 'session_info':'Получить сессию и CSRF-токен', 'logout':'Завершить сессию',
    'change_password':'Сменить пароль и завершить все сессии', 'submit_feedback':'Отправить обратную связь',
    'feedback_list':'Очередь обратной связи', 'feedback_detail':'Открыть обращение', 'feedback_attachment':'Получить вложение обращения',
    'analytics_event':'Зарегистрировать анонимное событие', 'overview':'Сводка активности',
    'frame_annotations':'Прочитать исходную разметку кадра', 'propose':'Предложить исправление разметки',
    'queue':'Очередь исправлений', 'annotation_detail':'Прочитать версии исправления', 'review':'Проверить исправление',
    'export':'Экспортировать одобренные версии в YOLO/COCO', 'thumbnail':'Миниатюра ориентированного кадра',
}



def array(items, description):
    return field('array', description, items=items)


COUNT = field('integer', 'Количество.', minimum=0)
NULL_UUID = {**UUID, 'type': ['string', 'null']}
PROJECT = obj({'id':UUID,'name':field('string','Название проекта.'),'timezone':field('string','Часовой пояс IANA.')}, ('id','name','timezone'))
ZONE = obj({'id':UUID,'project_id':UUID,'name':field('string','Название участка.')}, ('id','name'))
RISK = obj({'category':field('string','Категория риска для проверки.',enum=['process','plan','safety']),
            'text':field('string','Возможный риск, не подтверждённое нарушение.'),
            'frame_ids':array(UUID,'Ссылки на текущие кадры.'),
            'observation_ids':array(TEXT,'Ссылки на видимые объекты или признаки сцены этих кадров.')},
           ('category','text','frame_ids','observation_ids'))
ASSESSMENT = obj({'summary':field('string','Итог наблюдения.'),
                 'stage_hypothesis':obj({'stage':field('string','Гипотеза этапа; unknown/ambiguous при недостаточности.'),'reason':field('string','Видимое основание гипотезы.')},('stage','reason')),
                 'risks':array(RISK,'Риски с проверенными ссылками.'),
                 'recommendations':array(TEXT,'Действия для человека.'),
                 'limitations':array(TEXT,'Ограничения вывода, включая отсутствие плана.')},
                 ('summary','stage_hypothesis','risks','recommendations','limitations'))
from app.profiles.hybrid import ASSESSMENT_SCHEMA as HYBRID_ASSESSMENT_SCHEMA
ASSESSMENT['properties'].update({key: value for key, value in HYBRID_ASSESSMENT_SCHEMA['properties'].items()
                                 if key in ('activity', 'stage_hypotheses')})
RISK['properties'].update({key: value for key, value in HYBRID_ASSESSMENT_SCHEMA['properties']['risks']['items']['properties'].items()
                           if key not in RISK['properties']})
INPUT = obj({'input_id':UUID,'ordinal':field('integer','Порядок кадра, начиная с 0.'),'sha256':field('string','SHA-256 исходных байтов.'),'artifact_id':NULL_UUID,'size':COUNT,'media_type':TEXT}, ('input_id','ordinal','sha256','artifact_id'))
OBSERVATION = obj({'input_id':UUID,'class_name':TEXT,'state':field('string','Результат проверки присутствия; необнаружение не доказывает отсутствие на площадке.',enum=['detected','not_detected_in_frame','insufficient_data','not_analyzed']), 'source_artifact_id':NULL_UUID,'invocation_id':NULL_UUID,'reason':field(['string','null'],'Причина ограничения.')})
DETECTION = obj({'id':UUID,'input_id':UUID,'invocation_id':UUID,'class_name':field('string','Один из восьми классов либо unknown.'),'score':field(['number','null'],'Оценка провайдера, если предоставлена; мультимодальная модель не придумывает число.',minimum=0,maximum=1),
                 'box':{'anyOf':[BOX,{'type':'null'}],'description':'Рамка или null при отсутствии локализации.'},
                 'image_size':array(COUNT,'Ширина и высота ориентированного изображения.'),
                 'details':{'anyOf':[obj({'type_ru':field('string','Свободное название по-русски.'),'type_en':TEXT,'catalog_class':field(['string','null'],'Явное соответствие фиксированному каталогу.'),'status':TEXT,'evidence':field('string','Видимое основание.'),'missing_localization_reason':field(['string','null'],'Почему рамка отсутствует.')}),{'type':'null'}]}})
EVIDENCE = obj({'id':UUID,'kind':field('string','Тип вызова.',enum=['frame','assessment']),'input_id':NULL_UUID,
                'state':field('string','completed, invalid или uncertain. Любая резервация запрещает replay.',enum=['completed','invalid','uncertain']),
                'context':field('object','Неизменяемый контекст вызова: кадры, их порядок/время, план и история.'),
                'result':{'anyOf':[obj({'model':field(['string','null'],'Идентичность провайдера; null если отсутствует или имеет неверный тип.'),'value':field(['object','null'],'Проверенный ответ; null для invalid.'),'valid':field('boolean','Прошёл ли ответ строгую проверку.'),'raw':field('object','Точный исходный ответ, в том числе невалидный.'),'usage':{'anyOf':[obj({'input_tokens':COUNT,'output_tokens':COUNT,'total_tokens':COUNT}),{'type':'null'}],'description':'Проверенный usage, null для invalid. Исходное значение остаётся в raw.'},'instruction_version':TEXT,'schema_version':TEXT}),{'type':'null'}]}})
RUN = obj({'run_id':UUID,'state':field('string','Состояние запуска.',enum=['queued','running','succeeded','failed']),
           'purpose':TEXT,'error_code':field(['string','null'],'Безопасный код ошибки.'),'created_at':{**TIME,'type':['string','null']},
           'cloud_processing_consent':field('boolean','Согласие, сохранённое в неизменяемой записи анализа.'),'profile_id':NULL_UUID,
           'context':field(['object','null'],'Исходный пользовательский контекст.'),
           'ai_assessment':{'anyOf':[ASSESSMENT,{'type':'null'}],'description':'null для исторических и незавершённых запусков.'},
           'ai_evidence':array(EVIDENCE,'Неизменяемые ответы и резервации.'), 'inputs':array(INPUT,'Исходные кадры.'),
           'objects':array(DETECTION,'Свободные и каталогизированные объекты.'),'observations':array(OBSERVATION,'Состояния запрошенных классов.'),
           'result_projection':field(['object','null'],'Успешная проекция. hybrid_frames сохраняет manifest, обе модели YOLO с raw_class, catalog_class (nullable), score, box, SHA-256 весов и кадра; created_signals содержит идентификаторы сохранённых сигналов; rule_results содержит сравнение каждого кадра с точной ревизией.'),
           'stage_confirmation':field(['object','null'],'Отдельное подтверждение человеком.'),'retry_eligible':field('boolean','Допустим ли явный повтор до первого вызова.')}, ('run_id','state'))
ANNOTATION = obj({'id':UUID,'run_id':UUID,'input_id':UUID,'input_sha256':TEXT,'artifact_id':UUID,'version_id':UUID,
                  'revision':COUNT,'status':TEXT,'objects':OBJECTS,'original_objects':array(DETECTION,'Неизменяемая исходная гипотеза, включая unknown/null box.'),'whole_frame_verified':field('boolean','Проверен весь кадр.'),'reason':TEXT})
FEEDBACK = obj({'id':UUID,'category':TEXT,'message':TEXT,'context':field('object','Связанный экран/проект/анализ.'),'created_at':TIME,'read_at':{**TIME,'type':['string','null']},'attachments':array(obj({'id':UUID,'media_type':TEXT,'size':COUNT}),'Вложения обращения.')})
RESPONSES = {
    'live':obj({'live':field('boolean','Процесс отвечает.')},('live',)),
    'ready':obj({'ready':field('boolean','Стартовые проверки завершены.'),'code':TEXT},('ready','code')),
    'analysis_choices':obj({'stages':array(obj({'id':TEXT,'label':TEXT,'rule':field(['object','null'],'Историческое правило; для новых запусков null.')}),'Доступные сценарии.')}),
    'submit_single_image':obj({'run_id':UUID,'state':TEXT,'code':TEXT}), 'retry_run':obj({'run_id':UUID},('run_id',)),
    'read_run':RUN,'list_runs':obj({'runs':array(RUN,'Страница истории.'),'total':COUNT,'next_offset':field(['integer','null'],'Следующее смещение или null.')}),
    'stage_summary':obj({'stages':array(obj({'stage_id':TEXT,'name':TEXT,'supported':field('boolean','Поддержка исторического сценария.'),'latest_result':field(['object','null'],'Последняя сохранённая проекция.'),'latest_lifecycle':field(['object','null'],'Более новый незавершённый запуск.')}),'Сводка этапов.')}),
    'read_readiness':obj({'schema_revision':TEXT,'campaign_id':UUID,'status':TEXT,'sections':field('object','Разделы исторической оценки; структура определяется schema_revision.')}),
    'read_hybrid_readiness':obj({'status':field('string','Текущая готовность.',enum=['blocked','pass']),'code':TEXT,'profile_sha256':TEXT,'detector_manifest_sha256':TEXT,'blocking_reasons':array(TEXT,'Непройденные или отсутствующие доказательства.')}),
    'read_provider_comparison':obj({'campaign':obj({'id':UUID,'revision_number':COUNT,'evaluation_revision_id':UUID}),'candidates':array(field('object','Снимок исторического кандидата.'),'Сравниваемые профили.'),'cells':array(field('object','Измерения ячейки исторической кампании.'),'Сохранённые измерения.')}),
    'list_catalog':obj({'source_sha256':TEXT,'total':COUNT,'works':array(obj({'id':UUID,'source_row':COUNT,'title':TEXT,'code':field(['string','null'],'Исходный код работы.'),'raw_code':{},'applicability':field('object','Ограничения визуальной применимости.')}),'Работы исходного каталога.')}),
    'create_project':obj({**PROJECT['properties'],'default_zone_id':field('string','UUID автоматически созданного основного участка.',format='uuid')},(*PROJECT['required'],'default_zone_id')),'list_projects':obj({'projects':array(PROJECT,'Проекты.')}),
    'create_zone':ZONE,'list_zones':obj({'zones':array(ZONE,'Участки проекта.')}),
    'replace_zone_plan':obj({'revision_id':UUID,'revision_number':COUNT,'entry_count':COUNT}),
    'read_zone_plan':obj({'zone_id':UUID,'revision_id':UUID,'revision_number':COUNT,'created_at':TIME,'entries':array(obj({'id':UUID,'catalog_work_id':UUID,'starts_at':TIME,'ends_at':TIME,'state':TEXT,'stage_key':field(['string','null'],'Этап плана.')}),'Работы сохранённой ревизии.')}),
    'list_signals':obj({'new_count':COUNT,'summary':obj({'open_count':COUNT,'attention_count':COUNT,'insufficient_data_count':COUNT}),'signals':array(obj({'id':UUID,'run_id':NULL_UUID,'zone_id':UUID,'revision_id':NULL_UUID,'kind':TEXT,'state':TEXT,'basis':field('object','Неизменяемое основание сигнала.'),'comment':TEXT,'created_at':TIME}),'Сигналы ручного разбора.')}),
    'update_signal':obj({'id':UUID,'state':TEXT,'comment':TEXT}),'confirm_stage':obj({'run_id':UUID,'stage':TEXT,'comment':TEXT}),
    'login':obj({'csrf':field('string','CSRF-токен текущей сессии.')},('csrf',)),
    'session_info':obj({'csrf':field('string','CSRF-токен текущей сессии.')},('csrf',)),
    **{name:obj({'ok':field('boolean','Операция завершена.')},('ok',)) for name in ('logout','change_password','analytics_event')},
    'submit_feedback':obj({'id':UUID,'message':TEXT}), 'feedback_list':obj({'feedback':array(FEEDBACK,'Обращения.'),'next_offset':field(['integer','null'],'Следующая страница.')}), 'feedback_detail':FEEDBACK,
    'overview':obj({'period':TEXT,'collection_started_at':TIME,'cards':field('object','Счётчики визитов, запусков, проектов и отзывов.'),'daily':array(field('object','Счётчики за день.'),'Дневная статистика.'),'projects':array(field('object','Активность проекта.'),'Проекты.'),'funnel':field('object','Последовательность действий.'),'wizard':field('object','Счётчики знакомства с сервисом.')}),
    'frame_annotations':obj({'run_id':UUID,'input_id':UUID,'input_sha256':TEXT,'objects':array(DETECTION,'Исходные объекты.'),'classes':array(TEXT,'Восемь классов для явного сопоставления.')}),
    'propose':obj({'id':UUID,'status':TEXT}), 'queue':obj({'annotations':array(ANNOTATION,'Очередь версий.'),'next_offset':field(['integer','null'],'Следующая страница.')}),
    'annotation_detail':ANNOTATION,'review':obj({'id':UUID,'version_id':UUID,'revision':COUNT,'status':TEXT}),
}


def example(schema):
    if 'example' in schema:
        return schema['example']
    if 'const' in schema:
        return schema['const']
    if 'enum' in schema:
        return schema['enum'][0]
    kind = schema.get('type')
    if isinstance(kind, list):
        return None if 'null' in kind else ''
    if kind == 'object':
        return {name:example(value) for name,value in schema['properties'].items() if name in schema.get('required', ())}
    if kind == 'array':
        return [example(schema['items']) for _ in range(schema.get('minItems', 0))]
    if kind == 'boolean':
        return False
    if kind in ('number','integer'):
        return schema.get('minimum', 1)
    if schema.get('format') == 'uuid':
        return '00000000-0000-4000-8000-000000000001'
    if schema.get('format') == 'date-time':
        return '2026-09-26T12:00:00+03:00'
    if schema.get('contentEncoding') == 'base64':
        return 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC'
    return 'Пример'

def install(app):
    @app.get('/docs', include_in_schema=False)
    def swagger():
        return get_swagger_ui_html(openapi_url='./openapi.json', title='Контроль строительства: API')

    @app.get('/redoc', include_in_schema=False)
    def redoc():
        return get_redoc_html(openapi_url='./openapi.json', title='Контроль строительства: API')

    def schema():
        if app.openapi_schema:
            return app.openapi_schema
        value = get_openapi(title='Контроль строительства', version='1.0.0', routes=app.routes,
            description='Фотографии → наблюдения мультимодальной модели → аналитика → отдельная проверка человеком. '
            'Исторические данные доступны без новой аналитики (ai_assessment=null). '
            'Публичные операции не требуют входа. Административные операции требуют сессии, HTTPS (кроме loopback), Origin и CSRF.')
        value['servers'] = [{'url':app.root_path or '/', 'description':'Настроенный root_path'}]
        if app.root_path:
            value['servers'].append({'url':'/','description':'Прямой backend'})
        value.setdefault('components', {})['securitySchemes'] = {'AdminSession': {'type':'apiKey','in':'cookie','name':'owner_session','description':'HttpOnly cookie после /admin/login.'}}
        def endpoints(routes):
            for route in routes:
                if hasattr(route, 'original_router'):
                    yield from endpoints(route.original_router.routes)
                else:
                    yield route
        for route in endpoints(app.routes):
            if not isinstance(route, APIRoute) or not route.include_in_schema:
                continue
            path = value['paths'][route.path]
            for method in route.methods:
                operation = path[method.lower()]
                name = route.endpoint.__name__
                summary = SUMMARIES.get(name, 'Операция сервиса')
                group = ('Администрирование' if route.path.startswith('/admin') else
                         'Разметка' if 'annotations' in route.path else 'Проекты и планы' if route.path.startswith(('/projects','/zones','/catalog')) else
                         'Сигналы' if 'signals' in route.path or 'confirm-stage' in route.path else
                         'Обратная связь' if route.path == '/feedback' else 'Активность' if '/analytics' in route.path else
                         'Состояние и архив' if route.path.startswith(('/health','/readiness','/provider','/stages')) else 'Анализы')
                operation.update(summary=summary, description=summary + '.', tags=[group])
                body_limit = {'login':8192,'change_password':8192,'submit_feedback':20_100_000,
                              'analytics_event':2048,'propose':150_000,'review':150_000,'export':8192}.get(name)
                if body_limit:
                    operation['description'] += f' Максимальный размер HTTP-тела: {body_limit} байт; превышение возвращает 413.'
                parameters = operation.setdefault('parameters', [])
                for parameter in parameters:
                    parameter.setdefault('description', 'Идентификатор ресурса.' if parameter['in']=='path' else 'Фильтр или смещение страницы результатов.')
                if route.path.startswith('/admin') and name != 'login':
                    operation['security'] = [{'AdminSession':[]}]
                if route.path.startswith('/admin') and method != 'GET':
                    for header, description in [('Origin','Точный origin запроса.'),('X-CSRF-Token','Токен из ответа входа или сессии; не нужен для login.')]:
                        parameters.append({'in':'header','name':header,'required':header=='Origin' or name!='login','schema':{'type':'string'},'description':description})
                if name in ('submit_single_image','submit_feedback','propose','review','create_project'):
                    parameters.append({'in':'header','name':'Idempotency-Key','required':name != 'create_project','schema':{'type':'string'},'description':'Новый уникальный ключ операции; при потере ответа повторите тот же ключ и тело. Для feedback/annotations нужен UUID.'})
                if method in ('POST','PUT','PATCH'):
                    parameters.append({'in':'header','name':'X-Browser-Id','required':False,'schema':{'type':'string','format':'uuid'},'description':'Анонимный идентификатор браузера для атрибуции.'})
                body = BODIES.get(name)
                if name == 'submit_single_image':
                    body = {**SUBMISSION, 'properties':dict(SUBMISSION['properties']), 'required':list(SUBMISSION['required'])}
                    key = 'images_base64' if route.path.endswith('/series') else 'image_base64'
                    image = field('string','Полные байты JPEG/PNG в base64, до 16 МБ после декодирования, до 40 Мп.',contentEncoding='base64')
                    body['properties'][key] = field('array','От 2 до 8 кадров в фиксированном порядке.',items=image,minItems=2,maxItems=8) if key=='images_base64' else image
                    body['required'].append(key)
                    operation['description'] += ' Требуется cloud_processing_consent=true. Лимит HTTP: 25 100 000 байт для одного кадра, 200 000 000 для серии. Выведенные из исполнения профили и зарезервированные контрольные примеры запрещены.'
                if body:
                    operation['requestBody'] = {'required':True,'content':{'application/json':{'schema':body,'example':example(body)}}}
                errors = {'400':('Некорректные данные.','invalid_request'),'401':('Требуется сессия.','authentication_required'),
                          '403':('Неверный Origin/CSRF или транспорт.','invalid_csrf'),'404':('Ресурс не найден.','run_not_found'),
                          '409':('Конфликт неизменяемого состояния.','idempotency_key_conflict'),'413':('Слишком большое тело.','request_too_large'),
                          '429':('Превышен лимит частоты.','too_many_requests'),'503':('Сервис недоступен.','service_not_ready')}
                for code, (description, error) in errors.items():
                    key = 'detail' if route.path.startswith('/admin') or name in ('propose','frame_annotations','submit_feedback','analytics_event') else 'code'
                    operation['responses'][code] = {'description':description,'content':{'application/json':{'schema':obj({key:TEXT},(key,)), 'example':{key:error}}}}
                if name in ('login','change_password','submit_feedback','analytics_event','propose','export'):
                    operation['responses']['429']['headers'] = {'Retry-After':{'description':'Число секунд до следующей попытки.','schema':{'type':'integer','minimum':0}}}
                success = '202' if name in ('submit_single_image','retry_run') else '201' if name in ('create_project','create_zone') else '200'
                operation['responses'].pop('200', None)
                operation['responses'][success] = {'description':'Операция принята в очередь.' if success=='202' else summary + '.', 'content':{'application/json':{'schema':RESPONSES.get(name, {'type':'object'})}}}
                if name in ('read_run_artifact','thumbnail','feedback_attachment','export'):
                    media_types = {'export':['application/zip'],'thumbnail':['image/jpeg'],
                                   'read_run_artifact':['image/jpeg','image/png','application/json'],
                                   'feedback_attachment':['image/jpeg','image/png','image/webp']}[name]
                    operation['responses']['200'] = {'description':'Проверенный файл; для export возвращается ZIP с YOLO/COCO.',
                        'content':{media:{'schema':{'type':'string','format':'binary'}} for media in media_types}}
                if name == 'ready':
                    operation['responses']['503'] = {'description':'Стартовая проверка не завершена; code объясняет причину.',
                        'content':{'application/json':{'schema':RESPONSES['ready'],'example':{'ready':False,'code':'startup_pending'}}}}
        app.openapi_schema = value
        return value
    app.openapi = schema
