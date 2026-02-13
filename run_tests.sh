#!/bin/bash
# Test runner script for comprehensive application testing

echo "=========================================="
echo "Running Comprehensive Test Suite"
echo "=========================================="
echo ""

# Check if dependencies are installed
echo "Checking dependencies..."
python -c "import geopandas, duckdb, rapidfuzz, streamlit" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Dependencies not installed. Please run: pip install -r requirements.txt"
    exit 1
fi
echo "✅ Dependencies installed"
echo ""

# Run security tests first (critical)
echo "=========================================="
echo "1. Running Security Tests"
echo "=========================================="
pytest tests/test_security.py tests/test_duckdb_store_security.py -v
SECURITY_EXIT=$?

echo ""
echo "=========================================="
echo "2. Running Security Integration Tests"
echo "=========================================="
pytest tests/test_security_fixes_integration.py -v
SECURITY_INTEGRATION_EXIT=$?

echo ""
echo "=========================================="
echo "3. Running Full Integration Tests"
echo "=========================================="
pytest tests/test_integration_full_workflow.py -v
INTEGRATION_EXIT=$?

echo ""
echo "=========================================="
echo "4. Running Existing Unit Tests"
echo "=========================================="
pytest tests/test_geocoder.py tests/test_fuzzy.py tests/test_normalization.py tests/test_spatial.py -v
UNIT_EXIT=$?

echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
if [ $SECURITY_EXIT -eq 0 ] && [ $SECURITY_INTEGRATION_EXIT -eq 0 ] && [ $INTEGRATION_EXIT -eq 0 ] && [ $UNIT_EXIT -eq 0 ]; then
    echo "✅ ALL TESTS PASSED"
    exit 0
else
    echo "❌ SOME TESTS FAILED"
    echo "Security tests: $SECURITY_EXIT"
    echo "Security integration: $SECURITY_INTEGRATION_EXIT"
    echo "Integration tests: $INTEGRATION_EXIT"
    echo "Unit tests: $UNIT_EXIT"
    exit 1
fi


