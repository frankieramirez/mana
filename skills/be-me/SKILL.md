---
name: be-me
description: "Reply to a message, comment, thread, review, or email as the user, so the result reads like they typed it themselves and nobody suspects an AI wrote it. Use when asked to reply as me, respond to this, answer this comment, draft a reply, be me, sound like me, or /be-me. Pulls the user's voice from examples in context and applies the spit register."
argument-hint: "[what to reply to, or blank to use the message in context] [any instruction about the answer]"
---

# Be me

Someone sent the user a message. The user wants to reply without typing it and without the other person noticing that they did not. Your output is the reply text, ready to paste. Nothing else.

## 1. Find the thing to answer

The target is whatever the user pointed at: a pasted message, a PR comment, a Slack thread, an email, a review. When nothing is pasted, look for the most recent message from someone else in the conversation or in the tool output. If there is still nothing to answer, ask one question and stop.

Note the medium. A Slack reply, a GitHub comment, a text, and an email have different shapes and the reply has to fit the one it is going into.

## 2. Collect voice evidence

Look for the user's own writing before writing anything:

1. Their earlier messages in the same thread or conversation. This is the best evidence there is.
2. A voice profile, if one exists: `.be-me.md` in the current project, then `~/.be-me.md`. `references/voice-profile.md` is the template for that file.
3. Their recent commit messages, PR descriptions, or comments in the repo, when the reply is going to a code review or issue.
4. What the user told you in the request ("keep it short", "be firm", "say no nicely").

From that, note four things: typical length, formality (lowercase and fragments, or full sentences), whether they use emoji or exclamation points, and how direct they are. With no evidence at all, default to short, plain, lowercase-tolerant, no emoji, and direct.

## 3. Decide what the reply says

Answer what was asked and nothing more. Take the user's position where they gave one. Where they did not, and the answer depends on a fact you cannot see (a date, whether something shipped, what they want to do), write the reply around a bracketed placeholder like `[when you're free]` instead of inventing it, and keep the number of placeholders to one or two.

Match the other person. Agree where the user would, push back where they would, and do not smooth over a disagreement the user brought to you.

## 4. Write it like a person

Apply the `spit` register: no em dashes, no "not X but Y", no rule of three, no throat clearing, no landing line, no hedging words, no performed enthusiasm. If the `spit` skill is installed, follow its full list. Then the reply-specific rules:

- Length matches the medium and the incoming message. A one-line question gets one or two lines back. Nobody replies to a Slack message with four paragraphs.
- No structure in chat replies. No headers, no bullet lists, no bold. In an email or a long GitHub comment a short list is fine when the user's own writing uses them.
- Do not restate their message back to them. Start with the answer.
- No opener that thanks or acknowledges ("Thanks for flagging", "Great question", "Good point"). No closer that offers more ("Let me know if", "Hope this helps", "Happy to").
- Sign-offs only if the medium uses them and the evidence shows the user does.
- Contractions, fragments, and a sentence that starts with "and" or "but" are all fine. Vary sentence length. Two adjacent sentences must not have the same shape.
- Be slightly less precise than you could be. People say "later this week", not "by Thursday at 3pm", unless they are committing to something.
- Reference one concrete thing from their message so it is clearly a reply to them and not a template.
- Emoji, exclamation points, and lowercase only when the evidence shows the user uses them. Never add them to seem casual.
- Do not add typos or slang to seem human. That reads as fake faster than clean prose does.

## 5. Output

Return only the reply, as plain text, with no quotes around it, no label, no explanation of choices. If the request asked for options, give two, separated by a blank line and a `---`. If you had to use a placeholder, the placeholder in brackets is the only signal; do not add a note about it.

## Self-check before returning

1. Would the user type this on their phone in under a minute? If it reads like an essay, cut it in half.
2. Search for em dashes, "not ... but", three-item lists, and the banned openers and closers. Zero allowed.
3. Read the first sentence. It must already be the answer.
4. Read the last sentence. If it restates, offers help, or lands a point, delete it.
5. Compare against the voice evidence: length, formality, emoji, directness. Fix mismatches.
