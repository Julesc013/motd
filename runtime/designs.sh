# One data-only presentation engine for every generated Unix design.
# A design is a preset of orthogonal settings, resolved once before planning.
# Collectors and section formatters have no design branches and never run here.
# Content has conservative ASCII cell semantics; generated border glyphs are
# known single-cell Unicode. Only SGR colour escapes survive row sanitization.

# Raw template probes may omit generated labels. Standalone generated scripts
# override this callback with the configurator's one literal text registry.
motd_presentation_text() { if [ "$2" != note ]; then printf '%s\n' "$1"; fi; }

motd_view_clean() {
    mv_clean_rest=$1; MV_CLEAN=''; MV_LENGTH=0; mv_clean_before=''
    case "$mv_clean_rest" in *[!\ -~]*) : ;;
        *) if [ "${#mv_clean_rest}" -le "$2" ]; then MV_CLEAN=$mv_clean_rest; MV_LENGTH=${#mv_clean_rest}; return; fi ;;
    esac
    while [ -n "$mv_clean_rest" ]; do
        case "$mv_clean_rest" in "$MV_ESC"'['*)
            mv_clean_tail=${mv_clean_rest#??}; mv_clean_sgr=${mv_clean_tail%%m*}
            case "$mv_clean_tail" in *m*)
                case "$mv_clean_sgr" in *[!0-9\;]*) : ;;
                    *) if [ "${#mv_clean_sgr}" -le 32 ]; then
                        [ "$MV_COLOR" -eq 0 ] || MV_CLEAN=$MV_CLEAN$MV_ESC'['$mv_clean_sgr'm'
                        mv_clean_rest=${mv_clean_tail#*m}; continue
                    fi ;;
                esac ;;
            esac ;;
        esac
        mv_clean_ch=${mv_clean_rest%"${mv_clean_rest#?}"}; mv_clean_rest=${mv_clean_rest#?}
        case "$mv_clean_ch" in [\ -~]) : ;; *) mv_clean_ch='?' ;; esac
        if [ "$MV_LENGTH" -ge "$2" ]; then
            if [ "${OVERFLOW-ellipsis}" = ellipsis ] && [ "$2" -gt 0 ]; then MV_CLEAN=$mv_clean_before'~'; fi
            break
        fi
        mv_clean_before=$MV_CLEAN
        MV_CLEAN=$MV_CLEAN$mv_clean_ch; MV_LENGTH=$((MV_LENGTH + 1))
    done
}

