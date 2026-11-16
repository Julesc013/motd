#!/bin/sh
# Portable MOTD baseline. POSIX shell syntax; no Bash, Python or service manager.
# This deliberately small renderer does not reproduce the Linux Bash collectors.
# Linux /proc files provide cheap local observations when available. Missing
# counters stay unavailable; no external command or network lookup fills them in.
# GNU-compatible timeout is required only for explicitly configured hooks.

TITLE='SYSTEM STATUS'
SITE_LABEL=''
THEME=mono
MAX_WIDTH=80
ROWS=25
SECTIONS='system resources attention hints'
motd_messages() { :; }
motd_hints() { :; }
motd_before_hooks() { :; }
motd_after_hooks() { :; }

# @MOTD_CONFIG@

MOTD_DEMO=0
MOTD_DEMO_ALERTS=0
MOTD_HOOKS_ENABLED=1
MOTD_PLAIN=0
MOTD_FORCE_COLOR=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --demo) MOTD_DEMO=1; MOTD_HOOKS_ENABLED=0 ;;
        --demo-alerts) MOTD_DEMO=1; MOTD_DEMO_ALERTS=1; MOTD_HOOKS_ENABLED=0 ;;
        --no-hooks) MOTD_HOOKS_ENABLED=0 ;;
        --plain) MOTD_PLAIN=1 ;;
        --color) MOTD_FORCE_COLOR=1 ;;
        --ascii) : ;; # The baseline already uses ASCII framing.
        --width|--rows)
            motd_option=$1
            shift
            case "${1-}" in
                ''|*[!0-9]*) printf '%s\n' 'Width/rows require an integer.' >&2; exit 2 ;;
            esac
            # Check length first: never feed an unbounded integer into old shells.
            if [ "${#1}" -gt 3 ]; then
                printf '%s\n' 'Width/rows are outside the supported range.' >&2
                exit 2
            fi
            motd_number=$1
            # Old shells may read leading-zero arithmetic as octal.
            while [ "${motd_number#0}" != "$motd_number" ] && [ "${#motd_number}" -gt 1 ]; do
                motd_number=${motd_number#0}
            done
            if [ "$motd_option" = --width ]; then
                if [ "$motd_number" -lt 40 ] || [ "$motd_number" -gt 240 ]; then exit 2; fi
                MAX_WIDTH=$motd_number
            else
                if [ "$motd_number" -lt 20 ] || [ "$motd_number" -gt 60 ]; then exit 2; fi
                ROWS=$motd_number
            fi ;;
        --version) printf '%s\n' 'MOTD portable sh baseline'; exit 0 ;;
        --list-sections) printf '%s\n' 'system resources services processes sessions connections attention hints io'; exit 0 ;;
        --help|-h)
            printf '%s\n' 'Portable MOTD: --demo --demo-alerts --plain --color --ascii --no-hooks --width N --rows N' \
                'Basic identity, Linux memory/load/uptime where available, messages and hints.' \
                'Advanced service, process, session, connection and I/O collectors are unavailable.'
            exit 0 ;;
        *) printf '%s\n' "Unknown portable MOTD option: $1" >&2; exit 2 ;;
    esac
    shift
done

# No arbitrary helper programs run during data collection. Configuration text is
# quoted by the generator; the display helper also replaces terminal controls.
# Width clipping is by shell characters, not a Unicode grapheme-width engine.
motd_remaining=$((ROWS - 1))
motd_line() {
    if [ "$motd_remaining" -le 0 ]; then return; fi
    if [ "$motd_remaining" -eq 1 ]; then
        printf '%s\n' '[More content omitted]'
        motd_remaining=0
        return
    fi
    motd_rest=$1
    motd_clean=''
    motd_count=0
    while [ -n "$motd_rest" ] && [ "$motd_count" -lt "$MAX_WIDTH" ]; do
        motd_character=${motd_rest%"${motd_rest#?}"}
        motd_rest=${motd_rest#?}
        case "$motd_character" in [[:cntrl:]]) motd_character='?' ;; esac
        motd_clean=$motd_clean$motd_character
        motd_count=$((motd_count + 1))
    done
    printf '%s\n' "$motd_clean"
    motd_remaining=$((motd_remaining - 1))
}

