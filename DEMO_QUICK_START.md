# Entity Resolution Demo - Quick Start Guide

## 🚀 One-Minute Demo Launch

```bash
# 1. Start ArangoDB (if not running)
./scripts/setup.sh

# 2. Launch demo system
python demo/launch_presentation_demo.py

# 3. Choose your demo type:
#    Option 1: Interactive Presentation (45-60 min)
#    Option 3: Quick Demo (15-20 min)
#    Option 6: Environment Check
```

## 📋 Demo Options

| Demo Type | Duration | Use Case | Command |
|-----------|----------|----------|---------|
| **Interactive Presentation** | 45-60 min | Live stakeholder demos | Option 1 |
| **Database Inspector** | As needed | Show actual data states | Option 2 |
| **Quick Demo** | 15-20 min | Time-constrained presentations | Option 3 |
| **Automated Demo** | 5-10 min | Testing and validation | Option 4 |

## 🎯 What Each Demo Shows

### Interactive Presentation Demo
- **Act 1**: Reveal duplicate customer problem (John Smith examples)
- **Act 2**: AI-powered entity resolution in action
- **Act 3**: Business value and ROI calculations

### Database Inspector
- Raw customer data with duplicates
- Similarity analysis results
- Entity clustering visualization
- Before/after comparisons

### Quick Demo
- Auto-advancing slides
- Key highlights only
- Business impact focus

## 💰 Business Impact Examples

| Company Size | Customers | Duplicate Cost | Annual Savings | ROI |
|--------------|-----------|----------------|----------------|-----|
| Small | 10,000 | $67,000 | $67,000 | 312% |
| Medium | 50,000 | $187,500 | $187,500 | 445% |
| Enterprise | 500,000 | $675,000 | $675,000 | 782% |

## 🔧 Troubleshooting

### If Demo Won't Start
```bash
# Check environment
python demo/launch_presentation_demo.py
# Choose option 6: Environment Check

# If ArangoDB isn't running
./scripts/setup.sh
```

### If Database Connection Fails
- Demos work without database (use static examples)
- Focus on business value presentation
- Use slides and talking points

## 📞 Demo Support

- **Presentation Script**: `demo/PRESENTATION_SCRIPT.md`
- **Technical Guide**: `docs/TESTING_SETUP.md`
- **Business ROI**: Built into all demos
- **Industry Examples**: Healthcare, Finance, Retail, B2B

## 🎬 Demo Controls

During interactive demos:
- **[Enter]** - Continue to next step
- **[a]** - Toggle auto mode (3-second delays)
- **[r]** - Repeat current section
- **[s]** - Skip to next major section
- **[q]** - Quit demo

## 📊 Success Metrics

Track these during presentations:
- ✅ Audience engagement level
- ✅ Questions about their specific challenges  
- ✅ Interest in technical deep dive
- ✅ Business pain points identified
- ✅ Next steps requested

---
**Ready to demonstrate? Run:** `python demo/launch_presentation_demo.py`
