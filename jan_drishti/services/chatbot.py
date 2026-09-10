"""JAN-DRISHTI AI Chatbot - Help users understand the system and analysis.

This chatbot provides contextual help about:
- How to use the website
- Understanding risk scores and findings
- Model transparency and methodology
- Security features
- Data format requirements
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


class JanDrishtiChatbot:
    """Rule-based chatbot for answering user questions about the system."""
    
    def __init__(self):
        self.context_history: List[str] = []
        self.knowledge_base = self._build_knowledge_base()
    
    def _build_knowledge_base(self) -> Dict[str, Dict[str, any]]:
        """Build the knowledge base with questions and answers."""
        return {
            # Getting Started
            "upload": {
                "keywords": ["upload", "file", "csv", "how to start", "begin", "data"],
                "answer": """To upload your project data:

1. Click the file upload area or drag and drop your CSV file
2. Select a CSV file with government project data
3. Click "Run AI Risk Score" button
4. Wait a few seconds for analysis
5. View results in the dashboard below

**Supported formats:** CSV, JSON
**File size:** Up to 50MB
**Sample data:** Available in data/ folder""",
                "category": "getting_started"
            },
            
            "login": {
                "keywords": ["login", "username", "password", "access", "sign in", "authentication"],
                "answer": """JAN-DRISHTI AI uses secure authentication:

**Default Users:**
- Username: admin | Password: admin123 (Full access)
- Username: auditor | Password: auditor123 (Analysis + Audit logs)
- Username: viewer | Password: viewer123 (View only)

**Security Features:**
- PBKDF2 password hashing (100,000 iterations)
- Session tokens (8-hour timeout)
- Role-based access control

Change passwords in production deployment!""",
                "category": "getting_started"
            },
            
            # Understanding Scores
            "risk_score": {
                "keywords": ["risk score", "scoring", "how calculated", "formula", "points"],
                "answer": """Risk Score (0-100) measures overall project health:

**Formula:**
Base (5 points) + Finding Points + Continuous Bonuses

**Finding Points:**
Each finding = Severity Weight × Multiplier
- Critical: 36 points × multiplier
- High: 24 points × multiplier  
- Medium: 13 points × multiplier
- Low: 5 points × multiplier

**Multipliers:**
- Duplicate ID: 1.5×
- Duplicate Work: 1.35×
- Financial Mismatch: 1.25×
- Cost Overrun: 1.2×

**Continuous Bonuses:**
- Cost overrun %
- Delay days
- Financial-physical gap

**Risk Levels:**
- 0-34: Low
- 35-54: Medium
- 55-74: High
- 75-100: Critical""",
                "category": "understanding"
            },
            
            "fraud_score": {
                "keywords": ["fraud score", "fraud detection", "suspicious"],
                "answer": """Fraud Score (0-100) measures likelihood of intentional misuse:

**Key Difference from Risk Score:**
- Uses only fraud-relevant findings
- Higher weight on suspicious patterns
- Lower weight on operational issues

**Fraud-Relevant Signals:**
✓ Duplicate works/IDs
✓ Financial-physical mismatch
✓ Cost overruns
✓ Amount outliers
✓ Contractor concentration
✓ Invalid/negative amounts

**Non-Fraud Signals (lower weight):**
- Schedule delays (could be legitimate)
- Slow progress (operational issue)
- Stale reporting (admin issue)

High fraud score → Investigation priority""",
                "category": "understanding"
            },
            
            "findings": {
                "keywords": ["findings", "anomalies", "what detected", "signals", "detection"],
                "answer": """JAN-DRISHTI detects 10 types of anomalies:

1. **Cost Overrun** - Spending exceeds budget
2. **Schedule Delay** - Past deadline
3. **Slow Progress** - Work lagging schedule
4. **Financial Mismatch** - Money spent ≠ work done
5. **Stale Reporting** - No updates for 45+ days
6. **Duplicate Works** - Similar projects in same area
7. **Duplicate IDs** - Repeated project codes
8. **Amount Outliers** - Unusually high budgets
9. **Contractor Monopoly** - One contractor dominates
10. **Data Conflicts** - Logical inconsistencies

