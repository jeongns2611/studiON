CREATE TABLE `clip` (
	`id`	INT	NOT NULL	COMMENT '클립id',
	`track_id`	INT	NOT NULL	COMMENT '트랙id',
	`audio_metadata_id`	INT	NOT NULL	COMMENT '오디오 메타데이터id',
	`color`	CHAR(7)	NOT NULL	DEFAULT '#FFFFFF'	COMMENT '클립색상',
	`start`	DECIMAL(11, 7)	NOT NULL	DEFAULT 1	COMMENT '시작점 (마디기준)',
	`duration`	DECIMAL(11,7)	NOT NULL	DEFAULT 1	COMMENT '클립길이 (마디기준)',
	`audio_start_ms`	BIGINT	NOT NULL	DEFAULT 0	COMMENT '오디오 시작점 (오디오기준)',
	`audio_duration_ms`	BIGINT	NOT NULL	COMMENT '오디오 길이 (오디오기준)'
);

CREATE TABLE `comment_mention` (
	`userId`	INT	NOT NULL	COMMENT '회원id',
	`commentId`	INT	NOT NULL	COMMENT '댓글id'
);

CREATE TABLE `dm_room_member` (
	`roomId`	INT	NOT NULL	COMMENT '채팅방id',
	`userId`	INT	NOT NULL	COMMENT '회원id'
);

CREATE TABLE `user` (
	`id`	INT	NOT NULL	COMMENT '회원id',
	`email`	VARCHAR(255)	NOT NULL	COMMENT '이메일(로그인 식별자)',
	`provider`	VARCHAR(20)	NOT NULL	COMMENT '인증수단(google, kakao, naver)',
	`providerId`	VARCHAR(100)	NOT NULL	COMMENT 'oauth 인증id',
	`profileImgUrl`	VARCHAR(255)	NULL	COMMENT 'oauth 프로필 이미지',
	`nickname`	VARCHAR(20)	NOT NULL	COMMENT '닉네임',
	`lastLoginAt`	DATETIME	NOT NULL	COMMENT '마지막 로그인 일시',
	`deletedAt`	DATETIME	NULL	COMMENT '삭제일시'
);

CREATE TABLE `ai_suggestion_action` (
	`id`	INT	NOT NULL	COMMENT '수정 액션 ID',
	`suggestionId`	INT	NOT NULL	COMMENT '수정안 ID',
	`actionTypeCode`	TINYINT	NOT NULL	COMMENT '수정 액션 유형 코드',
	`clipId`	INT	NOT NULL	COMMENT '대상 클립 ID',
	`startMs`	INT	NULL	COMMENT '적용 시작 시각',
	`endMs`	INT	NULL	COMMENT '적용 종료 시각',
	`bandLowHz`	MEDIUMINT	NULL	COMMENT '적용 대역 시작 주파수',
	`bandHighHz`	MEDIUMINT	NULL	COMMENT '적용 대역 끝 주파수',
	`gainDeltaDb`	DECIMAL(6, 3)	NULL	COMMENT '볼륨 변화량',
	`moveDeltaMs`	MEDIUMINT	NULL	COMMENT '클립 이동량',
	`paramsJson`	JSON	NULL	COMMENT '추가 파라미터',
	`targetScopeCode`	TINYINT	NOT NULL	DEFAULT 1	COMMENT '대상 범위 코드',
	`targetTrackId`	INT	NULL	COMMENT '대상 트랙 ID',
	`sourceTrackId`	INT	NULL	COMMENT '트리거 트랙 ID',
	`sourceClipId`	INT	NULL	COMMENT '트리거 클립 ID'
);

CREATE TABLE `ai_track_vocal_prediction` (
	`id`	INT	NOT NULL	COMMENT '트랙 보컬 판별 결과 ID',
	`trackId`	INT	NOT NULL	COMMENT '트랙 ID',
	`jobId`	INT	NOT NULL	COMMENT 'AI 분석 작업 ID',
	`vocalScore`	DECIMAL(6, 5)	NOT NULL	COMMENT '보컬성 점수',
	`isVocal`	BOOLEAN	NOT NULL	DEFAULT FALSE	COMMENT '보컬 트랙 여부',
	`confidence`	DECIMAL(6, 5)	NULL	COMMENT '판별 신뢰도'
);

CREATE TABLE `user_position` (
	`userId`	INT	NOT NULL	COMMENT '회원id',
	`positionCode`	INT	NOT NULL	COMMENT '포지션 상세코드'
);

