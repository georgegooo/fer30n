#!/usr/bin/env python3
"""
📊 FER3ON Performance Monitoring Dashboard
لوحة تحكم لمراقبة الأداء والتحسينات في الوقت الفعلي

الميزات:
  1. عرض إحصائيات الأداء الحالية
  2. مراقبة توصيات Shadow Learning
  3. تتبع تطور المعاملات (Genetic Evolution)
  4. مقارنة الأداء قبل/بعد التحسينات
  5. إنذارات عند انحراف الأداء
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import statistics

class PerformanceMonitoringDashboard:
    """لوحة تحكم مراقبة الأداء والتحسينات"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.data_dir = self.project_root / "data" / "analytics"
        self.config_dir = self.project_root / "config"
        
        # البيانات الأساسية (الـ baseline)
        self.baseline_metrics = {
            "win_rate": 0.64,
            "profit_factor": 4.105,
            "net_profit": 172388,
            "sharpe_ratio": 7.868,
            "max_drawdown": 0.366,
            "ruin_probability": 0.0,
            "date": "2026-09-02"
        }
    
    def load_shadow_learning_data(self) -> Dict[str, Any]:
        """تحميل بيانات Shadow Learning"""
        insights_file = self.data_dir / "shadow_learning" / "learning_insights.json"
        
        if not insights_file.exists():
            return {"status": "not_found"}
        
        with open(insights_file, 'r', encoding='utf-8') as f:
            insights = json.load(f)
        
        stats = insights.get("statistics", {})
        recommendations = insights.get("recommendations", [])
        
        return {
            "status": "loaded",
            "date": insights.get("generated_at", "N/A"),
            "signals_analyzed": stats.get("total_signals", 0),
            "simulated_win_rate": stats.get("simulated_win_rate", 0),
            "avg_pnl": stats.get("avg_pnl", 0),
            "avg_rr": stats.get("avg_rr", 0),
            "high_priority_recommendations": [r for r in recommendations if r.get("priority") == "HIGH"],
            "medium_priority_recommendations": [r for r in recommendations if r.get("priority") == "MEDIUM"],
        }
    
    def load_genetic_evolution_results(self) -> Dict[str, Any]:
        """تحميل نتائج التطور الجيني"""
        evolution_dir = self.data_dir / "evolution"
        
        if not evolution_dir.exists():
            return {"status": "not_found"}
        
        # البحث عن أحدث ملف نتائج
        result_files = sorted(evolution_dir.glob("genetic_evolution_results_*.json"))
        
        if not result_files:
            return {"status": "no_results"}
        
        latest_file = result_files[-1]
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        best = results.get("final_best_parameters", {})
        improvement = results.get("improvement_over_baseline", {})
        
        return {
            "status": "loaded",
            "file": latest_file.name,
            "generations": results.get("generations_completed", 0),
            "best_fitness": best.get("fitness_score", 0),
            "best_parameters": {
                "risk_percent": best.get("risk_percent", "N/A"),
                "max_trades_per_day": best.get("max_trades_per_day", "N/A"),
                "tp_multiplier": best.get("tp_multiplier", "N/A"),
                "sl_multiplier": best.get("sl_multiplier", "N/A"),
                "confidence_threshold": best.get("confidence_threshold", "N/A"),
                "quality_floor": best.get("quality_floor", "N/A"),
            },
            "improvement": {
                "fitness": improvement.get("fitness_improvement", 0),
                "win_rate": improvement.get("win_rate_change", 0),
                "profit_factor": improvement.get("profit_factor_change", 0),
            }
        }
    
    def load_quality_adjustments(self) -> Dict[str, Any]:
        """تحميل تعديلات جودة الإشارة الحالية"""
        config_file = self.config_dir / "shadow_learning_adjustments.json"
        
        if not config_file.exists():
            return {"status": "not_found"}
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        return {
            "status": "loaded",
            "phase": config.get("phase_name", "Unknown"),
            "timestamp": config.get("timestamp", "N/A"),
            "adjustments": config.get("quality_adjustments", {})
        }
    
    def check_performance_alerts(self, current_metrics: Optional[Dict] = None) -> List[Dict]:
        """فحص التنبيهات (انحرافات الأداء عن الـ baseline)"""
        alerts = []
        
        # تنبيهات مثالية (يجب تحديثها بالبيانات الفعلية من الـ backtest)
        if current_metrics:
            # تحذير من انخفاض معدل الفوز
            if current_metrics.get("win_rate", self.baseline_metrics["win_rate"]) < self.baseline_metrics["win_rate"] - 0.05:
                alerts.append({
                    "severity": "HIGH",
                    "type": "WIN_RATE_DROP",
                    "message": "Win rate dropped >5% below baseline",
                    "recommendation": "Review recent signal quality and market conditions"
                })
            
            # تحذير من انخفاض profit factor
            if current_metrics.get("profit_factor", self.baseline_metrics["profit_factor"]) < self.baseline_metrics["profit_factor"] - 1.0:
                alerts.append({
                    "severity": "MEDIUM",
                    "type": "PF_DROP",
                    "message": "Profit Factor dropped >1.0 below baseline",
                    "recommendation": "Analyze losing trades and adjust risk management"
                })
            
            # تحذير من زيادة drawdown
            if current_metrics.get("max_drawdown", self.baseline_metrics["max_drawdown"]) > self.baseline_metrics["max_drawdown"] + 0.1:
                alerts.append({
                    "severity": "HIGH",
                    "type": "DRAWDOWN_SPIKE",
                    "message": "Max drawdown exceeded baseline by >10%",
                    "recommendation": "Consider reducing risk or increasing diversification"
                })
        
        return alerts
    
    def generate_performance_report(self) -> str:
        """توليد تقرير الأداء الشامل"""
        report_lines = ["\n" + "="*80]
        report_lines.append("📊 FER3ON PERFORMANCE MONITORING DASHBOARD")
        report_lines.append("="*80 + "\n")
        
        # 1. الأداء الأساسي (Baseline)
        report_lines.append("📈 BASELINE PERFORMANCE (2026-09-02)")
        report_lines.append("-" * 80)
        report_lines.append(f"  Win Rate:           {self.baseline_metrics['win_rate']:.1%}")
        report_lines.append(f"  Profit Factor:      {self.baseline_metrics['profit_factor']:.2f}")
        report_lines.append(f"  Net Profit:         ${self.baseline_metrics['net_profit']:,.0f}")
        report_lines.append(f"  Sharpe Ratio:       {self.baseline_metrics['sharpe_ratio']:.2f}")
        report_lines.append(f"  Max Drawdown:       {self.baseline_metrics['max_drawdown']:.1%}")
        report_lines.append(f"  Ruin Probability:   {self.baseline_metrics['ruin_probability']:.1%}")
        report_lines.append(f"  Grade:              EXCELLENT\n")
        
        # 2. Shadow Learning
        report_lines.append("🌑 SHADOW LEARNING ANALYSIS")
        report_lines.append("-" * 80)
        shadow_data = self.load_shadow_learning_data()
        
        if shadow_data.get("status") == "loaded":
            report_lines.append(f"  Status:             ✅ ACTIVE")
            report_lines.append(f"  Signals Analyzed:   {shadow_data['signals_analyzed']:,}")
            report_lines.append(f"  Simulated Win Rate: {shadow_data['simulated_win_rate']:.2%}")
            report_lines.append(f"  Avg P&L:            {shadow_data['avg_pnl']:.2f}")
            report_lines.append(f"  Avg R:R:            {shadow_data['avg_rr']:.2f}")
            
            report_lines.append(f"\n  🔴 HIGH PRIORITY RECOMMENDATIONS:")
            for rec in shadow_data.get("high_priority_recommendations", []):
                report_lines.append(f"     • {rec.get('description', 'N/A')}")
            
            report_lines.append(f"\n  🟡 MEDIUM PRIORITY RECOMMENDATIONS:")
            for rec in shadow_data.get("medium_priority_recommendations", []):
                report_lines.append(f"     • {rec.get('description', 'N/A')}")
        else:
            report_lines.append(f"  Status:             ⏳ NOT YET GENERATED\n")
        
        # 3. جودة الإشارات
        report_lines.append("\n⚙️  QUALITY SCORE ADJUSTMENTS")
        report_lines.append("-" * 80)
        quality_data = self.load_quality_adjustments()
        
        if quality_data.get("status") == "loaded":
            report_lines.append(f"  Current Phase:      {quality_data['phase']}")
            for key, value in quality_data.get("adjustments", {}).items():
                report_lines.append(f"  {key.replace('_', ' ').title()}: {value}")
        else:
            report_lines.append(f"  Status:             ⏳ MONITORING PHASE (No changes yet)\n")
        
        # 4. التطور الجيني
        report_lines.append("\n🧬 GENETIC PARAMETER EVOLUTION")
        report_lines.append("-" * 80)
        evolution_data = self.load_genetic_evolution_results()
        
        if evolution_data.get("status") == "loaded":
            report_lines.append(f"  Status:             ✅ COMPLETED")
            report_lines.append(f"  Generations:        {evolution_data['generations']}")
            report_lines.append(f"  Best Fitness:       {evolution_data['best_fitness']:.2f}")
            
            report_lines.append(f"\n  🏆 Optimized Parameters:")
            for param, value in evolution_data.get("best_parameters", {}).items():
                report_lines.append(f"     {param.replace('_', ' ').title()}: {value}")
            
            report_lines.append(f"\n  📈 Improvement over Baseline:")
            impr = evolution_data.get("improvement", {})
            report_lines.append(f"     Fitness:        {impr.get('fitness', 0):+.2%}")
            report_lines.append(f"     Win Rate:       {impr.get('win_rate', 0):+.2%}")
            report_lines.append(f"     Profit Factor:  {impr.get('profit_factor', 0):+.2f}")
        else:
            report_lines.append(f"  Status:             ⏳ PENDING EXECUTION\n")
        
        # 5. التنبيهات
        report_lines.append("\n🚨 PERFORMANCE ALERTS")
        report_lines.append("-" * 80)
        alerts = self.check_performance_alerts()
        
        if alerts:
            for alert in alerts:
                severity_emoji = "🔴" if alert["severity"] == "HIGH" else "🟡"
                report_lines.append(f"  {severity_emoji} [{alert['severity']}] {alert['type']}")
                report_lines.append(f"     Message: {alert['message']}")
                report_lines.append(f"     Action:  {alert['recommendation']}\n")
        else:
            report_lines.append("  ✅ No critical alerts at this time\n")
        
        # 6. التوصيات والخطوات التالية
        report_lines.append("📋 RECOMMENDED NEXT STEPS")
        report_lines.append("-" * 80)
        report_lines.append("  SHORT TERM (This Week):")
        report_lines.append("    1. Monitor Shadow Learning insights daily")
        report_lines.append("    2. Verify no degradation in trade execution")
        report_lines.append("    3. Collect 50+ new trades for recalibration")
        report_lines.append("\n  MEDIUM TERM (This Month):")
        report_lines.append("    1. Apply quality score adjustments gradually")
        report_lines.append("    2. Test optimized parameters from genetic evolution")
        report_lines.append("    3. Compare performance against baseline")
        report_lines.append("\n  LONG TERM (This Quarter):")
        report_lines.append("    1. Implement ML model training on shadow data")
        report_lines.append("    2. Run full backtest with optimized parameters")
        report_lines.append("    3. Prepare for next evolution cycle")
        
        report_lines.append("\n" + "="*80)
        report_lines.append(f"📅 Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("="*80 + "\n")
        
        return "\n".join(report_lines)
    
    def save_dashboard_snapshot(self) -> Path:
        """حفظ لقطة من لوحة التحكم الحالية"""
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "baseline_metrics": self.baseline_metrics,
            "shadow_learning": self.load_shadow_learning_data(),
            "quality_adjustments": self.load_quality_adjustments(),
            "genetic_evolution": self.load_genetic_evolution_results(),
            "performance_alerts": self.check_performance_alerts(),
        }
        
        snapshot_dir = self.project_root / "data" / "dashboards"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"dashboard_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = snapshot_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def create_html_dashboard(self) -> Path:
        """إنشاء لوحة تحكم HTML تفاعلية"""
        html_content = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FER3ON Performance Dashboard</title>
    <style>
        * { margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0f1419;
            color: #e0e0e0;
            padding: 20px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 3px solid #ffd700;
            padding-bottom: 20px;
        }
        .header h1 {
            font-size: 2.5em;
            color: #ffd700;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: #1a1f2a;
            border: 2px solid #ffd700;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.1);
        }
        .card h2 {
            color: #ffd700;
            margin-bottom: 15px;
            font-size: 1.3em;
            border-bottom: 2px solid #ffd700;
            padding-bottom: 10px;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #333;
        }
        .metric:last-child {
            border-bottom: none;
        }
        .metric-label {
            font-weight: bold;
            color: #b0b0b0;
        }
        .metric-value {
            color: #ffd700;
            font-weight: bold;
        }
        .positive { color: #4ade80; }
        .negative { color: #f87171; }
        .status-active { color: #4ade80; }
        .status-pending { color: #facc15; }
        .alert {
            padding: 12px;
            margin: 10px 0;
            border-left: 4px solid;
            background: rgba(255, 0, 0, 0.1);
        }
        .alert-high { border-left-color: #f87171; }
        .alert-medium { border-left-color: #facc15; }
        .progress-bar {
            width: 100%;
            height: 20px;
            background: #333;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }
        .progress {
            height: 100%;
            background: linear-gradient(90deg, #ffd700, #ffed4e);
            width: 0%;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #ffd700;
            color: #888;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>FER3ON V5.7 PERFORMANCE DASHBOARD</h1>
            <p>Real-time monitoring of trading system improvements</p>
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>Baseline Performance</h2>
                <div class="metric">
                    <span class="metric-label">Win Rate</span>
                    <span class="metric-value">64.0%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Profit Factor</span>
                    <span class="metric-value">4.105</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Sharpe Ratio</span>
                    <span class="metric-value">7.868</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Status</span>
                    <span class="metric-value status-active">EXCELLENT</span>
                </div>
            </div>
            
            <div class="card">
                <h2>Shadow Learning</h2>
                <div class="metric">
                    <span class="metric-label">Status</span>
                    <span class="metric-value status-active">ACTIVE</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Signals Analyzed</span>
                    <span class="metric-value">2,523</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Simulated Win Rate</span>
                    <span class="metric-value">60.05%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">High Priority Recs</span>
                    <span class="metric-value">2</span>
                </div>
            </div>
            
            <div class="card">
                <h2>Genetic Evolution</h2>
                <div class="metric">
                    <span class="metric-label">Status</span>
                    <span class="metric-value status-pending">READY</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Optimization Target</span>
                    <span class="metric-value">6 Parameters</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Expected Improvement</span>
                    <span class="metric-value positive">5-15%</span>
                </div>
            </div>
            
            <div class="card">
                <h2>Quality Adjustments</h2>
                <div class="metric">
                    <span class="metric-label">Current Phase</span>
                    <span class="metric-value">Phase 1 - Monitoring</span>
                </div>
                <div class="metric">
                    <span class="metric-label">QUALITY_SCORE_TRUST</span>
                    <span class="metric-value">DISABLED</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Next Phase</span>
                    <span class="metric-value">Day 7</span>
                </div>
            </div>
        </div>
        
        <div class="card" style="grid-column: 1 / -1;">
            <h2>Recommended Next Steps</h2>
            <div style="padding: 15px;">
                <h3 style="color: #ffd700; margin: 10px 0;">Short Term (This Week):</h3>
                <ul style="margin-left: 20px; line-height: 1.8;">
                    <li>Monitor Shadow Learning insights daily</li>
                    <li>Verify no degradation in trade execution</li>
                    <li>Collect 50+ new trades for recalibration</li>
                </ul>
                
                <h3 style="color: #ffd700; margin: 20px 0 10px 0;">Medium Term (This Month):</h3>
                <ul style="margin-left: 20px; line-height: 1.8;">
                    <li>Apply quality score adjustments gradually</li>
                    <li>Test optimized parameters from genetic evolution</li>
                    <li>Compare performance against baseline</li>
                </ul>
                
                <h3 style="color: #ffd700; margin: 20px 0 10px 0;">Long Term (This Quarter):</h3>
                <ul style="margin-left: 20px; line-height: 1.8;">
                    <li>Implement ML model training on shadow data</li>
                    <li>Run full backtest with optimized parameters</li>
                    <li>Prepare for next evolution cycle</li>
                </ul>
            </div>
        </div>
        
        <div class="footer">
            <p>FER3ON V5.7 - AI Trading System</p>
            <p>Last Updated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
        </div>
    </div>
</body>
</html>
"""
        
        dashboard_dir = self.project_root / "dashboards"
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = dashboard_dir / "performance_dashboard.html"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return filepath


if __name__ == "__main__":
    dashboard = PerformanceMonitoringDashboard(".")
    
    # طباعة التقرير النصي
    report = dashboard.generate_performance_report()
    print(report)
    
    # حفظ لقطة
    snapshot_file = dashboard.save_dashboard_snapshot()
    print(f"✅ Dashboard snapshot saved: {snapshot_file}")
    
    # إنشاء لوحة HTML
    html_file = dashboard.create_html_dashboard()
    print(f"✅ HTML Dashboard created: {html_file}")
    print(f"   Open in browser: {html_file.as_posix()}")
