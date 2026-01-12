# Custom Collections Guide

## Working with Non-Standard Collections

The Entity Resolution framework is designed to work with **any collection structure**, not just the tutorial "customers" collection. This guide shows how to use the framework with custom collections from enterprise systems, CRM platforms, ERP systems, or your own data models.

---

## Quick Start: Enterprise Data Example

### 1. Create Analyzers (One Time)

```bash
curl -X POST "https://your-db.arangodb.cloud:8529/_db/your_database/entity-resolution/setup/analyzers" \
-u root:yourpassword \
-H "Content-Type: application/json"
```

**Result:**
- `ngram_analyzer` - For typo tolerance
- `exact_analyzer` - For exact matching
- `phonetic_analyzer` - For name variations (if enabled)

### 2. Create Views for Your Collections

**Enterprise Collections Example:**

```bash
curl -X POST "https://your-db.arangodb.cloud:8529/_db/your_database/entity-resolution/setup/views" \
-u root:yourpassword \
-H "Content-Type: application/json" \
-d '{
"collections": ["companies", "contacts", "locations"],
"fields": {
"companies": ["company_name", "ceo_name", "industry"],
"contacts": ["first_name", "last_name", "email"],
"locations": ["address", "city", "postal_code"]
}
}'
```

**Result:**
- `companies_blocking_view` - Indexes company_name, ceo_name, industry
- `contacts_blocking_view` - Indexes first_name, last_name, email
- `locations_blocking_view` - Indexes address, city, postal_code

### 3. Alternative: Auto-Discovery Mode

Let the system index **all fields** automatically:

```bash
curl -X POST "https://your-db.arangodb.cloud:8529/_db/your_database/entity-resolution/setup/views" \
-u root:yourpassword \
-H "Content-Type: application/json" \
-d '{
"collections": ["companies"]
}'
```

Auto-discovery is enabled by default (`autoDiscoverFields: true` in service configuration).

### 4. One-Step Initialization

Create analyzers **and** views in one call:

```bash
curl -X POST "https://your-db.arangodb.cloud:8529/_db/your_database/entity-resolution/setup/initialize" \
-u root:yourpassword \
-H "Content-Type: application/json" \
-d '{
"collections": ["companies", "contacts"],
"fields": {
"companies": ["company_name", "industry"],
"contacts": ["first_name", "last_name", "email"]
}
}'
```

---

## Python Example

### Using the Python SDK

```python
from entity_resolution.services.setup_service import SetupService
from entity_resolution.utils.config import Config

# Configure for your database
config = Config(
host="your-db.arangodb.cloud",
port=8529,
username="root",
password="yourpassword",
database="your_database"
)

setup = SetupService(config)

# Initialize for your collections
result = setup.initialize(
collections=["companies", "contacts", "locations"],
fields={
"companies": ["company_name", "ceo_name", "industry"],
"contacts": ["first_name", "last_name", "email"],
"locations": ["address", "city", "postal_code"]
}
)

print(f"Setup complete: {result['success']}")
print(f"Views created: {list(result['results']['views'].keys())}")
```

---

## Configuration Options

### Service Configuration (Set Once)

Configure default behavior via ArangoDB web interface or API:

```json
{
"defaultCollections": "companies,contacts",
"autoDiscoverFields": true,
"ngramLength": 3,
"enablePhoneticMatching": true
}
```

**Benefits:**
- Omit `collections` parameter in API calls
- Auto-index all fields unless specific fields provided
- Customize n-gram size and phonetic matching

### Per-Request Configuration

Override defaults for specific operations:

```json
{
"collections": ["custom_collection"],
"fields": {
"custom_collection": ["specific_field1", "specific_field2"]
},
"force": true
}
```

**Options:**
- `collections` - Array of collection names to process
- `fields` - Map of collection name to field names to index
- `force` - Recreate views even if they exist

---

## API Reference

### POST /setup/views

**Purpose:** Create ArangoSearch views for blocking

**Request Body:**

```json
{
"collections": ["collection1", "collection2"],
"fields": {
"collection1": ["field_a", "field_b"],
"collection2": ["field_x", "field_y"]
}
}
```

