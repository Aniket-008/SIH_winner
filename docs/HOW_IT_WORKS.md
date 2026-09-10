# JAN-DRISHTI AI - How It Works

## 🎯 Core Principles

### 1. **Transparency First**
- Every risk score is explainable
- Officers can see WHY a project is flagged
- No "black box" decisions - every finding has evidence
- Model uses rule-based weighted scoring (can upgrade to ML later)

### 2. **Early Warning System**
- Detect problems BEFORE they become scandals
- Proactive monitoring instead of reactive audits
- Risk-based prioritization - focus on highest risk first

### 3. **Officer-Friendly**
- Clear explanations in simple language
- Actionable recommendations (not just scores)
- Visual dashboard with priority alerts
- No technical jargon

### 4. **Data Reality**
- Works with messy, real-world government data
- Handles multiple CSV formats automatically
- Cleans and standardizes inconsistent column names
- Tolerates missing data gracefully

---

## 🔬 How The AI Model Works

### **Pipeline Overview**

```
CSV Upload
    ↓
Data Cleaning (standardize columns, parse dates/amounts)
    ↓
Data Validation (check completeness, consistency)
    ↓
Anomaly Detection (10 different signals)
    ↓
Risk Scoring (weighted model)
    ↓
AI Explanation (convert findings to actions)
    ↓
Dashboard Report
```

---

## 📊 Risk Scoring Model

### **Formula**

```
Base Risk Score = 5 points (baseline)

For each finding:
    Points = Severity Weight × Finding Multiplier
    
Risk Score = Base + Sum of all finding points + Continuous metrics
Final Score = Capped between 0-100
```

### **Severity Weights**

| Severity | Points |
|----------|--------|
| Low      | 5      |
| Medium   | 13     |
| High     | 24     |
| Critical | 36     |

### **Finding Multipliers**

| Finding Type | Multiplier | Why? |
|--------------|-----------|------|
| Duplicate Project ID | 1.50× | Strongest fraud indicator |
| Possible Duplicate Work | 1.35× | High misuse potential |
| Financial-Physical Mismatch | 1.25× | Money spent but no progress |
| Cost Overrun | 1.20× | Budget violation |
| Schedule Delay | 1.00× | Common but important |
| Slow Physical Progress | 0.95× | Warning sign |
| Contractor Concentration | 0.90× | Monopoly risk |
| Stale Reporting | 0.85× | Oversight issue |
| Amount Outlier | 0.85× | Unusual spending |

### **Continuous Metrics Bonus**

1. **Cost Overrun %**: Up to +18 points
   - Formula: `min(18, overrun_percent × 0.25)`
   - Example: 50% overrun = +12.5 points

2. **Delay Days**: Up to +14 points
   - Formula: `min(14, delay_days / 30 × 1.2)`
   - Example: 90 days late = +3.6 points

3. **Financial-Physical Gap**: Up to +18 fraud points
   - Formula: `min(18, gap_percent × 0.3)`
   - Example: 40% gap = +12 fraud points

### **Risk Levels**

| Score Range | Risk Level |
|-------------|-----------|
| 0-34        | Low       |
| 35-54       | Medium    |
| 55-74       | High      |
| 75-100      | Critical  |

---

## 🔍 10 Anomaly Detection Signals

### 1. **Cost Overrun**
- **What**: Spent amount exceeds sanctioned budget
- **Threshold**: >15% over budget
- **Severity**: Medium to Critical (based on %)
- **Example**: Sanctioned ₹10 Cr, Spent ₹12 Cr = 20% overrun

### 2. **Schedule Delay**
- **What**: Project past deadline or completed late
- **Threshold**: >30 days late
- **Severity**: Medium to High
- **Example**: Planned end 2022-03-31, Today 2023-01-15 = 289 days late

### 3. **Slow Physical Progress**
- **What**: Physical completion lags behind schedule
- **Threshold**: >20% gap between expected and actual progress
- **Severity**: Medium
- **Example**: 60% time elapsed but only 30% work done = 30% gap

### 4. **Financial-Physical Mismatch**
- **What**: Money spent much more than work completed
- **Threshold**: >25% gap
- **Severity**: High to Critical
- **Example**: 80% funds used but only 40% work done = 40% gap
- **Why Critical**: Suggests fund diversion

### 5. **Stale Reporting**
- **What**: No status update for long time
- **Threshold**: >45 days with no update
- **Severity**: Low to Medium
- **Example**: Last updated 2022-10-15, today 2023-01-15 = 92 days

### 6. **Duplicate Works**
- **What**: Similar projects in same area
- **Detection**: Name similarity >70% + same district + similar amounts
- **Severity**: High
- **Example**: "Road Widening NH-44" and "Road Widdening NH-44" in same district

### 7. **Duplicate Project IDs**
- **What**: Same project code used multiple times
- **Severity**: Critical
- **Why**: Data integrity issue or deliberate fraud

