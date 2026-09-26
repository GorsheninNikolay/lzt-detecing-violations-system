"""Suggested equipment templates; expectations become authoritative only in a saved plan."""

STAGES = {
    "preparation": ("Подготовка территории и планировка", ["excavator", "dump_truck"]),
    "demolition": ("Снос и демонтаж", ["excavator", "dump_truck"]),
    "excavation": ("Земляные работы и котлован", ["excavator", "dump_truck"]),
    "concreting": ("Бетонные работы", ["concrete_mixer_truck"]),
    "installation": ("Подъём и монтаж конструкций", ["mobile_crane"]),
    "roadwork": ("Дорожные работы", ["road_roller"]),
    "utilities": ("Наружные инженерные сети", ["excavator"]),
    "landscaping": ("Благоустройство", ["excavator", "dump_truck"]),
}

CATALOG_SHA256 = "82beeb771b5d24bd3fc7323a34f35808dce0c3f396498303a3dd9b9d7f860e3a"
CATALOG_STAGE_SUGGESTIONS = {
    19: ("Снос домов в пятне застройки", "demolition"),
    20: ("Снос нежилых объектов в пятне застройки", "demolition"),
    24: ("Демонтаж ж/б перекрытий", "demolition"),
    25: ("Погрузка строительного мусора", "demolition"),
    47: ("Устройство котлована", "excavation"),
    54: ("Устройство бетонной подготовки", "concreting"),
    64: ("Земляные работы", "excavation"),
    67: ("Планировка грунта", "preparation"),
    72: ("Выемка грунта котлована", "excavation"),
    73: ("Разработка грунта с креплением котлована", "excavation"),
    79: ("Основание нижнего слоя дорожной одежды (в т.ч. Песчано-подстилающий слой)", "roadwork"),
    81: ("Планировка нижнего слоя основания дорожной одежды", "roadwork"),
    85: ("Устройство монолитной ж/б фундаментной плиты (плита под здание, плита под башенный кран, фундамент под оборудование), в т.ч. устройство бетонной подготовки", "concreting"),
    109: ("Устройство конструкций пролетного строения (металл, балки)", "installation"),
    243: ("Устройство наружных сетей", "utilities"),
    250: ("Устройство трубной канализации", "utilities"),
    352: ("Благоустройство территории", "landscaping"),
    354: ("Устройство асфальтобетонного покрытия проездов, тротуаров, площадок с установкой бортового камня", "roadwork"),
    368: ("Вертикальная планировка", "landscaping"),
}


def catalog_suggestion(source_sha256: str, source_row: int, title: str) -> dict:
    mapping = CATALOG_STAGE_SUGGESTIONS.get(source_row)
    if source_sha256 != CATALOG_SHA256 or mapping is None or title != mapping[0]:
        return {"suggested_stage": None, "suggested_equipment": [], "suggestion_revision": None}
    stage = mapping[1]
    return {"suggested_stage": stage, "suggested_equipment": list(STAGES[stage][1]),
            "suggestion_revision": "catalog-stage-suggestions-v1", "requires_manual_confirmation": True}
