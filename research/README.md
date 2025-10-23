# ArangoDB Entity Resolution Research

This directory contains academic papers, research notes, and analysis related to ArangoDB-based entity resolution and record blocking techniques.

## Directory Structure

- `papers/` - Academic papers and publications
- `notes/` - Research notes, summaries, and analysis

## Key Research Areas

### 1. Record Blocking Techniques
- Traditional blocking methods (exact, phonetic, n-gram)
- Advanced blocking strategies (Meta-blocking, Progressive blocking)
- **NEW**: Deep learning-based blocking with embeddings
- **NEW**: Hybrid approaches (traditional + learned)
- Scalable blocking for big data

### 2. Similarity Metrics
- String similarity functions (Jaro-Winkler, Levenshtein, etc.)
- Phonetic matching algorithms
- Probabilistic matching (Fellegi-Sunter framework)
- **NEW**: Deep learning similarity (RNN, Attention, Siamese networks)
- **NEW**: Embedding-based similarity (cosine, Euclidean)

### 3. Embeddings and Deep Learning
- **NEW**: Tuple embeddings for structured data
- **NEW**: Multi-resolution embeddings (coarse + fine)
- **NEW**: Siamese networks for similarity learning
- **NEW**: Transfer learning and pre-training strategies
- **NEW**: LSH and ANN indexing for vector search

### 4. Clustering and Matching
- Graph-based clustering approaches
- Probabilistic matching models
- Active learning for entity resolution
- Hard negative mining and contrastive learning

### 5. Evaluation Metrics
- Precision, Recall, F1-score for entity resolution
- Reduction ratio and pairs completeness for blocking
- Scalability and performance benchmarks

## Academic Papers Referenced in PRD

The PRD identifies several key foundational papers. Research notes are now available for the core papers:

1. **"A Survey of Blocking and Filtering Techniques for Entity Resolution"** - George Papadakis et al.
 - **Notes**: [papers/blocking/2014_Papadakis_BlockingFilteringSurvey_notes.md](papers/blocking/2014_Papadakis_BlockingFilteringSurvey_notes.md)
 - **Status**: Core concepts documented, implementation ready

2. **"Probabilistic Models of Record Linkage and Deduplication"** - Fellegi and Sunter (1969)
 - **Notes**: [papers/similarity/1969_Fellegi_ProbabilisticRecordLinkage_notes.md](papers/similarity/1969_Fellegi_ProbabilisticRecordLinkage_notes.md)
 - **Status**: Theoretical framework understood, ready for implementation

3. **"Magellan: Toward Building Entity Matching Management Systems"** - AnHai Doan et al. (2016)
   - **Notes**: [papers/systems/2016_Doan_MagellanEntityMatching_notes.md](papers/systems/2016_Doan_MagellanEntityMatching_notes.md)
   - **Status**: System architecture principles documented

4. **"Deep Learning for Entity Matching: A Design Space Exploration"** - Mudgal et al. (2018)
   - **Notes**: [papers/embeddings/2018_Mudgal_DeepLearningEntityMatching_notes.md](papers/embeddings/2018_Mudgal_DeepLearningEntityMatching_notes.md)
   - **Status**: Foundational DL architectures documented, ready for Phase 3

5. **"Distributed Representations of Tuples for Entity Resolution"** - Ebraheem et al. (2018)
   - **Notes**: [papers/embeddings/2018_Ebraheem_DistributedEntityMatching_notes.md](papers/embeddings/2018_Ebraheem_DistributedEntityMatching_notes.md)
   - **Status**: Tuple embedding methods documented, practical implementation guide

6. **"Deep Learning for Blocking in Entity Matching"** - Thirumuruganathan et al. (2021)
   - **Notes**: [papers/blocking/2021_Thirumuruganathan_LearningBlocking_notes.md](papers/blocking/2021_Thirumuruganathan_LearningBlocking_notes.md)
   - **Status**: Critical for embedding-based blocking, hybrid approach documented

7. **"The Dedoop Framework for Scalable Entity Resolution"** - Köpcke and Thor
   - **Status**: Research notes needed

8. **"A Comparative Analysis of Approximate Blocking Techniques for Entity Resolution"** - George Papadakis et al.
   - **Status**: Research notes needed

## Research Organization

### By Topic Areas
- **`papers/blocking/`** - Blocking and filtering techniques (traditional + deep learning)
- **`papers/similarity/`** - Similarity metrics and scoring methods 
- **`papers/embeddings/`** - **NEW**: Deep learning and embedding-based approaches
- **`papers/clustering/`** - Entity clustering and grouping approaches
- **`papers/evaluation/`** - Evaluation metrics and benchmarking methods
- **`papers/systems/`** - Complete system architectures and frameworks 

### Research Status
- **Core Foundation**: Key papers from PRD have research notes (6 papers documented)
- **Implementation Ready**: Traditional blocking, similarity scoring, **deep learning architectures**
- **Phase 3 Ready**: Embedding-based blocking and similarity with complete implementation guides
- **Additional Papers**: Modern surveys and specialized techniques being added
- **Bibliography**: Comprehensive catalog in [bibliography.md](bibliography.md)

## Research Workflow

1. **Paper Collection**: Gather relevant academic papers in `papers/` directory
2. **Analysis**: Create summary notes for each paper using standardized template
3. **Implementation**: Extract actionable insights and algorithms for the project
4. **Validation**: Test research findings against project requirements
5. **Documentation**: Update bibliography and cross-reference implementations

## Contributing Research

When adding new research materials:
- Use consistent naming convention: `YYYY_AuthorLastName_ShortTitle.pdf`
- Create corresponding notes file: `YYYY_AuthorLastName_ShortTitle_notes.md`
- Update this README with new research areas as they emerge
- Link research findings to specific implementation decisions
