"""Best-effort ownership written only inside the first accepting transaction."""
from uuid import UUID, uuid4
from sqlalchemy import text


def touch_browser(connection, browser, now):
    connection.execute(text('SELECT pg_advisory_xact_lock(:lock)'), {'lock': browser.int % (2**63)})
    session = uuid4()
    connection.execute(text('''INSERT INTO anonymous_browsers(id,session_id,first_at,last_at)
        VALUES (:browser,:session,:now,:now) ON CONFLICT(id) DO NOTHING'''),
        {'browser': browser, 'session': session, 'now': now})
    row = connection.execute(text("SELECT session_id,last_at <= :now-interval '30 minutes' AS expired FROM anonymous_browsers WHERE id=:id FOR UPDATE"), {'id': browser, 'now': now}).first()
    session = session if row.expired else row.session_id
    connection.execute(text('''UPDATE anonymous_browsers SET last_at=greatest(last_at,:now),session_id=:session WHERE id=:browser'''),
                       {'browser': browser, 'session': session, 'now': now})
    connection.execute(text('''INSERT INTO anonymous_sessions(id,browser_id,started_at) VALUES (:session,:browser,:now)
        ON CONFLICT(id) DO NOTHING'''), {'browser': browser, 'session': session, 'now': now})
    return session


def attribute(connection, browser_id, kind, object_id):
    try:
        browser = UUID(browser_id)
        with connection.begin_nested():
            now = connection.execute(text('SELECT transaction_timestamp()')).scalar_one()
            touch_browser(connection, browser, now)
            connection.execute(text('''INSERT INTO activity_attribution(kind,object_id,browser_id)
                VALUES (:kind,:object,:browser) ON CONFLICT(kind,object_id) DO NOTHING'''),
                {'kind':kind,'object':object_id,'browser':browser})
    except Exception:
        pass
