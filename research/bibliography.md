# Entity Resolution Research Bibliography

This bibliography contains all academic papers and research materials relevant to our ArangoDB Entity Resolution project, organized by topic and importance.

## Core Foundation Papers (From PRD)

### 1. Blocking and Filtering Techniques
**Papadakis, G., Papapetrou, O., Palpanas, T., & Koubarakis, M.** 
*"A Survey of Blocking and Filtering Techniques for Entity Resolution"* 
**Status**: Research notes available → [blocking/2014_Papadakis_BlockingFilteringSurvey_notes.md](papers/blocking/2014_Papadakis_BlockingFilteringSurvey_notes.md) 
**Importance**: Core blocking strategy foundation

### 2. Probabilistic Record Linkage Foundation 
**Fellegi, I. P., & Sunter, A. B. (1969)** 
*"A Theory for Record Linkage"* 
Journal of the American Statistical Association, 64(328), 1183-1210 
**DOI**: 10.1080/01621459.1969.10501049 
**Status**: Research notes available → [similarity/1969_Fellegi_ProbabilisticRecordLinkage_notes.md](papers/similarity/1969_Fellegi_ProbabilisticRecordLinkage_notes.md) 
**Importance**: Foundational theoretical framework

### 3. Scalable Entity Resolution Framework
**Köpcke, H., & Thor, A.** 
*"The Dedoop Framework for Scalable Entity Resolution"* 
**Status**: Referenced in PRD, research notes needed 
**Importance**: Scalability considerations

### 4. Comparative Blocking Analysis
**Papadakis, G., et al.** 
*"A Comparative Analysis of Approximate Blocking Techniques for Entity Resolution"* 
**Status**: Referenced in PRD, research notes needed 
**Importance**: Practical blocking method comparison

### 5. End-to-End System Design
**Doan, A., Ardalan, A., Naughton, J. R., & Ramakrishnan, R. (2016)** 
*"Magellan: Toward Building Entity Matching Management Systems"* 
VLDB Endowment 
**Status**: Research notes available → [systems/2016_Doan_MagellanEntityMatching_notes.md](papers/systems/2016_Doan_MagellanEntityMatching_notes.md) 
**Importance**: Complete system architecture

## Modern Survey Papers

### Comprehensive Entity Resolution Overview
**Christophides, V., Efthymiou, V., Palpanas, T., Papadakis, G., & Stefanidis, K.** 
*"End-to-End Entity Resolution for Big Data: A Survey"* 
arXiv:1905.06397 
**URL**: https://arxiv.org/abs/1905.06397 
**Status**: Available online, notes needed 
**Importance**: Modern comprehensive overview

## Graph-Based Approaches

### Knowledge Graph Entity Resolution
**Obraczka, D., Schuchart, J., & Rahm, E.** 
*"EAGER: Embedding-Assisted Entity Resolution for Knowledge Graphs"* 
arXiv:2101.06126 
**URL**: https://arxiv.org/abs/2101.06126 
**Status**: Available online, notes needed 
**Importance**: Graph embedding techniques

### Statistical Relational Methods
**Pujara, J., & Getoor, L.** 
*"Generic Statistical Relational Entity Resolution in Knowledge Graphs"* 
arXiv:1607.00992 
**URL**: https://arxiv.org/abs/1607.00992 
**Status**: Available online, notes needed 
**Importance**: Statistical graph methods

## Deep Learning and Embeddings for Entity Resolution

### Deep Learning for Entity Matching
**Mudgal, S., Li, H., Rekatsinas, T., Doan, A., Park, Y., Krishnan, G., Deep, R., Arcaute, E., & Raghavendra, V. (2018)**
*"Deep Learning for Entity Matching: A Design Space Exploration"*
ACM SIGMOD International Conference on Management of Data
**DOI**: 10.1145/3183713.3196926
**URL**: https://dl.acm.org/doi/10.1145/3183713.3196926
**Status**: Research notes available → [embeddings/2018_Mudgal_DeepLearningEntityMatching_notes.md](papers/embeddings/2018_Mudgal_DeepLearningEntityMatching_notes.md)
**Importance**: Foundational deep learning architectures for ER

### Distributed Tuple Embeddings
**Ebraheem, M., Thirumuruganathan, S., Joty, S., Ouzzani, M., & Tang, N. (2018)**
*"Distributed Representations of Tuples for Entity Resolution"*
Proceedings of the VLDB Endowment, 11(11), 1454-1467
**DOI**: 10.14778/3236187.3236198
**URL**: http://www.vldb.org/pvldb/vol11/p1454-ebraheem.pdf
**Status**: Research notes available → [embeddings/2018_Ebraheem_DistributedEntityMatching_notes.md](papers/embeddings/2018_Ebraheem_DistributedEntityMatching_notes.md)
**Importance**: Practical tuple embedding methods for structured data

### Deep Learning for Blocking
**Thirumuruganathan, S., Puthiya Parambath, S. A., Ouzzani, M., Tang, N., & Joty, S. (2021)**
*"Deep Learning for Blocking in Entity Matching: A Design Space Exploration"*
IEEE International Conference on Data Engineering (ICDE)
**DOI**: 10.1109/ICDE51399.2021.00095
**URL**: https://ieeexplore.ieee.org/document/9458727
**Status**: Research notes available → [blocking/2021_Thirumuruganathan_LearningBlocking_notes.md](papers/blocking/2021_Thirumuruganathan_LearningBlocking_notes.md)
**Importance**: Critical for embedding-based blocking strategies

