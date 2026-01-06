#!/bin/bash
#
# Agent-OS v3 - Sync with main branch
# Pulls latest changes from main and shows recent commits
#
# Usage: ./scripts/sync-main.sh
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Agent-OS v3: Syncing with main ===${NC}"

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
echo -e "Current branch: ${YELLOW}${CURRENT_BRANCH}${NC}"

# Fetch latest from remote
echo -e "\n${GREEN}Fetching latest from origin...${NC}"
git fetch origin

# Check if main branch exists locally
if git show-ref --verify --quiet refs/heads/main; then
    MAIN_BRANCH="main"
elif git show-ref --verify --quiet refs/heads/master; then
    MAIN_BRANCH="master"
else
    echo -e "${RED}Error: Neither 'main' nor 'master' branch found${NC}"
    exit 1
fi

echo -e "Main branch: ${YELLOW}${MAIN_BRANCH}${NC}"

# Store current branch for later
ORIGINAL_BRANCH="${CURRENT_BRANCH}"

# Switch to main and pull
echo -e "\n${GREEN}Switching to ${MAIN_BRANCH} and pulling latest...${NC}"
git checkout "${MAIN_BRANCH}"
git pull origin "${MAIN_BRANCH}"

# Show recent commits
echo -e "\n${GREEN}=== Recent commits on ${MAIN_BRANCH} ===${NC}"
git log --oneline --decorate --graph -10

# Show commit stats
echo -e "\n${GREEN}=== Commit stats (last 10 commits) ===${NC}"
git log --oneline --shortstat -10

# Return to original branch if different
if [ "${ORIGINAL_BRANCH}" != "${MAIN_BRANCH}" ]; then
    echo -e "\n${GREEN}Returning to branch: ${YELLOW}${ORIGINAL_BRANCH}${NC}"
    git checkout "${ORIGINAL_BRANCH}"
    
    # Show if current branch is ahead/behind main
    echo -e "\n${GREEN}=== Branch status relative to ${MAIN_BRANCH} ===${NC}"
    git rev-list --left-right --count "${MAIN_BRANCH}"..."${ORIGINAL_BRANCH}" | \
        awk '{print "Commits behind main: " $1 "\nCommits ahead of main: " $2}'
fi

echo -e "\n${GREEN}=== Sync complete ===${NC}"
