"""Bounded XLSX interchange for immutable zone plans."""
import io
import re
import zlib
from datetime import datetime, time, timedelta
from uuid import UUID
from zipfile import ZipFile, BadZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy import text
from app.application.site import _engine, ensure_catalog, SiteError, _response

router = APIRouter()
NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
HEADERS = ['Работа', 'Начало', 'Окончание', 'Состояние', 'Этап', 'Ожидаемая техника', 'Допустимая техника', 'Не предусмотренная техника']
EQUIPMENT = {'excavator': 'Экскаватор', 'dump_truck': 'Самосвал', 'road_roller': 'Каток', 'truck_mounted_crane': 'Кран-манипулятор', 'concrete_mixer_truck': 'Автобетоносмеситель', 'bulldozer': 'Бульдозер', 'truck': 'Грузовик', 'mobile_crane': 'Автокран'}
STATES = {'Запланирована': 'planned', 'Активна': 'active', 'Завершена': 'completed'}
STAGES = {'Земляные работы': 'excavation', 'Бетонные работы': 'concreting', 'Дорожные работы': 'roadwork'}
MAX_BYTES = 5 * 1024 * 1024


def workbook(sheets):
    output = io.BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' + ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheets)+1)) + '</Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', '<workbook xmlns="'+NS['x']+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>' for i,(name, _) in enumerate(sheets,1))+'</sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1))+'</Relationships>')
        for i,(_, rows) in enumerate(sheets,1):
            archive.writestr(f'xl/worksheets/sheet{i}.xml', '<worksheet xmlns="'+NS['x']+'"><sheetData>'+''.join(f'<row r="{n}">'+''.join(f'<c r="{chr(65+j)}{n}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>' for j,value in enumerate(row))+'</row>' for n,row in enumerate(rows,1))+'</sheetData></worksheet>')
    return output.getvalue()


def _format_has_time(number, custom):
    if number in (14, 15, 16, 17): return False
    if number in (18, 19, 20, 21, 22, 45, 46, 47): return True
    code = custom.get(number)
    if code is None: return None
    code = re.sub(r'"[^"]*"|\\.|_.|\*.', '', code).lower()
    elapsed = bool(re.search(r'\[[hms]+\]', code))
    code = re.sub(r'\[[^]]*\]', '', code)
    if elapsed or re.search(r'[hs]|am/pm|a/p', code): return True
    if re.search(r'[yd]', code): return False
    return None


def _date(value, zone, end=False, numeric=False, epoch1904=False, has_time=None):
    if numeric:
        parsed = datetime(1904,1,1) if epoch1904 else datetime(1899,12,30)
        parsed += timedelta(days=float(value))
        if has_time is None: raise ValueError('Неизвестный формат даты Excel: задайте формат даты/времени или введите дату текстом ГГГГ-ММ-ДД')
        date_only = not has_time and parsed.time() == time.min
    else:
        date_only = bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', value))
        parsed = datetime.fromisoformat(value)
    if date_only and end:
        parsed = datetime.combine(parsed.date(), time.max)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
        if parsed.astimezone(ZoneInfo('UTC')).astimezone(zone).replace(tzinfo=None) != parsed.replace(tzinfo=None):
            raise ValueError('Несуществующее местное время')
        if parsed.replace(fold=0).utcoffset() != parsed.replace(fold=1).utcoffset():
            raise ValueError('Неоднозначное время: укажите смещение UTC')
    return parsed.isoformat()


