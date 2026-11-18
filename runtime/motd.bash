#!/bin/bash
# MOTD Bash runtime 0.5.0-alpha.1 | derived from Workshop MOTD 1.2.0, 2026-11-16.
# Bash 4.3+ and GNU timeout; optional GNU df, procps ps, iproute2, systemd.
# Standalone output: generate settings with motd.py, then use --demo or --help.
# No daemon, installation side effects, network requests, recursive disk scans,
# privilege escalation, commands from data, or state-changing system actions.
# External helpers have deadlines; kernel I/O stalls cannot have a hard deadline.

if ((BASH_VERSINFO[0]<4 || (BASH_VERSINFO[0]==4 && BASH_VERSINFO[1]<3))); then
    printf '%s\n' 'MOTD status needs Bash 4.3 or newer.' >&2
    exit 0
fi

# Generated explicit hooks belong after the version guard: unsupported Bash
# must return to the login shell before any configured command can execute.
# @MOTD_HOOKS@

# =========================== 1. SETTINGS =====================================
# Legacy internal value retained for tested collectors/components. Public output
# always uses the adaptive row planner; there is no concise/verbose CLI switch.
MODE=concise
COMPACT_ROWS=25                  # Includes one row reserved for the shell prompt.
CONCISE_WORKER_SECONDS=0.20      # Whole worker deadline, not per-query timeout.
CONCISE_KILL_SECONDS=0.02        # Reserve parent/fallback time below a 400ms target.
COLLECTION_BUDGET_MS=140         # Stop starting collectors before worker deadline.
CONCISE_HELPER_MAX_MS=75


IO_TOP_N=3
IO_PROCESS_LIMIT=512            # Maximum PID directories examined per snapshot.
IO_SCAN_BUDGET_MS=35            # Cooperative budget per PID pass, checked per 8 PIDs.
IO_MIN_SAMPLE_MS=20             # Shorter natural intervals use cumulative totals.
IO_MAX_SAMPLE_MS=30000          # Counter comparison only within this invocation.
IO_DEVICE_LIMIT=64
IO_SHOW_DEVICES=3
IO_VERBOSE_PROCESS_LIMIT=8192
IO_VERBOSE_SCAN_BUDGET_MS=200

TITLE='SYSTEM STATUS'
MAX_WIDTH=132                   # Use available width up to this cap.
THEME=cyan                     # cyan | amber | mono
CHARSET=auto                    # auto | ascii | unicode; CLI flags override.
COLOR_MODE=auto                 # auto | always | never; NO_COLOR still wins.
BAR_LAYOUT=inline               # inline | wide; wide retains numeric labels.
DESIGN=classic                  # classic | cards | ledger | briefing | dashboard
DENSITY=balanced                # compact | balanced | comfortable
DETAIL=normal                   # brief | normal | full; independent of spacing
PADDING=1 SECTION_GAP=0
PANEL_LAYOUT=auto
PANEL_FRAME=auto
HEADING_STYLE=auto
BORDER_STYLE=single
BORDER_VISIBILITY=all
HEADING_ALIGN=left
SEPARATOR_TEXT=none
LABEL_STYLE=full
OVERFLOW=ellipsis
COLOR_EMPHASIS=balanced          # quiet | balanced | vivid
SECTION_PRIORITY=(attention resources system services processes io sessions connections hints)
declare -A SECTION_DETAIL=()
MOTD_FASTFETCH=0                # External before/after hooks are owned by motd.py.
FASTFETCH_TIMEOUT=1s
STORAGE_TIMEOUT=0.4s
IDENTITY_TIMEOUT=0.3s
JOURNAL_TIMEOUT=0.4s
RAM_WARN=85 RAM_CRITICAL=95
DISK_WARN=90 DISK_CRITICAL=95
INODE_WARN=90 INODE_CRITICAL=95
PSI_WARN=10                     # >=10% memory/I/O full stall, avg10; observation.
SHOW_SWAP=1 SHOW_COMPRESSION=1 SHOW_ATTENTION=1
SHOW_PRESSURE=1 SHOW_JOURNAL=0   # Journal access is an explicit optional collector.
JOURNAL_WINDOW=1h JOURNAL_LIMIT=20
# Host domain is local configuration, never a claim of AD membership or DNS health.
SITE_LABEL=''                   # Change freely for each site or machine role.
DOMAIN_OVERRIDE=''             # e.g. workshop.example; blank = local DNS config.
STORAGE_MOUNTS=()              # Empty = eligible local mounted filesystems.
MAX_IPS=4 MAX_DISK_DETAILS=4 MAX_ATTENTION=12
# Comments and commands are data; the MOTD never executes these suggestions.
MESSAGES=()                    # Example: ('INFO|Bench 3: storage test in progress.')
declare -A COLOR_CODE=(
    [border]=36 [heading]='1;37' [other]='1;34' [cache]=36
    [compressed]=35 [free]=90 [reserved]=33 [ok]=32 [warn]='1;33'
    [error]='1;31' [muted]=90 [text]=37
    [cpu]='1;33' [rss]='1;35' [io]='1;36' [label]='1;37' [value]=37
)
DISK_COLOR_CODES=('1;34' 36 35 32 33 37)

SERVICE_TIMEOUT=0.4s
SERVICES_MODE=common             # common | all; inventory still uses the work budget.
SERVICE_EXTRA_LIMIT=6            # Extra active units in the installed-unit inventory.
SERVICE_ALERT_LIMIT=8            # Failure details; the total is always reported.
# Explicitly required unit names only. Inactive/disabled optional units are normal.
# For socket activation, require the .socket rather than its idle .service.
REQUIRED_UNITS=()               # Example: (ssh.socket cron.service)
SERVICE_EXCLUDE_PATTERNS=('ollama*' 'llama*' 'vllm*' 'lmstudio*')
# Optional classification overrides: [your-backup.service]=System
declare -A SERVICE_GROUP_OVERRIDE=()
SERVICE_GROUPS=(Access Files Web Data Mail Network Identity Security Virtual System Time Local)

TOP_N=3
MAX_SESSIONS=6
MAX_CONNECTIONS=4
ACTIVITY_TIMEOUT=0.4s
SESSION_QUERY_LIMIT=128
# These are port hints, not protocol verification. Change for nonstandard ports.
declare -A CONNECTION_PORT_LABEL=(
    [22]=SSH [3389]=RDP [5900]=VNC [5901]=VNC [5902]=VNC
    [21]=FTP [445]=SMB [2049]=NFS [80]=HTTP [443]=HTTPS
)
CONNECTION_ADMIN_PORTS=(22 3389 5900 5901 5902)
# PAM service names reported by logind; a session can outlive its connection.
declare -A SESSION_SERVICE_KIND=([sshd]=SSH [ssh]=SSH [xrdp-sesman]=RDP)


# One adaptive display order. Hiding is presentation-only; alerts still collect.
SECTIONS=(system resources services processes sessions connections attention hints)
# ID = title | renderer | base rows | minimum rows | maximum rows.
# A row budget includes its named divider. Outer borders and prompt are separate.
declare -A SECTION_SPEC=(
    [system]='SYSTEM|ui_system|3|2|6'
    [resources]='RESOURCES|ui_resources|4|3|10'
    [services]='SERVICES|ui_services|3|2|10'
    [processes]='TOP PROCESSES|ui_tasks|5|3|10'
    [sessions]='SESSIONS|ui_sessions|3|2|10'
    [connections]='CONNECTIONS|ui_connections|1|1|8'
    [attention]='ATTENTION|ui_attention|2|2|14'
    [hints]='HINTS|ui_hints|1|1|10'
    [io]='DISK I/O|ui_io|4|2|12'
)
# Optional overrides: SECTION_VISIBLE[services]=0; SECTION_TITLE[sessions]='USERS'
# Explicit row overrides are hard caps, including the section's divider.
# SECTION_ROWS[processes]=6; SECTION_ROWS[services]=4
# ITEM_VISIBLE[resources.swap]=0; ITEM_VISIBLE[services.FTP]=0
# ITEM_VISIBLE[sessions.peer]=0; ITEM_VISIBLE[hints.devices]=0
# Legacy mode-prefixed row keys remain accepted for imported configurations.
declare -A SECTION_VISIBLE=() SECTION_TITLE=() SECTION_ROWS=() ITEM_VISIBLE=()
COMPACT_TRIM_ORDER=(resources services sessions system processes attention connections hints)
COMPACT_EXPAND_ORDER=(processes services sessions attention resources connections system hints)

THEME_NAMES=(cyan amber green mono)
declare -A THEME_COLOR_CODE=(
    [amber.border]=33 [amber.heading]='1;33' [amber.label]='1;33'
    [green.border]=32 [green.heading]='1;32' [green.label]='1;32'
)
# Common role aliases are data; append a role and its units to extend the overview.
SERVICE_ROLE_ORDER=(SSH RDP SMB FTP TFTP GUI OOM WEB DB NET DNS AUTH CONTAINERS CRON TIME NFS PRINT VPN VM LOG)
declare -A SERVICE_ROLE_UNITS=(
    [SSH]='ssh.service sshd.service ssh.socket sshd.socket'
    [RDP]='xrdp.service gnome-remote-desktop.service'
    [SMB]='smbd.service smb.service samba.service samba-ad-dc.service'
    [FTP]='vsftpd.service proftpd.service pure-ftpd.service vsftpd.socket'
    [TFTP]='tftpd-hpa.service tftp.service tftp.socket atftpd.service'
    [GUI]='display-manager.service lightdm.service gdm.service gdm3.service sddm.service xdm.service'
    [OOM]='earlyoom.service systemd-oomd.service'
    [WEB]='nginx.service apache2.service httpd.service caddy.service'
    [DB]='postgresql.service mariadb.service mysql.service mongod.service redis-server.service redis.service'
    [NET]='NetworkManager.service systemd-networkd.service networking.service'
    [DNS]='named.service bind9.service unbound.service dnsmasq.service systemd-resolved.service'
    [AUTH]='sssd.service winbind.service nslcd.service'
    [CONTAINERS]='docker.service containerd.service podman.service'
    [CRON]='cron.service crond.service'
    [TIME]='chrony.service chronyd.service systemd-timesyncd.service ntp.service ntpd.service'
    [NFS]='nfs-server.service nfs-kernel-server.service'
    [PRINT]='cups.service cups.socket'
    [VPN]='openvpn.service wg-quick@wg0.service tailscaled.service'
    [VM]='libvirtd.service virtqemud.service'
    [LOG]='rsyslog.service syslog-ng.service systemd-journald.service'
)
declare -A SERVICE_ROLE_LABEL=([CONTAINERS]='CTR')
# id | label | displayed command | longer explanation. Commands are NEVER executed.
HINTS=(
    'more|More|--rows 50|show more rows within the same layout'
    'tasks|Tasks|top|live CPU and memory'
    'io|I/O|iotop -o|live process I/O; if installed and permitted'
    'devices|Devices|iostat -xz 1|live device I/O; if installed'
    'services|Services|systemctl --failed|failed units'
    'logs|Logs|journalctl -b -p warning -n 30|visible journal'
    'sessions|Sessions|loginctl list-sessions|registered logins'
    'sockets|Sockets|ss -nt|established TCP sockets'
)

# Generated settings are literal assignments; no additional config file is read.
# @MOTD_CONFIG@

# MODE is a private compatibility detail, never an alternative public renderer.
MODE=concise

# This bootstrap runs before parsing the large function body on a normal adaptive
# invocation. A private regular file avoids pipe EOF waits on a stuck descendant.
# No persistent cache, daemon, or privilege escalation. Settings above stay shared.
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    ws_guard=1; ws_guard_worker=0
    for ws_arg in "$@"; do
        case $ws_arg in
            --demo|--demo-alerts|--help|-h|--version|--list-sections|--list-items|--_validate-options) ws_guard=0 ;;
            --_worker) ws_guard=0; ws_guard_worker=1 ;;
        esac
    done
    if ((ws_guard)); then
        export PATH=/usr/sbin:/usr/bin:/sbin:/bin
        ws_tmp=''; ws_dir=/tmp; ws_tty=''; ws_rc=0; ws_result=''
        [[ ! -d /dev/shm || ! -w /dev/shm || ! -x /dev/shm ]] || ws_dir=/dev/shm
        if [[ -t 1 ]]; then ws_tty=$( { stty size </dev/tty; } 2>/dev/null); fi
        if command -v timeout >/dev/null 2>&1 && command -v mktemp >/dev/null 2>&1; then
            ws_tmp=$(mktemp "$ws_dir/motd-status.XXXXXXXX" 2>/dev/null) || ws_tmp=''
        fi
        if [[ -n $ws_tmp ]]; then
            # A killed descendant may retain this unlinked regular file, never
            # the login's stdout pipe. Do not change this command to $(timeout...).
            trap 'rm -f -- "$ws_tmp"' EXIT
            {
                timeout --kill-after="$CONCISE_KILL_SECONDS" "$CONCISE_WORKER_SECONDS" \
                    /bin/bash "${BASH_SOURCE[0]}" --_worker --_tty-size "$ws_tty" "$@" \
                    >"$ws_tmp" 2>/dev/null || ws_rc=$?
            } 2>/dev/null
            if ((ws_rc==0)); then
                ws_result=$(<"$ws_tmp")
                if [[ $ws_result == *$'\n__WORKSHOP_COMPLETE_V2__' ]]; then
                    printf '%s\n' "${ws_result%$'\n__WORKSHOP_COMPLETE_V2__'}"
                    exit 0
                fi
            elif ((ws_rc==2)); then
                printf '%s\n' 'Invalid MOTD options or configuration; use --help.' >&2
                exit 2
            fi
            rm -f -- "$ws_tmp"; trap - EXIT; ws_tmp=''
        fi
        # Keep login usable if the collector cannot finish: a fresh small local
        # snapshot clearly marks omitted sections instead of publishing partial bytes.
        WORKSHOP_BUDGET_FALLBACK=1
    fi
fi


