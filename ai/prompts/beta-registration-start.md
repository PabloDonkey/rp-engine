# Copilot Implementation Prompt — Milestone 006: Telegram Adapter UX & Beta Registration

Implement the following milestone while preserving the existing architecture.

## Architectural Constraints

* Keep all Telegram-specific behavior inside the Telegram adapter.
* Do **not** leak Telegram concepts into the application or core domain.
* Do **not** introduce Telegram-specific fields into domain models.
* Follow the project's existing architecture, coding style, typing, and dependency direction.
* Update documentation and tests where appropriate.

---

# 1. Add `/chat` command for group chats

The Telegram adapter currently has no `/chat` command.

Implement `/chat` so users can explicitly talk to the bot in group chats.

Behavior:

* `/chat Hello`
* Strip the command.
* Forward `"Hello"` to the existing ChatService exactly like a normal private message.
* Preserve:

  * telegram user id
  * username
  * group id
  * message metadata

Do not duplicate chat logic. Reuse the existing message handling pipeline.

---

# 2. Fix `/regenerate`

The current implementation does not regenerate from the correct context.

Implement the following behavior.

## Case A

Conversation

User

Assistant

Running `/regenerate` should:

1. Delete the last assistant reply from conversation history.
2. Delete the persisted assistant message.
3. Remove any cached provider history if applicable.
4. Regenerate using the last **user** message.
5. Persist the replacement.
6. Send the replacement to Telegram.

---

## Case B

Conversation

User

Assistant

/continue

Assistant

Running `/regenerate` should:

1. Remove only the continuation assistant reply.
2. Regenerate from the previous assistant message (the one that `/continue` extended).
3. Do **not** regenerate from the user message.

---

## Case C

Conversation

User

Assistant

Assistant

Assistant

Each `/regenerate` removes and regenerates only the latest assistant reply.

Requirements:

* Never duplicate conversation entries.
* Never leave orphaned persisted messages.
* Keep conversation history consistent.
* Ensure memory remains coherent after regeneration.

---

# 3. Improve default user identity

Current fallback:

```
telegram_user_123456789
```

Replace with the following priority order whenever no Persona exists.

Priority:

1. Persona display name
2. Telegram username
3. Telegram first name
4. Telegram first name + last name
5. `telegram_user_<id>`

Do not require a migration.

This should only affect the adapter's default identity resolution.

---

# 4. Implement beta registration

Unauthorized users should be able to request access.

Create a new command:

```
/beta
```

Behavior:

Store requests in:

```
data/
    telegram/
        beta_requests/
```

One JSON file per Telegram user.

Example:

```json
{
  "telegram_id": 123456789,
  "username": "PabloDonkey",
  "first_name": "Pablo",
  "last_name": "Smith",
  "requested_at": "<ISO-8601 timestamp>",
  "status": "waiting_for_beta_seat"
}
```

Requirements:

* Do not overwrite an existing request.
* If already registered, inform the user they are already on the waiting list.
* Store only adapter-specific data.
* No database.
* No domain model changes.
* Simple JSON persistence.

---

# 5. Improve unauthorized message

Replace the current authorization failure message.

New behavior:

Inform the user that:

* the bot is currently in closed beta;
* they are not yet authorized;
* they can request access using `/beta`;
* their Telegram username and ID will be recorded so the administrator can approve their request.

Keep the message friendly and concise.

---

# 6. Register Telegram commands

During adapter startup, register Telegram bot commands using `set_my_commands()`.

Register:

| Command     | Description                             |
| ----------- | --------------------------------------- |
| /chat       | Send a message to the current character |
| /continue   | Continue the previous assistant reply   |
| /regenerate | Regenerate the last assistant reply     |
| /clear      | Clear the current conversation          |
| /beta       | Request a beta seat                     |

This should enable Telegram's built-in **[/]** command menu.

## 7. Implement `/start`

Add support for the standard Telegram `/start` command.

Behavior:

* Register `/start` in the Telegram command menu.
* Handle it entirely within the Telegram adapter.
* Do not involve the LLM.
* Do not create or modify conversation history.
* Do not create memory entries.

### Authorized users

Display a short welcome message explaining:

* the bot is ready;
* how to start chatting using `/chat` (especially in groups);
* available commands:

  * `/chat`
  * `/continue`
  * `/regenerate`
  * `/clear`

In private chats, mention that users can also send normal messages directly if that behavior is supported by the adapter.

---

### Unauthorized users

Display a welcome message explaining:

* the bot is currently in closed beta;
* they are not yet authorized;
* they can request a beta seat using `/beta`;
* their Telegram username and Telegram ID will be recorded for administrator review.

Do **not** create a beta request automatically. The user must explicitly invoke `/beta`.

---

### Command Registration

Update `set_my_commands()` to include:

| Command     | Description                             |
| ----------- | --------------------------------------- |
| /start      | Show welcome message                    |
| /chat       | Send a message to the current character |
| /continue   | Continue the previous assistant reply   |
| /regenerate | Regenerate the last assistant reply     |
| /clear      | Clear the current conversation          |
| /beta       | Request a beta seat                     |

---

### Tests

Add tests covering:

* `/start` for authorized users.
* `/start` for unauthorized users.
* `/start` does not invoke the LLM.
* `/start` does not modify conversation history.
* `/start` does not create memory.
* `/start` does not automatically create a beta request.

---

# Documentation

Update any affected documentation, including command documentation if applicable.

Document:

* `/chat`
* `/beta`
* corrected `/regenerate` behavior

---

# Testing

Add or update tests covering:

* `/chat` in group chats.
* `/regenerate` after a normal assistant reply.
* `/regenerate` after `/continue`.
* Multiple consecutive regenerations.
* Username resolution priority.
* `/beta` request creation.
* Duplicate `/beta` requests.
* Unauthorized message.
* Telegram command registration.

---

# Acceptance Criteria

* `/chat` works correctly in groups.
* `/regenerate` always replaces only the most recent assistant response.
* `/continue` + `/regenerate` regenerates from the previous assistant message.
* Username resolution follows the specified priority.
* `/beta` creates exactly one waiting-list JSON per user.
* Duplicate registrations are prevented.
* Unauthorized users are invited to use `/beta`.
* Telegram displays the built-in **[/]** command menu.
* Beta request data is stored under `data/telegram/beta_requests/`.
* No Telegram-specific logic leaks into the application or core domain.
* Existing functionality continues to work without regression.
