# Pre-Submission Checklist for IC Enrichment Pack

**Target:** Arango Entity Resolution Library contribution 
**Status:** NOT READY - Complete checklist before outreach

---

## Critical Blockers 

### [ ] 1. Metrics Validation (REQUIRED)

**Current status:** Metrics unsubstantiated 
**Time required:** 1-2 days 
**Blocking:** Yes - maintainers will immediately reject without this

**Tasks:**
- [ ] Create labeled ground truth test set
- [ ] 100-200 entity pairs minimum
- [ ] Manual labels: match/no-match
- [ ] Document labeling criteria
- [ ] Save as `evaluation/ground_truth.json`

- [ ] Implement baseline evaluation
- [ ] Run ER Library without enhancements
- [ ] Calculate precision, recall, F1
- [ ] Save as `evaluation/baseline_results.json`

- [ ] Implement enhanced evaluation
- [ ] Add components one at a time
- [ ] Measure incremental improvements
- [ ] Save as `evaluation/enhanced_results.json`

- [ ] Document methodology
- [ ] Create `evaluation/METHODOLOGY.md`
- [ ] Include dataset description
- [ ] Include experimental setup
- [ ] Include reproducibility instructions

- [ ] Statistical analysis
- [ ] Run 5-fold cross-validation
- [ ] Calculate confidence intervals
- [ ] Test statistical significance
- [ ] Report in results table

**Acceptance criteria:**
```markdown
## Validation Results

**Dataset:** 847 OR1200 entities, 156 labeled pairs
**Methodology:** 5-fold cross-validation
**Baseline:** ER Library WeightedFieldSimilarity

| Configuration | Precision | Recall | F1 | p-value |
|--------------|-----------|--------|-----|---------|
| Baseline | X.XX | X.XX | X.XX | - |
| + Type | X.XX (+Y%) | X.XX | X.XX | <0.05 |
| + Context | X.XX (+Y%) | X.XX | X.XX | <0.05 |
| + Acronyms | X.XX (+Y%) | X.XX | X.XX | <0.05 |

**Reproducibility:** `python evaluation/run_experiments.py`
```

---

### [ ] 2. Domain-Agnostic Validation (REQUIRED)

**Current status:** Only hardware tested 
**Time required:** 4 hours 
**Blocking:** Yes - "domain-agnostic" claim is currently false

**Tasks:**
- [ ] Choose non-hardware domain
- Option 1: Medical terminology (easiest - acronyms abundant)
- Option 2: Organization hierarchies (good for context)
- Option 3: E-commerce products (good for types)

- [ ] Create example file
- [ ] `ic_enrichment/examples/medical_er_example.py` OR
- [ ] `ic_enrichment/examples/organization_er_example.py` OR
- [ ] `ic_enrichment/examples/ecommerce_er_example.py`

- [ ] Implement example
- [ ] Sample data (10-20 entities)
- [ ] Type compatibility matrix (if applicable)
- [ ] Acronym dictionary (if applicable)
- [ ] Hierarchical relationships (if applicable)
- [ ] Working demonstration

- [ ] Update README
- [ ] Add new example to examples list
- [ ] Update use cases section
- [ ] Show non-hardware domain

**Acceptance criteria:**
- Working example in second domain
- Demonstrates at least 2 of the 4 components
- Code runs without errors
- Shows clear use case

---

### [ ] 3. Rewrite Outreach Document (REQUIRED)

**Current status:** Overclaims results, missing details 
**Time required:** 2 hours 
**Blocking:** Yes - will damage credibility

**Tasks:**

#### Remove/Revise Claims
- [ ] Remove "+35% precision, +31% recall" (until validated)
- [ ] Remove "domain-agnostic (tested beyond hardware)" (until tested)
- [ ] Remove "Production-tested, validated" (only one production system)
- [ ] Change "4 reusable components" to "2 core + 2 utilities"

#### Add Required Sections
- [ ] Technical Requirements section
```markdown
## Technical Requirements
- Python 3.8+
- Zero external dependencies (stdlib only)
- Optional: python-arango for ArangoDB examples
- License: MIT
```

- [ ] Limitations section
```markdown
## Limitations
- Validated on IC design domain only
- Context resolver uses bag-of-words (no semantic similarity)
- Acronym handler requires manual dictionary curation
- Relationship sweeper assumes graph data model
```

- [ ] Maintenance Commitment section
```markdown
## Maintenance Commitment
- Committed to maintaining for 2+ years
- Will respond to issues within 1 week
- Will review PRs from community
- Willing to assign copyright to library project
```

#### Tone Changes
- [ ] Change from "We've proven this works" to "We've built this for hardware, seeking feedback"
- [ ] Change from "These solve universal problems" to "These might help in technical domains"
- [ ] Add questions for maintainers instead of only statements

---

## Important (Non-Blocking) 

### [ ] 4. Code Cleanup

**Time required:** 2 hours

- [ ] Add LICENSE file (MIT)
- [ ] Add CONTRIBUTING.md
- [ ] Add setup.py for pip install
- [ ] Run pytest and fix any failures
- [ ] Run linter and fix errors
- [ ] Check all examples run successfully

