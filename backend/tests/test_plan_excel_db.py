from test_accounts import accounts, project
from app.application.plan_excel import workbook, HEADERS


def test_excel_roundtrip_authorization_conflict_and_atomicity(accounts):
    make, store = accounts
    owner, _ = make()
    viewer, user = make()
    outsider, _ = make()
    own = project(owner)
    zone = own['default_zone_id']
    path = f'/zones/{zone}/plan'
    invitation = owner.post(f'/projects/{own["id"]}/invitations', json={'email': user['email'], 'role':'viewer'}).json()
    assert viewer.post('/invitations/accept', json={'token':invitation['token']}).status_code==200
    template = owner.get(path+'/template.xlsx?tutorial=true')
    assert template.status_code==200
    assert outsider.get(path+'/template.xlsx').status_code==404
    assert viewer.get(path+'/template.xlsx').status_code==200
    assert viewer.post(path+'/import-preview',content=template.content).status_code==403
    assert outsider.post(path+'/import-preview',content=template.content).status_code==404
    preview = owner.post(path+'/import-preview',content=template.content)
    assert preview.status_code==200, preview.text
    imported = preview.json()
    assert not imported['errors'], imported
    assert owner.get(path).json()['revision_number']==0
    body = {'expected_revision':imported['expected_revision'],'entries':imported['entries']}
    assert owner.put(path,json=body).status_code==200
    assert owner.get(path+'?revision=1').json()['revision_number']==1
    assert owner.put(path,json=body).status_code==409
    assert viewer.put(path,json=body).status_code==403
    assert owner.get(path).json()['revision_number']==1
    invalid = workbook([('План',[HEADERS,[imported['entries'][0]['catalog_work_id'],'2026-10-19','2026-10-20'],['unknown','bad','bad']])])
    bad_preview = owner.post(path+'/import-preview',content=invalid).json()
    assert bad_preview['errors'][0]['row']==3
    assert owner.get(path).json()['revision_number']==1
    bad_body = {'expected_revision':1,'entries':[imported['entries'][0],{'catalog_work_id':'invalid'}]}
    assert owner.put(path,json=bad_body).status_code==400
    assert owner.get(path).json()['revision_number']==1
    assert owner.post(path+'/import-preview',content=b'broken').json()['errors']
