export const meta = {
  name: 'marcille-build',
  description: 'Autonomously design, build, adversarially audit, and verify a new feature for the Marcille desktop companion',
  whenToUse: 'When the user asks to build/add/implement a feature for Marcille (the desktop pet at C:\\Users\\tamin\\desktop-pet). Pass the feature request string as args.',
  phases: [
    { title: 'Checkpoint', detail: 'git commit current state so the run is reversible' },
    { title: 'Think', detail: 'brainstorm distinct implementation approaches' },
    { title: 'Judge', detail: 'score approaches on feasibility/value/risk, pick one' },
    { title: 'Spec', detail: 'turn the choice into a concrete, testable spec' },
    { title: 'Code', detail: 'implement the spec and compile-check' },
    { title: 'Audit', detail: 'adversarial auditors find bugs; fixer fixes; loop until clean' },
    { title: 'Verify', detail: 'actually launch Marcille and confirm it works' },
    { title: 'Commit', detail: 'commit the verified change with a descriptive message' },
  ],
}

// ---- constants (real, verified paths) ----
const PROJECT = 'C:\\Users\\tamin\\desktop-pet'
const PY  = 'C:\\Users\\tamin\\AppData\\Local\\Programs\\Python\\Python314\\python.exe'
const PYW = 'C:\\Users\\tamin\\AppData\\Local\\Programs\\Python\\Python314\\pythonw.exe'

function need(v, who) { if (!v) throw new Error(`${who} returned nothing — aborting build.`); return v }

const feature = (typeof args === 'string' ? args : (args && args.feature)) || ''
if (!feature.trim()) throw new Error('marcille-build needs a feature request as args (a non-empty string).')

const ENV = `
PROJECT: ${PROJECT}
MAIN FILE: ${PROJECT}\\marcille.py  (one large single-file Tkinter app, ~3500 lines)
PYTHON 3.14 (has all of Marcille's deps): ${PY}
PYTHONW (windowless launch): ${PYW}

COMPILE-CHECK (success = no output / exit 0), run in PowerShell:
  & "${PY}" -m py_compile "${PROJECT}\\marcille.py"

HEADLESS SMOKE TEST (success = prints HARNESS_OK), run in PowerShell:
  Set-Location "${PROJECT}"; & "${PY}" test_marcille.py

LAUNCH the app (PowerShell):
  Start-Process "${PYW}" -ArgumentList 'marcille.py' -WorkingDirectory "${PROJECT}"

FIND / KILL running instances (filter by process NAME to avoid the self-match
false positive where the query matches its own command line):
  Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -like '*marcille.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

SEE THE CURRENT DIFF (feature changes vs the pre-run checkpoint):
  git -C "${PROJECT}" diff

RULES:
- Edit marcille.py in place; match the surrounding style (plain Tkinter + ctypes, no UI frameworks).
- All Tk widget work stays on the main thread; heavy work goes in daemon threads marshalled back via root.after (the existing pattern). Off-thread Tk calls crash the app.
- The brain is Gemini (cloud) with local Ollama gemma3 fallback; don't add new heavy model deps without saying so.
- NEVER report success without actually running the compile-check and smoke test.
`.trim()

