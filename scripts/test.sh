#!/bin/bash
# Pipeline testing shortcuts

set -e  # Exit on any error

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

case "${1:-help}" in
    "quick"|"q")
        echo "🔍 Running quick pipeline health check..."
        python dev.py quick-test
        ;;
    "test"|"t")
        echo "🧪 Running comprehensive pipeline tests..."
        python dev.py test
        ;;
    "all"|"a")
        echo "🚀 Running full test suite..."
        python dev.py all-tests
        ;;
    "check"|"c")
        echo "✅ Running syntax + quick tests..."
        python dev.py check
        ;;
    "ci")
        echo "🔄 Running CI pipeline..."
        python dev.py ci
        ;;
    "cleanup"|"clean")
        echo "🧹 Running cleanup pipeline..."
        python dev.py cleanup
        ;;
    "cluster"|"clust")
        echo "🔗 Running cluster pipeline..."
        python dev.py cluster
        ;;
    "syntax"|"s")
        echo "📝 Checking syntax..."
        python dev.py syntax
        ;;
    "help"|"h"|*)
        echo "Pipeline Testing Shortcuts"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  quick, q     - Quick health check (fastest)"
        echo "  test, t      - Run pipeline tests"
        echo "  all, a       - Run full test suite"
        echo "  check, c     - Syntax + quick test"
        echo "  ci           - Full CI pipeline"
        echo "  cleanup      - Run cleanup pipeline"
        echo "  cluster      - Run cluster pipeline"
        echo "  syntax, s    - Check syntax only"
        echo "  help, h      - Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 quick     # Fast check before making changes"
        echo "  $0 test      # After making changes"
        echo "  $0 ci        # Before committing"
        echo "  $0 all       # Before deploying"
        ;;
esac
