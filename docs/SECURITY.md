# JAN-DRISHTI AI Security Features

## Overview

JAN-DRISHTI AI implements enterprise-grade security features for government project fraud detection, ensuring data protection, access control, and full audit trails.

## Authentication System

### User Authentication
- **Password Security**: PBKDF2 with SHA-256, 100,000 iterations, per-user salt
- **Session Tokens**: JWT-style signed tokens with HMAC-SHA256
- **Token Expiry**: 8-hour session timeout for security
- **No Plain-text Storage**: Passwords are never stored in plain text

### Default User Accounts

For demonstration and testing:

| Username | Password | Role | Permissions |
|----------|----------|------|-------------|
| `admin` | `admin123` | Administrator | Full access: analyze, manage users, view audit logs, configure system |
| `auditor` | `auditor123` | Auditor/Officer | Upload and analyze data, export reports, view dashboards |
| `viewer` | `viewer123` | Viewer | Read-only access to reports and dashboards |

**⚠️ IMPORTANT**: Change these default passwords before deploying to production!

## Role-Based Access Control (RBAC)

### Roles and Permissions

#### Administrator
- View all reports and dashboards
- Upload and analyze project data
- Export reports
- Manage user accounts
- View complete audit trail
- Configure system thresholds

#### Auditor/Officer
- View all reports and dashboards
- Upload and analyze project data
- Export reports
- View own activity in audit log

#### Viewer
- View reports and dashboards only
- Cannot upload or modify data
- Cannot access audit logs

## Database Security

### SQLite Database
- **Location**: `data/jandrishti.db`
- **Encrypted Credentials**: All passwords hashed with salt
- **Prepared Statements**: Protection against SQL injection
- **Transaction Safety**: Automatic rollback on errors

### Database Schema

```sql
users              -- User accounts with hashed passwords
analysis_runs      -- Analysis history with user tracking
projects           -- Individual project results
audit_log          -- Complete activity trail
sessions           -- Active session tokens
```

### Data Protection
- Sensitive data (passwords) never logged
- Analysis results tied to user accounts
- Historical analysis preserved for compliance
- Audit-ready database structure

## Audit Logging

### What is Logged
Every significant action is logged:
- User login/logout
- File uploads and analysis
- Report exports
- Configuration changes
- Failed authentication attempts
- Authorization violations

### Audit Log Fields
```json
{
  "timestamp": "ISO 8601 timestamp",
  "user_id": "User identifier",
  "username": "Username",
  "action": "LOGIN | ANALYZE | EXPORT | etc.",
  "resource": "File or resource name",
  "details": "Additional context",
  "ip_address": "Client IP address",
  "success": true/false
}
```

### Audit Log Access
- **Administrators only** can view complete audit trail
- Non-repudiable record of all system activity
- Tamper-evident timestamping
- Suitable for government compliance requirements

## Model Transparency

### Explainable AI
JAN-DRISHTI uses a fully transparent, rule-based risk scoring model:

- **No Black Box**: Every score calculation is documented
- **Component Weights**: Risk factors have explicit weights (25% cost, 20% delay, etc.)
- **Threshold Visibility**: All decision thresholds are configurable and documented
- **Formula Disclosure**: Complete formulas for each risk component
- **Evidence Trail**: Each finding includes supporting evidence

### Score Calculation Documentation
The `/api/model-transparency` endpoint provides:
- Risk component definitions and weights
- Threshold values for all severity levels
- Fraud score calculation methodology
- Worked examples with step-by-step breakdowns
- Key principles of the explainable model

## API Security

### Protected Endpoints

All API endpoints (except `/api/login`) require authentication:

```http
Authorization: Bearer <token>
```

### Error Responses
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: Insufficient permissions
- `400 Bad Request`: Invalid input data
- `500 Internal Server Error`: System error (details logged)

### Rate Limiting
While not implemented in the prototype, production deployments should add:
- Login attempt rate limiting
- API request throttling
- IP-based blocking for repeated failures

## Network Security

### HTTPS in Production
The prototype runs on HTTP for local testing. For production:
- Deploy behind HTTPS reverse proxy (nginx, Apache, or cloud load balancer)
- Use TLS 1.2 or higher
- Implement HSTS headers
- Enable certificate pinning if needed

### CORS Configuration
Current CORS policy: `Access-Control-Allow-Origin: *`

For production, restrict to specific origins:
```python
allowed_origins = ["https://yourdomain.gov.in"]
```

## Security Best Practices

### Deployment Checklist
- [ ] Change all default passwords
- [ ] Generate new `JAN_DRISHTI_SECRET_KEY` environment variable
- [ ] Enable HTTPS with valid certificates
- [ ] Restrict CORS to trusted origins
- [ ] Configure firewall rules (allow only ports 80/443)
- [ ] Set up database backups
- [ ] Enable system logging to SIEM
- [ ] Review and harden file permissions
- [ ] Implement rate limiting
- [ ] Set up monitoring and alerting

### Password Policy
For production user accounts:
- Minimum 12 characters
- Mix of uppercase, lowercase, numbers, symbols
- No dictionary words
- Password expiry (90 days recommended)
- No password reuse (last 5 passwords)

### Token Management
- Tokens expire after 8 hours
- Users must re-login after expiry
- Logout immediately revokes client-side token
- Server-side token revocation can be added via sessions table

## Compliance Features

### Government Standards
JAN-DRISHTI is designed to meet:
- **ISO 27001**: Information security management
- **CERT-In Guidelines**: Indian cybersecurity compliance
- **RTI Act**: Transparent decision-making with audit trails
- **CAG Standards**: Audit-ready project tracking

### Audit Trail Requirements
- Immutable log records
- Timestamp integrity
- User accountability
- Action traceability
- Evidence preservation

## Vulnerability Reporting

If you discover a security vulnerability:
1. **Do not** create a public GitHub issue
2. Email security concerns to: [security@jandrishti.gov.in]
3. Include detailed reproduction steps
4. Allow 90 days for patch development

## Future Security Enhancements

Potential additions for production:
- Two-factor authentication (2FA)
- Single Sign-On (SSO) integration (OAuth2/SAML)
- Advanced threat detection
- Automated security scanning
- Data encryption at rest
- Key rotation policies
- Intrusion detection system (IDS)
- Security information and event management (SIEM) integration

## License and Liability

JAN-DRISHTI AI is a prototype for hackathon demonstration. For production use:
- Conduct professional security audit
- Implement additional hardening
- Follow your organization's security policies
- Obtain appropriate approvals and certifications

---

**Built for SIH26102** | Secure, Transparent & Auditable Fraud Detection
