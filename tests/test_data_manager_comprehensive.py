"""
Comprehensive tests for DataManager

Tests cover:
- Initialization
- Database connectivity
- Collection creation
- Data loading from files
- Data loading from DataFrame
- Collection statistics
- Record sampling
- Data quality validation
- Quality recommendations
- Test collection initialization
"""

import pytest
import json
import tempfile
from unittest.mock import Mock, MagicMock, patch, mock_open
from src.entity_resolution.data.data_manager import DataManager, PANDAS_AVAILABLE
from src.entity_resolution.utils.config import Config


class TestDataManagerInitialization:
    """Test DataManager initialization."""
    
    def test_initialization_with_default_config(self):
        """Test manager initializes with default configuration."""
        manager = DataManager()
        
        assert manager.config is not None
        assert manager.logger is not None
    
    def test_initialization_with_custom_config(self):
        """Test manager initializes with custom configuration."""
        config = Config()
        manager = DataManager(config=config)
        
        assert manager.config == config


class TestDatabaseConnection:
    """Test database connection functionality."""
    
    def test_connect_success(self):
        """Test successful database connection."""
        manager = DataManager()
        manager.test_connection = Mock(return_value=True)
        
        result = manager.connect()
        
        assert result is True
    
    def test_connect_failure(self):
        """Test database connection failure."""
        manager = DataManager()
        manager.test_connection = Mock(return_value=False)
        
        result = manager.connect()
        
        assert result is False
    
    def test_connect_exception(self):
        """Test connection handles exceptions."""
        manager = DataManager()
        manager.test_connection = Mock(side_effect=Exception("Connection error"))
        
        result = manager.connect()
        
        assert result is False


class TestCollectionCreation:
    """Test collection creation."""
    
    def test_create_collection_new(self):
        """Test creating a new collection."""
        manager = DataManager()
        manager._db = Mock()
        type(manager).database = property(lambda self: self._db)
        manager._db.has_collection.return_value = False
        manager._db.create_collection.return_value = Mock()
        
        result = manager.create_collection("test_collection")
        
        assert result is True
        manager._db.create_collection.assert_called_once_with("test_collection")
    
    def test_create_collection_already_exists(self):
        """Test creating a collection that already exists."""
        manager = DataManager()
        manager._db = Mock()
        manager._db.has_collection.return_value = True
        
        result = manager.create_collection("existing_collection")
        
        assert result is True
        manager._db.create_collection.assert_not_called()
    
    def test_create_edge_collection(self):
        """Test creating an edge collection."""
        manager = DataManager()
        manager._db = Mock()
        type(manager).database = property(lambda self: self._db)
        manager._db.has_collection.return_value = False
        manager._db.create_collection.return_value = Mock()
        
        result = manager.create_collection("edges", edge=True)
        
        assert result is True
        manager._db.create_collection.assert_called_once_with("edges", edge=True)
    
    def test_create_collection_exception(self):
        """Test collection creation handles exceptions."""
        manager = DataManager()
        manager._db = Mock()
        type(manager).database = property(lambda self: self._db)
        manager._db.has_collection.side_effect = Exception("DB error")
        
        result = manager.create_collection("test")
        
        assert result is False


