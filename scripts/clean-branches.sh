#!/bin/bash
#
# Agent-OS v3 - Clean local aos/ branches
# Deletes all local branches matching the aos/ prefix
#
# Usage: ./scripts/clean-branches.sh
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Agent-OS v3: Cleaning local aos/ branches ===${NC}"

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
echo -e "Current branch: ${YELLOW}${CURRENT_BRANCH}${NC}"

# Check if we're on an aos/ branch
if [[ "${CURRENT_BRANCH}" == aos/* ]]; then
    echo -e "${YELLOW}Warning: Currently on an aos/ branch${NC}"
    echo -e "${YELLOW}Switching to main before cleanup...${NC}"
    
    # Check if main branch exists
    if git show-ref --verify --quiet refs/heads/main; then
        git checkout main
    elif git show-ref --verify --quiet refs/heads/master; then
        git checkout master
    else
        echo -e "${RED}Error: Neither 'main' nor 'master' branch found${NC}"
        echo -e "${RED}Cannot proceed - please checkout a non-aos/ branch manually${NC}"
        exit 1
    fi
fi

# Get list of local aos/ branches
AOS_BRANCHES=$(git branch --list 'aos/*' | sed 's/^[* ]*//')

if [ -z "${AOS_BRANCHES}" ]; then
    echo -e "${GREEN}No local aos/ branches found - nothing to clean${NC}"
    exit 0
fi

# Count branches
BRANCH_COUNT=$(echo "${AOS_BRANCHES}" | wc -l)
echo -e "\n${YELLOW}Found ${BRANCH_COUNT} local aos/ branches:${NC}"
echo "${AOS_BRANCHES}"

# Confirm deletion
echo -e "\n${RED}WARNING: This will permanently delete all local aos/ branches${NC}"
read -p "Continue? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Cancelled - no branches deleted${NC}"
    exit 0
fi

# Delete branches
echo -e "\n${GREEN}Deleting branches...${NC}"
DELETED=0
FAILED=0

while IFS= read -r branch; do
    if [ -n "${branch}" ]; then
        if git branch -D "${branch}" 2>/dev/null; then
            echo -e "${GREEN}✓${NC} Deleted: ${branch}"
            ((DELETED++))
        else
            echo -e "${RED}✗${NC} Failed to delete: ${branch}"
            ((FAILED++))
        fi
    fi
done <<< "${AOS_BRANCHES}"

# Summary
echo -e "\n${GREEN}=== Cleanup Summary ===${NC}"
echo -e "Deleted: ${GREEN}${DELETED}${NC}"
if [ ${FAILED} -gt 0 ]; then
    echo -e "Failed: ${RED}${FAILED}${NC}"
fi
echo -e "\n${GREEN}=== Cleanup complete ===${NC}"