// ---- structured handoff schemas ----
const THINK_SCHEMA = {
  type: 'object', required: ['approaches'],
  properties: { approaches: { type: 'array', minItems: 2, maxItems: 4, items: {
    type: 'object', required: ['name', 'sketch', 'touches', 'effort', 'risk'],
    properties: {
      name: { type: 'string' },
      sketch: { type: 'string', description: 'concretely how it works' },
      touches: { type: 'string', description: 'which functions/classes/files it changes' },
      effort: { type: 'string', enum: ['small', 'medium', 'large'] },
      risk: { type: 'string', description: 'main risk to the existing app' },
    } } } },
}
const JUDGE_SCHEMA = {
  type: 'object', required: ['chosen', 'rationale', 'acceptanceHints'],
  properties: {
    chosen: { type: 'string', description: 'name of the chosen approach' },
    rationale: { type: 'string' },
    graft: { type: 'string', description: 'good ideas from the runners-up worth folding in' },
    acceptanceHints: { type: 'string', description: 'what done-and-working looks like' },
  },
}
const SPEC_SCHEMA = {
  type: 'object', required: ['summary', 'plan', 'acceptanceCriteria'],
  properties: {
    summary: { type: 'string', description: 'one-sentence summary of the change' },
    plan: { type: 'string', description: 'the COMPLETE implementation plan as one plain-text/markdown string: every function/region to change and exactly what to do, in order. Self-contained — the coder needs nothing else.' },
    acceptanceCriteria: { type: 'array', items: { type: 'string' }, description: '4-8 short, checkable bullet criteria' },
  },
}
const CODE_SCHEMA = {
  type: 'object', required: ['summary', 'compileOk'],
  properties: {
    summary: { type: 'string', description: 'what was implemented' },
    filesTouched: { type: 'array', items: { type: 'string' } },
    compileOk: { type: 'boolean', description: 'true ONLY if py_compile actually passed' },
    notes: { type: 'string', description: 'anything the auditor should double-check' },
  },
}
const AUDIT_SCHEMA = {
  type: 'object', required: ['verdict', 'compileOk', 'testsOk', 'findings'],
  properties: {
    verdict: { type: 'string', enum: ['pass', 'needs-fix'] },
    compileOk: { type: 'boolean', description: 'did py_compile pass' },
    testsOk: { type: 'boolean', description: 'did test_marcille.py print HARNESS_OK' },
    findings: { type: 'string', description: 'every real bug as plain text — each with severity + location + concrete fix; "none" if truly clean' },
  },
}
const VERIFY_SCHEMA = {
  type: 'object', required: ['verdict', 'evidence'],
  properties: {
    verdict: { type: 'string', enum: ['shipped', 'failed'] },
    startedClean: { type: 'boolean', description: 'app launched without crashing' },
    evidence: { type: 'string' },
  },
}
const COMMIT_SCHEMA = {
  type: 'object', required: ['hash'],
  properties: { hash: { type: 'string' }, committed: { type: 'boolean' } },
}

log(`Building Marcille feature: ${feature}`)

// ---------- 1. Checkpoint ----------
phase('Checkpoint')
await agent(`Make a git checkpoint so this build is reversible.
${ENV}

Run (PowerShell):
  git -C "${PROJECT}" add -A
  git -C "${PROJECT}" commit -m "Pre-build checkpoint: ${feature}" --allow-empty
Then report the short hash: git -C "${PROJECT}" rev-parse --short HEAD`,
  { label: 'checkpoint', phase: 'Checkpoint' })

// ---------- 2. Think ----------
phase('Think')
const ideas = need(await agent(`You are THE THINKER. Brainstorm distinct ways to implement this feature.

FEATURE REQUEST: "${feature}"
${ENV}

First READ the relevant parts of marcille.py to ground your ideas in the real code (the Marcille class and its update_behavior/draw/tick loop, the Brain/Voice/Memory classes, the right-click menu builder). Then propose 2-4 genuinely DIFFERENT approaches. For each: a concrete sketch, which functions/classes it touches, rough effort, and the main risk. Do NOT write code yet.`,
  { label: 'thinker', phase: 'Think', schema: THINK_SCHEMA }), 'Thinker')
log(`Thinker proposed ${ideas.approaches.length} approaches`)