motd_view_repeat() {
    MV_REPEAT=''; mv_repeat_left=$2; mv_repeat_piece=$1
    while [ "$mv_repeat_left" -gt 0 ]; do
        if [ "$((mv_repeat_left % 2))" -eq 1 ]; then MV_REPEAT=$MV_REPEAT$mv_repeat_piece; fi
        mv_repeat_left=$((mv_repeat_left / 2)); mv_repeat_piece=$mv_repeat_piece$mv_repeat_piece
    done
}
motd_view_fraction_bar() {
    # A bounded data-only formatter shared by both Unix adapters. Work in at
    # most six significant decimal digits before multiplication, keeping a
    # 240-cell bar within signed 32-bit arithmetic on old shells. The discarded
    # low digits are far smaller than one terminal cell. Callers supply the
    # original numeric observation in the label, so the bar is only a picture.
    MV_BAR=''; MV_BAR_VALID=0; mv_bar_total=$1; mv_bar_part=$2; mv_bar_width=$3
    case "$mv_bar_total" in ''|*[!0-9]*) return ;; esac
    case "$mv_bar_part" in ''|*[!0-9]*) return ;; esac
    while [ "${mv_bar_total#0}" != "$mv_bar_total" ] && [ "${#mv_bar_total}" -gt 1 ]; do mv_bar_total=${mv_bar_total#0}; done
    while [ "${mv_bar_part#0}" != "$mv_bar_part" ] && [ "${#mv_bar_part}" -gt 1 ]; do mv_bar_part=${mv_bar_part#0}; done
    [ "${#mv_bar_part}" -le "${#mv_bar_total}" ] || return
    if [ "${#mv_bar_part}" -eq "${#mv_bar_total}" ]; then
        # Validate before discarding low digits: a one-unit excess on a large
        # device is still invalid, even if both values round to the same bar.
        mv_bar_check_total=$mv_bar_total; mv_bar_check_part=$mv_bar_part
        while [ -n "$mv_bar_check_total" ]; do
            mv_bar_digit_total=${mv_bar_check_total%"${mv_bar_check_total#?}"}
            mv_bar_digit_part=${mv_bar_check_part%"${mv_bar_check_part#?}"}
            [ "$mv_bar_digit_part" -le "$mv_bar_digit_total" ] || return
            [ "$mv_bar_digit_part" -eq "$mv_bar_digit_total" ] || break
            mv_bar_check_total=${mv_bar_check_total#?}; mv_bar_check_part=${mv_bar_check_part#?}
        done
    fi
    while [ "${#mv_bar_total}" -gt 6 ]; do
        mv_bar_total=${mv_bar_total%?}; mv_bar_part=${mv_bar_part%?}; mv_bar_part=${mv_bar_part:-0}
    done
    [ "$mv_bar_total" -gt 0 ] && [ "$mv_bar_part" -le "$mv_bar_total" ] || return
    mv_bar_filled=$(((mv_bar_part * mv_bar_width + mv_bar_total / 2) / mv_bar_total))
    motd_view_repeat '#' "$mv_bar_filled"; MV_BAR=$MV_REPEAT
    motd_view_repeat '.' "$((mv_bar_width - mv_bar_filled))"; MV_BAR=$MV_BAR$MV_REPEAT
    MV_BAR_VALID=1
}


motd_view_policy() {
    # This is the sole named-preset dispatch. All subsequent code uses resolved
    # geometry and decoration values; cosmetic changes never select a renderer.
    MV_LAYOUT=stack; MV_FRAME=continuous; MV_HEADING=rule
    case "$DESIGN" in
        cards) MV_FRAME=separate ;;
        dashboard) MV_LAYOUT=columns; MV_FRAME=separate ;;
        ledger) MV_FRAME=none; MV_HEADING=inline ;;
        briefing) MV_FRAME=none; MV_HEADING=plain ;;
    esac
    [ "${PANEL_LAYOUT-auto}" = auto ] || MV_LAYOUT=$PANEL_LAYOUT
    [ "${PANEL_FRAME-auto}" = auto ] || MV_FRAME=$PANEL_FRAME
    [ "${HEADING_STYLE-auto}" = auto ] || MV_HEADING=$HEADING_STYLE
    MV_COLUMNS_PER_ROW=1
    if [ "$MV_LAYOUT" = columns ] && [ "$MV_COLUMNS" -ge 80 ]; then
        MV_COLUMNS_PER_ROW=2
        # Independent adjacent panels cannot share a continuous outer frame.
        [ "$MV_FRAME" != continuous ] || MV_FRAME=separate
    fi
    MV_PANEL_WIDTH=$MV_COLUMNS
    [ "$MV_COLUMNS_PER_ROW" -eq 1 ] || MV_PANEL_WIDTH=$(((MV_COLUMNS - 2) / 2))
    MV_OUTER=1; MV_SEPARATORS=1
    case "${BORDER_VISIBILITY-all}" in outer) MV_SEPARATORS=0 ;; sections) MV_OUTER=0 ;; none) MV_OUTER=0; MV_SEPARATORS=0 ;; esac
    [ "$MV_FRAME" != none ] || MV_OUTER=0
    MV_SIDES=$MV_OUTER
    MV_GAP=$SECTION_GAP; MV_INSET=0
    case "$DENSITY" in comfortable) MV_GAP=$((MV_GAP + 1)); MV_INSET=1 ;; esac
    MV_HEADER_ROWS=2
    if [ "$MV_FRAME" = continuous ] && [ "$MV_OUTER" -eq 1 ]; then MV_HEADER_ROWS=3; fi
    MV_FOOTER_WIDTH=$((MV_COLUMNS - 2 * PADDING - 2 * MV_SIDES))
    MV_H='-'; MV_V='|'; MV_TL='+'; MV_TR='+'; MV_ML='+'; MV_MR='+'; MV_BL='+'; MV_BR='+'
    if [ "$MV_UNICODE" -eq 1 ] && [ "${BORDER_STYLE-single}" != ascii ]; then
        MV_H='─'; MV_V='│'; MV_TL='┌'; MV_TR='┐'; MV_ML='├'; MV_MR='┤'; MV_BL='└'; MV_BR='┘'
        case "${BORDER_STYLE-single}" in
            rounded) MV_TL='╭'; MV_TR='╮'; MV_BL='╰'; MV_BR='╯' ;;
            double) MV_H='═'; MV_V='║'; MV_TL='╔'; MV_TR='╗'; MV_ML='╠'; MV_MR='╣'; MV_BL='╚'; MV_BR='╝' ;;
            heavy) MV_H='━'; MV_V='┃'; MV_TL='┏'; MV_TR='┓'; MV_ML='┣'; MV_MR='┫'; MV_BL='┗'; MV_BR='┛' ;;
        esac
    fi
}

