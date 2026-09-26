"""Build the jury presentation and supporting note from checked repository scope."""

from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf"
OUT.mkdir(parents=True, exist_ok=True)
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
pdfmetrics.registerFont(TTFont("ArialRU", FONT))
pdfmetrics.registerFont(TTFont("ArialRUBold", BOLD))
INK = HexColor("#172433")
MUTED = HexColor("#526174")
ORANGE = HexColor("#FF9A4D")
BLUE = HexColor("#2D7EA3")


def lines(value: str, width: float, size: float, font: str = "ArialRU") -> list[str]:
    result = []
    for paragraph in value.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if current and pdfmetrics.stringWidth(candidate, font, size) > width:
                result.append(current)
                current = word
            else:
                current = candidate
        result.append(current)
    return result


def text_block(c, value: str, x: float, top: float, width: float, size: float,
               leading: float | None = None, color=INK, bold=False) -> float:
    font = "ArialRUBold" if bold else "ArialRU"
    leading = leading or size * 1.36
    c.setFont(font, size)
    c.setFillColor(color)
    y = top
    for line in lines(value, width, size, font):
        if line:
            c.drawString(x, y, line)
        y -= leading
    return y


def slide(c, number: int, title: str, subtitle: str | None = None):
    c.setFillColor(HexColor("#F7F8F8"))
    c.rect(0, 0, 960, 540, fill=1, stroke=0)
    c.setFillColor(INK)
    c.rect(0, 0, 960, 12, fill=1, stroke=0)
    c.setFillColor(ORANGE)
    c.rect(52, 471, 48, 5, fill=1, stroke=0)
    text_block(c, title, 52, 443, 850, 32, 38, bold=True)
    if subtitle:
        text_block(c, subtitle, 52, 392, 850, 15, color=MUTED)
    text_block(c, f"Контроль строительства · {number}/7", 52, 31, 800, 11, color=MUTED)


def panel(c, x, y, w, h, heading, body, accent=BLUE):
    c.setFillColor(HexColor("#FFFFFF"))
    c.roundRect(x, y, w, h, 9, fill=1, stroke=0)
    c.setFillColor(accent)
    c.rect(x, y + h - 5, w, 5, fill=1, stroke=0)
    text_block(c, heading, x + 17, y + h - 38, w - 34, 17, 21, bold=True)
    text_block(c, body, x + 17, y + h - 72, w - 34, 13, 19)


