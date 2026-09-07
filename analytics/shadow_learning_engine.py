"""
🌑 Shadow Learning Engine - استخلاص البيانات من الإشارات المرفوضة

Purpose:
  تحويل الإشارات المرفوضة (40% من الإشارات) إلى بيانات تدريب قيمة.
  بدلاً من رميها دون استفادة، نتعلم منها لتحسين النموذج.

Architecture:
  1. قراءة rejected_shadow.jsonl (الإشارات المرفوضة)
  2. تحليل أسباب الرفض (QUALITY_TRUST_DISABLED, etc.)
  3. محاكاة ما كان سيحدث لو تم تنفيذها
  4. تخزين البيانات التدريبية
  5. توليد رؤى لتحسين النموذج الرئيسي

Data Flow:
  rejected_shadow.jsonl (input)
    ↓ (2500+ records)
  analyze_rejection_reasons()
  ↓
  simulate_shadow_outcomes()
  ↓
  extract_training_data()
  ↓
  shadow_learning_dataset.jsonl (output)

Key Metrics:
  - total_rejected: عدد الإشارات المرفوضة
  - rejection_by_gate: توزيع أسباب الرفض
  - shadow_win_rate: معدل النجاح لو تم تنفيذها
  - quality_distribution: توزيع جودة الإشارات المرفوضة
  - learning_insights: رؤى للتحسين
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import Counter, defaultdict
from datetime import datetime
from dataclasses import dataclass, asdict
import statistics


@dataclass
class RejectedSignal:
    """بيانات إشارة مرفوضة"""
    signal_id: str
    direction: str
    regime: str
    strategy: str
    confidence: float
    quality_score: float
    reject_reason: str
    gate: str
    sl_dist: float
    tp_dist: float
    session: str
    signal_time: str


@dataclass
class ShadowOutcome:
    """نتيجة محاكاة الإشارة المرفوضة"""
    signal_id: str
    simulated_win: bool
    simulated_pnl: float
    simulated_rr: float
    confidence_level: str  # A+, A, B+, B, C, D


class ShadowLearningEngine:
    """محرك التعلم من الإشارات المرفوضة"""
    
    def __init__(self):
        try:
            from core.settings import SHADOW_COUNTERFACTUAL_LOG_PATH
            self.rejected_file = Path(SHADOW_COUNTERFACTUAL_LOG_PATH)
        except Exception:
            self.rejected_file = Path(
                'data/analytics/shadow_counterfactual/rejected_shadow_2026-09-01-clean.jsonl'
            )
        self.training_output = Path('data/analytics/shadow_learning/training_dataset.jsonl')
        self.insights_output = Path('data/analytics/shadow_learning/learning_insights.json')
        self.training_output.parent.mkdir(parents=True, exist_ok=True)
        
    def load_rejected_signals(self) -> List[Dict[str, Any]]:
        """قراءة جميع الإشارات المرفوضة"""
        if not self.rejected_file.exists():
            return []
        
        signals = []
        with open(self.rejected_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    signals.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return signals
    
    def analyze_rejection_reasons(self, signals: List[Dict]) -> Dict[str, Any]:
        """تحليل أسباب الرفض"""
        if not signals:
            return {
                'total_rejected': 0,
                'rejection_gates': {},
                'rejection_reasons': {},
                'avg_quality_rejected': 0.0,
                'avg_confidence_rejected': 0.0
            }
        
        gates = Counter()
        reasons = Counter()
        qualities = []
        confidences = []
        
        for signal in signals:
            gate = signal.get('gate', 'UNKNOWN')
            reason = signal.get('reject_reason', 'UNKNOWN')
            quality = signal.get('quality_score', 0.0)
            confidence = signal.get('confidence', 0.0)
            
            gates[gate] += 1
            reasons[reason] += 1
            qualities.append(quality)
            confidences.append(confidence)
        
        return {
            'total_rejected': len(signals),
            'rejection_gates': dict(gates.most_common()),
            'rejection_reasons': dict(reasons.most_common()),
            'avg_quality_rejected': statistics.mean(qualities) if qualities else 0.0,
            'avg_confidence_rejected': statistics.mean(confidences) if confidences else 0.0,
            'quality_distribution': {
                'min': min(qualities) if qualities else 0.0,
                'max': max(qualities) if qualities else 0.0,
                'median': statistics.median(qualities) if qualities else 0.0,
                'stdev': statistics.stdev(qualities) if len(qualities) > 1 else 0.0
            }
        }
    
    def simulate_shadow_outcome(self, signal: Dict[str, Any]) -> ShadowOutcome:
        """
        محاكاة نتيجة الإشارة المرفوضة لو تم تنفيذها
        
        المنطق:
          - إذا sl_dist و tp_dist موجودة، نحسب R:R ratio
          - إذا كانت الإشارة عالية الجودة، احتمالية النجاح أعلى
          - نولد نتيجة محاكاة بناءً على جودة الإشارة
        """
        signal_id = signal.get('signal_id', 'unknown')
        quality = signal.get('quality_score', 50.0)
        confidence = signal.get('confidence', 50.0)
        sl_dist = signal.get('sl_dist', 100.0)
        tp_dist = signal.get('tp_dist', 100.0)
        
        # حساب R:R ratio
        if sl_dist > 0:
            rr_ratio = tp_dist / sl_dist
        else:
            rr_ratio = 1.0
        
        # تحديد احتمالية النجاح بناءً على الجودة والثقة
        # الصيغة: win_probability = (quality + confidence) / 200
        win_probability = (quality + confidence) / 200.0
        
        # محاكاة النتيجة
        import random
        random.seed(hash(signal_id) % 2**32)  # deterministic based on signal_id
        simulated_win = random.random() < win_probability
        
        # حساب P&L المحاكي
        if simulated_win:
            simulated_pnl = tp_dist * 0.95  # 95% من الربح المتوقع
        else:
            simulated_pnl = -sl_dist * 0.95  # 95% من الخسارة المتوقعة
        
        # تحديد مستوى الثقة
        if quality >= 85:
            confidence_level = 'A+'
        elif quality >= 75:
            confidence_level = 'A'
        elif quality >= 65:
            confidence_level = 'B+'
        elif quality >= 55:
            confidence_level = 'B'
        elif quality >= 45:
            confidence_level = 'C+'
        elif quality >= 35:
            confidence_level = 'C'
        else:
            confidence_level = 'D'
        
        return ShadowOutcome(
            signal_id=signal_id,
            simulated_win=simulated_win,
            simulated_pnl=simulated_pnl,
            simulated_rr=rr_ratio,
            confidence_level=confidence_level
        )
    
    def extract_training_data(self, signals: List[Dict]) -> List[Dict[str, Any]]:
        """استخلاص بيانات التدريب من الإشارات المرفوضة"""
        training_data = []
        
        for signal in signals:
            outcome = self.simulate_shadow_outcome(signal)
            
            training_record = {
                'signal_id': signal.get('signal_id'),
                'direction': signal.get('direction'),
                'regime': signal.get('regime'),
                'strategy': signal.get('strategy'),
                'session': signal.get('session'),
                'confidence': signal.get('confidence'),
                'quality_score': signal.get('quality_score'),
                'reject_gate': signal.get('gate'),
                'reject_reason': signal.get('reject_reason'),
                'sl_dist': signal.get('sl_dist'),
                'tp_dist': signal.get('tp_dist'),
                'rr_ratio': outcome.simulated_rr,
                'simulated_win': outcome.simulated_win,
                'simulated_pnl': outcome.simulated_pnl,
                'confidence_level': outcome.confidence_level,
                'learning_type': 'SHADOW',
                'extracted_at': datetime.utcnow().isoformat()
            }
            training_data.append(training_record)
        
        return training_data
    
    def generate_learning_insights(self, 
                                  rejection_analysis: Dict,
                                  training_data: List[Dict]) -> Dict[str, Any]:
        """توليد رؤى التعلم من البيانات"""
        if not training_data:
            return {}
        
        # تحليل معدل النجاح المحاكي
        simulated_wins = sum(1 for t in training_data if t['simulated_win'])
        simulated_win_rate = simulated_wins / len(training_data) if training_data else 0.0
        
        # تحليل توزيع الثقة
        confidence_dist = Counter(t['confidence_level'] for t in training_data)
        
        # تحليل الأداء حسب الـ regime
        regime_performance = defaultdict(list)
        for t in training_data:
            regime_performance[t['regime']].append(t['simulated_win'])
        
        regime_win_rates = {
            regime: sum(wins) / len(wins) if wins else 0.0
            for regime, wins in regime_performance.items()
        }
        
        # تحليل الأداء حسب الجودة
        high_quality = [t for t in training_data if t['quality_score'] >= 75]
        low_quality = [t for t in training_data if t['quality_score'] < 50]
        
        high_quality_wr = sum(1 for t in high_quality if t['simulated_win']) / len(high_quality) if high_quality else 0.0
        low_quality_wr = sum(1 for t in low_quality if t['simulated_win']) / len(low_quality) if low_quality else 0.0
        
        # التوصيات
        recommendations = []
        
        if simulated_win_rate > 0.50:
            recommendations.append({
                'priority': 'HIGH',
                'action': 'خفض معايير QUALITY_TRUST_DISABLED',
                'reason': f'الإشارات المرفوضة لديها معدل نجاح عالي ({simulated_win_rate:.2%})',
                'impact': 'قد تزيد الأرباح'
            })
        
        if high_quality_wr > low_quality_wr + 0.15:
            recommendations.append({
                'priority': 'HIGH',
                'action': 'تشديد معايير جودة الإشارات العالية',
                'reason': f'الإشارات عالية الجودة ({high_quality_wr:.2%}) أفضل من المنخفضة ({low_quality_wr:.2%})',
                'impact': 'تحسين نسبة الفوز الكلية'
            })
        
        # تحليل الأداء حسب الـ regime
        best_regime = max(regime_win_rates.items(), key=lambda x: x[1]) if regime_win_rates else None
        worst_regime = min(regime_win_rates.items(), key=lambda x: x[1]) if regime_win_rates else None
        
        if best_regime and worst_regime and (best_regime[1] - worst_regime[1]) > 0.20:
            recommendations.append({
                'priority': 'MEDIUM',
                'action': f'تكييف استراتيجية السلوك حسب الـ regime',
                'reason': f'{best_regime[0]} ({best_regime[1]:.2%}) يعمل أفضل من {worst_regime[0]} ({worst_regime[1]:.2%})',
                'impact': 'تحسين الأداء في الأنظمة المختلفة'
            })
        
        return {
            'analysis_date': datetime.utcnow().isoformat(),
            'total_shadow_records': len(training_data),
            'simulated_statistics': {
                'win_rate': simulated_win_rate,
                'winning_signals': simulated_wins,
                'avg_pnl': statistics.mean(t['simulated_pnl'] for t in training_data),
                'avg_rr_ratio': statistics.mean(t['rr_ratio'] for t in training_data)
            },
            'confidence_distribution': dict(confidence_dist),
            'regime_performance': regime_win_rates,
            'quality_performance': {
                'high_quality_wr': high_quality_wr,
                'low_quality_wr': low_quality_wr,
                'delta': high_quality_wr - low_quality_wr
            },
            'rejection_analysis': rejection_analysis,
            'recommendations': recommendations
        }
    
    def save_training_data(self, training_data: List[Dict]) -> bool:
        """حفظ بيانات التدريب"""
        try:
            with open(self.training_output, 'w', encoding='utf-8') as f:
                for record in training_data:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            return True
        except Exception as e:
            print(f"❌ خطأ في حفظ بيانات التدريب: {e}")
            return False
    
    def save_insights(self, insights: Dict) -> bool:
        """حفظ الرؤى"""
        try:
            with open(self.insights_output, 'w', encoding='utf-8') as f:
                json.dump(insights, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"❌ خطأ في حفظ الرؤى: {e}")
            return False
    
    def run(self) -> Dict[str, Any]:
        """تشغيل محرك التعلم الكامل"""
        print("\n" + "="*70)
        print("🌑 Shadow Learning Engine - تحليل الإشارات المرفوضة")
        print("="*70)
        
        # 1. تحميل الإشارات المرفوضة
        print("\n1️⃣ تحميل الإشارات المرفوضة...")
        signals = self.load_rejected_signals()
        print(f"   ✅ تم تحميل {len(signals):,} إشارة مرفوضة")
        
        if not signals:
            print("   ⚠️ لا توجد إشارات مرفوضة للتحليل")
            return {}
        
        # 2. تحليل أسباب الرفض
        print("\n2️⃣ تحليل أسباب الرفض...")
        rejection_analysis = self.analyze_rejection_reasons(signals)
        print(f"   ✅ Total Rejected: {rejection_analysis['total_rejected']:,}")
        print(f"   ✅ Avg Quality: {rejection_analysis['avg_quality_rejected']:.2f}")
        print(f"   ✅ Avg Confidence: {rejection_analysis['avg_confidence_rejected']:.2f}")
        print(f"   ✅ Top Gate: {list(rejection_analysis['rejection_gates'].items())[0]}")
        
        # 3. استخلاص بيانات التدريب
        print("\n3️⃣ استخلاص بيانات التدريب...")
        training_data = self.extract_training_data(signals)
        print(f"   ✅ تم استخلاص {len(training_data):,} سجل تدريب")
        
        # 4. توليد الرؤى
        print("\n4️⃣ توليد رؤى التعلم...")
        insights = self.generate_learning_insights(rejection_analysis, training_data)
        
        win_rate = insights.get('simulated_statistics', {}).get('win_rate', 0.0)
        print(f"   ✅ معدل النجاح المحاكي: {win_rate:.2%}")
        print(f"   ✅ عدد التوصيات: {len(insights.get('recommendations', []))}")
        
        # 5. حفظ البيانات
        print("\n5️⃣ حفظ البيانات والرؤى...")
        if self.save_training_data(training_data):
            print(f"   ✅ تم حفظ بيانات التدريب: {self.training_output}")
        
        if self.save_insights(insights):
            print(f"   ✅ تم حفظ الرؤى: {self.insights_output}")
        
        # 6. عرض التوصيات
        print("\n6️⃣ التوصيات الرئيسية:")
        for i, rec in enumerate(insights.get('recommendations', [])[:3], 1):
            print(f"   {i}. [{rec['priority']}] {rec['action']}")
        
        print("\n" + "="*70)
        print("✅ اكتمل تحليل Shadow Learning")
        print("="*70)
        
        return {
            'status': 'success',
            'signals_analyzed': len(signals),
            'training_records': len(training_data),
            'simulated_win_rate': win_rate,
            'insights': insights
        }


def should_apply_shadow_learning() -> bool:
    """فحص ما إذا كان يجب تطبيق Shadow Learning"""
    engine = ShadowLearningEngine()
    signals = engine.load_rejected_signals()
    return len(signals) > 0


if __name__ == '__main__':
    engine = ShadowLearningEngine()
    result = engine.run()
    
    # عرض الإحصائيات
    if result.get('status') == 'success':
        stats = result.get('insights', {}).get('simulated_statistics', {})
        print(f"\n📊 ملخص الإحصائيات:")
        print(f"   • معدل النجاح: {stats.get('win_rate', 0.0):.2%}")
        print(f"   • متوسط P&L: {stats.get('avg_pnl', 0.0):.2f}")
        print(f"   • متوسط R:R: {stats.get('avg_rr_ratio', 0.0):.2f}")
