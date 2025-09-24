# Entity Resolution Demo Setup Guide

## Quick Start (5 minutes)

### Minimal Demo Setup
```bash
# 1. Navigate to demo directory
cd demo/scripts

# 2. Generate sample data
python3 data_generator.py --records 1000 --output-dir ../data

# 3. Run automated demo
python3 demo_orchestrator.py --auto --records 1000

# 4. View results
# Demo report will be saved in demo/data/
```

### Dashboard Demo Setup
```bash
# 1. Generate data (if not done above)
python3 demo/scripts/data_generator.py --records 5000 --output-dir demo/data

# 2. Open dashboard in browser
open demo/templates/demo_dashboard.html
# Or: start a local web server for full functionality
python3 -m http.server 8080
# Then visit: http://localhost:8080/demo/templates/demo_dashboard.html
```

## Complete Setup (15 minutes)

### Prerequisites Check
```bash
# Check Python version (requires 3.8+)
python3 --version

# Check if ArangoDB is available (optional)
curl http://localhost:8529 2>/dev/null && echo "ArangoDB running" || echo "ArangoDB not available"

# Check required packages
pip install -r requirements.txt
```

### Full Demo Environment
```bash
# 1. Set up environment variables
cp env.example .env

# 2. Edit .env with your settings (if using ArangoDB)
# ARANGO_HOST=localhost
# ARANGO_PORT=8529
# ARANGO_USERNAME=root
# ARANGO_PASSWORD=testpassword123
# ARANGO_DATABASE=entity_resolution

# 3. Generate comprehensive demo data
cd demo/scripts
python3 data_generator.py --records 10000 --duplicate-rate 0.2 --output-dir ../data

# 4. Generate industry scenarios
python3 industry_scenarios.py

# 5. Test the complete demo
python3 demo_orchestrator.py --records 10000
```

## Demo Scenarios

### Scenario 1: Executive Briefing (15 minutes)
**Audience**: C-level, VPs, Decision Makers
**Focus**: Business value, ROI, competitive advantage

```bash
# Generate focused dataset
python3 data_generator.py --records 5000 --duplicate-rate 0.25 --output-dir ../data

# Run automated executive demo
python3 demo_orchestrator.py --auto --records 5000

# Key talking points:
# - $300K+ annual savings for typical enterprise
# - 500%+ first-year ROI
# - 99.9% efficiency improvement
# - Unique ArangoDB advantages
```

### Scenario 2: Technical Deep-Dive (45 minutes)
**Audience**: Engineers, Architects, Data Scientists
**Focus**: Technology, performance, implementation

```bash
# Generate large dataset for performance demo
python3 data_generator.py --records 25000 --duplicate-rate 0.2 --output-dir ../data

# Deploy Foxx services (requires ArangoDB)
cd ../../scripts/foxx
python3 automated_deploy.py

# Run interactive technical demo
cd ../../demo/scripts
python3 demo_orchestrator.py --records 25000

# Key talking points:
# - Sub-second processing for 25K records
# - ArangoDB's FTS+Graph capabilities
# - Scalability to millions of records
# - API integration examples
```

### Scenario 3: Industry-Specific Demo (30 minutes)
**Audience**: Industry experts, vertical specialists
**Focus**: Use case relevance, specific business challenges

```bash
# Choose industry scenario
python3 industry_scenarios.py

# Available scenarios:
# - B2B Sales: Lead deduplication
# - E-commerce: Customer 360
# - Healthcare: Patient matching
# - Financial: KYC and compliance

# Example: Healthcare demo
# Use demo/data/industry_scenarios/healthcare_scenario.json
# Customize talking points for patient safety and compliance
```

### Scenario 4: Self-Service Evaluation
**Audience**: Prospects for independent assessment
**Focus**: Hands-on experience, flexibility

```bash
# Create demo package
mkdir entity_resolution_demo
cp -r demo/ entity_resolution_demo/
cp requirements.txt entity_resolution_demo/
cp README.md entity_resolution_demo/

# Create setup script
cat > entity_resolution_demo/setup.sh << 'EOF'
#!/bin/bash
echo "Setting up Entity Resolution Demo..."
pip install -r requirements.txt
cd demo/scripts
python3 data_generator.py --records 5000 --output-dir ../data
echo "Demo ready! Run: python3 demo_orchestrator.py --auto --records 5000"
EOF

chmod +x entity_resolution_demo/setup.sh
```

## Customization Options

### Dataset Customization
```python
# Edit demo/scripts/data_generator.py

# Adjust duplicate patterns
class DataGenerator:
    def create_duplicate_variations(self, profile, num_variations=3):
        # Increase variations for higher duplicate complexity
        
# Adjust industry focus
industries = {
    'YourIndustry': {'employees': (100, 10000), 'revenue': (1000000, 100000000)}
}

# Adjust data quality
data_quality_score = random.randint(40, 100)  # Lower for worse quality
```

