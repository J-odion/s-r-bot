import os
import pandas as pd
from datetime import datetime

class AdvancedReporter:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def _calculate_metrics(self, trades):
        """Calculates core and risk metrics for a list of trades."""
        total_trades = len(trades)
        if total_trades == 0:
            return None
            
        wins = [t for t in trades if t['profit'] > 0]
        losses = [t for t in trades if t['profit'] <= 0]
        
        win_rate = len(wins) / total_trades
        
        total_profit = sum(t['profit'] for t in wins)
        total_loss = abs(sum(t['profit'] for t in losses))
        
        avg_win = total_profit / len(wins) if wins else 0
        avg_loss = total_loss / len(losses) if losses else 0
        
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Breakeven WR implied by realized RR
        # RR = Avg Win / Avg Loss
        if avg_loss > 0:
            realized_rr = avg_win / avg_loss
            breakeven_wr = 1 / (1 + realized_rr)
        else:
            realized_rr = float('inf')
            breakeven_wr = 0.0
            
        # Expectancy per trade: (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        max_win = max([t['profit'] for t in wins]) if wins else 0
        max_loss = min([t['profit'] for t in losses]) if losses else 0
        
        # Calculate Independent Trades (unique parent_signal_id)
        independent_ids = set()
        for t in trades:
            independent_ids.add(t.get('parent_signal_id', 'unknown'))
        independent_trade_count = len(independent_ids)
        
        # Calculate Drawdown and Longest Losing Streak
        cumulative_profit = 0
        peak = 0
        max_dd = 0
        current_streak = 0
        max_streak = 0
        
        for t in sorted(trades, key=lambda x: x['time']):
            cumulative_profit += t['profit']
            if cumulative_profit > peak:
                peak = cumulative_profit
            
            dd = peak - cumulative_profit
            if dd > max_dd:
                max_dd = dd
                
            if t['profit'] <= 0:
                current_streak += 1
                if current_streak > max_streak:
                    max_streak = current_streak
            else:
                current_streak = 0
                
        return {
            "total_trades": total_trades,
            "independent_trades": independent_trade_count,
            "net_profit": total_profit - total_loss,
            "win_rate": win_rate,
            "breakeven_wr": breakeven_wr,
            "expectancy": expectancy,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_win": max_win,
            "max_loss": max_loss,
            "max_dd": max_dd,
            "max_streak": max_streak
        }

    def generate_master_report(self, ict_trades, sr_trades, scalp_trades, metadata):
        """Generates the 8-part Master Report and saves to file."""
        all_trades = ict_trades + sr_trades + scalp_trades
        
        # Sort trades by time just in case
        all_trades = sorted(all_trades, key=lambda x: x['time'])
        
        report_path = os.path.join(self.output_dir, "Master_Report.txt")
        
        with open(report_path, 'w') as f:
            # 1. Header
            f.write("=========================================================\n")
            f.write("                 MASTER SYSTEM REPORT\n")
            f.write("=========================================================\n")
            f.write(f"Date Generated:   {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"Symbols:          {', '.join(metadata.get('symbols', []))}\n")
            f.write(f"Timeframe:        M5 base, D1 regime filtering\n")
            f.write(f"Parameters:       ATR-Normalized (ICT 1:10, Scalp 1:2)\n")
            f.write("=========================================================\n\n")
            
            # Aggregate Metrics
            agg = self._calculate_metrics(all_trades)
            if not agg:
                f.write("No trades executed across the entire backtest.\n")
                return report_path
                
            # 2. Executive Summary
            f.write("--- 2. EXECUTIVE SUMMARY ---\n")
            f.write(f"Net P/L:                  ${agg['net_profit']:.2f}\n")
            f.write(f"Total Trades:             {agg['total_trades']}\n")
            f.write(f"Independent Trades:       {agg['independent_trades']}\n")
            f.write(f"Profit Factor:            {agg['profit_factor']:.2f}\n")
            f.write(f"Max Drawdown:             ${agg['max_dd']:.2f}\n")
            
            verdict = "BELOW BREAKEVEN"
            if agg['net_profit'] > 0 and agg['win_rate'] > agg['breakeven_wr']:
                if agg['expectancy'] > (agg['avg_loss'] * 0.1): # Margin of safety
                    verdict = "CLEARED WITH MARGIN"
                else:
                    verdict = "MARGINAL"
            f.write(f"Verdict:                  [{verdict}]\n\n")
            
            # 3. Core Performance Metrics
            f.write("--- 3. CORE PERFORMANCE METRICS ---\n")
            f.write(f"Realized Win Rate:        {agg['win_rate']*100:.2f}%\n")
            f.write(f"Implied Breakeven WR:     {agg['breakeven_wr']*100:.2f}%\n")
            f.write(f"Expectancy per Trade:     ${agg['expectancy']:.2f}\n")
            f.write(f"Profit Factor:            {agg['profit_factor']:.2f}\n")
            f.write(f"Average Win / Loss:       ${agg['avg_win']:.2f} / -${agg['avg_loss']:.2f}\n")
            f.write(f"Largest Win / Loss:       ${agg['max_win']:.2f} / -${abs(agg['max_loss']):.2f}\n\n")
            
            # 4. Risk Metrics
            f.write("--- 4. RISK METRICS ---\n")
            f.write(f"Max Drawdown ($):         ${agg['max_dd']:.2f}\n")
            f.write(f"Longest Losing Streak:    {agg['max_streak']} trades\n\n")
            
            # 5. Segmented Breakdowns
            f.write("--- 5. SEGMENTED BREAKDOWNS (By Strategy) ---\n")
            strats = {
                "ICT (Trending)": ict_trades,
                "S/R (Ranging)": sr_trades,
                "Scalp (Aligned)": scalp_trades
            }
            
            for name, trades in strats.items():
                m = self._calculate_metrics(trades)
                if not m:
                    f.write(f"\n[{name}]\n  No trades.\n")
                    continue
                    
                f.write(f"\n[{name}]\n")
                f.write(f"  Net Profit:      ${m['net_profit']:.2f}\n")
                f.write(f"  Trades (Indep):  {m['total_trades']} ({m['independent_trades']})\n")
                f.write(f"  Win Rate vs BE:  {m['win_rate']*100:.1f}% vs {m['breakeven_wr']*100:.1f}%\n")
                f.write(f"  Expectancy:      ${m['expectancy']:.2f}\n")
                f.write(f"  Max Drawdown:    ${m['max_dd']:.2f}\n")
                
            # 6. Statistical Validity
            f.write("\n--- 6. STATISTICAL VALIDITY ---\n")
            inflation_ratio = agg['total_trades'] / agg['independent_trades'] if agg['independent_trades'] > 0 else 0
            f.write(f"Correlation Inflation:    {inflation_ratio:.2f}x (Total trades / Independent trades)\n")
            if inflation_ratio > 3.0:
                f.write("  -> WARNING: High correlation inflation. Trades are clustering heavily.\n")
            else:
                f.write("  -> OK: Acceptable trade independence.\n")
                
            # 7 & 8. Appendices
            f.write("\n\n=========================================================\n")
            f.write("          TRADE LOG APPENDIX (All Trades)\n")
            f.write("=========================================================\n")
            for i, t in enumerate(all_trades, 1):
                result = "SUCCESS" if t['profit'] > 0 else "FAILED "
                profit_str = f"+${t['profit']:.2f}" if t['profit'] > 0 else f"-${abs(t['profit']):.2f}"
                sig_id = t.get('parent_signal_id', 'none')
                f.write(f"{i:03d}. {t['time'].strftime('%Y-%m-%d %H:%M')} | {t.get('direction', 'none').upper():7s} | "
                        f"Entry: {t['entry_price']:.2f} | SL: {t['sl']:.2f} | TP: {t['tp']:.2f} | "
                        f"Profit: {profit_str} | ID: {sig_id}\n")
                        
        return report_path