CREATE TABLE `track` (
	`id`	INT	NOT NULL	COMMENT '트랙id',
	`projectId`	INT	NOT NULL	COMMENT '프로젝트id',
	`preTrackId`	INT	NULL	COMMENT '한 칸 위의 트랙id (정렬용)',
	`postTrackId`	INT	NULL	COMMENT '한 칸 뒤의 트랙id (정렬용)',
	`type`	ENUM	NOT NULL	DEFAULT audio	COMMENT '트랙타입(audio, midi)',
	`name`	VARCHAR(255)	NULL	COMMENT '트랙명',
	`isSoloed`	BOOLEAN	NOT NULL	DEFAULT FALSE	COMMENT '솔로 활성화 여부',
	`isMuted`	BOOLEAN	NOT NULL	DEFAULT FALSE	COMMENT '음소거 활성화 여부',
	`volume`	TINYINT	NOT NULL	DEFAULT 0	COMMENT '음량',
	`pan`	TINYINT	NOT NULL	DEFAULT 0	COMMENT '패닝'
);

CREATE TABLE `ai_offline_eval_item` (
	`id`	BIGINT	NOT NULL	COMMENT '오프라인 평가 항목 ID',
	`evalRunId`	BIGINT	NOT NULL	COMMENT '오프라인 평가 실행 ID',
	`jobId`	INT	NOT NULL	COMMENT 'AI 분석 작업 ID',
	`suggestionId`	INT	NULL	COMMENT '수정안 ID',
	`verdictCode`	TINYINT	NOT NULL	COMMENT '판정 코드',
	`score`	DECIMAL(6, 5)	NULL	COMMENT '점수',
	`artifactDocId`	VARCHAR(64)	NULL	COMMENT 'MongoDB 상세 결과 문서 ID',
	`createdAt`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각'
);

CREATE TABLE `ai_rag_retrieval` (
	`id`	INT	NOT NULL	COMMENT 'RAG 검색 로그 ID',
	`jobId`	INT	NOT NULL	COMMENT 'AI 분석 작업 ID',
	`regionId`	INT	NULL	COMMENT '분석 구간 ID',
	`queryText`	VARCHAR(255)	NOT NULL	COMMENT '검색 쿼리',
	`topK`	TINYINT	NOT NULL	COMMENT '검색 문서 수',
	`qualityScore`	DECIMAL(6, 5)	NULL	COMMENT '검색 품질 점수',
	`createdAt`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각'
);

CREATE TABLE `project_members` (
	`projectId`	INT	NOT NULL	COMMENT '프로젝트id',
	`userId`	INT	NOT NULL	COMMENT '회원id'
);

CREATE TABLE `ai_offline_eval_run` (
	`id`	BIGINT	NOT NULL	COMMENT '오프라인 평가 실행 ID',
	`evaluatorModelName`	VARCHAR(100)	NOT NULL	COMMENT '평가 모델명',
	`promptVersion`	VARCHAR(50)	NOT NULL	COMMENT '프롬프트 버전',
	`ruleVersion`	VARCHAR(50)	NOT NULL	COMMENT '룰 버전',
	`sampleCount`	INT	NOT NULL	DEFAULT 0	COMMENT '평가 건수',
	`passCount`	INT	NOT NULL	DEFAULT 0	COMMENT '통과 건수',
	`failCount`	INT	NOT NULL	DEFAULT 0	COMMENT '실패 건수',
	`createdAt`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각'
);

CREATE TABLE `ai_applied_suggestion` (
	`id`	INT	NOT NULL	COMMENT '적용 수정안 ID',
	`jobId`	INT	NOT NULL	COMMENT 'AI 분석 작업 ID',
	`suggestionId`	INT	NOT NULL	COMMENT '수정안 ID',
	`beforeSnapshotId`	INT	NULL	COMMENT '적용 전 스냅샷 ID',
	`afterSnapshotId`	INT	NULL	COMMENT '적용 후 스냅샷 ID',
	`appliedBy`	INT	NOT NULL	COMMENT '적용 사용자 ID',
	`statusCode`	TINYINT	NOT NULL	COMMENT '적용 상태 코드'
);

CREATE TABLE `comment` (
	`id`	INT	NOT NULL	COMMENT '댓글id',
	`trackId`	INT	NOT NULL	COMMENT '트랙id',
	`userId`	INT	NOT NULL	COMMENT '회원id',
	`content`	TEXT	NOT NULL	COMMENT '댓글 내용',
	`location`	DECIMAL(11, 7)	NOT NULL	COMMENT '댓글 달린 마디 위치',
	`deletedAt`	DATETIME	NULL	COMMENT '삭제일시',
	`isResolved`	BOOLEAN	NOT NULL	DEFAULT FALSE	COMMENT '해결여부'
);

