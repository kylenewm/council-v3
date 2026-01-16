# Production System Framework

Build real systems for real users. AI startup quality - sophisticated, reliable, and built to last.

---

## When to Use This

- Building for actual users (not just demos)
- System that needs to run 24/7
- Enterprise/startup production deployment
- You're charging money for this
- Reputation is on the line

**NOT for:**
- Prototypes (use MVP_BUILD.md)
- One-time demos (use SHOWCASE_DEMO.md)
- Feature additions (use SANDBOX_TO_SCALE.md)

---

## Philosophy

```
Production = Reliability × Sophistication × Observability × Security
```

**This is what separates toy projects from real systems.**

A production system:
- Works when you're not watching
- Handles edge cases gracefully
- Tells you when something's wrong
- Recovers from failures
- Scales with demand
- Protects user data

---

## The Five Pillars

### 1. Reliability
The system works. Always.

- Handles failures gracefully
- Retries transient errors
- Has fallbacks for dependencies
- Doesn't lose data
- Degrades gracefully under load

### 2. Observability
You know what's happening.

- Structured logging
- Metrics and dashboards
- Alerting on anomalies
- Distributed tracing
- Error tracking

### 3. Security
User trust is earned.

- Authentication/authorization
- Data encryption (transit + rest)
- Input validation
- Secret management
- Audit logging

### 4. Scalability
Grows with users.

- Stateless where possible
- Horizontal scaling path
- Database indexing
- Caching strategy
- Rate limiting

### 5. Operability
Easy to run and maintain.

- CI/CD pipeline
- Infrastructure as code
- Rollback capability
- Documentation
- Runbooks for incidents

---

## The Build Process

### Phase 1: Architecture (15% of time)

Define the system before building.

```markdown
## System Architecture Document

### Components
- [ ] List all services/modules
- [ ] Define responsibilities
- [ ] Identify integration points

### Data Flow
- [ ] How data enters the system
- [ ] How data is processed
- [ ] How data is stored
- [ ] How data is served

### Failure Modes
- [ ] What can fail?
- [ ] How do we detect failure?
- [ ] How do we recover?

### Scale Path
- [ ] Current capacity estimate
- [ ] Bottlenecks identified
- [ ] Scaling strategy defined
```

### Phase 2: Foundation (25% of time)

Build the infrastructure that everything else relies on.

```
1. Project structure and configuration
2. Logging and error handling
3. Database schema and migrations
4. Authentication/authorization
5. CI/CD pipeline
6. Local development environment
7. Deployment infrastructure
```

**Quality bar:** This foundation will be touched by every feature. Get it right.

### Phase 3: Core Features (35% of time)

Build features with production quality from the start.

Each feature includes:
- Implementation
- Unit tests
- Integration tests
- Error handling
- Logging
- Documentation

```
Feature → Tests → Error Handling → Logging → Docs → Next
```

**No "add tests later."** Tests are part of the feature.

### Phase 4: Hardening (15% of time)

Make it production-ready.

```bash
# Security
- Input validation audit
- Dependency vulnerability scan
- Secret management review
- Penetration testing (if applicable)

# Performance
- Load testing
- Database query optimization
- Caching implementation
- CDN configuration

# Reliability
- Chaos testing
- Failure scenario testing
- Backup/restore testing
- Monitoring setup
```

### Phase 5: Launch Preparation (10% of time)

```bash
# Documentation
- User documentation
- API documentation
- Operations runbook
- Incident response plan

# Monitoring
- Dashboards created
- Alerts configured
- On-call rotation (if applicable)

# Deployment
- Staging environment tested
- Production deployment tested
- Rollback procedure verified
- Feature flags configured
```

---

## Production Checklist

### Architecture
- [ ] Components documented
- [ ] Data flow defined
- [ ] API contracts specified
- [ ] Failure modes identified

### Code Quality
- [ ] Consistent code style
- [ ] Functions are testable
- [ ] No hardcoded secrets
- [ ] Proper error handling
- [ ] Meaningful logging

### Testing
- [ ] Unit test coverage > 80%
- [ ] Integration tests for critical paths
- [ ] E2E tests for user flows
- [ ] Load tests completed
- [ ] Security tests passed

### Security
- [ ] Authentication implemented
- [ ] Authorization enforced
- [ ] Inputs validated
- [ ] Secrets managed properly
- [ ] HTTPS everywhere
- [ ] Dependencies audited

### Observability
- [ ] Structured logging
- [ ] Metrics exposed
- [ ] Tracing configured
- [ ] Error tracking enabled
- [ ] Dashboards created
- [ ] Alerts configured

### Deployment
- [ ] CI/CD pipeline works
- [ ] Staging matches production
- [ ] Rollback tested
- [ ] Database migrations automated
- [ ] Zero-downtime deploys

### Operations
- [ ] Runbook written
- [ ] Incident response plan
- [ ] Backup/restore tested
- [ ] Monitoring coverage complete

---

## Technical Standards

### Logging
```python
# BAD
print("error occurred")

# GOOD
logger.error(
    "payment_failed",
    user_id=user.id,
    amount=amount,
    error=str(e),
    trace_id=context.trace_id
)
```

### Error Handling
```python
# BAD
try:
    do_thing()
except:
    pass

# GOOD
try:
    result = do_thing()
except TransientError as e:
    logger.warning("transient_error", error=str(e))
    return retry_with_backoff(do_thing)
except PermanentError as e:
    logger.error("permanent_error", error=str(e))
    raise UserFacingError("Something went wrong. Please try again.")
```

### Configuration
```python
# BAD
API_KEY = "sk-1234..."

# GOOD
API_KEY = os.environ["API_KEY"]
# With validation on startup
assert API_KEY, "API_KEY environment variable required"
```

