#!/usr/bin/env bash
# Host status: one portable Linux/Bash 4.3+ file. Install as update-motd.d/99-status.
# Read-only collectors run first; formatting uses builtins; one final stdout write.
# Keep the SETTINGS here; change LAYOUT below without changing collection code.

# =========================== 1. SETTINGS =====================================
MAX_WIDTH=80                    # Left aligned; never expand to fill a wide screen.
THEME=cyan                      # cyan | amber | mono; --plain also disables ANSI.
MOTD_FASTFETCH=1                 # Optional preface; --no-fastfetch for least work.
FASTFETCH_TIMEOUT=1s
SERVICE_TIMEOUT=0.5s
STORAGE_TIMEOUT=0.5s
RAM_WARN=85 RAM_CRITICAL=95      # Based on Total - Available, not cache occupancy.
DISK_WARN=90 DISK_CRITICAL=95    # Per-filesystem Used / (Used + Available).
SHOW_SWAP=1 SHOW_COMPRESSION=1 SHOW_ATTENTION=1
SECTIONS=(resources services hints attention)
GUI_SERVICE=lightdm              # One setting for both the check and GUI hints.

# A single ordered list controls service collection and visible order.
SERVICE_KEYS=(ssh rdp ftp tftp gui oom ollama)
declare -A SERVICE_UNIT=(
    [ssh]=ssh.service [rdp]=xrdp.service [ftp]=vsftpd.service
    [tftp]=tftpd-hpa.service [gui]="$GUI_SERVICE.service"
    [oom]=earlyoom.service [ollama]=ollama.service
)
declare -A SERVICE_LABEL=(
    [ssh]=SSH [rdp]=RDP [ftp]=FTP [tftp]=TFTP
    [gui]=GUI [oom]=EarlyOOM [ollama]=Ollama
)
declare -A SERVICE_GROUP=(
    [ssh]=Access [rdp]=Access [ftp]=Files [tftp]=Files
    [gui]=Local [oom]=Local [ollama]=AI
)
# These notes describe relationships, not a verified service/subsystem state.
declare -A SERVICE_NOTES=([Files]='SFTP via SSH')
# Empty = discover eligible local disk-backed filesystems mounted below /.
# Explicit paths override discovery, but unsupported/remote filesystems still skip.
STORAGE_MOUNTS=()

# One entry per hint: label | command or alternatives | optional short note.
# '/' between AI commands means alternatives, not a shell pipeline.
HINTS=(
    "GUI on|sudo systemctl start $GUI_SERVICE|"
    "GUI off|sudo systemctl stop $GUI_SERVICE|"
    'Terminal|tmux new -A -s codex|detach: Ctrl+B, D'
    'AI tools|codex / claude / ollama|if installed'
)
# Optional local notes. No file sourcing or remote lookups.
MESSAGES=()                     # Example: ('INFO|Backups run overnight.')

# Semantic colours: edit here without touching collection or layout.
declare -A COLOR_CODE=(
    [border]=36 [heading]='1;37' [other]='1;34' [cache]=36
    [compressed]=35 [free]=90 [reserved]=33 [ok]=32 [warn]='1;33'
    [error]='1;31' [muted]=90 [text]=37
)
DISK_COLOR_CODES=('1;34' 36 35 32 33 37)

# ======================= 2. COLLECTION / RAW MODEL ===========================
# MODEL contains plain facts in KiB, counters, state flags and raw strings.
# DISK[id.field] contains one entry per included filesystem, never per directory.
declare -A MODEL=() LOAD=() ACTIVE=() DISK=() COLOR=() VIEW=()
DISK_IDS=() ATTENTION=()
FASTFETCH_TEXT='' OUTPUT='' REPLY=''
DEMO=0 PLAIN=0 ASCII=0 WIDTH_OVERRIDE='' FETCH_OVERRIDE='' THEME_OVERRIDE=''
# These roots also allow deterministic fixtures; no environment variable sourcing.
PROC_ROOT=/proc SYS_ROOT=/sys

