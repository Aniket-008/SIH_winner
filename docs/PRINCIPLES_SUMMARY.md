# JAN-DRISHTI AI - Core Principles & Model Summary

## 🎯 Three Core Principles

### 1️⃣ **TRANSPARENCY FIRST**
> "Every score tells a story"

- ✅ No black-box decisions
- ✅ Every finding has evidence  
- ✅ Officers see WHY, not just WHAT
- ✅ Explainable in court/audit

**Example:**
```
❌ Bad: "Project risk score: 67/100"
✅ Good: "Project risk score: 67/100 due to:
   • 45% cost overrun (Critical)
   • 120 days delay (High)
   • Financial-physical mismatch (High)"
```

---

### 2️⃣ **EARLY WARNING SYSTEM**
> "Catch problems before they become scandals"

- ⚡ Real-time anomaly detection
- 🎯 Risk-based prioritization
- 🚨 Proactive alerts
- 📊 Dashboard monitoring

**Impact:**
- Before: Discover fraud in audit (2-3 years later)
- After: Flag anomalies in days/weeks

---

### 3️⃣ **OFFICER-FRIENDLY**
> "Built for humans, not just data scientists"

- 💬 Simple language (not technical jargon)
- 📋 Actionable recommendations
- 🎨 Visual dashboard
- 📱 Easy to use

**Example Recommendation:**
```
Instead of: "Detected financial coefficient deviation of 2.3σ"
We say: "Money spent (80%) is much higher than work completed (40%). 
        Action: Conduct physical verification and review payment records."
```

---

## 🧮 How The Model Works (Simple Version)

### The Formula

```
Risk Score = Base (5 points) 
           + Findings Points 
           + Overrun Bonus 
           + Delay Bonus 
           + Mismatch Bonus

Where each finding gets:
Points = Severity × Multiplier
```

### Example Calculation

**Project: Road Construction in Bihar**
- Sanctioned: ₹100 Cr
- Spent: ₹130 Cr (30% overrun)
- Physical Progress: 45%
- Financial Progress: 75%
- Planned End: 2022-03-31
- Today: 2023-01-15 (289 days late)

**Findings:**
1. Cost Overrun (30%) → Critical severity = 36 points × 1.2 = **43.2**
2. Schedule Delay (289 days) → High severity = 24 points × 1.0 = **24.0**
3. Financial-Physical Mismatch (30%) → High = 24 × 1.25 = **30.0**

**Continuous Bonuses:**
- Overrun bonus: 30% × 0.25 = **+7.5**
- Delay bonus: 289÷30 × 1.2 = **+11.6**
- Mismatch bonus (fraud): 30% × 0.3 = **+9.0**

**Total:**
- Risk Score: 5 + 43.2 + 24 + 30 + 7.5 + 11.6 = **121.3** → Capped at **100**
- Fraud Score: Similar calculation with fraud weighting = **87/100**
- Risk Level: **CRITICAL** 🔴

**Explanation Shown:**
```
"This project has CRITICAL risk scoring 100/100 due to:
• 30% cost overrun
• 289 days schedule delay  
• Financial-physical mismatch (30% gap)

Recommended Actions:
1. Immediately halt further payments
2. Conduct detailed physical verification
3. Review contractor performance
4. Investigate fund utilization with audit team"
```

---

## 🔍 10 Detection Signals

| # | Signal | What It Catches | Severity |
|---|--------|----------------|----------|
| 1 | Cost Overrun | Spending > Budget | 🟠 Medium-Critical |
| 2 | Schedule Delay | Past deadline | 🟠 Medium-High |
| 3 | Slow Progress | Work lagging schedule | 🟡 Medium |
| 4 | Financial Mismatch | Money spent ≠ Work done | 🔴 High-Critical |
| 5 | Stale Reporting | No updates for 45+ days | 🟢 Low-Medium |
| 6 | Duplicate Works | Same project twice | 🔴 High |
| 7 | Duplicate IDs | Same code reused | 🔴 Critical |
| 8 | Amount Outliers | Unusually high budget | 🟡 Low-Medium |
| 9 | Contractor Monopoly | One contractor = too many projects | 🟠 Medium |
| 10 | Data Conflicts | Logical inconsistencies | 🟢 Low-High |

