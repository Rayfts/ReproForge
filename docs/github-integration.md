# GitHub integration

The initial CLI can ingest GitHub issue URLs and can post comments through the control-plane GitHub client when explicitly invoked by future automation. GitHub credentials are not automatically passed into target-repository containers.

## Intended triggers

ReproForge is designed to support:

- `/repro` issue comments;
- issue labels;
- `workflow_dispatch`;
- manual CLI runs.

The repository ships a workflow-dispatch example before enabling automatic issue-comment execution. Automatically running arbitrary issue content on privileged self-hosted runners requires a deliberate deployment threat model.

## Result comment shape

A future GitHub App/Action should post concise evidence only:

- status and confidence;
- failing command/test;
- environment/revision;
- reproduction rate and determinism;
- artifact link;
- proposed regression test;
- caveats.

Do not post verbose agent narration.

## Permissions

Use least privilege. Read-only repository/issues permissions are sufficient for ingestion. Commenting requires issue write permission. Generated patches must remain artifacts until a maintainer explicitly approves a branch/push workflow.

## Tokens

`GITHUB_TOKEN` or `GH_TOKEN` may be used by the control plane for GitHub API calls. They are not part of the default sandbox environment. Never add them to `security.allowed_secrets` merely to make repository setup easier.