### 8. **Amount Outliers**
- **What**: Budget unusually high compared to similar projects
- **Threshold**: >3× median amount in uploaded batch
- **Severity**: Low to Medium
- **Example**: Most projects ₹5 Cr, this one ₹50 Cr

### 9. **Contractor Concentration**
- **What**: One contractor has too many projects
- **Threshold**: >25% of projects or >30% of total value
- **Severity**: Medium
- **Why**: Monopoly risk, less competition

### 10. **Data Conflicts**
- **What**: Logical inconsistencies in data
- **Examples**:
  - Status "Completed" but physical progress <80%
  - Completion date before start date
  - Negative expenditure
  - Sanctioned amount = 0 but spending exists
- **Severity**: Low to High

---

## 🤖 Fraud Score vs Risk Score

### **Risk Score** (0-100)
- Measures: Overall project health
- Considers: ALL findings
- Use: Priority for monitoring
- Formula: Balanced weighting of all anomalies

### **Fraud Score** (0-100)
- Measures: Likelihood of intentional misuse
- Considers: ONLY fraud-relevant findings
- Use: Investigation priority
- Formula: Higher weight on fraud indicators

**Fraud-Relevant Signals:**
- Duplicate works/IDs
- Financial-physical mismatch
- Cost overruns
- Amount outliers
- Contractor concentration
- Invalid amounts
- Negative expenditure

---

## 💡 AI Explanation Engine

### How Explanations Are Generated

1. **Identify Top Risk Drivers** (max 4)
   - Sort findings by contribution to risk score
   - Select most impactful ones

2. **Generate Human-Readable Summary**
   ```
   Template:
   "This project has [RISK_LEVEL] risk scoring [SCORE]/100 due to [TOP_DRIVERS]. 
   Key concerns: [DETAILED_FINDINGS]."
   ```

3. **Create Action Recommendations**
   - Cost overrun → "Review revised budget approval and fund utilization"
   - Delay → "Assess contractor performance and extend timeline"
   - Mismatch → "Conduct physical verification and audit payments"
   - Duplicate → "Cross-check with project registry"

---

## 📈 Model Transparency Benefits

### For Officers
- ✅ Understand WHY a project is flagged
- ✅ Know WHAT to do next
- ✅ Justify decisions with evidence
- ✅ Learn patterns over time

### For Auditors
- ✅ See complete audit trail
- ✅ Export findings with evidence
- ✅ Filter by severity/type
- ✅ Track who analyzed what (with auth)

### For System
- ✅ Deterministic results (same data = same score)
- ✅ Tunable thresholds without retraining
- ✅ Explainable to courts/committees
- ✅ Easy to upgrade to ML later (findings become features)

---

## 🚀 Future Enhancements

### Phase 2: Machine Learning
- Train supervised model on past audit outcomes
- Use current rule-based findings as ML features
- Combine rule scores with ML predictions
- Still maintain explainability

### Phase 3: Advanced Analytics
- Geographic clustering of anomalies
- Temporal patterns across years
- Contractor/agency risk profiles
- Predictive delay forecasting

### Phase 4: Integration
- Real-time data feeds from state systems
- Automated alerts to officer dashboards
- Mobile app for field verification
- API for third-party tools

---

## 📋 Model Validation

### How We Ensure Accuracy

1. **Threshold Calibration**
   - Set based on real-world data distributions
   - Reviewed with domain experts
   - Adjustable in config.py

2. **False Positive Management**
   - Multiple severity levels avoid over-alerting
   - Context-aware rules (e.g., status-based delays)
   - Findings require evidence, not just thresholds

3. **Transparency Testing**
   - Every score must have traceable findings
   - Manual review of 100+ sample projects
   - Cross-validation with actual audit reports

---

## 🎓 Key Innovation

**The model is BOTH powerful AND explainable:**

❌ Traditional Approach:
- Complex ML model
- High accuracy but "black box"
- Officers don't trust it
- Can't explain decisions

✅ JAN-DRISHTI Approach:
- Rule-based weighted model
- Transparent scoring logic
- Every finding has evidence
- Officers understand and trust it
- **Can upgrade to ML later while keeping transparency**

---

## 📞 Model Configuration

All thresholds and weights are configurable in `jan_drishti/config.py`:

```python
class RiskThresholds:
    cost_overrun_pct = 15.0          # Trigger when spending >15% over budget
    schedule_delay_days = 30         # Flag if >30 days late
    financial_mismatch_gap = 25.0    # Alert if gap >25%
    stale_reporting_days = 45        # Warn if no update for 45+ days
    
    low_risk = 0
    medium_risk = 35
    high_risk = 55
    critical_risk = 75
```

This makes the system adaptable to different government contexts and priorities!

---

## 📚 Summary

**JAN-DRISHTI AI is built on three pillars:**

1. **Explainable AI** - Every decision has a reason
2. **Practical Design** - Works with real messy data
3. **Officer-Centric** - Designed for government users

**The result?** 
A system that detects fraud and anomalies early, explains findings clearly, and empowers officers to take action - all while maintaining complete transparency and accountability.
