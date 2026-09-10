# JAN-DRISHTI AI Chatbot Guide

## 🤖 Overview

The JAN-DRISHTI AI Chatbot is an intelligent assistant that helps users understand and navigate the system. It can answer questions about:

- **Getting Started** - How to upload data, login, navigate the interface
- **Understanding Scores** - Risk scores, fraud scores, findings explanations
- **Using Features** - Explain button, transparency viewer, audit logs
- **Data Requirements** - CSV formats, column mapping, data preparation
- **Security** - Authentication, roles, compliance features
- **Troubleshooting** - Common errors, problem resolution
- **Taking Actions** - Recommended officer actions for different findings

---

## 💬 How to Use

### Accessing the Chatbot

1. Look for the **purple chat bubble button** (💬) in the bottom-right corner
2. Click it to open the chatbot window
3. The assistant will greet you with a welcome message

### Asking Questions

**Type your question** in the input box at the bottom:
- "How do I upload a CSV file?"
- "What does risk score mean?"
- "How are findings detected?"
- "What should I do about delays?"

**Use Quick Action buttons** for common questions:
- 📤 Upload Help
- 📊 Risk Score
- 🔬 Model Info
- 💰 Actions

### Getting Help

The chatbot understands natural language! Ask in your own words:
- "How does this work?"
- "I'm getting an error"
- "Explain fraud score"
- "What columns do I need in my CSV?"

---

## 📚 Topics the Chatbot Knows

### 1. Getting Started
**Sample Questions:**
- "How do I upload data?"
- "How to login?"
- "What are the default credentials?"
- "How do I start analyzing projects?"

**What You'll Learn:**
- Step-by-step upload instructions
- Login credentials and security features
- Navigation tips
- File format requirements

---

### 2. Understanding Risk Scores
**Sample Questions:**
- "What is risk score?"
- "How is risk calculated?"
- "What do the numbers mean?"
- "What are risk levels?"

**What You'll Learn:**
- Complete scoring formula
- Severity weights and multipliers
- Risk level thresholds (Low/Medium/High/Critical)
- How continuous metrics affect scores

---

### 3. Fraud Detection
**Sample Questions:**
- "What is fraud score?"
- "How is fraud detected?"
- "Difference between risk and fraud score?"
- "What signals indicate fraud?"

**What You'll Learn:**
- Fraud vs risk scoring differences
- Fraud-relevant anomaly types
- Investigation priorities
- Why certain patterns are suspicious

---

### 4. Anomaly Detection
**Sample Questions:**
- "What anomalies are detected?"
- "What findings does it look for?"
- "How does duplicate detection work?"
- "What is financial mismatch?"

**What You'll Learn:**
- All 10 anomaly types explained
- Detection thresholds and severity levels
- Evidence provided for each finding
- Why each anomaly matters

---

### 5. Using Features
**Sample Questions:**
- "How does the explain button work?"
- "Where is model transparency?"
- "What is audit log?"
- "How to view project details?"

**What You'll Learn:**
- Feature locations and usage
- What information each feature shows
- How to interpret results
- Best practices for analysis

---

### 6. Data Requirements
**Sample Questions:**
- "What CSV format is required?"
- "What columns do I need?"
- "Can I use different column names?"
- "How to prepare my data?"

**What You'll Learn:**
- Flexible column mapping (50+ variations)
- Required vs optional fields
- Special format support (Parliament data, etc.)
- Amount and date format handling

---

### 7. Security & Compliance
**Sample Questions:**
- "Is this secure?"
- "What about data privacy?"
- "What are the user roles?"
- "Is it compliance ready?"

**What You'll Learn:**
- Authentication mechanisms
- Role-based access control
- Data protection features
- Compliance standards (ISO 27001, CERT-In)

---

### 8. Troubleshooting
**Sample Questions:**
- "Why is upload not working?"
- "Why showing unnamed project?"
- "Getting an error"
- "Analysis taking too long"

**What You'll Learn:**
- Common error solutions
- File format troubleshooting
- Browser compatibility tips
- Performance optimization

---

### 9. Taking Action
**Sample Questions:**
- "What should I do about cost overrun?"
- "How to handle delays?"
- "What actions for duplicate work?"
- "Next steps for high risk projects?"

**What You'll Learn:**
- Specific officer actions for each finding type
- Priority levels for action
- Documentation requirements
- Investigation procedures

---

### 10. About the System
**Sample Questions:**
- "What is JAN-DRISHTI?"
- "How does it work?"
- "What technology is used?"
- "What is the purpose?"

**What You'll Learn:**
- System purpose and goals
- Technology stack
- Built for SIH 2026
- Impact and benefits

---

## 🎯 Sample Conversations

