---
type: llm
focus: last_message
weight: 1
---
Judge only the Slack message itself. Ignore a single short framing line such as "Here's the message:".

PASS only if all four hold:

1. The message is brief, in the range a person actually posts to a channel. A couple of sentences is right. Multiple paragraphs, or a message padded with reassurance, fails.
2. It uses no headers, no bullet list, and no bold section labels. Plain sentences only.
3. The opening says the deploy is delayed and that it is going out tomorrow. A greeting such as "Hey team" immediately followed by the news is fine. An apology, a preamble, or context placed ahead of the news fails.
4. The reason given is that the migration needs a second review, and no different reason is substituted.

Saying what happens next, such as promising to post a new time once the review lands, is normal for this kind of message and does not fail any claim.