### Testing
```python
# Every feature has tests
def test_payment_success():
    result = process_payment(valid_card, amount=100)
    assert result.status == "success"
    assert result.charge_id is not None

def test_payment_insufficient_funds():
    result = process_payment(low_balance_card, amount=10000)
    assert result.status == "declined"
    assert result.reason == "insufficient_funds"

def test_payment_network_failure():
    with mock_network_failure():
        result = process_payment(valid_card, amount=100)
        assert result.status == "pending"
        assert result.retry_scheduled
```

---

## Observability Stack

### Minimum Viable Observability
```
Logs → Structured JSON logs to stdout
Metrics → Prometheus/StatsD
Traces → OpenTelemetry
Errors → Sentry/Rollbar
Dashboards → Grafana/Datadog
```

### Key Metrics
```
# System
- Request rate
- Error rate
- Latency (p50, p95, p99)
- CPU/Memory utilization

# Business
- Active users
- Transactions processed
- Revenue (if applicable)
- Key conversion rates
```

### Alerts
```yaml
# Critical (page immediately)
- Error rate > 10%
- Latency p99 > 5s
- System down

# Warning (review soon)
- Error rate > 1%
- Disk usage > 80%
- Unusual traffic pattern

# Info (review daily)
- Deployment completed
- New error type seen
- Traffic milestone reached
```

---

## Security Baseline

### Authentication
- [ ] Secure password storage (bcrypt/argon2)
- [ ] Session management
- [ ] OAuth/SSO if applicable
- [ ] Rate limiting on auth endpoints
- [ ] Account lockout on repeated failures

### Authorization
- [ ] Role-based access control
- [ ] Resource ownership checks
- [ ] API key scoping
- [ ] Audit logging for sensitive actions

### Data Protection
- [ ] Encryption at rest
- [ ] Encryption in transit (TLS)
- [ ] PII handling compliant
- [ ] Data retention policy
- [ ] Backup encryption

### Input Validation
- [ ] All inputs validated
- [ ] SQL injection prevented
- [ ] XSS prevented
- [ ] File upload restrictions
- [ ] Request size limits

---

## Deployment Strategy

### CI/CD Pipeline
```yaml
# Every push
1. Lint
2. Unit tests
3. Build

# Every PR merge
4. Integration tests
5. Security scan
6. Deploy to staging

# Production deploy
7. E2E tests on staging
8. Deploy to production (canary)
9. Monitor metrics
10. Full rollout or rollback
```

### Infrastructure as Code
```
# Everything is version controlled
terraform/
  production/
  staging/
  modules/
kubernetes/
  deployments/
  services/
  configs/
```

### Rollback Plan
```bash
# Instant rollback capability
# Every deploy can be reverted in < 5 minutes

# Database
- Backward-compatible migrations only
- Or: Feature flags to control new code paths

# Code
- Previous version always deployable
- Blue-green or canary deploys
```

---

## Parallel Development

Production systems benefit from specialized agents:

```
Orchestrator
├── Backend Agent: "Core API and business logic"
├── Infrastructure Agent: "CI/CD, deployment, monitoring"
├── Security Agent: "Auth, validation, audit"
├── Frontend Agent: "UI and user experience"
└── QA Agent: "Test coverage and quality gates"
```

**Integration points defined upfront.** Agents work in parallel on agreed interfaces.

---

## Quality Gates

### Before Feature Merge
- [ ] Code reviewed
- [ ] Tests pass
- [ ] Coverage maintained
- [ ] No new vulnerabilities
- [ ] Documentation updated

### Before Production Deploy
- [ ] Staging tested
- [ ] Load test passed
- [ ] Security review (if applicable)
- [ ] Rollback plan confirmed
- [ ] Monitoring ready

### After Production Deploy
- [ ] Metrics nominal
- [ ] No new errors
- [ ] User-facing functionality verified
- [ ] Performance acceptable

---

## Common Mistakes

### 1. Skipping tests "to move fast"
**Wrong:** "We'll add tests later"
**Right:** Tests are part of the feature. No exceptions.

### 2. Logging as afterthought
**Wrong:** Add logging when debugging production
**Right:** Structured logging from day one

### 3. Security as last step
**Wrong:** "We'll secure it before launch"
**Right:** Security is built in, not bolted on

### 4. No rollback plan
**Wrong:** "This deploy will work"
**Right:** Every deploy has a tested rollback

### 5. Monitoring after launch
**Wrong:** "We'll add dashboards when we need them"
**Right:** Dashboards and alerts before first user

---

## Time Investment

| Phase | Time | Focus |
|-------|------|-------|
| Architecture | 15% | Design and planning |
| Foundation | 25% | Infrastructure and patterns |
| Core Features | 35% | Features with full quality |
| Hardening | 15% | Security and performance |
| Launch Prep | 10% | Docs, monitoring, final checks |

**Total time is 3-5x MVP time** - but the system actually works in production.

---

## Summary

```
1. ARCHITECTURE: Design before building
2. FOUNDATION: Infrastructure and patterns
3. FEATURES: Built with tests, logging, docs
4. HARDENING: Security, performance, reliability
5. LAUNCH: Monitoring, runbooks, preparation

Production = Works when you're not watching
Quality is not optional
Security is not a feature
Observability is not a luxury
```

---

## Comparison: When to Use What

| Framework | Speed | Quality | Use Case |
|-----------|-------|---------|----------|
| MVP_BUILD | Fast | Basic | Validate idea |
| SANDBOX_TO_SCALE | Medium | High | Add features |
| SHOWCASE_DEMO | Medium | Polish | Impress people |
| PRODUCTION_SYSTEM | Slow | Highest | Real users |