CREATE TABLE `audio_metadata` (
	`id`	INT	NOT NULL	COMMENT '오디오메타데이터id',
	`object_key`	VARCHAR(1024)	NOT NULL	COMMENT 'S3_key',
	`original_name`	VARCHAR(255)	NOT NULL	COMMENT '사용자가 입력한 원본 파일명',
	`stored_name`	VARCHAR(255)	NOT NULL	COMMENT '서버 관리용 파일명(UUID)',
	`mime_type`	ENUM	NULL	COMMENT '콘텐츠 형식/전송 타입(audio/mpeg, audio/wav)',
	`size_bytes`	INT	NOT NULL	COMMENT '파일 크기(바이트 단위)',
	`duration_ms`	INT	NOT NULL	COMMENT '오디오 길이',
	`deleted_at`	DATETIME	NULL	COMMENT '삭제일시(soft delete)'
);

CREATE TABLE `ai_suggestion` (
	`id`	INT	NOT NULL	COMMENT '수정안 ID',
	`groupId`	INT	NOT NULL	COMMENT '수정안 그룹 ID',
	`rankNo`	TINYINT	NOT NULL	COMMENT '추천 순위',
	`summary`	VARCHAR(255)	NOT NULL	COMMENT '수정안 요약',
	`explanation`	TEXT	NULL	COMMENT '수정안 설명',
	`validationStatusCode`	TINYINT	NOT NULL	COMMENT '수정안 검증 상태 코드',
	`judgeScore`	DECIMAL(6, 5)	NULL	COMMENT '평가 점수'
);

CREATE TABLE `position_detail` (
	`code`	INT	NOT NULL	COMMENT '상세코드',
	`groupCode`	INT	NOT NULL	COMMENT '그룹코드',
	`name`	VARCHAR(50)	NOT NULL	COMMENT '코드명',
	`order`	TINYINT	NOT NULL	COMMENT '정렬 순서'
);

CREATE TABLE `project_edit_event_log` (
	`logId`	BIGINT	NOT NULL	COMMENT '로그id',
	`eventType`	ENUM	NOT NULL	COMMENT '이벤트타입 (enum or 공통코드)',
	`payload`	JSON	NOT NULL	COMMENT '변경내용',
	`sequence`	INT	NOT NULL	COMMENT '프로젝트 내 편집 순서(cusor 이동 시 사용)',
	`createdAt`	DATETIME	NOT NULL	COMMENT '생성일시',
	`projectId`	INT	NOT NULL	COMMENT '프로젝트id',
	`userId`	INT	NOT NULL	COMMENT '유저id'
);

CREATE TABLE `ai_rag_retrieval_doc` (
	`id`	INT	NOT NULL	COMMENT 'RAG 검색 결과 문서 ID',
	`rankNo`	TINYINT	NOT NULL	COMMENT '검색 순위',
	`score`	DECIMAL(8, 6)	NULL	COMMENT '검색 점수',
	`snippet`	TEXT	NULL	COMMENT '사용 문단',
	`retrievalId`	INT	NOT NULL	COMMENT 'RAG 검색 로그 ID',
	`ragDocumentId`	INT	NOT NULL	COMMENT 'RAG 문서 ID'
);

CREATE TABLE `ai_rag_document` (
	`id`	INT	NOT NULL	COMMENT 'RAG 문서 ID',
	`title`	VARCHAR(255)	NOT NULL	COMMENT '문서 제목',
	`body`	TEXT	NOT NULL	COMMENT '문서 본문',
	`genreMain`	VARCHAR(50)	NULL	COMMENT '주 장르',
	`genreSub`	VARCHAR(50)	NULL	COMMENT '세부 장르',
	`conflictBand`	VARCHAR(50)	NULL	COMMENT '충돌 대역',
	`conflictType`	VARCHAR(80)	NULL	COMMENT '충돌 유형',
	`clipCharacter`	VARCHAR(80)	NULL	COMMENT '클립 성격',
	`actionType`	VARCHAR(80)	NULL	COMMENT '수정 방식',
	`appliesWhen`	TEXT	NULL	COMMENT '적용 조건',
	`avoidWhen`	TEXT	NULL	COMMENT '피해야 할 조건',
	`source`	VARCHAR(255)	NULL	COMMENT '출처',
	`vectorStore`	VARCHAR(50)	NULL	COMMENT '벡터 저장소 종류',
	`vectorRef`	VARCHAR(255)	NULL	COMMENT '벡터 저장소 참조값',
	`createdAt`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각',
	`updatedAt`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '수정 시각'
);

CREATE TABLE `system_column` (
	`createdAt`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성일시',
	`createdBy`	INT	NOT NULL	DEFAULT 0	COMMENT '생성자',
	`updatedAt`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '수정일시',
	`updatedBy`	INT	NOT NULL	DEFAULT 0	COMMENT '수정자'
);

