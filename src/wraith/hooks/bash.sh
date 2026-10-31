# Wraith bash integration hook
# Evaluated via: eval "$(wraith init bash)"

if [ -z "$WRAITH_SESSION_ID" ]; then
    export WRAITH_SESSION_ID="$(od -vAn -N4 -tx1 /dev/urandom 2>/dev/null | tr -d ' ' || echo $$)"
fi

_wraith_get_runtime_dir() {
    if [ -n "$XDG_RUNTIME_DIR" ] && [ -d "$XDG_RUNTIME_DIR" ]; then
        echo "$XDG_RUNTIME_DIR/wraith"
    else
        echo "${HOME}/.cache/wraith"
    fi
}

_wraith_bash_preexec() {
    if [ "$WRAITH_OFF" = "1" ] || [ ! -t 1 ]; then
        return
    fi
    # Ignore internal commands or prompt executions
    if [[ "$1" =~ ^_wraith_ ]] || [[ "$1" =~ ^_bash_preexec ]]; then
        return
    fi
    _WRAITH_CMD="$1"
    _WRAITH_START_TS=$(date +%s%3N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1000))' 2>/dev/null || echo 0)
}

_wraith_bash_precmd() {
    local exit_code=$?
    if [ "$WRAITH_OFF" = "1" ] || [ ! -t 1 ]; then
        return
    fi

    local runtime_dir="$(_wraith_get_runtime_dir)"
    local whisper_file="${runtime_dir}/sessions/${WRAITH_SESSION_ID}.whisper"

    # Display pending whisper if present
    if [ -f "$whisper_file" ]; then
        cat "$whisper_file" 2>/dev/null
        rm -f "$whisper_file" 2>/dev/null
    fi

    if [ -n "$_WRAITH_CMD" ]; then
        local now_ts=$(date +%s%3N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1000))' 2>/dev/null || echo 0)
        local dur_ms=$(( now_ts - _WRAITH_START_TS ))
        if [ "$dur_ms" -lt 0 ]; then
            dur_ms=0
        fi
        local ts=$(( now_ts / 1000 ))
        local cmd="$_WRAITH_CMD"
        _WRAITH_CMD=""

        (
            python3 -m wraith.sender "$cmd" "$exit_code" "$PWD" "$ts" "$dur_ms" "$WRAITH_SESSION_ID" >/dev/null 2>&1 &
        ) 2>/dev/null
    fi
}

# Install DEBUG trap for preexec capture and PROMPT_COMMAND for precmd
set -o functrace >/dev/null 2>&1
trap '_wraith_bash_preexec "$BASH_COMMAND"' DEBUG
if [[ ";$PROMPT_COMMAND;" != *";_wraith_bash_precmd;"* ]]; then
    PROMPT_COMMAND="_wraith_bash_precmd${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
fi

