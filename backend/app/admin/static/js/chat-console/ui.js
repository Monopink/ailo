export function formatGenderLabel(value) {
  if (value === 1) return '男';
  if (value === 2) return '女';
  if (value === 3) return '其他';
  return '-';
}

export function setAvatarImage(node, avatarUrl) {
  if (!node) {
    return;
  }
  if (!node.dataset.errorBound) {
    node.addEventListener('error', () => {
      node.removeAttribute('src');
      node.classList.add('is-empty');
    });
    node.dataset.errorBound = '1';
  }
  const text = typeof avatarUrl === 'string' ? avatarUrl.trim() : '';
  if (text) {
    node.src = text;
    node.classList.remove('is-empty');
    return;
  }
  node.removeAttribute('src');
  node.classList.add('is-empty');
}

export function formatTimestamp(ms) {
  if (!ms || !Number.isFinite(ms)) {
    return '';
  }
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(ms));
  } catch {
    return String(ms);
  }
}

function summaryFieldText(value) {
  if (value === null || value === undefined) {
    return '-';
  }
  const text = String(value).trim();
  return text || '-';
}

export function resetSnapshotPanel(el) {
  el.snapshotStatus.textContent = '';
  el.snapshotBase.textContent = '-';
  el.snapshotStylePersonality.textContent = '-';
  el.snapshotRelationship.textContent = '-';
  el.snapshotMemoryItems.textContent = '';
}

export function renderSnapshotPanel(el, snapshot) {
  if (!snapshot) {
    resetSnapshotPanel(el);
    return;
  }
  const relationship =
    snapshot.relationship && typeof snapshot.relationship === 'object' ? snapshot.relationship : null;
  const memoryItems = Array.isArray(snapshot.memory_items) ? snapshot.memory_items : [];

  el.snapshotStatus.textContent = '';
  el.snapshotBase.textContent = `${snapshot.instance_qiao_id || '-'} (${snapshot.instance_id || '-'})`;
  el.snapshotStylePersonality.textContent = `${
    snapshot.style && snapshot.style.display_name ? snapshot.style.display_name : '-'
  } | ${snapshot.personality && snapshot.personality.display_name ? snapshot.personality.display_name : '-'}`;
  el.snapshotRelationship.textContent = relationship
    ? `${relationship.display_name || '-'} | ${relationship.prompt_fragment || '-'}`
    : '-';
  el.snapshotMemoryItems.textContent = memoryItems.length
    ? memoryItems.map((item) => `[${item.memory_type}/${item.importance}] ${item.content}`).join('\n')
    : '';
}

export function clearAutoLlmDetails(el) {
  if (el.llmAutoSystemPrompt) el.llmAutoSystemPrompt.textContent = '-';
  if (el.llmAutoFlags) el.llmAutoFlags.textContent = '-';
  if (el.llmAutoInternalThoughts) el.llmAutoInternalThoughts.textContent = '-';
  if (el.llmAutoCurrentState) el.llmAutoCurrentState.textContent = '-';
  if (el.llmAutoOutgoing) el.llmAutoOutgoing.textContent = '-';
  if (el.llmAutoFollowup) el.llmAutoFollowup.textContent = '-';
  if (el.llmAutoScores) el.llmAutoScores.textContent = '-';
  if (el.llmAutoRelationship) el.llmAutoRelationship.textContent = '-';
  if (el.llmAutoMemoryOps) el.llmAutoMemoryOps.textContent = '-';
  if (el.llmAutoPerf) el.llmAutoPerf.textContent = '-';
  if (el.llmAutoRequest) el.llmAutoRequest.textContent = '-';
  if (el.llmAutoResponse) el.llmAutoResponse.textContent = '-';
}

