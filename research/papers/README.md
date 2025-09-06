# Academic Papers on Entity Resolution and Record Blocking

This directory contains academic papers and research materials that provide the theoretical foundation for our ArangoDB Entity Resolution project.

## Core Papers from PRD

The following papers are specifically referenced in our [Product Requirements Document](../../docs/PRD.md) as foundational works:

### 1. Blocking and Filtering Techniques
- **"A Survey of Blocking and Filtering Techniques for Entity Resolution"** by George Papadakis et al.
- **Importance**: Comprehensive survey of blocking methods and trade-offs
- **Relevance**: Core to our blocking key strategy implementation

### 2. Scalable Entity Resolution Frameworks  
- **"The Dedoop Framework for Scalable Entity Resolution"** by S. E. K. M. A. Köpcke and A. Thor
- **Importance**: Distributed computing approach to entity resolution
- **Relevance**: Scalability considerations for our ArangoDB implementation

### 3. Probabilistic Record Linkage Foundation
- **"Probabilistic Models of Record Linkage and Deduplication"** by A. E. M. L. Fellegi and A. B. Sunter
- **Importance**: Foundational paper introducing the Fellegi-Sunter model
- **Relevance**: Theoretical basis for our similarity scoring algorithms

### 4. Comparative Blocking Analysis
- **"A Comparative Analysis of Approximate Blocking Techniques for Entity Resolution"** by George Papadakis et al.
- **Importance**: Practical comparison of blocking methods with performance evaluation
- **Relevance**: Guides our choice of blocking strategies

### 5. End-to-End Entity Matching Systems
- **"Magellan: Toward Building Entity Matching Management Systems"** by AnHai Doan et al.
- **Importance**: Complete pipeline approach including data cleaning, blocking, and matching
- **Relevance**: Architectural guidance for our comprehensive system

## Additional Relevant Papers

### Modern Entity Resolution Surveys
- **"End-to-End Entity Resolution for Big Data: A Survey"** by Vassilis Christophides et al.
  - arXiv:1905.06397
  - Comprehensive overview of modern ER workflows for big data

### Graph-Based Approaches
- **"EAGER: Embedding-Assisted Entity Resolution for Knowledge Graphs"** by Daniel Obraczka et al.
  - arXiv:2101.06126
  - Combines graph embeddings with attribute similarities

- **"Generic Statistical Relational Entity Resolution in Knowledge Graphs"** by Jay Pujara, Lise Getoor
  - arXiv:1607.00992
  - Statistical relational approach to ER in knowledge graphs

### Advanced Techniques
- **"Efficient Entity Resolution on Heterogeneous Records"**
  - arXiv:1610.09500
  - Addresses schema heterogeneity challenges

- **"FlexER: Flexible Entity Resolution for Multiple Intents"**
  - arXiv:2209.07569
  - Multi-intent entity resolution approach

## Research Organization

### By Topic
- **`blocking/`** - Papers focused on blocking and filtering techniques
- **`similarity/`** - Similarity metrics and matching algorithms  
- **`clustering/`** - Entity clustering and grouping methods
- **`evaluation/`** - Evaluation metrics and benchmarking
- **`systems/`** - Complete system architectures and frameworks

### By Year
- **Classic (1969-2000)**: Foundational papers like Fellegi-Sunter
- **Modern (2001-2015)**: Advanced algorithms and distributed approaches
- **Contemporary (2016+)**: Machine learning and graph-based methods

## Citation Format

Papers are organized using the naming convention:
`YYYY_FirstAuthorLastName_ShortTitle.pdf`

Notes files follow the format:
`YYYY_FirstAuthorLastName_ShortTitle_notes.md`

## Access Notes

Due to copyright restrictions, PDF files of academic papers are not included in this repository. However, we provide:
- Complete bibliographic information
- Abstract summaries
- Key findings relevant to our project
- Links to official sources where available

## Contributing Research

When adding new papers:
1. Follow the established naming convention
2. Create corresponding notes file with key insights
3. Update this README with paper information
4. Link findings to specific implementation decisions
5. Categorize by relevant topic area

## Next Steps

1. **Priority Reading**: Focus on the 5 core papers from the PRD
2. **Implementation Mapping**: Connect paper findings to our code modules
3. **Evaluation Framework**: Use paper benchmarks for our testing
4. **Algorithm Selection**: Choose specific techniques based on paper comparisons
