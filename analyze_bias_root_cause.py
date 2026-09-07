#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تحليل معمق لسبب الانحياز SELL/BUY
"""

import json
from pathlib import Path
from collections import defaultdict

def analyze_bias_root_cause():
    """تحليل الأسباب الجذرية للانحياز"""
    
    try:
        from core.settings import SHADOW_COUNTERFACTUAL_LOG_PATH
        rejected_shadow_path = Path(SHADOW_COUNTERFACTUAL_LOG_PATH)
    except Exception:
        rejected_shadow_path = Path(
            'data/analytics/shadow_counterfactual/rejected_shadow_2026-09-01-clean.jsonl'
        )
    
    if not rejected_shadow_path.exists():
        print(f"❌ الملف غير موجود: {rejected_shadow_path}")
        return
    
    # تحليل الرفض والقيم الأخرى
    reject_reasons = defaultdict(int)
    quality_scores = []
    confidence_scores = []
    directions = defaultdict(list)  # direction -> list of quality scores
    
    try:
        with open(rejected_shadow_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    
                    # سبب الرفض
                    reject_reason = record.get('reject_reason', 'NONE')
                    reject_reasons[reject_reason] += 1
                    
                    # جودة الإشارة
                    quality = float(record.get('quality_score', 0) or 0)
                    confidence = float(record.get('confidence', 0) or 0)
                    quality_scores.append(quality)
                    confidence_scores.append(confidence)
                    
                    # ربط الاتجاه بالجودة
                    direction = record.get('direction', 'UNKNOWN')
                    directions[direction].append(quality)
                    
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return
    
    print(f"\n{'='*70}")
    print(f"تحليل الأسباب الجذرية للانحياز SELL/BUY")
    print(f"{'='*70}")
    
    # أسباب الرفض
    print(f"\n📋 أسباب الرفض (Top 10):")
    top_reasons = sorted(reject_reasons.items(), key=lambda x: x[1], reverse=True)[:10]
    for reason, count in top_reasons:
        pct = (count / sum(reject_reasons.values())) * 100
        print(f"  {reason:40s}: {count:4d} ({pct:5.2f}%)")
    
    # جودة الإشارات
    if quality_scores:
        avg_quality = sum(quality_scores) / len(quality_scores)
        print(f"\n📊 جودة الإشارات:")
        print(f"  المتوسط: {avg_quality:.2f}")
        print(f"  الحد الأدنى: {min(quality_scores):.2f}")
        print(f"  الحد الأقصى: {max(quality_scores):.2f}")
    
    # مقارنة جودة BUY vs SELL
    print(f"\n🔍 مقارنة جودة الإشارات:")
    for direction in ['BUY', 'SELL']:
        if direction in directions and directions[direction]:
            scores = directions[direction]
            avg_score = sum(scores) / len(scores)
            print(f"  {direction}: متوسط جودة = {avg_score:.2f} (عدد = {len(scores)})")
    
    # البحث عن الأنماط
    print(f"\n🔎 الأنماط المكتشفة:")
    
    # إذا كانت إشارات SELL لها جودة أعلى بشكل متسق، قد تكون طبيعية
    if 'BUY' in directions and 'SELL' in directions:
        buy_avg = sum(directions['BUY']) / len(directions['BUY'])
        sell_avg = sum(directions['SELL']) / len(directions['SELL'])
        diff = sell_avg - buy_avg
        
        if diff > 1:
            print(f"  ⚠️  إشارات SELL لها جودة أعلى بمتوسط {diff:.2f}")
            print(f"      → قد يكون السوق هابطًا بالفعل (الذهب متقلب)")
        elif diff < -1:
            print(f"  ⚠️  إشارات BUY لها جودة أعلى، لكن البوت يختار SELL أكثر")
            print(f"      → قد يكون هناك bias في منطق الاختيار")
        else:
            print(f"  ✓ الجودة متقاربة (فرق = {diff:.2f})")
    
    # السبب الكبير
    print(f"\n🎯 السبب الجذري المحتمل:")
    
    # حساب نسبة سبب الرفض الأساسي
    main_reason = max(reject_reasons.items(), key=lambda x: x[1])[0] if reject_reasons else "UNKNOWN"
    main_reason_count = reject_reasons.get(main_reason, 0)
    main_reason_pct = (main_reason_count / sum(reject_reasons.values())) * 100 if reject_reasons else 0
    
    print(f"\n  السبب الأساسي: {main_reason}")
    print(f"  النسبة: {main_reason_pct:.1f}% من الرفضات")
    
    if "QUALITY_TRUST_DISABLED" in reject_reasons or "QUALITY" in main_reason:
        print(f"  ✓ السبب واضح: بوابة الجودة معطلة!")
        print(f"    → الأمر يحتاج إلى تفعيل بوابة الجودة الحقيقية")
    
    if "BOS" in main_reason or "CHOCH" in main_reason or "STRUCTURE" in main_reason:
        print(f"  ✓ السبب: منطق الهيكل السعري يميل نحو SELL")
        print(f"    → قد يكون السوق هابطًا حقًا في فترة الاختبار")
    
    print(f"\n{'='*70}\n")

if __name__ == '__main__':
    analyze_bias_root_cause()