motd_view_colors() {
    MV_ESC=$(printf '\033'); MV_ACCENT=''; MV_TITLE_COLOR=''; MV_MUTED=''; MV_WARN=''; MV_RESET=''
    [ "$MV_COLOR" -eq 1 ] || return 0
    case "$THEME" in green) mv_color_code=32 ;; amber) mv_color_code=33 ;; *) mv_color_code=36 ;; esac
    MV_RESET=$MV_ESC'[0m'; MV_WARN=$MV_ESC'[1;31m'
    MV_ACCENT=$MV_ESC'['$mv_color_code'm'; MV_TITLE_COLOR=$MV_ESC'[1;'$mv_color_code'm'; MV_MUTED=$MV_ESC'[90m'
    case "$COLOR_EMPHASIS" in quiet) MV_TITLE_COLOR=$MV_ACCENT; MV_ACCENT=''; MV_MUTED='' ;; vivid) MV_ACCENT=$MV_TITLE_COLOR ;; esac
}

motd_view_caption() {
    MV_CAPTION=$(motd_presentation_text "$1" "${LABEL_STYLE-full}")
    [ -n "$MV_CAPTION" ] || MV_CAPTION=$1
    MV_NOTE=''
    case "${SEPARATOR_TEXT-none}" in
        custom) MV_NOTE=$(motd_presentation_text "$1" note) ;;
        summary) MV_NOTE=$(motd_view_summary "$1") ;;
    esac
}

motd_view_content_width() {
    MV_CONTENT_WIDTH=$(($2 - 2 * PADDING - 2 * MV_SIDES))
    if [ "$MV_HEADING" = inline ]; then MV_CONTENT_WIDTH=$((MV_CONTENT_WIDTH - 13)); fi
    [ "$MV_CONTENT_WIDTH" -gt 0 ] || MV_CONTENT_WIDTH=1
}

motd_view_take_line() {
    MV_LINE=${MV_TEXT%%'
'*}
    case "$MV_TEXT" in *'
'*) MV_TEXT=${MV_TEXT#*'
'} ;; *) MV_TEXT='' ;; esac
}

motd_view_tint() {
    MV_ROW_COLOR=''
    case "$1" in *ERROR:*|*WARNING:*|*WARN:*|*': failed'*|*' FAIL'*) MV_ROW_COLOR=$MV_WARN ;; esac
}