class TestLoadDataFromFile:
    """Test loading data from files."""
    
    def test_load_data_from_file_list_format(self):
        """Test loading data in list format."""
        manager = DataManager()
        manager._db = Mock()
        manager.create_collection = Mock(return_value=True)
        
        # Mock the database property
        type(manager).database = property(lambda self: self._db)
        
        mock_collection = Mock()
        mock_collection.insert_many.return_value = ["id1", "id2"]
        manager._db.collection.return_value = mock_collection
        
        # Mock file reading
        test_data = [{"name": "John"}, {"name": "Jane"}]
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            result = manager.load_data_from_file("test.json", "customers")
        
        assert result["success"] is True
        assert result["inserted_records"] == 2
        assert result["collection"] == "customers"
    
    def test_load_data_from_file_dict_with_customers_key(self):
        """Test loading data in dict format with 'customers' key."""
        manager = DataManager()
        manager._db = Mock()
        manager.create_collection = Mock(return_value=True)
        
        # Mock the database property
        type(manager).database = property(lambda self: self._db)
        
        mock_collection = Mock()
        mock_collection.insert_many.return_value = ["id1"]
        manager._db.collection.return_value = mock_collection
        
        test_data = {"customers": [{"name": "John"}]}
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            result = manager.load_data_from_file("test.json", "customers")
        
        assert result["success"] is True
        assert result["inserted_records"] == 1
    
    def test_load_data_from_file_dict_with_data_key(self):
        """Test loading data in dict format with 'data' key."""
        manager = DataManager()
        manager._db = Mock()
        manager.create_collection = Mock(return_value=True)
        
        # Mock the database property
        type(manager).database = property(lambda self: self._db)
        
        mock_collection = Mock()
        mock_collection.insert_many.return_value = ["id1"]
        manager._db.collection.return_value = mock_collection
        
        test_data = {"data": [{"name": "John"}]}
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            result = manager.load_data_from_file("test.json", "customers")
        
        assert result["success"] is True
    
    def test_load_data_from_file_batch_processing(self):
        """Test data loading respects batch size."""
        manager = DataManager()
        manager._db = Mock()
        manager.create_collection = Mock(return_value=True)
        
        # Mock the database property to return _db
        type(manager).database = property(lambda self: self._db)
        
        mock_collection = Mock()
        mock_collection.insert_many.return_value = ["id"] * 5
        manager._db.collection.return_value = mock_collection
        
        # 15 records, batch size 5 = 3 batches
        test_data = [{"name": f"Person{i}"} for i in range(15)]
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            result = manager.load_data_from_file("test.json", "customers", batch_size=5)
        
        assert result["success"] is True
        assert mock_collection.insert_many.call_count == 3
    
    def test_load_data_from_file_collection_creation_fails(self):
        """Test loading handles collection creation failure."""
        manager = DataManager()
        manager.create_collection = Mock(return_value=False)
        
        result = manager.load_data_from_file("test.json", "customers")
        
        assert result["success"] is False
        assert "Failed to create collection" in result["error"]
    
    def test_load_data_from_file_exception(self):
        """Test loading handles exceptions."""
        manager = DataManager()
        manager.create_collection = Mock(return_value=True)
        
        with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
            result = manager.load_data_from_file("missing.json", "customers")
        
        assert result["success"] is False


@pytest.mark.skipif(not PANDAS_AVAILABLE, reason="pandas not available")
class TestLoadDataFromDataFrame:
    """Test loading data from pandas DataFrame."""
    
    def test_load_data_from_dataframe_success(self):
        """Test loading data from DataFrame."""
        import pandas as pd
        
        manager = DataManager()
        manager._db = Mock()
        type(manager).database = property(lambda self: self._db)
        manager.create_collection = Mock(return_value=True)
        
        mock_collection = Mock()
        mock_collection.insert_many.return_value = ["id1", "id2"]
        manager._db.collection.return_value = mock_collection
        
        df = pd.DataFrame([{"name": "John"}, {"name": "Jane"}])
        result = manager.load_data_from_dataframe(df, "customers")
        
        assert result["success"] is True
        assert result["inserted_records"] == 2
    
    def test_load_data_from_dataframe_batch_processing(self):
        """Test DataFrame loading respects batch size."""
        import pandas as pd
        
        manager = DataManager()
        manager._db = Mock()
        type(manager).database = property(lambda self: self._db)
        manager.create_collection = Mock(return_value=True)
        
        mock_collection = Mock()
        mock_collection.insert_many.return_value = ["id"] * 3
        manager._db.collection.return_value = mock_collection
        
        df = pd.DataFrame([{"name": f"Person{i}"} for i in range(10)])
        result = manager.load_data_from_dataframe(df, "customers", batch_size=3)
        
        assert result["success"] is True
        # 10 records / 3 per batch = 4 batches
        assert mock_collection.insert_many.call_count == 4


