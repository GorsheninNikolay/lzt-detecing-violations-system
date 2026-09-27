"""Build evidence-bound Russian presentation and technical PDFs from local facts."""

from io import BytesIO
import hashlib
import json
from pathlib import Path
import statistics
from zipfile import ZipFile

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf"
FONT_DIR = Path("/System/Library/Fonts/Supplemental")
FONT_PAIRS = [
    (FONT_DIR / "Arial.ttf", FONT_DIR / "Arial Bold.ttf"),
    (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    (Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf")),
]
fonts = next((pair for pair in FONT_PAIRS if all(path.is_file() for path in pair)), None)
if fonts is None:
    raise FileNotFoundError("Cyrillic Arial or DejaVuSans regular/bold system fonts are required")
pdfmetrics.registerFont(TTFont("RU", str(fonts[0])))
pdfmetrics.registerFont(TTFont("RUB", str(fonts[1])))
INK = HexColor("#17313F")
MUTED = HexColor("#566A75")
BLUE = HexColor("#216D83")
PALE = HexColor("#EAF2F3")
ORANGE = HexColor("#DB6D3C")
BG = HexColor("#F8F8F4")
WHITE = HexColor("#FFFFFF")
RULE = HexColor("#D4DFE0")
DATE = "Проверки: 27.09.2026; тексты: 28.09.2026"
SLIDES = 12
NOTES = 12


def read_json(path):
    return json.loads((ROOT / path).read_text())


MANIFEST = read_json("docs/pdf-inputs/yolo-manifest-2026-09-27.json")
SMOKE = read_json("evaluation/hybrid/yolo-smoke-summary.json")
QUEUE = read_json("evaluation/hybrid/control-review-queue.json")
BUDGET = read_json("evaluation/hybrid/budget.json")
VERIFICATION_PATH = ROOT / "docs/HYBRID_VERIFICATION.json"
if not VERIFICATION_PATH.exists():
    raise FileNotFoundError("Final docs/HYBRID_VERIFICATION.json is required before PDF authoring")
VERIFICATION = json.loads(VERIFICATION_PATH.read_text())
current_manifest_sha = hashlib.sha256(json.dumps(MANIFEST, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
if VERIFICATION.get("container_build", {}).get("profile_check", {}).get("detector_manifest_sha256") != current_manifest_sha:
    raise ValueError("PDF verification belongs to different weights; preserve historical PDFs and obtain a new verified report")
for field in ("pdf_checks_summary", "pdf_http_summary", "local_url", "paid"):
    if field not in VERIFICATION:
        raise ValueError(f"Final verification report is missing {field}")
WARM_MS = statistics.median(sum(m["latency_ms"] for m in f["models"]) for f in SMOKE["frames"][1:])


def wrap(value, width, size, font="RU"):
    result = []
    value = str(value).translate(str.maketrans({char: "-" for char in "\u2010\u2011\u2013\u2014"}))
    for paragraph in value.split("\n"):
        current = ""
        for word in paragraph.split():
            if pdfmetrics.stringWidth(word, font, size) > width:
                parts = []
                part = ""
                for char in word:
                    if part and pdfmetrics.stringWidth(part + char, font, size) > width:
                        parts.append(part)
                        part = ""
                    part += char
                parts.append(part)
            else:
                parts = [word]
            for part in parts:
                candidate = f"{current} {part}".strip()
                if current and pdfmetrics.stringWidth(candidate, font, size) > width:
                    result.append(current)
                    current = part
                else:
                    current = candidate
        result.append(current)
    return result


def text(c, value, x, top, width, size=15, leading=None, color=INK, bold=False, floor=None):
    font = "RUB" if bold else "RU"
    leading = leading or size * 1.35
    items = wrap(value, width, size, font)
    bottom = top - (len(items) - 1) * leading
    if floor is not None and bottom < floor:
        raise ValueError(f"Text overflows: {value[:70]} ({bottom:.1f} < {floor})")
    c.setFillColor(color)
    c.setFont(font, size)
    for line in items:
        c.drawString(x, top, line)
        top -= leading
    return top


def photo(c, name, x, y, width, height):
    member = "Строительная_техника/" + name
    expected = next(i["sha256"] for i in QUEUE["images"] if i["archive_member"] == member)
    with ZipFile(ROOT / "artifacts/dataset/Строительная_техника.zip") as archive:
        data = archive.read(member)
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"Original image hash changed: {name}")
    c.setFillColor(PALE)
    c.rect(x, y, width, height, stroke=0, fill=1)
    c.drawImage(ImageReader(BytesIO(data)), x, y, width, height, preserveAspectRatio=True, anchor="c")


def box(c, x, y, w, h, heading, body, size=15, accent=BLUE):
    c.setFillColor(WHITE)
    c.rect(x, y, w, h, fill=1, stroke=0)
    c.setFillColor(accent)
    c.rect(x, y + h - 4, w, 4, fill=1, stroke=0)
    title_bottom = text(c, heading, x + 17, y + h - 31, w - 34, 17, 22, bold=True)
    text(c, body, x + 17, title_bottom - 12, w - 34, size, size * 1.38, floor=y + 15)


def band(c, value, y=74, color=PALE, size=14):
    c.setFillColor(color)
    c.rect(44, y, 872, 48, fill=1, stroke=0)
    text(c, value, 59, y + 29, 842, size, size * 1.3, floor=y + 9)


def slide(c, number, title, subtitle):
    c.setFillColor(BG)
    c.rect(0, 0, 960, 540, fill=1, stroke=0)
    c.setFillColor(ORANGE)
    c.rect(44, 493, 36, 4, fill=1, stroke=0)
    text(c, title, 44, 457, 872, 29, 36, bold=True, floor=435)
    text(c, subtitle, 44, 415, 872, 14, 19, color=MUTED, floor=395)
    c.setStrokeColor(RULE)
    c.line(44, 47, 916, 47)
    text(c, f"Контроль строительства  /  гибридный прототип  /  {DATE}", 44, 29, 790, 9, color=MUTED)
    text(c, f"{number:02d} / {SLIDES}", 865, 29, 51, 9, color=MUTED)


def section(c, title, body, y, size=11.3, floor=67):
    y = text(c, title, 42, y, 511, 15, 20, bold=True) - 4
    return text(c, body, 42, y, 511, size, size * 1.43, floor=floor) - 17


def note(c, number, title, subtitle):
    c.setFillColor(BG)
    c.rect(0, 0, 595, 842, fill=1, stroke=0)
    c.setFillColor(ORANGE)
    c.rect(42, 787, 36, 4, fill=1, stroke=0)
    text(c, title, 42, 754, 511, 23, 29, bold=True, floor=716)
    text(c, subtitle, 42, 711, 511, 10.5, 15, color=MUTED, floor=684)
    c.setStrokeColor(RULE)
    c.line(42, 48, 553, 48)
    text(c, f"Гибридный анализ фотографий  /  {DATE}", 42, 31, 445, 8.5, color=MUTED)
    text(c, f"{number:02d} / {NOTES}", 510, 31, 45, 8.5, color=MUTED)
    return 661


def table(c, rows, x, top, widths, size=10.5, header=True, floor=65, padding=16):
    y = top
    for i, row in enumerate(rows):
        font = "RUB" if i == 0 and header else "RU"
        wrapped = [wrap(v, w - 16, size, font) for v, w in zip(row, widths)]
        height = max(len(v) for v in wrapped) * size * 1.35 + padding
        if y - height < floor:
            raise ValueError(f"Table overflows at row {i}: {row}")
        c.setFillColor(INK if i == 0 and header else WHITE if i % 2 else PALE)
        c.rect(x, y - height, sum(widths), height, fill=1, stroke=0)
        cursor = x
        for value, width in zip(row, widths):
            text(c, value, cursor + 8, y - size - padding / 2 + 2, width - 16, size, size * 1.35,
                 color=WHITE if i == 0 and header else INK, bold=i == 0 and header)
            cursor += width
        y -= height
    return y - 20


def checks_text():
    return VERIFICATION["pdf_checks_summary"]


def paid_text():
    paid = VERIFICATION["paid"]
    calls = paid["calls"]
    cost = paid["actual_estimate_rub"]
    return f"{calls} платных вызовов; оценка по токенам {cost:.4f} руб. / лимит {BUDGET['limit_rub']} руб."


def http_text(detail=False):
    value = VERIFICATION["pdf_http_summary"]
    if detail and not VERIFICATION["http"]["identical_ai_stage_risk_live_repeat_verified"]:
        value += " Одинаковые риски модели в живом повторе не подтверждены; изменённые ссылки проверены отдельным тестом с БД."
    return value


def container_text():
    container = VERIFICATION["container_build"]
    final_digest = container["final_image"]["Digest"].removeprefix("sha256:")[:12]
    earlier_digest = container["cpu_measurement_image"]["Digest"].removeprefix("sha256:")[:12]
    profile = container["profile_check"]["profile_sha256"][:12]
    return (f"Финальный Linux ARM64-образ: {final_digest}…; профиль {profile}… проверен. "
            f"CPU-замер относится к {earlier_digest}… . Инференс на финальном образе не повторялся; "
            "детектор, веса и зависимости не менялись.")


def presentation():
    path = OUT / "construction-monitoring-hybrid-presentation.pdf"
    c = canvas.Canvas(str(path), pagesize=(960, 540))
    c.setTitle("Контроль строительства: гибридный анализ фотографий")
    c.setAuthor("Construction monitoring project")

    slide(c, 1, "От фотографии к проверяемому сигналу", "Контроль строительства  /  локальный CPU + Мультимодальная модель (Yandex AI Studio)  /  прототип")
    photo(c, "Screenshot_48.png", 464, 143, 452, 234)
    text(c, "Увидеть технику.\nСопоставить с работами.\nОбъяснить повод для проверки.", 44, 351, 388, 26, 36, bold=True)
    text(c, "Два YOLO сохраняют свои детекции; мультимодальная модель согласует объекты и анализирует фото с планом. Человек принимает решение.",
         44, 204, 388, 15, 22, floor=135)
    text(c, "Исходное фото организаторов: Screenshot_48.png", 464, 128, 452, 10, color=MUTED)
    band(c, "Качество пока BLOCKED: есть пропуски и путаница классов; достоверных серий простоя нет.", 66, size=14)
    c.showPage()

    slide(c, 2, "Архитектура: факты сохраняются на каждом шаге", "Оригиналы в приватном S3; контекст, вызовы, наблюдения и сигналы в PostgreSQL")
    for x, heading, body in [
        (44, "01  Фото и согласие", "Проект, участок, порядок и время кадров; хеш оригинала."),
        (342, "02  Два YOLO / CPU", "Ориентированные пиксели, классы, рамки, score и версия весов."),
        (640, "03  Мультимодальная модель / кадр", "Фото + обе детекции; один физический объект и разногласия."),
    ]:
        box(c, x, 244, 276, 138, heading, body, 13.5)
    for x, heading, body in [
        (44, "04  Контекст", "Точная ревизия плана, правила, до трёх прежних результатов участка."),
        (342, "05  Анализ серии", "Фотографии, признаки активности, гипотезы работ, риски и ограничения."),
        (640, "06  Публикация", "Проверка; сигналы и результат в одной транзакции с проверкой прав исполнителя."),
    ]:
        box(c, x, 86, 276, 138, heading, body, 13.5, ORANGE if x == 640 else BLUE)
    c.showPage()

    slide(c, 3, "Модели: независимые источники наблюдений", "Выбор задан поставленными весами; качество проверяется отдельно от запуска")
    box(c, 44, 167, 276, 214, "APOCE  /  7 классов", "apoce.pt\nSHA-256: db4447329776…\nБульдозер, миксер, самосвал, экскаватор; lifting-equipment, piling-machine и tower-crane остаются без каталожного типа.", 13.5)
    box(c, 342, 167, 276, 214, "Kaggle  /  17 классов", "kaggle.pt\nSHA-256: 0e86af081bd7…\nВосемь классов сопоставлены с каталогом. Погрузчики, трейлер и другие неподдержанные имена сохраняются под исходным классом.", 13.5)
    box(c, 640, 167, 276, 214, "Мультимодальная модель", "Yandex AI Studio\nlatest; temperature 0\nreasoning none; store=false\nСогласование объектов, признаки сцены и анализ плана. Версия latest у провайдера может меняться; исходный ответ сохраняется.", 13.5, ORANGE)
    band(c, "Манифест фиксирует полные хеши, сопоставления и версии. APOCE lifting-equipment ≠ автоматический автокран.")
    c.showPage()

    slide(c, 4, "План сравнивается с каждым кадром", "Каталог работ не создаёт календарный план; выбранная ревизия неизменяема для запуска")
    table(c, [
        ["Иллюстрация: план", "08:00", "09:00", "10:00"],
        ["A  Земляные работы / 08:00-10:00", "применим", "применим", "применим"],
        ["B  Бетонные работы / 09:00-11:00", "нет", "применим", "применим"],
    ], 44, 373, [431, 147, 147, 147], 14, floor=226)
    box(c, 44, 130, 425, 124, "Необнаруженная ожидаемая техника", "Нужны ≥3 независимых оцениваемых кадра именно этой работы. Дубли хеша не добавляют доказательств.", 13.5)
    box(c, 491, 130, 425, 124, "Одновременные операции", "Разрешение класса любой активной работой подавляет сигнал явного исключения. Границы времени включаются.", 13.5)
    band(c, "План выше служит синтетическим примером метода. Фото архива не имеют подтверждённого расписания.", 69, size=13.5)
    c.showPage()

    slide(c, 5, "Присутствие машины не доказывает работу", "Активность отделена от класса техники и всегда связана с исходными кадрами")
    photo(c, "Screenshot_48.png", 44, 224, 276, 157)
    photo(c, "Screenshot_60.png", 342, 224, 276, 157)
    photo(c, "Screenshot_24.png", 640, 224, 276, 157)
    text(c, "working_signs", 44, 198, 276, 17, bold=True)
    text(c, "Видимый перенос/падение грунта: признак действия в этот момент, без оценки выработки.", 44, 168, 276, 14, 20, floor=99)
    text(c, "insufficient_data", 342, 198, 276, 17, bold=True)
    text(c, "Каток и подготовленный грунт видны. Активное уплотнение или простой по позе не установлены.", 342, 168, 276, 14, 20, floor=99)
    text(c, "Простой не подтверждён", 640, 198, 276, 17, bold=True)
    text(c, "possible_idle требует независимой серии с временем, сопоставимым обзором и нерабочими признаками. Одно фото крана такой серии не даёт.", 640, 168, 276, 14, 20, floor=82)
    c.showPage()

    slide(c, 6, "Демонстрация на реальном оригинале", "Screenshot_48.png  /  техническая проверка полного локального пути")
    photo(c, "Screenshot_48.png", 44, 123, 494, 257)
    text(c, "Что показали два YOLO", 563, 360, 353, 18, bold=True)
    text(c, "APOCE: 1 excavator\nKaggle: 1 Excavator\nНа фото несколько машин: подсчёт не подтверждён.", 563, 326, 353, 14.5, 22)
    text(c, "Что проверено через HTTP", 563, 235, 353, 18, bold=True)
    text(c, http_text(), 563, 204, 353, 13, 18, floor=72)
    text(c, "Оригинал из архива; это не снимок интерфейса. Время на изображении не подтверждено метаданными.", 44, 91, 494, 11, 16, color=MUTED)
    c.showPage()

    slide(c, 7, "Наблюдаемые ошибки сохраняются для оценки", "Оба детектора обработали 15 исходных PNG; результаты не подтверждают качество")
    for x, name, heading, body in [
        (44, "Screenshot_60.png", "60  /  каток", "APOCE: 5 excavator\nKaggle: Trailer\nНи один результат не описал видимый каток верно."),
        (342, "Screenshot_24.png", "24  /  автокран", "Оба YOLO: 0 детекций.\nВидимый колёсный кран пропущен; исходные результаты сохранены."),
        (640, "Screenshot_99.png", "99  /  машины и грунт", "APOCE: 0 детекций\nKaggle: Trailer + Mixer\nКлючевые экскаваторы и самосвал пропущены."),
    ]:
        photo(c, name, x, 221, 276, 159)
        text(c, heading, x, 195, 276, 18, bold=True)
        text(c, body, x, 164, 276, 14, 20, floor=73)
    c.showPage()

    slide(c, 8, "Сигнал имеет основание и жизненный цикл", "Основание связывает причины, фото, наблюдения, работу и зафиксированный план")
    box(c, 44, 180, 276, 200, "Проверить перед публикацией", "Ссылки на текущие кадры; пригодный обзор; основания оценки активности; применимость работы. Плановый риск требует плана; для процессного нужен участок.", 13.5)
    box(c, 342, 180, 276, 200, "Дедупликация оснований", "Fingerprint: участок, ревизия, причина, работа и исходные доказательства. Без сгенерированного текста и run ID. Повтор не открывает закрытый сигнал.", 13.5)
    box(c, 640, 180, 276, 200, "Решение человека", "new → in_progress → closed\nКомментарии и подтверждение этапа хранятся отдельно. Новый спокойный анализ не закрывает старые сигналы автоматически.", 13.5, ORANGE)
    band(c, "До каждого облачного запроса сохраняется резервация. Неопределённый исход не повторяется автоматически.")
    c.showPage()

    slide(c, 9, "Контрольный набор пока не даёт допуск", "Подборка и агентская проверка готовят разметку; человек её ещё не принял")
    for x, value, label in [(44, "100", "оригиналов в архиве"), (267, "15", "кадров в очереди"), (490, "14 / 36", "просмотрено / примерных рамок"), (713, "6 / 8", "классов в агентской подборке")]:
        text(c, value, x, 362, 203, 35, bold=True, color=BLUE)
        text(c, label, x, 314, 203, 12.5, 17, color=MUTED)
    table(c, [["Необходимое покрытие", "Фактический пробел"],
              ["Земляные / бетонные / дорожные × normal / risk / ambiguous / unusable", "Нет аутентичных планов и согласованных normal/risk меток"],
              ["8 классов + работа / простой / плохой обзор", "Нет бульдозера, крана-манипулятора и реальных серий простоя с проверенным временем"]],
          44, 259, [448, 424], 13.5, floor=100)
    text(c, "Точность классов, рамок, этапов и сигналов не измерена по принятой эталонной разметке. Readiness: BLOCKED.", 44, 83, 872, 13, 18, bold=True)
    c.showPage()

    slide(c, 10, "Камеры: обеспечить сравнимое наблюдение", "Рекомендации к сбору данных; фактический монтаж камер здесь не подтверждается")
    box(c, 44, 168, 276, 211, "Зона операции", "Стабильный обзор машины и конструкции. Отдельно покрыть места погрузки, бетонирования и уплотнения; проверить размер и перекрытия объектов.", 14)
    box(c, 342, 168, 276, 211, "Въезд + внутренние зоны", "Второй ракурс для движения техники и слепых участков. В помещении/тоннеле нужна отдельная камера; общий обзор не доказывает отсутствие внутри.", 14)
    box(c, 640, 168, 276, 211, "Время и сопоставимость", "Синхронные часы, camera_id, неизменный ракурс и известный интервал. Сохранять реальные времена, исходные файлы и события смены камеры.", 14, ORANGE)
    band(c, "Проверить день/ночь, осадки, пыль и закрытый обзор. Частоту съёмки выбрать по пилоту; универсальная норма не задана.")
    c.showPage()

    slide(c, 11, "Локальный запуск и масштабирование", "Текущая поставка локальная; сервер и комплект обучения для Windows/RTX не обновлялись")
    box(c, 44, 173, 425, 207, "Воспроизводимый стек", "Python 3.13.15 + uv; Node/npm; PostgreSQL; приватный S3.\nmake up собирает Compose. Веса read-only; startup проверяет хеши и классы. Облачный ключ передаётся только через окружение.", 14)
    box(c, 491, 173, 425, 207, "Измерять перед расширением", f"CPU smoke: загрузка {SMOKE['load_ms']/1000:.2f} с; прогретая медиана пары {WARM_MS:.1f} мс, 14 кадров. Это не целевой benchmark.\nСначала измерить очередь, память, p95 и затраты; затем добавлять worker-процессы с отдельным lease.", 14)
    band(c, "Успешный запуск из N кадров = N согласований фото + 1 assessment; стоимость зависит от фото и объёма ответа.")
    c.showPage()

    slide(c, 12, "Проверенное состояние и следующий допуск", "Проверки от 27.09.2026 и прежние веса; текущие веса требуют отдельной проверки")
    box(c, 44, 188, 425, 192, "Фактические проверки", checks_text(), 13.5)
    box(c, 491, 188, 425, 192, "Качество: BLOCKED", "Нужна человеческая разметка восьми классов; реальные normal/risk сцены; независимый split по площадке/камере; сопоставимые серии работы и простоя; измерения ложных сигналов.", 13.5, ORANGE)
    text(c, paid_text(), 44, 154, 872, 15, bold=True)
    text(c, f"Локально: {VERIFICATION.get('local_url', 'http://127.0.0.1:58159')}. В этой поставке сервер не обновлялся; GUI-приёмка не выполнялась.", 44, 122, 872, 13.5, 20)
    text(c, "Источники: Architecture.md; HYBRID_PHOTO_SIGNALS.md; manifest; evaluation/hybrid; HYBRID_VERIFICATION.json.", 44, 79, 872, 10.5, 15, color=MUTED)
    c.save()
    return path


def accompanying():
    path = OUT / "construction-monitoring-hybrid-accompanying.pdf"
    c = canvas.Canvas(str(path), pagesize=(595, 842))
    c.setTitle("Гибридный анализ фотографий: техническое сопровождение")
    c.setAuthor("Construction monitoring project")

    y = note(c, 1, "Техническое сопровождение", "Гибридный анализ фотографий: оба YOLO → Мультимодальная модель → проверяемые сигналы")
    y = section(c, "Назначение и граница результата", "Сервис связывает видимые объекты с работами участка и формирует гипотезы, риски и рекомендации для менеджера. Наблюдение, правило и решение человека хранятся отдельно. Система не устанавливает юридическое нарушение, непрерывную выработку или фактический процент готовности по одному снимку.", y)
    photo(c, "Screenshot_48.png", 42, 294, 511, 244)
    text(c, "Оригинал Screenshot_48.png из архива организаторов; без изменения байтов. Дата поверх фото не считается подтверждённым capture time.", 42, 277, 511, 9.5, 14, color=MUTED)
    section(c, "Проверенное техническое состояние", checks_text(), 229, 11, floor=156)
    section(c, "Отдельный статус качества: BLOCKED", "Подборка содержит агентские кандидаты разметки, без принятия эталонной разметки человеком. Есть серьёзные ошибки обоих детекторов, отсутствуют два класса и реальные сопоставимые серии простоя. Технический успех не снимает ограничения.", 132, 10.8)
    c.showPage()

    y = note(c, 2, "Архитектура и модель данных", "Исходные фото неизменны; каждый анализ связан с точным профилем и контекстом")
    y = table(c, [["Сущности", "Назначение"],
        ["project → zone → plan revision", "Участок и неизменяемый снимок параллельных работ; каталог не создаёт план"],
        ["analysis_runs / run_inputs / run_plan_bindings", "Профиль, порядок, время, SHA-256 кадров, согласие и точная ревизия"],
        ["observer_profiles / manifest", "Модель, версии и хеши схемы/инструкции, классы и настройки YOLO"],
        ["deepseek_calls / deepseek_results", "Резервация до отправки; исходный ответ, токены, задержка, нормализованные данные"],
        ["result_projections / project signals", "Совместная публикация результата и сигналов; неизменяемое основание"],
        ["annotation_versions / stage confirmation", "Отдельные решения человека, версии исправлений и одобренный экспорт"]],
        42, y, [230, 281], 10.6)
    y = section(c, "Где хранятся факты", "Приватный S3 хранит исходные байты и метаданные артефактов. PostgreSQL хранит анализы, контекст и JSON доказательств. Чтение изображения повторно проверяет SHA-256. Новые данные добавляются миграциями; старые результаты остаются читаемыми без повторного анализа.", y)
    section(c, "Исполняемый путь", "FastAPI принимает загрузку без вызова провайдера внутри HTTP-запроса. ClaimLoop получает lease; оба YOLO работают на CPU; по каждому кадру сохраняется резервация и вызывается мультимодальная модель. Затем фиксируются план, правила и до трёх прошлых успешных результатов того же участка, выполняется один общий анализ с фотографиями серии.", y)
    c.showPage()

    y = note(c, 3, "Модели и происхождение классов", "Снимок проверенных весов: docs/pdf-inputs/yolo-manifest-2026-09-27.json")
    for model in MANIFEST["models"]:
        y = section(c, f"{model['id']} / {model['filename']} / {len(model['classes'])} исходных классов", f"SHA-256: {model['sha256']}", y, 10)
    y = section(c, "Настройки инференса", "ultralytics 8.4.163; torch 2.10.0; torchvision 0.25.0. EXIF-oriented RGB; device=cpu; imgsz=640; conf=0.25; iou=0.7; max_det=100; half=false; augment=false. Startup сверяет байты весов и исходный список классов, модели загружаются один раз и делят lock. Отдельные сырые результаты сохраняют model/frame identity.", y)
    y = table(c, [["APOCE: исходное имя", "Каталог"],
        *[[name, value or "null / исходное имя сохраняется"] for name, value in MANIFEST["models"][0]["mapping"].items()]],
        42, y, [241, 270], 10.5)
    section(c, "Смысл выбора", "Два предоставленных checkpoint дают независимые гипотезы объектов. Мультимодальная модель получает оба набора и само фото. Их согласование не превращает ошибочные детекции в эталонную разметку. lifting-equipment, piling-machine и tower-crane не сопоставляются автоматически с автокраном.", y)
    c.showPage()

    y = note(c, 4, "Kaggle: явное отображение классов", "17 исходных имён сохраняются дословно; неподдержанное имя не расширяет каталог")
    y = table(c, [["Исходный класс Kaggle", "Каталог / raw-only"],
        *[[name, value or "null"] for name, value in MANIFEST["models"][1]["mapping"].items()]],
        42, y, [251, 260], 10.5, padding=10)
    section(c, "Каталог сервиса: восемь классов", "dump_truck, excavator, road_roller, truck_mounted_crane, concrete_mixer_truck, bulldozer, truck, mobile_crane. В текущей независимой подборке уверенные кандидаты есть только для шести классов. Бульдозер и кран-манипулятор не покрыты подтверждёнными примерами.", y, 10.8)
    c.showPage()

    y = note(c, 5, "Наблюдения и проверка ответа", "Рамки относятся к ориентированному изображению, а не к произвольной копии кадра")
    y = section(c, "Нормализация входа", "JPEG/PNG декодируются с EXIF-ориентацией. Исходный файл остаётся неизменным. Координаты YOLO переводятся в normalized xyxy; сохраняются source class, nullable catalog mapping, score, frame ID, detector ID и checkpoint SHA-256. Отсутствующим box/confidence модели не присваиваются искусственные значения.", y)
    y = section(c, "Согласование физического объекта", "Мультимодальная модель получает само фото и результаты обоих детекторов. Для каждой исходной детекции нужно решение accepted/dismissed/unresolved. Одна исходная детекция не может принадлежать двум согласованным объектам. Разногласия и непринятые детекции сохраняются; unresolved класс не даёт отрицательного доказательства.", y)
    y = section(c, "Независимые признаки достаточности", "Пригодность кадра и возможность оценить класс не выводятся из количества детекций. Неоцениваемый ракурс, неясная идентичность и повторные SHA-256 не доказывают отсутствие техники. Объекты вне восьми классов остаются свободными именами. Фотографии и ссылки текущего анализа проверяются до публикации.", y)
    y = section(c, "Облачный профиль и контекст", "Профиль hybrid-photo-signals-v1 совместим с kind=deepseek и имеет отдельные хеши схемы, инструкции и manifest. Используется deepseek-v4.1-flash/latest, reasoning=none, temperature=0, max output=8192, store=false. Фактический URI, сведения об использовании, полный исходный ответ и причина отклонения сохраняются. Версия latest у провайдера не гарантирует постоянство весов.", y)
    section(c, "Публикационные проверки", "Сервер проверяет JSON-контракт, ссылки на кадры, наблюдения и детекции, пригодность доказательств, признаки активности и связь работы с зафиксированным планом. Неподкреплённые утверждения о длительности/динамике запрещены во всех публикуемых текстовых полях. Невалидный ответ сохраняется для проверки, но не становится успешным результатом или сигналом.", y)
    c.showPage()

    y = note(c, 6, "План, активность и основания рисков", "Применимость определяется отдельно по времени каждого кадра и каждой операции")
    y = section(c, "Неизменяемая привязка", "При наличии плана участка сравнение включено по умолчанию; интерфейс показывает выбранную ревизию и позволяет отказаться. Run читает run_plan_bindings.revision_id, а не будущую текущую версию. Время входит в интервал работы включительно; одновременные операции оцениваются независимо.", y)
    y = table(c, [["Правило", "Минимальное основание"],
        ["Ожидаемая техника не обнаружена", "Явное ожидание активной работы; ≥3 независимых пригодных для оценки кадра именно этой работы"],
        ["Техника явно исключена", "Класс исключён всеми применимыми параллельными работами; разрешение одной подавляет риск"],
        ["Завершение не подтверждено", "Прошедшая плановая дата без отметки завершения; это календарный факт, не доказанный простой"],
        ["Плановый / процессный риск", "Плановый: применимая работа; процессный: участок и цитируемое наблюдение"]],
        42, y, [207, 304], 10.7)
    y = section(c, "Три состояния активности", "working_signs: видимое действие на каждом цитируемом кадре. possible_idle: независимые надёжные времена, один участок, сопоставимый обзор, связь физического объекта и явные нерабочие признаки; остаётся гипотезой. insufficient_data: данных недостаточно. Присутствие, статичная поза, watermark-дата и повторы одного файла не доказывают движение или длительность.", y)
    section(c, "Гипотезы и история", "Один кадр может соответствовать нескольким stage/plan-entry гипотезам; требуется пригодный кадр и явное основание. Подтверждение человеком отдельно. История ограничена тем же участком и успешными анализами с временем раньше самого раннего нового кадра; ненадёжные или неупорядоченные времена исключают историю.", y)
    c.showPage()

    y = note(c, 7, "Надёжность: права исполнителя и защита от повторов", "История и платные эффекты защищены отдельными контрактами")
    y = section(c, "Повтор HTTP-запроса и обращение к модели", "Idempotency-Key связан с телом загрузки. То же тело и ключ возвращают тот же run; другое тело даёт 409. deepseek_calls(run_id, call_key) резервируется уникально до отправки. Отсутствие результата после резервации означает неопределённый исход, а не право на повтор.", y)
    y = section(c, "Сбой и неопределённый вызов", "Тайм-аут, повреждённый JSON, завершение процесса или потеря lease не вызывают автоматического платного повтора. Исходный ответ и причина отклонения сохраняются, если получены. Восстановление после сбоя переводит прерванный анализ в failed; резервированные вызовы не удаляются для повторной отправки. Новый анализ запускается отдельным осознанным действием.", y)
    y = section(c, "Атомарная публикация", "Результат и сигналы сохраняются одной транзакцией, проверяющей владельца, срок lease и fence. Истёкшая lease запрещает успешную публикацию. Резервации, зафиксированный контекст и исходный ответ защищены от UPDATE/DELETE. Миграции сохраняют старые анализы; откат миграций отказывается стирать доказательства.", y)
    y = section(c, "Устойчивое отождествление сигнала", "Fingerprint использует участок, ревизию, причину, работу, хеши кадров, тип/класс цитированных наблюдений и исходные идентификаторы детекций. Координаты, сгенерированный текст и run ID не участвуют. Модельные и детерминированные повторы рисков объединяются; календарный fingerprint сохраняет совместимость со старой историей.", y)
    section(c, "Управление человеком", "Состояния new / in_progress / closed и комментарии сохраняются. Повтор тех же доказательств не открывает закрытый сигнал. Спокойный новый анализ автоматически не закрывает старый. Исправления объектов, подтверждение этапа и экспорт YOLO/COCO создают отдельные одобренные версии.", y)
    c.showPage()

    y = note(c, 8, "Оценка и подготовка к дообучению", "Не превращать машинное предложение или агентскую разметку в принятую эталонную разметку")
    y = section(c, "Фактический инвентарь", "Архив содержит 100 исходных PNG; SHA-256 архива: " + QUEUE["archive_sha256"] + ". Очередь включает 15 кадров. Независимый агент просмотрел 14 и предложил 36 примерных рамок для шести классов. Нет принятия человеком; перечень не даёт исчерпывающей разметки отсутствующих объектов.", y, 10.8)
    y = section(c, "Приёмочная матрица", "Требуются земляные, бетонные и дорожные работы, каждая с normal/risk/ambiguous/unusable исходами; восемь классов; single/duplicate/poor visibility/working/possible idle. Сейчас нет аутентичного привязанного плана и согласованных normal/risk меток, бульдозера, крана-манипулятора и надёжных серий с одной камеры с временем съёмки. Естественно непригодные сцены также не покрыты; синтетический пустой кадр проверяет только устойчивость обработки.", y)
    y = section(c, "Что измерять после принятия разметки", "Precision/recall классов, локализацию, корректность этапа/activity, ложные сигналы и долю insufficient_data, задержку и стоимость. Набор разделяется по проверенным площадкам/камерам/сериям до обучения; одинаковые или соседние источники не попадают в train и test. Допуск требует фактического покрытия и нуля ложных предупреждений; отсутствие метрики не считается нулевой ошибкой.", y)
    y = section(c, "Происхождение весов из отчёта", "Kaggle metadata: epoch 4, то есть пятая эпоха, несмотря на запрос обучения до 100. APOCE optimizer-stripped: epoch -1 не подтверждает длительность обучения. Сохраняются исходные классы и SHA-256. Название checkpoint и длительность обучения сами по себе не устанавливают качество.", y)
    section(c, "Отдельное обучение на Windows/RTX", "training/windows содержит исходники команд smoke/pilot/full и проверок целостности. Нужен полный проверенный комплект для обучения с манифестами, изображениями, метками и предобученными весами yolo26s.pt; его нет в репозитории. Windows 10/11, Python 3.11/3.12 x64, RTX 3060 12 GB, driver CUDA 12.8, ≥35 GB. На целевой машине обучение/установка не выполнялись; новый checkpoint подключается только после независимой оценки.", y, 10.8)
    c.showPage()

    y = note(c, 9, "Реальные прогоны и их ограничения", "CPU-прогон и платные HTTP-вызовы подтверждают интеграцию; точность оценивается отдельно")
    y = table(c, [["Оригинал", "Наблюдаемый результат YOLO"],
        ["Screenshot_60.png", "Каток; APOCE: 5 excavator; Kaggle: Trailer"],
        ["Screenshot_24.png", "Видимый автокран; оба: 0 детекций"],
        ["Screenshot_99.png", "Экскаваторы/самосвал; APOCE: 0; Kaggle: Trailer + Mixer"],
        ["Screenshot_48.png", "Несколько машин; APOCE: 1 excavator; Kaggle: 1 Excavator"]],
        42, y, [164, 347], 10.8)
    y = section(c, "Измеренное время работы на CPU", f"Оба checkpoint отработали на 15 оригиналах. Загрузка: {SMOKE['load_ms']/1000:.2f} с. Первый кадр: {sum(m['latency_ms'] for m in SMOKE['frames'][0]['models'])/1000:.2f} с; медиана суммарного инференса пары на следующих 14 кадрах: {WARM_MS:.1f} мс. Это smoke окружения от 27.09.2026, без p95, memory/load benchmark или гарантий для целевого ноутбука.", y)
    y = section(c, "Полный HTTP-путь", http_text(detail=True), y, 11)
    y = section(c, "Финальные технические проверки", checks_text(), y, 11)
    y = section(c, "Контейнер: отдельные уровни проверки", container_text(), y, 10.5)
    section(c, "Затраты и воспроизводимость", paid_text() + " Это расчёт по возвращённым сведениям об использовании токенов, без сверки счёта. До запроса резервируется верхняя стоимость; неопределённый исход учитывается по ней. Запросы, сырые ответы, хеши, usage и задержка сохраняются для аудита.", y + 8, 11)
    c.showPage()

    y = note(c, 10, "Воспроизводимый локальный запуск", "Приватные БД/S3 и существующие тома сохраняются; ключи не попадают в артефакты")
    y = section(c, "Входные артефакты", "Оригинальные artifacts/Models/apoce.pt и kaggle.pt, XLSX каталога artifacts/dataset/Свод*.xlsx и архив Строительная_техника.zip. Имена весов case-sensitive. Удаление или замена исходных байтов не исправляет расхождение с манифестом.", y)
    y = section(c, "1. Выбрать один способ запуска", "Compose: Node/npm и Docker либо Podman с Compose-провайдером; backend собирается в контейнере. Прямой backend: Python 3.13.15 + uv, Node/npm, отдельные PostgreSQL и приватный S3. До создания профиля задайте YANDEX_CLOUD_FOLDER_ID и временный YANDEX_AI_STUDIO_API_KEY. Ключ не сохраняйте и не печатайте.", y, 10.7)
    y = section(c, "2. Compose: собственные БД и бакет", "Задайте POSTGRES_PASSWORD и MINIO_ROOT_PASSWORD; HYBRID_PHOTO_SIGNALS=1. Для изоляции сохраняйте один COMPOSE_PROJECT и PORT во всех командах.\nmake up\nmake profile\nВыданный UUID задайте как OBSERVER_PROFILE_ID в окружении.\nmake up\ncurl --fail http://127.0.0.1:8096/api/health/ready\nМиграции и каталог применяются init автоматически. Host DATABASE_URL/S3_* этот путь не использует. Не выполняйте down --volumes.", y, 10.5)
    section(c, "3. Прямой backend: профиль в его БД", "Сначала задайте DATABASE_URL, S3_ENDPOINT/S3_BUCKET/S3_ACCESS_KEY/S3_SECRET_KEY, YOLO_MODELS_DIR и API_ROOT_PATH=/api. Затем из корня:\nuv sync --project backend --extra test\nnpm --prefix web ci\nbackend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head\nHYBRID_PHOTO_SIGNALS=1 backend/.venv/bin/evidence-profile\nЗадайте UUID как OBSERVER_PROFILE_ID. В двух терминалах:\nuv run --project backend uvicorn app.main:app --host 127.0.0.1 --port 58049\nAPI_PROXY_TARGET=http://127.0.0.1:58049 npm --prefix web run dev -- --port 58149\nБакет должен существовать и быть приватным; профиль создаёт только конфигурацию, без платного запроса.", y, 10.2)
    c.showPage()

    y = note(c, 11, "Проверка и локальная демонстрация", "Команды проверяют разные свойства системы; успешная сборка не подтверждает точность")
    y = section(c, "4. Регрессия на изолированных ресурсах", "uv run --project backend --extra test pytest backend/tests -q\nnpm --prefix web test -- --run\nnpm --prefix web run build\nTEST_DATABASE_URL и TEST_S3_BUCKET обязаны отличаться от рабочих. Fixtures удаляют только созданные ими временные ресурсы. Реальный HTTP-smoke выполняется отдельно с согласованным бюджетом.", y, 10.7)
    y = section(c, "Проверенная локальная демонстрация", VERIFICATION.get("local_url", "http://127.0.0.1:58159") + "; отдельные БД/бакет сохраняют существующее приложение пользователя. Доступны проект/участок, фото с согласием, исходные рамки обеих моделей, согласованные наблюдения, активность, гипотезы и лента. Отображение в браузере не проверялось: GUI запрещён.", y, 10.7)
    y = section(c, "Подготовка оригиналов контрольной очереди", "python evaluation/hybrid/prepare.py --archive artifacts/dataset/Строительная_техника.zip --output output/hybrid-review/images\nЭкстрактор сверяет хеш архива и каждого изображения; отказывается перезаписывать другие байты. Он не создаёт эталонную разметку или метаданные камер и времени.", y, 10.7)
    y = section(c, "Сборка двух PDF", "python scripts/build_submission_pdfs.py\nНужны reportlab, системные Arial или DejaVuSans с кириллицей и финальный docs/HYBRID_VERIFICATION.json. Генератор читает manifest, CPU smoke, очередь и бюджет; фото берёт из оригинального ZIP и сверяет SHA-256. Финальные артефакты: output/pdf/*hybrid*.pdf.", y, 10.7)
    section(c, "Граница проверенного результата", "Контейнерный build, startup readiness, автоматические тесты и реальный HTTP-анализ проверяются отдельно. Видеопоток, автоматический монтаж камер и удалённый сервер не входят в эту поставку. Подробные факты, даты и исключения зафиксированы в HYBRID_VERIFICATION.json.", y, 10.7)
    c.showPage()

    y = note(c, 12, "Эксплуатация и следующий допуск", "Масштабирование начинается с измеренного пилота, а не с обещания производительности")
    y = section(c, "Камеры и сбор последовательностей", "Закрепить обзор зоны операции, машины и конструкции; перекрыть слепые участки дополнительным ракурсом и въездом. Внутренние зоны/тоннели требуют своего обзора. Хранить camera_id, фактическое время съёмки и события изменения ракурса; синхронизировать часы. Проверять ночь, осадки, пыль, закрытый обзор и малые объекты. Частота съёмки выбирается по длительности операции и пилоту.", y)
    y = section(c, "Рост нагрузки", "Успешный run из N кадров выполняет N frame calls и один assessment. CPU-инференс внутри процесса сериализован, модели кешируются. Сначала измерить пропускную способность, p95, время ожидания в очереди, память и стоимость по площадкам. При необходимости добавить worker-процессы/хосты с независимым lease и теми же fenced contracts; модельный cache потребует памяти на каждый процесс. Не ослаблять проверку данных и запрет повтора ради скорости.", y)
    y = section(c, "Данные для следующей итерации", "Человек согласует объекты, рамки, сцены, активность и сигналы с автором и датой; разногласия разбираются отдельно. Добавить отсутствующие классы, отрицательные примеры кранов/погрузчиков/трейлеров и реальные серии работы/простоя. Test-источники исключить из обучения и подбора. Затем прогнать обязательную матрицу и измерить метрики; допуск по качеству остаётся BLOCKED.", y)
    y = section(c, "Основные модули", "profiles/yolo.py и data/yolo-manifest.json: детекторы и pins. profiles/deepseek.py: схема/нормализация. application/deepseek_runtime.py: резервации, context, lease и публикация. domain/site_analysis.py: frame/work правила. application/signals.py: лента. adapters/postgres.py: сохранение. web EvidenceViewer/AiAssessment: raw/reconciled объекты и доказательства.", y, 10.7)
    section(c, "Источники фактов в репозитории", "Architecture.md; README.md; docs/HYBRID_PHOTO_SIGNALS.md; docs/HYBRID_VERIFICATION.json; docs/pdf-inputs/yolo-manifest-2026-09-27.json; evaluation/hybrid/README.md, control-review-queue.json, independent-visual-review.json, yolo-smoke-summary.json, budget.json; training/windows/README.md; PRODUCT.md. Фото сверены по хешам очереди. Проверки и веса относятся к отчёту от 27 сентября; переименование не подтверждает текущие веса.", y, 10.5)
    c.save()
    return path


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for output in (presentation(), accompanying()):
        print(output)