motd_view_row() {
    # $3 controls exterior side glyphs. Visible width counts exclude SGR bytes.
    mv_row_width=$2; mv_row_sides=$3; mv_row_inner=$((mv_row_width - 2 * PADDING - 2 * mv_row_sides))
    motd_view_clean "$1" "$mv_row_inner"; motd_view_tint "$1"
    [ "$mv_row_sides" -eq 0 ] || printf '%s%s%s' "$MV_ACCENT" "$MV_V" "$MV_RESET"
    printf '%*s%s%s%s%*s%*s' "$PADDING" '' "${4-$MV_ROW_COLOR}" "$MV_CLEAN" "$MV_RESET" "$((mv_row_inner - MV_LENGTH))" '' "$PADDING" ''
    [ "$mv_row_sides" -eq 0 ] || printf '%s%s%s' "$MV_ACCENT" "$MV_V" "$MV_RESET"
    printf '\n'
}

motd_view_rule() {
    # A heading can be centered independently of the border character family.
    mv_rule_width=$1; mv_rule_left=$2; mv_rule_right=$3; mv_rule_label=$4
    mv_rule_inside=$((mv_rule_width - 2))
    if [ -n "$mv_rule_label" ]; then
        motd_view_clean "$mv_rule_label" "$((mv_rule_inside - 2))"; mv_rule_label=" $MV_CLEAN "; mv_rule_length=$((MV_LENGTH + 2))
    else mv_rule_length=0; fi
    mv_rule_spare=$((mv_rule_inside - mv_rule_length)); mv_rule_before=0
    case "${HEADING_ALIGN-left}" in center) mv_rule_before=$((mv_rule_spare / 2)) ;; right) mv_rule_before=$mv_rule_spare ;; esac
    motd_view_repeat "$MV_H" "$mv_rule_before"; mv_rule_prefix=$MV_REPEAT
    motd_view_repeat "$MV_H" "$((mv_rule_spare - mv_rule_before))"
    printf '%s%s%s%s%s%s%s\n' "$MV_ACCENT" "$mv_rule_left" "$mv_rule_prefix" "$mv_rule_label" "$MV_REPEAT" "$mv_rule_right" "$MV_RESET"
}

motd_view_plain_heading() {
    motd_view_clean "$1" "$(($2 - 2 * PADDING - 2 * MV_SIDES))"
    mv_heading_text=$MV_CLEAN; mv_heading_space=$(($2 - 2 * PADDING - 2 * MV_SIDES - MV_LENGTH))
    case "${HEADING_ALIGN-left}" in
        center) mv_heading_space=$((mv_heading_space / 2)) ;;
        right) : ;;
        *) mv_heading_space=0 ;;
    esac
    motd_view_repeat ' ' "$mv_heading_space"
    motd_view_row "$MV_REPEAT$mv_heading_text" "$2" "$MV_SIDES" "$MV_TITLE_COLOR"
}

motd_view_overhead() {
    MV_OVERHEAD=$MV_INSET
    # A separate closed panel has top+bottom; the title may occupy its top.
    if [ "$MV_FRAME" = separate ] && [ "$MV_OUTER" -eq 1 ]; then MV_OVERHEAD=$((MV_OVERHEAD + 2)); fi
    case "$MV_HEADING" in
        rule)
            if [ "$MV_FRAME" != separate ] || [ "$MV_OUTER" -eq 0 ]; then MV_OVERHEAD=$((MV_OVERHEAD + 1)); fi ;;
        plain) MV_OVERHEAD=$((MV_OVERHEAD + 1)) ;;
    esac
    # Rule headings carry metadata on their same row. Other heading styles
    # use an explicit note row, whose cost is measured before allocation.
    case " $MV_NOTE_IDS " in *" $1 "*)
        [ "$MV_HEADING" = rule ] || MV_OVERHEAD=$((MV_OVERHEAD + 1)) ;;
    esac
}

