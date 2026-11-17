# Shared presentation engine for generated Unix outputs.
#
# This file only defines POSIX-shell functions. It is embedded once, before the
# chosen Unix backend. It never collects machine data, invokes a configured
# command, evaluates configuration as code, or writes persistent files.
#
# Backend adapters supply already-collected observations through
# motd_view_capture(section, content_columns, content_rows, flavour). The
# callback emits printable ASCII data rows; this engine owns framing, spacing,
# colour and Unicode borders. motd_view_detail(section) emits its detail policy.
# Keeping these policies here makes old Bash, dash and delegated Zsh layouts
# obey the same geometry rather than maintaining separate render algorithms.

motd_view_clean() {
    mv_clean_rest=$1; MV_CLEAN=''; mv_clean_count=0
    while [ -n "$mv_clean_rest" ] && [ "$mv_clean_count" -lt "$2" ]; do
        mv_clean_ch=${mv_clean_rest%"${mv_clean_rest#?}"}; mv_clean_rest=${mv_clean_rest#?}
        case "$mv_clean_ch" in [\ -~]) : ;; *) mv_clean_ch='?' ;; esac
        MV_CLEAN=$MV_CLEAN$mv_clean_ch; mv_clean_count=$((mv_clean_count + 1))
    done
    if [ -n "$mv_clean_rest" ] && [ "$2" -gt 0 ]; then MV_CLEAN=${MV_CLEAN%?}'~'; fi
}

motd_view_repeat() {
    MV_REPEAT=''; mv_repeat_left=$2
    while [ "$mv_repeat_left" -gt 0 ]; do
        MV_REPEAT=$MV_REPEAT$1; mv_repeat_left=$((mv_repeat_left - 1))
    done
}

motd_view_get() {
    MV_ALLOCATED=0
    for mv_get_record in $MV_PLAN; do
        if [ "${mv_get_record%%:*}" = "$1" ]; then MV_ALLOCATED=${mv_get_record#*:}; break; fi
    done
}

motd_view_set() {
    mv_set_result=''
    for mv_set_record in $MV_PLAN; do
        if [ "${mv_set_record%%:*}" = "$1" ]; then
            if [ "$2" -gt 0 ]; then mv_set_result="$mv_set_result $1:$2"; fi
        else mv_set_result="$mv_set_result $mv_set_record"; fi
    done
    MV_PLAN=$mv_set_result
}

motd_view_caption() {
    case "$1" in
        system) MV_CAPTION=SYSTEM; MV_HEADLINE='System' ;;
        resources) MV_CAPTION=RESOURCES; MV_HEADLINE='Capacity' ;;
        services) MV_CAPTION=SERVICES; MV_HEADLINE='Services' ;;
        processes) MV_CAPTION=PROCESSES; MV_HEADLINE='Top workloads' ;;
        sessions) MV_CAPTION=SESSIONS; MV_HEADLINE='People online' ;;
        connections) MV_CAPTION=CONNECTIONS; MV_HEADLINE='Connections' ;;
        attention) MV_CAPTION=ATTENTION; MV_HEADLINE='Attention' ;;
        hints) MV_CAPTION=HINTS; MV_HEADLINE='Useful commands' ;;
        io) MV_CAPTION='DISK I/O'; MV_HEADLINE='Disk activity' ;;
    esac
}

motd_view_content_width() {
    # Each backend formats at its final data width. We do not create a larger
    # table and crop it afterwards, including the headings in a briefing.
    MV_CONTENT_WIDTH=$((MV_PANEL_WIDTH - 2 - 2 * PADDING))
    case "$DESIGN" in
        ledger)
            mv_content_label=12; [ "$MV_COLUMNS" -ge 60 ] || mv_content_label=10
            MV_CONTENT_WIDTH=$((MV_COLUMNS - PADDING - mv_content_label - 3)) ;;
        briefing)
            motd_view_caption "$1"; mv_content_prefix=${#MV_HEADLINE}
            MV_CONTENT_WIDTH=$((MV_COLUMNS - mv_content_prefix - 2)) ;;
    esac
}

