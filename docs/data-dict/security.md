# 安全

管理用户违规行为检测和风险统计。

## user_violation_logs

用户安全日志表，记录用户恶意行为检测结果。

```txt
id -- Snowflake ID
user_id -- 关联users.id
user_qiao_id -- 关联users.qiao_id
instance_id -- 关联ai_instances.id（如果涉及特定AI）
instance_qiao_id -- 关联ai_instances.qiao_id
violation_type -- 违规类型（enum: ViolationType）
severity_level -- 严重程度（enum: SeverityLevel）
original_message -- 原始用户消息
auto_action_taken -- 自动处理动作（enum: AutoAction）
manual_review_status -- 人工审核状态（enum: ManualReviewStatus）
reviewer_id -- 审核管理员ID
review_notes -- 审核备注
created_at
updated_at
```

## user_risk_stats

用户安全统计表，汇总用户的违规行为统计。

```txt
id -- Snowflake ID
user_id -- 关联users.id
user_qiao_id -- 关联users.qiao_id
total_violations -- 总违规次数
violation_by_type -- 按类型统计，JSON格式：{"prompt_injection": 5, "abuse_content": 2}
last_violation_at -- 最后违规时间
current_risk_level -- 当前风险等级（enum: RiskLevel）
consecutive_violations -- 连续违规次数（清零条件：7天无违规）
warning_count -- 警告次数
restriction_count -- 限制次数
suspension_count -- 停用次数
last_action_at -- 最后处理动作时间
created_at
updated_at
```
