import json
from pathlib import Path
from collections import Counter

print("=" * 70)
print("📊 فحص نسب SELL/BUY من البيانات الكاملة")
print("=" * 70)

# قراءة البيانات
ledger_path = Path('data/analytics/decision_ledger/decisions.jsonl')

if not ledger_path.exists():
    print(f"❌ الملف غير موجود: {ledger_path}")
    exit(1)

directions = []
strategies = {
    'SELL': [],
    'BUY': []
}

with open(ledger_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            direction = data.get('direction', 'UNKNOWN')
            directions.append(direction)
            
            strategy = data.get('strategy', 'UNKNOWN')
            if direction in strategies:
                strategies[direction].append(strategy)
        except json.JSONDecodeError:
            pass

total = len(directions)
sell_count = directions.count('SELL')
buy_count = directions.count('BUY')

print(f"\n📈 إجمالي الإشارات: {total:,}")
print(f"📍 SELL إشارات: {sell_count:,} ({sell_count/total*100:.2f}%)")
print(f"📍 BUY إشارات:  {buy_count:,} ({buy_count/total*100:.2f}%)")
print(f"📍 النسبة (SELL:BUY): {sell_count/buy_count:.2f}:1" if buy_count > 0 else "🔴 لا توجد إشارات BUY!")

print("\n" + "=" * 70)
print("🔍 تحليل الانحياز:")
print("=" * 70)

ratio = sell_count / buy_count if buy_count > 0 else float('inf')

print(f"\n✅ الانحياز الحالي: {ratio:.2f}:1")
print(f"❓ الهدف السابق: ~1.85:1 (توازن أفضل)")
print(f"📌 التصنيف:")

if ratio > 4.0:
    print(f"   🔴 VERY HIGH (>4:1) - الانحياز شديد جداً")
elif ratio > 3.0:
    print(f"   🟠 HIGH (3-4:1) - الانحياز قوي")
elif ratio > 2.0:
    print(f"   🟡 MODERATE (2-3:1) - الانحياز معتدل")
elif ratio > 1.5:
    print(f"   🟢 BALANCED (1.5-2:1) - توازن جيد")
else:
    print(f"   ✅ VERY BALANCED (<1.5:1) - توازن ممتاز")

print("\n" + "=" * 70)
print("📋 توزيع الاستراتيجيات:")
print("=" * 70)

sell_strategies = Counter(strategies['SELL'])
buy_strategies = Counter(strategies['BUY'])

print(f"\n📍 SELL الاستراتيجيات:")
for strategy, count in sell_strategies.most_common():
    print(f"   - {strategy}: {count:,} ({count/len(strategies['SELL'])*100:.1f}%)")

print(f"\n📍 BUY الاستراتيجيات:")
for strategy, count in buy_strategies.most_common():
    print(f"   - {strategy}: {count:,} ({count/len(strategies['BUY'])*100:.1f}%)")

print("\n" + "=" * 70)
print("✅ التحليل مكتمل")
print("=" * 70)
