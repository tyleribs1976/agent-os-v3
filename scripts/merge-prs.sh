#!/usr/bin/env bash
#
# Agent-OS v3 PR Merge Script
# Lists open PRs and prompts for confirmation before merging
#
# Usage: ./scripts/merge-prs.sh [project-name]
#

set -euo pipefail

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source environment if available
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check for gh CLI
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed${NC}"
    echo "Install from: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}Error: Not authenticated with GitHub CLI${NC}"
    echo "Run: gh auth login"
    exit 1
fi

# Determine repository
if [ -n "${1:-}" ]; then
    REPO="$1"
else
    # Try to detect from git remote
    if git remote get-url origin &> /dev/null; then
        REPO=$(git remote get-url origin | sed -e 's/.*github\.com[:\/]//' -e 's/\.git$//')
    else
        echo -e "${RED}Error: Could not determine repository${NC}"
        echo "Usage: $0 [owner/repo]"
        exit 1
    fi
fi

echo -e "${BLUE}=== Agent-OS v3 PR Merge Tool ===${NC}"
echo -e "Repository: ${GREEN}${REPO}${NC}"
echo ""

# List open PRs
echo -e "${BLUE}Fetching open pull requests...${NC}"
PR_LIST=$(gh pr list --repo "$REPO" --json number,title,headRefName,author,createdAt,url --limit 50)

if [ "$(echo "$PR_LIST" | jq '. | length')" -eq 0 ]; then
    echo -e "${YELLOW}No open pull requests found.${NC}"
    exit 0
fi

# Display PRs
echo -e "${GREEN}Open Pull Requests:${NC}"
echo ""
echo "$PR_LIST" | jq -r '.[] | "  #\(.number) - \(.title)\n    Branch: \(.headRefName)\n    Author: \(.author.login)\n    Created: \(.createdAt)\n    URL: \(.url)\n"'

echo -e "${YELLOW}───────────────────────────────────────${NC}"
echo ""

# Prompt for PR number
while true; do
    read -p "Enter PR number to merge (or 'q' to quit): " PR_NUMBER
    
    if [ "$PR_NUMBER" = "q" ] || [ "$PR_NUMBER" = "Q" ]; then
        echo "Exiting."
        exit 0
    fi
    
    # Validate PR number is numeric
    if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}Invalid input. Please enter a number or 'q' to quit.${NC}"
        continue
    fi
    
    # Check if PR exists in list
    if ! echo "$PR_LIST" | jq -e ".[] | select(.number == $PR_NUMBER)" > /dev/null; then
        echo -e "${RED}PR #$PR_NUMBER not found in open PRs.${NC}"
        continue
    fi
    
    break
done

# Get PR details
PR_DETAILS=$(echo "$PR_LIST" | jq ".[] | select(.number == $PR_NUMBER)")
PR_TITLE=$(echo "$PR_DETAILS" | jq -r '.title')
PR_BRANCH=$(echo "$PR_DETAILS" | jq -r '.headRefName')
PR_AUTHOR=$(echo "$PR_DETAILS" | jq -r '.author.login')

echo ""
echo -e "${BLUE}Selected PR:${NC}"
echo -e "  Number: ${GREEN}#$PR_NUMBER${NC}"
echo -e "  Title: $PR_TITLE"
echo -e "  Branch: $PR_BRANCH"
echo -e "  Author: $PR_AUTHOR"
echo ""

# Get PR status checks
echo -e "${BLUE}Checking PR status...${NC}"
PR_STATUS=$(gh pr view "$PR_NUMBER" --repo "$REPO" --json statusCheckRollup,mergeable,reviewDecision)

MERGEABLE=$(echo "$PR_STATUS" | jq -r '.mergeable')
REVIEW_DECISION=$(echo "$PR_STATUS" | jq -r '.reviewDecision // "NONE"')

if [ "$MERGEABLE" != "MERGEABLE" ]; then
    echo -e "${RED}Warning: PR is not in a mergeable state (status: $MERGEABLE)${NC}"
fi

if [ "$REVIEW_DECISION" != "APPROVED" ]; then
    echo -e "${YELLOW}Warning: PR has not been approved (review status: $REVIEW_DECISION)${NC}"
fi

# Check status checks
STATUS_CHECKS=$(echo "$PR_STATUS" | jq -r '.statusCheckRollup // [] | length')
if [ "$STATUS_CHECKS" -gt 0 ]; then
    FAILED_CHECKS=$(echo "$PR_STATUS" | jq -r '[.statusCheckRollup[] | select(.conclusion == "FAILURE" or .conclusion == "CANCELLED")] | length')
    if [ "$FAILED_CHECKS" -gt 0 ]; then
        echo -e "${RED}Warning: $FAILED_CHECKS status check(s) failed${NC}"
    fi
fi

echo ""

# Confirmation prompt
read -p "$(echo -e "${YELLOW}Merge PR #$PR_NUMBER? [y/N]:${NC} ")" CONFIRM

if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Merge cancelled."
    exit 0
fi

# Perform merge
echo ""
echo -e "${BLUE}Merging PR #$PR_NUMBER...${NC}"

if gh pr merge "$PR_NUMBER" --repo "$REPO" --squash --delete-branch; then
    echo -e "${GREEN}✓ Successfully merged PR #$PR_NUMBER${NC}"
    echo -e "${GREEN}✓ Branch '$PR_BRANCH' deleted${NC}"
    exit 0
else
    echo -e "${RED}✗ Failed to merge PR #$PR_NUMBER${NC}"
    exit 1
fi
