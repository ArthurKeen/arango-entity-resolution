# Probabilistic Models of Record Linkage and Deduplication

**Authors**: Ivan P. Fellegi, Alan B. Sunter

**Publication**: Journal of the American Statistical Association, 1969

**Relevance to Project**: (Foundational Theory)

## Abstract Summary

This is the foundational paper in probabilistic record linkage that introduces the Fellegi-Sunter model. While not exclusively about blocking, it provides the theoretical underpinnings for scoring and matching records, which is the crucial step after blocking in our entity resolution pipeline.

## Key Theoretical Framework

### The Fellegi-Sunter Model

**Core Principle**: Use probability theory to determine if two records refer to the same entity.

**Mathematical Foundation**:
- **m-probability**: P(agreement | records match)
- **u-probability**: P(agreement | records don't match) 
- **Weight calculation**: log(m/u) for agreement, log((1-m)/(1-u)) for disagreement

### Decision Rules
1. **Link**: Total weight > upper threshold
2. **Non-link**: Total weight < lower threshold 
3. **Possible link**: Weight between thresholds (requires manual review)

## Core Concepts for Implementation

### Comparison Vectors
For each pair of records, create a comparison vector γ where:
- γ[i] = 1 if field i agrees between records
- γ[i] = 0 if field i disagrees between records

### Weight Calculation
```
Weight(γ) = Σ γ[i] * log(m[i]/u[i]) + Σ (1-γ[i]) * log((1-m[i])/(1-u[i]))
```

### Optimal Thresholds
- **Upper threshold (λ_u)**: Minimizes false positives
- **Lower threshold (λ_l)**: Minimizes false negatives
- **Gray area**: Records requiring manual review

## Relevance to Our ArangoDB Project

### For Similarity Scoring
After blocking reduces candidate pairs, apply Fellegi-Sunter scoring:

```python
def fellegi_sunter_score(record1, record2, field_weights):
 """Calculate Fellegi-Sunter similarity score"""
 score = 0
 for field, (m_prob, u_prob) in field_weights.items():
 if records_agree(record1[field], record2[field]):
 score += math.log(m_prob / u_prob)
 else:
 score += math.log((1 - m_prob) / (1 - u_prob))
 return score
```

### For Customer Data Fields
| Field | Agreement Type | m-probability | u-probability |
|-------|---------------|---------------|---------------|
| Email | Exact match | 0.95 | 0.001 |
| Phone | Exact match | 0.90 | 0.002 |
| Last Name | Approximate | 0.85 | 0.1 |
| First Name | Approximate | 0.80 | 0.15 |
| Address | Normalized | 0.75 | 0.05 |

### For ArangoDB Implementation
- Store m and u probabilities as configuration
- Calculate weights for each field comparison
- Apply thresholds to determine match likelihood
- Create edges in graph for different match confidence levels

## Implementation Strategy

### Phase 1: Manual Parameter Estimation
1. **Training Data**: Use manually labeled record pairs
2. **Calculate Frequencies**: Count agreements/disagreements for matches/non-matches
3. **Estimate Parameters**: Derive m and u probabilities

### Phase 2: EM Algorithm Implementation
1. **Expectation Step**: Estimate match probabilities given current parameters
2. **Maximization Step**: Update m and u parameters
3. **Iterate**: Until convergence

### Phase 3: Threshold Optimization
1. **Cost Functions**: Define costs for false positives/negatives
2. **Threshold Selection**: Minimize expected cost
3. **Validation**: Test on held-out data

## Modern Extensions

### String Similarity Integration
- Replace binary agreement with similarity scores
- Use Jaro-Winkler, Levenshtein, etc. for approximate matching
- Adapt weight calculations for continuous similarity

### Machine Learning Enhancement
- Use ML to learn better comparison functions
- Ensemble methods combining multiple similarity metrics
- Deep learning for complex field comparisons

## Evaluation Framework

### Quality Metrics
- **Precision**: True matches / Predicted matches
- **Recall**: True matches / Actual matches
- **F1-Score**: Harmonic mean of precision and recall

### Operational Metrics
- **Review Rate**: Percentage of pairs requiring manual review
- **Throughput**: Pairs processed per unit time
- **False Positive Rate**: Incorrect matches / Total non-matches

## Connection to Other Papers

### With Blocking Techniques
- **Papadakis Survey**: Provides candidate pair reduction before FS scoring
- **Comparative Analysis**: Different blocking methods feed into FS framework

### With System Design
- **Magellan**: End-to-end systems using FS as core matching component
- **Dedoop**: Distributed implementation of FS model

## Implementation Roadmap

### Immediate (Sprint 1)
- [ ] Implement basic FS scoring function
- [ ] Define field-specific m/u parameters for customer data
- [ ] Create threshold-based classification

### Short-term (Sprint 2-3)
- [ ] Add string similarity integration
- [ ] Implement EM parameter estimation
- [ ] Build evaluation framework

### Long-term (Sprint 4+)
- [ ] Machine learning enhancements
- [ ] Dynamic threshold adjustment
- [ ] Performance optimization

## ArangoDB Schema Implications

### Match Edges
```javascript
// Store match relationships with FS scores
{
 "_from": "customers/123",
 "_to": "customers/456", 
 "similarity_score": 8.5,
 "fellegi_sunter_weight": 12.3,
 "field_agreements": {
 "email": true,
 "phone": true,
 "last_name": false,
 "address": true
 },
 "match_probability": 0.95,
 "decision": "link" // link, non-link, or review
}
```

### Configuration Collection
```javascript
// Store FS parameters
{
 "field": "email",
 "m_probability": 0.95,
 "u_probability": 0.001,
 "comparison_type": "exact",
 "weight": 6.55 // log(m/u)
}
```

## Research Status

- [x] **Core Theory**: Understood from available summaries
- [ ] **Original Paper**: Need full access for detailed algorithms
- [ ] **Parameter Estimation**: Need to implement EM algorithm
- [ ] **Threshold Optimization**: Need cost function definition

## Key Takeaways

1. **Probabilistic Foundation**: Provides rigorous statistical basis for matching decisions
2. **Configurable**: Allows field-specific parameter tuning
3. **Scalable**: Separates parameter learning from matching
4. **Practical**: Handles uncertain matches through review process
5. **Extensible**: Modern adaptations maintain core principles
