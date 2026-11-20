# Switch from the sync to your agent

{.lead}
A checklist the tool's sync keeps can be handed to your agent at any time, with nothing to migrate.
Both find a requirement's check by the line in its description that links to Jama Connect, and both find the checklist by its properties, `jama_host`, `jama_project` and `jama_items`.

## Hand the checklist to your agent

1. Write the plan, passing the run or asset whose channels the conditions should use:

   ```sh
   python nominal-checks-from-jama.py agent-plan --target <run or asset RID>
   ```

2. Give `checks-plan.md` to your agent, as in [Build checks with your agent](agent.md#run-your-agent).

The agent finds the sync's checklist, drafts conditions for the checks that have none, and leaves the conditions you wrote alone.
From then on, write the plan again when requirements change in Jama Connect, instead of syncing.

## Go back to the sync

`sync` also finds checks your agent made, by their Jama Connect link. Run it as in [Sync checks with the tool](sync.md#sync-again-after-jama-changes).
It rewrites any check whose text differs from Jama Connect, keeping its condition. To see the differences first, add `--update none` or `--dry-run`.
Where your agent made more than one check for an item, such as a test case split by its pass criteria, the sync leaves those checks as they are and lists them.

The sync finds only published checklists. Publish your agent's draft before syncing.

Jama Connect® is a registered trademark of Jama Software, Inc.
