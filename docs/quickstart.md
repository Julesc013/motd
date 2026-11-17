# Create your first MOTD

Start with a synthetic preview, save the settings as a TOML **recipe**, then build
the standalone file for your destination computer. The recipe lets you change
the design later. The generated file displays the message without Python.

You need Python 3.8 or later to run `motd.py`. Run the commands below from the
directory containing that file. On Windows, use `python` or `py -3` in place of
`python3`. Previewing executable output also needs its selected interpreter;
you can build for another computer even when its interpreter is unavailable here.
See [compatibility](compatibility.md) for tested versions and dependencies.

## 1. Open the wizard

Create a workspace for your trial files and local recovery records:

```sh
python3 -c "from pathlib import Path; Path('motd-tryout').mkdir(exist_ok=True)"
python3 motd.py wizard --state-dir ./motd-tryout/state
```

Choose **Create/customise a message**. On Linux, choose **This user** when asked
for installation scope; choosing a scope does not install anything. Start with
**home-lab** for fewer sections or **workshop** for a fuller operational overview.
**public-console** starts a static notice intended for a pre-login consumer.

On Destination, check the output interpreter against the computer that will run
the file. Bash, Zsh, sh and Fish serve Unix routes; PowerShell has its own output;
CMD launches the PowerShell dashboard. A separate Windows batch notice contains
ASCII text and needs no PowerShell.

## 2. Choose a reading style

On Design and readability, try a different Design:

| Design | Starting point |
|---|---|
| Classic | Compact framed overview. |
| Cards | Separate panels with room between topics. |
| Ledger | Open headings and aligned facts. |
| Briefing | Attention and essential context first. |
| Dashboard | Panels alongside each other when space permits. |

**Spacing bias** changes compactness; **Information detail** changes how much
content is requested. Try Comfortable with Brief for a quieter display. Padding,
section gaps and colour emphasis are independent. Short views reduce optional
detail and name hidden sections.

On Characters and colour, change **Usage bars** to **Wide** to give each gauge its
own panel-width row. Inline keeps the existing compact arrangement. In a paired
dashboard, the bar fills its own card. Numeric readings survive when there is too
little room for a gauge. Resize the window to compare short and tall layouts.

## 3. Use the preview and keys

In a screen menu that previews a choice, type its number and press **Enter** to
see the result; press **Enter again** to accept. Up/Down moves the selection.
Ordinary action menus and line mode accept number-plus-Enter immediately.

On settings pages, choose a field number to edit it; **Enter** or **N** advances,
**B** goes back, **?** explains the page, and **Q** cancels from menus or settings
pages. `[` and `]` reveal additional choices. Text fields retain the current value
when left blank; Ctrl-C leaves the wizard.

**P** opens the synthetic preview. **H**, then Enter, toggles literal before/after
call samples; configured commands never run there. In line mode, use P after H
to print the samples. J/K scroll long samples in screen mode. To request the
line interface explicitly, add `--ui line` to the wizard command.

## 4. Save, build and reopen

Continue to Review and finish. Choose **Save TOML recipe** and enter
`./motd-tryout/first.toml`. Then choose **Build portable output** and a matching
filename, such as `./motd-tryout/first.bash` or `./motd-tryout/first.ps1`.
Use new names when saving a revision. Windows exports also write a hash manifest
and refuse replacement of existing files. **Cancel** leaves requested exports
in place and exits the wizard.

To reopen, run the wizard again, choose **Open an existing recipe or output**,
then **A TOML recipe**, and enter `./motd-tryout/first.toml`. Choose **Change draft
settings**. A recognized generated shell output can also supply its embedded
recipe; static notices need their saved TOML file.

## A repeatable command-line build

This example writes new files into the workspace created above:

```sh
python3 motd.py build --preset home-lab --shell sh --design cards --density comfortable --detail brief --bar-layout wide --output ./motd-tryout/greeting.sh --save-config ./motd-tryout/greeting.toml --create-only
python3 motd.py preview --config ./motd-tryout/greeting.toml --width 40 --rows 25
```

For Windows output, change `--shell sh` to `--shell powershell` and the output
suffix to `.ps1`. Use a new recipe filename for a second build. Preview remains
synthetic by default; generated-recipe `preview --live` collects local observations
while suppressing configured calls. Read [configuration](configuration.md) for
other settings and [plan before applying](install.md#plan-before-applying) when
you are ready to attach a greeting to a supported login route.
