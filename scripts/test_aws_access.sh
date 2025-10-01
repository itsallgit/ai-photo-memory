#!/bin/bash

# Function to print colored status messages
print_status() {
    local status="$1"
    local message="$2"
    case $status in
        "SUCCESS")
            printf "${GREEN}✅ %s${NC}\\n" "$message"
            ;;
        "ERROR")
            printf "${RED}❌ %s${NC}\\n" "$message"
            ;;
        "WARNING")
            printf "${YELLOW}⚠️  %s${NC}\\n" "$message"
            ;;
        "INFO")
            printf "${BLUE}ℹ️  %s${NC}\\n" "$message"
            ;;
    esac
}

# Tests all required AWS permissions and service access for the voice assistant

# Don't exit on errors - we want to continue testing even if some checks fail
# set -e

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables from .env file if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "📄 Loading environment variables from .env file..."
    # Export variables from .env file, ignoring comments and empty lines
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | grep -v '^$' | xargs)
    echo "✅ Environment variables loaded from .env"
else
    echo "⚠️  No .env file found at $PROJECT_ROOT/.env"
    echo "   Consider copying .env.example to .env and configuring your settings."
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values (can be overridden by .env or command line)
PROFILE="${AWS_PROFILE:-}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
VERBOSE=false

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "SUCCESS")
            printf "${GREEN}✅ $message${NC}"
            ;;
        "ERROR")
            printf "${RED}❌ $message${NC}"
            ;;
        "WARNING")
            printf "${YELLOW}⚠️  $message${NC}"
            ;;
        "INFO")
            printf "${BLUE}ℹ️  $message${NC}"
            ;;
    esac
}

# Function to run AWS CLI command with error handling
run_aws_command() {
    local cmd="$1"
    local description="$2"
    
    printf "\\n${BLUE}Testing: %s${NC}\\n" "$description"
    echo "Command: $cmd"
    
    if eval "$cmd" 2>/dev/null; then
        print_status "SUCCESS" "$description"
        return 0
    else
        print_status "ERROR" "$description failed"
        return 1
    fi
}

# Function to check if command exists
check_command() {
    if command -v "$1" >/dev/null 2>&1; then
        print_status "SUCCESS" "$1 is installed"
        return 0
    else
        print_status "ERROR" "$1 is not installed"
        return 1
    fi
}

