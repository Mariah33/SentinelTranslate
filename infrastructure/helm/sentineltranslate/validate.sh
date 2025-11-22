#!/bin/bash
# Validation script for SentinelTranslate Helm chart
# This script performs basic structural validation

set -e

CHART_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ERRORS=0

echo "==================================="
echo "SentinelTranslate Chart Validation"
echo "==================================="
echo ""

# Function to check file exists
check_file() {
    if [ -f "$1" ]; then
        echo "✓ Found: $1"
    else
        echo "✗ Missing: $1"
        ((ERRORS++))
    fi
}

# Function to check directory exists
check_dir() {
    if [ -d "$1" ]; then
        echo "✓ Found: $1"
    else
        echo "✗ Missing: $1"
        ((ERRORS++))
    fi
}

# Check chart structure
echo "Checking chart structure..."
echo ""

check_file "$CHART_DIR/Chart.yaml"
check_file "$CHART_DIR/values.yaml"
check_file "$CHART_DIR/values-dev.yaml"
check_file "$CHART_DIR/values-prod.yaml"
check_file "$CHART_DIR/README.md"
check_file "$CHART_DIR/INSTALL.md"
check_file "$CHART_DIR/.helmignore"
check_file "$CHART_DIR/Makefile"

check_dir "$CHART_DIR/templates"
check_dir "$CHART_DIR/charts"

echo ""
echo "Checking template files..."
echo ""

check_file "$CHART_DIR/templates/_helpers.tpl"
check_file "$CHART_DIR/templates/NOTES.txt"
check_file "$CHART_DIR/templates/serviceaccounts.yaml"
check_file "$CHART_DIR/templates/triton-deployment.yaml"
check_file "$CHART_DIR/templates/triton-service.yaml"
check_file "$CHART_DIR/templates/sidecar-deployment.yaml"
check_file "$CHART_DIR/templates/sidecar-service.yaml"
check_file "$CHART_DIR/templates/api-deployment.yaml"
check_file "$CHART_DIR/templates/api-service.yaml"
check_file "$CHART_DIR/templates/worker-deployment.yaml"
check_file "$CHART_DIR/templates/ingress.yaml"
check_file "$CHART_DIR/templates/hpa.yaml"
check_file "$CHART_DIR/templates/pdb.yaml"

echo ""
echo "Checking Chart.yaml contents..."
echo ""

if grep -q "name: sentineltranslate" "$CHART_DIR/Chart.yaml"; then
    echo "✓ Chart name is correct"
else
    echo "✗ Chart name is incorrect"
    ((ERRORS++))
fi

if grep -q "apiVersion: v2" "$CHART_DIR/Chart.yaml"; then
    echo "✓ API version is v2"
else
    echo "✗ API version is not v2"
    ((ERRORS++))
fi

if grep -q "dependencies:" "$CHART_DIR/Chart.yaml"; then
    echo "✓ Dependencies section found"
else
    echo "✗ Dependencies section missing"
    ((ERRORS++))
fi

echo ""
echo "Checking values.yaml contents..."
echo ""

# Check for required sections
required_sections=("redis" "triton" "sidecar" "api" "worker" "ingress")
for section in "${required_sections[@]}"; do
    if grep -q "^${section}:" "$CHART_DIR/values.yaml"; then
        echo "✓ Found section: $section"
    else
        echo "✗ Missing section: $section"
        ((ERRORS++))
    fi
done

echo ""
echo "Checking template syntax..."
echo ""

# Check for common template syntax errors
template_files=$(find "$CHART_DIR/templates" -name "*.yaml")
for file in $template_files; do
    # Check for unmatched braces (very basic check)
    if grep -E "{{[^}]*$" "$file" | grep -v "{{-" > /dev/null 2>&1; then
        echo "⚠ Warning: Potential unmatched template braces in: $file"
        # Don't count as error - helm lint will catch this
    fi
done

echo "✓ Template syntax check passed (basic validation)"

echo ""
echo "Checking YAML syntax..."
echo ""

# Check if yamllint is available
if command -v yamllint &> /dev/null; then
    echo "Running yamllint..."
    if yamllint -d relaxed "$CHART_DIR" 2>/dev/null; then
        echo "✓ YAML syntax is valid"
    else
        echo "⚠ YAML linting warnings found (not blocking)"
    fi
else
    echo "⚠ yamllint not installed, skipping YAML syntax check"
fi

echo ""
echo "==================================="
echo "Validation Summary"
echo "==================================="
echo ""

if [ $ERRORS -eq 0 ]; then
    echo "✓ Chart structure validation PASSED"
    echo ""
    echo "Next steps:"
    echo "  1. Run 'helm dependency update' to download Redis chart"
    echo "  2. Run 'helm lint .' to perform full Helm validation"
    echo "  3. Run 'helm template .' to test template rendering"
    echo "  4. Run 'make test' to run all checks"
    exit 0
else
    echo "✗ Chart structure validation FAILED with $ERRORS error(s)"
    echo ""
    echo "Please fix the errors above before proceeding."
    exit 1
fi