def presentation():
    path = OUT / "construction-monitoring-presentation.pdf"
    c = canvas.Canvas(str(path), pagesize=(960, 540))
    slide(c, 1, "Контроль строительства", "Этапы, техника и сигналы для проверки человеком")
    text_block(c, "Изображение → наблюдаемые объекты → гипотеза этапа → сравнение с планом → сигнал",
               52, 300, 820, 23, 32, bold=True)
    text_block(c, "Подготовка выпуска: каталог, планы, PNG и внутренняя лента доступны в коде."
               " Восемь классов и новые сценарии ждут отдельного размеченного набора и допуска модели.",
               52, 176, 820, 16, 24, color=MUTED)
    c.showPage()

    slide(c, 2, "Как устроен анализ", "Структурированные решения хранятся в PostgreSQL, изображения и вызовы модели — в S3")
    cards = [
        ("Каталог и план", "377 строк XLSX; проект, зона, неизменяемая ревизия."),
        ("Кадры", "JPEG/PNG, исходные байты, время каждого кадра."),
        ("Наблюдение", "Локальная модель, рамки, классы и признаки сцены."),
        ("Результат", "Гипотезы, правило, доказательства и лента сигналов."),
    ]
    for index, (heading, body) in enumerate(cards):
        panel(c, 52 + index * 226, 176, 208, 180, heading, body, ORANGE if index == 3 else BLUE)
    text_block(c, "Старые анализы связаны со своими профилями. Облачный профиль сообщает только присутствие двух классов.",
               52, 116, 830, 14, 21, color=MUTED)
    c.showPage()

    slide(c, 3, "Связь фотографии с планом", "Одна заявленная зона; параллельные операции остаются отдельными записями")
    panel(c, 52, 184, 257, 186, "1. План", "Работа каталога, начало и конец, состояние, ожидаемая и исключённая техника.")
    panel(c, 351, 184, 257, 186, "2. Кадры", "Выбранная зона, точная ревизия плана и время съёмки каждого файла.")
    panel(c, 650, 184, 257, 186, "3. Сравнение", "Только активные работы в этой зоне и наблюдаемые классы с достаточными кадрами.", ORANGE)
    text_block(c, "Изображение не подтверждает срок выполнения или отсутствие техники вне кадра.",
               52, 116, 820, 17, 24, bold=True)
    c.showPage()

    slide(c, 4, "Что означает сигнал", "Повод проверить участок, а не доказанное нарушение")
    panel(c, 52, 184, 270, 190, "Ожидаемой техники нет", "Явное ожидание активной операции и минимум три пригодных кадра одной зоны.")
    panel(c, 345, 184, 270, 190, "Техника не предусмотрена", "Есть явное исключение; ни одна параллельная работа не разрешает этот класс.")
    panel(c, 638, 184, 270, 190, "Срок прошёл", "Нет отметки завершения. Формулировка: «Завершение не подтверждено».", ORANGE)
    text_block(c, "Человек может подтвердить этап, перевести сигнал в работу или закрыть с комментарием.",
               52, 113, 850, 15, 23)
    c.showPage()

    slide(c, 5, "Размещение камер", "Рекомендации для сравнимых серий и меньшего числа ложных сигналов")
    panel(c, 52, 179, 270, 195, "Рабочая зона", "Покрывать место операции; сохранять обзор техники и строящейся конструкции.")
    panel(c, 345, 179, 270, 195, "Въезд и перекрытия", "Отдельный ракурс для прибывающей техники; перекрывающиеся зоны обзора.")
    panel(c, 638, 179, 270, 195, "Внутренние работы", "Дополнительные камеры внутри помещений и тоннеля; синхронное время.", ORANGE)
    text_block(c, "Перед выводом об отсутствии техники проверить закрытый обзор, размер объекта и интервал съёмки.",
               52, 109, 850, 15, 23)
    c.showPage()

    slide(c, 6, "Проба на исходном PNG", "Архив организаторов · Screenshot_87.png · камера не установлена")
    with ZipFile(ROOT / "artifacts/dataset/Строительная_техника.zip") as archive:
        photo = ImageReader(BytesIO(archive.read("Строительная_техника/Screenshot_87.png")))
    c.drawImage(photo, 52, 130, 535, 240, preserveAspectRatio=True, anchor="c")
    text_block(c, "Локальный CPU-прогон", 620, 360, 280, 20, 27, bold=True)
    text_block(c, "Модель выдала рамки для экскаватора, автобетоносмесителя и бульдозера."
               " Визуальная проверка указывает на путаницу классов: этот пример не подтверждает точность новой таксономии.",
               620, 314, 280, 15, 23)
    text_block(c, "Снимок демонстрирует источник и ограничение модели, не строительное отклонение.",
               52, 91, 850, 13, 19, color=MUTED)
    c.showPage()

    slide(c, 7, "Путь к демонстрации", "Проверенная поставка и оставшиеся измерения — разные факты")
    panel(c, 52, 174, 407, 198, "В коде прототипа", "Импорт 377 работ; планы зон; PNG; хранение доказательств; API и интерфейс. Это не допуск восьмиклассовой модели.")
    panel(c, 501, 174, 407, 198, "Требует доказательства", "Независимая разметка восьми классов; допуск профиля; проверенные демо; HTTPS и код жюри; серверный прогон.", ORANGE)
    text_block(c, "До приёмки: этот документ описывает прототип и ограничения. Финальная демонстрация не готова.",
               52, 104, 850, 15, 22, bold=True)
    c.save()
    return path