motd_view_get() {
    MV_ALLOCATED=0; MV_MINIMUM=1; MV_PRESENT=0
    for mv_get_record in $MV_PLAN; do
        if [ "${mv_get_record%%:*}" = "$1" ]; then MV_ALLOCATED=${mv_get_record#*:}; MV_PRESENT=1; break; fi
    done
    for mv_get_record in $MV_MINIMA; do
        if [ "${mv_get_record%%:*}" = "$1" ]; then MV_MINIMUM=${mv_get_record#*:}; break; fi
    done
}

motd_view_set() {
    mv_set_result=''
    for mv_set_record in $MV_PLAN; do
        if [ "${mv_set_record%%:*}" = "$1" ]; then
            [ "$2" -lt 0 ] || mv_set_result="$mv_set_result $1:$2"
        else mv_set_result="$mv_set_result $mv_set_record"; fi
    done
    MV_PLAN=$mv_set_result
}

motd_view_footer() {
    MV_FOOTER=''; MV_FOOTER_COUNT=0
    [ -n "$MV_OMITTED" ] || return 0
    mv_footer_row='Hidden:'
    for mv_footer_id in $MV_OMITTED; do
        mv_footer_next="$mv_footer_row $mv_footer_id"
        if [ "${#mv_footer_next}" -gt "$MV_FOOTER_WIDTH" ]; then
            MV_FOOTER="$MV_FOOTER$mv_footer_row
"; MV_FOOTER_COUNT=$((MV_FOOTER_COUNT + 1)); mv_footer_row=$mv_footer_id
        else mv_footer_row=$mv_footer_next; fi
    done
    MV_FOOTER="$MV_FOOTER$mv_footer_row
"; MV_FOOTER_COUNT=$((MV_FOOTER_COUNT + 1))
}

motd_view_cost() {
    motd_view_footer
    MV_COST=$((MV_HEADER_ROWS + MV_FOOTER_COUNT)); mv_cost_groups=0; mv_cost_pending=0
    for mv_cost_record in $MV_PLAN; do
        motd_view_overhead "${mv_cost_record%%:*}"
        mv_cost_rows=$((${mv_cost_record#*:} + MV_OVERHEAD))
        if [ "$MV_COLUMNS_PER_ROW" -eq 2 ]; then
            if [ "$mv_cost_pending" -eq 0 ]; then mv_cost_pending=$mv_cost_rows; continue; fi
            [ "$mv_cost_pending" -le "$mv_cost_rows" ] || mv_cost_rows=$mv_cost_pending
            mv_cost_pending=0
        fi
        MV_COST=$((MV_COST + mv_cost_rows)); mv_cost_groups=$((mv_cost_groups + 1))
    done
    if [ "$mv_cost_pending" -gt 0 ]; then MV_COST=$((MV_COST + mv_cost_pending)); mv_cost_groups=$((mv_cost_groups + 1)); fi
    [ "$mv_cost_groups" -lt 2 ] || MV_COST=$((MV_COST + (mv_cost_groups - 1) * MV_GAP))
}

motd_view_plan() {
    MV_PLAN=''; MV_MINIMA=''; MV_OMITTED=''; MV_REVERSE_PRIORITY=''
    MV_ORDER=$MV_SECTION_IDS; MV_PRIORITY_ORDER=''; MV_NOTE_IDS=''
    if [ "${SEPARATOR_TEXT-none}" != none ]; then
        for mv_note_id in $MV_ORDER; do
            motd_view_caption "$mv_note_id"
            [ -z "$MV_NOTE" ] || MV_NOTE_IDS="$MV_NOTE_IDS $mv_note_id"
        done
    fi
    for mv_plan_id in $MV_PRIORITY $MV_SECTION_IDS; do
        case " $MV_PRIORITY_ORDER " in *" $mv_plan_id "*) continue ;; esac
        case " $MV_SECTION_IDS " in *" $mv_plan_id "*)
            MV_PRIORITY_ORDER="$MV_PRIORITY_ORDER $mv_plan_id"
            MV_REVERSE_PRIORITY="$mv_plan_id $MV_REVERSE_PRIORITY" ;;
        esac
    done
    for mv_plan_id in $MV_ORDER; do
        mv_plan_detail=$(motd_view_detail "$mv_plan_id")
        case "$mv_plan_detail" in
            brief) MV_MAX_ROWS=1 ;;
            full) case "$mv_plan_id" in resources|io|processes|services) MV_MAX_ROWS=12 ;; *) MV_MAX_ROWS=8 ;; esac ;;
            *) case "$mv_plan_id" in resources|services|processes|io) MV_MAX_ROWS=4 ;; *) MV_MAX_ROWS=2 ;; esac ;;
        esac
        if [ "$mv_plan_id" = resources ] && [ "${BAR_LAYOUT-inline}" = wide ] && [ "$mv_plan_detail" != brief ]; then MV_MAX_ROWS=9; fi
        MV_MIN_ROWS=1
        motd_view_content_width "$mv_plan_id" "$MV_PANEL_WIDTH"
        motd_view_limits "$mv_plan_id" "$MV_CONTENT_WIDTH" "$mv_plan_detail"
        [ "$MV_MAX_ROWS" -ge "$MV_MIN_ROWS" ] || MV_MAX_ROWS=$MV_MIN_ROWS
        if [ "$MV_MAX_ROWS" -eq 0 ]; then
            MV_PLAN="$MV_PLAN $mv_plan_id:0"; MV_MINIMA="$MV_MINIMA $mv_plan_id:0"; continue
        fi
        mv_plan_text=$(motd_view_capture "$mv_plan_id" "$MV_CONTENT_WIDTH" "$MV_MAX_ROWS" section)
        mv_plan_count=0
        while [ -n "$mv_plan_text" ]; do
            mv_plan_count=$((mv_plan_count + 1))
            case "$mv_plan_text" in *'
