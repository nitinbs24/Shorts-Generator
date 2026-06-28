from shared.db import init_db
from channel_b.config import fetch_topic, _load_topic_bank

init_db()
bank = _load_topic_bank()
print(f'[OK] Topic bank loaded: {len(bank)} topics')

cats = {}
for e in bank:
    cats[e['category']] = cats.get(e['category'], 0) + 1
for cat, count in sorted(cats.items()):
    print(f'     {cat}: {count} topics')

topic = fetch_topic()
print(f'[OK] Topic selected: "{topic}"')
print('[OK] === Channel B topic bank: PASSED ===')
