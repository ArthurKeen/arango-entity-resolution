# ArangoDB Entity Resolution Research

This directory contains academic papers, research notes, and analysis related to ArangoDB-based entity resolution and record blocking techniques.

## Directory Structure

- `papers/` - Academic papers and publications
- `notes/` - Research notes, summaries, and analysis

## Key Research Areas

### 1. Record Blocking Techniques
- Traditional blocking methods
- Advanced blocking strategies (Meta-blocking, Progressive blocking)
- Scalable blocking for big data

### 2. Similarity Metrics
- String similarity functions (Jaro-Winkler, Levenshtein, etc.)
- Phonetic matching algorithms
- Machine learning-based similarity

### 3. Clustering and Matching
- Graph-based clustering approaches
- Probabilistic matching models
- Active learning for entity resolution

### 4. Evaluation Metrics
- Precision, Recall, F1-score for entity resolution
- Reduction ratio and pairs completeness for blocking
- Scalability and performance benchmarks

## Academic Papers Referenced in PRD

The PRD already identifies several key papers:

1. **"A Survey of Blocking and Filtering Techniques for Entity Resolution"** - George Papadakis et al.
2. **"The Dedoop Framework for Scalable Entity Resolution"** - Köpcke and Thor
3. **"Probabilistic Models of Record Linkage and Deduplication"** - Fellegi and Sunter
4. **"A Comparative Analysis of Approximate Blocking Techniques for Entity Resolution"** - George Papadakis et al.
5. **"Magellan: Toward Building Entity Matching Management Systems"** - AnHai Doan et al.

## Research Workflow

1. **Paper Collection**: Gather relevant academic papers in `papers/` directory
2. **Analysis**: Create summary notes for each paper in `notes/`
3. **Implementation**: Extract actionable insights for the project
4. **Validation**: Test research findings against project requirements

## Contributing Research

When adding new research materials:
- Use consistent naming convention: `YYYY_AuthorLastName_ShortTitle.pdf`
- Create corresponding notes file: `YYYY_AuthorLastName_ShortTitle_notes.md`
- Update this README with new research areas as they emerge
- Link research findings to specific implementation decisions
