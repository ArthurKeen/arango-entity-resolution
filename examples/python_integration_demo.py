#!/usr/bin/env python3
"""
Entity Resolution Python Integration Demo

Demonstrates the complete Python-based entity resolution pipeline:
1. Data loading and validation
2. System setup (collections, analyzers, views)
3. Entity resolution pipeline execution
4. Results analysis and reporting
5. Integration with Foxx services (when available)

This script showcases both standalone Python mode and hybrid Python/Foxx mode.
"""

import os
import sys
import json
import time
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from entity_resolution import (
    EntityResolver, 
    DataManager, 
    Config,
    BlockingService,
    SimilarityService,
    ClusteringService
)
from entity_resolution.utils.logging import setup_logging, get_logger


def main():
    """Run the complete entity resolution demo"""
    
    # Set up logging
    logger = setup_logging(log_level="INFO", enable_debug=True)
    logger.info("=== Entity Resolution Python Integration Demo ===")
    
    # Load configuration
    config = Config.from_env()
    logger.info(f"Configuration loaded: Foxx services {'enabled' if config.er.enable_foxx_services else 'disabled'}")
    logger.info(f"Database: {config.db.host}:{config.db.port}")
    
    try:
        # Stage 1: Initialize the entity resolution pipeline
        logger.info("\n📊 Stage 1: Initializing Entity Resolution Pipeline")
        
        pipeline = EntityResolver(config)
        
        if not pipeline.connect():
            logger.error("Failed to connect to database")
            return False
        
        logger.info("✅ Pipeline connected successfully")
        
        # Stage 2: Load sample data
        logger.info("\n📁 Stage 2: Loading Sample Data")
        
        sample_data_path = Path(__file__).parent.parent / "data" / "sample" / "customers_sample.json"
        
        if not sample_data_path.exists():
            logger.error(f"Sample data file not found: {sample_data_path}")
            return False
        
        load_result = pipeline.load_data(str(sample_data_path), "customers")
        
        if not load_result["success"]:
            logger.error(f"Failed to load data: {load_result.get('error')}")
            return False
        
        logger.info(f"✅ Loaded {load_result['inserted_records']} customer records")
        
        # Display data quality analysis
        if "data_quality" in load_result and load_result["data_quality"]["success"]:
            quality = load_result["data_quality"]
            logger.info(f"📈 Data Quality Score: {quality['overall_quality_score']:.1f}%")
            
            # Show field analysis
            for field, analysis in quality["field_analysis"].items():
                if not field.startswith('_'):
                    logger.info(f"   - {field}: {analysis['non_null_count']}/{analysis['total_count']} records ({100-analysis['null_percentage']:.1f}% complete)")
        
        # Stage 3: Set up the system
        logger.info("\n⚙️  Stage 3: Setting Up Entity Resolution System")
        
        setup_result = pipeline.setup_system(["customers"])
        
        if not setup_result["success"]:
            logger.error(f"Failed to set up system: {setup_result.get('error')}")
            return False
        
        logger.info("✅ System setup completed")
        logger.info(f"   - Collections initialized: {len(setup_result.get('created', []))}")
        
        # Stage 4: Run entity resolution
        logger.info("\n🔍 Stage 4: Running Entity Resolution Pipeline")
        
        er_start_time = time.time()
        er_result = pipeline.run_entity_resolution("customers", similarity_threshold=0.7)
        er_end_time = time.time()
        
        if not er_result["success"]:
            logger.error(f"Entity resolution failed: {er_result.get('error')}")
            return False
        
        # Display results
        logger.info("✅ Entity Resolution Completed!")
        logger.info(f"⏱️  Total processing time: {er_end_time - er_start_time:.2f} seconds")
        logger.info(f"📊 Results Summary:")
        logger.info(f"   - Input records: {er_result['input_records']}")
        logger.info(f"   - Candidate pairs generated: {er_result['candidate_pairs']}")
        logger.info(f"   - Pairs scored: {er_result['scored_pairs']}")
        logger.info(f"   - Entity clusters found: {er_result['entity_clusters']}")
        
        # Performance breakdown
        perf = er_result["performance"]
        logger.info(f"📈 Performance Breakdown:")
        logger.info(f"   - Blocking: {perf['blocking_time']:.2f}s")
        logger.info(f"   - Similarity: {perf['similarity_time']:.2f}s") 
        logger.info(f"   - Clustering: {perf['clustering_time']:.2f}s")
        
        # Stage 5: Analyze clusters
        logger.info("\n🔍 Stage 5: Analyzing Entity Clusters")
        
        clusters = er_result["stages"]["clustering"]["clusters"]
        
        if clusters:
            logger.info(f"Found {len(clusters)} entity clusters:")
            
            for i, cluster in enumerate(clusters[:5]):  # Show first 5 clusters
                logger.info(f"   Cluster {i+1}: {cluster['cluster_size']} entities")
                logger.info(f"      - Average similarity: {cluster.get('average_similarity', 0):.3f}")
                logger.info(f"      - Quality score: {cluster.get('quality_score', 0):.3f}")
                logger.info(f"      - Members: {cluster['member_ids'][:3]}{'...' if len(cluster['member_ids']) > 3 else ''}")
            
            if len(clusters) > 5:
                logger.info(f"   ... and {len(clusters) - 5} more clusters")
        else:
            logger.info("No entity clusters found - try lowering the similarity threshold")
        
        # Stage 6: Test individual services
        logger.info("\n🧪 Stage 6: Testing Individual Services")
        
        test_services(config, logger)
        
        # Stage 7: Generate summary report
        logger.info("\n📋 Stage 7: Generating Summary Report")
        
        generate_summary_report(pipeline, er_result, logger)
        
        logger.info("\n✅ Demo completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Demo failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_services(config: Config, logger):
    """Test individual services independently"""
    
    # Test Blocking Service
    logger.info("Testing Blocking Service...")
    blocking_service = BlockingService(config)
    blocking_service.connect()
    
    # Test setup
    setup_result = blocking_service.setup_for_collections(["customers"])
    logger.info(f"   Blocking setup: {'✅' if setup_result['success'] else '❌'} ({setup_result.get('method', 'unknown')} mode)")
    
    # Test Similarity Service
    logger.info("Testing Similarity Service...")
    similarity_service = SimilarityService(config)
    similarity_service.connect()
    
    # Test similarity computation
    doc_a = {"first_name": "John", "last_name": "Smith", "email": "john.smith@email.com"}
    doc_b = {"first_name": "Jon", "last_name": "Smith", "email": "jon.smith@email.com"}
    
    sim_result = similarity_service.compute_similarity(doc_a, doc_b, include_details=True)
    logger.info(f"   Similarity test: {'✅' if 'total_score' in sim_result else '❌'}")
    if 'total_score' in sim_result:
        logger.info(f"      Score: {sim_result['total_score']:.3f}, Match: {sim_result.get('is_match', False)}")
    
    # Test Clustering Service
    logger.info("Testing Clustering Service...")
    clustering_service = ClusteringService(config)
    clustering_service.connect()
    
    # Test with sample scored pairs
    sample_pairs = [
        {"record_a_id": "doc1", "record_b_id": "doc2", "similarity_score": 0.85, "is_match": True},
        {"record_a_id": "doc2", "record_b_id": "doc3", "similarity_score": 0.75, "is_match": True},
        {"record_a_id": "doc4", "record_b_id": "doc5", "similarity_score": 0.90, "is_match": True}
    ]
    
    cluster_result = clustering_service.cluster_entities(sample_pairs, min_similarity=0.7)
    logger.info(f"   Clustering test: {'✅' if cluster_result['success'] else '❌'} ({cluster_result.get('method', 'unknown')} mode)")
    if cluster_result["success"]:
        logger.info(f"      Clusters found: {len(cluster_result.get('clusters', []))}")


def generate_summary_report(pipeline, er_result, logger):
    """Generate a comprehensive summary report"""
    
    # Get pipeline statistics
    stats = pipeline.get_pipeline_stats()
    
    # Create report
    report = {
        "demo_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "configuration": stats["configuration"],
        "system_status": stats["system_status"],
        "pipeline_performance": stats["pipeline_stats"],
        "entity_resolution_results": {
            "input_records": er_result["input_records"],
            "candidate_pairs": er_result["candidate_pairs"],
            "scored_pairs": er_result["scored_pairs"],
            "entity_clusters": er_result["entity_clusters"],
            "total_processing_time": er_result["performance"]["total_time"],
            "configuration_used": er_result["configuration"]
        },
        "cluster_analysis": {
            "total_clusters": len(er_result["stages"]["clustering"]["clusters"]),
            "cluster_size_distribution": {},
            "quality_distribution": {}
        }
    }
    
    # Analyze cluster distribution
    clusters = er_result["stages"]["clustering"]["clusters"]
    if clusters:
        sizes = [c["cluster_size"] for c in clusters]
        qualities = [c.get("quality_score", 0) for c in clusters]
        
        report["cluster_analysis"]["cluster_size_distribution"] = {
            "min": min(sizes),
            "max": max(sizes),
            "average": sum(sizes) / len(sizes)
        }
        
        report["cluster_analysis"]["quality_distribution"] = {
            "min": min(qualities),
            "max": max(qualities),
            "average": sum(qualities) / len(qualities),
            "high_quality_clusters": len([q for q in qualities if q > 0.8])
        }
    
    # Save report
    report_path = Path(__file__).parent.parent / "reports" / "demo_report.json"
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"📄 Summary report saved to: {report_path}")
    logger.info(f"🎯 Overall Results:")
    logger.info(f"   - Entity resolution accuracy: {(er_result['entity_clusters'] / max(er_result['input_records'], 1)) * 100:.1f}% clustering efficiency")
    logger.info(f"   - Processing speed: {er_result['input_records'] / er_result['performance']['total_time']:.1f} records/second")
    
    if clusters:
        avg_quality = report["cluster_analysis"]["quality_distribution"]["average"]
        logger.info(f"   - Average cluster quality: {avg_quality:.3f}")


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