// ---------- 3. Judge ----------
phase('Judge')
const choice = need(await agent(`You are THE JUDGE. Pick the single best approach to actually build.

FEATURE: "${feature}"
APPROACHES:
${ideas.approaches.map((a, i) => `${i + 1}. ${a.name}\n   sketch: ${a.sketch}\n   touches: ${a.touches}\n   effort: ${a.effort} | risk: ${a.risk}`).join('\n')}

Score each against: (1) feasibility on this stack (plain Tkinter, Windows, weak GPU), (2) value toward making Marcille more alive/useful, (3) effort, (4) risk to the existing 3500-line single file. Pick ONE. Give rationale, name any good ideas from the losers worth folding in, and describe what "done and working" looks like.`,
  { label: 'judge', phase: 'Judge', schema: JUDGE_SCHEMA }), 'Judge')
log(`Judge chose: ${choice.chosen}`)

// ---------- 4. Spec ----------
phase('Spec')
const spec = need(await agent(`You are THE SPEC WRITER. Turn the chosen approach into a precise, buildable spec.

FEATURE: "${feature}"
CHOSEN APPROACH: ${choice.chosen}
RATIONALE: ${choice.rationale}
FOLD IN: ${choice.graft || '(nothing extra)'}
ACCEPTANCE HINTS: ${choice.acceptanceHints}
${ENV}

The Judge already traced the real code and cited exact line numbers above — lean on it. Read only specific functions in marcille.py if you must confirm a detail; do NOT re-read the whole ~4000-line file.

Output exactly three fields:
- summary: one sentence.
- plan: ONE plain-text/markdown string with the COMPLETE implementation plan — every function/region to change and exactly what to do there, in order. Put ALL the detail here; make it self-contained.
- acceptanceCriteria: 4-8 short checkable bullets.
Keep the JSON small and clean — the detail lives inside the single 'plan' string.`,
  { label: 'spec', phase: 'Spec', schema: SPEC_SCHEMA }), 'Spec')
log(`Spec ready: ${spec.summary}`)

// ---------- 5. Code ----------
phase('Code')
const code = need(await agent(`You are THE CODER. Implement this plan by editing marcille.py (and any other files it names).

FEATURE: "${feature}"
SUMMARY: ${spec.summary}

IMPLEMENTATION PLAN:
${spec.plan}

ACCEPTANCE CRITERIA:
${(spec.acceptanceCriteria || []).map(c => `- ${c}`).join('\n')}
${ENV}

Be surgical — Read/grep only the functions named in the plan; don't read the whole file. Implement cleanly, matching surrounding style. THEN run the compile-check and fix any syntax errors until it compiles. Report what you implemented and the compile result. Do NOT set compileOk true unless py_compile actually succeeded.`,
  { label: 'coder', phase: 'Code', schema: CODE_SCHEMA }), 'Coder')
log(`Coder done. compileOk=${code.compileOk}`)