CREATE TABLE `ai_snapshot_ref` (
	`id`	INT	NOT NULL	COMMENT 'AI 분석 타임라인 스냅샷 ID',
	`projectId`	INT	NOT NULL	COMMENT '프로젝트 ID',
	`snapshotTypeCode`	TINYINT	NOT NULL	COMMENT '스냅샷 유형 코드',
	`snapshotDocId`	VARCHAR(64)	NOT NULL	COMMENT 'MongoDB 문서 ID',
	`snapshotHash`	CHAR(64)	NULL	COMMENT '스냅샷 해시',
	`summary`	VARCHAR(255)	NULL	COMMENT '스냅샷 요약'
);

CREATE TABLE `ai_runtime_critic_result` (
	`id`	BIGINT	NOT NULL	COMMENT '런타임 critic 결과 ID',
	`jobId`	INT	NOT NULL	COMMENT 'AI 분석 작업 ID',
	`suggestionId`	INT	NOT NULL	COMMENT '수정안 ID',
	`modelName`	VARCHAR(100)	NOT NULL	COMMENT '모델명',
	`verdictCode`	TINYINT	NOT NULL	COMMENT '판정 코드',
	`score`	DECIMAL(6, 5)	NULL	COMMENT '점수',
	`summary`	VARCHAR(500)	NULL	COMMENT '평가 요약',
	`artifactDocId`	VARCHAR(64)	NULL	COMMENT 'MongoDB 상세 결과 문서 ID',
	`createdAt`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각'
);

CREATE TABLE `common_code_group` (
	`code`	INT	NOT NULL	COMMENT '그룹코드ID',
	`name`	VARCHAR(50)	NOT NULL	COMMENT '그룹코드명',
	`description`	VARCHAR(255)	NULL	COMMENT '설명'
);

CREATE TABLE `project` (
	`id`	INT	NOT NULL	COMMENT '프로젝트id',
	`rootNote`	VARCHAR(2)	NOT NULL	DEFAULT C	COMMENT '근음 (전조가 있는 경우, 가장 첫 부분을 기준)',
	`mode`	VARCHAR(10)	NOT NULL	DEFAULT major	COMMENT '조성 (전조가 있는 경우, 가장 첫 부분을 기준)',
	`tempo`	DECIMAL(6, 2)	NOT NULL	DEFAULT 120.00	COMMENT '빠르기 (일정하지 않은 경우, 가장 첫 부분을 기준)',
	`timeSigNumerator`	TINYINT	NOT NULL	DEFAULT 4	COMMENT '박자표의 분자 (변박의 경우, 가장 첫 부분을 기준)',
	`timeSigDenominator`	TINYINT	NOT NULL	DEFAULT 4	COMMENT '박자표의 분모 (변박의 경우, 가장 첫 부분을 기준)',
	`totalBarCount`	SMALLINT	NOT NULL	DEFAULT 0	COMMENT '프로젝트의 총 마디 수',
	`totalPlayTime`	SMALLINT	NOT NULL	DEFAULT 0	COMMENT '프로젝트의 총 재생시간',
	`deletedAt`	DATETIME	NULL	COMMENT '삭제일시'
);

CREATE TABLE `ai_clipping_fix_log` (
	`id`	BIGINT	NOT NULL	COMMENT '클리핑 자동 보정 로그 ID',
	`jobId`	INT	NOT NULL	COMMENT 'AI 분석 작업 ID',
	`regionId`	INT	NULL	COMMENT '분석 구간 ID',
	`targetScopeCode`	TINYINT	NOT NULL	COMMENT '대상 범위 코드',
	`targetTrackId`	INT	NULL	COMMENT '대상 트랙 ID',
	`targetClipId`	INT	NULL	COMMENT '대상 클립 ID',
	`fixTypeCode`	TINYINT	NOT NULL	COMMENT '보정 유형 코드',
	`beforeValue`	DECIMAL(8, 3)	NULL	COMMENT '보정 전 값',
	`afterValue`	DECIMAL(8, 3)	NULL	COMMENT '보정 후 값',
	`summary`	VARCHAR(255)	NULL	COMMENT '보정 요약',
	`createdAt`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각'
);

CREATE TABLE `ai_llm_evaluation` (
	`id`	INT	NOT NULL	COMMENT 'LLM 평가 로그 ID',
	`modelName`	VARCHAR(100)	NOT NULL	COMMENT '평가 모델명',
	`verdictCode`	TINYINT	NOT NULL	COMMENT '평가 결과 코드',
	`score`	DECIMAL(6, 5)	NULL	COMMENT '평가 점수',
	`reasonJson`	JSON	NULL	COMMENT '평가 근거',
	`inputCredit`	DECIMAL(12, 4)	NULL	COMMENT '입력 사용 크레딧',
	`outputCredit`	DECIMAL(12, 4)	NULL	COMMENT '출력 사용 크레딧',
	`totalCredit`	DECIMAL(12, 4)	NULL	COMMENT '총 사용 크레딧',
	`createdAt`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '생성 시각',
	`jobId`	INT	NOT NULL	COMMENT 'AI 분석 작업 ID',
	`suggestionId`	INT	NOT NULL	COMMENT '수정안 ID'
);

