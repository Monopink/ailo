# Fix typing indicator state in mini-program

## Problem
Mini-program keeps showing typing indicator briefly after a content message arrives.
Current frontend typing state does not reset on content messages, ignores conv_id, and does not prevent out-of-order typing events.

## Goal
Align client behavior with design:
- Typing indicator ends on new content message or typing_end
- Typing events scoped to current conversation
- Ignore typing events from self
- Prevent out-of-order typing start after content
- Use config-based timeout

## Plan
- Extend adapter typing payload to carry sent_time
- Pass sent_time through adapter/service/event-bus to state store
- Update message state store to:
  - filter by conv_id
  - ignore self typing
  - clear typing on non-typing messages
  - ignore stale typing events based on last content sent_time
  - use MESSAGE_CONFIG.typingTimeout
- Update adapter interface doc

## Files
- frontend/wx-minipg/utils/message/adapter-types.ts
- frontend/wx-minipg/utils/message/leancloud.ts
- frontend/wx-minipg/utils/message/service.ts
- frontend/wx-minipg/utils/message/event-bus.ts
- frontend/wx-minipg/utils/message/message-state-store.ts
- frontend/wx-minipg/utils/message/ADAPTER_INTERFACE.md