### Example 1: New User
**User:** "I'm new here, how do I start?"

**Chatbot:** 
```
To upload your project data:

1. Click the file upload area or drag and drop your CSV file
2. Select a CSV file with government project data
3. Click "Run AI Risk Score" button
4. Wait a few seconds for analysis
5. View results in the dashboard below

Supported formats: CSV, JSON
File size: Up to 50MB
Sample data: Available in data/ folder
```

---

### Example 2: Understanding Results
**User:** "What does the risk score mean?"

**Chatbot:**
```
Risk Score (0-100) measures overall project health:

Formula:
Base (5 points) + Finding Points + Continuous Bonuses

Finding Points:
Each finding = Severity Weight × Multiplier
- Critical: 36 points × multiplier
- High: 24 points × multiplier  
- Medium: 13 points × multiplier
- Low: 5 points × multiplier

Risk Levels:
- 0-34: Low
- 35-54: Medium
- 55-74: High
- 75-100: Critical
```

---

### Example 3: Troubleshooting
**User:** "Error uploading file"

**Chatbot:**
```
Common Issues & Solutions:

"Upload fails":
- Check file size (<50MB)
- Ensure file is CSV or JSON format
- Verify file is not corrupted
- Try saving as UTF-8 CSV

"No data showing":
- Ensure CSV has column headers
- Check file is not empty
- Try sample CSV from data/ folder
- Refresh browser (Ctrl+Shift+R)

Still stuck? Check docs/ folder for detailed guides.
```

---

## 🚀 Advanced Features

### Context Awareness
The chatbot remembers your last 5 questions to provide better responses. It can understand follow-up questions based on context.

### Keyword Matching
Uses intelligent keyword matching to find the most relevant answer even if you don't use exact phrases.

### Fallback Responses
If it doesn't understand your question, it provides contextual suggestions based on what you asked.

### Quick Actions
Pre-configured buttons for the most common questions - just click to get instant answers!

---

## 🔧 Technical Details

### How It Works

1. **Rule-Based NLP** - Uses keyword matching and pattern recognition
2. **Knowledge Base** - Pre-programmed answers for 15+ topic areas
3. **Context History** - Remembers recent questions for better responses
4. **Graceful Fallback** - Provides helpful suggestions when unsure

### API Endpoint
- **URL:** `/api/chatbot`
- **Method:** POST
- **Auth:** Required (Bearer token)
- **Request:** `{"query": "your question", "context": {}}`
- **Response:** `{"response": "answer text", "timestamp": "ISO date"}`

### Security
- Requires authentication
- All queries logged in audit trail
- No sensitive data exposed
- Rate limiting ready (can be added)

---

## 💡 Tips for Best Results

### Do:
✅ Ask specific questions
✅ Use simple, clear language
✅ Try rephrasing if first answer isn't helpful
✅ Use Quick Action buttons for common topics
✅ Ask follow-up questions

### Don't:
❌ Ask multiple questions in one message
❌ Use very technical jargon
❌ Expect real-time data analysis (use the dashboard)
❌ Ask about unrelated topics (weather, news, etc.)

---

## 🎨 Customization

The chatbot knowledge base can be easily extended by editing:
- **File:** `jan_drishti/services/chatbot.py`
- **Method:** `_build_knowledge_base()`

Add new topics by adding entries to the knowledge base dictionary:

```python
"your_topic": {
    "keywords": ["word1", "word2", "phrase"],
    "answer": """Your detailed answer here...""",
    "category": "your_category"
}
```

---

## 📱 Mobile Support

The chatbot is fully responsive:
- Adapts to mobile screen sizes
- Touch-friendly buttons
- Smooth animations
- Easy to close/open

---

## 🆘 Support

If the chatbot can't answer your question:

1. **Check Documentation**
   - docs/HOW_IT_WORKS.md
   - docs/PRINCIPLES_SUMMARY.md
   - docs/PROJECT_BLUEPRINT.md

2. **Use Model Transparency**
   - Click "Model Transparency" button
   - See complete scoring formulas

3. **Check Audit Log**
   - View system activity
   - Track your actions

4. **Contact Support**
   - Review GitHub repository
   - Check project README

---

## 🎓 Future Enhancements

Planned improvements:
- **AI/ML Integration** - Use GPT-like models for more natural conversations
- **Voice Input** - Speak your questions
- **Multi-language** - Support Hindi and regional languages
- **Contextual Help** - Show relevant help based on current page
- **Project-Specific Help** - Answer questions about specific projects in your data

---

**Built with transparency for accountable governance 🇮🇳**

**Version:** 1.0  
**Last Updated:** Smart India Hackathon 2026  
**Problem Statement:** SIH26102 - Government Project Fraud Detection
