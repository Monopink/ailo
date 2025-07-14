# Frontend Development Rules

## UI Design Principles

### Modern macOS/Notion Style

- **Border Radius**: Smaller radius for windows/modals, larger for buttons/inputs
- **Colors**: Green primary (#42db5a), Yellow accent (#fdd700)
- **Effects**: Semi-transparent blur effects, inset shadow (embossed/engraved style)
- **Layout**: Unified chat interface without gaps between chat list and chat window
- **Buttons**: Rounded corners, circular send buttons with arrows
- **No Background Grid**: Clean, minimal design without grid patterns

### Strict No-Fallback Principle

- **Never use fallback data**: `user.nickname || user.username` is forbidden
- **Show nothing if data unavailable**: Don't hide data problems with defaults
- **Explicit error handling**: Expose errors clearly, no silent failures
- **No backward compatibility**: MVP phase, breaking changes acceptable

### Component Design Standards

- **Contact Items**: No borders, subtle rounded corners with hover effects
- **Modal Windows**: Smaller border radius, unified styling
- **Input Fields**: Unified sizes, configurable character limits via config files
- **Buttons**: Maintain hover color states, especially for red buttons
- **Avatars**: Use nickname first character, multiple size support

## Data Management

### API Integration

- **Unified API Client**: All calls use `apiClient` from `apiHelpers.js`
- **Authentication**: Automatic Bearer token handling
- **Error Handling**: Use `handleApiError` for consistent error messaging
- **Logging**: Structured API request/response logging in development

### State Management (Pinia)

- **Auth Store**: User authentication, profile setup status
- **Chat Store**: Chat lists, selected chat, contact limits
- **No Global State Pollution**: Keep stores focused and minimal

### Data Persistence

- **Local Storage**: Chat history, user preferences
- **Session Storage**: Multi-account support, temporary data
- **No Caching**: Always fetch fresh data, no stale data tolerance

## Specific Requirements

### Chat Interface

- **No Emojis**: Remove emojis from chat lists and interfaces
- **Empty State**: Show brand name with inset shadow instead of placeholder text
- **Timestamps**: Less frequent display, not on every message
- **Delete Buttons**: Clear chat history only, don't remove conversations
- **Desktop Layout**: Delete buttons inline with nicknames

### User Interface Elements

- **Phone Input**: No country flags for international codes
- **Password Toggle**: Monkey emoji for visibility toggle
- **Settings**: Single-line notification reminders, no toggle buttons
- **Error Containers**: Minimal reserved space when no errors present
- **Login Interface**: No background frames, elements integrated into page

### Contact Management

- **Terminology**: Use 'contact' instead of 'entity', 'bot', 'ai' in user-facing code
- **ID Mapping**: Frontend 'id' field maps to backend 'entity_id' (globally unique)
- **User Experience**: Treat bot users and regular users identically in frontend
- **Code Terminology**: Avoid 'bot', 'entity', 'ai' in frontend code and network requests
- **User Types**: Use 'type1', 'type2' to represent different user types internally
- **Contact Sections**: No bottom borders, rounded background styling
- **Selection Indicators**: Background-only, no colored bars
- **Gender Selection**: Use icons instead of text

## Technical Constraints

### Browser Compatibility

- **Cache Management**: Automatic cache refresh on system updates
- **No Manual Cache Clearing**: System handles cache invalidation
- **Progressive Enhancement**: Core functionality works without advanced features

### Performance

- **Polling Over WebSocket**: Use polling/querying instead of real-time connections
- **Lazy Loading**: Components and routes loaded on demand
- **Minimal Bundle Size**: Remove unused code and dependencies

### Development Practices

- **English Comments**: All code comments in English
- **Remove Test Code**: Clean up after testing
- **Config-driven**: Character limits and UI constraints in config files
- **Toast Notifications**: User-facing errors in Chinese, simple messages

## API Response Handling

### Error Messages

- **Business Errors**: Keep specific messages in errorHandler.js
- **Network Errors**: Simplified generic handling
- **User-friendly**: Chinese messages, no code exposure
- **Development Logs**: Detailed error information for debugging

### Data Types

- **Consistent Types**: Discuss frontend adaptation vs backend consistency
- **String IDs**: All entity references as strings
- **No Null Fallbacks**: Handle missing data explicitly