def preview(data, catalog, timezone):
    errors, entries = [], []
    def error(row, message): errors.append({'row': row, 'message': message})
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos)>1000 or sum(item.file_size for item in infos)>20*1024*1024 or len({item.filename for item in infos}) != len(infos):
                raise ValueError('Архив XLSX слишком велик или содержит повторяющиеся файлы')
            def xml(name):
                raw = archive.read(name)
                if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper(): raise ValueError('Недопустимый XML')
                return ET.fromstring(raw)
            strings = [''.join(item.itertext()) for item in xml('xl/sharedStrings.xml').findall('x:si',NS)] if 'xl/sharedStrings.xml' in archive.namelist() else []
            styles = xml('xl/styles.xml') if 'xl/styles.xml' in archive.namelist() else None
            formats = {int(item.get('numFmtId')): item.get('formatCode', '') for item in styles.findall('x:numFmts/x:numFmt', NS)} if styles is not None else {}
            cell_styles = styles.findall('x:cellXfs/x:xf', NS) if styles is not None else []
            book = xml('xl/workbook.xml')
            prop = book.find('x:workbookPr',NS)
            epoch1904 = prop is not None and prop.get('date1904') in ('1','true')
            sheet = book.find('x:sheets/x:sheet',NS)
            relid = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            rels = xml('xl/_rels/workbook.xml.rels')
            target = next(item.get('Target') for item in rels if item.get('Id')==relid and item.get('TargetMode') != 'External')
            path = target.lstrip('/') if target.startswith('/') else 'xl/'+target
            rows = xml(path).findall('x:sheetData/x:row',NS)
            if len(rows)>1001: raise ValueError('Не более 1000 работ')
            parsed = []
            previous_row = 0
            for row in rows:
                n = int(row.get('r', str(previous_row + 1)))
                if n <= previous_row or n > 1048576: raise ValueError('Некорректный номер строки')
                previous_row = n
                values = {}
                previous_column = 0
                for cell in row.findall('x:c',NS):
                    address = cell.get('r')
                    if address:
                        match = re.fullmatch(r'([A-Z]+)([1-9][0-9]*)', address)
                        if not match or int(match.group(2)) != n: raise ValueError('Некорректный адрес ячейки')
                        column = match.group(1)
                        column_number = 0
                        for letter in column: column_number = column_number * 26 + ord(letter) - 64
                    else:
                        column_number = previous_column + 1
                        number, column = column_number, ''
                        while number:
                            number, remainder = divmod(number - 1, 26)
                            column = chr(65 + remainder) + column
                    if column_number <= previous_column or column_number > 16384: raise ValueError('Некорректный столбец')
                    previous_column = column_number
                    if cell.find('x:f',NS) is not None: error(n,f'Формулы не поддерживаются: {column}{n}')
                    raw = cell.findtext('x:v','',NS)
                    kind = cell.get('t','n')
                    value = strings[int(raw)] if kind=='s' else ''.join(cell.find('x:is',NS).itertext()) if kind=='inlineStr' else raw
                    has_time = None
                    if kind == 'n' and column in ('B', 'C') and value.strip():
                        style_index = int(cell.get('s', '0'))
                        if 0 <= style_index < len(cell_styles):
                            has_time = _format_has_time(int(cell_styles[style_index].get('numFmtId', '0')), formats)
                    values[column] = (value.strip(),kind,has_time)
                parsed.append((n,values))
    except (BadZipFile, KeyError, ValueError, ET.ParseError, StopIteration, IndexError, AttributeError, OverflowError, RuntimeError, TypeError, zlib.error) as cause:
        return {'entries': [], 'errors': [{'row': None, 'message': 'Не удалось прочитать XLSX: '+str(cause)}], 'timezone': timezone}
    if not parsed or [parsed[0][1].get(chr(65+i),('',))[0] for i in range(3)] != HEADERS[:3]:
        error(1,'Первые столбцы должны называться: Работа, Начало, Окончание')
    for index, header in enumerate(HEADERS[3:], 3):
        actual = parsed[0][1].get(chr(65+index), ('',))[0] if parsed else ''
        if actual and actual != header: error(1, f'Столбец {chr(65+index)} должен называться: {header}')
    zone = ZoneInfo(timezone)
    by_title = {}
    for work in catalog: by_title.setdefault(work['title'].strip().casefold(),[]).append(work)
    for n, cells in parsed[1:]:
        if not any(value[0] for value in cells.values()): continue
        values = [cells.get(chr(65+i),('','n'))[0] for i in range(8)]
        try:
            matches = [work for work in catalog if str(work['id'])==values[0]] or by_title.get(values[0].casefold(),[])
            if len(matches)!=1: raise ValueError('Работа не найдена или название неоднозначно; используйте ID из справочника')
            start = _date(values[1],zone,numeric=cells.get('B',('',''))[1]=='n',epoch1904=epoch1904,has_time=cells.get('B', ('', '', None))[2])
            end = _date(values[2],zone,True,numeric=cells.get('C',('',''))[1]=='n',epoch1904=epoch1904,has_time=cells.get('C', ('', '', None))[2])
            if datetime.fromisoformat(start)>datetime.fromisoformat(end): raise ValueError('Начало позже окончания')
            state = STATES.get(values[3],values[3] or 'planned')
            stage = STAGES.get(values[4],values[4] or None)
            if state not in STATES.values() or stage not in (*STAGES.values(),None): raise ValueError('Неизвестное состояние или этап')
            entry = {'catalog_work_id': str(matches[0]['id']), 'title': matches[0]['title'], 'start_at':start,'end_at':end,'state':state,'stage_key':stage}
            for field, raw in zip(('expected_equipment','allowed_equipment','excluded_equipment'),values[5:]):
                items = [item.strip() for item in raw.split(';') if item.strip()]
                mapped = [next((key for key,label in EQUIPMENT.items() if item.casefold() in (key.casefold(),label.casefold())),None) for item in items]
                if None in mapped: raise ValueError('Неизвестная техника; используйте справочник и разделитель ;')
                entry[field] = sorted(set(mapped))
            if set(entry['excluded_equipment']) & (set(entry['expected_equipment'])|set(entry['allowed_equipment'])): raise ValueError('Техника одновременно ожидается и исключена')
            entries.append(entry)
        except (ValueError, OverflowError, TypeError) as cause: error(n,str(cause))
    if not entries and not errors: error(2,'Файл не содержит работ')
    return {'entries':entries,'errors':errors,'timezone':timezone,'date_note':'Даты без времени: начало в 00:00, окончание в 23:59:59.999999 по часовому поясу проекта.'}


