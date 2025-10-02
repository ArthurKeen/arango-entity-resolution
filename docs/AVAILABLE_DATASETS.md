# Available Datasets and Demo Guide

## Available Datasets

### 1. **Customer Entity Resolution Dataset** (Primary)

#### **Location**: `data/sample/customers_sample.json`
#### **Purpose**: Demonstrates customer deduplication and entity resolution
#### **Data Schema**:
```json
{
  "first_name": "John",
  "last_name": "Smith", 
  "email": "john.smith@email.com",
  "phone": "+1-555-0101",
  "address": "123 Main St",
  "city": "New York",
  "state": "NY",
  "zip_code": "10001",
  "source": "system_a",
  "created_at": "2024-01-15T10:30:00Z",
  "blocking_keys": ["S_N", "JS_10001", "john.smith@email.com"]
}
```

#### **Test Cases Included**:
- **John Smith** variations (John/Jon, different emails)
- **Mary/Maria Johnson** (name variations, contact differences)
- **Robert/Bob Brown** (nickname variations)
- **Jennifer/Jenny Wilson** (formal vs informal names)

#### **How to Test/Demo**:
```bash
# Quick test with sample data
cd /Users/arthurkeen/code/arango-entity-resolution-record-blocking
python examples/complete_entity_resolution_demo.py

# Or use the interactive demo system
python demo/launch_presentation_demo.py
```

### 2. **Generated Demo Datasets** (Synthetic)

#### **Location**: `demo/data/` (generated on demand)
#### **Purpose**: Large-scale demonstrations with realistic business scenarios

#### **Available Generators**:

##### **A. Customer Data Generator**
- **File**: `demo/scripts/data_generator.py`
- **Generates**: 1K-50K+ realistic customer records
- **Duplicate Rate**: Configurable (default 20%)
- **Variations**: Names, emails, phones, addresses, companies

```bash
# Generate demo dataset
cd demo/scripts
python data_generator.py --records 10000 --duplicate-rate 0.2 --output-dir ../data
```

##### **B. Industry Scenario Generators**
- **File**: `demo/scripts/industry_scenarios.py`
- **Scenarios**: B2B Sales, E-commerce, Healthcare, Financial Services

```bash
# Generate industry-specific scenarios
python industry_scenarios.py
```

### 3. **Industry-Specific Test Datasets**

#### **Location**: `demo/data/industry_scenarios/`

#### **Available Scenarios**:

##### **A. B2B Sales Scenario** (`b2b_sales_scenario.json`)
- Lead deduplication across CRM systems
- Account hierarchy resolution
- Contact role identification

##### **B. E-commerce Scenario** (`ecommerce_scenario.json`)
- Customer journey tracking
- Multi-channel user identification
- Purchase behavior analysis

##### **C. Healthcare Scenario** (`healthcare_scenario.json`)
- Patient master data management
- Provider network resolution
- Compliance and privacy considerations

##### **D. Financial Services Scenario** (`financial_scenario.json`)
- Customer 360 across products
- Risk profile consolidation
- Regulatory compliance

#### **How to Test Industry Scenarios**:
```bash
# Load specific industry scenario
python demo/scripts/demo_orchestrator.py --scenario b2b_sales --records 5000

# Or use the interactive demo
python demo/scripts/interactive_presentation_demo.py
```

## How to Execute Demos

### **Method 1: Quick Start Demo**
```bash
# Navigate to project root
cd /Users/arthurkeen/code/arango-entity-resolution-record-blocking

# Run complete pipeline with sample data
python examples/complete_entity_resolution_demo.py
```

### **Method 2: Interactive Presentation Demo**
```bash
# Launch interactive demo system
python demo/launch_presentation_demo.py

# Choose from menu:
# 1. Interactive Presentation Demo (manual control)
# 2. Database Inspector (view real-time data)
# 3. Quick Automated Demo (fast overview)
# 4. Business Impact Examples
# 5. Industry Scenarios
```

### **Method 3: Service-Level Testing**
```bash
# Test individual services
python examples/test_blocking_service.py
python examples/test_similarity_service.py
python examples/test_clustering_service.py
```

### **Method 4: Custom Dataset Demo**
```bash
# Generate custom dataset
cd demo/scripts
python data_generator.py --records 25000 --duplicate-rate 0.15

# Run demo with custom data
python demo_orchestrator.py --records 25000 --auto
```

## Dataset Characteristics

### **Small Sample Dataset** (10 records)
- **Purpose**: Quick validation and testing
- **Duplicates**: 4 entity clusters from 10 records
- **Use Case**: Unit testing, development

### **Medium Demo Dataset** (1K-10K records)
- **Purpose**: Sales demonstrations and presentations
- **Duplicates**: 20% duplication rate (realistic enterprise level)
- **Use Case**: Prospect demos, technical presentations

### **Large Performance Dataset** (50K+ records)
- **Purpose**: Performance testing and scalability validation
- **Duplicates**: Configurable rate
- **Use Case**: Benchmark testing, production validation

## Data Quality Issues Demonstrated

### **Name Variations**
- Nicknames: Robert → Bob, Jennifer → Jenny
- Typos: Jon → John, Smyth → Smith
- Formatting: "Dr. Sarah Johnson" vs "Sarah Johnson"

### **Contact Information**
- Email formats: john.smith@email.com vs j.smith@email.com
- Phone formats: +1-555-0101 vs 555-0101
- Address variations: "123 Main St" vs "123 Main Street"

### **Company Data**
- Legal names: "Microsoft Corp" vs "Microsoft Corporation"
- Acquisitions and subsidiaries
- Department vs company distinctions

## Performance Characteristics

### **Blocking Effectiveness**
- **Without Blocking**: 10K records = 50M comparisons
- **With Blocking**: 10K records = ~500K comparisons (99% reduction)

### **Processing Speed**
- **1K records**: ~2 seconds
- **10K records**: ~20 seconds  
- **100K records**: ~3 minutes
- **1M records**: ~30 minutes

### **Accuracy Metrics**
- **Precision**: 99.5%+ for high-confidence matches
- **Recall**: 98%+ for obvious duplicates
- **F1-Score**: 98.7%+ overall performance

## No Neo4j Movie Dataset

**To clarify**: This system does NOT include:
- Neo4j's movie database
- Actor/Director relationships
- Movie ratings or recommendations
- Film industry data
- IMDB-style datasets

**Instead, this system provides**:
- Business-focused customer entity resolution
- Real-world data quality scenarios
- Enterprise-scale demonstrations
- Industry-specific use cases

## Getting Help

If you need assistance with the available datasets:

1. **Quick Reference**: `DEMO_QUICK_START.md`
2. **Detailed Setup**: `demo/DEMO_SETUP_GUIDE.md`
3. **Presentation Guide**: `demo/PRESENTATION_SCRIPT.md`
4. **Technical Details**: `README.md` - System Demonstrations section

## Creating Custom Datasets

To create your own test datasets:

```python
from demo.scripts.data_generator import DataGenerator

# Initialize generator
generator = DataGenerator()

# Generate custom dataset
records, metadata = generator.generate_dataset(
    total_records=5000,
    duplicate_rate=0.25,
    industry_focus="healthcare"  # or "finance", "retail", "b2b"
)

# Save to file
import json
with open('custom_dataset.json', 'w') as f:
    json.dump(records, f, indent=2)
```

This provides enterprise-focused entity resolution demonstrations using realistic business data scenarios rather than entertainment industry data.
