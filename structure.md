# Codebase Organization Report for nlp-service

I'll list all the individual files in the nlp-service directory, organized by folder:

## Complete File List for nlp-service

### Root Directory Files:
1. .env.example
2. Dockerfile
3. README.md
4. analytics.py
5. app_dependencies.py
6. async_patterns.py
7. cache.py
8. chat_history.py
9. circuit_breaker.py
10. config.py
11. conftest.py
12. context_retrieval.py
13. database.py
14. dependencies.py
15. document_scanning/schemas/medical_bill.py
16. entity_extractor.py
17. error_handling.py
18. integrated_ai_service.py
19. intent_recognizer.py
20. keywords.py
21. main.py
22. memory_aware_agents.py
23. memory_manager.py
24. memory_middleware.py
25. memory_observability.py
26. memory_performance.py
27. ml_risk_assessor.py
28. model_versioning.py
29. models.py
30. ollama_generator.py
31. prompt_builder.py
32. pytest.ini
33. rag_api.py
34. rate_limiting.py
35. requirements.txt
36. risk_assessor.py
37. security.py
38. sentiment_analyzer.py
39. structured_outputs.py
40. telemetry.py
41. user_preferences.py

### agents/ Directory:
42. agents/__init__.py
43. agents/base.py
44. agents/cardio_specialist.py
45. agents/config.py
46. agents/crew_simulation.py
47. agents/health_agent.py
48. agents/langgraph_orchestrator.py
49. agents/orchestrator.py
50. agents/planner.py
51. agents/task_executor.py

### appointments/ Directory:
52. appointments/__init__.py
53. appointments/agents.py
54. appointments/models.py
55. appointments/service.py

### calendar_integration/ Directory:
56. calendar_integration/__init__.py
57. calendar_integration/agents.py
58. calendar_integration/google_service.py
59. calendar_integration/models.py
60. calendar_integration/notifications.py
61. calendar_integration/outlook_service.py
62. calendar_integration/scheduler.py

### compliance/ Directory:
63. compliance/__init__.py
64. compliance/audit_logger.py
65. compliance/consent_manager.py
66. compliance/data_retention.py
67. compliance/disclaimer_service.py
68. compliance/encryption_service.py
69. compliance/verification_queue.py

### core/ Directory:
70. core/__init__.py
71. core/guardrails.py
72. core/langchain_gateway.py
73. core/llm_gateway.py
74. core/observable_llm_gateway.py

### document_scanning/ Directory:
75. document_scanning/__init__.py
76. document_scanning/classifier.py
77. document_scanning/ingestion.py
78. document_scanning/ocr_engine.py
79. document_scanning/unstructured_processor.py
80. document_scanning/schemas/__init__.py
81. document_scanning/schemas/medical_bill.py

### engines/ Directory:
82. engines/__init__.py

### evaluation/ Directory:
83. evaluation/__init__.py
84. evaluation/rag_evaluator.py

### integrations/ Directory:
85. integrations/__init__.py
86. integrations/chatbot_document_context.py
87. integrations/doctor_dashboard.py
88. integrations/prediction_integration.py
89. integrations/timeline_service.py
90. integrations/weekly_aggregation.py

### knowledge_graph/ Directory:
91. knowledge_graph/__init__.py
92. knowledge_graph/graph_rag.py
93. knowledge_graph/neo4j_service.py

### medical_ai/ Directory:
94. medical_ai/__init__.py
95. medical_ai/medgemma_service.py
96. medical_ai/multimodal_processor.py
97. medical_ai/terminology_normalizer.py

### memori/ Directory:
98. memori/__init__.py

### memori/agents/ Directory:
99. memori/agents/__init__.py
100. memori/agents/conversational_agent.py
101. memori/agents/memory_agent.py
102. memori/agents/reasoning_agent.py
103. memori/agents/search_agent.py
104. memori/agents/update_agent.py

### memori/config/ Directory:
105. memori/config/__init__.py
106. memori/config/agent_config.py
107. memori/config/cache_config.py
108. memori/config/database_config.py
109. memori/config/embedding_config.py
110. memori/config/pool_config.py

### memori/core/ Directory:
111. memori/core/__init__.py
112. memori/core/agent_coordinator.py
113. memori/core/memory_engine.py
114. memori/core/persistence_layer.py
115. memori/core/query_processor.py
116. memori/core/session_manager.py

### memori/database/ Directory:
117. memori/database/__init__.py
118. memori/database/backup_manager.py
119. memori/database/data_migrator.py
120. memori/database/index_optimizer.py
121. memori/database/memory_repository.py
122. memori/database/query_optimizer.py
123. memori/database/schema_manager.py