def context(request, zone_id):
    engine = _engine(request)
    source = ensure_catalog(engine)
    with engine.connect() as conn:
        timezone = conn.execute(text('SELECT p.timezone FROM site_zones z JOIN site_projects p ON p.id=z.project_id WHERE z.id=:id'), {'id':zone_id}).scalar_one_or_none()
        if not timezone: raise SiteError('zone_not_found',404)
        catalog = [dict(row) for row in conn.execute(text('SELECT id,title FROM catalog_works WHERE source_sha256=:hash ORDER BY source_row'), {'hash':source}).mappings()]
        revision = conn.execute(text('SELECT coalesce(max(revision_number),0) FROM zone_plan_revisions WHERE zone_id=:id'),{'id':zone_id}).scalar_one()
    return timezone,catalog,revision


@router.get('/zones/{zone_id}/plan/template.xlsx')
def template(zone_id: UUID, request: Request, tutorial: bool=False):
    try:
        timezone,catalog,_ = context(request,zone_id)
        selected = next((work for work in catalog if work['title']=='Земляные работы'), catalog[0])
        example = [str(selected['id']),'2026-10-19','2026-10-20','Запланирована','Земляные работы','Экскаватор','','']
        data = workbook([('План',[HEADERS]+([example] if tutorial else [])),('Справочник',[['ID работы','Работа']]+[[str(w['id']),w['title']] for w in catalog]),('Инструкция',[[f'Часовой пояс проекта: {timezone}'],['Начало без времени: 00:00; окончание: 23:59:59.999999.'],['Работа: точное уникальное название или ID из справочника. Формулы запрещены.'],['Даты: ГГГГ-ММ-ДД или ГГГГ-ММ-ДДTчч:мм. Техника через ;.'],['Состояние: '+', '.join(STATES)],['Этап: '+', '.join(STAGES)],['Техника: '+ '; '.join(EQUIPMENT.values())]]),('Пример',[HEADERS,example])])
        return Response(data,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="'+('tutorial-plan.xlsx' if tutorial else 'plan-template.xlsx')+'"'})
    except SiteError as error: return _response(error)


@router.post('/zones/{zone_id}/plan/import-preview')
async def import_preview(zone_id: UUID, request: Request):
    try:
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>MAX_BYTES: raise SiteError('xlsx_too_large',413)
        timezone,catalog,revision = context(request,zone_id)
        result = preview(bytes(data),catalog,timezone)
        return {**result,'expected_revision':revision}
    except SiteError as error: return _response(error)