// ---------- 6. Adversarial audit loop ----------
phase('Audit')
const LENSES = [
  { tag: 'crash', focus: 'Hunt for crashes, exceptions, threading violations (Tk touched off the main thread), None/attribute errors, and anything that could break the existing tick() loop or other features. Assume there IS a bug.' },
  { tag: 'spec', focus: 'Check it truly matches the spec and acceptance criteria, and probe edge cases (first run, missing config/key, feature toggled off, odd input, app restarted). Assume it is subtly wrong.' },
]
let round = 0, clear = false
const fixes = []
while (round < 3 && !clear) {
  round++
  const audits = (await parallel(LENSES.map(L => () =>
    agent(`You are AN ADVERSARIAL AUDITOR (${L.tag} lens). Your job is to BREAK this change, not bless it.

FEATURE: "${feature}"
ACCEPTANCE CRITERIA:
${(spec.acceptanceCriteria || []).map(c => `- ${c}`).join('\n')}
${ENV}

${L.focus}

Steps: read the current diff (git -C "${PROJECT}" diff), read the changed code in context, RUN the compile-check AND the headless smoke test (must print HARNESS_OK), and reason hard about failure modes. List every real bug with severity (critical/major/minor), where, and a concrete fix. Default verdict to "needs-fix" if anything is wrong or the smoke test does not print HARNESS_OK; only "pass" if it compiles, the smoke test passes, it matches the spec, and you genuinely could not break it.`,
      { label: `audit-r${round}-${L.tag}`, phase: 'Audit', schema: AUDIT_SCHEMA })
  ))).filter(Boolean)

  const compileOk = audits.length > 0 && audits.every(a => a.compileOk)
  const testsOk = audits.length > 0 && audits.every(a => a.testsOk)
  const needsFix = audits.length === 0 || audits.some(a => a.verdict === 'needs-fix') || !compileOk || !testsOk
  const findings = audits.map(a => `[verdict: ${a.verdict} | compileOk: ${a.compileOk} | testsOk: ${a.testsOk}]\n${a.findings}`).join('\n\n')

  if (!needsFix) { clear = true; log(`Audit round ${round}: clean`); break }
  log(`Audit round ${round}: needs-fix -> fixing`)

  const fix = await agent(`You are THE FIXER. Fix every real bug the auditors found in marcille.py, then re-verify.

FEATURE: "${feature}"
AUDITOR FINDINGS:
${findings}
${ENV}

Fix them properly (no band-aids that merely hide the symptom). THEN run the compile-check and the headless smoke test (must print HARNESS_OK). Report what you changed and the compile result (compileOk only if py_compile actually passed).`,
    { label: `fix-r${round}`, phase: 'Audit', schema: CODE_SCHEMA })
  fixes.push({ round })
}
if (!clear) log(`Audit did not fully converge after ${round} rounds — will flag in the report.`)

// ---------- 7. Verify (actually run it) ----------
phase('Verify')
const verify = need(await agent(`You are THE QA / VERIFIER. Confirm the feature works by RUNNING Marcille, not by reading code.

FEATURE: "${feature}"
ACCEPTANCE CRITERIA:
${(spec.acceptanceCriteria || []).map(c => `- ${c}`).join('\n')}
${ENV}

Steps:
1. Run the compile-check and the headless smoke test (must print HARNESS_OK).
2. Kill any running Marcille, then LAUNCH it. Wait ~6 seconds. Confirm the pythonw process is still alive (did not crash on startup) via the name-filtered Get-CimInstance query. If it died, get the traceback by running it in the foreground: & "${PY}" marcille.py
3. Judge whether the new behavior is actually present, as far as is confirmable without a human watching (process alive + smoke test + code path reachable + any log/file side effects). Note anything only a human can confirm visually.
4. Leave Marcille running (the user wants to see it).

Report verdict (shipped/failed), startedClean, and the concrete evidence you observed.`,
  { label: 'verify', phase: 'Verify', schema: VERIFY_SCHEMA }), 'Verify')
log(`Verify: ${verify.verdict} (cleanStart=${verify.startedClean})`)

// ---------- 8. Commit the result ----------
phase('Commit')
const shipped = verify.verdict === 'shipped' && clear
const commit = await agent(`Commit the result of this build.
${ENV}

Run (PowerShell):
  git -C "${PROJECT}" add -A
  git -C "${PROJECT}" commit -m "Marcille: ${feature}" -m "Verify: ${verify.verdict}; audit rounds: ${round}; ${shipped ? 'clean' : 'NOT fully clean — see report'}" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
Report the short commit hash (git -C "${PROJECT}" rev-parse --short HEAD).`,
  { label: 'commit', phase: 'Commit', schema: COMMIT_SCHEMA })

return {
  feature,
  chosenApproach: choice.chosen,
  spec: spec.summary,
  filesTouched: code.filesTouched,
  auditRounds: round,
  auditConverged: clear,
  fixRounds: fixes.length,
  verify: verify.verdict,
  cleanStart: verify.startedClean,
  evidence: verify.evidence,
  commit: commit && commit.hash,
  outcome: shipped
    ? 'Built, audited clean, verified running, and committed.'
    : 'Built and committed, but NOT fully clean — review the diff and evidence before trusting it.',
}
