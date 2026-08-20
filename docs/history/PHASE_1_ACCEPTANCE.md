# FER3ON V3.5 — PHASE-1 ACCEPTANCE GATE

## القبول النهائي لتعديلات Phase-1

لا يتم اعتماد أي تعديل قبل نجاح جميع هذه الاختبارات:

| # | الاختبار | الملف |
|---|---|---|
| 1 | Risk Consistency         | `tests/test_risk_consistency.py` |
| 2 | Authority Isolation      | `tests/test_authority_isolation.py` |
| 3 | Truth Layer              | `tests/test_truth_layer.py` |
| 4 | Micro Stability          | `tests/test_micro_stability.py` |
| 5 | SMC Diagnostic           | `tests/test_smc_diagnostic.py` |
| 6 | Execution Verification   | `tests/test_live_execution.py` |
| 7 | Performance Validation   | `tests/test_performance_validation.py` |

## تشغيل الكل

```bash
python tools/phase1_acceptance.py
```

## الهدف المعماري

* زيادة عدد الفرص المنفذة.
* تقليل الرفض الخاطئ.
* الحفاظ على الانضباط المؤسسي.
* عدم زيادة الـ Drawdown بصورة جوهرية.
* عدم تحويل FER3ON إلى نظام تداول متهور.

## Forbidden Actions

ممنوع على Authority:

* رفض صفقة فقط بسبب اختلاف استراتيجية أخرى معها.
  مثال: `DAILY = BUY, SCALP = SELL` هذا ليس Conflict — هذا Portfolio Diversification.
* قرار الاتجاه BUY/SELL.

ممنوع على ML (طالما PARTIAL):

* BLOCK
* REJECT
* OVERRIDE

مسموح فقط:

* BOOST أو PENALTY حتى ±5 نقاط.

## Priority Roadmap

### Phase 1 (تم)
1. إزالة اختناق Authority
2. توحيد Risk
3. تهدئة MICRO بنسبة 10%
4. إنشاء Truth Layer
5. جعل ML Advisor فقط

### Phase 2 (لاحق)
1. جمع بيانات حقيقية
2. تحليل ربحية كل Strategy
3. تحليل SMC Diagnostics
4. تحديد نقاط الضعف الفعلية

### Phase 3 (لاحق)
1. بناء XGB الحقيقي
2. بناء RL الحقيقي
3. Walk Forward Testing
4. Live Learning Validation
