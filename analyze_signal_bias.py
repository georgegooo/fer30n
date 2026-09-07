#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تحليل انحياز SELL/BUY في البيانات الحقيقية
"""

import json
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def analyze_signal_bias():
    """تحليل نسبة SELL/BUY في البيانات"""
    
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
    
    # قراءة البيانات
    signals = defaultdict(int)
    regimes = defaultdict(lambda: defaultdict(int))
    sessions = defaultdict(lambda: defaultdict(int))
    strategies = defaultdict(lambda: defaultdict(int))
    
    total_records = 0
    
    try:
        with open(rejected_shadow_path, 'r', encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                    
                try:
                    record = json.loads(line)
                    total_records += 1
                    
                    direction = record.get('direction', 'UNKNOWN')
                    regime = record.get('regime', 'UNKNOWN')
                    session = record.get('session', 'UNKNOWN')
                    strategy = record.get('strategy', 'UNKNOWN')
                    
                    # إحصائيات عامة
                    signals[direction] += 1
                    
                    # حسب الـ regime
                    regimes[regime][direction] += 1
                    
                    # حسب الـ session
                    sessions[session][direction] += 1
                    
                    # حسب الـ strategy
                    strategies[strategy][direction] += 1
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️  خطأ في السطر {line_no}: {e}")
                    continue
    except Exception as e:
        print(f"❌ خطأ في القراءة: {e}")
        return
    
    # الطباعة
    print(f"\n{'='*70}")
    print(f"تحليل الانحياز SELL/BUY")
    print(f"{'='*70}")
    print(f"\n📊 الإحصائيات العامة:")
    print(f"إجمالي السجلات: {total_records}")
    print(f"\nنسبة الإشارات:")
    
    total_buys = signals.get('BUY', 0)
    total_sells = signals.get('SELL', 0)
    
    if total_buys + total_sells > 0:
        buy_pct = (total_buys / (total_buys + total_sells)) * 100
        sell_pct = (total_sells / (total_buys + total_sells)) * 100
        ratio = total_sells / max(total_buys, 1)
        
        print(f"  BUY:  {total_buys:6d} ({buy_pct:5.2f}%)")
        print(f"  SELL: {total_sells:6d} ({sell_pct:5.2f}%)")
        print(f"  النسبة (SELL:BUY): {ratio:.2f}:1")
    
    # تحليل حسب الـ regime
    print(f"\n📍 تفصيل حسب Regime:")
    for regime in sorted(regimes.keys()):
        buy = regimes[regime].get('BUY', 0)
        sell = regimes[regime].get('SELL', 0)
        total = buy + sell
        if total > 0:
            ratio = sell / max(buy, 1)
            print(f"  {regime:12s}: BUY={buy:4d} SELL={sell:4d} (ratio={ratio:.2f}:1, {(sell/total)*100:.1f}% SELL)")
    
    # تحليل حسب الـ session
    print(f"\n🌍 تفصيل حسب Session:")
    for session in sorted(sessions.keys()):
        buy = sessions[session].get('BUY', 0)
        sell = sessions[session].get('SELL', 0)
        total = buy + sell
        if total > 0:
            ratio = sell / max(buy, 1)
            print(f"  {session:12s}: BUY={buy:4d} SELL={sell:4d} (ratio={ratio:.2f}:1, {(sell/total)*100:.1f}% SELL)")
    
    # تحليل حسب الـ strategy
    print(f"\n🎯 تفصيل حسب Strategy:")
    for strategy in sorted(strategies.keys()):
        buy = strategies[strategy].get('BUY', 0)
        sell = strategies[strategy].get('SELL', 0)
        total = buy + sell
        if total > 0:
            ratio = sell / max(buy, 1)
            print(f"  {strategy:12s}: BUY={buy:4d} SELL={sell:4d} (ratio={ratio:.2f}:1, {(sell/total)*100:.1f}% SELL)")
    
    # تحليل معقد: الجمع بين dimension اثنين
    print(f"\n🔬 تحليل معقد (Regime × Session):")
    complex_analysis = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    
    try:
        with open(rejected_shadow_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    direction = record.get('direction', 'UNKNOWN')
                    regime = record.get('regime', 'UNKNOWN')
                    session = record.get('session', 'UNKNOWN')
                    complex_analysis[regime][session][direction] += 1
                except:
                    pass
    except:
        pass
    
    for regime in sorted(complex_analysis.keys()):
        print(f"\n  {regime}:")
        for session in sorted(complex_analysis[regime].keys()):
            buy = complex_analysis[regime][session].get('BUY', 0)
            sell = complex_analysis[regime][session].get('SELL', 0)
            total = buy + sell
            if total > 0 and total >= 5:  # فقط الـ combos التي لها 5 أو أكثر
                ratio = sell / max(buy, 1)
                print(f"    {session:10s}: BUY={buy:3d} SELL={sell:3d} (ratio={ratio:.2f}:1)")
    
    print(f"\n{'='*70}\n")

if __name__ == '__main__':
    analyze_signal_bias()