Each finding includes:
- Severity (Low/Medium/High/Critical)
- Evidence (specific data)
- Explanation (why it's flagged)""",
                "category": "understanding"
            },
            
            # Using Features
            "explain": {
                "keywords": ["explain button", "project details", "why flagged", "reasoning"],
                "answer": """The "Explain" button shows detailed analysis:

**What you'll see:**
- Complete risk breakdown
- All findings with evidence
- AI-generated explanation
- Recommended officer actions
- Project financial details
- Timeline information

**How to use:**
1. Find project in results table
2. Click "Explain" button
3. Read findings and recommendations
4. Take suggested actions

The explanation shows WHY the project is risky, not just the score.""",
                "category": "features"
            },
            
            "transparency": {
                "keywords": ["transparency", "model transparency", "how it works", "methodology"],
                "answer": """JAN-DRISHTI uses transparent AI:

**View Model Transparency:**
Click "Model Transparency" button to see:
- Complete risk scoring formula
- All threshold values
- Severity weights
- Finding multipliers
- Worked examples

**Why Transparent?**
✓ Officers can verify calculations
✓ Explainable in court/audit
✓ No "black box" decisions
✓ Builds trust
✓ Allows threshold tuning

**Rule-Based Model:**
Uses expert rules, not neural networks
→ Every decision is traceable
→ Same data = same score (deterministic)""",
                "category": "features"
            },
            
            "audit_log": {
                "keywords": ["audit log", "activity", "history", "who did what"],
                "answer": """Audit Log tracks all system activity:

**What's Logged:**
- User logins/logouts
- File uploads and analyses
- Data exports
- Administrative actions

**Information Captured:**
- Timestamp (when)
- User (who)
- Action (what)
- Resource (which file/project)
- IP address (from where)
- Status (success/failure)

**Access:**
- Admin role: Full audit log
- Auditor role: Own actions + analysis
- Viewer role: Own actions only

Used for compliance and investigation.""",
                "category": "features"
            },
            
            # Data Requirements
            "data_format": {
                "keywords": ["data format", "csv format", "columns", "required fields"],
                "answer": """JAN-DRISHTI works with various CSV formats:

**Intelligent Column Mapping:**
The system recognizes 50+ column name variations!

**Key Fields (flexible names):**
- Project ID: project_id, work_id, sl_no, etc.
- Project Name: project_name, work_name, scheme, etc.
- Location: district, state, block
- Amounts: sanctioned_amount, spent_amount, budget
- Progress: physical_progress_pct, financial_progress_pct
- Dates: start_date, end_date, completion_date
- Status: status, project_status, stage

**Special Formats Supported:**
- Parliament expenditure data (multi-year columns)
- Amount formats: Crore, Lakh, thousands
- Date formats: DD/MM/YYYY, YYYY-MM-DD, etc.
- Missing data: Handled gracefully

**Not Required:**
All fields are optional! The system works with partial data.""",
                "category": "data"
            },
            
            # Security
            "security": {
                "keywords": ["security", "safe", "encryption", "privacy", "protection"],
                "answer": """JAN-DRISHTI Security Features:

**Authentication:**
- PBKDF2 password hashing (100,000 iterations)
- HMAC-SHA256 session tokens
- 8-hour session timeout
- Secure password storage

**Authorization:**
- Role-based access control (RBAC)
- 3 roles: Admin, Auditor, Viewer
- Permission checks on every action
- Least-privilege principle

**Data Protection:**
- SQL injection prevention (prepared statements)
- Input validation and sanitization
- Audit trail for accountability
- Local storage (no cloud exposure)

**Compliance Ready:**
- ISO 27001 aligned
- CERT-In guidelines followed
- CAG audit-ready logging
- Government security standards

All project data stays on your server!""",
                "category": "security"
            },
            
            # Troubleshooting
            "error": {
                "keywords": ["error", "not working", "problem", "issue", "failed", "broken"],
                "answer": """Common Issues & Solutions:

**"No data showing":**
- Ensure CSV has column headers
- Check file is not empty
- Try sample CSV from data/ folder
- Refresh browser (Ctrl+Shift+R)

**"Unnamed Project":**
- Check CSV has project name column
- Ensure correct file uploaded
- Look for columns: project_name, work_name, scheme

**"Upload fails":**
- Check file size (<50MB)
- Ensure file is CSV or JSON format
- Verify file is not corrupted
- Try saving as UTF-8 CSV

**"Login doesn't work":**
- Check username/password (case sensitive)
- Clear browser cache
- Use default: admin/admin123

**"Analysis taking too long":**
- Large files (1000+ projects) take 5-10 seconds
- Don't click "Run" multiple times
- Check console for errors (F12)

Still stuck? Check docs/ folder for detailed guides.""",
                "category": "troubleshooting"
            },
            
            # About the System
            "about": {
                "keywords": ["what is", "about", "purpose", "jan-drishti", "jandrishti"],
                "answer": """About JAN-DRISHTI AI:

**Full Name:** JAN-DRISHTI AI  
**Meaning:** People's Vision (जन-दृष्टि)

**Purpose:**
Early-warning system for government project fraud and anomalies

**Built For:**
Smart India Hackathon 2026
Problem Statement: SIH26102

**Key Features:**
✓ Automated fraud detection
✓ Risk-based prioritization  
✓ Explainable AI (not black box)
✓ Officer-friendly interface
✓ 100% project coverage
✓ Instant analysis (seconds)

**Technology:**
- Python backend (zero dependencies)
- Rule-based AI model
- Modular architecture
- Secure authentication
- SQLite database

**Impact:**
Helps prevent fraud BEFORE money disappears
Potential savings: ₹100s-1000s Crores per state!

Built with transparency for accountable governance 🇮🇳""",
                "category": "about"
            },
            
            # Actions
            "recommendations": {
                "keywords": ["what to do", "action", "recommendation", "next steps", "officer action"],
                "answer": """Understanding Recommendations:

Each high-risk project includes specific actions:

**Cost Overrun Actions:**
- Review revised budget approvals
- Audit fund utilization records
- Check contractor bills and payments
- Verify physical progress vs spending

**Delay Actions:**
- Assess contractor performance
- Identify bottlenecks
- Review timeline extension requests
- Consider penalty clauses

**Financial Mismatch Actions:**
- Conduct immediate physical verification
- Audit all payments and work orders
- Check for ghost billing
- Investigate with engineer

**Duplicate Work Actions:**
- Cross-check with project registry
- Verify locations and scope
- Review contractor records
- Consolidate if legitimate, flag if fraud

**Priority:**
1. Critical risk → Immediate action
2. High risk → Review within 1 week
3. Medium risk → Monitor closely
4. Low risk → Periodic check

Document all actions in audit log!""",
                "category": "actions"
            }
        }
    
    def get_response(self, user_query: str, context: Optional[Dict] = None) -> str:
        """Get chatbot response for user query."""
        if not user_query or not user_query.strip():
            return self._get_default_response()
        
        query = user_query.lower().strip()
        
        # Add to context history
        self.context_history.append(query)
        if len(self.context_history) > 5:
            self.context_history.pop(0)
        
        # Find best matching response
        best_match, confidence = self._find_best_match(query)
        
        if best_match and confidence > 0.3:
            return best_match["answer"]
        
        # No good match - provide helpful fallback
        return self._get_fallback_response(query)
    
    def _find_best_match(self, query: str) -> Tuple[Optional[Dict], float]:
        """Find the best matching knowledge base entry."""
        best_match = None
        best_score = 0.0
        
        for topic, data in self.knowledge_base.items():
            score = self._calculate_match_score(query, data["keywords"])
            if score > best_score:
                best_score = score
                best_match = data
        
        return best_match, best_score
    
    def _calculate_match_score(self, query: str, keywords: List[str]) -> float:
        """Calculate how well query matches keywords."""
        score = 0.0
        query_words = set(re.findall(r'\w+', query.lower()))
        
        for keyword in keywords:
            keyword_words = set(re.findall(r'\w+', keyword.lower()))
            
            # Exact phrase match
            if keyword in query:
                score += 1.0
            # Partial word match
            else:
                overlap = len(query_words & keyword_words)
                if overlap > 0:
                    score += overlap * 0.3
        
        return score / len(keywords) if keywords else 0.0
    
    def _get_default_response(self) -> str:
        """Default greeting response."""
        return """👋 Hello! I'm the JAN-DRISHTI AI Assistant.

I can help you with:
• **Getting Started** - Upload data, login, navigation
• **Understanding Scores** - Risk, fraud, findings
• **Using Features** - Explain, transparency, audit log
• **Data Format** - CSV requirements, column mapping
• **Security** - Authentication, roles, compliance
• **Troubleshooting** - Error resolution, common issues

**Ask me anything!** For example:
- "How do I upload data?"
- "What is a risk score?"
- "How does the model work?"
- "What should I do about cost overruns?"

Type your question below 👇"""
    
    def _get_fallback_response(self, query: str) -> str:
        """Fallback response when no good match found."""
        suggestions = self._get_contextual_suggestions(query)
        
        return f"""I'm not sure about that specific question, but I can help with:

{suggestions}

**You can also:**
- Click "Model Transparency" to see how scoring works
- Check the docs/ folder for detailed documentation
- Try asking in different words

**Popular questions:**
- How do I upload a CSV file?
- What does the risk score mean?
- How are findings detected?
- What should I do with high-risk projects?"""
    
    def _get_contextual_suggestions(self, query: str) -> str:
        """Get contextual suggestions based on query."""
        suggestions = []
        
        # Detect query intent
        if any(word in query for word in ["how", "what", "explain"]):
            suggestions.append("• Ask 'What is risk score?' for scoring details")
            suggestions.append("• Ask 'How do I upload data?' for getting started")
        
        if any(word in query for word in ["error", "problem", "not working"]):
            suggestions.append("• Check common errors: 'Error uploading file'")
            suggestions.append("• Try 'Troubleshooting tips'")
        
        if any(word in query for word in ["data", "csv", "format"]):
            suggestions.append("• Ask 'What CSV format is required?'")
            suggestions.append("• Ask 'How does column mapping work?'")
        
        if not suggestions:
            suggestions = [
                "• Getting started with uploads",
                "• Understanding risk scores",
                "• Using the explain feature"
            ]
        
        return "\n".join(suggestions)
    
    def get_quick_help(self, topic: str) -> str:
        """Get quick help for specific topic."""
        topic_key = topic.lower().replace(" ", "_")
        
        if topic_key in self.knowledge_base:
            return self.knowledge_base[topic_key]["answer"]
        
        return f"No help available for '{topic}'. Try asking in the chatbot!"
    
    def get_categories(self) -> Dict[str, List[str]]:
        """Get all help categories and topics."""
        categories = {}
        for topic, data in self.knowledge_base.items():
            category = data["category"]
            if category not in categories:
                categories[category] = []
            categories[category].append(topic)
        return categories