motd_view_footer() {
    MV_FOOTER=''; MV_FOOTER_COUNT=0
    [ -n "$MV_OMITTED" ] || return 0
    mv_footer_row='Hidden:'
    for mv_footer_id in $MV_OMITTED; do
        mv_footer_next="$mv_footer_row $mv_footer_id"; mv_footer_length=${#mv_footer_next}
        if [ "$mv_footer_length" -gt "$MV_FOOTER_WIDTH" ]; then
            MV_FOOTER="$MV_FOOTER$mv_footer_row
"; MV_FOOTER_COUNT=$((MV_FOOTER_COUNT + 1)); mv_footer_row=$mv_footer_id
        else mv_footer_row=$mv_footer_next; fi
    done
    MV_FOOTER="$MV_FOOTER$mv_footer_row
"; MV_FOOTER_COUNT=$((MV_FOOTER_COUNT + 1))
}

motd_view_cost() {
    # A dashboard pair costs the taller card, not the sum of its two cards.
    # Gaps, interior blank rows, borders, headers and omission text all count.
    motd_view_footer
    MV_COST=$((MV_HEADER_ROWS + MV_FOOTER_COUNT)); mv_cost_groups=0; mv_cost_pending=0
    for mv_cost_record in $MV_PLAN; do
        mv_cost_rows=${mv_cost_record#*:}
        case "$DESIGN" in
            classic) mv_cost_rows=$((mv_cost_rows + 1 + MV_INSET)) ;;
            cards|dashboard) mv_cost_rows=$((mv_cost_rows + 2 + MV_INSET)) ;;
            ledger|briefing) mv_cost_rows=$((mv_cost_rows + MV_INSET)) ;;
        esac
        if [ "$MV_COLUMNS_PER_ROW" -eq 2 ]; then
            if [ "$mv_cost_pending" -eq 0 ]; then mv_cost_pending=$mv_cost_rows; continue; fi
            if [ "$mv_cost_pending" -gt "$mv_cost_rows" ]; then mv_cost_rows=$mv_cost_pending; fi
            mv_cost_pending=0
        fi
        MV_COST=$((MV_COST + mv_cost_rows)); mv_cost_groups=$((mv_cost_groups + 1))
    done
    if [ "$mv_cost_pending" -gt 0 ]; then
        MV_COST=$((MV_COST + mv_cost_pending)); mv_cost_groups=$((mv_cost_groups + 1))
    fi
    if [ "$mv_cost_groups" -gt 1 ]; then MV_COST=$((MV_COST + (mv_cost_groups - 1) * MV_GAP)); fi
}

motd_view_plan() {
    MV_PLAN=''; MV_OMITTED=''; MV_REVERSE_PRIORITY=''; MV_ORDER=$MV_SECTION_IDS
    # Briefing explicitly leads with attention. Other layouts preserve the
    # configured display order. Priority influences allocation, not ordering.
    if [ "$DESIGN" = briefing ]; then
        MV_ORDER=''
        case " $MV_SECTION_IDS " in *' attention '*) MV_ORDER=attention ;; esac
        for mv_order_id in $MV_SECTION_IDS; do
            [ "$mv_order_id" = attention ] || MV_ORDER="$MV_ORDER $mv_order_id"
        done
    fi
    MV_PRIORITY_ORDER=''
    for mv_order_id in $MV_PRIORITY $MV_SECTION_IDS; do
        case " $MV_PRIORITY_ORDER " in *" $mv_order_id "*) continue ;; esac
        case " $MV_SECTION_IDS " in *" $mv_order_id "*)
            MV_PRIORITY_ORDER="$MV_PRIORITY_ORDER $mv_order_id"
            MV_REVERSE_PRIORITY="$mv_order_id $MV_REVERSE_PRIORITY" ;;
        esac
    done
    for mv_plan_id in $MV_ORDER; do
        mv_plan_detail=$(motd_view_detail "$mv_plan_id")
        case "$mv_plan_detail" in brief) mv_plan_rows=1 ;;
            full)
                case "$mv_plan_id" in system) mv_plan_rows=4 ;; resources) mv_plan_rows=7 ;;
                    services|sessions) mv_plan_rows=6 ;; processes|attention|io) mv_plan_rows=8 ;;
                    connections) mv_plan_rows=4 ;; hints) mv_plan_rows=5 ;; esac ;;
            *)
                case "$mv_plan_id" in resources|io) mv_plan_rows=3 ;; processes) mv_plan_rows=4 ;;
                    *) mv_plan_rows=2 ;; esac ;;
        esac
        # Charge populated rows, not an arbitrary rectangle of empty space.
        # This is formatting of the existing model, never a second collection.
        # A short section can therefore leave room for another complete panel.
        motd_view_content_width "$mv_plan_id"
        mv_plan_text=$(motd_view_capture "$mv_plan_id" "$MV_CONTENT_WIDTH" "$mv_plan_rows" "$DESIGN")
        mv_plan_count=0
        while [ -n "$mv_plan_text" ]; do
            mv_plan_count=$((mv_plan_count + 1))
            case "$mv_plan_text" in *'