CREATE TABLE `ai_region_clip` (
	`id`	INT	NOT NULL	COMMENT '분석 구간 관련 클립 ID',
	`regionId`	INT	NOT NULL	COMMENT '분석 구간 ID',
	`clipId`	INT	NOT NULL	COMMENT '클립 ID',
	`peakDb`	DECIMAL(6,3)	NULL	COMMENT '피크 dB',
	`rmsDb`	DECIMAL(6,3)	NULL	COMMENT 'RMS dB',
	`bandLowHz`	MEDIUMINT	NULL	COMMENT '핵심 대역 시작',
	`bandHighHz`	MEDIUMINT	NULL	COMMENT '핵심 대역 끝',
	`featureDocId`	VARCHAR(64)	NULL	COMMENT 'MongoDB 특징 문서 ID',
	`isPrimary`	BOOLEAN	NOT NULL	DEFAULT FALSE	COMMENT '대표 클립 여부'
);

CREATE TABLE `ai_analysis_region` (
	`id`	INT	NOT NULL	COMMENT '분석 구간 ID',
	`jobId`	INT	NOT NULL	COMMENT 'AI 분석 작업 ID',
	`regionTypeCode`	INT	NOT NULL	COMMENT '구간 유형 코드',
	`startMs`	MEDIUMINT	NOT NULL	COMMENT '시작 시각(ms)',
	`endMs`	MEDIUMINT	NOT NULL	COMMENT '종료 시각(ms)',
	`severityCode`	TINYINT	NOT NULL	COMMENT '심각도 코드',
	`analysisSummary`	VARCHAR(500)	NULL	COMMENT '분석 요약',
	`evidenceDocId`	VARCHAR(64)	NULL	COMMENT 'MongoDB 근거 문서 ID',
	`rangkingScore`	DECIMAL(8,6)	NULL	COMMENT '우선순위 점수',
	`requiresUserAction`	BOOLEAN	NOT NULL	COMMENT '사용자 승인 필요 여부'
);

CREATE TABLE `project_master_audio_version` (
	`id`	INT	NOT NULL	COMMENT '버전id',
	`project_id`	INT	NOT NULL	COMMENT '프로젝트id',
	`audio_metadata_id`	INT	NOT NULL	COMMENT '오디오메타데이터id',
	`name`	VARCHAR(30)	NOT NULL	COMMENT '이름',
	`memo`	VARCHAR(255)	NULL	COMMENT '메모'
);

CREATE TABLE `common_code_detail` (
	`code`	INT	NOT NULL	COMMENT '상세코드ID',
	`groupCode`	INTEGER	NOT NULL	COMMENT '그룹코드ID',
	`name`	VARCHAR(50)	NOT NULL	COMMENT '상세코드명',
	`description`	VARCHAR(255)	NULL	COMMENT '설명',
	`isActive`	BOOLEAN	NOT NULL	DEFAULT TRUE	COMMENT '사용 여부'
);

CREATE TABLE `position_group` (
	`code`	INT	NOT NULL	COMMENT '그룹코드',
	`name`	VARCHAR(50)	NOT NULL	COMMENT '코드명',
	`order`	TINYINT	NOT NULL	COMMENT '정렬 순서'
);

CREATE TABLE `ai_suggestion_group` (
	`id`	INT	NOT NULL	COMMENT '수정안 그룹 ID',
	`jobId`	INT	NOT NULL	COMMENT 'AI 분석 작업 ID',
	`regionId`	INT	NULL	COMMENT '분석 구간 ID',
	`startMs`	MEDIUMINT	NULL	COMMENT '그룹 시작 시각',
	`endMs`	MEDIUMINT	NULL	COMMENT '그룹 종료 시각',
	`title`	VARCHAR(100)	NOT NULL	COMMENT '그룹 제목',
	`summary`	TEXT	NULL	COMMENT '그룹 설명'
);

