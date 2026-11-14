# Shared agent workflow

This repository is worked on by three people using Codex and/or Claude agents. Keep changes isolated, reviewable, and attributable to the person who authorized them.

## Before changing code

- Start from the repository root and run `git status --short --branch`.
- Before every code change, update the current branch from its upstream with `git pull --ff-only`. If there is no upstream, fetch and rebase/merge only with the owner's direction; do not silently change branches or overwrite local work.
- If the pull fails or the working tree contains work you did not make, stop and report the conflict instead of resetting, stashing, or discarding it.
- Make changes on a task branch, not directly on `main`. Use a descriptive name such as `feature/...` or `fix/...`.
- Keep each change focused. After each code change, run the relevant verification, then commit and push the task branch so its pull request stays current. Use a concise commit message that describes the change. Do not commit or push directly to `main`.
- If verification fails, report the failure and do not describe the change as verified. Fix it and rerun relevant verification before committing and pushing, or document the unresolved result in the pull request and track it as an issue as described below.

## Pull requests and review

- Open a GitHub pull request for each completed task and describe the purpose, notable changes, and checks performed. Link related issues when applicable.
- Before merge, ask one of the other two project members to review the diff. The reviewer should inspect the changes independently, check for correctness and unintended effects, and leave actionable findings or explicitly state approval.
- The authoring agent must not be the sole reviewer of its own work. Address review comments in a follow-up commit and request another look when the changes affect the review.
- Merge only after the human project members' agreed review process is satisfied. Do not self-merge unless explicitly authorized by the repository owner.
- For bugs, risks, or other issues found during implementation or review that cannot be fixed immediately, or need clarification from the user, create a GitHub issue describing the problem, impact, and what is needed to resolve it. Link the issue from the pull request and keep it open until addressed; update or close it after resolution.

## GitHub identity and agent use

- Agents are tools operated by the three people, not project members or GitHub accounts. Do not create agent accounts, add agents as collaborators, or share personal access tokens, SSH keys, or login sessions between people or agents.
- Keep Git commits and pull requests attributed to the human who authorized the work, using that person's own GitHub credentials and configured Git identity. Never impersonate another person or fabricate a review, approval, or status check.
- A second agent can help inspect a pull request, but its comments do not count as a GitHub review from a separate collaborator unless a human reviewer submits the review through their own authorized account. Have the other project member verify and submit the formal review.
- Do not add reviewers or collaborators automatically. The humans decide who has repository access and who formally reviews each pull request.

## Review checklist

- Read the full diff and confirm it matches the pull request description.
- Look for bugs, security or privacy issues, regressions, and unnecessary scope.
- Check relevant existing tests or validation commands and report what was run. Do not claim checks passed if they were not run.
- Give findings with file and line references; if there are no findings, say so and identify any remaining uncertainty.
- Create or link a GitHub issue for any finding that cannot be resolved during the review, including questions that require user clarification, and keep it tracked until addressed.
