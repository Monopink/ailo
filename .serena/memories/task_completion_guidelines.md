# Task Completion Guidelines

## When Task is Completed

### 1. Code Quality Checks

# Type checking
mypy backend/app/
```

### 2. Testing Requirements
```bash
# Run relevant tests
pytest backend/app/tests/
pytest -v  # For detailed output
```

### 3. Database Validation
- Ensure database migrations are applied
- Verify data integrity after changes
- Check foreign key constraints
- Validate JSON Schema compliance

### 4. Integration Testing
```bash
# Test API endpoints
curl http://localhost:8000/health

# Test admin panel access
# Navigate to http://localhost:8000/qiao-dash/
```

### 5. Documentation Updates
- Update relevant README files
- Document API changes
- Update prototype documentation if needed
- Add memory files for complex changes

## Design Principles Validation

### SOLID Principles Check
- **S**: Each service has single responsibility
- **O**: Extensions don't modify existing code
- **L**: Subclasses can replace parent classes
- **I**: Interfaces are specific and focused
- **D**: Depend on abstractions, not concretions

### KISS/YAGNI Validation
- Remove unnecessary complexity
- Avoid premature optimization
- Implement only required features
- Keep code simple and readable

### DRY Principle
- No code duplication
- Shared logic extracted to utilities
- Common patterns abstracted

## Specific Completion Criteria

### For AI Character Testing
- [ ] All precondition validations pass
- [ ] Test interface follows prototype design exactly
- [ ] Complete 11-step conversation flow works
- [ ] All data written to correct database tables
- [ ] Continuous conversation state maintained
- [ ] Security logging implemented
- [ ] Performance metrics captured

### For Architecture Changes
- [ ] No circular dependencies
- [ ] Layer boundaries respected
- [ ] Service responsibilities clear
- [ ] Error handling comprehensive
- [ ] Logging structured and contextual

### For Database Changes
- [ ] Foreign keys valid
- [ ] Data consistency maintained
- [ ] Migrations can be rolled back
- [ ] Performance impact assessed
