# Guides

{.lead}
The tool makes one Nominal check per Jama Connect requirement, with the requirement's text and a link back to it.
Turning a requirement into a condition, the limit or behavior Nominal evaluates on a run, is the systems engineering work. Choose who drafts it.

| | [With your agent](agent.md) | [With the tool's sync](sync.md) |
|---|---|---|
| What builds the checklist | The tool's `sync`, then your agent, following `checks-plan.md` | The tool |
| Conditions | Your agent drafts them where a requirement states something measurable; you review them | You write each one in Nominal |
| When Jama changes | `sync` adds new checks and rewrites changed text from Jama, and your agent drafts the new checks' conditions | The tool adds new checks, and rewrites changed text from Jama |
| Publishing | You publish the agent's draft | The tool publishes the checklist |

Both find a requirement's check by the line in its description that links to Jama, so you can [switch from the sync to an agent](switch.md) at any time.

Test cases get a checklist of their own: see [Test cases](test-cases.md).
To control which channel names become checklist variables, see [Mark channels in requirements](channels.md).
To run the steps from your own code, see [Use the tool from Python](python.md).

Jama Connect® is a registered trademark of Jama Software, Inc.