class TestCollectionStats:
    """Test collection statistics."""
    
    def test_get_collection_stats_success(self):
        """Test getting collection statistics."""
        manager = DataManager()
        manager.db = Mock()
        manager.db.has_collection.return_value = True
        
        mock_collection = Mock()
        mock_collection.count.return_value = 100
        mock_collection.properties.return_value = {"type": "document", "status": "loaded"}
        mock_collection.indexes.return_value = []
        manager._db = Mock()
        manager._db.collection.return_value = mock_collection
        
        result = manager.get_collection_stats("customers")
        
        assert result["success"] is True
        assert result["name"] == "customers"
        assert result["count"] == 100
    
    def test_get_collection_stats_not_exists(self):
        """Test getting stats for non-existent collection."""
        manager = DataManager()
        manager.db = Mock()
        manager.db.has_collection.return_value = False
        
        result = manager.get_collection_stats("nonexistent")
        
        assert result["success"] is False
        assert "does not exist" in result["error"]
    
    def test_get_collection_stats_exception(self):
        """Test stats handles exceptions."""
        manager = DataManager()
        manager.db = Mock()
        manager.db.has_collection.side_effect = Exception("DB error")
        
        result = manager.get_collection_stats("customers")
        
        assert result["success"] is False


class TestSampleRecords:
    """Test record sampling."""
    
    def test_sample_records_success(self):
        """Test sampling records from collection."""
        manager = DataManager()
        manager.db = Mock()
        manager.db.has_collection.return_value = True
        manager._db = Mock()
        type(manager).database = property(lambda self: self._db)
        manager._db.collection.return_value = Mock()
        
        sample_data = [{"id": "1"}, {"id": "2"}]
        manager.db.aql.execute.return_value = iter(sample_data)
        
        result = manager.sample_records("customers", limit=2)
        
        assert len(result) == 2
        assert result == sample_data
    
    def test_sample_records_collection_not_exists(self):
        """Test sampling from non-existent collection."""
        manager = DataManager()
        manager.db = Mock()
        manager.db.has_collection.return_value = False
        
        result = manager.sample_records("nonexistent")
        
        assert result == []
    
    def test_sample_records_exception(self):
        """Test sampling handles exceptions."""
        manager = DataManager()
        manager.db = Mock()
        manager.db.has_collection.return_value = True
        manager.db.aql.execute.side_effect = Exception("Query error")
        
        result = manager.sample_records("customers")
        
        assert result == []


class TestDataQualityValidation:
    """Test data quality validation."""
    
    def test_validate_data_quality_success(self):
        """Test data quality validation."""
        manager = DataManager()
        manager.db = Mock()
        manager.db.has_collection.return_value = True
        
        sample_data = [
            {"name": "John", "email": "john@example.com", "phone": "555-1234"},
            {"name": "Jane", "email": "jane@example.com", "phone": None}
        ]
        manager.sample_records = Mock(return_value=sample_data)
        
        result = manager.validate_data_quality("customers")
        
        assert result["success"] is True
        assert "field_analysis" in result
        assert "overall_quality_score" in result
        assert "recommendations" in result
    
    def test_validate_data_quality_collection_not_exists(self):
        """Test validation for non-existent collection."""
        manager = DataManager()
        manager.db = Mock()
        manager.db.has_collection.return_value = False
        
        result = manager.validate_data_quality("nonexistent")
        
        assert result["success"] is False
        assert "does not exist" in result["error"]
    
    def test_validate_data_quality_no_records(self):
        """Test validation with no records."""
        manager = DataManager()
        manager.db = Mock()
        manager.db.has_collection.return_value = True
        manager.sample_records = Mock(return_value=[])
        
        result = manager.validate_data_quality("customers")
        
        assert result["success"] is False
        assert "No records found" in result["error"]
    
    def test_validate_data_quality_field_analysis(self):
        """Test field analysis in validation."""
        manager = DataManager()
        manager.db = Mock()
        manager.db.has_collection.return_value = True
        
        sample_data = [
            {"name": "John", "email": "john@example.com"},
            {"name": "Jane", "email": None},
            {"name": "Bob", "email": "bob@example.com"}
        ]
        manager.sample_records = Mock(return_value=sample_data)
        
        result = manager.validate_data_quality("customers")
        
        assert result["success"] is True
        assert "name" in result["field_analysis"]
        assert "email" in result["field_analysis"]
        # Email has 2/3 non-null = ~67% completeness
        assert result["field_analysis"]["email"]["null_percentage"] > 30