'*) mv_plan_text=${mv_plan_text#*'
'} ;; *) mv_plan_text='' ;; esac
        done
        [ "$mv_plan_count" -gt 0 ] || mv_plan_count=1
        [ "$mv_plan_count" -ge "$MV_MAX_ROWS" ] || MV_MAX_ROWS=$mv_plan_count
        [ "$MV_MIN_ROWS" -le "$MV_MAX_ROWS" ] || MV_MIN_ROWS=$MV_MAX_ROWS
        MV_PLAN="$MV_PLAN $mv_plan_id:$MV_MAX_ROWS"; MV_MINIMA="$MV_MINIMA $mv_plan_id:$MV_MIN_ROWS"
    done
    motd_view_cost
    for mv_plan_id in $MV_REVERSE_PRIORITY; do
        motd_view_get "$mv_plan_id"
        while [ "$MV_COST" -gt "$MV_LIMIT" ] && [ "$MV_ALLOCATED" -gt "$MV_MINIMUM" ]; do
            motd_view_set "$mv_plan_id" "$((MV_ALLOCATED - 1))"; motd_view_cost; motd_view_get "$mv_plan_id"
        done
    done
    for mv_plan_id in $MV_REVERSE_PRIORITY; do
        [ "$MV_COST" -gt "$MV_LIMIT" ] || break
        motd_view_get "$mv_plan_id"; [ "$MV_PRESENT" -eq 1 ] || continue
        mv_plan_remaining=0
        for mv_remaining_record in $MV_PLAN; do mv_plan_remaining=$((mv_plan_remaining + 1)); done
        if [ "$mv_plan_remaining" -eq 1 ]; then
            MV_GAP=0; MV_INSET=0; MV_SHORT_HEADER=1; MV_HEADER_ROWS=1
            if [ "$MV_FRAME" = continuous ] && [ "$MV_OUTER" -eq 1 ]; then MV_HEADER_ROWS=2; fi
            motd_view_cost
            [ "$MV_COST" -gt "$MV_LIMIT" ] || break
        fi
        motd_view_set "$mv_plan_id" -1; MV_OMITTED="$MV_OMITTED $mv_plan_id"; motd_view_cost
    done
    # At tiny sizes, the named omission list can exceed available rows by
    # itself. Replace it with a truthful count while preserving the prompt row.
    if [ "$MV_COST" -gt "$MV_LIMIT" ]; then
        mv_plan_omitted=0; for mv_plan_id in $MV_OMITTED; do mv_plan_omitted=$((mv_plan_omitted + 1)); done
        MV_FOOTER="Hidden: $mv_plan_omitted sections; resize for more."
        MV_FOOTER_COUNT=1
    fi
}

