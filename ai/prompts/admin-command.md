# 8. Implement Hidden Telegram Admin Commands

Implement a small set of **Telegram adapter-only** administrative commands for managing closed beta access.

## Architectural Constraints

* These commands are **Telegram adapter features**.
* Do **not** expose them to the application layer or core domain.
* Do **not** introduce Telegram-specific concepts into domain models.
* Reuse the existing authorization mechanism where possible.

---

# Authorization

Only the configured administrator may execute these commands.

Use the configured Telegram administrator ID from the application settings.

Every admin command must verify that:

* the sender's Telegram ID matches the configured administrator ID.

If the sender is not the administrator:

* return a generic "You are not authorized to use this command." message or silently ignore the request.
* never expose administrative information.

---

# Hidden Commands

These commands **must not** be registered with `set_my_commands()`.

They are intentionally hidden from the Telegram **[/]** menu and normal users.

---

# `/admin_beta_list`

Display all pending beta requests.

Read every JSON file from:

```text
data/
    telegram/
        beta_requests/
```

Sort requests by request date (oldest first).

Display an indexed list similar to:

```text
Pending Beta Requests

1.
Username: @PabloDonkey
Name: Pablo
Telegram ID: 123456789
Requested: 2026-07-15 13:42 UTC

2.
Username: @AnotherUser
Name: Alice
Telegram ID: 987654321
Requested: 2026-07-16 09:18 UTC
```

If there are no pending requests, inform the administrator.

---

# `/admin_beta_accept`

Accept a pending beta request.

Support two forms:

```
/admin_beta_accept <telegram_id>
```

or

```
/admin_beta_accept <list_index>
```

If a list index is provided, resolve it using the ordering produced by `/admin_beta_list`.

Behavior:

1. Verify the request exists.
2. Add the Telegram ID to the adapter's authorized user list.
3. Remove the pending request from `data/telegram/beta_requests/`.
4. Persist the updated authorization data.
5. Inform the administrator of success.

If the user is already authorized:

* report that they are already authorized.
* clean up any remaining pending request if appropriate.

If the request cannot be found:

* display a clear error.

---

# `/admin_beta_reject`

(Optional but recommended.)

Support:

```
/admin_beta_reject <telegram_id>
```

or

```
/admin_beta_reject <list_index>
```

Behavior:

* remove the pending request.

Optionally move it to:

```text
data/
    telegram/
        beta_rejected/
```

instead of deleting it.

If a rejection reason is supplied, store it in the archived JSON.

---

# Optional Notification

If possible, notify the approved user.

Example:

> 🎉 Your beta request has been approved!
>
> You can now use the bot.
>
> Send `/start` to begin.

Failure to send the notification must **not** prevent approval.

---

# Command Registration

Do **not** include these commands in `set_my_commands()`.

They are intentionally hidden administrative commands.

---

# Documentation

Document these commands in the project documentation for administrators only.

Do not include them in user-facing help.

---

# Testing

Add tests covering:

* administrator can list requests.
* non-admin cannot list requests.
* administrator can approve by Telegram ID.
* administrator can approve by list index.
* duplicate approvals are handled correctly.
* pending request is removed after approval.
* authorized user list is updated.
* administrator can reject requests.
* hidden commands are not registered in Telegram's command menu.

---

# Acceptance Criteria

* Only the configured administrator can execute admin commands.
* Commands remain hidden from the Telegram command menu.
* `/admin_beta_list` displays pending requests in chronological order.
* `/admin_beta_accept` supports both Telegram IDs and list indexes.
* Approval updates the authorization list and removes the pending request.
* `/admin_beta_reject` removes or archives pending requests.
* Optional user notifications do not block approval.
* No Telegram-specific administrative logic leaks outside the Telegram adapter.