CREATE TABLE `ai_preview_render` (
	`id`	INT	NOT NULL	COMMENT '프리뷰 렌더 ID',
	`job_id`	INT	NOT NULL	COMMENT 'AI 분석 작업 ID',
	`analysis_region_id`	VARCHAR(128)	NOT NULL	COMMENT '분석 구간 ID',
	`suggestion_id`	VARCHAR(128)	NULL	COMMENT '수정안 ID',
	`status`	VARCHAR(32)	NOT NULL	COMMENT '프리뷰 생성 상태',
	`render_no`	INT	NOT NULL	DEFAULT 1	COMMENT '프리뷰 렌더 시도 번호',
	`object_key`	VARCHAR(1024)	NULL	COMMENT '프리뷰 오디오 파일 저장 키',
	`duration_ms`	INT	NULL	COMMENT '프리뷰 길이(ms)',
	`requested_by`	INT	NULL	COMMENT '프리뷰 요청 사용자 ID',
	`requested_at`	VARCHAR(64)	NOT NULL	COMMENT '프리뷰 요청 시각',
	`started_at`	VARCHAR(64)	NULL	COMMENT '렌더 시작 시각',
	`completed_at`	VARCHAR(64)	NULL	COMMENT '렌더 완료 시각',
	`expired_at`	VARCHAR(64)	NULL	COMMENT '프리뷰 만료 시각',
	`error_code`	VARCHAR(64)	NULL	COMMENT '오류 코드',
	`error_message`	VARCHAR(1000)	NULL	COMMENT '오류 메시지',
	`user_feedback_message`	VARCHAR(1000)	NULL	COMMENT '프리뷰 재요청 메시지',
	`preserve_clip_id`	INT	NULL	COMMENT '보존 대상 클립 ID',
	INDEX `idx_ai_preview_render_job_requested` (`job_id`, `requested_at`),
	INDEX `idx_ai_preview_render_region_requested` (`analysis_region_id`, `requested_at`)
);

CREATE TABLE `ai_main_clip_selection` (
	`id`	INT	NOT NULL	COMMENT '메인 클립 선택 ID',
	`regionId`	INT	NOT NULL	COMMENT '분석 구간 ID',
	`selectedClipId`	MEDIUMINT	NOT NULL	COMMENT '선택한 메인 클립 ID',
	`selectedBy`	INT	NOT NULL	COMMENT '선택 사용자 ID',
	`selectedAt`	DATETIME	NOT NULL	DEFAULT CURRENT_TIMESTAMP	COMMENT '선택 시각'
);

CREATE TABLE `ai_analysis_job` (
	`id`	INT	NOT NULL	COMMENT 'AI 분석 작업 ID',
	`project_id`	INT	NOT NULL	COMMENT '프로젝트 ID',
	`status`	VARCHAR(32)	NOT NULL	COMMENT '작업 상태',
	`phase`	VARCHAR(64)	NOT NULL	COMMENT '현재 workflow phase',
	`current_node`	VARCHAR(64)	NULL	COMMENT '현재 LangGraph 노드',
	`progress`	TINYINT	NOT NULL	DEFAULT 0	COMMENT '진행률 0~100',
	`langgraph_thread_id`	VARCHAR(128)	NOT NULL	COMMENT 'LangGraph 스레드 ID',
	`timeline_snapshot_id`	VARCHAR(128)	NULL	COMMENT '분석 기준 타임라인 스냅샷 ID',
	`requested_by`	INT	NULL	COMMENT '요청 사용자 ID',
	`started_at`	VARCHAR(64)	NULL	COMMENT '작업 시작 시각',
	`completed_at`	VARCHAR(64)	NULL	COMMENT '작업 완료 시각',
	`error_code`	VARCHAR(64)	NULL	COMMENT '오류 코드',
	`error_message`	VARCHAR(255)	NULL	COMMENT '오류 메시지',
	`state_artifact_id`	VARCHAR(128)	NULL	COMMENT 'Mongo durable state 아티팩트 ID',
	`state_json`	JSON	NOT NULL	COMMENT 'Worker resume용 최소 orchestration 상태'
);

CREATE TABLE `dm_room` (
	`id`	INT	NOT NULL	COMMENT '채팅방id'
);

CREATE TABLE `ai_genre_candidate` (
	`id`	INT	NOT NULL	COMMENT '장르 후보 ID',
	`trackId`	INT	NOT NULL	COMMENT '트랙 ID',
	`label`	VARCHAR(100)	NOT NULL	COMMENT '장르 라벨',
	`score`	DECIMAL(8, 6)	NOT NULL	COMMENT '유사도 점수',
	`rankNo`	TINYINT	NOT NULL	COMMENT '순위',
	`modelName`	VARCHAR(100)	NOT NULL	COMMENT '모델명'
);

ALTER TABLE `clip` ADD CONSTRAINT `PK_CLIP` PRIMARY KEY (
	`id`
);

ALTER TABLE `user` ADD CONSTRAINT `PK_USER` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_suggestion_action` ADD CONSTRAINT `PK_AI_SUGGESTION_ACTION` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_track_vocal_prediction` ADD CONSTRAINT `PK_AI_TRACK_VOCAL_PREDICTION` PRIMARY KEY (
	`id`
);

ALTER TABLE `user_position` ADD CONSTRAINT `PK_USER_POSITION` PRIMARY KEY (
	`userId`,
	`positionCode`
);