## Specialized Techniques

### Heterogeneous Data Handling
**Author information needed** 
*"Efficient Entity Resolution on Heterogeneous Records"* 
arXiv:1610.09500 
**URL**: https://arxiv.org/abs/1610.09500 
**Status**: Available online, notes needed 
**Importance**: Schema heterogeneity solutions

### Multi-Intent Resolution
**Author information needed** 
*"FlexER: Flexible Entity Resolution for Multiple Intents"* 
arXiv:2209.07569 
**URL**: https://arxiv.org/abs/2209.07569 
**Status**: Available online, notes needed 
**Importance**: Advanced flexible approaches

## ArangoDB-Specific Resources

### Official Documentation and Tutorials
**ArangoDB Inc.** 
*"Entity Resolution in ArangoDB"* 
**URL**: https://arangodb.com/entity-resolution/ 
**Status**: Available online 
**Importance**: Platform-specific guidance

**ArangoDB Inc.** 
*"Graph and Entity Resolution Against Cyber Fraud"* 
**URL**: https://arangodb.com/2023/04/graph-and-entity-resolution-against-cyber-fraud/ 
**Status**: Available online 
**Importance**: Real-world use case examples

### Technical Sessions
**ArangoDB Inc.** 
*"Graph & Beyond Lunch Break #15: Entity Resolution"* 
**URL**: https://arangodb.com/resources/lunch-sessions/graph-beyond-lunch-break-15-entity-resolution/ 
**Status**: Video session available 
**Importance**: Practical implementation demo

## Research Gaps and Future Work

### Areas Needing Research
1. **ArangoDB-Native Algorithms**: Optimization for graph database architecture
2. **Real-time Entity Resolution**: Streaming and incremental processing
3. **Multi-modal Data**: Handling text, structured, and graph data together
4. **Privacy-Preserving ER**: Federated and secure entity resolution
5. **Automated Parameter Tuning**: ML-driven configuration optimization

### Potential Research Directions
- **Graph Neural Networks**: For similarity computation
- **Active Learning**: Efficient training data selection
- **Explainable AI**: Interpretable matching decisions
- **Distributed Processing**: Large-scale multi-node implementations

## Citation Guidelines

### Standard Format
For research notes and implementation references:

```
Author, A. B. (Year). Title of paper. Journal/Conference, Volume(Issue), pages.
DOI: doi_number (if available)
URL: paper_url (if available)
Notes: path/to/notes.md
Relevance: Brief description of relevance to project
```

### Implementation Citations
When implementing algorithms from papers:

```python
def algorithm_implementation():
 """
 Implementation based on:
 Author, A. B. (Year). "Paper Title". Conference/Journal.
 
 Original algorithm description on page X.
 Adapted for ArangoDB with modifications for [specific reasons].
 """
 pass
```

## Research Workflow

### Paper Acquisition Process
1. **Identify**: Reference in PRD or related work
2. **Search**: Academic databases (arXiv, ACM, IEEE, VLDB)
3. **Access**: Download PDF or access through institutional access
4. **Organize**: File with standard naming convention
5. **Summarize**: Create research notes with key insights

### Note-Taking Template
For each paper, create notes covering:
- **Abstract Summary**: Key contributions in 2-3 sentences
- **Relevance Assessment**: 1-5 star rating with justification
- **Key Concepts**: Main ideas and techniques
- **Implementation Insights**: How to apply to our project
- **Evaluation Methods**: How they measured success
- **Connections**: Links to other papers and concepts
- **Action Items**: Specific next steps for our implementation

### Implementation Tracking
- [ ] **Priority Queue**: Papers ordered by implementation importance
- [ ] **Algorithm Inventory**: Catalog of techniques to implement
- [ ] **Evaluation Benchmarks**: Standard datasets and metrics
- [ ] **Performance Baselines**: Reference implementations for comparison

## Status Summary

### Completed Research Notes
- Papadakis Blocking Survey (core concepts)
- Fellegi-Sunter Foundation (theoretical framework) 
- Magellan System Design (architecture principles)
- **NEW**: Mudgal et al. Deep Learning for Matching (DL architectures)
- **NEW**: Ebraheem et al. Tuple Embeddings (embedding methods)
- **NEW**: Thirumuruganathan et al. DL for Blocking (embedding-based blocking)

### Priority Research Needed
- Dedoop Scalability Framework
- Comparative Blocking Analysis
- Modern Big Data Survey (Christophides et al.)
- Graph Neural Networks for entity matching
- Transfer learning for domain-specific ER
- Active learning strategies for labeling

### Implementation Ready
- Basic blocking key strategies
- Fellegi-Sunter similarity scoring
- Modular system architecture
- Advanced blocking techniques
- **NEW**: Deep learning architectures (RNN, Attention)
- **NEW**: Tuple embedding generation (Siamese networks)
- **NEW**: Hybrid blocking (traditional + embeddings)
- **NEW**: LSH and ANN indexing strategies

This bibliography serves as the central hub for all research materials supporting our ArangoDB Entity Resolution project development.