**Field Configuration Rules:**
- If `fields[collection]` provided: Index only those fields
- If `fields[collection]` omitted AND `autoDiscoverFields: true`: Index all fields
- If `fields[collection]` omitted AND `autoDiscoverFields: false`: Index no fields

**Response:**

```json
{
"success": true,
"message": "ArangoSearch views created successfully",
"views": {
"collection1_blocking_view": {
"name": "collection1_blocking_view",
"status": "created"
}
},
"collections": ["collection1", "collection2"],
"configuration": {
"autoDiscoverFields": true,
"fieldsConfigured": true
}
}
```

**Error Response (No Collections):**

```json
{
"success": false,
"error": "No collections specified",
"message": "Provide collections in request body or configure defaultCollections",
"available_collections": ["companies", "contacts", "locations", ...],
"example": {
"collections": ["companies", "contacts"],
"fields": {
"companies": ["field1", "field2"]
}
}
}
```

---

### POST /setup/initialize

**Purpose:** One-step setup (analyzers + views)

**Request Body:**

```json
{
"collections": ["companies"],
"fields": {
"companies": ["company_name", "ceo_name"]
},
"force": false
}
```

**Response:**

```json
{
"success": true,
"message": "Entity resolution setup initialized successfully",
"results": {
"analyzers": {
"ngram_analyzer": {"status": "created"},
"exact_analyzer": {"status": "created"}
},
"views": {
"companies_blocking_view": {"status": "created"}
},
"collections": {
"companies": true
},
"warnings": []
},
"configuration": {
"ngramLength": 3,
"collections": ["companies"],
"force": false,
"autoDiscoverFields": true,
"fieldsConfigured": true
}
}
```

---

## Real-World Examples

### Example 1: Enterprise Master Data

**Collections:**
- `companies` - Company master records
- `divisions` - Business divisions
- `subsidiaries` - Subsidiary companies

**Setup:**

```bash
curl -X POST "$ARANGO_ENDPOINT/_db/$ARANGO_DATABASE/entity-resolution/setup/initialize" \
-u "$ARANGO_USER:$ARANGO_PASSWORD" \
-H "Content-Type: application/json" \
-d '{
"collections": ["companies", "divisions", "subsidiaries"],
"fields": {
"companies": [
"company_name",
"legal_name",
"ceo_name",
"headquarters_address",
"headquarters_city",
"headquarters_state"
],
"divisions": [
"division_name",
"division_number",
"division_type"
],
"subsidiaries": [
"subsidiary_name",
"parent_company"
]
}
}'
```

**Result:**
- 3 views created
- All company name fields indexed with n-gram analyzer
- Ready for blocking and similarity computation

---

### Example 2: CRM System

**Collections:**
- `accounts` - Company accounts
- `contacts` - Individual contacts
- `leads` - Prospective customers

**Setup:**

```bash
curl -X POST "$ARANGO_ENDPOINT/_db/crm/entity-resolution/setup/initialize" \
-u "$ARANGO_USER:$ARANGO_PASSWORD" \
-H "Content-Type: application/json" \
-d '{
"collections": ["accounts", "contacts", "leads"],
"fields": {
"accounts": ["account_name", "website", "phone"],
"contacts": ["first_name", "last_name", "email", "company"],
"leads": ["company_name", "contact_name", "email"]
}
}'
```

---

### Example 3: Auto-Discovery for Unknown Schema

**When to use:** Exploring new data, rapid prototyping, schema varies

```bash
# Auto-index ALL fields in collections
curl -X POST "$ARANGO_ENDPOINT/_db/my_database/entity-resolution/setup/views" \
-u "$ARANGO_USER:$ARANGO_PASSWORD" \
-H "Content-Type: application/json" \
-d '{
"collections": ["unknown_collection"]
}'
```

**What happens:**
- `includeAllFields: true` set in view configuration
- Every field automatically indexed with analyzers
- Trade-off: Higher storage, slower writes, but maximum flexibility

---

## Troubleshooting

### Issue: "Collection 'customers' does not exist"

**Cause:** Old tutorial examples reference "customers"

**Fix:** Explicitly provide your collections:

```json
{
"collections": ["your_collection_name"]
}
```

---

### Issue: "No collections specified"

**Cause:** Neither request body nor service configuration provides collections

