# Permission registry

Assignment/ownership and tenant policy still apply when a permission is granted. This is a role mapping, not a blanket authorization to every resource.

| Permission | super_admin | institution_admin | coordinator | instructor | teaching_assistant | student | auditor |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `academic.manage` | Yes | Yes | Yes | — | — | — | — |
| `academic.read` | Yes | Yes | Yes | — | — | — | — |
| `announcements.create` | Yes | Yes | — | Yes | — | — | — |
| `assessments.attempt` | — | — | — | — | — | Yes | — |
| `assessments.create` | Yes | Yes | — | Yes | — | — | — |
| `assessments.grade` | Yes | Yes | — | Yes | Yes | — | — |
| `attendance.manage` | Yes | Yes | Yes | Yes | — | — | — |
| `audit.read` | Yes | Yes | — | — | — | — | Yes |
| `certificates.manage` | Yes | Yes | — | — | — | — | — |
| `certificates.read` | Yes | Yes | — | Yes | — | Yes | — |
| `courses.assign_assistant` | Yes | Yes | — | Yes | — | — | — |
| `courses.create` | Yes | Yes | — | Yes | — | — | — |
| `courses.manage` | Yes | Yes | Yes | — | — | — | — |
| `courses.publish` | Yes | Yes | — | Yes | — | — | — |
| `courses.read` | Yes | Yes | Yes | Yes | Yes | Yes | — |
| `courses.update` | Yes | Yes | — | Yes | — | — | — |
| `discussions.write` | Yes | Yes | — | Yes | Yes | Yes | — |
| `enrollments.create` | Yes | Yes | Yes | — | — | Yes | — |
| `enrollments.manage` | Yes | Yes | Yes | — | — | — | — |
| `enrollments.read` | Yes | Yes | Yes | Yes | Yes | — | — |
| `files.create` | Yes | Yes | — | Yes | — | — | — |
| `imports.manage` | Yes | Yes | — | — | — | — | — |
| `institutions.manage` | Yes | — | — | — | — | — | — |
| `messages.create` | Yes | Yes | — | Yes | — | — | — |
| `profile.update` | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| `progress.update` | — | — | — | — | — | Yes | — |
| `reports.export` | Yes | Yes | Yes | Yes | — | — | Yes |
| `reports.read` | Yes | Yes | Yes | Yes | — | — | Yes |
| `roles.assign` | Yes | Yes | — | — | — | — | — |
| `roles.read` | Yes | Yes | — | — | — | — | — |
| `settings.manage` | Yes | Yes | — | — | — | — | — |
| `submissions.create` | — | — | — | — | — | Yes | — |
| `system.manage` | Yes | — | — | — | — | — | — |
| `users.create` | Yes | Yes | — | — | — | — | — |
| `users.disable` | Yes | Yes | — | — | — | — | — |
| `users.read` | Yes | Yes | Yes | — | — | — | — |
| `users.update` | Yes | Yes | — | — | — | — | — |