motd_view_panel() {
    # The sole section compositor. Each panel reads the same collector-owned
    # observations at its final width; headings/notes/borders consume real rows.
    mv_panel_id=$1; mv_panel_rows=$2; mv_panel_width=$3; mv_panel_height=${4-0}
    motd_view_caption "$mv_panel_id"; mv_panel_caption=$MV_CAPTION; mv_panel_note=$MV_NOTE
    mv_panel_label=$mv_panel_caption
    [ -z "$mv_panel_note" ] || mv_panel_label="$mv_panel_label | $mv_panel_note"
    if [ "$MV_FRAME" = separate ] && [ "$MV_OUTER" -eq 1 ]; then
        if [ "$MV_HEADING" = rule ]; then motd_view_rule "$mv_panel_width" "$MV_TL" "$MV_TR" "$mv_panel_label"
        else motd_view_rule "$mv_panel_width" "$MV_TL" "$MV_TR" ''; fi
    fi
    case "$MV_HEADING" in
        rule)
            if [ "$MV_FRAME" != separate ] || [ "$MV_OUTER" -eq 0 ]; then
                if [ "$MV_SEPARATORS" -eq 1 ]; then
                    mv_panel_left=$MV_ML; mv_panel_right=$MV_MR
                    if [ "$MV_SIDES" -eq 0 ]; then mv_panel_left=$MV_H; mv_panel_right=$MV_H; fi
                    motd_view_rule "$mv_panel_width" "$mv_panel_left" "$mv_panel_right" "$mv_panel_label"
                else motd_view_plain_heading "$mv_panel_label" "$mv_panel_width"; fi
            fi ;;
        plain) motd_view_plain_heading "$mv_panel_caption" "$mv_panel_width" ;;
    esac
    if [ -n "$mv_panel_note" ] && [ "$MV_HEADING" != rule ]; then motd_view_row "$mv_panel_note" "$mv_panel_width" "$MV_SIDES" "$MV_MUTED"; fi
    [ "$MV_INSET" -eq 0 ] || motd_view_row '' "$mv_panel_width" "$MV_SIDES"
    motd_view_content_width "$mv_panel_id" "$mv_panel_width"
    MV_TEXT=$(motd_view_capture "$mv_panel_id" "$MV_CONTENT_WIDTH" "$mv_panel_rows" section)
    mv_panel_index=0
    while [ "$mv_panel_index" -lt "$mv_panel_rows" ]; do
        motd_view_take_line
        if [ "$MV_HEADING" = inline ]; then
            mv_panel_prefix=''
            [ "$mv_panel_index" -ne 0 ] || mv_panel_prefix=$mv_panel_caption
            motd_view_clean "$mv_panel_prefix" 10
            mv_panel_prefix=$(printf '%s%*s' "$MV_CLEAN" "$((10 - MV_LENGTH))" '')
            MV_LINE="$MV_TITLE_COLOR$mv_panel_prefix$MV_RESET | $MV_LINE"
        fi
        motd_view_row "$MV_LINE" "$mv_panel_width" "$MV_SIDES"
        mv_panel_index=$((mv_panel_index + 1))
    done
    # Pair alignment expands only whitespace; data budgets remain independent.
    motd_view_overhead "$mv_panel_id"
    mv_panel_size=$((mv_panel_rows + MV_OVERHEAD))
    while [ "$mv_panel_size" -lt "$mv_panel_height" ]; do
        motd_view_row '' "$mv_panel_width" "$MV_SIDES"; mv_panel_size=$((mv_panel_size + 1))
    done
    if [ "$MV_FRAME" = separate ] && [ "$MV_OUTER" -eq 1 ]; then motd_view_rule "$mv_panel_width" "$MV_BL" "$MV_BR" ''; fi
}

