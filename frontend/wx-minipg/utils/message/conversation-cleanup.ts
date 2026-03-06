import {
  clearMessages,
  clearConversationViewPosition,
  getContacts,
  getConversationReadState,
  getConversationUnreadCounts,
  getConversationUnreadMarks,
  saveContacts,
  setConversationReadState,
  setConversationUnreadCounts,
  setConversationUnreadMarks,
} from '../storage';
import { isNonEmptyString } from '../guards';

const clearConversationPreview = async (convId: string): Promise<void> => {
  const contacts = await getContacts();
  const updatedContacts = contacts.map((contact) => {
    if (contact.conversation_id !== convId) {
      return contact;
    }
    return {
      ...contact,
      last_message: '',
      last_message_content: '',
      last_message_time: null,
    };
  });
  await saveContacts(updatedContacts);
};

const clearConversationUnreadState = async (convId: string): Promise<void> => {
  const unreadCounts = await getConversationUnreadCounts();
  delete unreadCounts[convId];
  await setConversationUnreadCounts(unreadCounts);

  const unreadMarks = await getConversationUnreadMarks();
  delete unreadMarks[convId];
  await setConversationUnreadMarks(unreadMarks);
};

const clearConversationReadState = async (convId: string): Promise<void> => {
  const readState = await getConversationReadState();
  delete readState[convId];
  await setConversationReadState(readState);
};

export async function clearLocalConversationState(convId: string): Promise<void> {
  if (!isNonEmptyString(convId)) {
    return;
  }

  await clearMessages(convId);
  await clearConversationViewPosition(convId);
  await clearConversationUnreadState(convId);
  await clearConversationReadState(convId);
  await clearConversationPreview(convId);
}
