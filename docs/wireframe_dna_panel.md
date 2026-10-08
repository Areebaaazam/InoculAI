# COMMAND — ScamDNA panel

```text
+------------------------------------------------------------------------+
| COMMAND / SCAM DNA                  dna_042       source: msg_117       |
| [94% match to #042]                 Confidence 97%                      |
|------------------------------------------------------------------------|
| TACTIC PROFILE                       ATTACK CHAIN                      |
| Urgency           [##################--] 91                            |
| Fear              [#################---] 84    [Authority] --> [Fear]   |
| Authority         [###############-----] 73                     |       |
| Reward            [##------------------] 12                     v       |
| Trust             [########------------] 40    [Action] <-- [Urgency]   |
| Payment pressure  [##########----------] 51                            |
|------------------------------------------------------------------------|
| INDICATORS OF COMPROMISE                                               |
| Phones        +91XXXXXXXXXX                                           |
| Domains       sbi-secure-verify.example                                |
| Wallets       None observed                                           |
| Payment links None observed                                           |
|------------------------------------------------------------------------|
| Model: featherless/<model>               2026-10-07 18:00 UTC           |
|                                          [ TRAIN ME ON THIS DNA ]      |
+------------------------------------------------------------------------+
```

| Component | Exact contract source | Rendering / behavior |
|---|---|---|
| Header IDs | `id`, `source_message_id` | Monospace labels; selecting source returns to the inbound feed |
| Six bars | `tactics.urgency`, `.fear`, `.authority`, `.reward`, `.trust`, `.payment_pressure` | Width=value%; integer 0–100 labels; fixed order above; never treat 0 as missing |
| Chain | `attack_chain` | Ordered left-to-right arrows; wrap visually without changing order; `action` is a stage, not a seventh bar |
| IOC groups | `iocs.phones`, `.domains`, `.wallets`, `.payment_links` | One inert text row per value; empty array=“None observed”; no clickable links or dialing controls |
| Similarity badge | `similarity`, `campaign_id` | Multiply similarity by 100, round; display `camp_042` as `#042`; 0.94 → “94% match to #042” |
| Confidence | `confidence` | 0.97 → “Confidence 97%”; separate from campaign similarity |
| Provenance | `extraction_model`, `created_at` | Model label; parse ISO8601 and show time with explicit zone |
| Train action | `id` | Pass exact ID as trained-on DNA; disabled until contract validation succeeds |

Contract source: `docs/fixtures/scam_dna.json`, matching context.md §4.1 exactly.
Use all six tactic keys; never add `impersonation` or rename `payment_pressure`.
Missing fields, non-finite/out-of-range numbers, invalid timestamps, unknown
chain stages, or non-array IOC groups produce a visible “DNA unavailable: invalid
response” state and disable TRAIN ME. Do not fabricate zeros or clamp bad data.
No selection → “Select an inbound attack.” Loading → skeleton bars. An empty IOC
group is valid. A backend error shows a reason plus Retry, without stale values
remaining labeled as current. Interpolate all strings as text, never HTML.

Dark command-center notes for Fran: canvas #0B1016, panels #141D27, primary text
#E6EDF3, muted #94A3B8. Cyan #38BDF8 marks selection; amber #FBBF24 highlights
pressure; red #F87171 marks invalid/blocked states; green #34D399 marks verified
completion. Use monospace for IDs, times and percentages; regular readable type
for descriptions. Give every color a text label; keyboard focus has a cyan ring.
Chain arrows light in order at 250ms per stage on selection, once only, then stay
steady. Honor reduced motion. On narrow screens stack chain below bars and IOCs
below both; preserve the logical reading order and full numbers.