'*) mv_plan_text=${mv_plan_text#*'
'} ;; *) mv_plan_text='' ;; esac
        done
        [ "$mv_plan_count" -gt 0 ] || mv_plan_count=1
        if [ "$mv_plan_count" -lt "$mv_plan_rows" ]; then mv_plan_rows=$mv_plan_count; fi
        MV_PLAN="$MV_PLAN $mv_plan_id:$mv_plan_rows"
    done
    motd_view_cost
    # Trim meaningful detail from low-priority sections before removing one.
    for mv_plan_id in $MV_REVERSE_PRIORITY; do
        motd_view_get "$mv_plan_id"
        while [ "$MV_COST" -gt "$MV_LIMIT" ] && [ "$MV_ALLOCATED" -gt 1 ]; do
            mv_plan_next=$((MV_ALLOCATED - 1)); motd_view_set "$mv_plan_id" "$mv_plan_next"
            motd_view_cost; motd_view_get "$mv_plan_id"
        done
    done
    for mv_plan_id in $MV_REVERSE_PRIORITY; do
        [ "$MV_COST" -gt "$MV_LIMIT" ] || break
        motd_view_get "$mv_plan_id"; [ "$MV_ALLOCATED" -gt 0 ] || continue
        # At an eight-row preview, decoration yields before the final useful
        # section. Spacing is always charged, never silently allowed to scroll.
        mv_plan_remaining=0
        for mv_plan_record in $MV_PLAN; do mv_plan_remaining=$((mv_plan_remaining + 1)); done
        if [ "$mv_plan_remaining" -eq 1 ]; then
            MV_GAP=0; MV_INSET=0; MV_SHORT_HEADER=1
            if [ "$DESIGN" = classic ]; then MV_HEADER_ROWS=2; else MV_HEADER_ROWS=1; fi
            motd_view_cost
            [ "$MV_COST" -gt "$MV_LIMIT" ] || break
        fi
        motd_view_set "$mv_plan_id" 0; MV_OMITTED="$MV_OMITTED $mv_plan_id"
        motd_view_cost
    done
}

motd_view_colors() {
    MV_ACCENT=''; MV_TITLE_COLOR=''; MV_MUTED=''; MV_WARN=''; MV_RESET=''
    [ "$MV_COLOR" -eq 1 ] || return 0
    case "$THEME" in green) mv_color_code=32 ;; amber) mv_color_code=33 ;; *) mv_color_code=36 ;; esac
    MV_RESET=$(printf '\033[0m'); MV_WARN=$(printf '\033[1;31m')
    MV_TITLE_COLOR=$(printf '\033[1;%sm' "$mv_color_code")
    case "$COLOR_EMPHASIS" in
        quiet) MV_TITLE_COLOR=$(printf '\033[%sm' "$mv_color_code") ;;
        vivid) MV_ACCENT=$(printf '\033[1;%sm' "$mv_color_code"); MV_MUTED=$(printf '\033[36m') ;;
        *) MV_ACCENT=$(printf '\033[%sm' "$mv_color_code"); MV_MUTED=$(printf '\033[90m') ;;
    esac
}

motd_view_plain_row() {
    motd_view_clean "$1" "$MV_COLUMNS"
    motd_view_tint "$1"
    printf '%s%s%s\n' "${MV_ROW_COLOR:-${2-}}" "$MV_CLEAN" "$MV_RESET"
}

motd_view_tint() {
    MV_ROW_COLOR=''
    # A phrase such as "0 failed" is not an alert. Colour explicit failing
    # states or severity labels rather than merely finding the word "failed".
    case "$1" in *ERROR:*|*WARNING:*|*WARN:*|*': failed'*|*' FAIL'*) MV_ROW_COLOR=$MV_WARN ;; esac
}