---

## 🎨 Model Transparency

### What Makes It Transparent?

1. **Deterministic**: Same data always gives same score
2. **Traceable**: Every point has a source finding
3. **Tunable**: Thresholds can be adjusted without code changes
4. **Explainable**: Officers understand the logic
5. **Auditable**: Complete trail of decisions

### Comparison

| Feature | Black-Box ML | JAN-DRISHTI AI |
|---------|-------------|----------------|
| Accuracy | High | Good |
| Explainability | ❌ Low | ✅ Complete |
| Officer Trust | ❌ Low | ✅ High |
| Auditability | ❌ Hard | ✅ Easy |
| Court-Ready | ❌ No | ✅ Yes |
| Tunability | ❌ Retrain needed | ✅ Config change |
| Upgrade Path | ❌ Complex | ✅ Findings → ML Features |

---

## 📊 Risk vs Fraud Scores

### Risk Score (0-100)
**Measures:** Overall project health  
**Includes:** ALL 10 anomaly signals  
**Use Case:** Monitoring priority, resource allocation  
**Question:** "How problematic is this project?"

### Fraud Score (0-100)
**Measures:** Intentional misuse likelihood  
**Includes:** ONLY fraud-relevant signals (6/10)  
**Use Case:** Investigation priority, legal action  
**Question:** "How suspicious is this project?"

### Fraud Signals (Higher Weight)
- ✅ Duplicate works/IDs
- ✅ Financial-physical mismatch
- ✅ Cost overruns
- ✅ Amount outliers
- ✅ Contractor concentration
- ✅ Data conflicts (negative amounts, etc.)

### Non-Fraud Signals (Lower Weight)
- Schedule delays
- Slow progress
- Stale reporting
- Amount outliers (lower impact)

---

## 💪 Why This Approach Wins

### Problem with Traditional Audits
- ❌ Reactive (find fraud after 2-3 years)
- ❌ Sample-based (miss many issues)
- ❌ Manual (slow, expensive)
- ❌ No prioritization (check everything equally)

### JAN-DRISHTI Solution
- ✅ Proactive (flag anomalies early)
- ✅ Comprehensive (analyze ALL projects)
- ✅ Automated (fast, scalable)
- ✅ Risk-based (focus on high-risk first)
- ✅ Explainable (officers trust it)

---

## 🚀 Real-World Impact

### Before JAN-DRISHTI
```
Upload 1000 projects → Manual review (maybe 100 samples) 
→ Find issues in 2-3 years → By then money is gone
```

### After JAN-DRISHTI
```
Upload 1000 projects → AI analysis in seconds 
→ Get 50 high-risk alerts immediately → Investigate & act early
→ Prevent fraud BEFORE money disappears
```

### Example Savings
**State Project Portfolio:** ₹10,000 Crore  
**Typical Fraud/Waste:** 5-10% = ₹500-1000 Crore  
**JAN-DRISHTI Detection:** 60% of issues caught early  
**Potential Recovery:** ₹300-600 Crore saved! 💰

---

## 🎓 Key Innovation

**We built a model that is BOTH accurate AND explainable**

Most AI systems force you to choose:
- High accuracy OR explainability
- Complex ML OR simple rules
- Technical power OR user-friendly

**JAN-DRISHTI gives you BOTH:**
- ✅ Accurate detection
- ✅ Complete explainability  
- ✅ Officer-friendly
- ✅ Upgrade path to ML (findings become features)

---

## 📝 In One Sentence

> **JAN-DRISHTI AI is an early-warning system that detects fraud and anomalies in government projects using transparent, rule-based AI that officers can understand, trust, and act upon immediately.**

---

## 📚 Learn More

- Full technical details: `docs/HOW_IT_WORKS.md`
- Architecture: `docs/PROJECT_BLUEPRINT.md`
- API documentation: `README.md`
- Model code: `jan_drishti/services/risk_predictor.py`
- Anomaly detection: `jan_drishti/services/anomaly_detector.py`

---

**Built for Smart India Hackathon 2026**  
**Problem Statement:** SIH26102 - Government Project Fraud Detection  
**Team:** JAN-DRISHTI AI  
**Mission:** Transparent AI for Accountable Governance 🇮🇳