class TestQualityRecommendations:
    """Test quality recommendation generation."""
    
    def test_generate_recommendations_high_null_percentage(self):
        """Test recommendation for high null percentage."""
        manager = DataManager()
        
        field_analysis = {
            "email": {
                "null_percentage": 60.0,
                "unique_count": 50,
                "total_count": 100
            }
        }
        
        recommendations = manager._generate_quality_recommendations(field_analysis)
        
        # Should recommend data cleaning for high null percentage
        assert any("high null percentage" in r for r in recommendations)
    
    def test_generate_recommendations_unique_field(self):
        """Test recommendation for unique fields."""
        manager = DataManager()
        
        field_analysis = {
            "customer_id": {
                "null_percentage": 0.0,
                "unique_count": 100,
                "total_count": 100
            }
        }
        
        recommendations = manager._generate_quality_recommendations(field_analysis)
        
        # Should recommend using as blocking key
        assert any("blocking key" in r for r in recommendations)
    
    def test_generate_recommendations_single_value(self):
        """Test recommendation for fields with single value."""
        manager = DataManager()
        
        field_analysis = {
            "country": {
                "null_percentage": 0.0,
                "unique_count": 1,
                "total_count": 100
            }
        }
        
        recommendations = manager._generate_quality_recommendations(field_analysis)
        
        # Should recommend field may not be useful
        assert any("one unique value" in r for r in recommendations)


class TestInitializeTestCollections:
    """Test test collection initialization."""
    
    def test_initialize_test_collections_success(self):
        """Test initializing standard test collections."""
        manager = DataManager()
        manager.create_collection = Mock(return_value=True)
        
        result = manager.initialize_test_collections()
        
        assert result["success"] is True
        assert len(result["created"]) == 5  # customers, entities, similarities, entity_clusters, golden_records
        assert "customers" in result["created"]
        assert "similarities" in result["created"]  # Edge collection
    
    def test_initialize_test_collections_partial_failure(self):
        """Test initialization with some failures."""
        manager = DataManager()
        
        # Make some collections succeed and some fail
        def create_side_effect(name, edge=False):
            return name != "entities"  # Fail on "entities"
        
        manager.create_collection = Mock(side_effect=create_side_effect)
        
        result = manager.initialize_test_collections()
        
        assert result["success"] is False
        assert len(result["errors"]) > 0


class TestEdgeCases:
    """Test edge cases and robustness."""
    
    def test_load_data_unsupported_format(self):
        """Test loading data in unsupported format."""
        manager = DataManager()
        manager._db = Mock()
        type(manager).database = property(lambda self: self._db)
        manager.create_collection = Mock(return_value=True)
        
        # Invalid data format (not list or dict)
        test_data = "invalid data"
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            result = manager.load_data_from_file("test.json", "customers")
        
        assert result["success"] is False
        assert "Unsupported data format" in result["error"]
    
    def test_sample_records_default_limit(self):
        """Test sampling with default limit."""
        manager = DataManager()
        manager.db = Mock()
        manager.db.has_collection.return_value = True
        manager._db = Mock()
        type(manager).database = property(lambda self: self._db)
        manager._db.collection.return_value = Mock()
        manager.db.aql.execute.return_value = iter([])
        
        # Should use default limit of 10
        result = manager.sample_records("customers")
        
        assert result == []
    
    def test_validate_data_quality_skips_internal_fields(self):
        """Test validation skips ArangoDB internal fields."""
        manager = DataManager()
        manager.db = Mock()
        manager.db.has_collection.return_value = True
        
        sample_data = [
            {"_id": "customers/1", "_key": "1", "_rev": "abc", "name": "John"}
        ]
        manager.sample_records = Mock(return_value=sample_data)
        
        result = manager.validate_data_quality("customers")
        
        assert result["success"] is True
        # Internal fields (_id, _key, _rev) should be skipped
        assert "_id" not in result["field_analysis"]
        assert "_key" not in result["field_analysis"]
        assert "name" in result["field_analysis"]

