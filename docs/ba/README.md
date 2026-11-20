# Business analysis pack: the LEAP → triConvey cut-over

The rest of this repository answers *what the data says*. This pack answers the questions a Business Analyst gets asked
before and during a system change: **what problem are we solving, who is involved, how does the work change, how do we
know it worked, and what happens on the day?**

It covers one change: a small NSW law firm moves practice management from **LEAP** to **triConvey (Smokeball)** and its
search supplier from **InfoTrack** to **TriSearch**. Dates, defects and rules come from [TRANSITION.md](../TRANSITION.md).
Every requirement is traced to the mart, page or test that delivers it, so the documents cannot quietly drift from the build.

| Document | What it answers | Typical BA artefact |
|---|---|---|
| [BRD.md](BRD.md) | Why are we doing this, what is in scope, what must the solution do? | Business requirements document with traceability |
| [STAKEHOLDERS.md](STAKEHOLDERS.md) | Who is affected, who decides, who does the work? | Stakeholder map and RACI |
| [PROCESS_MAPS.md](PROCESS_MAPS.md) | How does the work change, and where can it break? | As-is / to-be process maps with gap analysis |
| [UAT.md](UAT.md) | How do we prove the cut-over is clean before sign-off? | UAT test cases with expected results and evidence |
| [CUTOVER_RUNBOOK.md](CUTOVER_RUNBOOK.md) | What happens, hour by hour, and what if it goes wrong? | Cut-over plan, go / no-go criteria and rollback |

**Honest limits.** The firm, people and amounts are fictional and the roles are generic. The documents show the method
a BA would follow, written against a simulated cut-over; they are not records of a real project.