### memori/database/queries/ Directory:
124. memori/database/queries/__init__.py
125. memori/database/queries/chat_queries.py
126. memori/database/queries/memory_queries.py
127. memori/database/queries/search_queries.py

### memori/integrations/ Directory:
128. memori/integrations/__init__.py
129. memori/integrations/api_client.py
130. memori/integrations/calendar_sync.py
131. memori/integrations/document_processor.py
132. memori/integrations/health_data_sync.py

### memori/security/ Directory:
133. memori/security/__init__.py
134. memori/security/access_control.py
135. memori/security/encryption_manager.py

### memori/tools/ Directory:
136. memori/tools/__init__.py
137. memori/tools/anonymizer.py
138. memori/tools/exporter.py

### memori/utils/ Directory:
139. memori/utils/__init__.py
140. memori/utils/cache_utils.py
141. memori/utils/date_utils.py
142. memori/utils/embedding_utils.py
143. memori/utils/error_utils.py
144. memori/utils/file_utils.py
145. memori/utils/formatting_utils.py
146. memori/utils/hash_utils.py
147. memori/utils/json_utils.py
148. memori/utils/logging_utils.py
149. memori/utils/memory_utils.py
150. memori/utils/metric_utils.py
151. memori/utils/network_utils.py
152. memori/utils/notification_utils.py
153. memori/utils/pagination_utils.py
154. memori/utils/parser_utils.py
155. memori/utils/path_utils.py
156. memori/utils/proxy_utils.py
157. memori/utils/retry_utils.py
158. memori/utils/string_utils.py
159. memori/utils/thread_utils.py
160. memori/utils/timezone_utils.py
161. memori/utils/validation_utils.py

### middleware/ Directory:
162. middleware/__init__.py

### models/ Directory:
163. models/__init__.py

### monitoring/ Directory:
164. monitoring/__init__.py
165. monitoring/phoenix_monitor.py

### notifications/ Directory:
166. notifications/__init__.py

### rag/ Directory:
167. rag/__init__.py
168. rag/embedding_onnx.py
169. rag/embedding_service.py
170. rag/llama_index_pipeline.py
171. rag/memori_integration.py
172. rag/model_converter.py
173. rag/rag_pipeline.py
174. rag/vector_store.py

### rag/knowledge_base/ Directory:
175. rag/knowledge_base/__init__.py
176. rag/knowledge_base/cardiovascular_guidelines.py
177. rag/knowledge_base/drug_database.py
178. rag/knowledge_base/knowledge_loader.py
179. rag/knowledge_base/symptom_checker.py

### realtime/ Directory:
180. realtime/__init__.py

### routes/ Directory:
181. routes/__init__.py
182. routes/agents.py
183. routes/calendar_routes.py
184. routes/compliance_routes.py
185. routes/document_routes.py
186. routes/evaluation_routes.py
187. routes/generation.py
188. routes/integrations_routes.py
189. routes/knowledge_graph_routes.py
190. routes/medical_ai_routes.py
191. routes/memory.py
192. routes/notifications_routes.py
193. routes/tools_routes.py
194. routes/vision_routes.py
195. routes/weekly_summary_routes.py

### services/ Directory:
196. services/__init__.py
197. services/advanced_cache.py
198. services/analyzer_protocol.py
199. services/di_container.py
200. services/encryption_service.py
201. services/health_service.py
202. services/nlp_service.py
203. services/observability.py
204. services/resilience.py

### structured_outputs/ Directory:
205. structured_outputs/__init__.py

### tools/ Directory:
206. tools/__init__.py

### vision/ Directory:
207. vision/__init__.py
208. vision/ecg_analyzer.py
209. vision/food_recognition.py
210. vision/vision_service.py

### weekly_summary/ Directory:
211. weekly_summary/__init__.py

That's a total of 211 files in the nlp-service directory. Would you like me to provide more details about any specific files or directories?


## Executive Summary

This document outlines a proposed restructuring of the nlp-service codebase to improve organization, maintainability, and team collaboration. The restructuring separates functionality into three main areas: chatbot, medgemma, and shared components.

## Proposed Directory Structure

```
nlp-service/
├── chatbot/
│   ├── core/
│   ├── agents/
│   ├── memory/
│   ├── routes/
│   ├── services/
│   ├── utils/
│   └── __init__.py
│
├── medgemma/
│   ├── core/
│   ├── models/
│   ├── processors/
│   ├── routes/
│   ├── services/
│   ├── knowledge_base/
│   └── __init__.py
│
├── shared/
│   ├── common/
│   ├── config/
│   ├── database/
│   ├── exceptions/
│   ├── middleware/
│   ├── security/
│   ├── telemetry/
│   └── __init__.py
│
├── main.py
└── requirements.txt
```