ALTER TABLE `track` ADD CONSTRAINT `PK_TRACK` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_offline_eval_item` ADD CONSTRAINT `PK_AI_OFFLINE_EVAL_ITEM` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_rag_retrieval` ADD CONSTRAINT `PK_AI_RAG_RETRIEVAL` PRIMARY KEY (
	`id`
);

ALTER TABLE `project_members` ADD CONSTRAINT `PK_PROJECT_MEMBERS` PRIMARY KEY (
	`projectId`,
	`userId`
);

ALTER TABLE `ai_offline_eval_run` ADD CONSTRAINT `PK_AI_OFFLINE_EVAL_RUN` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_applied_suggestion` ADD CONSTRAINT `PK_AI_APPLIED_SUGGESTION` PRIMARY KEY (
	`id`
);

ALTER TABLE `comment` ADD CONSTRAINT `PK_COMMENT` PRIMARY KEY (
	`id`
);

ALTER TABLE `audio_metadata` ADD CONSTRAINT `PK_AUDIO_METADATA` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_suggestion` ADD CONSTRAINT `PK_AI_SUGGESTION` PRIMARY KEY (
	`id`
);

ALTER TABLE `position_detail` ADD CONSTRAINT `PK_POSITION_DETAIL` PRIMARY KEY (
	`code`
);

ALTER TABLE `project_edit_event_log` ADD CONSTRAINT `PK_PROJECT_EDIT_EVENT_LOG` PRIMARY KEY (
	`logId`
);

ALTER TABLE `ai_rag_retrieval_doc` ADD CONSTRAINT `PK_AI_RAG_RETRIEVAL_DOC` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_rag_document` ADD CONSTRAINT `PK_AI_RAG_DOCUMENT` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_snapshot_ref` ADD CONSTRAINT `PK_AI_SNAPSHOT_REF` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_runtime_critic_result` ADD CONSTRAINT `PK_AI_RUNTIME_CRITIC_RESULT` PRIMARY KEY (
	`id`
);

ALTER TABLE `common_code_group` ADD CONSTRAINT `PK_COMMON_CODE_GROUP` PRIMARY KEY (
	`code`
);

ALTER TABLE `project` ADD CONSTRAINT `PK_PROJECT` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_clipping_fix_log` ADD CONSTRAINT `PK_AI_CLIPPING_FIX_LOG` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_llm_evaluation` ADD CONSTRAINT `PK_AI_LLM_EVALUATION` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_region_clip` ADD CONSTRAINT `PK_AI_REGION_CLIP` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_analysis_region` ADD CONSTRAINT `PK_AI_ANALYSIS_REGION` PRIMARY KEY (
	`id`
);

ALTER TABLE `project_master_audio_version` ADD CONSTRAINT `PK_PROJECT_MASTER_AUDIO_VERSION` PRIMARY KEY (
	`id`
);

ALTER TABLE `common_code_detail` ADD CONSTRAINT `PK_COMMON_CODE_DETAIL` PRIMARY KEY (
	`code`
);

ALTER TABLE `position_group` ADD CONSTRAINT `PK_POSITION_GROUP` PRIMARY KEY (
	`code`
);

ALTER TABLE `ai_suggestion_group` ADD CONSTRAINT `PK_AI_SUGGESTION_GROUP` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_preview_render` ADD CONSTRAINT `PK_AI_PREVIEW_RENDER` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_main_clip_selection` ADD CONSTRAINT `PK_AI_MAIN_CLIP_SELECTION` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_analysis_job` ADD CONSTRAINT `PK_AI_ANALYSIS_JOB` PRIMARY KEY (
	`id`
);

ALTER TABLE `dm_room` ADD CONSTRAINT `PK_DM_ROOM` PRIMARY KEY (
	`id`
);

ALTER TABLE `ai_genre_candidate` ADD CONSTRAINT `PK_AI_GENRE_CANDIDATE` PRIMARY KEY (
	`id`
);

ALTER TABLE `user_position` ADD CONSTRAINT `FK_user_TO_user_position_1` FOREIGN KEY (
	`userId`
)
REFERENCES `user` (
	`id`
);

ALTER TABLE `user_position` ADD CONSTRAINT `FK_position_detail_TO_user_position_1` FOREIGN KEY (
	`positionCode`
)
REFERENCES `position_detail` (
	`code`
);

ALTER TABLE `project_members` ADD CONSTRAINT `FK_project_TO_project_members_1` FOREIGN KEY (
	`projectId`
)
REFERENCES `project` (
	`id`
);

ALTER TABLE `project_members` ADD CONSTRAINT `FK_user_TO_project_members_1` FOREIGN KEY (
	`userId`
)
REFERENCES `user` (
	`id`
);