**Fix Option 1 - Per Request:**

```json
{
"collections": ["companies"]
}
```

**Fix Option 2 - Service Configuration:**

Configure `defaultCollections` in ArangoDB web interface:
```
Settings -> Services -> entity-resolution -> Configuration -> defaultCollections = "companies,contacts"
```

---

### Issue: "Field names don't match my data"

**Cause:** Using auto-discovery with explicit field list

**Solution 1 - Provide Your Fields:**

```json
{
"collections": ["companies"],
"fields": {
"companies": ["your_field_name", "another_field"]
}
}
```

**Solution 2 - Use Auto-Discovery:**

```json
{
"collections": ["companies"]
}
```

Leave `fields` empty and set `autoDiscoverFields: true` in service configuration.

---

### Issue: Views created but blocking returns no candidates

**Likely Causes:**
1. Wrong field names in view configuration
2. Analyzers not applied to the right fields
3. Data doesn't match blocking strategy
4. **Database-prefixed analyzer names** (AddressERService only)

**Debug Steps:**

1. **Check view exists:**
```bash
curl "$ARANGO_ENDPOINT/_db/$DB/_api/view" -u "$USER:$PASS"
```

2. **Inspect view configuration:**
```bash
curl "$ARANGO_ENDPOINT/_db/$DB/_api/view/companies_blocking_view/properties" \
-u "$USER:$PASS"
```

3. **Test analyzer:**
```bash
curl -X POST "$ARANGO_ENDPOINT/_db/$DB/_api/analyzer" \
-u "$USER:$PASS" \
-d '{
"analyzer": "ngram_analyzer",
"text": "Your Company Name"
}'
```

4. **Check for database-prefixed analyzers (AddressERService):**
If you're using `AddressERService` and analyzers are stored with database prefixes (e.g., `my_db::address_normalizer`), ensure you're using version 3.0.1+ which automatically detects and uses prefixed analyzer names.

```bash
# List all analyzers to check for prefixes
curl "$ARANGO_ENDPOINT/_db/$DB/_api/analyzer" -u "$USER:$PASS"
```

5. **Recreate with force:**
```json
{
"collections": ["companies"],
"fields": {
"companies": ["CORRECT_FIELD_NAME"]
},
"force": true
}
```

---

## Best Practices

### 1. Start with Specific Fields

**Recommended:**
```json
{
"collections": ["companies"],
"fields": {
"companies": ["company_name", "address"]
}
}
```

**Why:** Faster, lower storage, more control

### 2. Use Auto-Discovery for Exploration

**When:** New data, unknown schema, rapid prototyping

```json
{
"collections": ["unknown_data"]
}
```

**Trade-off:** Indexes everything, higher cost

### 3. Configure Service Defaults

**For production:** Set `defaultCollections` to avoid repeating in every API call

**ArangoDB Web UI:**
```
Settings -> Services -> entity-resolution -> Configuration
-> defaultCollections: "companies,contacts,locations"
```

### 4. Test with Small Collections First

**Workflow:**
1. Create views for small collection (100-1000 docs)
2. Test blocking and similarity
3. Verify field names and results
4. Scale to full collections

### 5. Monitor View Creation

**Large collections** (100K+ docs) can take minutes to index.

Check progress:
```bash
curl "$ARANGO_ENDPOINT/_db/$DB/_api/view/companies_blocking_view/properties" \
-u "$USER:$PASS"
```

---

## Next Steps

After setup:

1. **Test Blocking:**
```bash
POST /entity-resolution/blocking/candidates
{
"collection": "companies",
"record_id": "test_record_id"
}
```

2. **Compute Similarity:**
```bash
POST /entity-resolution/similarity/compute
{
"collection": "companies",
"record_id_1": "id1",
"record_id_2": "id2"
}
```

3. **Run Clustering:**
```bash
POST /entity-resolution/clustering/wcc
{
"similarity_threshold": 0.8
}
```

---

## Support

**Framework Repository:** https://github.com/your-org/arango-entity-resolution

**Issues:** Report collection-specific bugs or feature requests

**Examples:** Check `examples/` directory for more use cases

---

**Last Updated:** October 28, 2025 
**Version:** 1.1.0 (Custom Collections Support)