### [ ] 5. Documentation Enhancement

**Time required:** 3 hours

- [ ] Create API reference document
- [ ] Add troubleshooting section
- [ ] Add FAQ section
- [ ] Add integration guide showing how to use with ER Library
- [ ] Add performance tuning guide

### [ ] 6. Component-Specific Issues

#### Acronym Handler
- [ ] Implement unused `expansion_strategy` parameter (union/intersection/ranked)
- [ ] Or remove parameter if not needed

#### Relationship Sweeper
- [ ] Fix magic number in cycle detection (100 -> make configurable)
- [ ] Add tests for edge cases

---

## Recommended Outreach Strategy

### Option A: Start with Discussion (RECOMMENDED)

**Why:** Lower risk, get feedback before investing in full validation

**Steps:**
1. [ ] Complete items 1-3 above (validation, second domain, rewrite)
2. [ ] Open GitHub Discussion (not Issue, not PR)
3. [ ] Post SHORT inquiry (200 words max)
4. [ ] Include link to code and working example
5. [ ] Ask specific questions about fit/scope
6. [ ] Wait for maintainer response

**Discussion template:**
```markdown
Title: Feedback Request: Type Constraints and Hierarchical Context

Hi maintainers,

I've built two ER enhancements for IC design that might benefit other 
technical domains:

1. Hierarchical Context Resolver - boosts candidates using parent context
2. Type Compatibility Filter - prevents type-incompatible matches

Tested on hardware with positive results. Code is designed to be general 
(tested on medical terminology as well).

Questions:
- Do features like these align with library goals?
- Better as core library or companion package?
- What validation would you want to see?

Code: [link]
Examples: [hardware_er_example.py, medical_er_example.py]

Thanks!
```

### Option B: Full Proposal

**Why:** If you're confident in alignment and have completed all validation

**Steps:**
1. [ ] Complete ALL items above (1-6)
2. [ ] Create formal RFC (Request for Comments) issue
3. [ ] Include complete technical proposal
4. [ ] Include validated metrics
5. [ ] Include integration design
6. [ ] Wait for feedback before starting implementation

---

## Pre-Submission Self-Review

### Can I answer these questions honestly?

- [ ] "How did you measure the +35% precision improvement?"
- Answer: [Detailed methodology with reproducible experiments]

- [ ] "Have you tested this on domains other than hardware?"
- Answer: [Yes, here's the medical/org/ecommerce example]

- [ ] "How does this integrate with existing library architecture?"
- Answer: [Specific integration points identified]

- [ ] "What are the limitations of your approach?"
- Answer: [Honest assessment of failure modes]

- [ ] "Are you willing to maintain this long-term?"
- Answer: [Yes, committed to 2+ years]

- [ ] "What license is this under?"
- Answer: [MIT, willing to assign copyright]

### Red Flags (DO NOT SEND if any are true)

- [ ] I can't reproduce my metrics claims
- [ ] I've only tested on one domain but claim it's general
- [ ] I'm not sure where these components fit in the library
- [ ] I haven't actually read the library's contribution guidelines
- [ ] I expect maintainers to do the integration work
- [ ] I'm not willing to revise based on feedback

---

## Estimated Timeline

### Minimum Viable Outreach
- Metrics validation: 1-2 days
- Second domain example: 4 hours
- Rewrite outreach: 2 hours
- **Total: 2-3 days**

### Full Polish
- Above + code cleanup: +2 hours
- Above + documentation: +3 hours
- Above + component fixes: +2 hours
- **Total: 3-4 days**

---

## Success Criteria

### You're ready to send when:

You can show maintainers a table of validated metrics 
You have working examples in 2+ domains 
Your outreach is honest about limitations 
You've answered all "Pre-Submission Self-Review" questions 
All code runs without errors 
Documentation is complete and accurate

### You're NOT ready if:

Metrics are estimates/projections, not measurements 
Only one domain tested 
Outreach overclaims results 
Code has errors or missing examples 
You can't answer maintainer questions about methodology

---

## After Sending

### Expected Timeline
- Initial response: 1-4 weeks (maintainers are busy)
- Discussion phase: 2-4 weeks
- Implementation: 4-8 weeks
- **Total: 2-4 months from first contact to merged PR**

### Likely Questions from Maintainers
1. "Can you show the evaluation methodology?"
2. "Have you tested on other domains?"
3. "How does this integrate with existing components?"
4. "What's the maintenance plan?"
5. "Can you submit a PR with tests?"

Be ready to answer all of these with specific details.

---

## Final Checklist Before Clicking Send

- [ ] Metrics validated with ground truth
- [ ] Second domain example exists
- [ ] Outreach document revised
- [ ] All code runs successfully
- [ ] Documentation complete
- [ ] Pre-submission self-review passed
- [ ] Started with Discussion (not full proposal)
- [ ] Maintainer questions anticipated

**Status:** Ready Not Ready

---

**Last Updated:** January 2, 2026 
**Next Review:** After completing critical blockers