CREATE TABLE `ai_workflow_node_timing` (
      `id` BIGINT NOT NULL COMMENT '워크플로우 노드 타이밍 ID',
      `job_id` INT NOT NULL COMMENT 'AI 분석 작업 ID',
      `node_name` VARCHAR(100) NOT NULL COMMENT 'LangGraph 노드명',
      `phase` VARCHAR(100) NULL COMMENT '노드 실행 시점 phase',
      `sequence_no` SMALLINT NOT NULL COMMENT '해당 job 내 실행 순서',
      `status_code` TINYINT NOT NULL COMMENT '노드 실행 상태 코드',
      `wait_category_code` TINYINT NOT NULL COMMENT '대기/작업 유형 코드',
      `started_at` DATETIME NOT NULL COMMENT '노드 시작 시각',
      `completed_at` DATETIME NULL COMMENT '노드 종료 시각',
      `duration_ms` INT NULL COMMENT '노드 소요 시간(ms)',
      `queue_wait_ms` INT NULL COMMENT '큐 대기 시간(ms)',
      `error_code` CHAR(5) NULL COMMENT '오류 코드',
      `error_message` VARCHAR(1000) NULL COMMENT '오류 메시지',
      `artifact_doc_id` VARCHAR(64) NULL COMMENT 'MongoDB 상세 타이밍/메타 문서 ID',
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성 시각'
  );

  ALTER TABLE `ai_workflow_node_timing`
  ADD CONSTRAINT `PK_AI_WORKFLOW_NODE_TIMING` PRIMARY KEY (`id`);

CREATE TABLE `ai_analysis_job` (
      `id` INT NOT NULL COMMENT 'AI workflow durable job ID',
      `projectId` INT NOT NULL COMMENT 'AI workflow target project ID',
      `status` VARCHAR(32) NOT NULL COMMENT 'Durable workflow job status',
      `phase` VARCHAR(64) NOT NULL COMMENT 'Current workflow phase',
      `currentNode` VARCHAR(64) NULL COMMENT 'Last persisted workflow node',
      `progress` TINYINT NOT NULL DEFAULT 0 COMMENT 'Workflow progress percent',
      `langgraphThreadId` VARCHAR(128) NOT NULL COMMENT 'LangGraph thread identifier',
      `timelineSnapshotId` VARCHAR(128) NULL COMMENT 'Timeline snapshot reference',
      `requestedBy` INT NULL COMMENT 'User who requested the workflow run',
      `startedAt` VARCHAR(64) NULL COMMENT 'Workflow start time',
      `completedAt` VARCHAR(64) NULL COMMENT 'Workflow completion time',
      `errorCode` VARCHAR(64) NULL COMMENT 'Failure code for terminal errors',
      `errorMessage` VARCHAR(255) NULL COMMENT 'Failure message for terminal errors',
      `stateJson` JSON NOT NULL COMMENT 'Worker resume용 최소 orchestration 상태'
  );

  ALTER TABLE `ai_analysis_job`
  ADD CONSTRAINT `PK_AI_ANALYSIS_JOB` PRIMARY KEY (`id`);

ALTER TABLE `ai_preview_render`
  ADD COLUMN `analysisRegionId` VARCHAR(128) NOT NULL,
  ADD COLUMN `userFeedbackMessage` VARCHAR(1000) NULL,
  ADD COLUMN `preserveClipId` INT NULL;

ALTER TABLE `ai_preview_render`
  ADD INDEX `IDX_AI_PREVIEW_RENDER_REGION_REQUESTED` (`analysisRegionId`, `requestedAt`),
  ADD INDEX `IDX_AI_PREVIEW_RENDER_JOB_REQUESTED` (`jobId`, `requestedAt`);

CREATE TABLE `master_limiter` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `project_id` INT NOT NULL,
  `is_enabled` TINYINT(1) NOT NULL DEFAULT 0,
  `threshold_db` DOUBLE NOT NULL DEFAULT -6.0,
  `ceiling_dbfs` DOUBLE NOT NULL DEFAULT -1.0,
  `attack_ms` DOUBLE NOT NULL DEFAULT 3.0,
  `release_ms` DOUBLE NOT NULL DEFAULT 80.0,
  `input_gain_db` DOUBLE NOT NULL DEFAULT 0.0,
  `makeup_gain_db` DOUBLE NOT NULL DEFAULT 0.0,
  `job_id` INT NULL,
  `suggestion_action_id` INT NULL,
  `applied_suggestion_id` INT NULL,
  `source_type_code` INT NOT NULL DEFAULT 1,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` INT NULL,
  `updated_by` INT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `UK_MASTER_LIMITER_PROJECT` (`project_id`)
);

ALTER TABLE `master_limiter`
  ADD CONSTRAINT `FK_MASTER_LIMITER_PROJECT`
  FOREIGN KEY (`project_id`) REFERENCES `project` (`id`);