motd_view_rule() {
    # Results are already cell-padded before adding ANSI colour or Unicode.
    mv_rule_width=$1; mv_rule_left=$2; mv_rule_right=$3; mv_rule_title=$4
    if [ -n "$mv_rule_title" ]; then
        motd_view_clean "$mv_rule_title" "$((mv_rule_width - 4))"; mv_rule_title=$MV_CLEAN
        mv_rule_length=${#mv_rule_title}
        motd_view_repeat "$MV_H" "$((mv_rule_width - mv_rule_length - 4))"
        printf '%s%s %s %s%s%s\n' "$MV_ACCENT" "$mv_rule_left" "$mv_rule_title" "$MV_REPEAT" "$mv_rule_right" "$MV_RESET"
    else
        motd_view_repeat "$MV_H" "$((mv_rule_width - 2))"
        printf '%s%s%s%s%s\n' "$MV_ACCENT" "$mv_rule_left" "$MV_REPEAT" "$mv_rule_right" "$MV_RESET"
    fi
}

motd_view_box_row() {
    mv_box_width=$1; mv_box_text=$2; mv_box_inner=$((mv_box_width - 2 - 2 * PADDING))
    motd_view_clean "$mv_box_text" "$mv_box_inner"
    motd_view_tint "$mv_box_text"; mv_box_color=$MV_ROW_COLOR
    printf '%s%s%s%*s%s%-*s%s%*s%s%s%s\n' "$MV_ACCENT" "$MV_V" "$MV_RESET" "$PADDING" '' \
        "$mv_box_color" "$mv_box_inner" "$MV_CLEAN" "$MV_RESET" "$PADDING" '' "$MV_ACCENT" "$MV_V" "$MV_RESET"
}

motd_view_take_line() {
    # Parameter expansion keeps both old-shell execution and FIFO-free capture
    # deterministic. MV_TEXT is a newline-separated list of already-safe rows.
    MV_LINE=${MV_TEXT%%'
'*}
    case "$MV_TEXT" in *'
'*) MV_TEXT=${MV_TEXT#*'
'} ;; *) MV_TEXT='' ;; esac
}

motd_view_card() {
    mv_card_id=$1; mv_card_rows=$2; mv_card_width=$3; mv_card_height=${4-$2}
    motd_view_caption "$mv_card_id"
    motd_view_rule "$mv_card_width" "$MV_TL" "$MV_TR" "$MV_CAPTION"
    if [ "$MV_INSET" -gt 0 ]; then motd_view_box_row "$mv_card_width" ''; fi
    MV_TEXT=$(motd_view_capture "$mv_card_id" "$((mv_card_width - 2 - 2 * PADDING))" "$mv_card_rows" card)
    mv_card_index=0
    while [ "$mv_card_index" -lt "$mv_card_height" ]; do
        motd_view_take_line; motd_view_box_row "$mv_card_width" "$MV_LINE"
        mv_card_index=$((mv_card_index + 1))
    done
    motd_view_rule "$mv_card_width" "$MV_BL" "$MV_BR" ''
}

motd_view_gap() {
    mv_gap_left=$MV_GAP
    while [ "$mv_gap_left" -gt 0 ]; do
        if [ "$DESIGN" = classic ]; then motd_view_box_row "$MV_COLUMNS" ''; else printf '\n'; fi
        mv_gap_left=$((mv_gap_left - 1))
    done
}

motd_design_render() {
    MV_LIMIT=$((MV_ROWS_LIMIT - 1)); MV_SHORT_HEADER=0
    MV_HEADER_ROWS=2; MV_GAP=$SECTION_GAP; MV_INSET=0; MV_COLUMNS_PER_ROW=1
    [ "$DESIGN" != classic ] || MV_HEADER_ROWS=3
    case "$DENSITY" in
        comfortable) MV_GAP=$((MV_GAP + 1)); MV_INSET=1 ;;
        balanced) case "$DESIGN" in cards|briefing|dashboard) MV_GAP=$((MV_GAP + 1)) ;; esac ;;
    esac
    if [ "$DESIGN" = dashboard ] && [ "$MV_COLUMNS" -ge 80 ]; then MV_COLUMNS_PER_ROW=2; fi
    MV_PANEL_WIDTH=$MV_COLUMNS
    if [ "$MV_COLUMNS_PER_ROW" -eq 2 ]; then MV_PANEL_WIDTH=$(((MV_COLUMNS - 2) / 2)); fi
    MV_FOOTER_WIDTH=$MV_COLUMNS
    [ "$DESIGN" != classic ] || MV_FOOTER_WIDTH=$((MV_COLUMNS - 2 - 2 * PADDING))
    MV_H='-'; MV_V='|'; MV_TL='+'; MV_TR='+'; MV_ML='+'; MV_MR='+'; MV_BL='+'; MV_BR='+'
    if [ "$MV_UNICODE" -eq 1 ]; then
        MV_H='─'; MV_V='│'; MV_TL='┌'; MV_TR='┐'; MV_ML='├'; MV_MR='┤'; MV_BL='└'; MV_BR='┘'
    fi
    motd_view_colors; motd_view_plan
    case "$DESIGN" in
        classic)
            motd_view_rule "$MV_COLUMNS" "$MV_TL" "$MV_TR" "$MV_TITLE"
            [ "$MV_SHORT_HEADER" -eq 1 ] || motd_view_box_row "$MV_COLUMNS" "$MV_SUBTITLE" ;;
        briefing)
            motd_view_plain_row "$MV_TITLE / BRIEFING" "$MV_TITLE_COLOR"
            [ "$MV_SHORT_HEADER" -eq 1 ] || motd_view_plain_row "$MV_SUBTITLE" "$MV_MUTED" ;;
        dashboard)
            motd_view_plain_row "$MV_TITLE / DASHBOARD" "$MV_TITLE_COLOR"
            [ "$MV_SHORT_HEADER" -eq 1 ] || motd_view_plain_row "$MV_METRICS" "$MV_MUTED" ;;
        ledger)
            motd_view_plain_row "$MV_TITLE / LEDGER" "$MV_TITLE_COLOR"
            [ "$MV_SHORT_HEADER" -eq 1 ] || motd_view_plain_row 'SECTION       OBSERVATIONS' "$MV_MUTED" ;;
        cards)
            motd_view_plain_row "$MV_TITLE / CARDS" "$MV_TITLE_COLOR"
            [ "$MV_SHORT_HEADER" -eq 1 ] || motd_view_plain_row "$MV_SUBTITLE" "$MV_MUTED" ;;
    esac
    mv_render_first=1; mv_render_pending=''
    for mv_render_record in $MV_PLAN; do
        mv_render_id=${mv_render_record%%:*}; mv_render_rows=${mv_render_record#*:}
        if [ "$MV_COLUMNS_PER_ROW" -eq 2 ]; then
            if [ -z "$mv_render_pending" ]; then mv_render_pending=$mv_render_record; continue; fi
            [ "$mv_render_first" -eq 1 ] || motd_view_gap
            mv_render_height=${mv_render_pending#*:}
            if [ "$mv_render_rows" -gt "$mv_render_height" ]; then mv_render_height=$mv_render_rows; fi
            mv_render_left=$(motd_view_card "${mv_render_pending%%:*}" "${mv_render_pending#*:}" "$MV_PANEL_WIDTH" "$mv_render_height")
            mv_render_right=$(motd_view_card "$mv_render_id" "$mv_render_rows" "$MV_PANEL_WIDTH" "$mv_render_height")
            while [ -n "$mv_render_left" ] || [ -n "$mv_render_right" ]; do
                MV_TEXT=$mv_render_left; motd_view_take_line; mv_render_cell_left=$MV_LINE; mv_render_left=$MV_TEXT
                MV_TEXT=$mv_render_right; motd_view_take_line; mv_render_cell_right=$MV_LINE; mv_render_right=$MV_TEXT
                [ -n "$mv_render_cell_left" ] || mv_render_cell_left=$(printf '%*s' "$MV_PANEL_WIDTH" '')
                printf '%s  %s\n' "$mv_render_cell_left" "$mv_render_cell_right"
            done
            mv_render_pending=''; mv_render_first=0; continue
        fi
        [ "$mv_render_first" -eq 1 ] || motd_view_gap
        mv_render_first=0
        case "$DESIGN" in
            cards|dashboard) motd_view_card "$mv_render_id" "$mv_render_rows" "$MV_COLUMNS" ;;
            classic)
                motd_view_caption "$mv_render_id"
                motd_view_rule "$MV_COLUMNS" "$MV_ML" "$MV_MR" "$MV_CAPTION"
                [ "$MV_INSET" -eq 0 ] || motd_view_box_row "$MV_COLUMNS" ''
                MV_TEXT=$(motd_view_capture "$mv_render_id" "$((MV_COLUMNS - 2 - 2 * PADDING))" "$mv_render_rows" card)
                mv_render_index=0
                while [ "$mv_render_index" -lt "$mv_render_rows" ]; do
                    motd_view_take_line; motd_view_box_row "$MV_COLUMNS" "$MV_LINE"
                    mv_render_index=$((mv_render_index + 1))
                done ;;
            ledger|briefing)
                motd_view_caption "$mv_render_id"; mv_render_caption=$MV_CAPTION; mv_render_headline=$MV_HEADLINE
                mv_render_label_width=12; [ "$MV_COLUMNS" -ge 60 ] || mv_render_label_width=10
                motd_view_content_width "$mv_render_id"; mv_render_content_width=$MV_CONTENT_WIDTH
                MV_TEXT=$(motd_view_capture "$mv_render_id" "$mv_render_content_width" "$mv_render_rows" "$DESIGN")
                if [ "$DESIGN" = briefing ]; then
                    # A concise first sentence comes from the same one-row
                    # section adapter. Keep the first actual observation: it
                    # may be a service, address or session, not a heading.
                    # Only an identical summary or known table heading can
                    # be replaced. The row budget still bounds the result.
                    mv_render_head=$(motd_view_capture "$mv_render_id" "$mv_render_content_width" 1 briefing)
                    mv_render_first_line=${MV_TEXT%%'
'*}
                    if [ "$mv_render_first_line" = "$mv_render_head" ]; then
                        motd_view_take_line
                    else
                        case "$mv_render_id:$mv_render_first_line" in
                            processes:'CPU avg / PID name'*|io:'Disk I/O / '*) motd_view_take_line ;;
                        esac
                    fi
                    MV_TEXT="$mv_render_head
