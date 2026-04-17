#!/bin/bash
# Skopus Guard — PreToolUse hook that injects relevant corrections
# before risky actions (git push, deployment, file writes, etc.)
#
# How it works:
# 1. Reads the tool name and input from Claude Code's hook JSON
# 2. Extracts keywords from the command/action
# 3. Searches Skopus feedback files for matching corrections
# 4. Injects matched corrections as additionalContext
#
# The agent sees the correction RIGHT BEFORE executing the action —
# maximum attention, zero drift.
#
# Fires on: PreToolUse (Bash)

set -e

SKOPUS_DIR="$HOME/.skopus"
FEEDBACK_DIR="$SKOPUS_DIR/memory/feedback"

# Exit silently if Skopus isn't installed
[ -d "$FEEDBACK_DIR" ] || exit 0

# Read hook input
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input.command // .tool_input.file_path // ""' 2>/dev/null || echo "")

# Only process Bash commands (the risky ones)
[ "$TOOL_NAME" = "Bash" ] || exit 0
[ -n "$TOOL_INPUT" ] || exit 0

# Build keyword set from the command
COMMAND_LOWER=$(echo "$TOOL_INPUT" | tr '[:upper:]' '[:lower:]')

# Define trigger patterns and their search terms
# Each pattern: "command_pattern|search_keywords"
# Keywords must be specific enough that only 1-3 feedback files match
# Categories: git, deployment, testing, dependencies, destructive, build
TRIGGERS=(
    # Git operations
    "git push|git push,before push"
    "git rebase|rebase,cherry-pick"
    "git reset --hard|reset --hard,destructive"
    "git checkout --|checkout,discard"
    "git merge|merge,conflict"
    "git stash drop|stash drop,destructive"
    "git branch -D|branch -D,delete branch"
    "git clean|git clean,untracked"
    "--force|force-push,force push"
    "--no-verify|--no-verify,pre-commit,bypass"
    "git commit|commit,convention,message"
    "git tag|tag,release,version"
    # Deployment & infrastructure
    "deploy|deploy,staging,production"
    "kubectl|kubernetes,deploy,production"
    "terraform apply|terraform,infrastructure,apply"
    "docker push|docker push,registry"
    "docker compose up|docker,compose,overlay"
    "heroku|heroku,deploy"
    "railway|railway,staging,deploy"
    "aws |aws,cloud,infrastructure"
    "gcloud|gcloud,cloud,deploy"
    # Package management
    "npm run dev|npm run dev,local dev"
    "npm publish|npm publish,package,version"
    "pip install|pip install,dependency"
    "npm install|npm install,dependency"
    "pip uninstall|uninstall,remove,dependency"
    "yarn add|dependency,package"
    # Testing & CI
    "make ci|ci,test,before push"
    "pytest|test,coverage,assert"
    "npm test|test,coverage"
    "npm run build|build,compile,error"
    # Database operations
    "migrate|migration,database,schema"
    "alembic|alembic,migration,rollback"
    "DROP TABLE|drop table,destructive,database"
    "DROP DATABASE|drop database,destructive"
    "DELETE FROM|delete from,database,where"
    "TRUNCATE|truncate,destructive,database"
    "psql|database,query,production"
    "mongosh|database,query,production"
    # Destructive operations
    "rm -rf|rm -rf,delete,destructive"
    "rm -r|rm -r,delete,recursive"
    "chmod 777|chmod,permission,security"
    "curl.*POST|curl,api,request"
    "curl.*DELETE|curl,delete,api"
    # Secrets & security
    "echo.*KEY|secret,key,expose"
    "echo.*TOKEN|secret,token,expose"
    "echo.*PASSWORD|secret,password,expose"
    "cat.*\\.env|env,secret,expose"
    # Process management
    "kill -9|kill,process,force"
    "pkill|kill,process"
    "systemctl restart|restart,service,production"
)

# Check if command matches any trigger pattern
MATCHED_KEYWORDS=""
for trigger in "${TRIGGERS[@]}"; do
    PATTERN="${trigger%%|*}"
    KEYWORDS="${trigger##*|}"

    if echo "$COMMAND_LOWER" | grep -qi "$PATTERN" 2>/dev/null; then
        MATCHED_KEYWORDS="$KEYWORDS"
        break
    fi
done

# No match — exit silently (zero cost)
[ -n "$MATCHED_KEYWORDS" ] || exit 0

# Search feedback files for matching corrections
CORRECTIONS=""
MATCH_TOTAL=0
IFS=',' read -ra SEARCH_TERMS <<< "$MATCHED_KEYWORDS"

for feedback_file in "$FEEDBACK_DIR"/*.md; do
    [ -f "$feedback_file" ] || continue

    CONTENT_LOWER=$(tr '[:upper:]' '[:lower:]' < "$feedback_file")
    MATCH_COUNT=0

    for term in "${SEARCH_TERMS[@]}"; do
        term=$(echo "$term" | xargs)  # trim whitespace
        if echo "$CONTENT_LOWER" | grep -q "$term" 2>/dev/null; then
            MATCH_COUNT=$((MATCH_COUNT + 1))
        fi
    done

    # Require at least 2 keyword matches to avoid false positives
    if [ "$MATCH_COUNT" -ge 2 ]; then
        # Extract the title (first # heading) and first line of How to apply
        TITLE=$(grep "^# " "$feedback_file" | head -1 | sed 's/^# //')
        APPLY=$(grep -A1 '\*\*How to apply' "$feedback_file" | tail -1 | sed 's/^- //')

        if [ -n "$TITLE" ]; then
            MATCH_TOTAL=$((MATCH_TOTAL + 1))
            # Cap at 3 corrections to keep context focused
            if [ "$MATCH_TOTAL" -le 3 ]; then
                CORRECTIONS="${CORRECTIONS}
- ${TITLE}: ${APPLY}"
            fi
        fi
    fi
done

# No corrections matched — exit silently
[ -n "$CORRECTIONS" ] || exit 0

# Inject corrections as additionalContext
CONTEXT="Skopus correction reminder (relevant to this command):
${CORRECTIONS}"

jq -n --arg ctx "$CONTEXT" '{
    hookSpecificOutput: {
        hookEventName: "PreToolUse",
        additionalContext: $ctx
    }
}' 2>/dev/null || echo "$CONTEXT"

exit 0
