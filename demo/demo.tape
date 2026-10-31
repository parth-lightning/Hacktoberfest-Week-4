# VHS tape script for Wraith demonstration
# Install VHS: https://github.com/charmbracelet/vhs
# Render with: vhs demo/demo.tape

Output demo/demo.gif

Set FontSize 18
Set Width 1200
Set Height 700
Set Theme "Catppuccin Mocha"
Set Padding 20

# 1. Quick setup & initialization
Type "wraith setup"
Sleep 500ms
Enter
Sleep 2s

# 2. Shell initialization
Type 'eval "$(wraith init zsh)"'
Sleep 500ms
Enter
Sleep 1s

# 3. Typo trigger: command not found
Type "gti status"
Sleep 500ms
Enter
Sleep 2.5s

# 4. Dangerous command trigger: rm -rf
Type "rm -rf build node_modules"
Sleep 500ms
Enter
Sleep 2.5s

# 5. Possessed Mode & Error Rewriting
Type "wraith possess"
Sleep 500ms
Enter
Sleep 1.5s

Type "python -c 'import nonexistentmod'"
Sleep 500ms
Enter
Sleep 3s

Type "exit"
Sleep 500ms
Enter
Sleep 1s

# 6. Día de los Muertos Ofrenda View
Type "wraith ofrenda"
Sleep 500ms
Enter
Sleep 4s