# Usage function
usage() {
    echo "Usage: $0 [--profile PROFILE_NAME] [--region REGION] [--verbose]"
    echo ""
    echo "Options:"
    echo "  --profile    AWS profile name to test (optional if AWS_PROFILE set in .env)"
    echo "  --region     AWS region to test (default: us-east-1, can be set in .env as AWS_DEFAULT_REGION)"
    echo "  --verbose    Enable verbose output"
    echo "  -h, --help   Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Use profile from .env file"
    echo "  $0 --profile exalm"
    echo "  $0 --profile exalm --region us-east-1 --verbose"
    echo ""
    echo "Note: Create a .env file in the project root with AWS_PROFILE and AWS_DEFAULT_REGION"
    echo "      to avoid specifying these parameters every time."
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required parameters
if [[ -z "$PROFILE" ]]; then
    print_status "ERROR" "AWS profile not specified and not found in .env file"
    echo "  Either:"
    echo "  - Use --profile PROFILE_NAME, or"
    echo "  - Set AWS_PROFILE in .env file"
    usage
fi

echo "=================================================="
echo "AWS Access Validation for PhotoAgent Voice Assistant"
echo "=================================================="
echo "Profile: $PROFILE"
echo "Region: $REGION"
echo "Verbose: $VERBOSE"
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "Config source: .env file (can be overridden with command line args)"
else
    echo "Config source: command line arguments"
fi
echo "=================================================="

# Test 1: Check if AWS CLI is installed
printf "\\n\\n${YELLOW}=== STEP 1: Prerequisites Check ===${NC}\\n\\n"
if ! check_command "aws"; then
    print_status "ERROR" "AWS CLI is required but not installed"
    exit 1
fi
check_command "jq" || print_status "WARNING" "jq not installed (recommended for JSON parsing)"

# Test 2: Verify AWS profile exists and credentials work
printf "\\n\\n${YELLOW}=== STEP 2: AWS Profile and Credentials ===${NC}\\n\\n"

print_status "INFO" "Checking if profile '$PROFILE' exists..."
if aws configure list --profile "$PROFILE" >/dev/null 2>&1; then
    print_status "SUCCESS" "Profile '$PROFILE' exists"
    
    # Show profile configuration
    echo "Profile configuration:"
    aws configure list --profile "$PROFILE"
else
    print_status "ERROR" "Profile '$PROFILE' not found"
    print_status "INFO" "Run: aws configure --profile $PROFILE"
    exit 1
fi

# Test 3: Test basic AWS access
printf "\\n\\n${YELLOW}=== STEP 3: Basic AWS Access ===${NC}\\n\\n"

run_aws_command "aws sts get-caller-identity --profile $PROFILE --region $REGION" \
    "Get caller identity (basic access test)"

if [[ $? -eq 0 ]]; then
    printf "\\n\\n"
    echo "Account details:"
    aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" | jq . 2>/dev/null || aws sts get-caller-identity --profile "$PROFILE" --region "$REGION"
fi

# Test 4: Amazon Bedrock Service Access
printf "\\n\\n${YELLOW}=== STEP 4: Amazon Bedrock Service Access ===${NC}\\n\\n"

# Part 1: Check model availability
print_status "INFO" "Part 1: Checking available Nova and Claude models..."
printf "\\n\\n"

# Check for Nova models
print_status "INFO" "Checking Nova models availability..."
NOVA_MODELS=$(aws bedrock list-foundation-models --profile "$PROFILE" --region "$REGION" --query 'modelSummaries[?contains(modelId, `nova`)]' --output json 2>/dev/null)
NOVA_COUNT=$(echo "$NOVA_MODELS" | jq length 2>/dev/null || echo "0")

if [[ "$NOVA_COUNT" -gt 0 ]]; then
    print_status "SUCCESS" "Found $NOVA_COUNT Nova model(s) available"
    echo "$NOVA_MODELS" | jq -r '.[] | "  - " + .modelId' 2>/dev/null || echo "  (jq not available for detailed listing)"
else
    print_status "ERROR" "No Nova models available in $REGION"
fi

printf "\\n\\n"

# Check for Claude models
print_status "INFO" "Checking Claude models availability..."
CLAUDE_MODELS=$(aws bedrock list-foundation-models --profile "$PROFILE" --region "$REGION" --query 'modelSummaries[?contains(modelId, `claude`)]' --output json 2>/dev/null)
CLAUDE_COUNT=$(echo "$CLAUDE_MODELS" | jq length 2>/dev/null || echo "0")

if [[ "$CLAUDE_COUNT" -gt 0 ]]; then
    print_status "SUCCESS" "Found $CLAUDE_COUNT Claude model(s) available"
    echo "$CLAUDE_MODELS" | jq -r '.[] | "  - " + .modelId' 2>/dev/null || echo "  (jq not available for detailed listing)"
else
    print_status "ERROR" "No Claude models available in $REGION"
fi

printf "\\n\\n"

# Overall model availability assessment
if [[ "$NOVA_COUNT" -gt 0 && "$CLAUDE_COUNT" -gt 0 ]]; then
    print_status "SUCCESS" "Both Nova and Claude models are available"
elif [[ "$CLAUDE_COUNT" -gt 0 ]]; then
    print_status "WARNING" "Only Claude models available (Nova models missing)"
else
    print_status "ERROR" "Neither Nova nor Claude models available"
fi

printf "\\n\\n"

# Part 2: Test model invocation
print_status "INFO" "Part 2: Testing actual model invocation..."
printf "\\n\\n"

# Helper function to test model invocation using Python script
test_model_invocation() {
    local model_id="$1"
    local model_name="$2"
    
    # Check if virtual environment exists and activate it
    if [ -d "$PROJECT_ROOT/.venv" ]; then
        source "$PROJECT_ROOT/.venv/bin/activate"
    fi
    
    # Run the Python helper script
    if python3 "$PROJECT_ROOT/scripts/test_model_invocation.py" "$model_id" --profile "$PROFILE" --region "$REGION" $([[ "$VERBOSE" == "true" ]] && echo "--verbose"); then
        print_status "SUCCESS" "$model_name model invocation successful"
        return 0
    else
        print_status "ERROR" "$model_name model invocation failed - check model access in Bedrock console"
        return 1
    fi
}

# Use Claude model from .env file if available, otherwise use default
CLAUDE_MODEL_TO_TEST="${CLAUDE_MODEL_ID:-anthropic.claude-3-haiku-20240307-v1:0}"
print_status "INFO" "Testing Claude model invocation: $CLAUDE_MODEL_TO_TEST"
test_model_invocation "$CLAUDE_MODEL_TO_TEST" "Claude 3 Haiku"

printf "\\n\\n"
print_status "INFO" "Note: Nova Sonic requires audio input and cannot be tested with simple text invocation"


# Test 5: Region Compatibility Check
printf "\\n\\n${YELLOW}=== STEP 5: Region Compatibility Check ===${NC}\\n\\n"

if [[ "$REGION" == "us-east-1" ]]; then
    print_status "SUCCESS" "Using us-east-1 (recommended region for Nova models)"
else
    print_status "WARNING" "Using region $REGION - Nova Sonic may not be available"
    print_status "INFO" "Checking Nova Sonic availability in us-east-1..."
    NOVA_SONIC_US_EAST=$(aws bedrock list-foundation-models --profile "$PROFILE" --region "us-east-1" --query 'modelSummaries[?contains(modelId, `nova-sonic`)]' --output json 2>/dev/null | jq length 2>/dev/null || echo "0")
    if [[ "$NOVA_SONIC_US_EAST" -gt 0 ]]; then
        print_status "INFO" "Nova Sonic IS available in us-east-1"
        print_status "INFO" "Consider using us-east-1 for best Nova model support"
    fi
fi

# Test 6: Environment Variables Check
printf "\\n\\n${YELLOW}=== STEP 6: Environment Variables ===${NC}\\n\\n"

print_status "INFO" "Checking relevant environment variables..."
printf "\\n\\n"

if [[ -n "$AWS_PROFILE" ]]; then
    print_status "INFO" "AWS_PROFILE is set to: $AWS_PROFILE"
    if [[ "$AWS_PROFILE" != "$PROFILE" ]]; then
        print_status "WARNING" "AWS_PROFILE ($AWS_PROFILE) differs from test profile ($PROFILE)"
    fi
else
    print_status "INFO" "AWS_PROFILE not set (will use default profile)"
fi

printf "\\n\\n"

if [[ -n "$AWS_DEFAULT_REGION" ]]; then
    print_status "INFO" "AWS_DEFAULT_REGION is set to: $AWS_DEFAULT_REGION"
    if [[ "$AWS_DEFAULT_REGION" != "$REGION" ]]; then
        print_status "WARNING" "AWS_DEFAULT_REGION ($AWS_DEFAULT_REGION) differs from test region ($REGION)"
    fi
else
    print_status "INFO" "AWS_DEFAULT_REGION not set"
fi

printf "\\n\\n"

if [[ -n "$CLAUDE_MODEL_ID" ]]; then
    print_status "INFO" "CLAUDE_MODEL_ID is set to: $CLAUDE_MODEL_ID"
else
    print_status "INFO" "CLAUDE_MODEL_ID not set (using default)"
fi

# Summary
printf "\\n\\n${YELLOW}=== SUMMARY ===${NC}\\n"

echo ""
echo "Profile: $PROFILE"
echo "Region: $REGION"
echo ""