def supporting_document():
    path = OUT / "construction-monitoring-supporting-document.pdf"
    c = canvas.Canvas(str(path), pagesize=(595, 842))
    page = 0

    def start(title, subtitle=None):
        nonlocal page
        page += 1
        c.setFillColor(HexColor("#F7F8F8"))
        c.rect(0, 0, 595, 842, fill=1, stroke=0)
        c.setFillColor(ORANGE)
        c.rect(42, 773, 43, 5, fill=1, stroke=0)
        y = text_block(c, title, 42, 748, 510, 24, 29, bold=True)
        if subtitle:
            y = text_block(c, subtitle, 42, y - 8, 510, 11, 16, color=MUTED)
        c.setStrokeColor(HexColor("#D9E0E4"))
        c.line(42, 46, 553, 46)
        text_block(c, f"Контроль строительства · {page}", 42, 31, 510, 9, color=MUTED)
        return y - 26

    def section(title, body, y):
        y = text_block(c, title, 42, y, 510, 15, 21, bold=True) - 6
        return text_block(c, body, 42, y, 510, 11, 16) - 17

    y = start("Сопроводительный документ", "Подготовка выпуска · 26 сентября 2026 · приёмка не завершена")
    y = section("Назначение", "Сервис помогает менеджеру сопоставлять фотографии с ручным планом работ одной зоны. Результат содержит наблюдения, гипотезу этапа и повод для проверки человеком. Он не устанавливает нарушение договора или фактический процент готовности.", y)
    y = section("Данные", "Источник каталога — 377 строк предоставленного XLSX. Хранятся SHA-256 файла, исходный код, формат и координата ячейки, заголовок, применимость к девяти типам объектов. Проект содержит зоны. Каждая ревизия плана — неизменяемый снимок параллельных работ с датами, состоянием, этапом и тремя списками техники: ожидаемой, допустимой, явно исключённой.", y)
    y = section("Следы анализа", "Запуск связывает проект, зону, ревизию плана и время каждого кадра. Оригиналы JPEG/PNG остаются в S3. PostgreSQL хранит ссылки на исходные кадры, вызовы наблюдателя, прямоугольники объектов в нормализованных координатах, признаки сцены, результаты правил и сигналы. Повтор создаёт новый связанный запуск; история не пересчитывается.", y)
    c.showPage()

    y = start("Распознавание и правила")
    y = section("Классы техники", "Первый расширенный профиль предусматривает: самосвал, экскаватор, каток, кран-манипулятор, автобетоносмеситель, бульдозер, грузовик, автокран. Старый допущенный локальный и облачный профили проверяли только самосвал и экскаватор; облачный профиль не возвращает рамки. Новые классы нельзя считать допущенными без отдельной разметки и проверки.", y)
    y = section("Признаки и гипотезы", "Локальный профиль предлагает пять признаков: выемка/траншея, опалубка, арматура, бетонная конструкция, дорожное основание/покрытие. Гипотеза «земляные работы» требует экскаватор и выемку в одном кадре; «бетонирование» — автобетоносмеситель и бетонный признак; «дорожные работы» — каток и дорожный признак. Без совместных признаков этап остаётся неустановленным. Подтверждение менеджера хранится отдельно.", y)
    y = section("Сигналы", "Для необнаруженной ожидаемой техники требуются минимум три пригодных кадра и активная операция с явным ожиданием. Не предусмотренная техника требует явного исключения и отсутствия разрешения у параллельных работ в момент кадра. Несовпадение этапа требует подтверждения человеком. Просроченная дата сообщает только «Завершение не подтверждено». Сигналы сохраняются с основанием и не закрываются автоматически новым анализом.", y)
    y = section("Ограничения модели", "Архив организаторов не имеет полной разметки восьми классов, рамок и признаков. Нужен отдельный набор с разделением по площадкам и сериям; отчёты о точности классов, локализации, ложных сигналах и скорости на целевом ноутбуке. Закрытый обзор, мелкие объекты, внутренние работы и неполные серии дают недостаточно данных, а не строительное нарушение.", y)
    c.showPage()

    y = start("Код и воспроизводимый запуск")
    y = section("Основные модули", "backend/app/application/site.py импортирует каталог и управляет планом; submission.py проверяет кадры и контекст; executor.py выполняет связанный профиль; profiles/grounding_dino.py содержит локальный адаптер; domain/observations.py и site_analysis.py формируют наблюдения и сравнения; application/signals.py ведёт ленту. adapters/postgres.py сохраняет транзакционные факты. web/src/App.tsx предоставляет русскоязычный интерфейс.", y)
    y = section("Локальный запуск", "1. Установить Python 3.13, uv, PostgreSQL, S3-совместимое хранилище и Node.js.\n2. Запустить инфраструктуру по infra/compose.yaml и создать отдельные бакет и БД.\n3. В backend задать DATABASE_URL и S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY; выполнить uv sync --frozen и uv run alembic upgrade head.\n4. Для наблюдений привязать допущенный OBSERVER_PROFILE_ID и локальный OBSERVER_SNAPSHOT_DIR, затем uv run evidence-service.\n5. В web выполнить npm ci и npm run dev. Подробные команды и требования допуска находятся в README.md.", y)
    y = section("Проверка", "Локальные тесты и миграции должны проходить на отдельной БД. Затем требуется прогон исходного PNG через модель и интерфейс, проверка рамок после поворота/масштаба, скорости на целевом компьютере и доступности развёрнутой версии для жюри. Эти последние проверки не подменяются успешной сборкой исходников.", y)
    c.showPage()
    c.save()
    return path


if __name__ == "__main__":
    print(presentation())
    print(supporting_document())