motd_heading() {
    # Colour is an optional enhancement. NO_COLOR and dumb/redirected terminals
    # remain plain; no terminal escape sequence is sourced from configuration.
    if [ "$MOTD_PLAIN" -eq 0 ] && [ "$THEME" != mono ] && { [ -t 1 ] || [ "$MOTD_FORCE_COLOR" -eq 1 ]; } && [ -z "${NO_COLOR+x}" ] && [ "${TERM-dumb}" != dumb ]; then
        case "$THEME" in
            cyan) printf '\033[1;36m' ;;
            green) printf '\033[1;32m' ;;
            amber) printf '\033[1;33m' ;;
        esac
        motd_line "$1"
        printf '\033[0m'
    else
        motd_line "$1"
    fi
}

motd_host=unavailable
motd_os=unavailable
motd_release=unavailable
motd_uptime=unavailable
motd_load=unavailable
motd_total=unavailable
motd_available=unavailable
motd_free=unavailable
if [ "$MOTD_DEMO" -eq 1 ]; then
    motd_host=demo-host
    motd_os=Linux
    motd_release=demo-kernel
    motd_uptime=86400
    motd_load='0.25 0.18 0.12'
    motd_total=16777216
    motd_available=12582912
    motd_free=8388608
else
    # All reads are of fixed local procfs files. The scan has a hard line-count
    # bound; kernel/filesystem stalls are still outside a shell's timing control.
    if [ -r /proc/sys/kernel/hostname ]; then IFS= read -r motd_host < /proc/sys/kernel/hostname || :; fi
    if [ -r /proc/sys/kernel/ostype ]; then IFS= read -r motd_os < /proc/sys/kernel/ostype || :; fi
    if [ -r /proc/sys/kernel/osrelease ]; then IFS= read -r motd_release < /proc/sys/kernel/osrelease || :; fi
    if [ -r /proc/uptime ]; then
        read -r motd_uptime motd_unused < /proc/uptime || :
        motd_uptime=${motd_uptime%%.*}
        case "$motd_uptime" in ''|*[!0-9]*) motd_uptime=unavailable ;; esac
    fi
    if [ -r /proc/loadavg ]; then
        read -r motd_load1 motd_load5 motd_load15 motd_unused < /proc/loadavg || :
        if [ -n "$motd_load1" ] && [ -n "$motd_load5" ] && [ -n "$motd_load15" ]; then
            motd_load="$motd_load1 $motd_load5 $motd_load15"
        fi
    fi
    if [ -r /proc/meminfo ]; then
        motd_mem_lines=0
        while read -r motd_key motd_value motd_unit; do
            motd_mem_lines=$((motd_mem_lines + 1))
            if [ "$motd_mem_lines" -gt 128 ]; then break; fi
            case "$motd_value" in ''|*[!0-9]*) continue ;; esac
            case "$motd_key" in
                MemTotal:) motd_total=$motd_value ;;
                MemAvailable:) motd_available=$motd_value ;;
                MemFree:) motd_free=$motd_value ;;
            esac
        done < /proc/meminfo
    fi
fi
motd_host=${motd_host:-unavailable}
motd_os=${motd_os:-unavailable}
motd_release=${motd_release:-unavailable}

motd_before_hooks || exit "$?"
motd_heading "$TITLE"
if [ -n "$SITE_LABEL" ]; then motd_line "$SITE_LABEL"; fi
motd_line 'Portable sh baseline'
for motd_section in $SECTIONS; do
    case "$motd_section" in
        system)
            motd_heading 'SYSTEM'
            motd_line "Host: $motd_host | OS: $motd_os $motd_release"
            motd_line "Uptime: $motd_uptime s | Load (1/5/15 min): $motd_load" ;;
        resources)
            motd_heading 'RESOURCES'
            if [ "$motd_available" != unavailable ]; then
                motd_line "Memory available: $motd_available KiB / $motd_total KiB total"
            elif [ "$motd_free" != unavailable ]; then
                motd_line "Memory free: $motd_free KiB / $motd_total KiB total (available: unavailable)"
            else
                motd_line 'Memory: unavailable'
            fi
            motd_line 'Storage, swap detail and pressure: unavailable in portable baseline' ;;
        attention)
            motd_heading 'NOTICES'
            if [ "$MOTD_DEMO_ALERTS" -eq 1 ]; then motd_line 'DEMO: Example warning; no live fault is implied.'; fi
            motd_messages ;;
        hints)
            motd_heading 'HINTS'
            motd_hints ;;
        services|processes|sessions|connections|io)
            motd_line "$motd_section: not collected by the portable sh backend" ;;
    esac
done
motd_after_hooks || exit "$?"