$MV_TEXT"
                fi
                mv_render_index=0
                [ "$MV_INSET" -eq 0 ] || printf '\n'
                while [ "$mv_render_index" -lt "$mv_render_rows" ]; do
                    motd_view_take_line
                    if [ "$DESIGN" = briefing ]; then
                        if [ "$mv_render_index" -eq 0 ]; then motd_view_plain_row "$mv_render_headline: $MV_LINE" "$MV_TITLE_COLOR"
                        else printf '%*s' "$((PADDING + 2))" ''; motd_view_clean "$MV_LINE" "$mv_render_content_width"; printf '%s\n' "$MV_CLEAN"; fi
                    else
                        motd_view_clean "$mv_render_caption" "$mv_render_label_width"; mv_render_label=$MV_CLEAN
                        motd_view_clean "$MV_LINE" "$mv_render_content_width"
                        motd_view_tint "$MV_LINE"
                        printf '%*s%s%-*s%s | %s%-*s%s\n' "$PADDING" '' "$MV_TITLE_COLOR" "$mv_render_label_width" "$mv_render_label" "$MV_RESET" "$MV_ROW_COLOR" "$mv_render_content_width" "$MV_CLEAN" "$MV_RESET"
                        mv_render_caption=''
                    fi
                    mv_render_index=$((mv_render_index + 1))
                done ;;
        esac
    done
    if [ -n "$mv_render_pending" ]; then
        [ "$mv_render_first" -eq 1 ] || motd_view_gap
        motd_view_card "${mv_render_pending%%:*}" "${mv_render_pending#*:}" "$MV_PANEL_WIDTH"
    fi
    MV_TEXT=$MV_FOOTER
    while [ -n "$MV_TEXT" ]; do
        motd_view_take_line; [ -n "$MV_LINE" ] || continue
        if [ "$DESIGN" = classic ]; then motd_view_box_row "$MV_COLUMNS" "$MV_LINE"
        else motd_view_plain_row "$MV_LINE" "$MV_MUTED"; fi
    done
    [ "$DESIGN" != classic ] || motd_view_rule "$MV_COLUMNS" "$MV_BL" "$MV_BR" ''
}
