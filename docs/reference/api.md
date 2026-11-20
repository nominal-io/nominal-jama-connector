# Python API

Each step is a function that takes the previous step's data and returns its own. [Use the tool from Python](../guides/python.md) shows them together.

## Step 1: read the requirements or test cases

```{eval-rst}
.. autofunction:: nominal_checks_from_jama.read_requirements

.. autoclass:: nominal_checks_from_jama.Requirements
   :members: save, load

.. autoclass:: nominal_checks_from_jama.Requirement

.. autoclass:: nominal_checks_from_jama.Source

.. autoclass:: nominal_checks_from_jama.ItemKind
   :members: REQUIREMENTS, TEST_CASES
```

## Step 2: make the checks

```{eval-rst}
.. autofunction:: nominal_checks_from_jama.build_checks

.. autoclass:: nominal_checks_from_jama.Checks
   :members: save, load

.. autoclass:: nominal_checks_from_jama.CheckSpec

.. autofunction:: nominal_checks_from_jama.lineage

.. autofunction:: nominal_checks_from_jama.checks_from_jama

.. autofunction:: nominal_checks_from_jama.checks_from_file
```

### Finding channels

```{eval-rst}
.. autodata:: nominal_checks_from_jama.markers.ChannelFinder
   :no-value:

.. autofunction:: nominal_checks_from_jama.marked_channels

.. autofunction:: nominal_checks_from_jama.channel_names

.. autodata:: nominal_checks_from_jama.markers.PAIRS
   :no-value:
```

## Output: your agent's plan

```{eval-rst}
.. autofunction:: nominal_checks_from_jama.write_agent_plan

.. autoclass:: nominal_checks_from_jama.AgentPlan
```

## Output: the checklist in Nominal

```{eval-rst}
.. autofunction:: nominal_checks_from_jama.sync

.. autofunction:: nominal_checks_from_jama.plan_sync

.. autoclass:: nominal_checks_from_jama.SyncResult

.. autoclass:: nominal_checks_from_jama.SyncPlan
   :members: changed, counts

.. autoclass:: nominal_checks_from_jama.Result

.. autoclass:: nominal_checks_from_jama.Difference

.. autoclass:: nominal_checks_from_jama.VariableResult

.. autoclass:: nominal_checks_from_jama.Outcome
   :members:
   :undoc-members:

.. autoclass:: nominal_checks_from_jama.Field
   :members:
   :undoc-members:
```

## Settings

```{eval-rst}
.. autoclass:: nominal_checks_from_jama.Config
   :members: load, save

.. autoclass:: nominal_checks_from_jama.JamaSettings

.. autoclass:: nominal_checks_from_jama.NominalSettings

.. autoclass:: nominal_checks_from_jama.AuthKind
   :members:
   :undoc-members:
```

## Errors

```{eval-rst}
.. autoexception:: nominal_checks_from_jama.ReadError

.. autoexception:: nominal_checks_from_jama.SyncError

.. autoexception:: nominal_checks_from_jama.NominalError

.. autoexception:: nominal_checks_from_jama.ChecklistConflict

.. autoexception:: nominal_checks_from_jama.FileFormatError
```

Jama Connect® is a registered trademark of Jama Software, Inc.
