# Wraith zsh integration hook
# Evaluated via: eval "$(wraith init zsh)"

if [[ -z "$WRAITH_SESSION_ID" ]]; then
    export WRAITH_SESSION_ID="$(od -vAn -N4 -tx1 /dev/urandom 2>/dev/null | tr -d ' ' || echo $$)"
fi

_wraith_get_runtime_dir() {
    if [[ -n "$XDG_RUNTIME_DIR" && -d "$XDG_RUNTIME_DIR" ]]; then
        echo "$XDG_RUNTIME_DIR/wraith"
    else
        echo "${HOME}/.cache/wraith"
    fi
}

_wraith_preexec() {
    # Check if disabled for this session
    if [[ "$WRAITH_OFF" = "1" || ! -t 1 ]]; then
        return
    fi
    _WRAITH_CMD="$1"
    _WRAITH_START_TS=$(date +%s%3N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1000))' 2>/dev/null || echo 0)
}

_wraith_precmd() {
    local exit_code=$?
    if [[ "$WRAITH_OFF" = "1" || ! -t 1 ]]; then
        return
    fi

    local runtime_dir="$(_wraith_get_runtime_dir)"
    local whisper_file="${runtime_dir}/sessions/${WRAITH_SESSION_ID}.whisper"

    # Display pending whisper if present
    if [[ -f "$whisper_file" ]]; then
        cat "$whisper_file" 2>/dev/null
        rm -f "$whisper_file" 2>/dev/null
    fi

    # If we have a recorded command from preexec, report it
    if [[ -n "$_WRAITH_CMD" ]]; then
        local now_ts=$(date +%s%3N 2>/dev/null || python3 -c 'import time; print(int(time.time()*1000))' 2>/dev/null || echo 0)
        local dur_ms=$(( now_ts - _WRAITH_START_TS ))
        if (( dur_ms < 0 )); then
            dur_ms=0
        fi
        local ts=$(( now_ts / 1000 ))
        local cmd="$_WRAITH_CMD"
        _WRAITH_CMD=""

        # Fire and forget background dispatch to daemon
        (
            python3 -m wraith.sender "$cmd" "$exit_code" "$PWD" "$ts" "$dur_ms" "$WRAITH_SESSION_ID" >/dev/null 2>&1 &
        ) 2>/dev/null
    fi
}

autoload -Uz add-zsh-hook 2>/dev/null
if typeset -f add-zsh-hook >/dev/null 2>&1; then
    add-zsh-hook preexec _wraith_preexec
    add-zsh-hook precmd _wraith_precmd
else
    preexec_functions+=(_wraith_preexec)
    precmd_functions+=(_wraith_precmd)
fi