usage() {
    printf '%s\n' 'Usage: 99-status [--demo|--demo-alerts] [--width N] [--theme cyan|amber|mono]' \
        '                 [--plain] [--ascii] [--no-fastfetch|--with-fastfetch]'
}
parse_options() {
    while (($#)); do
        case $1 in
            --demo) DEMO=1; shift ;;
            --demo-alerts) DEMO=2; shift ;;
            --plain) PLAIN=1; shift ;;
            --ascii) ASCII=1; shift ;;
            --no-fastfetch) FETCH_OVERRIDE=0; shift ;;
            --with-fastfetch) FETCH_OVERRIDE=1; shift ;;
            --width)
                [[ ${2-} =~ ^[0-9]{1,5}$ ]] || { usage >&2; return 2; }
                WIDTH_OVERRIDE=$((10#$2)); ((WIDTH_OVERRIDE > 0)) || return 2
                shift 2 ;;
            --theme)
                case ${2-} in cyan|amber|mono) THEME_OVERRIDE=$2 ;; *) usage >&2; return 2 ;; esac
                shift 2 ;;
            --help) usage; return 3 ;;
            *) usage >&2; return 2 ;;
        esac
    done
}
collect_display_context() {
    local cols=$WIDTH_OVERRIDE size
    MODEL[color]=1; MODEL[unicode]=0
    if ((PLAIN)) || [[ -v NO_COLOR ]]; then MODEL[color]=0; fi
    [[ -z $THEME_OVERRIDE ]] || THEME=$THEME_OVERRIDE
    [[ $THEME != mono ]] || MODEL[color]=0
    if ((!ASCII)) && [[ $(LC_ALL=C.UTF-8 locale charmap 2>/dev/null) == UTF-8 ]]; then
        export LC_ALL=C.UTF-8; MODEL[unicode]=1
    fi
    if [[ -z $cols ]]; then
        size=$( { stty size </dev/tty; } 2>/dev/null); cols=${size##* }
        [[ $cols =~ ^[0-9]{1,5}$ && $cols != 0 ]] || cols=$(tput cols 2>/dev/null)
    fi
    [[ $cols =~ ^[0-9]{1,5}$ ]] || cols=80
    cols=$((10#$cols)); ((cols > 0)) || cols=80
    MODEL[terminal_columns]=$cols
    MODEL[columns]=$((cols < MAX_WIDTH ? cols : MAX_WIDTH))
    MODEL[fastfetch_enabled]=${FETCH_OVERRIDE:-$MOTD_FASTFETCH}
}
collect_fastfetch() {
    FASTFETCH_TEXT=''
    ((!DEMO && MODEL[fastfetch_enabled] && MODEL[terminal_columns] >= 76)) || return 0
    command -v fastfetch >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1 || return 0
    local pipe=false; ((MODEL[color])) || pipe=true
    FASTFETCH_TEXT=$(timeout --kill-after=0.1s "$FASTFETCH_TIMEOUT" \
        fastfetch --pipe "$pipe" </dev/null 2>/dev/null) || FASTFETCH_TEXT=''
}
collect_identity() {
    local addresses=''
    MODEL[host]=Unknown; MODEL[ip]=''
    [[ ! -r $PROC_ROOT/sys/kernel/hostname ]] || read -r 'MODEL[host]' <"$PROC_ROOT/sys/kernel/hostname"
    read -r _ _ 'MODEL[ip]' _ <<<"${SSH_CONNECTION-}"
    if [[ -z ${MODEL[ip]} ]] && command -v hostname >/dev/null 2>&1; then
        addresses=$(hostname -I 2>/dev/null); read -r 'MODEL[ip]' _ <<<"$addresses"
    fi
    [[ -n ${MODEL[ip]} ]] || MODEL[ip]=Unavailable
}

# Linux collectors: GNU df/timeout, optional systemd. No extra runtime files.
# Empty values mean unknown, never zero. All memory/disk quantities are KiB.
# No collector prints; the only child commands are bounded systemctl and df.
# PROC_ROOT / SYS_ROOT permit read-only fixtures without touching the host.
PROC_ROOT=${PROC_ROOT:-/proc}
SYS_ROOT=${SYS_ROOT:-/sys}
declare -A DISK SUBSTATE
declare -a DISK_IDS STORAGE_MOUNTS

run_bounded() {
    command -v timeout >/dev/null 2>&1 || return 127
    timeout --kill-after=0.2s "$@" </dev/null
}
collector_uint() {
    # Keep subsequent signed Bash arithmetic safe, even on malformed fixtures.
    [[ $1 =~ ^[0-9]{1,15}$ ]] || return 1
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

service_record() {
    local id=$1 load=$2 active=$3 sub=$4 names=$5 name
    local -a aliases=()
    [[ -n $id ]] || return 0
    read -r -a aliases <<<"$names"
    for name in "$id" "${aliases[@]}"; do
        LOAD[$name]=$load; ACTIVE[$name]=$active; SUBSTATE[$name]=$sub
    done
}
collect_services() {
    local key value id='' load='' active='' sub='' names='' output rc=0 unit
    local -a units=()
    local -A seen=()
    LOAD=(); ACTIVE=(); SUBSTATE=(); MODEL[services_state]=unavailable
    for key in "${SERVICE_KEYS[@]}"; do
        unit=${SERVICE_UNIT[$key]-}
        [[ -n $unit && ! ${seen[$unit]+set} ]] || continue
        units+=("$unit"); seen[$unit]=1
    done
    ((${#units[@]})) || { MODEL[services_state]=ok; return 0; }
    command -v systemctl >/dev/null 2>&1 || return 0
    output=$(run_bounded "${SERVICE_TIMEOUT:-0.5s}" systemctl show --no-pager \
        --property=Id,Names,LoadState,ActiveState,SubState -- "${units[@]}" 2>/dev/null) || rc=$?
    while IFS='=' read -r key value; do
        case $key in
            Id) id=$value ;; Names) names=$value ;; LoadState) load=$value ;;
            ActiveState) active=$value ;; SubState) sub=$value ;;
            '') service_record "$id" "$load" "$active" "$sub" "$names"
                id=''; load=''; active=''; sub=''; names='' ;;
        esac
    done <<<"$output"$'\n'
    MODEL[services_state]=ok
    for unit in "${units[@]}"; do
        case ${LOAD[$unit]-} in
            not-found|error|bad-setting) ;;
            '') MODEL[services_state]=partial ;;
            *) [[ -n ${ACTIVE[$unit]-} ]] || MODEL[services_state]=partial ;;
        esac
    done
    if ((rc == 124 || rc == 137)); then MODEL[services_state]=timeout
    elif ((rc && ! ${#LOAD[@]})); then MODEL[services_state]=unavailable; fi
    # A nonzero systemctl status can still contain complete not-found records.
}

collect_storage() {
    local line before after id parent dev root target options type source rest key index
    local total used avail output rc=0 skipped=0 shared=0 invalid=0
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
        --output=size,used,avail,target -- "${targets[@]}" 2>/dev/null) || rc=$?
    while IFS= read -r line; do
        [[ $line =~ ^[[:space:]]*([0-9]+)[[:space:]]+([0-9]+)[[:space:]]+(-?[0-9]+)[[:space:]]+(.*)$ ]] || continue
        total=${BASH_REMATCH[1]}; used=${BASH_REMATCH[2]}; avail=${BASH_REMATCH[3]}; target=${BASH_REMATCH[4]}
        if ! collector_uint "$total"; then invalid=1; continue; fi; total=$REPLY
        if ! collector_uint "$used"; then invalid=1; continue; fi; used=$REPLY
        if ! collector_uint "$avail"; then invalid=1; continue; fi; avail=$REPLY
        if ((total == 0 || used + avail > total)) || [[ ! ${devices[$target]+set} ]]; then invalid=1; continue; fi
        [[ ! ${seen_target[$target]+set} ]] || continue
        seen_target[$target]=1; id=${#DISK_IDS[@]}; DISK_IDS+=("$id")
        DISK[$id.target]=$target; DISK[$id.source]=${sources[$target]}; DISK[$id.fstype]=${types[$target]}
        DISK[$id.total_kib]=$total; DISK[$id.used_kib]=$used; DISK[$id.avail_kib]=$avail
        DISK[$id.reserved_kib]=$((total - used - avail)); DISK[$id.valid]=1
    done <<<"$output"
    MODEL[storage_count]=${#DISK_IDS[@]}; MODEL[storage_state]=ok
    if ((rc || invalid || skipped || shared || MODEL[storage_shared_pool] || ${#DISK_IDS[@]} != ${#targets[@]})); then
        MODEL[storage_state]=partial
    else MODEL[storage_complete]=1; fi
    if ((rc == 124 || rc == 137)); then MODEL[storage_state]=timeout
    elif ((rc && ! ${#DISK_IDS[@]})); then MODEL[storage_state]=unavailable; fi
}

collect_resources() { collect_memory; collect_swap; collect_zram; collect_zswap; collect_storage; }

# ==================== 3. DERIVE / VALIDATE THE SNAPSHOT =======================
# No repeated sampling. The few loops below make one pass over small record lists.
# The RAM categories are a derived allocation view, not per-process attribution.
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
    for id in "${DISK_IDS[@]}"; do
        disk_total=$((disk_total+${DISK[$id.total_kib]})); disk_used=$((disk_used+${DISK[$id.used_kib]}))
        disk_avail=$((disk_avail+${DISK[$id.avail_kib]})); disk_reserved=$((disk_reserved+${DISK[$id.reserved_kib]}))
    done
    MODEL[storage_total]=$disk_total; MODEL[storage_used]=$disk_used
    MODEL[storage_avail]=$disk_avail; MODEL[storage_reserved]=$disk_reserved
}
demo_model() {
    # Illustrative workload, not live measurements of Gunmetal. All components
    # deliberately nonzero so previews explain the colours and compressed pools.
    MODEL[host]=Gunmetal-Debian; MODEL[ip]=192.168.137.50
    MODEL[mem_total]=32830915; MODEL[mem_available]=23068672
    MODEL[mem_free]=15351843; MODEL[mem_buffers]=262144
    MODEL[mem_cached]=10223616; MODEL[mem_shmem]=524288
    MODEL[mem_sreclaimable]=524288
    MODEL[zram_pool_kib]=655360; MODEL[zram_original_kib]=2097152
    MODEL[zram_compressed_kib]=589824; MODEL[zram_count]=1; MODEL[zram_state]=ok
    MODEL[zswap_pool_kib]=0; MODEL[zswap_original_kib]=0; MODEL[zswap_state]=ok
    MODEL[swap_total]=33187430; MODEL[swap_free]=31090278
    MODEL[swap_zram_used]=2097152; MODEL[swap_other_used]=0; MODEL[swap_state]=ok
    MODEL[storage_state]=ok; MODEL[storage_skipped]=0
    DISK_IDS=(root home files)
    local id
    for id in root home files; do DISK[$id.fstype]=ext4; done
    DISK[root.target]=/; DISK[root.total_kib]=32841400; DISK[root.used_kib]=10139730; DISK[root.avail_kib]=21059500
    DISK[home.target]=/home; DISK[home.total_kib]=102414000; DISK[home.used_kib]=20080394; DISK[home.avail_kib]=77102906
    DISK[files.target]=/mnt/files; DISK[files.fstype]=exfat
    DISK[files.total_kib]=488374272; DISK[files.used_kib]=233811476; DISK[files.avail_kib]=254562796
    for id in "${DISK_IDS[@]}"; do
        DISK[$id.reserved_kib]=$((${DISK[$id.total_kib]}-${DISK[$id.used_kib]}-${DISK[$id.avail_kib]}))
    done
    LOAD=(); ACTIVE=()
    for id in "${SERVICE_KEYS[@]}"; do LOAD[${SERVICE_UNIT[$id]}]=loaded; ACTIVE[${SERVICE_UNIT[$id]}]=active; done
    ACTIVE[${SERVICE_UNIT[gui]}]=inactive
    ACTIVE[${SERVICE_UNIT[ollama]}]=inactive
    if ((DEMO == 2)); then
        ACTIVE[${SERVICE_UNIT[ftp]}]=failed
        DISK[root.used_kib]=30500000; DISK[root.avail_kib]=1100000
        DISK[root.reserved_kib]=$((32841400-30500000-1100000))
        MODEL[mem_available]=1048576
        MODEL[mem_free]=524288; MODEL[mem_cached]=786432
        MODEL[mem_shmem]=262144; MODEL[mem_buffers]=65536
        MODEL[mem_sreclaimable]=196608
    fi
}
collect_all() {
    collect_display_context
    collect_fastfetch                 # Capture preface before taking status samples.
    if ((DEMO)); then demo_model
    else
        collect_identity; collect_memory; collect_swap; collect_zram; collect_zswap
        collect_storage; collect_services
    fi
    derive_model
}

# ======================= 4. FORMAT / BUILD THE VIEW ===========================
# Builtins only from here onward: no system reads, command substitutions or tools.
repeat_char() { printf -v REPLY '%*s' "$2" ''; REPLY=${REPLY// /$1}; }
strip_ansi() {
    REPLY=$1; local pattern=$'\033''\[[0-9;]*m'
    while [[ $REPLY =~ $pattern ]]; do REPLY=${REPLY/"${BASH_REMATCH[0]}"/}; done
}
pad_cell() {
    local text=$1 width=$2 length
    strip_ansi "$text"; length=${#REPLY}
    if ((length > width)); then
        if ((width >= 3)); then text="${REPLY:0:width-3}..."; else text=${REPLY:0:width}; fi
        length=$width
    fi
    printf -v REPLY '%s%*s' "$text" "$((width-length))" ''
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
format_service() {
    local unit=${SERVICE_UNIT[$1]} state='?' color=${COLOR[warn]}
    case ${LOAD[$unit]-} in
        not-found) state=N/A; color=${COLOR[muted]} ;;
        error|bad-setting) state=FAIL; color=${COLOR[error]} ;;
        *) case ${ACTIVE[$unit]-} in
            active|reloading) state=ON; color=${COLOR[ok]} ;;
            inactive) state=OFF; color=${COLOR[muted]} ;;
            failed) state=FAIL; color=${COLOR[error]} ;;
            activating) state=START ;;
            deactivating) state=STOP ;;
        esac ;;
    esac
    VIEW[$1.state]=$state; REPLY=$color$state$RST
}
prepare_view() {
    local key id code i=0
    RST=''; COLOR=()
    [[ $THEME != amber ]] || COLOR_CODE[border]=33
    (( ! MODEL[color] )) || RST=$'\033[0m'
    for key in "${!COLOR_CODE[@]}"; do
        COLOR[$key]=''
        (( ! MODEL[color] )) || COLOR[$key]=$'\033['${COLOR_CODE[$key]}m
    done
    COLS=${MODEL[columns]}; INNER=$((COLS-2)); TEXT_WIDTH=$((INNER-2))
    if ((COLS < 24)); then INNER=$COLS; TEXT_WIDTH=$((COLS-1)); fi
    BORDER=${COLOR[border]}
    H='═'; V='║'; TL='╔'; TR='╗'; BL='╚'; BR='╝'; LEFT='╠'; RIGHT='╣'; DOWN='╦'; UP='╩'
    GLYPH_USED='█'; GLYPH_FREE='░'
    if ((!MODEL[unicode])); then
        H='='; V='|'; TL='+'; TR='+'; BL='+'; BR='+'; LEFT='+'; RIGHT='+'; DOWN='+'; UP='+'
        GLYPH_USED='#'; GLYPH_FREE='.'
    fi
    W1=26; W3=24; W2=$((COLS-W1-W3-4))
    repeat_char "$H" "$INNER"; RULE_FULL=$REPLY
    if ((COLS >= 80)); then
        repeat_char "$H" "$W1"; RULE1=$REPLY
        repeat_char "$H" "$W2"; RULE2=$REPLY
        repeat_char "$H" "$W3"; RULE3=$REPLY
    fi
    for key in mem_total mem_used mem_available mem_free mem_cache mem_compressed mem_other \
               swap_total swap_used swap_free swap_zram_used swap_other_used \
               zram_pool_kib zram_original_kib zswap_pool_kib zswap_original_kib; do
        format_number "${MODEL[$key]-}"; VIEW[$key]=$REPLY
    done
    VIEW[mem_percent]='?'
    if ((MODEL[mem_valid])); then printf -v 'VIEW[mem_percent]' '%d.%d' "$((MODEL[mem_tenths]/10))" "$((MODEL[mem_tenths]%10))"; fi
    for key in "${SERVICE_KEYS[@]}"; do format_service "$key"; VIEW[$key]=$REPLY; done
    for id in "${DISK_IDS[@]}"; do
        code=${DISK_COLOR_CODES[i%${#DISK_COLOR_CODES[@]}]}; VIEW[$id.color]=''
        (( ! MODEL[color] )) || VIEW[$id.color]=$'\033['${code}m
        human_kib "${DISK[$id.used_kib]}"; VIEW[$id.used]=$REPLY
        ((i+=1))
    done
    for key in storage_total storage_used storage_avail storage_reserved; do human_kib "${MODEL[$key]}"; VIEW[$key]=$REPLY; done
    prepare_attention
}
prepare_attention() {
    local key id percent denom note
    ATTENTION=("${MESSAGES[@]}")
    if ((MODEL[mem_valid])); then
        if ((MODEL[mem_tenths] >= RAM_CRITICAL*10)); then ATTENTION+=("ERROR|RAM available: ${VIEW[mem_available]} (${VIEW[mem_percent]}% unavailable).")
        elif ((MODEL[mem_tenths] >= RAM_WARN*10)); then ATTENTION+=("WARN|RAM available: ${VIEW[mem_available]} (${VIEW[mem_percent]}% unavailable)."); fi
    else ATTENTION+=('INFO|Memory counters unavailable.'); fi
    ((MODEL[mem_parts_valid])) || ATTENTION+=('INFO|RAM allocation breakdown unavailable.')
    for key in "${SERVICE_KEYS[@]}"; do
        [[ ${VIEW[$key.state]} != FAIL ]] || ATTENTION+=("ERROR|${SERVICE_LABEL[$key]} failed: ${SERVICE_UNIT[$key]}")
    done
    case ${MODEL[services_state]-ok} in
        ok) ;;
        timeout) ATTENTION+=('INFO|Service status query timed out.') ;;
        *) ATTENTION+=('INFO|Some service states are unavailable.') ;;
    esac
    case ${MODEL[storage_state]-unavailable} in
        ok) ;;
        partial) ATTENTION+=('INFO|Storage is incomplete; aggregate bar withheld.') ;;
        timeout) ATTENTION+=('INFO|Storage query timed out; no total shown.') ;;
        *) ATTENTION+=('INFO|Storage statistics unavailable.') ;;
    esac
    if ((${MODEL[storage_skipped]:-0}+${MODEL[storage_skipped_shared]:-0} > 0)); then ATTENTION+=('INFO|Shared-pool or unsupported storage omitted.'); fi
    for id in "${DISK_IDS[@]}"; do
        denom=$((${DISK[$id.used_kib]}+${DISK[$id.avail_kib]})); ((denom > 0)) || continue
        percent=$((${DISK[$id.used_kib]}*100/denom))
        if ((percent >= DISK_CRITICAL)); then ATTENTION+=("ERROR|${DISK[$id.target]}: $percent% of usable filesystem space used.")
        elif ((percent >= DISK_WARN)); then ATTENTION+=("WARN|${DISK[$id.target]}: $percent% of usable filesystem space used."); fi
    done
}
line() { OUTPUT+="$1"$'\n'; }
rule_full() { ((COLS < 24)) || line "$BORDER$1$RULE_FULL$2$RST"; }
row_full() {
    if ((COLS < 24)); then line "$1"; return; fi
    pad_cell "$1" "$INNER"; line "$BORDER$V$RST$REPLY$BORDER$V$RST"
}
row_three() {
    local row="$BORDER$V$RST"
    pad_cell "$1" "$W1"; row+=$REPLY$BORDER$V$RST
    pad_cell "$2" "$W2"; row+=$REPLY$BORDER$V$RST
    pad_cell "$3" "$W3"; row+=$REPLY$BORDER$V$RST
    line "$row"
}
section() { row_full " ${COLOR[heading]}$1$RST"; }
flow_items() {
    # Pack complete coloured items left to right; wrap between items, not labels.
    local row='' item length prefix=${FLOW_PREFIX-} continued=${FLOW_CONTINUE-}
    for item in "$@"; do
        strip_ansi "$prefix$row${row:+  }$item"; length=${#REPLY}
        if ((length > TEXT_WIDTH)) && [[ -n $row ]]; then
            row_full " $prefix$row"; prefix=$continued; row=''
        fi
        strip_ansi "$prefix$item"
        if ((${#REPLY} > TEXT_WIDTH)); then
            text_rows "$REPLY"; prefix=$continued; continue
        fi
        row+="${row:+  }$item"
    done
    [[ -z $row ]] || row_full " $prefix$row"
}
text_rows() {
    # Long plain notes/commands wrap completely instead of disappearing at a border.
    local text=$1 color=${2-} chunk cut width=$TEXT_WIDTH
    ((width > 0)) || width=20
    while ((${#text} > width)); do
        chunk=${text:0:width}; cut=${chunk% *}
        [[ $cut == "$chunk" || -z $cut ]] && cut=$chunk
        row_full " $color$cut$RST"; text=${text:${#cut}}; text=${text# }
    done
    row_full " $color$text$RST"
}
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

# ========================= 5. LAYOUT: EDIT HERE ===============================
render_memory() {
    local -a legend
    section MEMORY
    flow_items "Total ${VIEW[mem_total]}" "Available ${VIEW[mem_available]}" "In use ${VIEW[mem_percent]}%"
    if ((MODEL[mem_parts_valid])); then
        segmented_bar "${MODEL[mem_total]}" "${MODEL[mem_other]}" "${COLOR[other]}" O \
            "${MODEL[mem_cache]}" "${COLOR[cache]}" C "${MODEL[mem_compressed]}" "${COLOR[compressed]}" Z \
            "${MODEL[mem_free]}" "${COLOR[free]}" .
        row_full " $REPLY"
        flow_items "${COLOR[other]}Other ${VIEW[mem_other]}$RST" "${COLOR[cache]}Cache ${VIEW[mem_cache]}$RST" \
            "${COLOR[compressed]}Comp ${VIEW[mem_compressed]}$RST" "${COLOR[free]}Free ${VIEW[mem_free]}$RST"
    else row_full " ${COLOR[muted]}Allocation breakdown unavailable$RST"; fi
    if ((SHOW_COMPRESSION)); then
        if ((${MODEL[zram_count]:-0} > 0)); then
            flow_items "Zram: ${VIEW[zram_original_kib]} data" "${VIEW[zram_pool_kib]} RAM pool"
        fi
        if ((${MODEL[zswap_pool_kib]:-0} > 0)) || [[ ${MODEL[zswap_state]-} != ok && ${MODEL[zswap_state]-} != absent ]]; then
            flow_items "Zswap: ${VIEW[zswap_original_kib]} data" "${VIEW[zswap_pool_kib]} RAM pool"
        fi
    fi
    if ((SHOW_SWAP)); then
        if ((MODEL[swap_valid] && MODEL[swap_total] > 0)); then
            flow_items "Swap ${VIEW[swap_used]} / ${VIEW[swap_total]}" "Free ${VIEW[swap_free]}"
            if [[ ${MODEL[swap_state]-} == ok ]] &&
               ((${MODEL[swap_zram_used]:-0}+${MODEL[swap_other_used]:-0} == MODEL[swap_used])); then
                segmented_bar "${MODEL[swap_total]}" "${MODEL[swap_zram_used]}" "${COLOR[compressed]}" Z \
                    "${MODEL[swap_other_used]}" "${COLOR[other]}" O "${MODEL[swap_free]}" "${COLOR[free]}" .
                row_full " $REPLY"
                flow_items "${COLOR[compressed]}Zram ${VIEW[swap_zram_used]}$RST" "${COLOR[other]}Other swap ${VIEW[swap_other_used]}$RST"
            else
                segmented_bar "${MODEL[swap_total]}" "${MODEL[swap_used]}" "${COLOR[other]}" O "${MODEL[swap_free]}" "${COLOR[free]}" .
                row_full " $REPLY"
            fi
        elif ((MODEL[swap_valid])); then row_full ' Swap: not configured'
        else row_full ' Swap: unavailable'; fi
    fi
}
render_storage() {
    local id i=0 symbol
    local -a parts=() legend=()
    section 'STORAGE / LOCAL FILESYSTEMS'
    if [[ ${MODEL[storage_state]-} != ok ]]; then
        row_full " ${COLOR[muted]}Statistics ${MODEL[storage_state]:-unavailable}$RST"; return
    elif ((MODEL[storage_total] <= 0)); then
        text_rows 'No eligible local filesystems.' "${COLOR[muted]}"; return
    fi
    flow_items "Used ${VIEW[storage_used]} / ${VIEW[storage_total]}" "Available ${VIEW[storage_avail]}"
    for id in "${DISK_IDS[@]}"; do
        printf -v symbol '%d' "$((i%9+1))"
        parts+=("${DISK[$id.used_kib]}" "${VIEW[$id.color]}" "$symbol")
        if ((MODEL[color])); then legend+=("${VIEW[$id.color]}${DISK[$id.target]} ${VIEW[$id.used]}$RST")
        else legend+=("$symbol:${DISK[$id.target]} ${VIEW[$id.used]}"); fi
        ((i+=1))
    done
    parts+=("${MODEL[storage_reserved]}" "${COLOR[reserved]}" R "${MODEL[storage_avail]}" "${COLOR[free]}" .)
    segmented_bar "${MODEL[storage_total]}" "${parts[@]}"; row_full " $REPLY"
    flow_items "${legend[@]}"
    flow_items "${COLOR[reserved]}Reserved ${VIEW[storage_reserved]}$RST" "${COLOR[free]}Available ${VIEW[storage_avail]}$RST"
}
render_services() {
    local key group='' label state item prefix
    local -a items=()
    section SERVICES
    for key in "${SERVICE_KEYS[@]}"; do
        if [[ -n $group && $group != "${SERVICE_GROUP[$key]}" ]]; then
            [[ -z ${SERVICE_NOTES[$group]-} ]] || items+=("${COLOR[muted]}${SERVICE_NOTES[$group]}$RST")
            printf -v prefix '%-8s' "$group"
            FLOW_PREFIX="$prefix" FLOW_CONTINUE='        ' flow_items "${items[@]}"; items=()
        fi
        group=${SERVICE_GROUP[$key]}; label=${SERVICE_LABEL[$key]}; state=${VIEW[$key]}
        item="$label $state"; strip_ansi "$item"
        if ((${#REPLY} < 12)); then pad_cell "$item" 12; item=$REPLY; fi
        items+=("$item")
    done
    if [[ -n $group ]]; then
        [[ -z ${SERVICE_NOTES[$group]-} ]] || items+=("${COLOR[muted]}${SERVICE_NOTES[$group]}$RST")
        printf -v prefix '%-8s' "$group"
        FLOW_PREFIX="$prefix" FLOW_CONTINUE='        ' flow_items "${items[@]}"
    fi
}
render_hints() {
    local entry label command note text
    section HINTS
    for entry in "${HINTS[@]}"; do
        IFS='|' read -r label command note <<<"$entry"
        printf -v text '%-9s %s' "$label" "$command"
        text+="${note:+  ($note)}"
        if ((${#text} <= TEXT_WIDTH)); then row_full " $text"
        else
            text_rows "$label${note:+ ($note)}" "${COLOR[muted]}"
            text_rows "$command" "${COLOR[text]}"
        fi
    done
}
render_attention() {
    ((SHOW_ATTENTION && ${#ATTENTION[@]})) || return
    local entry level message color
    section ATTENTION
    for entry in "${ATTENTION[@]}"; do
        IFS='|' read -r level message <<<"$entry"; color=${COLOR[muted]}
        case $level in WARN) color=${COLOR[warn]} ;; ERROR) color=${COLOR[error]} ;; esac
        text_rows "$level: $message" "$color"
    done
}
render_status() {
    local section_name first=1
    OUTPUT=''; line ''
    if [[ -n $FASTFETCH_TEXT ]]; then line "$FASTFETCH_TEXT"; line ''; fi
    if ((COLS >= 80)); then
        line "$BORDER$TL$RULE1$DOWN$RULE2$DOWN$RULE3$TR$RST"
        row_three " ${COLOR[heading]}SYSTEM STATUS$RST" " Host: ${MODEL[host]}" " IP: ${MODEL[ip]}"
        line "$BORDER$LEFT$RULE1$UP$RULE2$UP$RULE3$RIGHT$RST"
    else
        rule_full "$TL" "$TR"
        row_full " ${COLOR[heading]}SYSTEM STATUS$RST"
        text_rows "Host: ${MODEL[host]}"; text_rows "IP: ${MODEL[ip]}"
        rule_full "$LEFT" "$RIGHT"
    fi
    for section_name in "${SECTIONS[@]}"; do
        [[ $section_name != attention ]] || ((SHOW_ATTENTION && ${#ATTENTION[@]})) || continue
        ((first)) || rule_full "$LEFT" "$RIGHT"; first=0
        case $section_name in
            resources) render_memory; render_storage ;;
            services) render_services ;;
            hints) render_hints ;;
            attention) render_attention ;;
        esac
    done
    rule_full "$BL" "$BR"; line ''
}

# ============================ 6. EXECUTION ===================================
main() {
    local rc=0
    parse_options "$@" || rc=$?
    ((rc != 3)) || return 0
    ((rc == 0)) || return "$rc"
    collect_all
    prepare_view
    render_status
    printf '%s' "$OUTPUT"
}
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then main "$@"; fi