# ===================== 2. CORE COLLECTION / CONTROL ==========================
ROWS_OVERRIDE='' TTY_SIZE_OVERRIDE='' WORKER=0 VALIDATE_ONLY=0
BUDGET_START_MS=0 BUDGET_ACTIVE=0 LOCAL_ONLY=0
budget_clock() {
    # /proc/uptime is monotonic and available on Bash4.3; centisecond resolution.
    local now rest whole fraction
    if read -r now rest <"$PROC_ROOT/uptime" 2>/dev/null && [[ $now =~ ^([0-9]+)\.([0-9]+)$ ]]; then
        whole=${BASH_REMATCH[1]}; fraction=${BASH_REMATCH[2]}00; fraction=${fraction:0:3}
        REPLY=$((10#$whole*1000+10#$fraction)); return 0
    fi
    REPLY=0; return 1
}
budget_start() {
    BUDGET_ACTIVE=0; MODEL[budget_limited]=0
    [[ $MODE == concise && $DEMO == 0 ]] || return 0
    if budget_clock; then BUDGET_START_MS=$REPLY; BUDGET_ACTIVE=1; fi
}
budget_remaining() {
    REPLY=$COLLECTION_BUDGET_MS
    ((BUDGET_ACTIVE)) || return 0
    if budget_clock; then REPLY=$((COLLECTION_BUDGET_MS-(REPLY-BUDGET_START_MS))); fi
    ((REPLY>0))
}
budget_allow() {
    if budget_remaining; then return 0; fi
    MODEL[budget_limited]=1; return 1
}


initialize_optional_model() {
    MODEL[services_state]=budget; MODEL[svc_runtime_state]=budget; MODEL[svc_files_state]=skipped
    MODEL[services_scope]=runtime; svc_finalize
    MODEL[process_state]=budget; MODEL[process_count]=0; MODEL[process_running]=0
    MODEL[process_blocked]=0; MODEL[process_zombies]=0
    MODEL[session_state]=budget; MODEL[session_source]=none
    MODEL[session_records]=0; MODEL[session_parsed]=0; MODEL[session_count]=0; MODEL[session_users]=0; MODEL[session_limited]=0
    MODEL[connection_state]=budget; MODEL[tcp_established]=0; MODEL[tcp_admin]=0
    MODEL[journal_state]=skipped; MODEL[journal_count]=0; MODEL[journal_capped]=0
    MODEL[storage_state]=budget; MODEL[storage_skipped]=0; MODEL[storage_skipped_shared]=0
    MODEL[io_state]=budget; MODEL[io_mode]=unavailable
    ACT_PROC=(); ACT_CPU_IDS=(); ACT_RAM_IDS=(); ACT_SESSION=(); ACT_SESSION_IDS=(); ACT_CONN=(); ACT_CONN_IDS=()
}


# Plain numbers are KiB unless a key says otherwise; unknown is never zero.
declare -A MODEL=() DISK=() COLOR=() VIEW=()
DISK_IDS=() ATTENTION=() HEALTH_NOTES=() HOST_IPS=()
FASTFETCH_TEXT='' OUTPUT='' REPLY=''
DEMO=0 PLAIN=0 ASCII=0 FORCE_COLOR=0 WIDTH_OVERRIDE='' FETCH_OVERRIDE='' THEME_OVERRIDE=''
[[ $CHARSET != ascii ]] || ASCII=1
PROC_ROOT=/proc SYS_ROOT=/sys ETC_ROOT=/etc RUN_ROOT=/run
VERSION=0.5.0-alpha.1

usage() {
    printf '%s\n' \
      'MOTD adaptive runtime 0.5.0-alpha.1 - standalone Linux status display.' \
      'Usage: motd.bash [--rows 8..200]' \
      '       [--width 24..240] [--theme cyan|amber|green|mono] [--plain|--color] [--ascii|--unicode]' \
      '       [--design classic|cards|ledger|briefing|dashboard] [--detail brief|normal|full]' \
      '       [--density compact|balanced|comfortable] [--padding 0..3] [--section-gap 0..2]' \
      '       [--color-emphasis quiet|balanced|vivid]' \
      '       [--bar-layout inline|wide]' \
      '       [--sections system,resources,services,processes,sessions,connections,attention,hints]' \
      '       [--hide SECTION,...] [--show SECTION,...]' \
      '       [--hide-item SECTION.ITEM,...] [--show-item SECTION.ITEM,...]' \
      '       [--list-sections] [--list-items] [--demo|--demo-alerts]' \
      '       [--services common|all] [--top 1..10] [--sessions 1..30]' \
      '       [--connections 1..30] [--journal|--no-journal]' \
      '' \
      'One adaptive layout keeps section frames and aligned rankings.' \
      'The default budget is 25 rows including a prompt row; --rows 50 adds detail.' \
      '--services all requests installed-unit inventory within the collection budget.' \
      '--journal explicitly requests the recent visible journal summary.' \
      'Section order, item visibility, titles, themes and hints share one renderer.' \
      'Hiding a panel does not disable its underlying warning checks.' \
      'I/O rates use two reads during other collection; no sampling sleep.' \
      'Collection uses a bounded worker and a clearly marked reduced fallback.' \
      'Optional hooks configured by motd.py run outside this display budget.' \
      'Elapsed time is not guaranteed under scheduler starvation or kernel stalls.'
}
parse_options() {
    local n candidate found
    while (($#)); do
        case $1 in
            --_worker) WORKER=1; shift ;;
            --_validate-options) VALIDATE_ONLY=1; shift ;;
            --_tty-size)
                (($#>=2)) || return 2
                [[ -z $2 || $2 =~ ^[0-9]{1,3}[[:space:]][0-9]{1,3}$ ]] || return 2
                TTY_SIZE_OVERRIDE=$2; shift 2 ;;
            --demo) DEMO=1; shift ;;
            --demo-alerts) DEMO=2; shift ;;
            --plain) PLAIN=1; shift ;;
            --no-hooks) shift ;; # The generated wrapper owns hook suppression.
            --color) FORCE_COLOR=1; shift ;;
            --ascii) ASCII=1; shift ;;
            --unicode) ASCII=0; shift ;;
            --design)
                case ${2-} in classic|cards|ledger|briefing|dashboard) DESIGN=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --density)
                case ${2-} in compact|balanced|comfortable) DENSITY=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --detail)
                case ${2-} in brief|normal|full) DETAIL=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --color-emphasis)
                case ${2-} in quiet|balanced|vivid) COLOR_EMPHASIS=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --panel-layout)
                case ${2-} in auto|stack|columns) PANEL_LAYOUT=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --panel-frame)
                case ${2-} in auto|continuous|separate|none) PANEL_FRAME=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --heading-style)
                case ${2-} in auto|rule|plain|inline|hidden) HEADING_STYLE=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --border-style)
                case ${2-} in single|rounded|double|heavy|ascii) BORDER_STYLE=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --border-visibility)
                case ${2-} in all|outer|sections|none) BORDER_VISIBILITY=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --heading-align)
                case ${2-} in left|center|right) HEADING_ALIGN=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --separator-text)
                case ${2-} in none|summary|custom) SEPARATOR_TEXT=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --label-style)
                case ${2-} in full|short) LABEL_STYLE=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --overflow)
                case ${2-} in ellipsis|clip) OVERFLOW=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --bar-layout)
                case ${2-} in inline|wide) BAR_LAYOUT=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --padding)
                case ${2-} in 0|1|2|3) PADDING=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --section-gap)
                case ${2-} in 0|1|2) SECTION_GAP=$2 ;; *) return 2 ;; esac; shift 2 ;;
            --no-fastfetch) FETCH_OVERRIDE=0; shift ;;
            --journal) SHOW_JOURNAL=1; shift ;;
            --no-journal) SHOW_JOURNAL=0; shift ;;
            --services)
                case ${2-} in common|all) SERVICES_MODE=$2 ;; *) usage >&2; return 2 ;; esac
                shift 2 ;;
            --width|--rows|--top|--sessions|--connections)
                [[ ${2-} =~ ^[0-9]{1,3}$ ]] || { usage >&2; return 2; }
                n=$((10#$2))
                case $1 in
                    --width) ((n>=24 && n<=240)) || return 2; WIDTH_OVERRIDE=$n ;;
                    --rows) ((n>=8 && n<=200)) || return 2; ROWS_OVERRIDE=$n ;;
                    --top) ((n>=1 && n<=10)) || return 2; TOP_N=$n; IO_TOP_N=$n ;;
                    --sessions) ((n>=1 && n<=30)) || return 2; MAX_SESSIONS=$n ;;
                    --connections) ((n>=1 && n<=30)) || return 2; MAX_CONNECTIONS=$n ;;
                esac; shift 2 ;;
            --theme)
                found=0
                for candidate in "${THEME_NAMES[@]}"; do [[ ${2-} != "$candidate" ]] || found=1; done
                ((found)) || { usage >&2; return 2; }
                THEME_OVERRIDE=$2; shift 2 ;;
            --sections|--hide|--show)
                (($#>=2)) || return 2
                ui_set_sections "$1" "$2" || return 2; shift 2 ;;
            --hide-item|--show-item)
                (($#>=2)) || return 2
                ui_set_items "$1" "$2" || return 2; shift 2 ;;
            --list-sections)
                ui_registry_init || return 2; ui_section_list; return 3 ;;
            --list-items)
                ui_registry_init || return 2; ui_item_list; return 3 ;;
            --help|-h) usage; return 3 ;;
            --version) printf '%s\n' "$VERSION"; return 3 ;;
            *) usage >&2; return 2 ;;
        esac
    done
    [[ -z $ROWS_OVERRIDE ]] || COMPACT_ROWS=$ROWS_OVERRIDE
}
safe_text() {
    # External names may contain terminal escapes. Render printable ASCII only;
    # never modify raw paths used as command arguments. Fixed cap bounds rendering.
    local LC_ALL=C value=${1:0:1024}
    REPLY=${value//[! -~]/?}
}
collect_display_context() {
    local cols=$WIDTH_OVERRIDE rows='' size=$TTY_SIZE_OVERRIDE language=${LC_ALL:-${LC_CTYPE:-${LANG:-C.UTF-8}}}
    MODEL[color]=1; MODEL[unicode]=0
    [[ $COLOR_MODE != never ]] || ((FORCE_COLOR)) || PLAIN=1
    ((PLAIN)) || [[ ! -v NO_COLOR ]] || PLAIN=1
    [[ ${TERM-} != dumb ]] || PLAIN=1
    [[ -z $THEME_OVERRIDE ]] || THEME=$THEME_OVERRIDE
    (( ! PLAIN )) && [[ $THEME != mono ]] || MODEL[color]=0
    # Reuse an active UTF-8 locale; do not spawn two locale probes per login.
    if ((!ASCII)) && [[ $language == *UTF-8* || $language == *utf8* || $language == *utf-8* ]]; then
        export LC_ALL=$language 2>/dev/null
        local unicode_probe='═'
        if ((${#unicode_probe}==1)); then MODEL[unicode]=1; else export LC_ALL=C; fi
    else export LC_ALL=C; fi
    if [[ -z $size && -t 1 ]]; then size=$( { stty size </dev/tty; } 2>/dev/null); fi
    if [[ $size =~ ^([0-9]{1,3})[[:space:]]+([0-9]{1,3})$ ]]; then
        rows=$((10#${BASH_REMATCH[1]})); [[ -n $cols ]] || cols=${BASH_REMATCH[2]}
    fi
    [[ $cols =~ ^[0-9]{1,3}$ ]] || cols=80
    cols=$((10#$cols)); ((cols>=24)) || cols=24
    if [[ -z $ROWS_OVERRIDE && $rows =~ ^[0-9]+$ ]] && ((rows>=8 && rows<COMPACT_ROWS)); then COMPACT_ROWS=$rows; fi
    MODEL[terminal_rows]=${rows:-$COMPACT_ROWS}
    MODEL[terminal_columns]=$cols; MODEL[columns]=$((cols<MAX_WIDTH ? cols : MAX_WIDTH))
    MODEL[fastfetch_enabled]=${FETCH_OVERRIDE:-$MOTD_FASTFETCH}
}
collect_fastfetch() {
    FASTFETCH_TEXT=''
    ((!DEMO && MODEL[fastfetch_enabled] && MODEL[terminal_columns]>=76)) || return 0
    command -v fastfetch >/dev/null 2>&1 || return 0
    local pipe=true
    (( ! MODEL[color] )) || pipe=false
    FASTFETCH_TEXT=$(run_bounded "$FASTFETCH_TIMEOUT" fastfetch --pipe "$pipe" 2>/dev/null) || FASTFETCH_TEXT=''
}
read_config_value() {
    # os-release values are data: no eval, source, or shell expansion.
    REPLY=$1
    if [[ $REPLY == \"*\" || $REPLY == \'*\' ]]; then REPLY=${REPLY:1:${#REPLY}-2}; fi
    safe_text "$REPLY"
}
collect_identity() {
    local key value line iface family address rest output rc=0 search='' hostdomain=''
    MODEL[host]=Unknown; MODEL[os]=Linux; MODEL[kernel]=Unknown
    MODEL[domain]='not configured locally'; MODEL[domain_source]='local config'
    HOST_IPS=(); MODEL[ip_state]=unavailable
    if [[ -r $PROC_ROOT/sys/kernel/hostname ]]; then read -r value <"$PROC_ROOT/sys/kernel/hostname"; safe_text "$value"; MODEL[host]=$REPLY; fi
    if [[ -r $PROC_ROOT/sys/kernel/osrelease ]]; then read -r value <"$PROC_ROOT/sys/kernel/osrelease"; safe_text "$value"; MODEL[kernel]=$REPLY; fi
    if [[ -r $ETC_ROOT/os-release ]]; then
        while IFS='=' read -r key value; do
            [[ $key == PRETTY_NAME ]] || continue
            read_config_value "$value"; MODEL[os]=$REPLY; break
        done <"$ETC_ROOT/os-release"
    fi
    if [[ ${MODEL[host]} == *.* ]]; then hostdomain=${MODEL[host]#*.}; fi
    if [[ -r $ETC_ROOT/resolv.conf ]]; then
        while read -r key value rest; do
            case $key in domain|search) [[ -z $value ]] || search=$value ;; esac
        done <"$ETC_ROOT/resolv.conf"
    fi
    if [[ -n $DOMAIN_OVERRIDE ]]; then MODEL[domain]=$DOMAIN_OVERRIDE; MODEL[domain_source]=configured
    elif [[ -n $hostdomain ]]; then MODEL[domain]=$hostdomain; MODEL[domain_source]='hostname suffix'
    elif [[ -n $search && $search != '~.' ]]; then MODEL[domain]=$search; MODEL[domain_source]='DNS search'
    fi
    safe_text "${MODEL[domain]}"; MODEL[domain]=$REPLY
    if (( ! LOCAL_ONLY )) && command -v ip >/dev/null 2>&1; then
        output=$(run_bounded "$IDENTITY_TIMEOUT" ip -o address show scope global 2>/dev/null) || rc=$?
        if ((rc==0)); then
            MODEL[ip_state]=ok
            while read -r key iface family address rest; do
                [[ $family == inet || $family == inet6 ]] || continue
                [[ -n $address ]] || continue
                safe_text "$iface $address"; HOST_IPS+=("$REPLY")
            done <<<"$output"
        fi
    fi
    printf -v 'MODEL[sampled]' '%(%Y-%m-%d %H:%M:%S %Z)T' -1
}
collect_health() {
    local key value rest line scope avg10 attr total cpu=0 up='' dev mask
    HEALTH_NOTES=(); MODEL[cpus]='?'; MODEL[uptime]='?'
    MODEL[load1]='?'; MODEL[load5]='?'; MODEL[load15]='?'
    if [[ -r $PROC_ROOT/loadavg ]]; then
        read -r 'MODEL[load1]' 'MODEL[load5]' 'MODEL[load15]' rest <"$PROC_ROOT/loadavg"
        for key in load1 load5 load15; do
            [[ ${MODEL[$key]} =~ ^[0-9]+([.][0-9]+)?$ ]] || MODEL[$key]='?'
        done
    fi
    # The online range list is the same host-online CPU scope as /proc/stat.
    # Count ranges arithmetically instead of scanning one line per logical CPU.
    local online='' range first last previous=-1 online_valid=1
    local -a cpu_ranges=()
    if { read -r online <"$SYS_ROOT/devices/system/cpu/online"; } 2>/dev/null && [[ -n $online ]]; then
        IFS=, read -r -a cpu_ranges <<<"$online"
        [[ $online != ,* && $online != *, && $online != *,,* ]] || online_valid=0
        for range in "${cpu_ranges[@]}"; do
            first=${range%%-*}; last=${range#*-}
            collector_uint "$first" || { online_valid=0; break; }; first=$REPLY
            collector_uint "$last" || { online_valid=0; break; }; last=$REPLY
            ((first<=last && first>previous && last<=2147483647)) || { online_valid=0; break; }
            cpu=$((cpu+last-first+1)); previous=$last
        done
        ((online_valid && cpu>0)) && MODEL[cpus]=$cpu
    fi
    if [[ ${MODEL[cpus]} == '?' && -r $PROC_ROOT/stat ]]; then
        cpu=0
        while read -r key rest; do
            case $key in
                cpu) ;;
                cpu[0-9]*) collector_uint "${key#cpu}" && ((cpu+=1)) ;;
                *) ((cpu==0)) || break ;;
            esac
        done <"$PROC_ROOT/stat"
        ((cpu==0)) || MODEL[cpus]=$cpu
    fi
    if [[ -r $PROC_ROOT/uptime ]]; then
        read -r up rest <"$PROC_ROOT/uptime"; up=${up%%.*}
        if collector_uint "$up"; then
            printf -v 'MODEL[uptime]' '%dd %02dh %02dm' "$((up/86400))" "$((up/3600%24))" "$((up/60%60))"
        fi
    fi
    MODEL[oom_kills]=''
    if [[ -r $PROC_ROOT/vmstat ]]; then
        while read -r key value rest; do
            [[ $key == oom_kill ]] || continue
            if collector_uint "$value"; then MODEL[oom_kills]=$REPLY; fi; break
        done <"$PROC_ROOT/vmstat"
    fi
    for key in cpu memory io; do
        MODEL[psi_$key]=''
        [[ -r $PROC_ROOT/pressure/$key ]] || continue
        while read -r scope avg10 rest; do
            [[ $scope == full && $key != cpu || $scope == some && $key == cpu ]] || continue
            value=${avg10#avg10=}
            [[ $value =~ ^[0-9]{1,3}\.[0-9]{2}$ ]] || continue
            MODEL[psi_$key]=$value; break
        done <"$PROC_ROOT/pressure/$key"
    done
    MODEL[reboot_marker]=0
    [[ ! -e $RUN_ROOT/reboot-required && ! -e $RUN_ROOT/reboot-needed ]] || MODEL[reboot_marker]=1
    MODEL[md_degraded]=0
    if [[ -r $PROC_ROOT/mdstat ]]; then
        dev=''
        while IFS= read -r line; do
            if [[ $line =~ ^(md[^[:space:]]+)[[:space:]]*: ]]; then dev=${BASH_REMATCH[1]}; fi
            if [[ $line =~ \[([U_]+)\] ]]; then
                mask=${BASH_REMATCH[1]}
                if [[ $mask == *_* ]]; then
                    MODEL[md_degraded]=$((MODEL[md_degraded]+1))
                    safe_text "$dev"; HEALTH_NOTES+=("ERROR|MD RAID $REPLY reports missing members ($mask). Check /proc/mdstat.")
                fi
            fi
        done <"$PROC_ROOT/mdstat"
    fi
    MODEL[root_readonly]=0
    if [[ -r $PROC_ROOT/self/mountinfo ]]; then
        while read -r _ _ _ _ value rest; do
            [[ $value == / ]] || continue
            read -r value rest <<<"$rest"
            case ,$value, in *,ro,*) MODEL[root_readonly]=1 ;; *) MODEL[root_readonly]=0 ;; esac
        done <"$PROC_ROOT/self/mountinfo"
    fi
}
collect_journal() {
    MODEL[journal_state]=off; MODEL[journal_count]=0; MODEL[journal_capped]=0
    ((SHOW_JOURNAL)) || return 0
    MODEL[journal_state]=unavailable
    command -v journalctl >/dev/null 2>&1 || return 0
    local output rc=0 key value count=0
    # Metadata only: no log message bodies in a potentially shared PAM MOTD cache.
    output=$(run_bounded "$JOURNAL_TIMEOUT" journalctl --system --boot \
        --since="-$JOURNAL_WINDOW" --priority=err --lines="$((JOURNAL_LIMIT+1))" \
        --output=export --output-fields=PRIORITY --no-pager --quiet 2>/dev/null) || rc=$?
    ((rc==0)) || { [[ $rc != 124 && $rc != 137 ]] || MODEL[journal_state]=timeout; return 0; }
    MODEL[journal_state]=ok
    while IFS='=' read -r key value; do [[ $key != __CURSOR ]] || ((count+=1)); done <<<"$output"
    MODEL[journal_count]=$count
    ((count<=JOURNAL_LIMIT)) || MODEL[journal_capped]=1
}
prepare_view() {
    local key id code theme_key i=0
    local -a disk_palette=("${DISK_COLOR_CODES[@]}")
    # An empty customization still gets a usable local colour; keep its config.
    ((${#disk_palette[@]})) || disk_palette=(37)
    # A declaration without assignment preserves a configured associative map.
    # Resolve into COLOR; never mutate the base palette while selecting a theme.
    declare -gA THEME_COLOR_CODE
    RST=''; COLOR=()
    (( ! MODEL[color] )) || RST=$'\033[0m'
    for key in "${!COLOR_CODE[@]}"; do
        code=${COLOR_CODE[$key]}; theme_key="$THEME.$key"
        [[ $THEME != amber || $key != border ]] || code=33
        code=${THEME_COLOR_CODE[$theme_key]-$code}
        COLOR[$key]=''
        if ((MODEL[color])) && [[ -n $code ]]; then COLOR[$key]=$'\033['${code}m; fi
    done
    COLS=${MODEL[columns]}; INNER=$((COLS-2)); TEXT_WIDTH=$((INNER-2))
    BORDER=${COLOR[border]}
    H='═'; V='║'; TL='╔'; TR='╗'; BL='╚'; BR='╝'; LEFT='╠'; RIGHT='╣'
    GLYPH_USED='█'; GLYPH_FREE='░'
    if ((!MODEL[unicode])); then H='='; V='|'; TL='+'; TR='+'; BL='+'; BR='+'; LEFT='+'; RIGHT='+'; GLYPH_USED='#'; GLYPH_FREE='.'; fi
    repeat_char "$H" "$INNER"; RULE_FULL=$REPLY
    for key in mem_total mem_used mem_available mem_free mem_cache mem_compressed mem_other \
               swap_total swap_used swap_free swap_zram_used swap_other_used \
               zram_pool_kib zram_original_kib zswap_pool_kib zswap_original_kib; do
        format_number "${MODEL[$key]-}"; VIEW[$key]=$REPLY
    done
    VIEW[mem_percent]='?'
    if ((MODEL[mem_valid])); then printf -v 'VIEW[mem_percent]' '%d.%d' "$((MODEL[mem_tenths]/10))" "$((MODEL[mem_tenths]%10))"; fi
    for id in "${DISK_IDS[@]}"; do
        code=${disk_palette[i%${#disk_palette[@]}]}; VIEW[$id.color]=''
        (( ! MODEL[color] )) || VIEW[$id.color]=$'\033['${code}m
        human_kib "${DISK[$id.used_kib]}"; VIEW[$id.used]=$REPLY
        safe_text "${DISK[$id.target]}"; VIEW[$id.target]=$REPLY
        ((i+=1))
    done
    for key in storage_total storage_used storage_avail storage_reserved; do human_kib "${MODEL[$key]}"; VIEW[$key]=$REPLY; done
    prepare_attention
}
prepare_attention() {
    local key id percent denom entry level message count info='' shown=0
    ATTENTION=()
    service_attention
    for entry in "${HEALTH_NOTES[@]}"; do ATTENTION+=("$entry"); done
    if ((MODEL[mem_valid])); then
        if ((MODEL[mem_tenths]>=RAM_CRITICAL*10)); then ATTENTION+=("ERROR|Available RAM ${VIEW[mem_available]}; investigate top RSS processes.")
        elif ((MODEL[mem_tenths]>=RAM_WARN*10)); then ATTENTION+=("WARN|Available RAM ${VIEW[mem_available]}; check memory pressure and tasks."); fi
    else ATTENTION+=('INFO|Memory usage unavailable.'); fi
    for id in "${DISK_IDS[@]}"; do
        denom=$((${DISK[$id.used_kib]}+${DISK[$id.avail_kib]})); ((denom>0)) || continue
        percent=$((${DISK[$id.used_kib]}*100/denom))
        if ((percent>=DISK_CRITICAL)); then ATTENTION+=("ERROR|${VIEW[$id.target]}: $percent% usable space used. Inspect with df -h.")
        elif ((percent>=DISK_WARN)); then ATTENTION+=("WARN|${VIEW[$id.target]}: $percent% usable space used. Check free space."); fi
        if [[ ${DISK[$id.inodes_total]-} =~ ^[0-9]+$ && ${DISK[$id.inodes_free]-} =~ ^[0-9]+$ ]] && ((${DISK[$id.inodes_total]}>0)); then
            percent=$((100-100*${DISK[$id.inodes_free]}/${DISK[$id.inodes_total]}))
            if ((percent>=INODE_CRITICAL)); then ATTENTION+=("ERROR|${VIEW[$id.target]}: $percent% inodes used. Inspect with df -i.")
            elif ((percent>=INODE_WARN)); then ATTENTION+=("WARN|${VIEW[$id.target]}: $percent% inodes used. Inspect with df -i."); fi
        fi
    done
    for key in memory io; do
        if [[ ${MODEL[psi_$key]-} =~ ^([0-9]+)\. ]]; then
            percent=$((10#${BASH_REMATCH[1]}))
            ((percent<PSI_WARN)) || ATTENTION+=("WARN|$key full-stall pressure ${MODEL[psi_$key]}% (10s average); inspect workload.")
        fi
    done
    ((${MODEL[reboot_marker]:-0}==0)) || ATTENTION+=('WARN|OS reboot marker present. Review and schedule a restart.')
    ((${MODEL[oom_kills]:-0}==0)) || ATTENTION+=("WARN|Kernel recorded ${MODEL[oom_kills]} OOM-kill event(s) since boot; review kernel logs.")
    ((${MODEL[root_readonly]:-0}==0)) || ATTENTION+=('INFO|Root is mounted read-only; verify this is intended.')
    case ${MODEL[storage_state]-unavailable} in
        ok) ;;
        partial) ATTENTION+=('INFO|Storage aggregate incomplete; available filesystem details shown.') ;;
        *) ATTENTION+=("INFO|Storage statistics ${MODEL[storage_state]:-unavailable}.") ;;
    esac
    activity_attention
    io_attention
    if ((${MODEL[budget_limited]:-0})); then
        ATTENTION+=('INFO|Collection budget reached; omitted measurements remain unknown.')
    fi
    if ((${MODEL[deadline_fallback]:-0})); then
        ATTENTION+=('WARN|Full display unavailable (deadline or helper failure); fresh local counters only.')
    fi
    if ((SHOW_JOURNAL)); then
        if [[ ${MODEL[journal_state]} == ok ]]; then
            count=${MODEL[journal_count]}
            if ((count>0)); then
                ((MODEL[journal_capped]==0)) || count="$JOURNAL_LIMIT+"
                ATTENTION+=("WARN|$count visible system journal error(s) in the last $JOURNAL_WINDOW; review journalctl -b -p err.")
            fi
        else ATTENTION+=("INFO|System journal summary ${MODEL[journal_state]}; log access may be restricted."); fi
    fi
    for entry in "${MESSAGES[@]}"; do
        IFS='|' read -r level message <<<"$entry"; safe_text "$message"
        case $level in ERROR|WARN|INFO) ;; *) level=INFO ;; esac
        ATTENTION+=("$level|$REPLY")
    done
    # Errors first, then warnings, then information. This avoids hiding urgent
    # findings behind missing optional tools when MAX_ATTENTION limits the view.
    local -a ordered=()
    for level in ERROR WARN INFO; do
        for entry in "${ATTENTION[@]}"; do [[ $entry == "$level|"* ]] && ordered+=("$entry"); done
    done
    ATTENTION=("${ordered[@]}")
}


collect_all() {
    collect_display_context
    budget_start
    if ((DEMO)); then
        demo_model; demo_services; demo_activity; demo_io
        # Keep the example workload and shared-account sessions internally consistent.
        ACT_LOCAL_USER[1000]=workshop; ACT_PROC[2418.name]=badblocks
        ACT_SESSION_IDS=(0 1 2 3)
        for demo_i in 0 1 2 3; do
            ACT_SESSION[$demo_i.Name]=workshop; ACT_SESSION[$demo_i.User]=1000
            ACT_SESSION[$demo_i.Id]=c$((11+demo_i)); ACT_SESSION[$demo_i.State]=online
            ACT_SESSION[$demo_i.Kind]=SSH
        done
        ACT_SESSION[0.TTY]=pts/0; ACT_SESSION[0.RemoteHost]=192.0.2.24
        ACT_SESSION[1.TTY]=pts/1; ACT_SESSION[1.Display]=''; ACT_SESSION[1.RemoteHost]=192.0.2.41
        ACT_SESSION[2.TTY]=''; ACT_SESSION[2.Display]=:10; ACT_SESSION[2.Kind]=RDP; ACT_SESSION[2.RemoteHost]=192.0.2.58
        ACT_SESSION[3.TTY]=tty2; ACT_SESSION[3.Kind]=TTY; ACT_SESSION[3.RemoteHost]=''
        MODEL[session_users]=1; MODEL[session_count]=4; MODEL[session_records]=4; MODEL[session_parsed]=4
        MODEL[tcp_admin]=3
        ACT_CONN[1.local]=192.0.2.17:22; ACT_CONN[1.label]=SSH
        ACT_CONN[2.local]=192.0.2.17:3389; ACT_CONN[2.peer]=192.0.2.58:55001; ACT_CONN[2.label]=RDP
        if [[ $SERVICES_MODE == all ]]; then MODEL[services_scope]=full
        else MODEL[services_scope]=runtime; fi
        ((SHOW_JOURNAL)) || MODEL[journal_state]=skipped
    else
        initialize_optional_model
        if (( ${WORKSHOP_BUDGET_FALLBACK:-0} )); then
            LOCAL_ONLY=1; SHOW_JOURNAL=0
            collect_identity; collect_health; collect_memory; collect_swap; collect_zram; collect_zswap
            MODEL[budget_limited]=1; MODEL[deadline_fallback]=1
        else
            io_begin
            collect_identity; collect_health; collect_memory; collect_swap; collect_zram; collect_zswap
            if budget_allow; then collect_storage; fi
            if budget_allow; then
                if [[ $SERVICES_MODE == all ]]; then collect_services; MODEL[services_scope]=full
                else collect_services_fast; fi
            fi
            if budget_allow; then collect_processes; fi
            if budget_allow; then collect_sessions; fi
            if budget_allow; then collect_connections; fi
            io_finish
            if ((SHOW_JOURNAL)) && budget_allow; then collect_journal; fi
        fi
    fi
    derive_model
}
main() {
    export PATH=/usr/sbin:/usr/bin:/sbin:/bin
    export SYSTEMD_PAGER=cat SYSTEMD_COLORS=0 SYSTEMD_URLIFY=0 SYSTEMD_PAGERSECURE=1 SYSTEMD_ASK_PASSWORD_AGENT=0
    local rc=0
    parse_options "$@" || rc=$?
    ((rc!=3)) || return 0; ((rc==0)) || return "$rc"
    if ! ui_registry_init; then
        printf '%s\n' 'Invalid section registry or display configuration; inspect SETTINGS.' >&2
        return 2
    fi
    ((VALIDATE_ONLY==0)) || return 0
    collect_all; prepare_view
    render_adaptive || return $?
    printf '%s' "$OUTPUT"
    ((WORKER==0)) || printf '%s\n' '__WORKSHOP_COMPLETE_V2__'
}

# ===================== 3. RESOURCE COLLECTION ================================
run_bounded() {
    command -v timeout >/dev/null 2>&1 || return 127
    local duration=$1 limit remain number
    shift
    if [[ $MODE == concise ]]; then
        budget_remaining || return 125
        remain=$REPLY; limit=$CONCISE_HELPER_MAX_MS
        ((limit<=remain)) || limit=$remain
        ((limit>0)) || return 125
        printf -v duration '%d.%03ds' "$((limit/1000))" "$((limit%1000))"
        LC_ALL=C timeout --kill-after=0.02s "$duration" "$@" </dev/null
    else LC_ALL=C timeout --kill-after=0.2s "$duration" "$@" </dev/null; fi
}

collector_uint() {
    # Bounded ASCII digits keep signed arithmetic safe without regex compilation.
    [[ -n $1 && ${#1} -le 15 && $1 != *[!0123456789]* ]] || return 1
    REPLY=$((10#$1))
}

mount_unescape() {
    REPLY=${1//\\040/ }; REPLY=${REPLY//\\011/$'\t'}
    REPLY=${REPLY//\\012/$'\n'}; REPLY=${REPLY//\\134/\\}
}

collect_memory() {
    local key value unit field
    local -A names=([MemTotal]=mem_total [MemFree]=mem_free
        [MemAvailable]=mem_available [Buffers]=mem_buffers [Cached]=mem_cached
        [Shmem]=mem_shmem [SReclaimable]=mem_sreclaimable
        [SwapTotal]=swap_total [SwapFree]=swap_free
        [Zswap]=zswap_pool_kib [Zswapped]=zswap_original_kib)
    for field in "${names[@]}"; do MODEL[$field]=''; done
    MODEL[meminfo_state]=unavailable
    [[ -r $PROC_ROOT/meminfo ]] || return 0
    while read -r key value unit; do
        [[ -n $key ]] || continue
        key=${key%:}; field=${names[$key]-}
        [[ -n $field && $unit == kB ]] || continue
        if collector_uint "$value"; then MODEL[$field]=$REPLY; fi
    done 2>/dev/null <"$PROC_ROOT/meminfo"
    MODEL[meminfo_state]=ok
    for field in mem_total mem_free mem_available mem_buffers mem_cached mem_shmem mem_sreclaimable swap_total swap_free; do
        [[ -n ${MODEL[$field]} ]] || MODEL[meminfo_state]=partial
    done
}

collect_zswap() {
    local value='' enabled_file=$SYS_ROOT/module/zswap/parameters/enabled
    MODEL[zswap_enabled]=''; MODEL[zswap_state]=unavailable; MODEL[zswap_present]=1
    if [[ -r $enabled_file ]]; then
        read -r value 2>/dev/null <"$enabled_file" || :
        case $value in Y|y|1) MODEL[zswap_enabled]=1 ;; N|n|0) MODEL[zswap_enabled]=0 ;; esac
    fi
    if [[ -n ${MODEL[zswap_pool_kib]-} && -n ${MODEL[zswap_original_kib]-} ]]; then
        MODEL[zswap_state]=ok
    elif [[ -n ${MODEL[zswap_pool_kib]-} || -n ${MODEL[zswap_original_kib]-} ]]; then
        MODEL[zswap_state]=partial
    elif [[ ! -e $enabled_file ]]; then
        # No exposed interface is treated as absent, not proof of kernel configuration.
        MODEL[zswap_state]=absent; MODEL[zswap_present]=0
    fi
    # Disabled does not mean empty. Unreadable/missing counters stay unknown.
}

collect_swap() {
    local path type size used priority extra total=0 occupied=0
    MODEL[swap_devices_state]=unavailable; MODEL[swap_state]=unavailable
    MODEL[swap_snapshot_mismatch]=0
    MODEL[swap_zram_used]=''; MODEL[swap_other_used]=''
    MODEL[swap_zram_total]=''; MODEL[swap_other_total]=''
    [[ -r $PROC_ROOT/swaps ]] || return 0
    MODEL[swap_devices_state]=ok
    MODEL[swap_zram_used]=0; MODEL[swap_other_used]=0
    MODEL[swap_zram_total]=0; MODEL[swap_other_total]=0
    while read -r path type size used priority extra; do
        [[ $path == Filename ]] && continue
        if ! collector_uint "$size"; then MODEL[swap_devices_state]=partial; continue; fi
        size=$REPLY
        if ! collector_uint "$used"; then MODEL[swap_devices_state]=partial; continue; fi
        used=$REPLY
        if ((used > size)); then MODEL[swap_devices_state]=partial; continue; fi
        # /proc/swaps counts occupied swap slots, not zram's stored byte total.
        if [[ $path =~ ^/dev/zram[0-9]+$ ]]; then type=zram; else type=other; fi
        MODEL[swap_${type}_total]=$((MODEL[swap_${type}_total] + size))
        MODEL[swap_${type}_used]=$((MODEL[swap_${type}_used] + used))
        total=$((total + size)); occupied=$((occupied + used))
    done 2>/dev/null <"$PROC_ROOT/swaps"
    if [[ -n ${MODEL[swap_total]-} && -n ${MODEL[swap_free]-} ]] &&
       ((total != MODEL[swap_total] || occupied != MODEL[swap_total] - MODEL[swap_free])); then
        MODEL[swap_snapshot_mismatch]=1
    fi
    MODEL[swap_state]=${MODEL[swap_devices_state]}
    ((MODEL[swap_snapshot_mismatch] == 0)) || MODEL[swap_state]=partial
}

collect_zram() {
    local dir original compressed pool rest backing count=0 valid=0
    local original_sum=0 compressed_sum=0 pool_sum=0
    MODEL[zram_state]=unavailable; MODEL[zram_partial]=0
    MODEL[zram_pool_kib]=''; MODEL[zram_original_kib]=''; MODEL[zram_compressed_kib]=''
    MODEL[zram_count]=0; MODEL[zram_valid_count]=0
    MODEL[zram_writeback]=0; MODEL[zram_writeback_unknown]=0
    [[ -d $SYS_ROOT/block && -r $SYS_ROOT/block ]] || return 0
    for dir in "$SYS_ROOT"/block/zram[0-9]*; do
        [[ -d $dir ]] || continue
        count=$((count + 1))
        original=''; compressed=''; pool=''
        if [[ -r $dir/mm_stat ]]; then
            read -r original compressed pool rest 2>/dev/null <"$dir/mm_stat" || :
        fi
        if collector_uint "$original"; then original=$REPLY; else original=''; fi
        if collector_uint "$compressed"; then compressed=$REPLY; else compressed=''; fi
        if collector_uint "$pool"; then pool=$REPLY; else pool=''; fi
        if [[ -n $original && -n $compressed && -n $pool ]]; then
            original_sum=$((original_sum + original)); compressed_sum=$((compressed_sum + compressed))
            pool_sum=$((pool_sum + pool)); valid=$((valid + 1))
        else MODEL[zram_partial]=1; fi
        backing=''
        if [[ -r $dir/backing_dev ]]; then read -r backing 2>/dev/null <"$dir/backing_dev" || :; fi
        if [[ $backing == none ]]; then :
        elif [[ -n $backing ]]; then MODEL[zram_writeback]=1
        else MODEL[zram_writeback_unknown]=1; fi
    done
    MODEL[zram_count]=$count; MODEL[zram_valid_count]=$valid
    MODEL[zram_state]=ok
    if ((valid == count)); then
        MODEL[zram_pool_kib]=$((pool_sum / 1024))
        MODEL[zram_original_kib]=$((original_sum / 1024))
        MODEL[zram_compressed_kib]=$((compressed_sum / 1024))
    else MODEL[zram_state]=partial; fi
    # Pool RAM is already part of MemTotal usage; never add it to RAM/swap capacity.
    # Ratios require nonzero denominators and known-disabled writeback.
}

collect_storage() {
    local line before after id parent dev root target options type source rest key index
    local total used avail raw_avail itotal iused ifree output rc=0 skipped=0 shared=0 invalid=0
    local -a order=() targets=() requested=()
    local -A devices=() sources=() types=() seen_dev=() seen_source=() seen_target=()
    DISK=(); DISK_IDS=(); MODEL[storage_state]=unavailable
    MODEL[storage_complete]=0; MODEL[storage_skipped]=0; MODEL[storage_skipped_shared]=0
    MODEL[storage_shared_pool]=0; MODEL[storage_count]=0
    [[ -r $PROC_ROOT/self/mountinfo ]] || return 0
    while IFS= read -r line; do
        [[ $line == *' - '* ]] || continue
        before=${line%%' - '*}; after=${line#*' - '}
        read -r id parent dev root target options rest <<<"$before"
        read -r type source rest <<<"$after"
        mount_unescape "$target"; target=$REPLY
        mount_unescape "$source"; source=$REPLY
        [[ -n $target && $target != *[$'\n\r\t']* ]] || continue
        [[ ${devices[$target]+set} ]] || order+=("$target")
        devices[$target]=$dev; sources[$target]=$source; types[$target]=$type
    done 2>/dev/null <"$PROC_ROOT/self/mountinfo"
    if ((${#STORAGE_MOUNTS[@]})); then requested=("${STORAGE_MOUNTS[@]}")
    else requested=("${order[@]}"); fi
    for target in "${requested[@]}"; do
        if [[ -z $target || ! ${devices[$target]+set} ]]; then skipped=$((skipped + 1)); continue; fi
        dev=${devices[$target]}; source=${sources[$target]}; type=${types[$target]}
        case $type in
            zfs) shared=$((shared + 1)); continue ;;
            btrfs) if ((${#STORAGE_MOUNTS[@]} == 0)); then shared=$((shared + 1)); continue; fi
                   MODEL[storage_shared_pool]=1 ;;
            tmpfs|devtmpfs|overlay|squashfs|ramfs|proc|sysfs|cgroup*|autofs|fuse.portal|fuse.gvfsd-fuse) continue ;;
            nfs*|cifs|smb*|9p|ceph|afs|fuse.sshfs|fuse.rclone|fuse.s3fs|fuse.glusterfs|fuse.davfs*)
                ((${#STORAGE_MOUNTS[@]} == 0)) || skipped=$((skipped + 1)); continue ;;
        esac
        [[ $source != /dev/zram* && $source != /dev/loop* && $source != /dev/ram* && $dev != 7:* && $dev != 1:* ]] || continue
        case $type in
            ext2|ext3|ext4|xfs|btrfs|f2fs|vfat|msdos|exfat|ntfs|ntfs3|fuseblk|jfs|reiserfs|bcachefs|ufs) ;;
            *) if [[ $source == /dev/* || $type == fuse.* ]] || ((${#STORAGE_MOUNTS[@]})); then
                   skipped=$((skipped + 1))
               fi
               continue ;;
        esac
        [[ $source == /dev/* ]] || { skipped=$((skipped + 1)); continue; }
        [[ $dev =~ ^[0-9]+:[0-9]+$ && -n $source && $source != none ]] || { skipped=$((skipped + 1)); continue; }
        # Device identity merges bind mounts/aliases. Btrfs sources also merge subvolumes.
        key=$dev
        [[ $type != btrfs || ! ${seen_source[$source]+set} ]] || key=${seen_source[$source]}
        if [[ ${seen_dev[$key]+set} ]]; then
            index=${seen_dev[$key]}
            if ((${#target} < ${#targets[$index]})); then targets[$index]=$target; fi
        else
            seen_dev[$key]=${#targets[@]}; targets+=("$target")
        fi
        [[ $type != btrfs ]] || seen_source[$source]=$key
    done
    # Skipped counters count mount entries, not disks or unique storage pools.
    MODEL[storage_skipped]=$skipped; MODEL[storage_skipped_shared]=$shared
    if ((${#targets[@]} == 0)); then
        MODEL[storage_state]=ok
        ((skipped + shared == 0)) || MODEL[storage_state]=partial
        ((skipped + shared != 0)) || MODEL[storage_complete]=1
        return 0
    fi
    command -v df >/dev/null 2>&1 || return 0
    # Explicit mount targets avoid recursive traversal. --local filters known remote types.
    # Numeric-first output preserves spaces in target paths; no per-mount child processes.
    output=$(run_bounded "${STORAGE_TIMEOUT:-0.5s}" df --local --no-sync --block-size=1024 \
        --output=size,used,avail,itotal,iused,iavail,target -- "${targets[@]}" 2>/dev/null) || rc=$?
    while IFS= read -r line; do
        [[ $line =~ ^[[:space:]]*([0-9]+)[[:space:]]+([0-9]+)[[:space:]]+(-?[0-9]+)[[:space:]]+([0-9-]+)[[:space:]]+([0-9-]+)[[:space:]]+([0-9-]+)[[:space:]]+(.*)$ ]] || continue
        total=${BASH_REMATCH[1]}; used=${BASH_REMATCH[2]}; avail=${BASH_REMATCH[3]}; itotal=${BASH_REMATCH[4]}; iused=${BASH_REMATCH[5]}; ifree=${BASH_REMATCH[6]}; target=${BASH_REMATCH[7]}
        if ! collector_uint "$total"; then invalid=1; continue; fi; total=$REPLY
        if ! collector_uint "$used"; then invalid=1; continue; fi; used=$REPLY
        raw_avail=$avail
        if [[ $avail == -* ]]; then
            if ! collector_uint "${avail#-}"; then invalid=1; continue; fi
            avail=0
        else
            if ! collector_uint "$avail"; then invalid=1; continue; fi; avail=$REPLY
        fi
        if ((total == 0 || used + avail > total)) || [[ ! ${devices[$target]+set} ]]; then invalid=1; continue; fi
        [[ ! ${seen_target[$target]+set} ]] || continue
        seen_target[$target]=1; id=${#DISK_IDS[@]}; DISK_IDS+=("$id")
        DISK[$id.target]=$target; DISK[$id.source]=${sources[$target]}; DISK[$id.fstype]=${types[$target]}
        DISK[$id.total_kib]=$total; DISK[$id.used_kib]=$used; DISK[$id.avail_kib]=$avail
        DISK[$id.reserved_kib]=$((total - used - avail)); DISK[$id.valid]=1
        DISK[$id.raw_avail_kib]=$raw_avail
        DISK[$id.inodes_total]=''; DISK[$id.inodes_free]=''
        if collector_uint "$itotal"; then
            itotal=$REPLY
            if [[ $ifree =~ ^-[0-9]+$ ]] && collector_uint "${ifree#-}"; then ifree=0; fi
            if collector_uint "$ifree" && ((REPLY<=itotal)); then
                DISK[$id.inodes_total]=$itotal; DISK[$id.inodes_free]=$REPLY
            fi
        fi
    done <<<"$output"
    MODEL[storage_count]=${#DISK_IDS[@]}; MODEL[storage_state]=ok
    if ((rc || invalid || skipped || shared || MODEL[storage_shared_pool] || ${#DISK_IDS[@]} != ${#targets[@]})); then
        MODEL[storage_state]=partial
    else MODEL[storage_complete]=1; fi
    if ((rc == 124 || rc == 137)); then MODEL[storage_state]=timeout
    elif ((rc && ! ${#DISK_IDS[@]})); then MODEL[storage_state]=unavailable; fi
}

derive_model() {
    local total=${MODEL[mem_total]:-0} free=${MODEL[mem_free]-} cache comp other
    local id disk_total=0 disk_used=0 disk_avail=0 disk_reserved=0
    MODEL[mem_valid]=0; MODEL[mem_parts_valid]=0; MODEL[swap_valid]=0
    if [[ $total =~ ^[0-9]+$ && ${MODEL[mem_available]-} =~ ^[0-9]+$ ]] &&
        ((total > 0 && MODEL[mem_available] <= total)); then
        MODEL[mem_valid]=1; MODEL[mem_used]=$((total-MODEL[mem_available]))
        MODEL[mem_tenths]=$(((MODEL[mem_used]*1000+total/2)/total))
    fi
    if [[ $free =~ ^[0-9]+$ && ${MODEL[mem_buffers]-} =~ ^[0-9]+$ &&
          ${MODEL[mem_cached]-} =~ ^[0-9]+$ && ${MODEL[mem_shmem]-} =~ ^[0-9]+$ &&
          ${MODEL[mem_sreclaimable]-} =~ ^[0-9]+$ &&
          ${MODEL[zram_state]-} == ok && ( ${MODEL[zswap_state]-} == ok || ${MODEL[zswap_state]-} == absent ) ]] &&
          ((MODEL[mem_cached] >= MODEL[mem_shmem])); then
        cache=$((MODEL[mem_cached]-MODEL[mem_shmem]))
        cache=$((cache+MODEL[mem_buffers]+MODEL[mem_sreclaimable]))
        comp=$((${MODEL[zram_pool_kib]:-0}+${MODEL[zswap_pool_kib]:-0}))
        other=$((total-free-cache-comp))
        if ((total > 0 && other >= 0 && free <= total)); then
            MODEL[mem_parts_valid]=1; MODEL[mem_cache]=$cache
            MODEL[mem_compressed]=$comp; MODEL[mem_other]=$other
        fi
    fi
    if [[ ${MODEL[swap_total]-} =~ ^[0-9]+$ && ${MODEL[swap_free]-} =~ ^[0-9]+$ ]] &&
        ((MODEL[swap_free] <= MODEL[swap_total])); then
        MODEL[swap_valid]=1; MODEL[swap_used]=$((MODEL[swap_total]-MODEL[swap_free]))
    fi
    MODEL[storage_overflow]=0
    for id in "${DISK_IDS[@]}"; do
        if ((${DISK[$id.total_kib]}>900000000000000-disk_total)); then
            MODEL[storage_overflow]=1; MODEL[storage_state]=partial; continue
        fi
        disk_total=$((disk_total+${DISK[$id.total_kib]})); disk_used=$((disk_used+${DISK[$id.used_kib]}))
        disk_avail=$((disk_avail+${DISK[$id.avail_kib]})); disk_reserved=$((disk_reserved+${DISK[$id.reserved_kib]}))
    done
    MODEL[storage_total]=$disk_total; MODEL[storage_used]=$disk_used
    MODEL[storage_avail]=$disk_avail; MODEL[storage_reserved]=$disk_reserved
}

# ===================== 4. SERVICES AND ACTIVITY ==============================

# Runtime state and installation state are independent snapshots. SVC keys are
# "unit.field". An absent runtime record never becomes STOP unless actually read.
declare -A SVC=() SVC_GROUP_MEMBERS=()
SVC_KEYS=() SVC_FAILURES=() SVC_EXTRA=()

svc_add_key() {
    [[ -n ${SVC[$1.seen]-} ]] && return 0
    SVC[$1.seen]=1
    SVC_KEYS+=("$1")
}
svc_excluded() {
    local pattern
    for pattern in "${SERVICE_EXCLUDE_PATTERNS[@]}"; do
        [[ $1 == $pattern ]] && return 0
    done
    return 1
}
svc_group() {
    local u=$1
    REPLY=${SERVICE_GROUP_OVERRIDE[$u]-}
    [[ -z $REPLY ]] || return 0
    case $u in
        ssh.service|sshd.service|ssh.socket|sshd.socket|sshd@*.service|dropbear*|xrdp*|vncserver*|tigervnc*|x11vnc*|wayvnc*|gnome-remote-desktop*|cockpit*|webmin*) REPLY=Access ;;
        vsftpd*|proftpd*|pure-ftpd*|tftpd*|tftp.*|tftp@*|atftpd*|smbd.*|nmbd.*|smb.*|nmb.*|samba.service|nfs-server.*|nfs-kernel-server.*|nfs-mountd.*|rpcbind.*|rsync.*|rsyncd.*) REPLY=Files ;;
        apache2.*|httpd.*|nginx.*|caddy.*|haproxy.*|squid.*|traefik.*) REPLY=Web ;;
        postgresql*|mysql.*|mysqld.*|mariadb.*|redis*|memcached.*|mongod.*|mongodb.*|elasticsearch.*|opensearch.*|influxdb.*|clickhouse*) REPLY=Data ;;
        postfix*|exim*|sendmail*|dovecot*) REPLY=Mail ;;
        NetworkManager.*|systemd-networkd.*|networking.*|wicked*|connman.*|systemd-resolved.*|dnsmasq.*|unbound.*|named.*|bind9.*|dhcpd*|isc-dhcp*|kea-*|openvpn*|wg-quick*|tailscaled.*|zerotier-one.*|strongswan*|charon*) REPLY=Network ;;
        sssd*|winbind.*|realmd.*|krb5-kdc.*|slapd.*|samba-ad-dc.*) REPLY=Identity ;;
        ufw.*|firewalld.*|nftables.*|iptables.*|ip6tables.*|fail2ban.*|apparmor.*|auditd.*) REPLY=Security ;;
        docker.*|containerd.*|podman.*|libvirtd.*|virtqemud.*|virtlogd.*|virtlockd.*|virtnetworkd.*|virtstoraged.*|virtproxyd.*|qemu-guest-agent.*|vmtoolsd.*|vboxservice.*|lxc.*|lxcfs.*|kubelet.*|k3s*) REPLY=Virtual ;;
        chrony.*|chronyd.*|ntp.*|ntpd.*|ntpsec.*|systemd-timesyncd.*) REPLY=Time ;;
        systemd-journald.*|systemd-logind.*|systemd-udevd.*|dbus.*|dbus-broker.*|rsyslog.*|syslog-ng.*|cron.*|crond.*|earlyoom.*|systemd-oomd.*|smartd.*|smartmontools.*|mdmonitor.*|irqbalance.*|zabbix-agent*|prometheus*|node_exporter.*|nagios*|nrpe.*|netdata.*) REPLY=System ;;
        display-manager.*|lightdm.*|gdm.*|gdm3.*|sddm.*|xdm.*|cups.*|cups-browsed.*|bluetooth.*|avahi-daemon.*) REPLY=Local ;;
        *) REPLY='' ;;
    esac
}
svc_parse_runtime() {
    local unit load active sub ignored
    while read -r unit load active sub ignored; do
        [[ -n $unit ]] || continue
        # --plain removes systemctl's bullet; no unit names or descriptions run.
        [[ $unit == *.* && -n $load && -n $active && -n $sub ]] || continue
        safe_text "$unit"; unit=$REPLY
        [[ -n $unit ]] || continue
        svc_add_key "$unit"
        safe_text "$load"; SVC[$unit.load]=$REPLY
        safe_text "$active"; SVC[$unit.active]=$REPLY
        safe_text "$sub"; SVC[$unit.sub]=$REPLY
        SVC[$unit.runtime]=1
    done <<<"$1"
}
svc_parse_files() {
    local unit state preset ignored
    while read -r unit state preset ignored; do
        [[ -n $unit ]] || continue
        case $unit in *.service|*.socket|*.timer) ;; *) continue ;; esac
        [[ -n $state ]] || continue
        safe_text "$unit"; unit=$REPLY
        [[ -n $unit ]] || continue
        svc_add_key "$unit"
        safe_text "$state"; SVC[$unit.file]=$REPLY
        # The optional PRESET column is policy, not current enablement; ignore it.
    done <<<"$1"
}
svc_finalize() {
    local unit group active load
    SVC_FAILURES=(); SVC_EXTRA=(); SVC_GROUP_MEMBERS=()
    MODEL[svc_loaded]=0; MODEL[svc_running]=0; MODEL[svc_installed]=0
    MODEL[svc_failed]=0; MODEL[svc_aliases]=0
    for unit in "${SVC_KEYS[@]}"; do
        svc_excluded "$unit" && continue
        active=${SVC[$unit.active]-}; load=${SVC[$unit.load]-}
        if [[ $active == failed || $load == error || $load == bad-setting || ${SVC[$unit.file]-} == bad ]]; then
            SVC_FAILURES+=("$unit"); ((MODEL[svc_failed]+=1))
        fi
        case $unit in *.service|*.socket|*.timer) ;; *) continue ;; esac
        [[ $load != loaded ]] || ((MODEL[svc_loaded]+=1))
        [[ -z ${SVC[$unit.file]-} ]] || ((MODEL[svc_installed]+=1))
        [[ $active != active || ${SVC[$unit.sub]-} != running ]] || ((MODEL[svc_running]+=1))
        if [[ ${SVC[$unit.file]-} == alias && -z ${SVC[$unit.runtime]-} ]]; then
            ((MODEL[svc_aliases]+=1)); continue
        fi
        svc_group "$unit"; group=$REPLY
        # Template files are available definitions, not stopped instances.
        if [[ $unit == *@.service || $unit == *@.socket || $unit == *@.timer ]]; then continue; fi
        if [[ -n $group ]]; then
            SVC_GROUP_MEMBERS[$group]+="$unit"$'\n'
        else
            case $active in active|reloading|activating|deactivating|failed|maintenance) SVC_EXTRA+=("$unit") ;; esac
        fi
    done
}
collect_services() {
    local output rc
    SVC=(); SVC_KEYS=(); SVC_FAILURES=(); SVC_EXTRA=(); SVC_GROUP_MEMBERS=()
    MODEL[services_state]=unavailable
    MODEL[svc_runtime_state]=unavailable; MODEL[svc_files_state]=unavailable
    if ! command -v systemctl >/dev/null 2>&1; then svc_finalize; return 0; fi
    # Includes every unit type so a failed mount/swap is not lost in Attention.
    if output=$(LC_ALL=C SYSTEMD_COLORS=0 SYSTEMD_URLIFY=0 \
        run_bounded "$SERVICE_TIMEOUT" systemctl --no-ask-password --no-pager \
        --no-legend --plain --full list-units --all 2>/dev/null); then
        MODEL[svc_runtime_state]=ok; svc_parse_runtime "$output"
    else
        rc=$?; [[ $rc != 124 && $rc != 137 ]] || MODEL[svc_runtime_state]=timeout
    fi
    if output=$(LC_ALL=C SYSTEMD_COLORS=0 SYSTEMD_URLIFY=0 \
        run_bounded "$SERVICE_TIMEOUT" systemctl --no-ask-password --no-pager \
        --no-legend --full list-unit-files --type=service,socket,timer 2>/dev/null); then
        MODEL[svc_files_state]=ok; svc_parse_files "$output"
    else
        rc=$?; [[ $rc != 124 && $rc != 137 ]] || MODEL[svc_files_state]=timeout
    fi
    if [[ ${MODEL[svc_runtime_state]} == ok && ${MODEL[svc_files_state]} == ok ]]; then MODEL[services_state]=ok
    elif [[ ${MODEL[svc_runtime_state]} == ok || ${MODEL[svc_files_state]} == ok ]]; then MODEL[services_state]=partial
    elif [[ ${MODEL[svc_runtime_state]} == timeout || ${MODEL[svc_files_state]} == timeout ]]; then MODEL[services_state]=timeout; fi
    svc_finalize
}

# Both terse and full views preserve separate runtime, load and boot information.
# The compact suffix is an installation flag, never a claim about running state.
svc_state() {
    local unit=$1 active=${SVC[$1.active]-} sub=${SVC[$1.sub]-}
    local load=${SVC[$1.load]-} file=${SVC[$1.file]-}
    SVC_COLOR=${COLOR[muted]}; REPLY='?'
    if [[ $active == failed || $load == bad-setting || $load == error || $file == bad ]]; then
        REPLY=FAIL; SVC_COLOR=${COLOR[error]}
    elif [[ -n ${SVC[$unit.runtime]-} ]]; then
        case $active/$sub in
            active/running) REPLY=RUN; SVC_COLOR=${COLOR[ok]} ;;
            active/exited) REPLY=DONE; SVC_COLOR=${COLOR[ok]} ;;
            active/listening) REPLY=LISTEN; SVC_COLOR=${COLOR[ok]} ;;
            active/waiting) REPLY=WAIT; SVC_COLOR=${COLOR[ok]} ;;
            reloading/*) REPLY=RELOAD; SVC_COLOR=${COLOR[ok]} ;;
            activating/*) REPLY=START; SVC_COLOR=${COLOR[warn]} ;;
            deactivating/*) REPLY=STOPPING; SVC_COLOR=${COLOR[warn]} ;;
            maintenance/*) REPLY=MAINT; SVC_COLOR=${COLOR[warn]} ;;
            active/*) REPLY=ACTIVE; SVC_COLOR=${COLOR[ok]} ;;
            inactive/*)
                if [[ $load == masked || $file == masked* ]]; then REPLY=MASK
                elif [[ $load == not-found ]]; then REPLY=N/A
                else REPLY=STOP; fi ;;
        esac
    elif [[ $unit == *@.service || $unit == *@.socket || $unit == *@.timer ]]; then REPLY=TEMPLATE
    elif [[ $file == alias ]]; then REPLY=ALIAS
    elif [[ $file == masked* ]]; then REPLY=MASK
    elif [[ ${MODEL[svc_runtime_state]-} == ok && -n $file ]]; then REPLY=UNLOADED
    fi
}
svc_file_flag() {
    case ${SVC[$1.file]-} in
        enabled) REPLY=e ;; enabled-runtime) REPLY=er ;;
        disabled) REPLY=d ;; static) REPLY=s ;;
        masked) REPLY=m ;; masked-runtime) REPLY=mr ;;
        generated) REPLY=g ;; transient) REPLY=t ;; alias) REPLY=a ;;
        linked) REPLY=l ;; linked-runtime) REPLY=lr ;; indirect) REPLY=i ;;
        bad) REPLY=b ;; *) REPLY='?' ;;
    esac
}


service_attention() {
    local unit count=0 total=${#SVC_FAILURES[@]} quoted_unit
    case ${MODEL[services_state]-unavailable} in
        ok) ;;
        partial) ATTENTION+=('INFO|Service inventory is partial; some runtime/installation states are unknown.') ;;
        timeout) ATTENTION+=('INFO|Service inventory timed out; states are unknown.') ;;
        *) ATTENTION+=('INFO|Systemd service inventory unavailable on this system.') ;;
    esac
    for unit in "${SVC_FAILURES[@]}"; do
        ((count < SERVICE_ALERT_LIMIT)) || break
        safe_text "$unit"; printf -v quoted_unit '%q' "$REPLY"
        ATTENTION+=("ERROR|Unit needs review: systemctl status -- $quoted_unit")
        ((count+=1))
    done
    if ((total > count)); then ATTENTION+=("ERROR|$((total-count)) additional failed/bad units; run systemctl --failed."); fi
    for unit in "${REQUIRED_UNITS[@]}"; do
        safe_text "$unit"; unit=$REPLY
        if [[ ${MODEL[svc_runtime_state]-} != ok ]]; then
            ATTENTION+=("INFO|Required unit cannot be checked: $unit")
        elif [[ ${SVC[$unit.active]-} != active && ${SVC[$unit.active]-} != reloading ]]; then
            # Alias listings do not resolve canonical runtime state: say unknown.
            if [[ ${SVC[$unit.file]-} == alias ]]; then
                ATTENTION+=("INFO|Required alias needs a canonical unit name: $unit")
            else
                ATTENTION+=("WARN|Required unit is not recorded active: $unit")
            fi
        fi
    done
}
demo_services() {
    SVC=(); SVC_KEYS=(); SVC_FAILURES=(); SVC_EXTRA=(); SVC_GROUP_MEMBERS=()
    MODEL[services_state]=ok; MODEL[svc_runtime_state]=ok; MODEL[svc_files_state]=ok
    svc_parse_runtime 'ssh.service loaded active running OpenBSD Secure Shell
xrdp.service loaded active running Remote Desktop
xrdp-sesman.service loaded active running Remote sessions
vsftpd.service loaded inactive dead FTP server
tftpd-hpa.service loaded active running TFTP server
smbd.service loaded active running SMB server
nginx.service loaded active running Web server
mariadb.service loaded active running Database
NetworkManager.service loaded active running Network manager
systemd-resolved.service loaded active running Resolver
sssd.service loaded active running Identity
nftables.service loaded active exited Packet rules
docker.service loaded active running Containers
systemd-journald.service loaded active running Journal
cron.service loaded active running Scheduled jobs
earlyoom.service loaded active running Memory guardian
chrony.service loaded active running Time sync
lightdm.service loaded inactive dead Display manager
cups.socket loaded active listening Print activation
workshop-agent.service loaded active running Workshop agent
apt-daily.timer loaded active waiting Package metadata timer'
    svc_parse_files 'ssh.service enabled enabled
sshd.service alias -
xrdp.service enabled enabled
xrdp-sesman.service enabled enabled
vsftpd.service disabled enabled
tftpd-hpa.service enabled enabled
smbd.service enabled enabled
nginx.service enabled enabled
mariadb.service enabled enabled
NetworkManager.service enabled enabled
systemd-resolved.service enabled enabled
sssd.service enabled enabled
nftables.service enabled disabled
docker.service enabled enabled
systemd-journald.service static -
cron.service enabled enabled
earlyoom.service enabled enabled
chrony.service enabled enabled
lightdm.service disabled enabled
display-manager.service alias -
cups.socket enabled enabled
workshop-agent.service enabled enabled
apt-daily.timer enabled enabled
getty@.service indirect enabled'
    if [[ ${DEMO:-0} == 2 ]]; then
        svc_parse_runtime 'nginx.service loaded failed failed Web server
mnt-backup.mount loaded failed failed Backup volume'
    fi
    svc_finalize
}


declare -A ACT_PROC ACT_SESSION ACT_CONN ACT_LOCAL_USER
declare -a ACT_CPU_IDS ACT_RAM_IDS ACT_SESSION_IDS ACT_CONN_IDS

activity_top_insert() {
    # Fixed-size insertion: O(processes * TOP_N), never sort a full PID table.
    local -n list=$1
    local field=$2 pid=$3 score=$4 i j
    for ((i=0; i<${#list[@]}; i++)); do
        ((score > ${ACT_PROC[${list[i]}.$field]:-0})) && break
    done
    ((i < TOP_N)) || return 0
    for ((j=${#list[@]}; j>i; j--)); do
        ((j < TOP_N)) && list[j]=${list[j-1]}
    done
    list[i]=$pid
}

collect_processes() {
    ACT_PROC=(); ACT_CPU_IDS=(); ACT_RAM_IDS=(); ACT_LOCAL_USER=()
    MODEL[process_state]=unavailable
    MODEL[process_count]=0; MODEL[process_running]=0
    MODEL[process_blocked]=0; MODEL[process_zombies]=0
    local snapshot rc pid uid cpu rss state name integer fraction score bad=0
    snapshot=$(run_bounded "$ACTIVITY_TIMEOUT" ps -eo pid=,euid=,pcpu=,rss=,stat=,comm= -ww 2>/dev/null); rc=$?
    if ((rc != 0)); then
        ((rc == 124 || rc == 137)) && MODEL[process_state]=timeout
        return 0
    fi
    [[ -n $snapshot ]] || return 0
    while read -r pid uid cpu rss state name; do
        [[ -n $pid ]] || continue
        if ! collector_uint "$pid" || ! collector_uint "$uid" || ! collector_uint "$rss" ||
            [[ ! $cpu =~ ^([0-9]{1,9})\.([0-9])$ ]]; then
            ((bad+=1)); continue
        fi
        integer=${BASH_REMATCH[1]}; fraction=${BASH_REMATCH[2]}
        score=$((10#$integer*10+10#$fraction))
        ((MODEL[process_count]+=1))
        case ${state:0:1} in
            R) ((MODEL[process_running]+=1)) ;;
            D) ((MODEL[process_blocked]+=1)) ;;
            Z) ((MODEL[process_zombies]+=1)) ;;
        esac
        # The reporting script and its ps snapshot are not useful workload rows.
        [[ $pid != "$$" && $name != ps ]] || continue
        ACT_PROC[$pid.uid]=$uid; ACT_PROC[$pid.cpu]=$cpu
        ACT_PROC[$pid.score]=$score; ACT_PROC[$pid.rss]=$rss
        safe_text "$name"; ACT_PROC[$pid.name]=$REPLY
        safe_text "$state"; ACT_PROC[$pid.state]=$REPLY
        activity_top_insert ACT_CPU_IDS score "$pid" "$score"
        activity_top_insert ACT_RAM_IDS rss "$pid" "$rss"
    done <<<"$snapshot"
    if ((MODEL[process_count] == 0)); then return 0; fi
    MODEL[process_state]=ok
    ((bad == 0)) || MODEL[process_state]=partial
    # Only local files: do not trigger LDAP/SSSD/NIS lookups for every PID.
    if [[ -r ${ETC_ROOT:-/etc}/passwd ]]; then
        while IFS=: read -r name _ uid _; do
            [[ $uid =~ ^[0-9]+$ ]] || continue
            safe_text "$name"; ACT_LOCAL_USER[$uid]=$REPLY
        done <"${ETC_ROOT:-/etc}/passwd"
    fi
}

activity_session_record() {
    local -n rec=$1
    local sid=${rec[Id]-} uid=${rec[User]-} class=${rec[Class]-}
    local field value kind index name service
    [[ -n $sid && $uid =~ ^[0-9]+$ ]] || return 0
    ((MODEL[session_parsed]+=1))
    case $class in greeter|lock-screen|background*|manager*) return 0 ;; esac
    # Unknown classes remain visible with their explicit type, not discarded.
    index=${#ACT_SESSION_IDS[@]}; ACT_SESSION_IDS+=("$index")
    for field in Id Name User Service Type Class State Remote RemoteHost TTY Display; do
        safe_text "${rec[$field]-}"; ACT_SESSION[$index.$field]=$REPLY
    done
    service=${ACT_SESSION[$index.Service]}
    kind=''
    [[ -z $service ]] || kind=${SESSION_SERVICE_KIND[$service]-}
    if [[ -z $kind ]]; then
        if [[ ${ACT_SESSION[$index.Remote]} == yes ]]; then kind=Remote
        else
            case ${ACT_SESSION[$index.Type]} in
                tty) kind=TTY ;; x11|wayland|mir|web) kind=GUI ;; *) kind=Other ;;
            esac
        fi
    fi
    ACT_SESSION[$index.Kind]=$kind
    name=${ACT_SESSION[$index.Name]}
    [[ -n $name ]] || ACT_SESSION[$index.Name]="UID $uid"
    ACT_SESSION_SEEN[$uid]=1
}

collect_sessions() {
    ACT_SESSION=(); ACT_SESSION_IDS=()
    MODEL[session_state]=unavailable; MODEL[session_source]=none
    MODEL[session_records]=0; MODEL[session_parsed]=0
    MODEL[session_count]=0; MODEL[session_users]=0; MODEL[session_limited]=0
    local listing details rc sid rest key value name tty date clock endpoint index
    local -a ids=()
    local -A record=() ACT_SESSION_SEEN=()
    listing=$(run_bounded "$ACTIVITY_TIMEOUT" loginctl list-sessions --no-legend --no-pager 2>/dev/null); rc=$?
    if ((rc == 0)); then
        while read -r sid rest; do
            [[ -n $sid ]] || continue
            [[ $sid =~ ^[A-Za-z0-9_][A-Za-z0-9_.:-]*$ ]] || continue
            ((MODEL[session_records]+=1))
            if ((${#ids[@]} < SESSION_QUERY_LIMIT)); then ids+=("$sid")
            else MODEL[session_limited]=1; fi
        done <<<"$listing"
        MODEL[session_source]=logind
        if ((${#ids[@]} == 0)); then MODEL[session_state]=ok; return 0; fi
        details=$(run_bounded "$ACTIVITY_TIMEOUT" loginctl show-session --all --no-pager \
            -p Id -p Name -p User -p Service -p Type -p Class -p State \
            -p Remote -p RemoteHost -p TTY -p Display "${ids[@]}" 2>/dev/null); rc=$?
        # Exiting sessions can make the batch return nonzero; retain complete
        # records but mark the inventory partial. Discard timed-out output.
        if ((rc != 124 && rc != 137)) && [[ -n $details ]]; then
            while IFS= read -r rest; do
                if [[ -z $rest ]]; then activity_session_record record; record=(); continue; fi
                [[ $rest == *=* ]] || continue
                key=${rest%%=*}; value=${rest#*=}
                case $key in Id|Name|User|Service|Type|Class|State|Remote|RemoteHost|TTY|Display) record[$key]=$value ;; esac
            done <<<"$details"
            activity_session_record record
            if ((MODEL[session_parsed] > 0)); then
                MODEL[session_count]=${#ACT_SESSION_IDS[@]}
                MODEL[session_users]=${#ACT_SESSION_SEEN[@]}
                MODEL[session_state]=ok
                if ((rc != 0 || MODEL[session_parsed] != MODEL[session_records] || MODEL[session_limited])); then
                    MODEL[session_state]=partial
                fi
                return 0
            fi
        fi
    fi
    # utmp is a fallback, not proof of complete SSH/GUI/RDP coverage.
    listing=$(run_bounded "$ACTIVITY_TIMEOUT" who 2>/dev/null); rc=$?
    if ((rc != 0)); then
        MODEL[session_source]=none
        ((rc == 124 || rc == 137)) && MODEL[session_state]=timeout
        return 0
    fi
    MODEL[session_source]=utmp; MODEL[session_state]=fallback
    ACT_SESSION_SEEN=(); ACT_SESSION=(); ACT_SESSION_IDS=()
    while read -r name tty date clock endpoint; do
        [[ -n $name && -n $tty ]] || continue
        index=${#ACT_SESSION_IDS[@]}; ACT_SESSION_IDS+=("$index")
        safe_text "$name"; ACT_SESSION[$index.Name]=$REPLY; ACT_SESSION_SEEN[$REPLY]=1
        safe_text "$tty"; ACT_SESSION[$index.TTY]=$REPLY
        safe_text "$endpoint"; ACT_SESSION[$index.RemoteHost]=$REPLY
        ACT_SESSION[$index.Kind]=utmp; ACT_SESSION[$index.State]=recorded
        ACT_SESSION[$index.Type]=tty; ACT_SESSION[$index.User]=''
    done <<<"$listing"
    MODEL[session_count]=${#ACT_SESSION_IDS[@]}
    MODEL[session_users]=${#ACT_SESSION_SEEN[@]}
}

collect_connections() {
    ACT_CONN=(); ACT_CONN_IDS=()
    MODEL[connection_state]=unavailable
    MODEL[tcp_established]=0; MODEL[tcp_admin]=0
    local snapshot rc recv send local_ep peer extra port label index key bad=0
    local -a admin=() other=()
    local -A admin_ports=()
    for port in "${CONNECTION_ADMIN_PORTS[@]}"; do admin_ports[$port]=1; done
    snapshot=$(run_bounded "$ACTIVITY_TIMEOUT" ss -Hnt state established 2>/dev/null); rc=$?
    if ((rc != 0)); then
        ((rc == 124 || rc == 137)) && MODEL[connection_state]=timeout
        return 0
    fi
    MODEL[connection_state]=ok
    while read -r recv send local_ep peer extra; do
        [[ -n $recv ]] || continue
        # The explicit state filter suppresses ss's State column.
        if [[ ! $recv =~ ^[0-9]+$ || ! $send =~ ^[0-9]+$ || $local_ep != *:* || $peer != *:* ]]; then
            ((bad+=1)); continue
        fi
        port=${local_ep##*:}
        if [[ ! $port =~ ^[0-9]+$ ]]; then ((bad+=1)); continue; fi
        index=${MODEL[tcp_established]}; ((MODEL[tcp_established]+=1))
        label=${CONNECTION_PORT_LABEL[$port]-TCP}
        if [[ -n ${admin_ports[$port]-} ]]; then
            ((MODEL[tcp_admin]+=1))
            ((${#admin[@]} < MAX_CONNECTIONS)) || continue
            admin+=("$index")
        else
            ((${#other[@]} < MAX_CONNECTIONS)) || continue
            other+=("$index")
        fi
        safe_text "$local_ep"; ACT_CONN[$index.local]=$REPLY
        safe_text "$peer"; ACT_CONN[$index.peer]=$REPLY
        ACT_CONN[$index.label]=$label
    done <<<"$snapshot"
    ((bad == 0)) || MODEL[connection_state]=partial
    for key in "${admin[@]}" "${other[@]}"; do
        ((${#ACT_CONN_IDS[@]} < MAX_CONNECTIONS)) || break
        ACT_CONN_IDS+=("$key")
    done
}

collect_activity() {
    collect_processes
    collect_sessions
    collect_connections
}


activity_attention() {
    case ${MODEL[process_state]-unavailable} in
        ok) ;;
        *) ATTENTION+=("INFO|Process snapshot ${MODEL[process_state]-unavailable}; rankings may be incomplete.") ;;
    esac
    case ${MODEL[session_state]-unavailable} in
        ok|fallback) ;;
        *) ATTENTION+=("INFO|Session inventory ${MODEL[session_state]-unavailable}; review loginctl or who.") ;;
    esac
    case ${MODEL[connection_state]-unavailable} in
        ok) ;;
        *) ATTENTION+=("INFO|TCP socket snapshot ${MODEL[connection_state]-unavailable}.") ;;
    esac
    if ((${MODEL[process_zombies]:-0} > 0)); then
        ATTENTION+=("INFO|${MODEL[process_zombies]} zombie process(es) observed; inspect their parent processes.")
    fi
    if ((${MODEL[process_blocked]:-0} >= 3)); then
        ATTENTION+=("INFO|${MODEL[process_blocked]} processes in uninterruptible wait at this snapshot; inspect if persistent.")
    fi
}

demo_activity() {
    ACT_PROC=(); ACT_SESSION=(); ACT_CONN=(); ACT_LOCAL_USER=([1000]=tech [1001]=alex [33]=www-data [999]=postgres)
    local pid uid cpu rss name score index
    while read -r pid uid cpu rss name; do
        ACT_PROC[$pid.uid]=$uid; ACT_PROC[$pid.cpu]=$cpu
        ACT_PROC[$pid.rss]=$rss; ACT_PROC[$pid.name]=$name; ACT_PROC[$pid.state]=S
    done <<'ACTIVITY_DEMO'
2418 1000 82.4 841728 stress-ng
1632 999 12.8 1355776 postgres
2109 33 3.1 196608 nginx
3920 1001 1.2 622592 firefox
ACTIVITY_DEMO
    ACT_CPU_IDS=(2418 1632 2109); ACT_RAM_IDS=(1632 2418 3920)
    while ((${#ACT_CPU_IDS[@]} > TOP_N)); do unset 'ACT_CPU_IDS[${#ACT_CPU_IDS[@]}-1]'; done
    while ((${#ACT_RAM_IDS[@]} > TOP_N)); do unset 'ACT_RAM_IDS[${#ACT_RAM_IDS[@]}-1]'; done
    MODEL[process_state]=ok; MODEL[process_count]=184; MODEL[process_running]=2
    MODEL[process_blocked]=0; MODEL[process_zombies]=0
    MODEL[session_state]=ok; MODEL[session_source]=logind
    MODEL[session_records]=3; MODEL[session_parsed]=3; MODEL[session_count]=3
    MODEL[session_users]=2; MODEL[session_limited]=0; ACT_SESSION_IDS=(0 1 2)
    ACT_SESSION[0.Name]=tech; ACT_SESSION[0.Kind]=SSH; ACT_SESSION[0.State]=active
    ACT_SESSION[0.TTY]=pts/0; ACT_SESSION[0.RemoteHost]=192.0.2.24
    ACT_SESSION[1.Name]=alex; ACT_SESSION[1.Kind]=RDP; ACT_SESSION[1.State]=online
    ACT_SESSION[1.Display]=:10; ACT_SESSION[1.RemoteHost]=192.0.2.41
    ACT_SESSION[2.Name]=tech; ACT_SESSION[2.Kind]=TTY; ACT_SESSION[2.State]=online
    ACT_SESSION[2.TTY]=tty2; ACT_SESSION[2.RemoteHost]=''
    MODEL[connection_state]=ok; MODEL[tcp_established]=8; MODEL[tcp_admin]=2
    ACT_CONN_IDS=(0 1 2)
    ACT_CONN[0.local]=192.0.2.17:22; ACT_CONN[0.peer]=192.0.2.24:51422; ACT_CONN[0.label]=SSH
    ACT_CONN[1.local]=192.0.2.17:3389; ACT_CONN[1.peer]=192.0.2.41:60108; ACT_CONN[1.label]=RDP
    ACT_CONN[2.local]=192.0.2.17:443; ACT_CONN[2.peer]=198.51.100.8:50322; ACT_CONN[2.label]=HTTPS
    while ((${#ACT_CONN_IDS[@]} > MAX_CONNECTIONS)); do unset 'ACT_CONN_IDS[${#ACT_CONN_IDS[@]}-1]'; done
    if ((${DEMO:-1} == 2)); then MODEL[process_zombies]=2; MODEL[process_blocked]=3; fi
}

# ===================== 5. FORMAT AND LAYOUT ==================================
repeat_char() { printf -v REPLY '%*s' "$2" ''; REPLY=${REPLY// /$1}; }

strip_ansi() {
    REPLY=$1; local pattern=$'\033''\[[0-9;]*m'
    while [[ $REPLY =~ $pattern ]]; do REPLY=${REPLY/"${BASH_REMATCH[0]}"/}; done
}

pad_cell() {
    local text=$1 width=$2 align=${3:-left} length
    ((width>0)) || { REPLY=''; return 0; }
    strip_ansi "$text"; length=${#REPLY}
    if ((length>width)); then
        clip_sgr_cell "$text" "$width"; text=$REPLY; length=$width
    fi
    if [[ $align == right ]]; then printf -v REPLY '%*s%s' "$((width-length))" '' "$text"
    else printf -v REPLY '%s%*s' "$text" "$((width-length))" ''; fi
}

human_kib() {
    local kb=$1 div=1 suffix=Ki n
    if ((kb == 0)); then REPLY=0B; return; fi
    if ((kb >= 1073741824)); then div=1073741824; suffix=Ti
    elif ((kb >= 1048576)); then div=1048576; suffix=Gi
    elif ((kb >= 1024)); then div=1024; suffix=Mi; fi
    n=$(((kb*10+div/2)/div))
    if ((div == 1 || n >= 1000)); then printf -v REPLY '%d%s' "$((kb/div))" "$suffix"
    else printf -v REPLY '%d.%d%s' "$((n/10))" "$((n%10))" "$suffix"; fi
}

format_number() { if [[ ${1-} =~ ^[0-9]+$ ]]; then human_kib "$1"; else REPLY='?'; fi; }

line() { OUTPUT+="$1"$'\n'; }

rule_full() { ((COLS < 24)) || line "$BORDER$1$RULE_FULL$2$RST"; }


segmented_bar() {
    # Closed-form cumulative rounding: one operation per category, never per cell.
    # Arguments after total are triples: KiB, colour, plain-mode character.
    local total=$1 count=$TEXT_WIDTH sum=0 end=0 last=0 bar='' value color symbol glyph
    shift; ((total > 0 && count > 0)) || { REPLY=''; return; }
    while (($# >= 3)); do
        value=$1 color=$2 symbol=$3; shift 3
        sum=$((sum+value)); end=$(((sum*count+total/2)/total))
        ((end <= count)) || end=$count
        glyph=$GLYPH_USED
        [[ $symbol != . ]] || glyph=$GLYPH_FREE
        ((MODEL[color])) || glyph=$symbol
        repeat_char "$glyph" "$((end-last))"; bar+=$color$REPLY$RST; last=$end
    done
    REPLY=$bar
}


demo_model() {
    MODEL[host]=ws-bench-07; MODEL[domain]=workshop.example; MODEL[domain_source]='DNS search'
    MODEL[os]='Debian GNU/Linux 13 (trixie)'; MODEL[kernel]=6.12.57-amd64
    MODEL[ip_state]=ok; HOST_IPS=('eno1 192.0.2.17/24')
    MODEL[cpus]=8; MODEL[uptime]='4d 06h 12m'; MODEL[load1]=1.42; MODEL[load5]=1.18; MODEL[load15]=0.97
    MODEL[sampled]='2026-11-16 13:30:00 AEDT'
    MODEL[psi_cpu]=1.20; MODEL[psi_memory]=0.00; MODEL[psi_io]=0.15
    MODEL[oom_kills]=0; MODEL[reboot_marker]=0; MODEL[root_readonly]=0; MODEL[md_degraded]=0
    MODEL[journal_state]=ok; MODEL[journal_count]=0; MODEL[journal_capped]=0
    MODEL[mem_total]=33554432; MODEL[mem_available]=25165824
    MODEL[mem_free]=17563648; MODEL[mem_buffers]=262144
    MODEL[mem_cached]=8388608; MODEL[mem_shmem]=524288; MODEL[mem_sreclaimable]=524288
    MODEL[zram_pool_kib]=655360; MODEL[zram_original_kib]=2097152
    MODEL[zram_compressed_kib]=589824; MODEL[zram_count]=1; MODEL[zram_state]=ok
    MODEL[zswap_pool_kib]=0; MODEL[zswap_original_kib]=0; MODEL[zswap_state]=ok
    MODEL[swap_total]=8388608; MODEL[swap_free]=6291456
    MODEL[swap_zram_used]=2097152; MODEL[swap_other_used]=0; MODEL[swap_state]=ok
    MODEL[storage_state]=ok; MODEL[storage_skipped]=0; MODEL[storage_skipped_shared]=0
    DISK_IDS=(root data); local id
    DISK[root.target]=/; DISK[root.total_kib]=104857600; DISK[root.used_kib]=31457280; DISK[root.avail_kib]=68157440
    DISK[root.inodes_total]=6553600; DISK[root.inodes_free]=5898240
    DISK[data.target]=/srv/images; DISK[data.total_kib]=524288000; DISK[data.used_kib]=199229440; DISK[data.avail_kib]=325058560
    DISK[data.inodes_total]=32768000; DISK[data.inodes_free]=30474240
    for id in "${DISK_IDS[@]}"; do
        DISK[$id.fstype]=ext4
        DISK[$id.reserved_kib]=$((${DISK[$id.total_kib]}-${DISK[$id.used_kib]}-${DISK[$id.avail_kib]}))
    done
    HEALTH_NOTES=()
    if ((DEMO==2)); then
        MODEL[mem_available]=1048576; MODEL[mem_free]=524288; MODEL[mem_cached]=786432
        MODEL[mem_shmem]=262144; MODEL[mem_buffers]=65536; MODEL[mem_sreclaimable]=196608
        MODEL[reboot_marker]=1; MODEL[oom_kills]=2; MODEL[journal_count]=3
        MODEL[psi_memory]=12.25
        DISK[root.used_kib]=100663296; DISK[root.avail_kib]=2097152
        DISK[root.reserved_kib]=$((104857600-100663296-2097152))
    fi
}

# ==================== 6. BOUNDED COLLECTION AND DISK I/O =====================
# Normal collection omits installed-unit scanning and journal I/O. Explicit
# options request these providers without changing the layout or work budget.
collect_services_fast() {
    local output rc
    SVC=(); SVC_KEYS=(); SVC_FAILURES=(); SVC_EXTRA=(); SVC_GROUP_MEMBERS=()
    MODEL[services_scope]=runtime
    MODEL[services_state]=unavailable
    MODEL[svc_runtime_state]=unavailable; MODEL[svc_files_state]=skipped
    if ! command -v systemctl >/dev/null 2>&1; then svc_finalize; return 0; fi
    # Include every resident type so failures of mounts/swaps still surface.
    # Installed-unit scanning is an explicitly requested acquisition policy.
    if output=$(LC_ALL=C SYSTEMD_COLORS=0 SYSTEMD_URLIFY=0 \
        run_bounded "${SERVICE_TIMEOUT:-0.10s}" systemctl --no-ask-password --no-pager \
        --no-legend --plain --full list-units --all 2>/dev/null); then
        MODEL[svc_runtime_state]=ok
        MODEL[services_state]=ok
        svc_parse_runtime "$output"
    else
        rc=$?
        if ((rc==124 || rc==137)); then
            MODEL[svc_runtime_state]=timeout; MODEL[services_state]=timeout
        elif ((rc==125)); then
            MODEL[svc_runtime_state]=budget; MODEL[services_state]=budget
        fi
    fi
    svc_finalize
}


# Kernel storage attribution, not file-space use or raw syscall byte counts.
# read_bytes/write_bytes include waited-for children. Never sum these rows as a
# host-wide total, or subtract cancelled writes as if that were physical traffic.
declare -A IO_PROC=() IO_DEV=() IO_BASE_PROC=() IO_BASE_DEV=()
IO_TOP_IDS=() IO_DEV_IDS=() IO_SCAN_IDS=()
IO_HAVE_BASE=0

io_now_us() {
    local value=${EPOCHREALTIME-} whole frac ignored
    if [[ $value =~ ^([0-9]{1,12})\.([0-9]{1,6})$ ]]; then
        whole=${BASH_REMATCH[1]}; frac=${BASH_REMATCH[2]}000000; frac=${frac:0:6}
        REPLY=$((10#$whole*1000000+10#$frac)); return 0
    fi
    io_monotonic_us
}
io_monotonic_us() {
    local value whole frac ignored
    # Bash 4.3 has no EPOCHREALTIME. /proc/uptime gives a monotonic centisecond
    # fallback without launching date; sub-20ms intervals remain unavailable.
    if { read -r value ignored <"$PROC_ROOT/uptime"; } 2>/dev/null &&
       [[ $value =~ ^([0-9]{1,12})\.([0-9]{1,6})$ ]]; then
        whole=${BASH_REMATCH[1]}; frac=${BASH_REMATCH[2]}000000; frac=${frac:0:6}
        REPLY=$((10#$whole*1000000+10#$frac)); return 0
    fi
    REPLY=''; return 1
}
io_uint() {
    [[ -n $1 && ${#1} -le 18 && $1 != *[!0123456789]* ]] || return 1
    REPLY=$((10#$1))
}
io_rate_kib() {
    # bytes/usec * 1e6/1024 = bytes/usec * 15625/16; split the quotient
    # before multiplying to avoid overflow on large cumulative counters.
    local bytes=$1 us=$2
    REPLY=$(( ((bytes/us)*15625 + (bytes%us)*15625/us) / 16 ))
}
io_amount() { human_kib "$(( $1 / 1024 ))"; }
io_pid_stat() {
    local pid=$1 raw tail
    local -a fields=()
    IO_STAT_START=''; IO_STAT_NAME=''
    { IFS= read -r raw <"$PROC_ROOT/$pid/stat"; } 2>/dev/null || return 1
    [[ $raw == "$pid ("* && $raw == *') '* ]] || return 1
    tail=${raw##*) }; read -r -a fields <<<"$tail"
    ((${#fields[@]}>=20)) && io_uint "${fields[19]}" || return 1
    IO_STAT_START=$REPLY
    raw=${raw#*'('}; IO_STAT_NAME=${raw%') '*}
}
io_read_pid() {
    local pid=$1 target=$2 key value extra start name r='' w='' c='' stamp
    local -n out=$target
    io_pid_stat "$pid" || return 2
    start=$IO_STAT_START; name=$IO_STAT_NAME
    if ! {
        while read -r key value extra; do
            case $key in
                read_bytes:) io_uint "$value" && r=$REPLY ;;
                write_bytes:) io_uint "$value" && w=$REPLY ;;
                cancelled_write_bytes:) io_uint "$value" && c=$REPLY ;;
            esac
        done <"$PROC_ROOT/$pid/io"
    } 2>/dev/null; then return 1; fi
    [[ -n $r && -n $w && -n $c ]] || return 1
    io_now_us; stamp=$REPLY
    io_pid_stat "$pid" || return 2
    [[ $IO_STAT_START == "$start" ]] || return 2
    safe_text "$name"
    out[$pid.name]=$REPLY; out[$pid.starttime]=$start; out[$pid.stamp_us]=$stamp
    out[$pid.read_bytes]=$r; out[$pid.write_bytes]=$w; out[$pid.cancelled_bytes]=$c
}
io_scan_processes() {
    local target=$1 path pid begin='' now='' rc i=0
    local -n out=$target
    local -a paths=()
    out=(); IO_SCAN_IDS=()
    MODEL[io_candidates]=0; MODEL[io_examined]=0; MODEL[io_readable]=0
    MODEL[io_denied]=0; MODEL[io_gone]=0; MODEL[io_capped]=0
    MODEL[io_state]=unavailable
    [[ -d $PROC_ROOT && -r $PROC_ROOT ]] || return 0
    paths=("$PROC_ROOT"/[0-9]*)
    if [[ ! -d ${paths[0]} ]]; then paths=(); fi
    MODEL[io_candidates]=${#paths[@]}
    io_now_us && begin=$REPLY
    for path in "${paths[@]}"; do
        ((i<IO_PROCESS_LIMIT)) || { MODEL[io_capped]=1; break; }
        if ((i%8==0)) && [[ -n $begin ]]; then
            io_now_us; now=$REPLY
            if [[ -n $now ]] && ((now-begin>=IO_SCAN_BUDGET_MS*1000)); then MODEL[io_capped]=1; break; fi
        fi
        pid=${path##*/}; [[ $pid =~ ^[0-9]+$ ]] || continue
        ((i+=1)); MODEL[io_examined]=$i
        [[ $pid != "$$" ]] || continue
        io_read_pid "$pid" "$target"; rc=$?
        case $rc in
            0) IO_SCAN_IDS+=("$pid"); ((MODEL[io_readable]+=1)) ;;
            1) ((MODEL[io_denied]+=1)) ;;
            *) ((MODEL[io_gone]+=1)) ;;
        esac
    done
    if ((MODEL[io_readable]>0)); then
        MODEL[io_state]=ok
        ((MODEL[io_denied]+MODEL[io_gone]+MODEL[io_capped]==0)) || MODEL[io_state]=partial
    elif ((MODEL[io_capped])); then MODEL[io_state]=budget; fi
}
io_scan_devices() {
    local target=$1 major minor name rd rm rs rt wd wm ws wt inflight busy weighted rest
    local slave leaf seq stamp count=0 rbytes wbytes
    local -n out=$target
    out=(); IO_DEV_IDS=(); MODEL[diskstats_state]=unavailable
    MODEL[disk_inflight]=0; MODEL[disk_device_count]=0; MODEL[diskstats_capped]=0
    [[ -r $PROC_ROOT/diskstats && -d $SYS_ROOT/block && -r $SYS_ROOT/block ]] || return 0
    MODEL[diskstats_state]=ok; io_now_us; stamp=$REPLY
    while read -r major minor name rd rm rs rt wd wm ws wt inflight busy weighted rest; do
        [[ -n $name && -d $SYS_ROOT/block/$name ]] || continue  # No partitions.
        case $name in loop*|ram*|zram*|dm-*|md*) continue ;; esac
        # Whole leaf block devices only: avoid summing a virtual stack and its
        # backing disks. Device totals are scoped; they are not all hardware I/O.
        [[ -e $SYS_ROOT/block/$name/device ]] || continue
        leaf=1
        for slave in "$SYS_ROOT/block/$name/slaves/"*; do [[ ! -e $slave ]] || { leaf=0; break; }; done
        ((leaf)) || continue
        ((count<IO_DEVICE_LIMIT)) || { MODEL[diskstats_capped]=1; MODEL[diskstats_state]=partial; break; }
        io_uint "$rs" || { MODEL[diskstats_state]=partial; continue; }; rs=$REPLY
        io_uint "$ws" || { MODEL[diskstats_state]=partial; continue; }; ws=$REPLY
        io_uint "$inflight" || { MODEL[diskstats_state]=partial; continue; }; inflight=$REPLY
        # Kernel sectors are 512 bytes, independently of hardware sector size.
        ((rs<=18000000000000000 && ws<=18000000000000000 && inflight<=1000000000)) || { MODEL[diskstats_state]=partial; continue; }
        rbytes=$((rs*512)); wbytes=$((ws*512))
        seq=''
        { read -r seq <"$SYS_ROOT/block/$name/diskseq"; } 2>/dev/null || seq=''
        [[ -z $seq ]] || io_uint "$seq" || seq=''
        IO_DEV_IDS+=("$name"); ((count+=1))
        out[$name.read_bytes]=$rbytes; out[$name.write_bytes]=$wbytes
        out[$name.inflight]=$inflight; out[$name.stamp_us]=$stamp
        out[$name.identity]="$major:$minor:$seq"; out[$name.diskseq]=$seq
        MODEL[disk_inflight]=$((MODEL[disk_inflight]+inflight))
    done 2>/dev/null <"$PROC_ROOT/diskstats"
    MODEL[disk_device_count]=$count
}
io_top_insert() {
    local pid=$1 score=$2 i j other
    for ((i=0;i<${#IO_TOP_IDS[@]};i++)); do
        other=${IO_TOP_IDS[i]}; ((score>${IO_PROC[$other.score]:-0})) && break
    done
    ((i<IO_TOP_N)) || return 0
    for ((j=${#IO_TOP_IDS[@]};j>i;j--)); do ((j>=IO_TOP_N)) || IO_TOP_IDS[j]=${IO_TOP_IDS[j-1]}; done
    IO_TOP_IDS[i]=$pid
}
io_derive() {
    local pid dev elapsed r w stamp old paired=0 shortest=0 longest=0
    IO_TOP_IDS=(); MODEL[io_basis]=lifetime; MODEL[io_interval_ms]=0
    MODEL[io_interval_min_ms]=0; MODEL[io_interval_max_ms]=0
    MODEL[io_unpaired]=0; MODEL[io_reset]=0; MODEL[diskstats_basis]=lifetime
    for pid in "${IO_SCAN_IDS[@]}"; do
        IO_PROC[$pid.score]=$((${IO_PROC[$pid.read_bytes]}+${IO_PROC[$pid.write_bytes]}))
        IO_PROC[$pid.read_kib_s]=''; IO_PROC[$pid.write_kib_s]=''
        ((IO_HAVE_BASE)) || continue
        if [[ ${IO_BASE_PROC[$pid.starttime]-} != "${IO_PROC[$pid.starttime]}" || -z ${IO_BASE_PROC[$pid.stamp_us]-} || -z ${IO_PROC[$pid.stamp_us]-} ]]; then
            ((MODEL[io_unpaired]+=1)); continue
        fi
        elapsed=$((${IO_PROC[$pid.stamp_us]}-${IO_BASE_PROC[$pid.stamp_us]}))
        ((elapsed>=IO_MIN_SAMPLE_MS*1000 && elapsed<=IO_MAX_SAMPLE_MS*1000)) || { ((MODEL[io_unpaired]+=1)); continue; }
        r=$((${IO_PROC[$pid.read_bytes]}-${IO_BASE_PROC[$pid.read_bytes]}))
        w=$((${IO_PROC[$pid.write_bytes]}-${IO_BASE_PROC[$pid.write_bytes]}))
        if ((r<0 || w<0)); then ((MODEL[io_reset]+=1)); continue; fi
        io_rate_kib "$r" "$elapsed"; IO_PROC[$pid.read_kib_s]=$REPLY
        io_rate_kib "$w" "$elapsed"; IO_PROC[$pid.write_kib_s]=$REPLY
        IO_PROC[$pid.interval_ms]=$((elapsed/1000))
        ((paired+=1))
        ((shortest!=0 && elapsed>=shortest)) || shortest=$elapsed
        ((elapsed<=longest)) || longest=$elapsed
    done
    if ((paired>0)); then
        MODEL[io_basis]=interval; MODEL[io_interval_min_ms]=$((shortest/1000)); MODEL[io_interval_max_ms]=$((longest/1000))
        MODEL[io_interval_ms]=$(((shortest+longest)/2000))
    fi
    for pid in "${IO_SCAN_IDS[@]}"; do
        if [[ ${MODEL[io_basis]} == interval ]]; then
            [[ -n ${IO_PROC[$pid.read_kib_s]} && -n ${IO_PROC[$pid.write_kib_s]} ]] || continue
            IO_PROC[$pid.score]=$((${IO_PROC[$pid.read_kib_s]}+${IO_PROC[$pid.write_kib_s]}))
        fi
        io_top_insert "$pid" "${IO_PROC[$pid.score]}"
    done
    MODEL[io_rate_processes]=$paired
    if ((MODEL[io_reset]>0)) || { [[ ${MODEL[io_basis]} == interval ]] && ((MODEL[io_unpaired]>0)); }; then MODEL[io_state]=partial; fi
    for dev in "${IO_DEV_IDS[@]}"; do
        IO_DEV[$dev.read_kib_s]=''; IO_DEV[$dev.write_kib_s]=''
        ((IO_HAVE_BASE)) || continue
        # diskseq detects hot-unplug/replacement even if the name/devt is reused.
        [[ -n ${IO_DEV[$dev.diskseq]} && ${IO_DEV[$dev.identity]} == "${IO_BASE_DEV[$dev.identity]-}" && -n ${IO_BASE_DEV[$dev.stamp_us]-} && -n ${IO_DEV[$dev.stamp_us]-} ]] || continue
        elapsed=$((${IO_DEV[$dev.stamp_us]}-${IO_BASE_DEV[$dev.stamp_us]}))
        ((elapsed>=IO_MIN_SAMPLE_MS*1000 && elapsed<=IO_MAX_SAMPLE_MS*1000)) || continue
        r=$((${IO_DEV[$dev.read_bytes]}-${IO_BASE_DEV[$dev.read_bytes]})); w=$((${IO_DEV[$dev.write_bytes]}-${IO_BASE_DEV[$dev.write_bytes]}))
        ((r>=0 && w>=0)) || continue
        io_rate_kib "$r" "$elapsed"; IO_DEV[$dev.read_kib_s]=$REPLY
        io_rate_kib "$w" "$elapsed"; IO_DEV[$dev.write_kib_s]=$REPLY
        MODEL[diskstats_basis]=interval
    done
}
io_begin() {
    IO_HAVE_BASE=0; IO_BASE_PROC=(); IO_BASE_DEV=()
    MODEL[io_clock_discontinuity]=0
    io_now_us; IO_BEGIN_CLOCK_US=$REPLY
    io_monotonic_us; IO_BEGIN_MONO_US=$REPLY
    io_scan_devices IO_BASE_DEV
    io_scan_processes IO_BASE_PROC
    IO_HAVE_BASE=1
}
io_finish() {
    io_scan_devices IO_DEV
    io_scan_processes IO_PROC
    # Detect a wall-clock step during collection before trusting a short rate.
    # /proc/uptime quantization allows a 30ms difference between elapsed clocks.
    local end_clock end_mono divergence
    io_now_us; end_clock=$REPLY; io_monotonic_us; end_mono=$REPLY
    if ((IO_HAVE_BASE)) && [[ -n ${IO_BEGIN_CLOCK_US:-} && -n ${IO_BEGIN_MONO_US:-} && -n $end_clock && -n $end_mono ]]; then
        divergence=$(( (end_clock-IO_BEGIN_CLOCK_US)-(end_mono-IO_BEGIN_MONO_US) ))
        if ((divergence>30000 || divergence < -30000)); then
            IO_HAVE_BASE=0; MODEL[io_clock_discontinuity]=1
        fi
    fi
    io_derive
}
collect_io() {
    # One-shot fallback. The caller may instead bracket normal work with
    # io_begin / io_finish to obtain a short measured interval, with no sleep.
    IO_HAVE_BASE=0; io_finish
}


io_attention() {
    if ((${MODEL[io_clock_discontinuity]:-0})); then
        ATTENTION+=('INFO|Clock changed during I/O sampling; cumulative totals shown.')
    fi
    case ${MODEL[io_state]-unavailable} in
        ok) ;;
        partial) ATTENTION+=('INFO|Process I/O is partial; rankings cover readable, identity-checked tasks.') ;;
        budget) ATTENTION+=('INFO|Process I/O budget exhausted; no usable task rows collected.') ;;
        *) ATTENTION+=('INFO|Process I/O counters unavailable; permissions may restrict visibility.') ;;
    esac
}
demo_io() {
    IO_PROC=(); IO_DEV=(); IO_TOP_IDS=(2418 4301 1632); IO_DEV_IDS=(sdb sdc)
    MODEL[io_state]=ok; MODEL[io_basis]=interval; MODEL[io_interval_ms]=42
    MODEL[io_interval_min_ms]=40; MODEL[io_interval_max_ms]=44
    MODEL[io_candidates]=184; MODEL[io_examined]=184; MODEL[io_readable]=184
    MODEL[io_denied]=0; MODEL[io_gone]=0; MODEL[io_capped]=0; MODEL[io_rate_processes]=184
    local pid name r w total
    while read -r pid name r w total; do
        IO_PROC[$pid.name]=$name; IO_PROC[$pid.read_kib_s]=$r; IO_PROC[$pid.write_kib_s]=$w
        IO_PROC[$pid.read_bytes]=$total; IO_PROC[$pid.write_bytes]=$total
        IO_PROC[$pid.cancelled_bytes]=0; IO_PROC[$pid.score]=$((r+w)); IO_PROC[$pid.starttime]=100
    done <<'IO_DEMO'
2418 badblocks 185344 0 214748364800
4301 fio 4096 120832 107374182400
1632 postgres 128 512 4294967296
IO_DEMO
    while ((${#IO_TOP_IDS[@]}>IO_TOP_N)); do unset 'IO_TOP_IDS[${#IO_TOP_IDS[@]}-1]'; done
    MODEL[diskstats_state]=ok; MODEL[diskstats_basis]=interval; MODEL[disk_inflight]=4; MODEL[disk_device_count]=2
    IO_DEV[sdb.inflight]=1; IO_DEV[sdb.read_kib_s]=185344; IO_DEV[sdb.write_kib_s]=0
    IO_DEV[sdc.inflight]=3; IO_DEV[sdc.read_kib_s]=4096; IO_DEV[sdc.write_kib_s]=120832
    for name in sdb sdc; do IO_DEV[$name.read_bytes]=214748364800; IO_DEV[$name.write_bytes]=107374182400; done
}


# This renderer consumes the validated collection model.
# It never collects, samples, sleeps, executes a hint, or queries a service.
# Fixed-height rows deliberately truncate long display values with an ellipsis.
# Counts, explicit missing states and adjustable rows preserve reviewability.


# ==================== 7. SHARED DISPLAY COMPONENTS ==========================
# Shared presentation primitives and section callbacks.
# Every callback accepts a maximum row count, INCLUDING its titled divider.
# The dispatcher owns section order/visibility and assigns each row budget.
# These functions consume the validated model; they never collect or execute hints.
UI_REMAIN=0 UI_EMITTED=0 UI_SECTION_ID=''
UI_SEPARATOR=' | '
declare -a UI_COL_WIDTHS UI_CELLS

ui_enabled() { ui_item_enabled "$1" "$2"; }

ui_colour() { REPLY=${COLOR[$1]:-${COLOR[$2]:-}}; }
ui_plain_cell() {
    local value=$1 width=$2 colour=${3-} align=${4-left}
    safe_text "$value"; value=$REPLY
    if ((${#value}>width)); then
        if ((width>=3)); then value=${value:0:width-3}'...'; else value=${value:0:width}; fi
    fi
    if [[ $align == right ]]; then printf -v REPLY '%*s%s' "$((width-${#value}))" '' "$value"
    else printf -v REPLY '%s%*s' "$value" "$((width-${#value}))" ''; fi
    REPLY=$colour$REPLY$RST
}
ui_value_cell() {
    # Label and numeric/state value align independently; clipping precedes colour.
    local width=$1 label=$2 value=$3 shade=${4-} label_width
    safe_text "$value"; value=$REPLY
    ((width>${#value})) || { ui_plain_cell "$value" "$width" "$shade" right; return; }
    label_width=$((width-${#value}-1))
    ui_plain_cell "$label" "$label_width" "${COLOR[label]:-${COLOR[text]}}"
    REPLY="$REPLY $shade$value$RST"
}
ui_emit() {
    ((UI_REMAIN>0)) || return 0
    if ((${UI_DESIGN_CAPTURE:-0})); then
        # Keep the collector formatter's semantic SGR spans. The common
        # compositor measures visible cells and accepts only SGR escapes.
        UI_CAPTURE_LINES+=("$1")
        ((UI_REMAIN-=1)); ((UI_EMITTED+=1)); return 0
    fi
    line "$BORDER$V$RST $1 $BORDER$V$RST"
    ((UI_REMAIN-=1)); ((UI_EMITTED+=1)); return 0
}
ui_row() {
    ((UI_REMAIN>0)) || return 0
    ui_plain_cell "$1" "$TEXT_WIDTH" "${2-${COLOR[text]}}"
    ui_emit "$REPLY"
}
ui_rich_row() {
    ((UI_REMAIN>0)) || return 0
    pad_cell "$1" "$TEXT_WIDTH"; ui_emit "$REPLY"
}
ui_text() {
    local text=$1 shade=${2-${COLOR[text]}} part cut
    safe_text "$text"; text=$REPLY
    while [[ -n $text ]] && ((UI_REMAIN>0)); do
        if ((${#text}<=TEXT_WIDTH)); then ui_row "$text" "$shade"; break; fi
        part=${text:0:TEXT_WIDTH}; cut=${part% *}
        [[ -n $cut && $cut != "$part" ]] || cut=$part
        ui_row "$cut" "$shade"; text=${text:${#cut}}; text=${text# }
    done
}
ui_rule() {
    local title=$1 summary=${2-} left=${3-$LEFT} right=${4-$RIGHT} colour=${5-${COLOR[muted]}}
    local room=$((INNER-4)) tail='' title_room fill
    safe_text "$title"; title=$REPLY; safe_text "$summary"; summary=$REPLY
    # Keep the section title recognizable and let the right summary use spare width.
    title_room=$((room/2)); ((${#title}<=title_room)) || title=${title:0:title_room-3}'...'
    room=$((room-${#title}))
    if [[ -n $summary ]] && ((room>4)); then
        ((room>=${#summary}+2)) || summary=${summary:0:room-5}'...'
        tail=" $colour$summary$RST"; room=$((room-${#summary}-1))
    fi
    repeat_char "$H" "$((room>0 ? room : 0))"; fill=$REPLY
    line "$BORDER$left$H$RST ${COLOR[heading]}$title$RST $BORDER$fill$RST$tail $BORDER$right$RST"
}
ui_heading() {
    ((UI_REMAIN>0)) || return 0
    ui_rule "$1" "${2-}" "$LEFT" "$RIGHT" "${3-${COLOR[muted]}}"
    ((UI_REMAIN-=1)); ((UI_EMITTED+=1)); return 0
}
ui_begin() {
    UI_SECTION_ID=$1; UI_REMAIN=${2:-0}; UI_EMITTED=0
    local title=${UI_SECTION_TITLE:-${SECTION_TITLE[$1]:-$1}}
    if ((${UI_DESIGN_CAPTURE:-0})); then
        UI_CAPTURE_SUMMARY=${3-}; ((UI_REMAIN-=1)); return 0
    fi
    ui_heading "$title" "${3-}" "${4-${COLOR[muted]}}"
}
ui_columns() {
    local count=$1 i width available
    UI_COL_WIDTHS=(); UI_CELLS=()
    UI_SEPARATOR=' | '; ((${MODEL[unicode]:-0}==0)) || UI_SEPARATOR=' │ '
    available=$((TEXT_WIDTH-3*(count-1))); width=$((available/count))
    for ((i=0;i<count;i++)); do
        UI_COL_WIDTHS+=("$width"); ((i!=count-1)) || UI_COL_WIDTHS[i]=$((available-width*(count-1)))
    done
}
ui_grid() {
    local cell row='' i=0
    for cell in "${UI_CELLS[@]}"; do
        ((i==0)) || row+="${COLOR[muted]}$UI_SEPARATOR$RST"
        row+=$cell; ((i+=1))
    done
    ui_emit "$row"
}
ui_system() {
    local budget=$1 summary='' ip=${MODEL[ip_state]:-unknown} os=${MODEL[os]:-Linux} row='' item shown=0 room domain
    ui_enabled system identity && summary="up ${MODEL[uptime]:-?}"
    ui_begin system "$budget" "$summary"
    if [[ $MODE == verbose ]]; then
        ui_enabled system identity && ui_row "Host ${MODEL[host]:-?}  |  Site $SITE_LABEL"
        ui_enabled system domain && ui_row "Domain ${MODEL[domain]:-?} (${MODEL[domain_source]:-local configuration})"
        ui_enabled system platform && { ui_row "OS     ${MODEL[os]:-Linux}"; ui_row "Kernel ${MODEL[kernel]:-?}"; }
        if ui_enabled system addresses; then
            if ((${#HOST_IPS[@]})); then
                for item in "${HOST_IPS[@]}"; do ((shown<MAX_IPS)) || break; ui_row "IP     $item"; ((shown+=1)); done
                ((${#HOST_IPS[@]}<=shown)) || ui_row "$(( ${#HOST_IPS[@]}-shown )) additional address(es) not shown." "${COLOR[muted]}"
            else ui_row "IP     ${MODEL[ip_state]:-unavailable}" "${COLOR[muted]}"; fi
        fi
        ui_enabled system load && ui_row "CPU ${MODEL[cpus]:-?}  |  Load ${MODEL[load1]:-?} / ${MODEL[load5]:-?} / ${MODEL[load15]:-?} (1/5/15m)"
        ui_enabled system pressure && ui_row "Stall avg10: CPU ${MODEL[psi_cpu]:-?}%  RAM ${MODEL[psi_memory]:-?}%  I/O ${MODEL[psi_io]:-?}%"
        ui_row "Sample ${MODEL[sampled]:-?}" "${COLOR[muted]}"
        return
    fi
    ((${#HOST_IPS[@]}==0)) || ip=${HOST_IPS[0]}
    if ((TEXT_WIDTH>=60)); then
        ui_columns 2
        if ui_enabled system domain; then ui_plain_cell "Domain ${MODEL[domain]:-?}" "${UI_COL_WIDTHS[0]}" "${COLOR[label]:-${COLOR[text]}}"; UI_CELLS+=("$REPLY"); else ui_plain_cell '' "${UI_COL_WIDTHS[0]}"; UI_CELLS+=("$REPLY"); fi
        if ui_enabled system addresses; then ui_plain_cell "IP $ip" "${UI_COL_WIDTHS[1]}" "${COLOR[value]:-${COLOR[text]}}"; UI_CELLS+=("$REPLY"); else ui_plain_cell '' "${UI_COL_WIDTHS[1]}"; UI_CELLS+=("$REPLY"); fi
        ui_grid
        if ui_enabled system platform; then
            ui_columns 2; ui_plain_cell "$os" "${UI_COL_WIDTHS[0]}"; UI_CELLS+=("$REPLY")
            ui_plain_cell "Kernel ${MODEL[kernel]:-?}" "${UI_COL_WIDTHS[1]}"; UI_CELLS+=("$REPLY"); ui_grid
        fi
        if ((UI_REMAIN>0)) && ui_enabled system load; then ui_row "CPU ${MODEL[cpus]:-?} | load ${MODEL[load1]:-?}/${MODEL[load5]:-?}/${MODEL[load15]:-?}"; fi
    else
        if ((UI_REMAIN==1)) && ui_enabled system addresses; then
            row="IP $ip"; room=$((TEXT_WIDTH-${#row}-3))
            if ((room>=8)) && ui_enabled system domain; then
                safe_text "${MODEL[domain]:-?}"; domain=$REPLY
                ((${#domain}<=room)) || domain=${domain:0:room-3}'...'
                row+=" | $domain"
            fi
            ui_row "$row"
        else
            ui_enabled system domain && ui_row "Domain ${MODEL[domain]:-?}"
            ui_enabled system addresses && ui_row "IP $ip"
            ui_enabled system platform && ui_row "$os | ${MODEL[kernel]:-?}"
        fi
    fi
    if ((UI_REMAIN>0)) && ui_enabled system pressure; then ui_row "Stall: CPU ${MODEL[psi_cpu]:-?}% RAM ${MODEL[psi_memory]:-?}% I/O ${MODEL[psi_io]:-?}%"; fi
}
ui_small_bar() { local TEXT_WIDTH=$1; shift; segmented_bar "$@"; }
ui_memory_bar() {
    local width=$1 other=${MODEL[mem_other]:-0}
    UI_MEMORY_OTHER=$other; REPLY=''
    if ((${MODEL[mem_parts_valid]:-0})); then
        if ui_enabled resources compression; then
            ui_small_bar "$width" "${MODEL[mem_total]}" "$other" "${COLOR[other]}" O "${MODEL[mem_cache]}" "${COLOR[cache]}" C "${MODEL[mem_compressed]}" "${COLOR[compressed]}" Z "${MODEL[mem_free]}" "${COLOR[free]}" .
        else
            UI_MEMORY_OTHER=$((other+${MODEL[mem_compressed]:-0}))
            ui_small_bar "$width" "${MODEL[mem_total]}" "$UI_MEMORY_OTHER" "${COLOR[other]}" O "${MODEL[mem_cache]}" "${COLOR[cache]}" C "${MODEL[mem_free]}" "${COLOR[free]}" .
        fi
    elif ((${MODEL[mem_valid]:-0})); then
        ui_small_bar "$width" "${MODEL[mem_total]}" "${MODEL[mem_used]}" "${COLOR[other]}" U "${MODEL[mem_available]}" "${COLOR[free]}" .
    fi
}
ui_storage_bar() {
    local width=$1 id index=0 symbol
    local -a parts=()
    REPLY=''
    [[ ${MODEL[storage_state]-} == ok ]] && ((${MODEL[storage_total]:-0}>0)) || return
    for id in "${DISK_IDS[@]}"; do
        symbol=$((index%9+1)); ((index+=1))
        parts+=("${DISK[$id.used_kib]}" "${VIEW[$id.color]}" "$symbol")
    done
    parts+=("${MODEL[storage_reserved]}" "${COLOR[reserved]}" R "${MODEL[storage_avail]}" "${COLOR[free]}" .)
    ui_small_bar "$width" "${MODEL[storage_total]}" "${parts[@]}"
}
ui_memory_details() {
    local row other
    ui_row MEMORY "${COLOR[heading]}"
    ui_row "Total ${VIEW[mem_total]:-?} | available ${VIEW[mem_available]:-?} | used ${VIEW[mem_percent]:-?}%"
    ui_memory_bar "$TEXT_WIDTH"; ui_rich_row "$REPLY"
    if ((${MODEL[mem_parts_valid]:-0})); then
        human_kib "$UI_MEMORY_OTHER"; other=$REPLY
        row="${COLOR[other]}Other $other$RST | ${COLOR[cache]}Cache ${VIEW[mem_cache]:-?}$RST"
        ui_enabled resources compression && row+=" | ${COLOR[compressed]}Comp ${VIEW[mem_compressed]:-?}$RST"
        row+=" | Free ${VIEW[mem_free]:-?}"
        if ((TEXT_WIDTH>=60)); then ui_rich_row "$row"
        else ui_row "Other $other | Cache ${VIEW[mem_cache]:-?}"; ui_enabled resources compression && ui_row "Comp ${VIEW[mem_compressed]:-?} | Free ${VIEW[mem_free]:-?}"; fi
    else ui_row 'Bar uses available/unavailable RAM.' "${COLOR[muted]}"; fi
}
ui_compression_details() {
    if ((${MODEL[zram_count]:-0}>0)); then ui_row "Zram ${VIEW[zram_original_kib]:-?} data | ${VIEW[zram_pool_kib]:-?} RAM pool" "${COLOR[compressed]}"; fi
    if ((${MODEL[zswap_pool_kib]:-0}>0)) || [[ ${MODEL[zswap_state]-} != ok && ${MODEL[zswap_state]-} != absent ]]; then
        ui_row "Zswap ${VIEW[zswap_original_kib]:-?} data | ${VIEW[zswap_pool_kib]:-?} RAM pool" "${COLOR[compressed]}"
    fi
}
ui_swap_details() {
    local bar
    ui_row SWAP "${COLOR[heading]}"
    if ((${MODEL[swap_valid]:-0}==0)); then ui_row 'Swap unavailable.' "${COLOR[muted]}"; return; fi
    if ((${MODEL[swap_total]:-0}==0)); then ui_row 'Swap not configured.' "${COLOR[muted]}"; return; fi
    ui_row "Used ${VIEW[swap_used]} / ${VIEW[swap_total]} | free ${VIEW[swap_free]}"
    if ui_enabled resources compression && [[ ${MODEL[swap_state]-} == ok ]] && ((${MODEL[swap_zram_used]:-0}+${MODEL[swap_other_used]:-0}==${MODEL[swap_used]:-0})); then
        ui_small_bar "$TEXT_WIDTH" "${MODEL[swap_total]}" "${MODEL[swap_zram_used]}" "${COLOR[compressed]}" Z "${MODEL[swap_other_used]}" "${COLOR[other]}" O "${MODEL[swap_free]}" "${COLOR[free]}" .
        ui_rich_row "$REPLY"; ui_row "Zram ${VIEW[swap_zram_used]} | other swap ${VIEW[swap_other_used]}" "${COLOR[muted]}"
    else
        ui_small_bar "$TEXT_WIDTH" "${MODEL[swap_total]}" "${MODEL[swap_used]}" "${COLOR[other]}" U "${MODEL[swap_free]}" "${COLOR[free]}" .
        ui_rich_row "$REPLY"
    fi
}
ui_storage_details() {
    local id shown=0 denom percent inode
    ui_row STORAGE "${COLOR[heading]}"
    if [[ ${MODEL[storage_state]-} == ok ]] && ((${MODEL[storage_total]:-0}>0)); then
        ui_row "Used ${VIEW[storage_used]} / ${VIEW[storage_total]} | available ${VIEW[storage_avail]}"
        ui_storage_bar "$TEXT_WIDTH"; ui_rich_row "$REPLY"
        ui_row "Reserved ${VIEW[storage_reserved]} | available ${VIEW[storage_avail]}" "${COLOR[muted]}"
    else ui_row "Storage ${MODEL[storage_state]:-unavailable}" "${COLOR[muted]}"; fi
    ui_enabled resources filesystem_detail || return
    for id in "${DISK_IDS[@]}"; do
        ((shown<MAX_DISK_DETAILS)) || break; ((shown+=1))
        denom=$((${DISK[$id.used_kib]}+${DISK[$id.avail_kib]})); percent='?'; inode=''
        ((denom<=0)) || percent=$((${DISK[$id.used_kib]}*100/denom))
        if ((${DISK[$id.inodes_total]:-0}>0)); then inode=" | inodes $((100-100*${DISK[$id.inodes_free]}/${DISK[$id.inodes_total]}))%"; fi
        human_kib "${DISK[$id.avail_kib]}"; ui_text "$shown:${VIEW[$id.target]} $percent% used | $REPLY available$inode" "${VIEW[$id.color]}"
    done
    ((${#DISK_IDS[@]}<=shown)) || ui_row "$(( ${#DISK_IDS[@]}-shown )) additional filesystem(s) not shown." "${COLOR[muted]}"
}

ui_storage_worst() {
    UI_WORST='' UI_WORST_PCT=-1
    local id denominator percent
    for id in "${DISK_IDS[@]}"; do
        denominator=$((${DISK[$id.used_kib]}+${DISK[$id.avail_kib]})); ((denominator>0)) || continue
        percent=$((${DISK[$id.used_kib]}*100/denominator))
        if ((percent>UI_WORST_PCT)); then UI_WORST=$id; UI_WORST_PCT=$percent; fi
    done
}
ui_wide_resource_pair() {
    # Wide bars use the quantity named in the numeric row. In particular RAM
    # is used-versus-available, not the separate physical allocation categories
    # represented by the classic inline segmented bar. No observation is read
    # again here. If only one row survives allocation, keep its exact numbers.
    ((UI_REMAIN>0)) || return 0
    ui_row "$1" "${COLOR[heading]}"
    ((UI_REMAIN>0)) || return 0
    motd_view_fraction_bar "$2" "$3" "$TEXT_WIDTH"
    [[ $MV_BAR_VALID != 1 ]] || ui_row "$MV_BAR" "${COLOR[other]}"
}
ui_resources_wide() {
    if ui_enabled resources memory; then
        if ((${MODEL[mem_valid]:-0})); then
            ui_wide_resource_pair "RAM ${VIEW[mem_used]}/${VIEW[mem_total]} | ${VIEW[mem_percent]}% used" "${MODEL[mem_total]}" "${MODEL[mem_used]}"
        else ui_row 'RAM unavailable' "${COLOR[muted]}"; fi
    fi
    if ui_enabled resources storage; then
        if [[ ${MODEL[storage_state]-} == ok ]] && ((${MODEL[storage_total]:-0}>0)); then
            ui_wide_resource_pair "DISK ${VIEW[storage_used]}/${VIEW[storage_total]} used" "${MODEL[storage_total]}" "${MODEL[storage_used]}"
        else ui_row "DISK ${MODEL[storage_state]:-unavailable}" "${COLOR[muted]}"; fi
    fi
    if ui_enabled resources swap; then
        if ((${MODEL[swap_valid]:-0}==0)); then ui_row 'SWAP unavailable' "${COLOR[muted]}"
        elif ((${MODEL[swap_total]:-0}==0)); then ui_row 'SWAP not configured' "${COLOR[muted]}"
        else ui_wide_resource_pair "SWAP ${VIEW[swap_used]}/${VIEW[swap_total]} | free ${VIEW[swap_free]}" "${MODEL[swap_total]}" "${MODEL[swap_used]}"; fi
    fi
    if ((UI_REMAIN>0)) && ui_enabled resources memory; then
        ui_row "Cache ${VIEW[mem_cache]:-?} | available ${VIEW[mem_available]:-?}" "${COLOR[muted]}"
    fi
    if ((UI_REMAIN>0)) && ui_enabled resources compression; then ui_compression_details; fi
}
ui_resources() {
    local budget=$1 summary='' bar='' width=18 row='' value tail='' id inode='' shade=${COLOR[muted]} comp_label=Comp swap_label=Swap
    ui_storage_worst
    if [[ -n $UI_WORST ]] && ui_enabled resources storage && ui_enabled resources filesystem_detail; then
        summary="Max FS $UI_WORST_PCT%"
        ((UI_WORST_PCT<DISK_WARN)) || shade=${COLOR[warn]}
        ((UI_WORST_PCT<DISK_CRITICAL)) || shade=${COLOR[error]}
    fi
    ui_begin resources "$budget" "$summary" "$shade"
    if [[ $BAR_LAYOUT == wide ]]; then ui_resources_wide; return; fi
    if [[ $MODE == verbose ]]; then
        ui_enabled resources memory && ui_memory_details
        ui_enabled resources compression && ui_compression_details
        ui_enabled resources swap && ui_swap_details
        ui_enabled resources storage && ui_storage_details
        return
    fi
    ((TEXT_WIDTH>=60)) || width=8
    if ui_enabled resources memory; then
        ui_memory_bar "$width"; bar=$REPLY
        ui_plain_cell RAM 5 "${COLOR[heading]}"; row=$REPLY
        ui_plain_cell "${VIEW[mem_used]:-?}/${VIEW[mem_total]:-?}" 15 "${COLOR[value]:-${COLOR[text]}}"; row+="$REPLY $bar"
        ((TEXT_WIDTH<60)) || row+="  avail ${VIEW[mem_available]:-?}  ${VIEW[mem_percent]:-?}%"
        ui_rich_row "$row"
    fi
    if ui_enabled resources storage; then
        bar=''
        if [[ ${MODEL[storage_state]-} == ok ]] && ((${MODEL[storage_total]:-0}>0)); then
            ui_storage_bar "$width"; bar=$REPLY
            ui_plain_cell DISK 5 "${COLOR[heading]}"; row=$REPLY
            ui_plain_cell "${VIEW[storage_used]:-?}/${VIEW[storage_total]:-?}" 15 "${COLOR[value]:-${COLOR[text]}}"; row+="$REPLY $bar"
            ((TEXT_WIDTH<60)) || row+="  free ${VIEW[storage_avail]:-?}"
            ui_rich_row "$row"
        else ui_row "DISK ${MODEL[storage_state]:-unavailable}" "${COLOR[muted]}"; fi
    fi
    row=''
    if ((TEXT_WIDTH<60)); then comp_label=Z; swap_label=S; fi
    if ui_enabled resources memory; then row="${COLOR[cache]}Cache ${VIEW[mem_cache]:-?}$RST"; fi
    if ui_enabled resources compression; then row+="${row:+  }${COLOR[compressed]}$comp_label${comp_label:+ }${VIEW[mem_compressed]:-?}$RST"; fi
    if ui_enabled resources swap; then row+="${row:+  }$swap_label ${VIEW[swap_used]:-?}/${VIEW[swap_total]:-?}"; fi
    [[ -z $row ]] || ui_rich_row "$row"
    if [[ -n $UI_WORST ]] && ui_enabled resources storage && ui_enabled resources filesystem_detail; then
        id=$UI_WORST
        if ((${DISK[$id.inodes_total]:-0}>0)); then inode=" | inodes $((100-100*${DISK[$id.inodes_free]}/${DISK[$id.inodes_total]}))%"; fi
        ui_row "Fullest ${VIEW[$id.target]:-?} $UI_WORST_PCT%$inode" "$shade"
    fi
}
ui_role_state() {
    local role=$1 unit candidate='' chosen='' units=${SERVICE_ROLE_UNITS[$1]-}
    for unit in $units; do
        ui_enabled services "$unit" || continue
        [[ -n ${SVC[$unit.seen]-} ]] || continue
        [[ -n $candidate ]] || candidate=$unit
        if [[ -n ${SVC[$unit.runtime]-} && -z ${SVC[$candidate.runtime]-} ]]; then candidate=$unit; fi
        svc_state "$unit"
        if [[ $REPLY == FAIL ]]; then chosen=$unit; break; fi
        case ${SVC[$unit.active]-} in active|reloading) [[ -n $chosen ]] || chosen=$unit ;; esac
    done
    chosen=${chosen:-$candidate}; [[ -n $chosen ]] || return 1
    UI_ROLE_UNIT=$chosen; svc_state "$chosen"; UI_ROLE_STATE=$REPLY; UI_ROLE_COLOUR=$SVC_COLOR
}
ui_services() {
    local budget=$1 summary='' role count=0 columns capacity shown=0 omitted=0 state shade unit group label i flag raw
    local -a roles=() failed=() normal=() units=()
    local -A states=() colours=()
    if [[ $SERVICES_MODE == all ]]; then ui_services_inventory "$budget"; return; fi
    columns=$(((TEXT_WIDTH+3)/15)); ((columns>=1)) || columns=1
    capacity=$(((budget>0 ? budget-1 : 0)*columns))
    for role in "${SERVICE_ROLE_ORDER[@]}"; do
        ui_enabled services "$role" || continue
        ui_role_state "$role" || continue
        states[$role]=$UI_ROLE_STATE; colours[$role]=$UI_ROLE_COLOUR
        if [[ $UI_ROLE_STATE == FAIL ]]; then failed+=("$role"); else normal+=("$role"); fi
    done
    roles=("${failed[@]}" "${normal[@]}")
    if [[ ${MODEL[svc_runtime_state]-} == ok ]]; then summary="${MODEL[svc_running]:-?} run / ${MODEL[svc_loaded]:-?} load / ${MODEL[svc_failed]:-?} fail"
    else summary="${MODEL[svc_runtime_state]:-unavailable}"; fi
    omitted=$((${#roles[@]}-capacity)); ((omitted<=0)) || summary+=" +$omitted roles"
    shade=${COLOR[muted]}; ((${MODEL[svc_failed]:-0}==0)) || shade=${COLOR[error]}
    ui_enabled services summary || summary=''
    ui_begin services "$budget" "$summary" "$shade"
    local -A required_seen=()
    for unit in "${REQUIRED_UNITS[@]}"; do
        [[ ! ${required_seen[$unit]+set} ]] || continue; required_seen[$unit]=1
        svc_state "$unit"; state=$REPLY; shade=$SVC_COLOR
        ui_value_cell "$TEXT_WIDTH" "Required $unit" "$state" "$shade"; ui_emit "$REPLY"
    done
    if ((${#roles[@]}==0)); then ui_row 'No observed configured service roles.'  "${COLOR[muted]}"; return; fi
    while ((shown<${#roles[@]} && UI_REMAIN>0)); do
        ui_columns "$columns"
        for ((i=0;i<columns;i++)); do
            role=${roles[shown]-}
            if [[ -n $role ]]; then
                label=${SERVICE_ROLE_LABEL[$role]:-$role}
                ui_value_cell "${UI_COL_WIDTHS[i]}" "$label" "${states[$role]}" "${colours[$role]}"; ((shown+=1))
            else ui_plain_cell '' "${UI_COL_WIDTHS[i]}"; fi
            UI_CELLS+=("$REPLY")
        done
        ui_grid
    done
}
ui_service_visible() {
    local unit=$1 role member
    ui_enabled services "$unit" || return 1
    for role in "${SERVICE_ROLE_ORDER[@]}"; do
        ui_enabled services "$role" && continue
        for member in ${SERVICE_ROLE_UNITS[$role]-}; do [[ $unit != "$member" ]] || return 1; done
    done
    return 0
}
ui_services_inventory() {
    local budget=$1 unit group state shade flag label i columns=2 shown=0 summary excess=0
    local -a units=() filtered=()
    summary="${MODEL[svc_running]:-?} running / ${MODEL[svc_loaded]:-?} loaded / ${MODEL[svc_failed]:-?} failed"
    ui_enabled services summary || summary=''
    ui_begin services "$budget" "$summary"
    if [[ ${MODEL[svc_runtime_state]-} != ok && ${MODEL[svc_files_state]-} != ok ]]; then ui_row 'Service inventory unavailable.' "${COLOR[muted]}"; return; fi
    if [[ $SERVICES_MODE == all ]]; then
        if ((TEXT_WIDTH>=68)); then
            UI_COL_WIDTHS=("$((TEXT_WIDTH-54))" 8 14 8 12); UI_CELLS=()
            i=0; for label in UNIT STATE ACTIVE/SUB LOAD BOOT; do ui_plain_cell "$label" "${UI_COL_WIDTHS[i]}" "${COLOR[heading]}"; UI_CELLS+=("$REPLY"); ((i+=1)); done; ui_grid
        fi
        for unit in "${SVC_KEYS[@]}"; do
            case $unit in *.service|*.socket|*.timer) ;; *) continue ;; esac
            svc_excluded "$unit" && continue
            ui_service_visible "$unit" || continue
            svc_state "$unit"; state=$REPLY; shade=$SVC_COLOR
            if ((TEXT_WIDTH>=68)); then
                UI_CELLS=(); ui_plain_cell "$unit" "${UI_COL_WIDTHS[0]}"; UI_CELLS+=("$REPLY")
                ui_plain_cell "$state" 8 "$shade"; UI_CELLS+=("$REPLY")
                ui_plain_cell "${SVC[$unit.active]:-?}/${SVC[$unit.sub]:-?}" 14; UI_CELLS+=("$REPLY")
                ui_plain_cell "${SVC[$unit.load]:-?}" 8; UI_CELLS+=("$REPLY")
                ui_plain_cell "${SVC[$unit.file]:-?}" 12; UI_CELLS+=("$REPLY"); ui_grid
                ((${#unit}<=UI_COL_WIDTHS[0])) || ui_text "  $unit" "${COLOR[muted]}"
            else ui_text "$unit" "${COLOR[heading]}"; ui_text "$state | ${SVC[$unit.active]:-?}/${SVC[$unit.sub]:-?} | ${SVC[$unit.file]:-?}" "$shade"; fi
        done
    else
        ((TEXT_WIDTH>=60)) || columns=1
        for group in "${SERVICE_GROUPS[@]}" Other; do
            units=()
            if [[ $group == Other ]]; then units=("${SVC_EXTRA[@]}")
            else while IFS= read -r unit; do [[ -z $unit ]] || units+=("$unit"); done <<<"${SVC_GROUP_MEMBERS[$group]-}"; fi
            filtered=()
            for unit in "${units[@]}"; do ui_service_visible "$unit" && filtered+=("$unit"); done
            units=("${filtered[@]}"); excess=0
            if [[ $group == Other ]] && ((${#units[@]}>SERVICE_EXTRA_LIMIT)); then
                excess=$((${#units[@]}-SERVICE_EXTRA_LIMIT)); units=("${units[@]:0:SERVICE_EXTRA_LIMIT}")
            fi
            ((${#units[@]})) || continue
            ui_row "$group" "${COLOR[heading]}"; shown=0
            while ((shown<${#units[@]} && UI_REMAIN>0)); do
                ui_columns "$columns"
                for ((i=0;i<columns;i++)); do
                    unit=${units[shown]-}
                    if [[ -n $unit ]]; then
                        svc_state "$unit"; state=$REPLY; shade=$SVC_COLOR
                        svc_file_flag "$unit"; flag=$REPLY; label=${unit%.service}
                        ui_value_cell "${UI_COL_WIDTHS[i]}" "$label" "$state/$flag" "$shade"; ((shown+=1))
                    else ui_plain_cell '' "${UI_COL_WIDTHS[i]}"; fi
                    UI_CELLS+=("$REPLY")
                done
                ui_grid
            done
            ((excess==0)) || ui_row "$excess further other units; use --services all." "${COLOR[muted]}"
        done
        ui_text 'Boot /e enabled  /d disabled  /s static  /m masked  /? unknown' "${COLOR[muted]}"
        ui_text 'RUN running; DONE exited; WAIT/LISTEN armed; STOP inactive.' "${COLOR[muted]}"
        ui_text 'UNLOADED: installed, not resident. MASK: activation blocked.' "${COLOR[muted]}"
    fi
}
ui_process_value() {
    local kind=$1 pid=$2 value total
    UI_PROCESS_LABEL=''; UI_PROCESS_VALUE='?'
    [[ -n $pid ]] || return
    if [[ $kind == io ]]; then
        UI_PROCESS_LABEL="$pid ${IO_PROC[$pid.name]:-?}"
        if [[ ${MODEL[io_basis]-} == interval ]]; then
            total=$((${IO_PROC[$pid.read_kib_s]:-0}+${IO_PROC[$pid.write_kib_s]:-0})); human_kib "$total"; UI_PROCESS_VALUE=$REPLY/s
        else
            total=$((${IO_PROC[$pid.read_bytes]:-0}/1024+${IO_PROC[$pid.write_bytes]:-0}/1024)); human_kib "$total"; UI_PROCESS_VALUE=$REPLY
        fi
    else
        UI_PROCESS_LABEL="$pid ${ACT_PROC[$pid.name]:-?}"
        if [[ $kind == cpu ]]; then UI_PROCESS_VALUE=${ACT_PROC[$pid.cpu]:-?}%
        else human_kib "${ACT_PROC[$pid.rss]:-0}"; UI_PROCESS_VALUE=$REPLY; fi
    fi
}
ui_task_ids() {
    case $1 in cpu) UI_TASK_IDS=("${ACT_CPU_IDS[@]}") ;; rss) UI_TASK_IDS=("${ACT_RAM_IDS[@]}") ;; io) UI_TASK_IDS=("${IO_TOP_IDS[@]}") ;; esac
}
ui_tasks() {
    local budget=$1 summary='' count='?' d='?' z='?' kind label pid rank=0 i limit title shade dev r w shown=0 inflight='?'
    local -a kinds=() UI_TASK_IDS=()
    case ${MODEL[process_state]-} in ok|partial) count=${MODEL[process_count]:-?}; d=${MODEL[process_blocked]:-?}; z=${MODEL[process_zombies]:-?} ;; esac
    summary="$count tasks D$d Z$z"
    ui_enabled system load && summary+=" | ${MODEL[cpus]:-?}C L${MODEL[load1]:-?}"
    if ui_enabled processes io && [[ ${MODEL[io_basis]-} == interval ]]; then summary+=" | I/O ${MODEL[io_interval_ms]:-?}ms"; fi
    ui_begin processes "$budget" "$summary"
    if [[ $MODE == verbose ]]; then
        ui_enabled processes cpu && ui_process_table cpu 'CPU average since process start'
        ui_enabled processes rss && ui_process_table rss 'Resident memory (RSS)'
        ui_enabled processes io && ui_io_body
        ui_enabled processes details && ui_text 'CPU is a lifetime average; RSS includes shared pages.' "${COLOR[muted]}"
        return
    fi
    for kind in cpu rss io; do ui_enabled processes "$kind" && kinds+=("$kind"); done
    ((${#kinds[@]})) || return
    if ((TEXT_WIDTH>=60)); then
        ui_columns "${#kinds[@]}"; i=0
        for kind in "${kinds[@]}"; do
            case $kind in cpu) title='CPU avg / PID name' ;; rss) title='RAM RSS / PID name' ;; io) title="I/O R+W/s [${MODEL[io_readable]:-?}/${MODEL[io_candidates]:-?}]"; [[ ${MODEL[io_basis]-} == interval ]] || title="I/O total [${MODEL[io_readable]:-?}/${MODEL[io_candidates]:-?}]" ;; esac
            ((${MODEL[unicode]:-0}!=0)) || title=${title//·/|}
            ui_colour "$kind" heading; shade=$REPLY; ui_plain_cell "$title" "${UI_COL_WIDTHS[i]}" "$shade"; UI_CELLS+=("$REPLY"); ((i+=1))
        done
        ui_grid
        limit=$UI_REMAIN; ((limit<=TOP_N)) || limit=$TOP_N
        for ((rank=0;rank<limit;rank++)); do
            ui_columns "${#kinds[@]}"; i=0
            for kind in "${kinds[@]}"; do
                ui_task_ids "$kind"; pid=${UI_TASK_IDS[rank]-}; ui_process_value "$kind" "$pid"
                ui_colour "$kind" heading; shade=$REPLY
                if [[ -n $pid ]]; then ui_value_cell "${UI_COL_WIDTHS[i]}" "$UI_PROCESS_LABEL" "$UI_PROCESS_VALUE" "$shade"
                else ui_plain_cell '-' "${UI_COL_WIDTHS[i]}" "${COLOR[muted]}"; fi
                UI_CELLS+=("$REPLY"); ((i+=1))
            done
            ui_grid
        done
    else
        for kind in "${kinds[@]}"; do
            ui_task_ids "$kind"; pid=${UI_TASK_IDS[0]-}; ui_process_value "$kind" "$pid"; ui_colour "$kind" heading; shade=$REPLY
            case $kind in cpu) label='CPU avg' ;; rss) label='RAM RSS' ;; io) label='I/O /s'; [[ ${MODEL[io_basis]-} == interval ]] || label='I/O total' ;; esac
            ui_value_cell "$TEXT_WIDTH" "$label $UI_PROCESS_LABEL" "$UI_PROCESS_VALUE" "$shade"; ui_emit "$REPLY"
        done
    fi
    if ((UI_REMAIN>0)) && ui_enabled processes io; then
        if [[ ${MODEL[io_basis]-} == interval ]]; then summary="I/O ~${MODEL[io_interval_ms]:-?}ms"
        else summary='I/O lifetime totals'; fi
        summary+=" | ${MODEL[io_readable]:-?}/${MODEL[io_candidates]:-?} readable PIDs"
        ui_row "$summary" "${COLOR[muted]}"
        if [[ ${MODEL[diskstats_state]-} == ok || ${MODEL[diskstats_state]-} == partial ]]; then
            ((${MODEL[disk_device_count]:-0}==0)) || inflight=${MODEL[disk_inflight]:-?}
            summary="Devices ${MODEL[disk_device_count]:-?} | in flight $inflight"
            ui_enabled system pressure && summary+=" | I/O stall ${MODEL[psi_io]:-?}%"
            ui_row "$summary" "${COLOR[muted]}"
            for dev in "${IO_DEV_IDS[@]}"; do
                ((shown<IO_SHOW_DEVICES && UI_REMAIN>0)) || break; ((shown+=1))
                if [[ -n ${IO_DEV[$dev.read_kib_s]-} && -n ${IO_DEV[$dev.write_kib_s]-} ]]; then
                    human_kib "${IO_DEV[$dev.read_kib_s]}"; r=$REPLY/s
                    human_kib "${IO_DEV[$dev.write_kib_s]}"; w=$REPLY/s
                    ui_row "$dev  R$r  W$w  q${IO_DEV[$dev.inflight]:-?}"
                else ui_row "$dev  q${IO_DEV[$dev.inflight]:-?}; rate unavailable" "${COLOR[muted]}"; fi
            done
        fi
    fi
}
ui_process_table() {
    local kind=$1 title=$2 pid uid user i label shade
    local -a UI_TASK_IDS=()
    ui_colour "$kind" heading; shade=$REPLY; ui_row "$title" "$shade"
    ui_task_ids "$kind"
    if ((${#UI_TASK_IDS[@]}==0)); then ui_row "Process ranking ${MODEL[process_state]:-unavailable}." "${COLOR[muted]}"; return; fi
    if ((TEXT_WIDTH>=60)); then
        UI_COL_WIDTHS=(7 11 8 9 "$((TEXT_WIDTH-47))"); UI_CELLS=(); i=0
        for label in PID USER 'CPU avg' RSS COMMAND; do ui_plain_cell "$label" "${UI_COL_WIDTHS[i]}" "${COLOR[heading]}"; UI_CELLS+=("$REPLY"); ((i+=1)); done; ui_grid
    fi
    for pid in "${UI_TASK_IDS[@]}"; do
        uid=${ACT_PROC[$pid.uid]-?}; user=${ACT_LOCAL_USER[$uid]:-#$uid}
        if ((TEXT_WIDTH>=60)); then
            UI_CELLS=(); ui_plain_cell "$pid" 7; UI_CELLS+=("$REPLY")
            ui_plain_cell "$user" 11; UI_CELLS+=("$REPLY")
            ui_plain_cell "${ACT_PROC[$pid.cpu]:-?}%" 8 "${COLOR[cpu]:-${COLOR[heading]}}" right; UI_CELLS+=("$REPLY")
            human_kib "${ACT_PROC[$pid.rss]:-0}"; ui_plain_cell "$REPLY" 9 "${COLOR[rss]:-${COLOR[heading]}}" right; UI_CELLS+=("$REPLY")
            ui_plain_cell "${ACT_PROC[$pid.name]:-?}" "${UI_COL_WIDTHS[4]}"; UI_CELLS+=("$REPLY"); ui_grid
        else
            ui_text "$pid ${ACT_PROC[$pid.name]:-?} ($user)" "${COLOR[heading]}"
            human_kib "${ACT_PROC[$pid.rss]:-0}"; ui_row "CPU ${ACT_PROC[$pid.cpu]:-?}% | RSS $REPLY"
        fi
    done
}
ui_io_body() {
    local pid dev r w total label i shown=0 inflight='?'
    if [[ ${MODEL[io_basis]-} == interval ]]; then label="Disk I/O / ${MODEL[io_interval_min_ms]:-?}-${MODEL[io_interval_max_ms]:-?}ms sample"
    else label='Disk I/O / cumulative storage bytes'; fi
    ((${MODEL[unicode]:-0}!=0)) || label=${label//·/|}
    ui_row "$label" "${COLOR[io]:-${COLOR[heading]}}"
    if ((TEXT_WIDTH>=60)); then
        UI_COL_WIDTHS=(7 "$((TEXT_WIDTH-40))" 12 12); UI_CELLS=(); i=0
        for label in PID COMMAND READ WRITE; do ui_plain_cell "$label" "${UI_COL_WIDTHS[i]}" "${COLOR[heading]}"; UI_CELLS+=("$REPLY"); ((i+=1)); done; ui_grid
    fi
    for pid in "${IO_TOP_IDS[@]}"; do
        if [[ ${MODEL[io_basis]-} == interval ]]; then human_kib "${IO_PROC[$pid.read_kib_s]:-0}"; r=$REPLY/s; human_kib "${IO_PROC[$pid.write_kib_s]:-0}"; w=$REPLY/s
        else io_amount "${IO_PROC[$pid.read_bytes]:-0}"; r=$REPLY; io_amount "${IO_PROC[$pid.write_bytes]:-0}"; w=$REPLY; fi
        if ((TEXT_WIDTH>=60)); then
            UI_CELLS=(); ui_plain_cell "$pid" 7; UI_CELLS+=("$REPLY")
            ui_plain_cell "${IO_PROC[$pid.name]:-?}" "${UI_COL_WIDTHS[1]}"; UI_CELLS+=("$REPLY")
            ui_plain_cell "$r" 12 "${COLOR[io]:-${COLOR[heading]}}" right; UI_CELLS+=("$REPLY")
            ui_plain_cell "$w" 12 "${COLOR[io]:-${COLOR[heading]}}" right; UI_CELLS+=("$REPLY"); ui_grid
        else ui_text "$pid ${IO_PROC[$pid.name]:-?}"; ui_row "Read $r  Write $w" "${COLOR[io]:-${COLOR[heading]}}"; fi
        if ((${IO_PROC[$pid.cancelled_bytes]:-0}>0)); then io_amount "${IO_PROC[$pid.cancelled_bytes]}"; ui_text "Cancelled write accounting: $REPLY cumulative" "${COLOR[muted]}"; fi
    done
    ((${#IO_TOP_IDS[@]})) || ui_row "Process I/O ${MODEL[io_state]:-unavailable}" "${COLOR[muted]}"
    if ui_enabled processes details; then
        ui_text "Readable ${MODEL[io_readable]:-?}/${MODEL[io_examined]:-?} examined; denied/incomplete ${MODEL[io_denied]:-?}; exited/changed ${MODEL[io_gone]:-?}." "${COLOR[muted]}"
        ((${MODEL[io_capped]:-0}==0)) || ui_row 'PID pass capped; rankings cover the measured subset.' "${COLOR[warn]}"
        ui_text 'Includes waited-for children; buffering/cancellation affect attribution.' "${COLOR[muted]}"
    fi
    if [[ ${MODEL[diskstats_state]-} == ok || ${MODEL[diskstats_state]-} == partial ]]; then
        ((${MODEL[disk_device_count]:-0}==0)) || inflight=${MODEL[disk_inflight]:-?}
        ui_row "Devices ${MODEL[disk_device_count]:-?} | requests in flight $inflight" "${COLOR[heading]}"
        for dev in "${IO_DEV_IDS[@]}"; do
            ((shown<IO_SHOW_DEVICES)) || break; ((shown+=1))
            if [[ -n ${IO_DEV[$dev.read_kib_s]-} && -n ${IO_DEV[$dev.write_kib_s]-} ]]; then human_kib "${IO_DEV[$dev.read_kib_s]}"; r=$REPLY/s; human_kib "${IO_DEV[$dev.write_kib_s]}"; w=$REPLY/s; label=''
            else io_amount "${IO_DEV[$dev.read_bytes]:-0}"; r=$REPLY; io_amount "${IO_DEV[$dev.write_bytes]:-0}"; w=$REPLY; label=' totals'; fi
            ui_text "$dev  read $r  write $w  q${IO_DEV[$dev.inflight]:-?}$label"
        done
    else ui_row 'Block-device counters unavailable.' "${COLOR[muted]}"; fi
}
ui_io() { ui_begin io "$1"; ui_io_body; }
ui_session_row() {
    local index=$1 user=${ACT_SESSION[$1.Name]:-?} kind=${ACT_SESSION[$1.Kind]:-?}
    local sid=${ACT_SESSION[$1.Id]-} place=${ACT_SESSION[$1.TTY]:-${ACT_SESSION[$1.Display]:--}}
    local peer=${ACT_SESSION[$1.RemoteHost]:-(local/unknown)} state=${ACT_SESSION[$1.State]:-?} text='' i=0
    if ((TEXT_WIDTH>=60)); then
        UI_COL_WIDTHS=(6 8 8 13 "$((TEXT_WIDTH-47))"); UI_CELLS=()
        ui_plain_cell "$kind" 6 "${COLOR[heading]}"; UI_CELLS+=("$REPLY")
        text=''; ui_enabled sessions id && text=${sid:+#$sid}; ui_plain_cell "$text" 8; UI_CELLS+=("$REPLY")
        ui_plain_cell "$place" 8; UI_CELLS+=("$REPLY")
        text=''; ui_enabled sessions user && text=$user; ui_plain_cell "$text" 13; UI_CELLS+=("$REPLY")
        text=''; ui_enabled sessions peer && text=$peer
        ui_enabled sessions state && text+=" [$state]"
        ui_plain_cell "$text" "${UI_COL_WIDTHS[4]}"; UI_CELLS+=("$REPLY"); ui_grid
        if [[ $MODE == verbose ]]; then
            if ui_enabled sessions peer && ((${#text}>UI_COL_WIDTHS[4])); then ui_text "Peer $peer"; fi
            if ui_enabled sessions user && ((${#user}>13)); then ui_text "User $user"; fi
        fi
    else
        text=$kind; ui_enabled sessions id && text+=" ${sid:+#$sid}"
        text+=" $place"; ui_enabled sessions user && text+=" $user"
        if ((UI_REMAIN<2)); then text+=' ...'; fi
        ui_row "$text" "${COLOR[heading]}"
        text=''; ui_enabled sessions peer && text=$peer
        ui_enabled sessions state && text+=" [$state]"
        [[ -z $text ]] || ui_row "$text"
    fi
}
ui_sessions() {
    local budget=$1 summary='' index shown=0 total=${MODEL[session_count]:-0} per=1 capacity
    ((TEXT_WIDTH>=60)) || per=2
    capacity=$(((budget>0 ? budget-1+per-1 : 0)/per)); ((capacity<=MAX_SESSIONS)) || capacity=$MAX_SESSIONS
    case ${MODEL[session_state]-} in
        ok|partial|fallback)
            summary="$total sessions / ${MODEL[session_users]:-?} users"
            ((total<=capacity)) || summary+=" +$((total-capacity))"
            [[ ${MODEL[session_state]} != partial ]] || summary+=' partial'
            [[ ${MODEL[session_source]-} != utmp ]] || summary+=' utmp' ;;
        *) summary=${MODEL[session_state]:-unavailable} ;;
    esac
    ui_begin sessions "$budget" "$summary"
    case ${MODEL[session_state]-} in ok|partial|fallback) ;; *) ui_row 'Session records unavailable.' "${COLOR[muted]}"; return ;; esac
    for index in "${ACT_SESSION_IDS[@]}"; do
        ((UI_REMAIN>0 && shown<MAX_SESSIONS)) || break
        ui_session_row "$index"; ((shown+=1))
    done
    ((total!=0)) || ui_row 'No session records in the available source.' "${COLOR[muted]}"
    if [[ $MODE == verbose ]]; then
        ((total<=shown)) || ui_row "$((total-shown)) additional sessions not shown." "${COLOR[muted]}"
        ui_text 'Session records do not prove an attached SSH/RDP client.' "${COLOR[muted]}"
    fi
}
ui_connections() {
    local budget=$1 summary index
    case ${MODEL[connection_state]-} in ok|partial) summary="${MODEL[tcp_established]:-?} TCP / ${MODEL[tcp_admin]:-?} admin" ;; *) summary=${MODEL[connection_state]:-unavailable} ;; esac
    ui_begin connections "$budget" "$summary"
    if ui_enabled connections records; then
        for index in "${ACT_CONN_IDS[@]}"; do ui_text "${ACT_CONN[$index.label]:-TCP}  ${ACT_CONN[$index.local]:-?}  <->  ${ACT_CONN[$index.peer]:-?}"; done
    fi
    if [[ $MODE == verbose ]]; then ui_text 'Port labels are hints; sockets do not identify authenticated users.' "${COLOR[muted]}"; fi
}
ui_attention() {
    local budget=$1 entry level message shade summary='' errors=0 warnings=0 infos=0 shown=0
    local -a entries=()
    for entry in "${ATTENTION[@]}"; do
        level=${entry%%|*}; ui_enabled attention "$level" || continue
        entries+=("$entry")
        case $level in ERROR) ((errors+=1)) ;; WARN) ((warnings+=1)) ;; *) ((infos+=1)) ;; esac
    done
    summary="E$errors W$warnings I$infos"; shade=${COLOR[ok]}
    if ((${#entries[@]}==0 && ${#ATTENTION[@]}>0)); then summary="${#ATTENTION[@]} hidden"; shade=${COLOR[muted]}; fi
    ((errors+warnings+infos==0)) || shade=${COLOR[muted]}
    ((warnings==0)) || shade=${COLOR[warn]}; ((errors==0)) || shade=${COLOR[error]}
    ui_begin attention "$budget" "$summary" "$shade"
    if ((${#entries[@]}==0)); then
        if ((${#ATTENTION[@]}==0)); then ui_row 'No configured alerts in collected scope.' "${COLOR[ok]}"
        else ui_row "${#ATTENTION[@]} notice(s) hidden by display settings." "${COLOR[muted]}"; fi
        return
    fi
    for entry in "${entries[@]}"; do
        ((shown<MAX_ATTENTION && UI_REMAIN>0)) || break; ((shown+=1))
        IFS='|' read -r level message <<<"$entry"
        if [[ $MODE == concise ]]; then
            case $message in 'Unit needs review: systemctl status -- '*) message="${message#'Unit needs review: systemctl status -- '}: inspect unit" ;; esac
        fi
        shade=${COLOR[muted]}; [[ $level != ERROR ]] || shade=${COLOR[error]}; [[ $level != WARN ]] || shade=${COLOR[warn]}
        if [[ $MODE == concise ]]; then ui_row "$level: $message" "$shade"
        else ui_text "$level: $message" "$shade"; fi
    done
    ((${#entries[@]}<=shown)) || ui_row "$(( ${#entries[@]}-shown )) additional notice(s) not shown." "${COLOR[muted]}"
}
ui_hints() {
    local budget=$1 entry label command note id summary='' candidate available
    local -a entries=()
    available=$((INNER-4-${#UI_SECTION_TITLE}-2))
    for entry in "${HINTS[@]}"; do
        ui_hint_parse "$entry"; id=$UI_HINT_ID; label=$UI_HINT_LABEL; command=$UI_HINT_COMMAND; note=$UI_HINT_NOTE
        ui_enabled hints "$id" || continue
        entries+=("$label|$command|$note")
        candidate="$summary${summary:+ | }$command"
        if ((${#candidate}<=available)); then summary=$candidate; fi
    done
    ui_begin hints "$budget" "$summary"
    ((budget>1)) || return
    for entry in "${entries[@]}"; do
        IFS='|' read -r label command note <<<"$entry"
        if [[ $MODE == verbose ]]; then
            ui_columns 2; ui_plain_cell "$label" "${UI_COL_WIDTHS[0]}" "${COLOR[heading]}"; UI_CELLS+=("$REPLY")
            ui_plain_cell "$note" "${UI_COL_WIDTHS[1]}" "${COLOR[muted]}"; UI_CELLS+=("$REPLY"); ui_grid
            ui_text "$command" "${COLOR[value]:-${COLOR[text]}}"
        else ui_value_cell "$TEXT_WIDTH" "$label" "$command" "${COLOR[value]:-${COLOR[text]}}"; ui_emit "$REPLY"; fi
    done
}

# ==================== 8. DISPLAY POLICY AND SECTION REGISTRY =================

# The registry is display policy, not collection policy. A hidden panel must not
# silently disable a resource/service warning. User data is never evaluated as code.
declare -A SECTION_RENDERER=() SECTION_BASE_ROWS=() SECTION_MIN_ROWS=() SECTION_MAX_ROWS=() UI_PLAN=()
UI_ITEM_KEYS=(header.title header.site header.host header.time
    system.identity system.domain system.addresses system.platform system.load system.pressure
    resources.memory resources.swap resources.compression resources.storage resources.filesystem_detail
    services.summary processes.cpu processes.rss processes.io processes.details
    sessions.id sessions.user sessions.peer sessions.state connections.records
    attention.ERROR attention.WARN attention.INFO)
UI_SECTION_TITLE='' UI_REGISTRY_READY=0
UI_HINT_ID='' UI_HINT_LABEL='' UI_HINT_COMMAND='' UI_HINT_NOTE=''

ui_hint_parse() {
    local entry=$1 a b c d
    IFS='|' read -r a b c d <<<"$entry"
    if [[ $entry == *'|'*'|'*'|'* ]]; then
        UI_HINT_ID=$a; UI_HINT_LABEL=$b; UI_HINT_COMMAND=$c; UI_HINT_NOTE=$d
    else
        UI_HINT_ID=$a; UI_HINT_LABEL=$a; UI_HINT_COMMAND=$b; UI_HINT_NOTE=$c
    fi
}

ui_registry_init() {
    local id title renderer base minimum maximum key value
    for id in "${!SECTION_SPEC[@]}"; do
        IFS='|' read -r title renderer base minimum maximum <<<"${SECTION_SPEC[$id]}"
        [[ $id =~ ^[a-z][a-z0-9_]*$ && $renderer =~ ^[a-z_][a-z0-9_]*$ ]] || return 2
        declare -F "$renderer" >/dev/null || return 2
        for value in "$base" "$minimum" "$maximum"; do
            [[ -n $value && ${#value} -le 5 && $value != *[!0123456789]* ]] || return 2
        done
        base=$((10#$base)); minimum=$((10#$minimum)); maximum=$((10#$maximum))
        ((minimum<=base && base<=maximum && maximum<=10000)) || return 2
        [[ ${SECTION_TITLE[$id]+set} ]] || SECTION_TITLE[$id]=$title
        SECTION_RENDERER[$id]=$renderer
        SECTION_BASE_ROWS[$id]=$base
        SECTION_MIN_ROWS[$id]=$minimum; SECTION_MAX_ROWS[$id]=$maximum
    done
    local -A seen=()
    for id in "${SECTIONS[@]}"; do
        [[ ${SECTION_SPEC[$id]+set} && ! ${seen[$id]+set} ]] || return 2
        seen[$id]=1
    done
    for key in "${!SECTION_ROWS[@]}"; do
        value=${SECTION_ROWS[$key]}
        case $key in
            concise.*|verbose.*) [[ ${SECTION_SPEC[${key#*.}]+set} ]] || return 2 ;;
            *) [[ ${SECTION_SPEC[$key]+set} ]] || return 2 ;;
        esac
        [[ -n $value && ${#value} -le 5 && $value != *[!0123456789]* ]] && ((10#$value<=10000)) || return 2
        SECTION_ROWS[$key]=$((10#$value))
    done
    for key in "${!SECTION_VISIBLE[@]}"; do
        [[ ${SECTION_SPEC[$key]+set} && ${SECTION_VISIBLE[$key]} =~ ^[01]$ ]] || return 2
    done
    for key in "${!ITEM_VISIBLE[@]}"; do
        [[ ${ITEM_VISIBLE[$key]} =~ ^[01]$ ]] && ui_item_known "$key" || return 2
    done
    UI_REGISTRY_READY=1
}

ui_item_enabled() {
    local section=$1 item=$2
    [[ ${ITEM_VISIBLE[$section.$item]-1} == 1 ]] || return 1
    case $section.$item in
        resources.swap) ((SHOW_SWAP)) ;;
        resources.compression) ((SHOW_COMPRESSION)) ;;
        system.pressure|resources.pressure) ((SHOW_PRESSURE)) ;;
        *) return 0 ;;
    esac
}

ui_section_enabled() {
    local id=$1 entry found=0
    [[ ${SECTION_VISIBLE[$id]-1} == 1 ]] || return 1
    [[ $id != attention ]] || ((SHOW_ATTENTION)) || return 1
    if [[ $id == hints ]]; then
        for entry in "${HINTS[@]}"; do
            ui_hint_parse "$entry"
            if [[ -n $UI_HINT_COMMAND ]] && ui_item_enabled hints "$UI_HINT_ID"; then found=1; break; fi
        done
        ((found)) || return 1
    fi
    ui_section_rows "$id"
    ((REPLY>0))
}

ui_section_rows() {
    local id=$1
    if [[ ${SECTION_ROWS[$id]+set} ]]; then REPLY=${SECTION_ROWS[$id]}
    elif [[ ${SECTION_ROWS[$MODE.$id]+set} ]]; then REPLY=${SECTION_ROWS[$MODE.$id]}
    elif [[ $MODE == concise ]]; then REPLY=${SECTION_BASE_ROWS[$id]}
    else REPLY=10000; fi
}

# The design engine consumes the same section callbacks and validated model.
# It changes presentation only: collection, ranking and metric formulas still
# have exactly one owner. Capturing happens in the engine's command-substitution
# subshell, so temporary widths and glyph choices cannot leak into other cards.
motd_view_detail() { printf '%s\n' "${SECTION_DETAIL[$1]:-$DETAIL}"; }

motd_view_summary() {
    case $1 in
        services) printf '%s\n' "${MODEL[svc_running]:-?} running / ${MODEL[svc_failed]:-?} failed" ;;
        processes) printf '%s\n' "${MODEL[process_count]:-?} tasks; CPU / RAM / I/O" ;;
        sessions) printf '%s\n' "${MODEL[session_count]:-?} sessions / ${MODEL[session_users]:-?} users" ;;
        resources) printf '%s\n' 'RAM / storage / swap' ;;
        connections) printf '%s\n' "${MODEL[tcp_established]:-?} TCP" ;;
        *) printf '%s\n' '' ;;
    esac
}

motd_view_limits() {
    local id=$1 cap required=0 unit
    local -A seen=()
    if [[ $id == processes ]]; then
        MV_MIN_ROWS=0
        for unit in cpu rss io; do ui_enabled processes "$unit" && ((MV_MIN_ROWS+=1)); done
        if (($2>=60)); then MV_MIN_ROWS=2; fi
    fi
    if [[ $id == services && $3 != brief ]]; then
        for unit in "${REQUIRED_UNITS[@]}"; do
            [[ ! ${seen[$unit]+set} ]] || continue; seen[$unit]=1; ((required+=1))
        done
        ((required<=MV_MIN_ROWS)) || MV_MIN_ROWS=$required
    fi
    ((MV_MAX_ROWS>=MV_MIN_ROWS)) || MV_MAX_ROWS=$MV_MIN_ROWS
    # Explicit historical SECTION_ROWS caps include the section's decoration.
    if [[ ${SECTION_ROWS[$id]+set} || ${SECTION_ROWS[$MODE.$id]+set} ]]; then
        ui_section_rows "$id"; cap=$REPLY
        motd_view_overhead "$id"; cap=$((cap-MV_OVERHEAD)); ((cap>=0)) || cap=0
        ((MV_MAX_ROWS<=cap)) || MV_MAX_ROWS=$cap
        ((MV_MIN_ROWS<=cap)) || MV_MIN_ROWS=$cap
    fi
}

motd_view_capture() {
    local id=$1 rows=$3 flavour=$4 TEXT_WIDTH=$2 INNER=$(($2 + 2)) COLS=$(($2 + 4))
    local UI_DESIGN_CAPTURE=1 UI_CAPTURE_SUMMARY='' UI_SECTION_TITLE=${SECTION_TITLE[$1]}
    local GLYPH_USED='#' GLYPH_FREE='.' kind pid memory disk summary=''
    local -a UI_CAPTURE_LINES=() UI_TASK_IDS=()
    MODEL[unicode]=0
    # A one-row section must contain an observation, never only a table header.
    if ((rows==1)); then
        case $id in
            system)
                if ui_enabled system identity; then summary="${MODEL[host]:-?} | up ${MODEL[uptime]:-?}"; fi
                if ui_enabled system platform; then summary+="${summary:+ | }${MODEL[os]:-?}"; fi
                if [[ -n $summary ]]; then printf '%s\n' "$summary"; return; fi ;;
            resources)
                if ui_enabled resources memory; then
                    summary='RAM unavailable'
                    ((${MODEL[mem_valid]:-0}==0)) || summary="RAM ${VIEW[mem_used]:-?}/${VIEW[mem_total]:-?}"
                fi
                if ui_enabled resources storage; then
                    disk="Disk ${MODEL[storage_state]:-unavailable}"
                    [[ ${MODEL[storage_state]-} != ok ]] || disk="Disk ${VIEW[storage_used]:-?}/${VIEW[storage_total]:-?}"
                    summary+="${summary:+ | }$disk"
                fi
                if [[ -n $summary ]]; then printf '%s\n' "$summary"; return; fi ;;
            services)
                if ((${#REQUIRED_UNITS[@]})); then
                    kind=${REQUIRED_UNITS[0]}; svc_state "$kind"
                    printf '%s\n' "Required $kind: $REPLY"; return
                fi
                if ui_enabled services summary; then
                    if [[ ${MODEL[svc_runtime_state]-} == ok ]]; then printf '%s\n' "${MODEL[svc_running]:-?} running; ${MODEL[svc_failed]:-?} failed"
                    else printf '%s\n' "Service state: ${MODEL[svc_runtime_state]:-unavailable}"; fi; return
                fi ;;
            processes|io)
                for kind in cpu rss io; do
                    if [[ $id == io ]]; then [[ $kind == io ]] || continue
                    else ui_enabled processes "$kind" || continue; fi
                    ui_task_ids "$kind"; pid=${UI_TASK_IDS[0]-}; ui_process_value "$kind" "$pid"
                    if [[ -n $pid ]]; then printf '%s\n' "$kind: $UI_PROCESS_LABEL $UI_PROCESS_VALUE"
                    else printf '%s\n' 'Process observation unavailable'; fi; return
                done ;;
            sessions)
                case ${MODEL[session_state]-} in ok|partial|fallback) printf '%s\n' "${MODEL[session_count]:-?} sessions / ${MODEL[session_users]:-?} users" ;;
                    *) printf '%s\n' "Sessions: ${MODEL[session_state]:-unavailable}" ;; esac; return ;;
            connections)
                case ${MODEL[connection_state]-} in ok|partial) printf '%s\n' "${MODEL[tcp_established]:-?} TCP / ${MODEL[tcp_admin]:-?} admin" ;;
                    *) printf '%s\n' "Connections: ${MODEL[connection_state]:-unavailable}" ;; esac; return ;;
        esac
    fi
    "${SECTION_RENDERER[$id]}" "$((rows + 1))"
    if ((${#UI_CAPTURE_LINES[@]})); then printf '%s\n' "${UI_CAPTURE_LINES[@]}"
    elif [[ -n $UI_CAPTURE_SUMMARY ]]; then printf '%s\n' "$UI_CAPTURE_SUMMARY"
    else printf '%s\n' 'No additional observations in this section.'; fi
}

render_adaptive() {
    local MODE=concise id memory='RAM unavailable' storage="Disk ${MODEL[storage_state]:-unavailable}"
    MV_SECTION_IDS=''
    for id in "${SECTIONS[@]}"; do ui_section_enabled "$id" && MV_SECTION_IDS+=" $id"; done
    MV_COLUMNS=${MODEL[columns]}; MV_ROWS_LIMIT=$COMPACT_ROWS
    MV_PRIORITY=${SECTION_PRIORITY[*]}; MV_COLOR=${MODEL[color]}; MV_UNICODE=${MODEL[unicode]}
    MV_TITLE=''; MV_SUBTITLE=''; MV_METRICS=''
    ui_enabled header title && MV_TITLE=$TITLE
    # Keep machine identity and uptime visible in every design's context row.
    # The demo marker leads the title so a long configured title cannot hide it.
    ((DEMO==0)) || MV_TITLE="DEMO${MV_TITLE:+ | }$MV_TITLE"
    if ui_enabled header host && ui_enabled system identity; then
        MV_SUBTITLE="${MODEL[host]:-?} | up ${MODEL[uptime]:-?}"
        MV_METRICS=$MV_SUBTITLE
    fi
    if ui_enabled header site && [[ -n $SITE_LABEL ]]; then MV_SUBTITLE+="${MV_SUBTITLE:+ | }$SITE_LABEL"; fi
    MV_SUBTITLE+="${MV_SUBTITLE:+ | }local observations"
    ((${MODEL[mem_valid]:-0}==0)) || memory="RAM ${VIEW[mem_used]:-?}/${VIEW[mem_total]:-?}"
    [[ ${MODEL[storage_state]-} != ok ]] || storage="DISK ${VIEW[storage_used]:-?}/${VIEW[storage_total]:-?}"
    if [[ " $MV_SECTION_IDS " == *' resources '* ]]; then
        ui_enabled resources memory && MV_METRICS+="${MV_METRICS:+ | }$memory"
        ui_enabled resources storage && MV_METRICS+="${MV_METRICS:+ | }$storage"
    fi
    if [[ " $MV_SECTION_IDS " == *' system '* ]] && ui_enabled system load; then
        MV_METRICS+="${MV_METRICS:+ | }load ${MODEL[load1]:-?}"
    fi
    [[ -n $MV_METRICS ]] || MV_METRICS='Selected local observations'
    OUTPUT=$(motd_design_render) || return $?
    OUTPUT+=$'\n'
}

ui_section_list() {
    local id state
    printf '%-13s %-9s %-7s %s\n' ID DISPLAY ROWS TITLE
    for id in "${SECTIONS[@]}"; do
        state=shown; ui_section_enabled "$id" || state=hidden
        ui_section_rows "$id"
        printf '%-13s %-9s %-7s %s\n' "$id" "$state" "$REPLY" "${SECTION_TITLE[$id]}"
    done
}

ui_item_list() {
    local key id entry
    for key in "${UI_ITEM_KEYS[@]}"; do
        printf '%-34s %s\n' "$key" "${ITEM_VISIBLE[$key]-1}"
    done
    for id in "${SERVICE_ROLE_ORDER[@]}"; do printf '%-34s %s\n' "services.$id" "${ITEM_VISIBLE[services.$id]-1}"; done
    for entry in "${HINTS[@]}"; do
        ui_hint_parse "$entry"
        printf '%-34s %s\n' "hints.$UI_HINT_ID" "${ITEM_VISIBLE[hints.$UI_HINT_ID]-1}"
    done
}

ui_item_known() {
    local key=$1 known section=${1%%.*} item=${1#*.} entry
    for known in "${UI_ITEM_KEYS[@]}"; do [[ $key != "$known" ]] || return 0; done
    case $section in
        services)
            [[ ${SERVICE_ROLE_UNITS[$item]+set} ]] && return 0
            case $item in *.service|*.socket|*.timer) return 0 ;; esac ;;
        hints)
            for entry in "${HINTS[@]}"; do
                ui_hint_parse "$entry"
                [[ $UI_HINT_ID != "$item" ]] || return 0
            done ;;
        header|system|resources|processes|sessions|connections|attention|io) ;;
        *) [[ ${SECTION_SPEC[$section]+set} && -n $item ]] && return 0 ;;
    esac
    return 1
}

ui_set_sections() {
    local action=$1 value=$2 id present key section
    local -a requested=()
    [[ $value != ,* && $value != *, && $value != *,,* ]] || return 2
    IFS=',' read -r -a requested <<<"$value"
    ((${#requested[@]})) || return 2
    if [[ $action == --sections ]]; then SECTIONS=(); fi
    for id in "${requested[@]}"; do
        [[ -n $id && ${SECTION_SPEC[$id]+set} ]] || return 2
        case $action in
            --sections) SECTIONS+=("$id") ;;
            --hide) SECTION_VISIBLE[$id]=0 ;;
            --show)
                SECTION_VISIBLE[$id]=1; present=0
                for key in "${SECTIONS[@]}"; do [[ $key != "$id" ]] || present=1; done
                ((present)) || SECTIONS+=("$id") ;;
        esac
    done
    ui_registry_init
}

ui_set_items() {
    local action=$1 value=$2 key section item enabled=0
    local -a requested=()
    [[ $action != --show-item ]] || enabled=1
    [[ $value != ,* && $value != *, && $value != *,,* ]] || return 2
    IFS=',' read -r -a requested <<<"$value"
    ((${#requested[@]})) || return 2
    for key in "${requested[@]}"; do
        section=${key%%.*}; item=${key#*.}
        [[ $key == *.* && -n $item ]] || return 2
        [[ $section == header || ${SECTION_SPEC[$section]+set} ]] || return 2
        ui_item_known "$key" || { printf 'Unknown display item: %s\n' "$key" >&2; return 2; }
        ITEM_VISIBLE[$key]=$enabled
    done
}
# END REGISTRY

clip_sgr_cell() {
    local text=$1 width=$2 remaining suffix='' prefix token out='' styled=0
    local pattern=$'\033''\[[0-9;]*m'
    ((width>0)) || { REPLY=''; return 0; }
    remaining=$width
    if ((width>=3)); then remaining=$((width-3)); suffix='...'; fi
    while [[ $text =~ $pattern ]]; do
        token=${BASH_REMATCH[0]}; prefix=${text%%"$token"*}
        if [[ -n $prefix ]] && ((${#prefix}>=remaining)); then
            out+=${prefix:0:remaining}; remaining=0; break
        fi
        out+="$prefix$token"; styled=1
        remaining=$((remaining-${#prefix})); text=${text#*"$token"}
    done
    if ((remaining>0)); then out+=${text:0:remaining}; fi
    REPLY=$out$suffix
    ((styled==0)) || REPLY+=$'\033[0m'
}

# ==================== 9. EXECUTION ===========================================
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then main "$@"; fi
