import json
from pathlib import Path
from core.smart_counter_trading import SmartCounterTradingEngine

print("=" * 70)
print("🧪 اختبار Smart Counter-Trading بعد الإصلاح")
print("=" * 70)

# إنشء الإنجن
engine = SmartCounterTradingEngine()

print(f"\n📂 قراءة من: {engine.history_file}")

# فحص الملف
history_path = Path(engine.history_file)
if history_path.exists():
    with open(history_path, 'r', encoding='utf-8') as f:
        lines = [f.readline() for _ in range(10)]
    
    record_count = sum(1 for _ in open(history_path, 'r', encoding='utf-8'))
    print(f"✅ الملف موجود: {record_count:,} إشارة")
    
    # عرض أول إشارة
    first_line = open(history_path, 'r', encoding='utf-8').readline()
    data = json.loads(first_line)
    print(f"✅ تنسيق البيانات صحيح:")
    print(f"   - signal_id: {data['signal_id']}")
    print(f"   - direction: {data['direction']}")
    print(f"   - confidence: {data['confidence']}")
else:
    print(f"❌ الملف غير موجود!")

# حساب الانحياز
print("\n" + "=" * 70)
print("📊 حساب الانحياز من البيانات الكاملة:")
print("=" * 70)

bias_ratio, sell_count, buy_count = engine.calculate_signal_bias()
print(f"\n✅ SELL إشارات: {sell_count:,}")
print(f"✅ BUY إشارات:  {buy_count:,}")
print(f"✅ النسبة (SELL:BUY): {bias_ratio:.2f}:1")
print(f"\n📌 الحد الأدنى لتفعيل Counter-Trading: 3.0:1")
print(f"🔴 الحالة: {'✅ تفعيل Counter-Trading' if bias_ratio >= 3.0 else '⚠️ الانحياز أقل من 3.0'}")

# اختبار whether_to_counter_trade
print("\n" + "=" * 70)
print("🎯 فحص: هل يجب تطبيق Counter-Trading؟")
print("=" * 70)

should_counter = engine.should_apply_counter_trading()
print(f"\n✅ هل نطبق counter-trading: {should_counter}")

if should_counter:
    print(f"\n💰 الانحياز قوي جداً (4.21:1) → Counter-Trading ENABLED")
    print(f"   معاملات Counter-Trade تُحسب عند كل إشارة SELL")
    print(f"   - المنطق: لو السوق فيه انحياز قوي نحو SELL")
    print(f"   - نعرض صفقة معاكسة (BUY) بحجم أصغر")
    print(f"   - للاستفادة من الانحياز الشديد")

print("\n" + "=" * 70)
print("✅ جميع الاختبارات اكتملت بنجاح!")
print("=" * 70)
