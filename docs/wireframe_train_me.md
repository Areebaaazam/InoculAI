# IMMUNITY — TRAIN ME chat and report

```text
+------------------------------------------------------------------------+
| TRAIN ME     Fictional practice • no real data or payments     [ STOP ] |
| Based on dna_042    Variant var_042_3                                  |
|------------------------------------------------------------------------|
| CHAT VIEWPORT                                  TACTIC BUDGET (COACH)   |
| Counterpart: I'm with Alder Mutual's           Authority 73/100       |
| member-services desk ...                       Fear      84/100       |
|                                               Urgency   91/100       |
| You: Can I verify that through my usual app?   Reward    12/100       |
|                                               Trust     40/100       |
| Counterpart: Of course, I can wait ...         Payment   51/100       |
|                                               Stage 1/4: authority   |
|------------------------------------------------------------------------|
| [Type a practice reply; never enter real personal data...] [ SEND ]     |
|                                                [ END AND SEE REPORT ] |
+------------------------------------------------------------------------+

+------------------------------------------------------------------------+
| IMMUNITY REPORT                     Training score: 68 / 100          |
| Session s_001   Trained on dna_042   Variant var_042_3                  |
|------------------------------------------------------------------------|
| Authority        STRONG    Questioned the caller's title               |
| Urgency          MEDIUM    Almost acted before verifying               |
| Fear             STRONG    Paused and checked independently            |
| Payment pressure WEAK      Needed practice around time threats         |
|------------------------------------------------------------------------|
| Next drill targets payment-pressure resistance.                       |
| Training metric, not a scientifically validated probability of        |
| avoiding a real-world scam.                                           |
|                                           [ CLOSE ] [ PRACTICE AGAIN ]|
+------------------------------------------------------------------------+
```

| Component | Contract / owner | Behavior |
|---|---|---|
| Drill disclosure | Static UI copy | Always visible before Start and throughout; simulator stays in character |
| DNA/variant header | ScamDNA `id`; host-assigned `variant_id` | Carry IDs into report without inventing contract fields |
| Chat viewport | Session-local `[{role, text}]` held by host | Role+timestamp labels, text-only rendering; never fetch or navigate message links; transcript is not an ImmunityReport field |
| Composer / Send | Session-local draft and request state | Enter sends, Shift+Enter newline; disable while pending or ended; no attachments; redact real PII before model processing |
| Budget indicator | ScamDNA `tactics` (all six) | Show original 0–100 ceilings, not live scores; expand “Payment” label to `payment_pressure` for accessibility |
| Stage indicator | Host-local chain cursor over ScamDNA `attack_chain` | Progress only after accepted generation; no fabricated cursor in report JSON |
| Stop / End | Host session controller | Immediately disable composer; cancel pending rendering; request scoring only for recorded turns; never resume automatically |
| Report IDs | ImmunityReport `user_session`, `trained_on`, `variant_id` | Monospace provenance; verify trained_on/variant/session match the ended drill |
| Tactic rows | `scores[].tactic`, `.result`, `.note` | `strong` green, `medium` amber, `weak` red plus text; no assumed ordering or six-row minimum; render every supplied row |
| Training score | `immunity_score` | Integer 0–100; display as training points, never survival probability |
| Coaching | `coaching[]` | Render every item; first is the primary next-drill line |
| Disclaimer | `disclaimer` | Always fully visible under score and coaching, including narrow screens |

Fixtures: `docs/fixtures/scam_dna.json` and `docs/fixtures/immunity_report.json`
match context.md §4.1–4.2. Chat turns/cursor are view state owned by the host;
do not add them to either contract. In the trainee view, the coach budget panel
is collapsed until the drill ends so it does not reveal the next tactic; show it
expanded in the presenter/debug view. It displays ceilings, not measurement.

States: idle (Start enabled only with valid DNA), active, generating, ended,
scoring, report, error. A generation error pauses the drill with an explicit
reason and manual Retry. Malformed response gets one retry then review; no blank
counterpart bubble or fake successful score. A report error preserves the local
transcript and offers Retry report. A stopped drill with no turns has no score;
show “No practice turns recorded.” Validate score range, enum, required IDs,
coaching array and exact disclaimer before rendering. Missing data gets an error,
never a zero score. Keyboard focus returns to the composer after a reply and to
the report heading after scoring; use a polite live region for new turns.

Use the DNA panel palette. Keep chat text in a readable sans-serif; IDs and budget
numbers in monospace. Animate only a subtle pending dot and the chain's current
stage; no flashing pressure or countdown coercion. Scroll only if already near
the bottom; otherwise show “New reply.” Respect reduced motion. On mobile the
budget is a disclosure beneath the header, and the composer stays visible.