export function renderAutoLlmDetail(el, item) {
  if (!item || !item.found) {
    clearAutoLlmDetails(el);
    if (el.llmAutoFlags) {
      el.llmAutoFlags.textContent = '未找到';
    }
    return;
  }
  const summary = item.summary && typeof item.summary === 'object' ? item.summary : {};
  if (el.llmAutoFlags) {
    el.llmAutoFlags.textContent = [
      `should_reply=${summary.should_reply ?? '-'}`,
      `should_block=${summary.should_block ?? '-'}`,
      `attack_detected=${summary.attack_detected ?? '-'}`,
      `memory_update=${summary.should_update_memory ?? '-'}`,
    ].join(' | ');
  }
  if (el.llmAutoSystemPrompt) {
    el.llmAutoSystemPrompt.textContent = summaryFieldText(summary.system_prompt_preview);
  }
  if (el.llmAutoInternalThoughts) {
    el.llmAutoInternalThoughts.textContent = summaryFieldText(summary.internal_thoughts_preview);
  }
  if (el.llmAutoCurrentState) {
    el.llmAutoCurrentState.textContent = summaryFieldText(summary.current_state_preview);
  }
  if (el.llmAutoOutgoing) {
    el.llmAutoOutgoing.textContent = summaryFieldText(summary.outgoing_messages_preview);
  }
  if (el.llmAutoFollowup) {
    el.llmAutoFollowup.textContent = summaryFieldText(summary.followup_messages_preview);
  }
  if (el.llmAutoScores) {
    el.llmAutoScores.textContent = summaryFieldText(summary.score_updates_preview);
  }
  if (el.llmAutoRelationship) {
    el.llmAutoRelationship.textContent = summaryFieldText(summary.relationship_selection_preview);
  }
  if (el.llmAutoMemoryOps) {
    el.llmAutoMemoryOps.textContent = summaryFieldText(summary.memory_operations_preview);
  }
  if (el.llmAutoPerf) {
    el.llmAutoPerf.textContent = [
      `status=${item.status ?? '-'}`,
      `tokens=${item.token_count ?? '-'}`,
      `rt_ms=${item.response_time_ms ?? '-'}`,
      `model=${item.model_name || '-'}`,
      `finish_reason=${summary.finish_reason || '-'}`,
      `outgoing_count=${summary.outgoing_messages_count ?? 0}`,
      `followup_count=${summary.followup_messages_count ?? 0}`,
      `memory_ops_count=${summary.memory_operations_count ?? 0}`,
    ].join(' | ');
  }
  if (el.llmAutoRequest) {
    el.llmAutoRequest.textContent = item.request_preview || '-';
  }
  if (el.llmAutoResponse) {
    el.llmAutoResponse.textContent = item.response_preview || '-';
  }
}

export function formatLlmRequestDetails(details, normalizeLlmRequestId) {
  if (!Array.isArray(details) || !details.length) {
    return '';
  }

  const blocks = [];
  for (const item of details) {
    const llmRequestId = normalizeLlmRequestId(item && item.llm_request_id);
    if (!item || !llmRequestId) {
      continue;
    }
    if (!item.found) {
      blocks.push(`#${llmRequestId}\n未找到`);
      continue;
    }

    const summary = item.summary && typeof item.summary === 'object' ? item.summary : {};
    const metaLine = [
      `#${llmRequestId}`,
      `status=${item.status ?? '-'}`,
      `provider=${item.provider_name || '-'}`,
      `model=${item.model_name || '-'}`,
      `tokens=${item.token_count ?? '-'}`,
      `rt_ms=${item.response_time_ms ?? '-'}`,
      `created_at=${item.created_at || '-'}`,
    ].join(' | ');
    const summaryLine = [
      `should_reply=${summary.should_reply ?? '-'}`,
      `should_block=${summary.should_block ?? '-'}`,
      `attack_detected=${summary.attack_detected ?? '-'}`,
      `memory_update=${summary.should_update_memory ?? '-'}`,
      `outgoing=${summary.outgoing_messages_count ?? 0}`,
      `followup=${summary.followup_messages_count ?? 0}`,
      `memory_ops=${summary.memory_operations_count ?? 0}`,
      `finish_reason=${summary.finish_reason || '-'}`,
    ].join(' | ');
    const scoreKeys =
      Array.isArray(summary.score_keys) && summary.score_keys.length ? summary.score_keys.join(', ') : '-';

    blocks.push(
      [
        metaLine,
        `summary: ${summaryLine}`,
        `score_keys: ${scoreKeys}`,
        `system_prompt: ${summary.system_prompt_preview || '-'}`,
        `internal_thoughts: ${summary.internal_thoughts_preview || '-'}`,
        `current_state: ${summary.current_state_preview || '-'}`,
        `outgoing: ${summary.outgoing_messages_preview || '-'}`,
        `followup: ${summary.followup_messages_preview || '-'}`,
        `score_updates: ${summary.score_updates_preview || '-'}`,
        `relationship: ${summary.relationship_selection_preview || '-'}`,
        `memory_ops: ${summary.memory_operations_preview || '-'}`,
        'request_preview:',
        item.request_preview || '-',
        'response_preview:',
        item.response_preview || '-',
      ].join('\n')
    );
  }

  return blocks.join('\n\n----------------\n\n');
}
