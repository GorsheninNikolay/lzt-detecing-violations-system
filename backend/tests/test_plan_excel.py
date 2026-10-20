import io
import struct
from zipfile import ZipFile, ZIP_DEFLATED
from app.application.plan_excel import HEADERS, workbook, preview

CATALOG = [{'id':'11111111-1111-1111-1111-111111111111','title':'Земляные работы'}]


def parse(rows, catalog=CATALOG):
    return preview(workbook([('План',[HEADERS]+rows)]),catalog,'Europe/Moscow')


def test_roundtrip_dates_and_equipment():
    result = parse([['Земляные работы','2026-10-19','2026-10-20','Активна','Земляные работы','Экскаватор; Самосвал']])
    assert result['errors']==[]
    item = result['entries'][0]
    assert item['start_at']=='2026-10-19T00:00:00+03:00'
    assert item['end_at']=='2026-10-20T23:59:59.999999+03:00'
    assert item['expected_equipment']==['dump_truck','excavator']


def test_invalid_rows_are_explicit_and_block_whole_file():
    result = parse([['Земляные работы','2026-10-19','2026-10-20'],['Земляные работы','bad','2026-10-20'],['Unknown','2026-10-19','2026-10-20']])
    assert [error['row'] for error in result['errors']]==[3,4]
    assert len(result['entries'])==1


def test_ambiguous_title_requires_id():
    catalog = CATALOG+[{'id':'22222222-2222-2222-2222-222222222222','title':'Земляные работы'}]
    assert parse([['Земляные работы','2026-10-19','2026-10-20']],catalog)['errors'][0]['row']==2
    assert not parse([[CATALOG[0]['id'],'2026-10-19','2026-10-20']],catalog)['errors']


def test_equipment_and_period_validation():
    for row in [ ['Земляные работы','2026-10-21','2026-10-20'], ['Земляные работы','2026-10-19','2026-10-20','','','Летающий кран'], ['Земляные работы','2026-10-19','2026-10-20','','','Экскаватор','','Экскаватор'] ]:
        assert parse([row])['errors']


def test_formula_even_with_cached_value_rejected():
    data = workbook([('План',[HEADERS,['Земляные работы','2026-10-19','2026-10-20']])])
    output=io.BytesIO()
    with ZipFile(io.BytesIO(data)) as source, ZipFile(output,'w',ZIP_DEFLATED) as target:
        for name in source.namelist():
            value=source.read(name)
            if name.endswith('sheet1.xml'): value=value.replace(b'<c r="B2"',b'<c r="B2"').replace(b'<is><t xml:space="preserve">2026-10-19',b'<f>TODAY()</f><is><t xml:space="preserve">2026-10-19')
            target.writestr(name,value)
    assert any('Формулы' in error['message'] for error in preview(output.getvalue(),CATALOG,'Europe/Moscow')['errors'])


def test_corrupt_zip_and_empty_plan():
    assert preview(b'broken',CATALOG,'Europe/Moscow')['errors']
    assert parse([])['errors']


def test_corrupt_compressed_xml_is_a_preview_error():
    data = bytearray(workbook([('План', [HEADERS])]))
    with ZipFile(io.BytesIO(data)) as archive:
        offset = archive.getinfo('xl/workbook.xml').header_offset
    name_size, extra_size = struct.unpack_from('<HH', data, offset + 26)
    data[offset + 30 + name_size + extra_size] = 6
    result = preview(bytes(data), CATALOG, 'Europe/Moscow')
    assert result['entries'] == []
    assert result['errors'][0]['row'] is None


def test_optional_row_and_cell_addresses_are_inferred():
    import re
    original = workbook([('План',[HEADERS,['Земляные работы','2026-10-19','2026-10-20']])])
    output = io.BytesIO()
    with ZipFile(io.BytesIO(original)) as source, ZipFile(output,'w',ZIP_DEFLATED) as target:
        for name in source.namelist():
            value = source.read(name)
            if name.endswith('sheet1.xml'):
                value = re.sub(rb' r="[A-Z]*[0-9]+"', b'', value)
            target.writestr(name,value)
    result = preview(output.getvalue(),CATALOG,'Europe/Moscow')
    assert result['errors']==[]
    assert len(result['entries'])==1


def numeric_workbook(format_number, custom=None):
    original = workbook([('План',[HEADERS,['Земляные работы','2026-10-19','2026-10-20']])])
    output = io.BytesIO()
    with ZipFile(io.BytesIO(original)) as source, ZipFile(output,'w',ZIP_DEFLATED) as target:
        for name in source.namelist():
            value = source.read(name)
            if name.endswith('sheet1.xml'):
                value = value.replace(b'<c r="B2" t="inlineStr"><is><t xml:space="preserve">2026-10-19</t></is></c>',b'<c r="B2" s="0"><v>46314</v></c>')
                value = value.replace(b'<c r="C2" t="inlineStr"><is><t xml:space="preserve">2026-10-20</t></is></c>',b'<c r="C2" s="0"><v>46315</v></c>')
            target.writestr(name,value)
        from xml.sax.saxutils import quoteattr
        num_formats = f'<numFmts count="1"><numFmt numFmtId="{format_number}" formatCode={quoteattr(custom)}/></numFmts>' if custom else ''
        target.writestr('xl/styles.xml', f'<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{num_formats}<cellXfs count="1"><xf numFmtId="{format_number}"/></cellXfs></styleSheet>')
    return output.getvalue()


def test_numeric_dates_preserve_explicit_midnight_from_style():
    for number, custom in [(22,None),(164,'yyyy-mm-dd hh:mm'),(165,'yyyy-mm-dd hh:mm:ss AM/PM')]:
        result = preview(numeric_workbook(number,custom),CATALOG,'Europe/Moscow')
        assert not result['errors'], result
        assert result['entries'][0]['end_at'].endswith('T00:00:00+03:00')
    for number, custom in [(14,None),(164,'yyyy-mm-dd'),(165,'yyyy-mm-dd "hours"')]:
        result = preview(numeric_workbook(number,custom),CATALOG,'Europe/Moscow')
        assert not result['errors'], result
        assert result['entries'][0]['end_at'].endswith('T23:59:59.999999+03:00')
    result = preview(numeric_workbook(999),CATALOG,'Europe/Moscow')
    assert result['errors'][0]['row']==2
    assert 'формат' in result['errors'][0]['message']