## Detailed File Distribution

### 1. Chatbot Folder Structure

#### chatbot/core/
- intent_recognizer.py
- sentiment_analyzer.py
- entity_extractor.py
- prompt_builder.py
- response_generator.py

#### chatbot/agents/
- conversational_agent.py
- orchestrator.py
- langgraph_orchestrator.py
- planner.py
- task_executor.py
- base.py
- health_agent.py
- cardio_specialist.py

#### chatbot/memory/
- chat_history.py
- memory_manager.py
- memory_middleware.py
- memory_aware_agents.py
- memory_observability.py
- memory_performance.py

#### chatbot/routes/
- chat_routes.py (consolidated from existing routes)
- generation.py
- agents.py
- memory.py

#### chatbot/services/
- nlp_service.py
- chat_service.py
- context_service.py
- session_service.py

#### chatbot/utils/
- chat_utils.py
- formatting_utils.py
- validation_utils.py

### 2. MedGemma Folder Structure

#### medgemma/core/
- medgemma_service.py
- multimodal_processor.py
- terminology_normalizer.py
- llm_gateway.py
- observable_llm_gateway.py
- langchain_gateway.py

#### medgemma/models/
- medical_models.py (consolidated medical data models)
- patient_data.py
- diagnosis_models.py

#### medgemma/processors/
- document_scanning/
  - classifier.py
  - ingestion.py
  - ocr_engine.py
  - unstructured_processor.py
- vision/
  - ecg_analyzer.py
  - food_recognition.py
  - vision_service.py

#### medgemma/routes/
- medical_ai_routes.py
- document_routes.py
- vision_routes.py

#### medgemma/services/
- health_service.py
- diagnostic_service.py
- prediction_service.py

#### medgemma/knowledge_base/
- cardiovascular_guidelines.py
- drug_database.py
- symptom_checker.py
- knowledge_loader.py
- graph_rag.py
- neo4j_service.py

### 3. Shared Folder Structure

#### shared/common/
- utils.py
- constants.py
- enums.py
- helpers.py

#### shared/config/
- config.py
- environment.py
- settings.py

#### shared/database/
- database.py
- connection.py
- queries/ (moved from memori/database/queries/)
  - chat_queries.py
  - memory_queries.py
  - search_queries.py

#### shared/exceptions/
- error_handling.py
- exceptions.py
- validation_errors.py

#### shared/middleware/
- middleware/__init__.py
- auth_middleware.py
- logging_middleware.py
- rate_limiting.py
- circuit_breaker.py

#### shared/security/
- security.py
- encryption_service.py
- compliance/ (moved from root compliance/)
  - audit_logger.py
  - consent_manager.py
  - data_retention.py
  - disclaimer_service.py

#### shared/telemetry/
- analytics.py
- telemetry.py
- monitoring/
  - phoenix_monitor.py

## Migration Plan

### Phase 1: Preparation
1. Create the new directory structure
2. Set up proper `__init__.py` files
3. Configure Python path updates

### Phase 2: Component Migration
1. Move chatbot-related files to chatbot/ directory
2. Move medgemma-related files to medgemma/ directory
3. Consolidate shared components in shared/ directory

### Phase 3: Dependency Updates
1. Update import statements across all files
2. Modify relative imports to reflect new structure
3. Update configuration files and Dockerfile

### Phase 4: Testing & Validation
1. Run unit tests to ensure functionality
2. Perform integration testing
3. Validate API endpoints

## Benefits of This Structure

1. **Clear Separation of Concerns**: Each major functionality has its own dedicated space
2. **Improved Maintainability**: Teams can work on chatbot or medgemma independently
3. **Better Collaboration**: Reduced merge conflicts and clearer ownership
4. **Enhanced Scalability**: Easy to add new features without cluttering existing code
5. **Simplified Onboarding**: New developers can understand the codebase structure quickly

## Implementation Considerations

1. **Import Path Updates**: All import statements will need to be updated
2. **Configuration Changes**: Environment variables and config files may need adjustments
3. **Testing Updates**: Test files and configurations will need to be moved/updated
4. **Documentation**: README and other documentation will need to reflect new structure
5. **CI/CD Pipeline**: Build and deployment scripts may require updates

## Timeline Estimate

- Phase 1: 1-2 days
- Phase 2: 3-5 days
- Phase 3: 2-3 days
- Phase 4: 2-3 days
- Total: Approximately 8-13 days

## Conclusion

This restructuring will significantly improve the maintainability and scalability of the nlp-service codebase. The clear separation between chatbot, medgemma, and shared components will facilitate better team collaboration and make future development more efficient.