motd_view_gap() {
    mv_gap_left=$MV_GAP
    while [ "$mv_gap_left" -gt 0 ]; do
        mv_gap_sides=0; [ "$MV_FRAME" != continuous ] || mv_gap_sides=$MV_SIDES
        motd_view_row '' "$MV_COLUMNS" "$mv_gap_sides"; mv_gap_left=$((mv_gap_left - 1))
    done
}

motd_design_render() {
    MV_LIMIT=$((MV_ROWS_LIMIT - 1)); MV_SHORT_HEADER=0
    motd_view_policy; motd_view_colors; motd_view_plan
    if [ "$MV_FRAME" = continuous ] && [ "$MV_OUTER" -eq 1 ]; then motd_view_rule "$MV_COLUMNS" "$MV_TL" "$MV_TR" "$MV_TITLE"
    else motd_view_row "$MV_TITLE" "$MV_COLUMNS" 0 "$MV_TITLE_COLOR"; fi
    mv_render_header_sides=0; [ "$MV_FRAME" != continuous ] || mv_render_header_sides=$MV_SIDES
    [ "$MV_SHORT_HEADER" -eq 1 ] || motd_view_row "$MV_SUBTITLE" "$MV_COLUMNS" "$mv_render_header_sides" "$MV_MUTED"
    mv_render_first=1; mv_render_pending=''
    for mv_render_record in $MV_PLAN; do
        mv_render_id=${mv_render_record%%:*}; mv_render_rows=${mv_render_record#*:}
        if [ "$MV_COLUMNS_PER_ROW" -eq 2 ]; then
            if [ -z "$mv_render_pending" ]; then mv_render_pending=$mv_render_record; continue; fi
            [ "$mv_render_first" -eq 1 ] || motd_view_gap
            motd_view_overhead "${mv_render_pending%%:*}"; mv_render_height=$((${mv_render_pending#*:} + MV_OVERHEAD))
            motd_view_overhead "$mv_render_id"; mv_render_right_height=$((mv_render_rows + MV_OVERHEAD))
            [ "$mv_render_height" -ge "$mv_render_right_height" ] || mv_render_height=$mv_render_right_height
            mv_render_left=$(motd_view_panel "${mv_render_pending%%:*}" "${mv_render_pending#*:}" "$MV_PANEL_WIDTH" "$mv_render_height")
            mv_render_right=$(motd_view_panel "$mv_render_id" "$mv_render_rows" "$MV_PANEL_WIDTH" "$mv_render_height")
            while [ -n "$mv_render_left" ] || [ -n "$mv_render_right" ]; do
                MV_TEXT=$mv_render_left; motd_view_take_line; mv_render_cell_left=$MV_LINE; mv_render_left=$MV_TEXT
                MV_TEXT=$mv_render_right; motd_view_take_line; mv_render_cell_right=$MV_LINE; mv_render_right=$MV_TEXT
                [ -n "$mv_render_cell_left" ] || mv_render_cell_left=$(printf '%*s' "$MV_PANEL_WIDTH" '')
                printf '%s  %s\n' "$mv_render_cell_left" "$mv_render_cell_right"
            done
            mv_render_pending=''; mv_render_first=0; continue
        fi
        [ "$mv_render_first" -eq 1 ] || motd_view_gap
        motd_view_panel "$mv_render_id" "$mv_render_rows" "$MV_COLUMNS"
        mv_render_first=0
    done
    if [ -n "$mv_render_pending" ]; then
        [ "$mv_render_first" -eq 1 ] || motd_view_gap
        motd_view_panel "${mv_render_pending%%:*}" "${mv_render_pending#*:}" "$MV_PANEL_WIDTH"
    fi
    MV_TEXT=$MV_FOOTER
    while [ -n "$MV_TEXT" ]; do
        motd_view_take_line; [ -n "$MV_LINE" ] || continue
        motd_view_row "$MV_LINE" "$MV_COLUMNS" "$mv_render_header_sides" "$MV_MUTED"
    done
    if [ "$MV_FRAME" = continuous ] && [ "$MV_OUTER" -eq 1 ]; then motd_view_rule "$MV_COLUMNS" "$MV_BL" "$MV_BR" ''; fi
}
