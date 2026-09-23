"""Demo rewards ledger. Never fulfils real benefits or accepts client-side prices."""
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from .engine import next_grade, required_level

CATALOG = [
    {"id":"book","category":"work","title":"Книга для профессионального роста","cost":100,"icon":"📚"},
    {"id":"course","category":"work","title":"Сертификат на курс","cost":300,"icon":"🎓"},
    {"id":"merch","category":"self","title":"Фирменный термостакан","cost":200,"icon":"☕"},
    {"id":"subscription","category":"self","title":"Подписка на аудиокниги","cost":100,"icon":"🎧"},
    {"id":"cinema","category":"family","title":"Семейный поход в кино","cost":200,"icon":"🎬"},
    {"id":"workshop","category":"family","title":"Детский мастер-класс","cost":300,"icon":"🎨"},
    {"id":"aquapark","category":"family","title":"Семейный сертификат в аквапарк","cost":500,"icon":"🌊"},
]


def reward_amount(person, event, skills):
    if event.get("mandatory", False):
        return 0
    target = next_grade(person)
    units = 0
    for skill, rule in event["skill_gains"].items():
        current = person["skills"].get(skill, 0)
        gap = max(0, required_level(skills[skill],person) - current)
        units += min(gap, rule["gain"], max(0, rule["max_level"] - current))
    return units * 100


class Redemption(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    item_id: str = Field(min_length=1, max_length=80)
    request_id: str = Field(min_length=36, max_length=36)
    expected_epoch: int = Field(ge=1)


def register_rewards(app, store, employee_auth, demo_mode):
    def wallet(tx, owner):
        if not any(p['employee_id'] == owner for p in tx['data']['employees']):
            raise HTTPException(404, 'Profile absent')
        db = tx['db']
        balance = db.execute('SELECT COALESCE(SUM(amount),0) FROM coins WHERE owner=?', (owner,)).fetchone()[0]
        rows = db.execute('SELECT id,amount,event_id,item_id,created FROM coins WHERE owner=? ORDER BY id DESC LIMIT 100', (owner,)).fetchall()
        return {'balance':balance, 'epoch':db.execute('SELECT epoch FROM wallet_meta WHERE id=1').fetchone()[0],
                'catalog':CATALOG, 'demo_mode':True, 'redemption_enabled':demo_mode,
                'history':[dict(zip(['id','amount','event_id','item_id','created'], row)) for row in rows]}

    @app.get('/api/store')
    def get_wallet(owner=Depends(employee_auth)):
        with store.transaction() as tx:
            return wallet(tx, owner)

    @app.post('/api/store/redeem')
    def redeem(payload: Redemption, owner=Depends(employee_auth)):
        if not demo_mode:
            raise HTTPException(403, 'Demo exchange is disabled')
        try:
            request_id = str(UUID(payload.request_id))
        except ValueError:
            raise HTTPException(422, 'Invalid request identifier')
        with store.transaction() as tx:
            current = wallet(tx, owner)
            if payload.expected_epoch != current['epoch']:
                raise HTTPException(409, 'Store data changed; refresh the store')
            item = next((item for item in CATALOG if item['id'] == payload.item_id), None)
            if not item:
                raise HTTPException(404, 'Unknown reward')
            previous = tx['db'].execute('SELECT item_id FROM coins WHERE owner=? AND request_id=?', (owner,request_id)).fetchone()
            if previous:
                if previous[0] != item['id']:
                    raise HTTPException(409, 'Request identifier already used for another reward')
                return {'replayed':True,'wallet':current}
            if current['balance'] < item['cost']:
                raise HTTPException(409, 'Not enough Halyk Coins')
            tx['db'].execute('INSERT INTO coins(owner,amount,request_id,item_id) VALUES (?,?,?,?)', (owner,-item['cost'],request_id,item['id']))
            return {'replayed':False,'wallet':wallet(tx, owner)}