### ROI Customization
```python
# Edit demo/scripts/demo_orchestrator.py

# Prospect-specific costs
marketing_budget = customer_marketing_spend  # Use prospect's actual budget
customer_service_cost = customer_support_cost_per_customer
sales_efficiency_value = average_deal_size * conversion_rate_improvement

# Implementation costs
implementation_cost = custom_implementation_estimate
```

### Performance Tuning
```python
# For faster demos
records_count = 1000  # Smaller dataset
duplicate_rate = 0.3  # Higher duplicate rate for more dramatic results

# For impressive scale demos
records_count = 50000  # Larger dataset
use_foxx_services = True  # Enable for maximum performance
```

## Troubleshooting

### Common Setup Issues

1. **"Module not found" errors**
   ```bash
   # Ensure you're in the project root
   cd /path/to/arango-entity-resolution-record-blocking
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Check Python path
   export PYTHONPATH=$PWD:$PYTHONPATH
   ```

2. **ArangoDB connection failures**
   ```bash
   # Check if ArangoDB is running
   curl http://localhost:8529
   
   # Start ArangoDB with Docker
   docker run -p 8529:8529 -e ARANGO_ROOT_PASSWORD=testpassword123 arangodb/arangodb
   
   # Use Python fallback mode (demo works without ArangoDB)
   # The demo automatically falls back to Python implementation
   ```

3. **Memory issues with large datasets**
   ```bash
   # Reduce dataset size
   python3 data_generator.py --records 2000
   
   # Use auto mode to reduce memory usage
   python3 demo_orchestrator.py --auto
   
   # Monitor memory usage
   top -p $(pgrep -f demo_orchestrator)
   ```

4. **Slow performance**
   ```bash
   # Check system resources
   htop
   
   # Use smaller dataset for testing
   python3 demo_orchestrator.py --records 1000
   
   # Enable Foxx services for better performance
   python3 scripts/foxx/automated_deploy.py
   ```

### Demo Execution Issues

1. **Dashboard not loading data**
   ```bash
   # Ensure data files exist
   ls -la demo/data/
   
   # Serve dashboard with local web server
   cd demo/templates
   python3 -m http.server 8080
   ```

2. **Industry scenarios not generating**
   ```bash
   # Check output directory permissions
   mkdir -p demo/data/industry_scenarios
   chmod 755 demo/data/industry_scenarios
   
   # Run with verbose output
   python3 -v industry_scenarios.py
   ```

3. **Demo interruption/crashes**
   ```bash
   # Run in auto mode to avoid input issues
   python3 demo_orchestrator.py --auto
   
   # Check for existing data files
   ls -la demo/data/demo_customers.json
   
   # Clear cache and regenerate
   rm demo/data/demo_*.json
   python3 data_generator.py --records 5000 --output-dir demo/data
   ```

## Performance Optimization

### For Maximum Demo Impact
```bash
# 1. Use optimal dataset size
python3 data_generator.py --records 10000  # Sweet spot for demos

# 2. Enable all optimizations
export DEMO_MODE=performance
python3 demo_orchestrator.py --records 10000

# 3. Pre-generate all data
python3 data_generator.py --records 50000 --output-dir demo/data/large
python3 industry_scenarios.py

# 4. Warm up the system
python3 demo_orchestrator.py --auto --records 1000  # Quick test run
```

### For Reliability
```bash
# 1. Test everything beforehand
python3 demo_orchestrator.py --auto --records 1000

# 2. Prepare backup datasets
python3 data_generator.py --records 2000 --output-dir demo/data/small
python3 data_generator.py --records 10000 --output-dir demo/data/medium
python3 data_generator.py --records 25000 --output-dir demo/data/large

# 3. Have fallback options ready
# - Auto mode for network issues
# - Smaller datasets for memory issues
# - Dashboard demo for interactive needs
```

## Demo Checklist

### Pre-Demo (15 minutes before)
- [ ] Test complete demo run
- [ ] Check internet connectivity
- [ ] Verify data files exist
- [ ] Test dashboard in browser
- [ ] Prepare backup options
- [ ] Review talking points

### During Demo
- [ ] Start with business value
- [ ] Show live processing
- [ ] Highlight unique capabilities
- [ ] Invite questions
- [ ] Demonstrate flexibility
- [ ] Capture follow-up items

### Post-Demo
- [ ] Export demo results
- [ ] Share demo report
- [ ] Schedule follow-up meetings
- [ ] Plan proof-of-concept
- [ ] Document specific requirements
- [ ] Provide technical resources

## Success Metrics

### Demo Effectiveness Indicators
- **Audience engagement**: Questions about implementation details
- **Technical validation**: Requests for architecture documentation
- **Business buy-in**: Discussion of budget and timeline
- **Competitive interest**: Questions about alternatives
- **Next steps**: POC, pilot, or evaluation requests

### Follow-Up Actions
- **Immediate**: Demo report and technical documentation
- **1 week**: Proof-of-concept planning meeting
- **2 weeks**: Custom POC with prospect data
- **1 month**: Pilot program or full implementation planning

This setup guide ensures successful demo delivery across all audience types and scenarios.
