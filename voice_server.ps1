# Persistent text-to-speech server for Marcille.
# Reads one line of text per line from stdin and speaks it with the built-in
# Windows female voice. Special tokens: __STOP__ cancels queued speech,
# __RATE n__ sets rate (-10..10). Started/fed by marcille.py.

Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female,
                              [System.Speech.Synthesis.VoiceAge]::Adult)
} catch { }
$synth.Rate = 1
$synth.Volume = 100

while ($true) {
    $line = [Console]::In.ReadLine()
    if ($null -eq $line) { break }
    $line = $line.Trim()
    if ($line.Length -eq 0) { continue }
    if ($line -eq '__STOP__') { try { $synth.SpeakAsyncCancelAll() } catch {}; continue }
    if ($line -like '__RATE *__') {
        $n = ($line -replace '__RATE ', '') -replace '__', ''
        try { $synth.Rate = [int]$n } catch {}
        continue
    }
    try { $synth.Speak($line) } catch { }
}
