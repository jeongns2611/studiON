// package com.salmon.studion.domain.clip.service;

// import com.fasterxml.jackson.core.JsonProcessingException;
// import com.fasterxml.jackson.databind.ObjectMapper;
// import com.salmon.studion.domain.clip.dto.ClipState;
// import com.salmon.studion.domain.audio.entity.AudioMetadata;
// import com.salmon.studion.domain.audio.repository.AudioMetadataRepository;
// import com.salmon.studion.domain.audio.service.AudioService;
// import com.salmon.studion.domain.clip.dto.request.ClipCopyRequest;
// import com.salmon.studion.domain.clip.dto.request.ClipCreateRequest;
// import com.salmon.studion.domain.clip.dto.request.ClipCutRequest;
// import com.salmon.studion.domain.clip.dto.request.ClipDeleteRequest;
// import com.salmon.studion.domain.clip.dto.request.ClipPasteRequest;
// import com.salmon.studion.domain.clip.dto.request.ClipLockRequest;
// import com.salmon.studion.domain.clip.dto.request.ClipMoveRequest;
// import com.salmon.studion.domain.clip.dto.request.ClipResizeRequest;
// import com.salmon.studion.domain.clip.dto.request.ClipDuplicateRequest;
// import com.salmon.studion.domain.clip.dto.request.ClipSplitRequest;
// import com.salmon.studion.domain.clip.dto.response.ClipCopyResponse;
// import com.salmon.studion.domain.clip.dto.response.ClipCreateResponse;
// import com.salmon.studion.domain.clip.dto.response.ClipCutResponse;
// import com.salmon.studion.domain.clip.dto.response.ClipDeleteResponse;
// import com.salmon.studion.domain.clip.dto.response.ClipPasteResponse;
// import com.salmon.studion.domain.clip.dto.response.ClipLockResponse;
// import com.salmon.studion.domain.clip.dto.response.ClipMoveResponse;
// import com.salmon.studion.domain.clip.dto.response.ClipResizeResponse;
// import com.salmon.studion.domain.clip.dto.response.ClipDuplicateResponse;
// import com.salmon.studion.domain.clip.dto.response.ClipSplitResponse;
// import com.salmon.studion.domain.clip.entity.Clip;
// import com.salmon.studion.domain.clip.repository.ClipEventRepository;
// import com.salmon.studion.domain.clip.repository.ClipRepository;
// import com.salmon.studion.domain.project.entity.Project;
// import com.salmon.studion.domain.project.service.ProjectService;
// import com.salmon.studion.domain.track.entity.Track;
// import com.salmon.studion.domain.track.repository.TrackRepository;
// import com.salmon.studion.global.common.enums.MimeType;
// import com.salmon.studion.global.common.response.ErrorCode;
// import com.salmon.studion.global.exception.BusinessException;
// import org.junit.jupiter.api.BeforeEach;
// import org.junit.jupiter.api.DisplayName;
// import org.junit.jupiter.api.Nested;
// import org.junit.jupiter.api.Test;
// import org.junit.jupiter.api.extension.ExtendWith;
// import org.mockito.InjectMocks;
// import org.mockito.Mock;
// import org.mockito.Spy;
// import org.mockito.junit.jupiter.MockitoExtension;
// import org.springframework.data.redis.core.HashOperations;
// import org.springframework.data.redis.core.RedisTemplate;
// import org.springframework.data.redis.core.SetOperations;
// import org.springframework.data.redis.core.ValueOperations;

// import java.util.ArrayList;
// import java.util.HashMap;
// import java.util.List;
// import java.util.Map;
// import java.util.Optional;

// import static org.assertj.core.api.Assertions.assertThat;
// import static org.assertj.core.api.Assertions.assertThatThrownBy;
// import static org.mockito.ArgumentMatchers.*;
// import static org.mockito.Mockito.*;

// @ExtendWith(MockitoExtension.class)
// class ClipServiceTest {

//     @Mock private ProjectService projectService;
//     @Mock private AudioService audioService;
//     @Mock private ClipRepository clipRepository;
//     @Mock private ClipEventRepository clipEventRepository;
//     @Mock private TrackRepository trackRepository;
//     @Mock private AudioMetadataRepository audioMetadataRepository;
//     @Mock private RedisTemplate<String, String> redisTemplate;
//     @Spy  private ObjectMapper objectMapper = new ObjectMapper();

//     @InjectMocks private ClipService clipService;

//     @Mock private ValueOperations<String, String> valueOperations;
//     @Mock private HashOperations<String, Object, Object> hashOperations;
//     @Mock private SetOperations<String, String> setOperations;

//     private static final Integer PROJECT_ID = 1;
//     private static final Integer CLIP_ID = 3;
//     private static final Integer USER_ID = 1;
//     private static final Integer OTHER_USER_ID = 2;
//     private static final String LOCK_KEY = "project:1:clip:3:lock";
//     private static final String EVENT_SEQ_KEY = "project:1:clip:event:seq";

//     @BeforeEach
//     void setUp() {
//         lenient().when(redisTemplate.opsForValue()).thenReturn(valueOperations);
//         lenient().when(redisTemplate.opsForHash()).thenReturn(hashOperations);
//         lenient().when(redisTemplate.opsForSet()).thenReturn(setOperations);
//         lenient().when(projectService.getProjectOrThrow(PROJECT_ID)).thenReturn(mock(Project.class));
//         lenient().when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(1L);
//     }

//     private ClipLockRequest lockRequest(Boolean isLocked) {
//         ClipLockRequest req = new ClipLockRequest();
//         req.setProjectId(PROJECT_ID);
//         req.setClipId(CLIP_ID);
//         req.setIsLocked(isLocked);
//         return req;
//     }

//     @Nested
//     @DisplayName("전역 시퀀스")
//     class GlobalSequenceTest {

//         private static final String GLOBAL_CLIP_ID_SEQ_KEY = "global:clip:id_seq";
//         private static final String CLIP_STATE_KEY = "project:1:clips";
//         private static final String CLIP_STATE_KEY2 = "project:2:clips";
//         private static final Integer TRACK_ID = 1;
//         private static final Integer AUDIO_METADATA_ID = 42;
//         private static final Integer DURATION_MS = 8000;

//         @Test
//         @DisplayName("서로 다른 프로젝트의 클립 생성은 동일한 전역 시퀀스 키를 사용한다")
//         void differentProjectsUseSameGlobalKey() {
//             Integer projectId2 = 2;

//             Project mockProject = mock(Project.class);
//             lenient().when(mockProject.getTempo()).thenReturn(120.0);
//             lenient().when(mockProject.getTimeSigNumerator()).thenReturn(4);
//             lenient().when(projectService.getProjectOrThrow(PROJECT_ID)).thenReturn(mockProject);
//             lenient().when(projectService.getProjectOrThrow(projectId2)).thenReturn(mockProject);

//             AudioMetadata mockAudio = mock(AudioMetadata.class);
//             lenient().when(mockAudio.getId()).thenReturn(AUDIO_METADATA_ID);
//             lenient().when(mockAudio.getDurationMs()).thenReturn(DURATION_MS);
//             lenient().when(audioService.createAudioMetadata(any())).thenReturn(mockAudio);

//             lenient().when(valueOperations.increment(GLOBAL_CLIP_ID_SEQ_KEY)).thenReturn(1L).thenReturn(2L);
//             lenient().when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(1L);
//             lenient().when(valueOperations.increment("project:2:clip:event:seq")).thenReturn(1L);
//             lenient().doAnswer(inv -> null).when(hashOperations).put(any(), any(), any());
//             lenient().when(trackRepository.findByIdAndProject_Id(TRACK_ID, PROJECT_ID)).thenReturn(Optional.of(mock(Track.class)));
//             lenient().when(trackRepository.findByIdAndProject_Id(TRACK_ID, projectId2)).thenReturn(Optional.of(mock(Track.class)));

//             ClipCreateRequest req1 = createRequest(PROJECT_ID, TRACK_ID);
//             ClipCreateRequest req2 = createRequest(projectId2, TRACK_ID);

//             clipService.createClip(req1, USER_ID);
//             clipService.createClip(req2, USER_ID);

//             verify(valueOperations, times(2)).increment(GLOBAL_CLIP_ID_SEQ_KEY);
//             verify(valueOperations, never()).increment("project:1:clip:id_seq");
//             verify(valueOperations, never()).increment("project:2:clip:id_seq");
//         }

//         private ClipCreateRequest createRequest(Integer projectId, Integer trackId) {
//             ClipCreateRequest req = new ClipCreateRequest();
//             req.setProjectId(projectId);
//             req.setTrackId(trackId);
//             req.setStartBar(0.0);
//             req.setColor("#FF0000");
//             req.setObjectKey("projects/1/audios/test.mp3");
//             req.setOriginalName("test.mp3");
//             req.setStoredName("test.mp3");
//             req.setMimeType(com.salmon.studion.global.common.enums.MimeType.MPEG);
//             req.setSizeBytes(100000);
//             req.setDurationMs(DURATION_MS);
//             return req;
//         }
//     }

//     @Nested
//     @DisplayName("lockClip - 잠금")
//     class LockTest {

//         @Test
//         @DisplayName("잠금 성공 시 clipId, isLocked=true, userId를 반환한다")
//         void lockSuccess() {
//             when(valueOperations.setIfAbsent(eq(LOCK_KEY), eq(String.valueOf(USER_ID)))).thenReturn(true);

//             ClipLockResponse response = clipService.lockClip(lockRequest(true), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//             assertThat(response.getIsLocked()).isTrue();
//             assertThat(response.getUserId()).isEqualTo(USER_ID);
//         }

//         @Test
//         @DisplayName("다른 사용자가 잠근 경우 CLIP_LOCKED 예외를 던진다")
//         void lockFailWhenAlreadyLocked() {
//             when(valueOperations.setIfAbsent(eq(LOCK_KEY), eq(String.valueOf(USER_ID)))).thenReturn(false);

//             assertThatThrownBy(() -> clipService.lockClip(lockRequest(true), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));
//         }
//     }

//     @Nested
//     @DisplayName("lockClip - 해제")
//     class UnlockTest {

//         @Test
//         @DisplayName("잠금자 본인이 해제 요청 시 성공하고 isLocked=false를 반환한다")
//         void unlockSuccess() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(USER_ID));
//             when(redisTemplate.delete(LOCK_KEY)).thenReturn(true);

//             ClipLockResponse response = clipService.lockClip(lockRequest(false), USER_ID);

//             assertThat(response.getIsLocked()).isFalse();
//             assertThat(response.getUserId()).isEqualTo(USER_ID);
//             verify(redisTemplate).delete(LOCK_KEY);
//         }

//         @Test
//         @DisplayName("다른 사용자가 해제 요청 시 CLIP_LOCKED 예외를 던진다")
//         void unlockFailWhenNotLocker() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(OTHER_USER_ID));

//             assertThatThrownBy(() -> clipService.lockClip(lockRequest(false), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));

//             verify(redisTemplate, never()).delete(LOCK_KEY);
//         }

//         @Test
//         @DisplayName("잠금이 없는 클립에 해제 요청 시 정상 처리된다")
//         void unlockWhenNotLocked() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(null);
//             lenient().when(redisTemplate.delete(LOCK_KEY)).thenReturn(false);

//             ClipLockResponse response = clipService.lockClip(lockRequest(false), USER_ID);

//             assertThat(response.getIsLocked()).isFalse();
//         }
//     }

//     @Nested
//     @DisplayName("lockClip - validate")
//     class LockValidateTest {

//         @Test
//         @DisplayName("projectId가 null이면 INVALID_REQUEST 예외를 던진다")
//         void validateProjectIdNull() {
//             ClipLockRequest req = new ClipLockRequest();
//             req.setClipId(CLIP_ID);
//             req.setIsLocked(true);

//             assertThatThrownBy(() -> clipService.lockClip(req, USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.INVALID_REQUEST));
//         }

//         @Test
//         @DisplayName("clipId가 null이면 INVALID_REQUEST 예외를 던진다")
//         void validateClipIdNull() {
//             ClipLockRequest req = new ClipLockRequest();
//             req.setProjectId(PROJECT_ID);
//             req.setIsLocked(true);

//             assertThatThrownBy(() -> clipService.lockClip(req, USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.INVALID_REQUEST));
//         }

//         @Test
//         @DisplayName("isLocked가 null이면 INVALID_REQUEST 예외를 던진다")
//         void validateIsLockedNull() {
//             ClipLockRequest req = new ClipLockRequest();
//             req.setProjectId(PROJECT_ID);
//             req.setClipId(CLIP_ID);

//             assertThatThrownBy(() -> clipService.lockClip(req, USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.INVALID_REQUEST));
//         }
//     }

//     @Nested
//     @DisplayName("moveClip")
//     class MoveClipTest {

//         private static final Integer ORIGINAL_TRACK_ID = 1;
//         private static final Integer TARGET_TRACK_ID = 2;
//         private static final Double ORIGINAL_START = 1.0;
//         private static final Double ORIGINAL_DURATION = 4.0;
//         private static final Double TARGET_START = 4.5;
//         private static final String CLIP_STATE_KEY = "project:1:clips";

//         private Map<String, String> store;

//         @BeforeEach
//         void setUp() {
//             store = new HashMap<>();

//             lenient().when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(USER_ID));
//             lenient().when(trackRepository.findByIdAndProject_Id(TARGET_TRACK_ID, PROJECT_ID)).thenReturn(Optional.of(mock(Track.class)));

//             lenient().doAnswer(inv -> store.get(inv.getArgument(1).toString()))
//                     .when(hashOperations).get(eq(CLIP_STATE_KEY), any());
//             lenient().doAnswer(inv -> {
//                 store.put(inv.getArgument(1).toString(), inv.getArgument(2).toString());
//                 return null;
//             }).when(hashOperations).put(eq(CLIP_STATE_KEY), any(), any());
//         }

//         private ClipMoveRequest moveRequest(Integer clipId, Integer targetTrackId, Double targetStartBar) {
//             ClipMoveRequest req = new ClipMoveRequest();
//             req.setProjectId(PROJECT_ID);
//             req.setClipId(clipId);
//             req.setTargetTrackId(targetTrackId);
//             req.setTargetStartBar(targetStartBar);
//             return req;
//         }

//         private String clipStateJson(Integer trackId, Double start, Double duration) throws JsonProcessingException {
//             return objectMapper.writeValueAsString(ClipState.builder()
//                     .clipId(CLIP_ID).trackId(trackId).start(start).duration(duration)
//                     .build());
//         }

//         @Test
//         @DisplayName("Redis에 클립 상태가 있을 때 이동 성공 시 before/after 위치를 반환하고 Redis 상태를 업데이트한다")
//         void moveSuccess_fromRedis() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson(ORIGINAL_TRACK_ID, ORIGINAL_START, ORIGINAL_DURATION));

//             ClipMoveResponse response = clipService.moveClip(
//                     moveRequest(CLIP_ID, TARGET_TRACK_ID, TARGET_START), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//             assertThat(response.getBefore().getTrackId()).isEqualTo(ORIGINAL_TRACK_ID);
//             assertThat(response.getBefore().getStartBar()).isEqualTo(ORIGINAL_START);
//             assertThat(response.getAfter().getTrackId()).isEqualTo(TARGET_TRACK_ID);
//             assertThat(response.getAfter().getStartBar()).isEqualTo(TARGET_START);

//             ClipState updatedState = objectMapper.readValue(store.get(String.valueOf(CLIP_ID)), ClipState.class);
//             assertThat(updatedState.getTrackId()).isEqualTo(TARGET_TRACK_ID);
//             assertThat(updatedState.getStart()).isEqualTo(TARGET_START);
//             assertThat(updatedState.getDuration()).isEqualTo(ORIGINAL_DURATION);
//         }

//         @Test
//         @DisplayName("Redis에 클립 상태가 없을 때 MySQL에서 로드 후 이동 성공한다")
//         void moveSuccess_lazyInit() throws JsonProcessingException {
//             Track mockTrack = mock(Track.class);
//             Clip mockClip = mock(Clip.class);
//             AudioMetadata mockAudio = mock(AudioMetadata.class);
//             when(mockTrack.getId()).thenReturn(ORIGINAL_TRACK_ID);
//             when(mockClip.getId()).thenReturn(CLIP_ID);
//             when(mockClip.getTrack()).thenReturn(mockTrack);
//             when(mockClip.getStart()).thenReturn(ORIGINAL_START);
//             when(mockClip.getDuration()).thenReturn(ORIGINAL_DURATION);
//             when(mockAudio.getId()).thenReturn(42);
//             when(mockClip.getAudioMetadata()).thenReturn(mockAudio);
//             when(mockClip.getColor()).thenReturn("#FFFFFF");
//             when(mockClip.getAudioStartMs()).thenReturn(0);
//             when(mockClip.getAudioDurationMs()).thenReturn(4000);
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.of(mockClip));

//             ClipMoveResponse response = clipService.moveClip(
//                     moveRequest(CLIP_ID, TARGET_TRACK_ID, TARGET_START), USER_ID);

//             assertThat(response.getBefore().getTrackId()).isEqualTo(ORIGINAL_TRACK_ID);
//             assertThat(response.getBefore().getStartBar()).isEqualTo(ORIGINAL_START);
//             assertThat(response.getAfter().getTrackId()).isEqualTo(TARGET_TRACK_ID);
//             assertThat(response.getAfter().getStartBar()).isEqualTo(TARGET_START);

//             ClipState updatedState = objectMapper.readValue(store.get(String.valueOf(CLIP_ID)), ClipState.class);
//             assertThat(updatedState.getTrackId()).isEqualTo(TARGET_TRACK_ID);
//         }

//         @Test
//         @DisplayName("클립이 잠겨있지 않으면 CLIP_LOCKED 예외를 던진다")
//         void moveFailWhenNotLocked() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(null);

//             assertThatThrownBy(() -> clipService.moveClip(
//                     moveRequest(CLIP_ID, TARGET_TRACK_ID, TARGET_START), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));
//         }

//         @Test
//         @DisplayName("다른 사용자가 잠근 클립에 이동 요청 시 CLIP_LOCKED 예외를 던진다")
//         void moveFailWhenLockedByOtherUser() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(OTHER_USER_ID));

//             assertThatThrownBy(() -> clipService.moveClip(
//                     moveRequest(CLIP_ID, TARGET_TRACK_ID, TARGET_START), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));
//         }

//         @Test
//         @DisplayName("Redis에 없고 MySQL에도 없는 클립 이동 시 CLIP_NOT_FOUND 예외를 던진다")
//         void moveFailWhenClipNotFound() {
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.empty());

//             assertThatThrownBy(() -> clipService.moveClip(
//                     moveRequest(CLIP_ID, TARGET_TRACK_ID, TARGET_START), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_NOT_FOUND));
//         }

//         @Nested
//         @DisplayName("validate")
//         class ValidateTest {

//             @Test
//             @DisplayName("projectId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void projectIdNull() {
//                 ClipMoveRequest req = new ClipMoveRequest();
//                 req.setClipId(CLIP_ID);
//                 req.setTargetTrackId(TARGET_TRACK_ID);
//                 req.setTargetStartBar(TARGET_START);

//                 assertThatThrownBy(() -> clipService.moveClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("clipId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void clipIdNull() {
//                 ClipMoveRequest req = new ClipMoveRequest();
//                 req.setProjectId(PROJECT_ID);
//                 req.setTargetTrackId(TARGET_TRACK_ID);
//                 req.setTargetStartBar(TARGET_START);

//                 assertThatThrownBy(() -> clipService.moveClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("targetTrackId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void targetTrackIdNull() {
//                 ClipMoveRequest req = new ClipMoveRequest();
//                 req.setProjectId(PROJECT_ID);
//                 req.setClipId(CLIP_ID);
//                 req.setTargetStartBar(TARGET_START);

//                 assertThatThrownBy(() -> clipService.moveClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("targetStartBar가 null이면 INVALID_REQUEST 예외를 던진다")
//             void targetStartBarNull() {
//                 ClipMoveRequest req = new ClipMoveRequest();
//                 req.setProjectId(PROJECT_ID);
//                 req.setClipId(CLIP_ID);
//                 req.setTargetTrackId(TARGET_TRACK_ID);

//                 assertThatThrownBy(() -> clipService.moveClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }
//         }
//     }

//     @Nested
//     @DisplayName("resizeClip")
//     class ResizeClipTest {

//         private static final Double ORIGINAL_START_BAR = 1.0;
//         private static final Double ORIGINAL_LENGTH = 4.0;
//         private static final Double NEW_START_BAR = 2.0;
//         private static final Double NEW_LENGTH = 6.0;
//         private static final String CLIP_STATE_KEY = "project:1:clips";

//         private Map<String, String> store;

//         @BeforeEach
//         void setUp() {
//             store = new HashMap<>();

//             lenient().when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(USER_ID));

//             lenient().doAnswer(inv -> store.get(inv.getArgument(1).toString()))
//                     .when(hashOperations).get(eq(CLIP_STATE_KEY), any());
//             lenient().doAnswer(inv -> {
//                 store.put(inv.getArgument(1).toString(), inv.getArgument(2).toString());
//                 return null;
//             }).when(hashOperations).put(eq(CLIP_STATE_KEY), any(), any());
//             lenient().doAnswer(inv -> new ArrayList<>(store.values()))
//                     .when(hashOperations).values(eq(CLIP_STATE_KEY));
//         }

//         private ClipResizeRequest resizeRequest(Integer clipId, Double startBar, Double length) {
//             ClipResizeRequest req = new ClipResizeRequest();
//             req.setProjectId(PROJECT_ID);
//             req.setClipId(clipId);
//             req.setStartBar(startBar);
//             req.setLength(length);
//             return req;
//         }

//         private String clipStateJson(Double start, Double duration) throws JsonProcessingException {
//             return objectMapper.writeValueAsString(ClipState.builder()
//                     .clipId(CLIP_ID).trackId(1).start(start).duration(duration)
//                     .audioStartMs(0).audioDurationMs(4000)
//                     .build());
//         }

//         @Test
//         @DisplayName("Redis에 클립 상태가 있을 때 리사이즈 성공 시 before/after를 반환하고 Redis 상태를 업데이트한다")
//         void resizeSuccess_fromRedis() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson(ORIGINAL_START_BAR, ORIGINAL_LENGTH));

//             ClipResizeResponse response = clipService.resizeClip(
//                     resizeRequest(CLIP_ID, NEW_START_BAR, NEW_LENGTH), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//             assertThat(response.getBefore().getStartBar()).isEqualTo(ORIGINAL_START_BAR);
//             assertThat(response.getBefore().getLength()).isEqualTo(ORIGINAL_LENGTH);
//             assertThat(response.getAfter().getStartBar()).isEqualTo(NEW_START_BAR);
//             assertThat(response.getAfter().getLength()).isEqualTo(NEW_LENGTH);

//             ClipState updatedState = objectMapper.readValue(store.get(String.valueOf(CLIP_ID)), ClipState.class);
//             assertThat(updatedState.getStart()).isEqualTo(NEW_START_BAR);
//             assertThat(updatedState.getDuration()).isEqualTo(NEW_LENGTH);
//         }

//         @Test
//         @DisplayName("Redis에 클립 상태가 없을 때 MySQL에서 로드 후 리사이즈 성공한다")
//         void resizeSuccess_lazyInit() throws JsonProcessingException {
//             Track mockTrack = mock(Track.class);
//             Clip mockClip = mock(Clip.class);
//             AudioMetadata mockAudio = mock(AudioMetadata.class);
//             when(mockTrack.getId()).thenReturn(1);
//             when(mockClip.getId()).thenReturn(CLIP_ID);
//             when(mockClip.getTrack()).thenReturn(mockTrack);
//             when(mockClip.getStart()).thenReturn(ORIGINAL_START_BAR);
//             when(mockClip.getDuration()).thenReturn(ORIGINAL_LENGTH);
//             when(mockAudio.getId()).thenReturn(42);
//             when(mockClip.getAudioMetadata()).thenReturn(mockAudio);
//             when(mockClip.getColor()).thenReturn("#FFFFFF");
//             when(mockClip.getAudioStartMs()).thenReturn(0);
//             when(mockClip.getAudioDurationMs()).thenReturn(4000);
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.of(mockClip));

//             ClipResizeResponse response = clipService.resizeClip(
//                     resizeRequest(CLIP_ID, NEW_START_BAR, NEW_LENGTH), USER_ID);

//             assertThat(response.getBefore().getStartBar()).isEqualTo(ORIGINAL_START_BAR);
//             assertThat(response.getBefore().getLength()).isEqualTo(ORIGINAL_LENGTH);
//             assertThat(response.getAfter().getStartBar()).isEqualTo(NEW_START_BAR);
//             assertThat(response.getAfter().getLength()).isEqualTo(NEW_LENGTH);

//             ClipState updatedState = objectMapper.readValue(store.get(String.valueOf(CLIP_ID)), ClipState.class);
//             assertThat(updatedState.getDuration()).isEqualTo(NEW_LENGTH);
//         }

//         @Test
//         @DisplayName("클립이 잠겨있지 않으면 CLIP_LOCKED 예외를 던진다")
//         void resizeFailWhenNotLocked() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(null);

//             assertThatThrownBy(() -> clipService.resizeClip(
//                     resizeRequest(CLIP_ID, NEW_START_BAR, NEW_LENGTH), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));
//         }

//         @Test
//         @DisplayName("다른 사용자가 잠근 클립에 리사이즈 요청 시 CLIP_LOCKED 예외를 던진다")
//         void resizeFailWhenLockedByOtherUser() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(OTHER_USER_ID));

//             assertThatThrownBy(() -> clipService.resizeClip(
//                     resizeRequest(CLIP_ID, NEW_START_BAR, NEW_LENGTH), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));
//         }

//         @Test
//         @DisplayName("Redis에 없고 MySQL에도 없는 클립 리사이즈 시 CLIP_NOT_FOUND 예외를 던진다")
//         void resizeFailWhenClipNotFound() {
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.empty());

//             assertThatThrownBy(() -> clipService.resizeClip(
//                     resizeRequest(CLIP_ID, NEW_START_BAR, NEW_LENGTH), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_NOT_FOUND));
//         }

//         @Test
//         @DisplayName("같은 트랙 내 다른 클립과 겹치면 CLIP_OVERLAP 예외를 던진다")
//         void resizeFailWhenOverlap() throws JsonProcessingException {
//             // 대상 클립: trackId=1, start=1.0, duration=4.0
//             store.put(String.valueOf(CLIP_ID), clipStateJson(ORIGINAL_START_BAR, ORIGINAL_LENGTH));
//             // 같은 트랙의 다른 클립: trackId=1, start=7.0, duration=3.0 → [7, 10)
//             store.put("99", objectMapper.writeValueAsString(
//                     ClipState.builder().clipId(99).trackId(1).start(7.0).duration(3.0).build()));

//             // 리사이즈 후 범위: [2.0, 2.0+8.0) = [2, 10) → 다른 클립 [7, 10)과 겹침
//             assertThatThrownBy(() -> clipService.resizeClip(
//                     resizeRequest(CLIP_ID, 2.0, 8.0), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_OVERLAP));
//         }

//         @Test
//         @DisplayName("다른 트랙의 클립과 범위가 겹쳐도 예외를 던지지 않는다")
//         void resizeSuccessWhenOverlapOnDifferentTrack() throws JsonProcessingException {
//             // 대상 클립: trackId=1, start=1.0, duration=4.0
//             store.put(String.valueOf(CLIP_ID), clipStateJson(ORIGINAL_START_BAR, ORIGINAL_LENGTH));
//             // 다른 트랙의 클립: trackId=2, start=2.0, duration=3.0
//             store.put("99", objectMapper.writeValueAsString(
//                     ClipState.builder().clipId(99).trackId(2).start(2.0).duration(3.0).build()));

//             // 리사이즈 후 범위: [2.0, 2.0+5.0) — 다른 트랙이므로 겹침 체크 제외
//             ClipResizeResponse response = clipService.resizeClip(
//                     resizeRequest(CLIP_ID, 2.0, 5.0), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//         }

//         @Test
//         @DisplayName("같은 트랙 내 다른 클립과 겹치지 않으면 리사이즈 성공한다")
//         void resizeSuccessWhenNoOverlap() throws JsonProcessingException {
//             // 대상 클립: trackId=1, start=1.0, duration=4.0 → [1, 5)
//             store.put(String.valueOf(CLIP_ID), clipStateJson(ORIGINAL_START_BAR, ORIGINAL_LENGTH));
//             // 같은 트랙의 다른 클립: trackId=1, start=8.0, duration=2.0 → [8, 10)
//             store.put("99", objectMapper.writeValueAsString(
//                     ClipState.builder().clipId(99).trackId(1).start(8.0).duration(2.0).build()));

//             // 리사이즈 후 범위: [1.0, 1.0+5.0) = [1, 6) → [8, 10)과 겹치지 않음
//             ClipResizeResponse response = clipService.resizeClip(
//                     resizeRequest(CLIP_ID, 1.0, 5.0), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//         }

//         @Nested
//         @DisplayName("validate")
//         class ValidateTest {

//             @Test
//             @DisplayName("projectId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void projectIdNull() {
//                 ClipResizeRequest req = new ClipResizeRequest();
//                 req.setClipId(CLIP_ID);
//                 req.setStartBar(NEW_START_BAR);
//                 req.setLength(NEW_LENGTH);

//                 assertThatThrownBy(() -> clipService.resizeClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("clipId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void clipIdNull() {
//                 ClipResizeRequest req = new ClipResizeRequest();
//                 req.setProjectId(PROJECT_ID);
//                 req.setStartBar(NEW_START_BAR);
//                 req.setLength(NEW_LENGTH);

//                 assertThatThrownBy(() -> clipService.resizeClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("startBar가 null이면 INVALID_REQUEST 예외를 던진다")
//             void startBarNull() {
//                 ClipResizeRequest req = new ClipResizeRequest();
//                 req.setProjectId(PROJECT_ID);
//                 req.setClipId(CLIP_ID);
//                 req.setLength(NEW_LENGTH);

//                 assertThatThrownBy(() -> clipService.resizeClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("length가 null이면 INVALID_REQUEST 예외를 던진다")
//             void lengthNull() {
//                 ClipResizeRequest req = new ClipResizeRequest();
//                 req.setProjectId(PROJECT_ID);
//                 req.setClipId(CLIP_ID);
//                 req.setStartBar(NEW_START_BAR);

//                 assertThatThrownBy(() -> clipService.resizeClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }
//         }
//     }

//     @Nested
//     @DisplayName("deleteClip")
//     class DeleteClipTest {

//         private static final String CLIP_STATE_KEY = "project:1:clips";

//         private Map<String, String> store;

//         @BeforeEach
//         void setUp() {
//             store = new HashMap<>();

//             lenient().when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(USER_ID));

//             lenient().doAnswer(inv -> store.get(inv.getArgument(1).toString()))
//                     .when(hashOperations).get(eq(CLIP_STATE_KEY), any());
//             lenient().doAnswer(inv -> {
//                 store.remove(inv.getArgument(1).toString());
//                 return 1L;
//             }).when(hashOperations).delete(eq(CLIP_STATE_KEY), any());
//         }

//         private ClipDeleteRequest deleteRequest(Integer clipId) {
//             ClipDeleteRequest req = new ClipDeleteRequest();
//             req.setProjectId(PROJECT_ID);
//             req.setClipId(clipId);
//             return req;
//         }

//         private String clipStateJson() throws JsonProcessingException {
//             return objectMapper.writeValueAsString(ClipState.builder()
//                     .clipId(CLIP_ID).trackId(1).start(1.0).duration(4.0)
//                     .audioStartMs(0).audioDurationMs(4000)
//                     .build());
//         }

//         @Test
//         @DisplayName("Redis에 클립 상태가 있을 때 삭제 성공 시 clipId를 반환하고 Redis 상태와 락을 제거한다")
//         void deleteSuccess_fromRedis() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson());
//             when(redisTemplate.delete(LOCK_KEY)).thenReturn(true);

//             ClipDeleteResponse response = clipService.deleteClip(deleteRequest(CLIP_ID), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//             assertThat(store).doesNotContainKey(String.valueOf(CLIP_ID));
//             verify(redisTemplate).delete(LOCK_KEY);
//         }

//         @Test
//         @DisplayName("Redis에 클립 상태가 없을 때 MySQL에서 확인 후 삭제 성공한다")
//         void deleteSuccess_lazyInit() {
//             Track mockTrack = mock(Track.class);
//             Clip mockClip = mock(Clip.class);
//             AudioMetadata mockAudio = mock(AudioMetadata.class);
//             when(mockTrack.getId()).thenReturn(1);
//             when(mockClip.getId()).thenReturn(CLIP_ID);
//             when(mockClip.getTrack()).thenReturn(mockTrack);
//             when(mockClip.getStart()).thenReturn(1.0);
//             when(mockClip.getDuration()).thenReturn(4.0);
//             when(mockAudio.getId()).thenReturn(42);
//             when(mockClip.getAudioMetadata()).thenReturn(mockAudio);
//             when(mockClip.getColor()).thenReturn("#FFFFFF");
//             when(mockClip.getAudioStartMs()).thenReturn(0);
//             when(mockClip.getAudioDurationMs()).thenReturn(4000);
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.of(mockClip));
//             when(redisTemplate.delete(LOCK_KEY)).thenReturn(true);

//             ClipDeleteResponse response = clipService.deleteClip(deleteRequest(CLIP_ID), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//             verify(redisTemplate).delete(LOCK_KEY);
//         }

//         @Test
//         @DisplayName("클립이 잠겨있지 않으면 CLIP_LOCKED 예외를 던진다")
//         void deleteFailWhenNotLocked() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(null);

//             assertThatThrownBy(() -> clipService.deleteClip(deleteRequest(CLIP_ID), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));
//         }

//         @Test
//         @DisplayName("다른 사용자가 잠근 클립에 삭제 요청 시 CLIP_LOCKED 예외를 던진다")
//         void deleteFailWhenLockedByOtherUser() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(OTHER_USER_ID));

//             assertThatThrownBy(() -> clipService.deleteClip(deleteRequest(CLIP_ID), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));
//         }

//         @Test
//         @DisplayName("Redis에 없고 MySQL에도 없는 클립 삭제 시 CLIP_NOT_FOUND 예외를 던진다")
//         void deleteFailWhenClipNotFound() {
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.empty());

//             assertThatThrownBy(() -> clipService.deleteClip(deleteRequest(CLIP_ID), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_NOT_FOUND));
//         }

//         @Nested
//         @DisplayName("validate")
//         class ValidateTest {

//             @Test
//             @DisplayName("projectId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void projectIdNull() {
//                 ClipDeleteRequest req = new ClipDeleteRequest();
//                 req.setClipId(CLIP_ID);

//                 assertThatThrownBy(() -> clipService.deleteClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("clipId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void clipIdNull() {
//                 ClipDeleteRequest req = new ClipDeleteRequest();
//                 req.setProjectId(PROJECT_ID);

//                 assertThatThrownBy(() -> clipService.deleteClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }
//         }
//     }

//     @Nested
//     @DisplayName("splitClip")
//     class SplitClipTest {

//         private static final Double ORIGINAL_START = 1.0;
//         private static final Double ORIGINAL_DURATION = 6.0;
//         private static final Double SPLIT_BAR = 4.0;
//         private static final String CLIP_STATE_KEY = "project:1:clips";
//         private static final String CLIP_ID_SEQ_KEY = "global:clip:id_seq";
//         private static final Integer NEW_CLIP_ID = 100;

//         private Map<String, String> store;

//         @BeforeEach
//         void setUp() {
//             store = new HashMap<>();

//             lenient().when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(USER_ID));
//             lenient().when(valueOperations.increment(CLIP_ID_SEQ_KEY)).thenReturn(NEW_CLIP_ID.longValue());

//             lenient().doAnswer(inv -> store.get(inv.getArgument(1).toString()))
//                     .when(hashOperations).get(eq(CLIP_STATE_KEY), any());
//             lenient().doAnswer(inv -> {
//                 store.put(inv.getArgument(1).toString(), inv.getArgument(2).toString());
//                 return null;
//             }).when(hashOperations).put(eq(CLIP_STATE_KEY), any(), any());
//         }

//         private ClipSplitRequest splitRequest(Integer clipId, Double splitBar) {
//             ClipSplitRequest req = new ClipSplitRequest();
//             req.setProjectId(PROJECT_ID);
//             req.setClipId(clipId);
//             req.setSplitBar(splitBar);
//             return req;
//         }

//         private String clipStateJson(Double start, Double duration) throws JsonProcessingException {
//             return objectMapper.writeValueAsString(ClipState.builder()
//                     .clipId(CLIP_ID).trackId(1).start(start).duration(duration)
//                     .audioStartMs(0).audioDurationMs(6000)
//                     .build());
//         }

//         @Test
//         @DisplayName("분할 성공 시 원본 클립 duration이 줄고 새 클립이 생성된다")
//         void splitSuccess_fromRedis() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson(ORIGINAL_START, ORIGINAL_DURATION));

//             ClipSplitResponse response = clipService.splitClip(splitRequest(CLIP_ID, SPLIT_BAR), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//             assertThat(response.getSplitBar()).isEqualTo(SPLIT_BAR);
//             assertThat(response.getOriginalDuration()).isEqualTo(SPLIT_BAR - ORIGINAL_START);
//             assertThat(response.getNewClipId()).isEqualTo(NEW_CLIP_ID);
//             assertThat(response.getNewClipDuration()).isEqualTo(ORIGINAL_START + ORIGINAL_DURATION - SPLIT_BAR);

//             ClipState updatedOriginal = objectMapper.readValue(store.get(String.valueOf(CLIP_ID)), ClipState.class);
//             assertThat(updatedOriginal.getStart()).isEqualTo(ORIGINAL_START);
//             assertThat(updatedOriginal.getDuration()).isEqualTo(SPLIT_BAR - ORIGINAL_START);

//             ClipState newClip = objectMapper.readValue(store.get(String.valueOf(NEW_CLIP_ID)), ClipState.class);
//             assertThat(newClip.getStart()).isEqualTo(SPLIT_BAR);
//             assertThat(newClip.getDuration()).isEqualTo(ORIGINAL_START + ORIGINAL_DURATION - SPLIT_BAR);
//             assertThat(newClip.getTrackId()).isEqualTo(1);
//         }

//         @Test
//         @DisplayName("Redis에 상태가 없을 때 MySQL에서 로드 후 분할 성공한다")
//         void splitSuccess_lazyInit() throws JsonProcessingException {
//             Track mockTrack = mock(Track.class);
//             Clip mockClip = mock(Clip.class);
//             AudioMetadata mockAudio = mock(AudioMetadata.class);
//             when(mockTrack.getId()).thenReturn(1);
//             when(mockClip.getId()).thenReturn(CLIP_ID);
//             when(mockClip.getTrack()).thenReturn(mockTrack);
//             when(mockClip.getStart()).thenReturn(ORIGINAL_START);
//             when(mockClip.getDuration()).thenReturn(ORIGINAL_DURATION);
//             when(mockAudio.getId()).thenReturn(42);
//             when(mockClip.getAudioMetadata()).thenReturn(mockAudio);
//             when(mockClip.getColor()).thenReturn("#FFFFFF");
//             when(mockClip.getAudioStartMs()).thenReturn(0);
//             when(mockClip.getAudioDurationMs()).thenReturn(6000);
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.of(mockClip));

//             ClipSplitResponse response = clipService.splitClip(splitRequest(CLIP_ID, SPLIT_BAR), USER_ID);

//             assertThat(response.getOriginalDuration()).isEqualTo(SPLIT_BAR - ORIGINAL_START);
//             assertThat(response.getNewClipDuration()).isEqualTo(ORIGINAL_START + ORIGINAL_DURATION - SPLIT_BAR);
//         }

//         @Test
//         @DisplayName("분할 후 새 클립에는 락이 설정되지 않는다")
//         void splitDoesNotLockNewClip() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson(ORIGINAL_START, ORIGINAL_DURATION));
//             String newLockKey = String.format("project:%d:clip:%d:lock", PROJECT_ID, NEW_CLIP_ID);

//             clipService.splitClip(splitRequest(CLIP_ID, SPLIT_BAR), USER_ID);

//             verify(valueOperations, never()).set(eq(newLockKey), anyString());
//         }

//         @Test
//         @DisplayName("splitBar가 클립 시작과 같으면 INVALID_REQUEST 예외를 던진다")
//         void splitBarEqualsStart() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson(ORIGINAL_START, ORIGINAL_DURATION));

//             assertThatThrownBy(() -> clipService.splitClip(splitRequest(CLIP_ID, ORIGINAL_START), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.INVALID_REQUEST));
//         }

//         @Test
//         @DisplayName("splitBar가 클립 끝과 같으면 INVALID_REQUEST 예외를 던진다")
//         void splitBarEqualsEnd() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson(ORIGINAL_START, ORIGINAL_DURATION));
//             Double originalEnd = ORIGINAL_START + ORIGINAL_DURATION;

//             assertThatThrownBy(() -> clipService.splitClip(splitRequest(CLIP_ID, originalEnd), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.INVALID_REQUEST));
//         }

//         @Test
//         @DisplayName("splitBar가 클립 범위 밖이면 INVALID_REQUEST 예외를 던진다")
//         void splitBarOutOfRange() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson(ORIGINAL_START, ORIGINAL_DURATION));

//             assertThatThrownBy(() -> clipService.splitClip(splitRequest(CLIP_ID, 0.5), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.INVALID_REQUEST));
//         }

//         @Test
//         @DisplayName("클립이 잠겨있지 않으면 CLIP_LOCKED 예외를 던진다")
//         void splitFailWhenNotLocked() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(null);

//             assertThatThrownBy(() -> clipService.splitClip(splitRequest(CLIP_ID, SPLIT_BAR), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));
//         }

//         @Test
//         @DisplayName("다른 사용자가 잠근 클립에 분할 요청 시 CLIP_LOCKED 예외를 던진다")
//         void splitFailWhenLockedByOtherUser() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(OTHER_USER_ID));

//             assertThatThrownBy(() -> clipService.splitClip(splitRequest(CLIP_ID, SPLIT_BAR), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));
//         }

//         @Test
//         @DisplayName("Redis에 없고 MySQL에도 없는 클립 분할 시 CLIP_NOT_FOUND 예외를 던진다")
//         void splitFailWhenClipNotFound() {
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.empty());

//             assertThatThrownBy(() -> clipService.splitClip(splitRequest(CLIP_ID, SPLIT_BAR), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_NOT_FOUND));
//         }

//         @Nested
//         @DisplayName("validate")
//         class ValidateTest {

//             @Test
//             @DisplayName("projectId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void projectIdNull() {
//                 ClipSplitRequest req = new ClipSplitRequest();
//                 req.setClipId(CLIP_ID);
//                 req.setSplitBar(SPLIT_BAR);

//                 assertThatThrownBy(() -> clipService.splitClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("clipId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void clipIdNull() {
//                 ClipSplitRequest req = new ClipSplitRequest();
//                 req.setProjectId(PROJECT_ID);
//                 req.setSplitBar(SPLIT_BAR);

//                 assertThatThrownBy(() -> clipService.splitClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("splitBar가 null이면 INVALID_REQUEST 예외를 던진다")
//             void splitBarNull() {
//                 ClipSplitRequest req = new ClipSplitRequest();
//                 req.setProjectId(PROJECT_ID);
//                 req.setClipId(CLIP_ID);

//                 assertThatThrownBy(() -> clipService.splitClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }
//         }
//     }

//     @Nested
//     @DisplayName("duplicateClip")
//     class DuplicateClipTest {

//         private static final Double ORIGINAL_START = 2.0;
//         private static final Double ORIGINAL_DURATION = 4.0;
//         private static final Integer ORIGINAL_TRACK_ID = 1;
//         private static final Integer NEW_CLIP_ID = 200;
//         private static final String CLIP_STATE_KEY = "project:1:clips";
//         private static final String CLIP_ID_SEQ_KEY = "global:clip:id_seq";

//         private Map<String, String> store;

//         @BeforeEach
//         void setUp() {
//             store = new HashMap<>();

//             lenient().when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(USER_ID));
//             lenient().when(valueOperations.increment(CLIP_ID_SEQ_KEY)).thenReturn(NEW_CLIP_ID.longValue());

//             lenient().doAnswer(inv -> store.get(inv.getArgument(1).toString()))
//                     .when(hashOperations).get(eq(CLIP_STATE_KEY), any());
//             lenient().doAnswer(inv -> {
//                 store.put(inv.getArgument(1).toString(), inv.getArgument(2).toString());
//                 return null;
//             }).when(hashOperations).put(eq(CLIP_STATE_KEY), any(), any());
//         }

//         private ClipDuplicateRequest duplicateRequest(Integer clipId) {
//             ClipDuplicateRequest req = new ClipDuplicateRequest();
//             req.setProjectId(PROJECT_ID);
//             req.setClipId(clipId);
//             return req;
//         }

//         private String clipStateJson() throws JsonProcessingException {
//             return objectMapper.writeValueAsString(ClipState.builder()
//                     .clipId(CLIP_ID).trackId(ORIGINAL_TRACK_ID).start(ORIGINAL_START).duration(ORIGINAL_DURATION)
//                     .build());
//         }

//         @Test
//         @DisplayName("복제 성공 시 원본 클립 끝에 동일한 duration의 새 클립이 생성된다")
//         void duplicateSuccess_fromRedis() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson());

//             ClipDuplicateResponse response = clipService.duplicateClip(duplicateRequest(CLIP_ID), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//             assertThat(response.getNewClipId()).isEqualTo(NEW_CLIP_ID);
//             assertThat(response.getTargetTrackId()).isEqualTo(ORIGINAL_TRACK_ID);
//             assertThat(response.getTargetStartBar()).isEqualTo(ORIGINAL_START + ORIGINAL_DURATION);

//             ClipState newClipState = objectMapper.readValue(store.get(String.valueOf(NEW_CLIP_ID)), ClipState.class);
//             assertThat(newClipState.getStart()).isEqualTo(ORIGINAL_START + ORIGINAL_DURATION);
//             assertThat(newClipState.getDuration()).isEqualTo(ORIGINAL_DURATION);
//             assertThat(newClipState.getTrackId()).isEqualTo(ORIGINAL_TRACK_ID);
//         }

//         @Test
//         @DisplayName("Redis에 상태가 없을 때 MySQL에서 로드 후 복제 성공한다")
//         void duplicateSuccess_lazyInit() throws JsonProcessingException {
//             Track mockTrack = mock(Track.class);
//             Clip mockClip = mock(Clip.class);
//             AudioMetadata mockAudio = mock(AudioMetadata.class);
//             when(mockTrack.getId()).thenReturn(ORIGINAL_TRACK_ID);
//             when(mockClip.getId()).thenReturn(CLIP_ID);
//             when(mockClip.getTrack()).thenReturn(mockTrack);
//             when(mockClip.getStart()).thenReturn(ORIGINAL_START);
//             when(mockClip.getDuration()).thenReturn(ORIGINAL_DURATION);
//             when(mockAudio.getId()).thenReturn(42);
//             when(mockClip.getAudioMetadata()).thenReturn(mockAudio);
//             when(mockClip.getColor()).thenReturn("#FFFFFF");
//             when(mockClip.getAudioStartMs()).thenReturn(0);
//             when(mockClip.getAudioDurationMs()).thenReturn(4000);
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.of(mockClip));

//             ClipDuplicateResponse response = clipService.duplicateClip(duplicateRequest(CLIP_ID), USER_ID);

//             assertThat(response.getTargetStartBar()).isEqualTo(ORIGINAL_START + ORIGINAL_DURATION);
//             assertThat(response.getTargetTrackId()).isEqualTo(ORIGINAL_TRACK_ID);
//         }

//         @Test
//         @DisplayName("복제 후 락 이전이 MULTI/EXEC 트랜잭션으로 원자적으로 실행된다")
//         void duplicateTransfersLockAtomically() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson());

//             clipService.duplicateClip(duplicateRequest(CLIP_ID), USER_ID);

//             verify(redisTemplate).execute(any(org.springframework.data.redis.core.SessionCallback.class));
//         }

//         @Test
//         @DisplayName("클립이 잠겨있지 않으면 CLIP_LOCKED 예외를 던진다")
//         void duplicateFailWhenNotLocked() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(null);

//             assertThatThrownBy(() -> clipService.duplicateClip(duplicateRequest(CLIP_ID), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));
//         }

//         @Test
//         @DisplayName("다른 사용자가 잠근 클립에 복제 요청 시 CLIP_LOCKED 예외를 던진다")
//         void duplicateFailWhenLockedByOtherUser() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(OTHER_USER_ID));

//             assertThatThrownBy(() -> clipService.duplicateClip(duplicateRequest(CLIP_ID), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));
//         }

//         @Test
//         @DisplayName("Redis에 없고 MySQL에도 없는 클립 복제 시 CLIP_NOT_FOUND 예외를 던진다")
//         void duplicateFailWhenClipNotFound() {
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.empty());

//             assertThatThrownBy(() -> clipService.duplicateClip(duplicateRequest(CLIP_ID), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_NOT_FOUND));
//         }

//         @Nested
//         @DisplayName("validate")
//         class ValidateTest {

//             @Test
//             @DisplayName("projectId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void projectIdNull() {
//                 ClipDuplicateRequest req = new ClipDuplicateRequest();
//                 req.setClipId(CLIP_ID);

//                 assertThatThrownBy(() -> clipService.duplicateClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("clipId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void clipIdNull() {
//                 ClipDuplicateRequest req = new ClipDuplicateRequest();
//                 req.setProjectId(PROJECT_ID);

//                 assertThatThrownBy(() -> clipService.duplicateClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }
//         }
//     }

//     @Nested
//     @DisplayName("cutClip")
//     class CutClipTest {

//         private static final Double ORIGINAL_START = 2.0;
//         private static final Double ORIGINAL_DURATION = 4.0;
//         private static final Integer ORIGINAL_TRACK_ID = 1;
//         private static final String CLIP_STATE_KEY = "project:1:clips";

//         private Map<String, String> store;

//         @BeforeEach
//         void setUp() {
//             store = new HashMap<>();

//             lenient().when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(USER_ID));

//             lenient().doAnswer(inv -> store.get(inv.getArgument(1).toString()))
//                     .when(hashOperations).get(eq(CLIP_STATE_KEY), any());
//             lenient().doAnswer(inv -> {
//                 store.put(inv.getArgument(1).toString(), inv.getArgument(2).toString());
//                 return null;
//             }).when(hashOperations).put(eq(CLIP_STATE_KEY), any(), any());
//         }

//         private ClipCutRequest cutRequest(Integer clipId) {
//             ClipCutRequest req = new ClipCutRequest();
//             req.setProjectId(PROJECT_ID);
//             req.setClipId(clipId);
//             return req;
//         }

//         private String clipStateJson() throws JsonProcessingException {
//             return objectMapper.writeValueAsString(ClipState.builder()
//                     .clipId(CLIP_ID).trackId(ORIGINAL_TRACK_ID).start(ORIGINAL_START).duration(ORIGINAL_DURATION)
//                     .build());
//         }

//         @Test
//         @DisplayName("Redis에 클립 상태가 있을 때 CUT 성공 시 clipId를 반환한다")
//         void cutSuccess_fromRedis() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson());

//             ClipCutResponse response = clipService.cutClip(cutRequest(CLIP_ID), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//         }

//         @Test
//         @DisplayName("Redis에 상태가 없을 때 MySQL에서 로드 후 CUT 성공한다")
//         void cutSuccess_lazyInit() {
//             Track mockTrack = mock(Track.class);
//             Clip mockClip = mock(Clip.class);
//             AudioMetadata mockAudio = mock(AudioMetadata.class);
//             when(mockTrack.getId()).thenReturn(ORIGINAL_TRACK_ID);
//             when(mockClip.getId()).thenReturn(CLIP_ID);
//             when(mockClip.getTrack()).thenReturn(mockTrack);
//             when(mockClip.getStart()).thenReturn(ORIGINAL_START);
//             when(mockClip.getDuration()).thenReturn(ORIGINAL_DURATION);
//             when(mockAudio.getId()).thenReturn(42);
//             when(mockClip.getAudioMetadata()).thenReturn(mockAudio);
//             when(mockClip.getColor()).thenReturn("#FFFFFF");
//             when(mockClip.getAudioStartMs()).thenReturn(0);
//             when(mockClip.getAudioDurationMs()).thenReturn(4000);
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.of(mockClip));

//             ClipCutResponse response = clipService.cutClip(cutRequest(CLIP_ID), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//         }

//         @Test
//         @DisplayName("클립보드 저장, 타임라인 제거, 락 해제가 MULTI/EXEC 트랜잭션으로 원자적으로 실행된다")
//         void cutAtomicExecution() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson());

//             clipService.cutClip(cutRequest(CLIP_ID), USER_ID);

//             verify(redisTemplate).execute(any(org.springframework.data.redis.core.SessionCallback.class));
//         }

//         @Test
//         @DisplayName("클립이 잠겨있지 않으면 CLIP_LOCKED 예외를 던진다")
//         void cutFailWhenNotLocked() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(null);

//             assertThatThrownBy(() -> clipService.cutClip(cutRequest(CLIP_ID), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));
//         }

//         @Test
//         @DisplayName("다른 사용자가 잠근 클립에 CUT 요청 시 CLIP_LOCKED 예외를 던진다")
//         void cutFailWhenLockedByOtherUser() {
//             when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(OTHER_USER_ID));

//             assertThatThrownBy(() -> clipService.cutClip(cutRequest(CLIP_ID), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_LOCKED));
//         }

//         @Test
//         @DisplayName("Redis에 없고 MySQL에도 없는 클립 CUT 시 CLIP_NOT_FOUND 예외를 던진다")
//         void cutFailWhenClipNotFound() {
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.empty());

//             assertThatThrownBy(() -> clipService.cutClip(cutRequest(CLIP_ID), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_NOT_FOUND));
//         }

//         @Nested
//         @DisplayName("validate")
//         class ValidateTest {

//             @Test
//             @DisplayName("projectId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void projectIdNull() {
//                 ClipCutRequest req = new ClipCutRequest();
//                 req.setClipId(CLIP_ID);

//                 assertThatThrownBy(() -> clipService.cutClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("clipId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void clipIdNull() {
//                 ClipCutRequest req = new ClipCutRequest();
//                 req.setProjectId(PROJECT_ID);

//                 assertThatThrownBy(() -> clipService.cutClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }
//         }
//     }

//     @Nested
//     @DisplayName("copyClip")
//     class CopyClipTest {

//         private static final Double ORIGINAL_START = 1.0;
//         private static final Double ORIGINAL_DURATION = 4.0;
//         private static final Integer ORIGINAL_TRACK_ID = 1;
//         private static final String CLIP_STATE_KEY = "project:1:clips";
//         private static final String CLIPBOARD_KEY = "project:1:user:1:clipboard";

//         private Map<String, String> store;

//         @BeforeEach
//         void setUp() {
//             store = new HashMap<>();

//             lenient().doAnswer(inv -> store.get(inv.getArgument(1).toString()))
//                     .when(hashOperations).get(eq(CLIP_STATE_KEY), any());
//             lenient().doAnswer(inv -> {
//                 store.put(inv.getArgument(1).toString(), inv.getArgument(2).toString());
//                 return null;
//             }).when(hashOperations).put(eq(CLIP_STATE_KEY), any(), any());
//         }

//         private ClipCopyRequest copyRequest(Integer clipId) {
//             ClipCopyRequest req = new ClipCopyRequest();
//             req.setProjectId(PROJECT_ID);
//             req.setClipId(clipId);
//             return req;
//         }

//         private String clipStateJson() throws JsonProcessingException {
//             return objectMapper.writeValueAsString(ClipState.builder()
//                     .clipId(CLIP_ID).trackId(ORIGINAL_TRACK_ID).start(ORIGINAL_START).duration(ORIGINAL_DURATION)
//                     .build());
//         }

//         @Test
//         @DisplayName("Redis에 클립 상태가 있을 때 COPY 성공 시 clipId를 반환한다")
//         void copySuccess_fromRedis() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson());

//             ClipCopyResponse response = clipService.copyClip(copyRequest(CLIP_ID), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//         }

//         @Test
//         @DisplayName("Redis에 상태가 없을 때 MySQL에서 로드 후 COPY 성공한다")
//         void copySuccess_lazyInit() {
//             Track mockTrack = mock(Track.class);
//             Clip mockClip = mock(Clip.class);
//             AudioMetadata mockAudio = mock(AudioMetadata.class);
//             when(mockTrack.getId()).thenReturn(ORIGINAL_TRACK_ID);
//             when(mockClip.getId()).thenReturn(CLIP_ID);
//             when(mockClip.getTrack()).thenReturn(mockTrack);
//             when(mockClip.getStart()).thenReturn(ORIGINAL_START);
//             when(mockClip.getDuration()).thenReturn(ORIGINAL_DURATION);
//             when(mockAudio.getId()).thenReturn(42);
//             when(mockClip.getAudioMetadata()).thenReturn(mockAudio);
//             when(mockClip.getColor()).thenReturn("#FFFFFF");
//             when(mockClip.getAudioStartMs()).thenReturn(0);
//             when(mockClip.getAudioDurationMs()).thenReturn(4000);
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.of(mockClip));

//             ClipCopyResponse response = clipService.copyClip(copyRequest(CLIP_ID), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//         }

//         @Test
//         @DisplayName("COPY 시 타임라인 클립은 제거되지 않는다")
//         void copyDoesNotRemoveClipFromTimeline() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson());

//             clipService.copyClip(copyRequest(CLIP_ID), USER_ID);

//             verify(hashOperations, never()).delete(any(), any());
//         }

//         @Test
//         @DisplayName("COPY 시 락이 필요하지 않아 잠겨있지 않은 클립도 복사할 수 있다")
//         void copySuccessWithoutLock() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson());
//             lenient().when(valueOperations.get(LOCK_KEY)).thenReturn(null);

//             ClipCopyResponse response = clipService.copyClip(copyRequest(CLIP_ID), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(CLIP_ID);
//         }

//         @Test
//         @DisplayName("COPY 시 클립보드에 ClipState JSON이 저장된다")
//         void copySavesStateToClipboard() throws JsonProcessingException {
//             store.put(String.valueOf(CLIP_ID), clipStateJson());

//             clipService.copyClip(copyRequest(CLIP_ID), USER_ID);

//             verify(valueOperations).set(eq(CLIPBOARD_KEY), anyString());
//         }

//         @Test
//         @DisplayName("Redis에 없고 MySQL에도 없는 클립 COPY 시 CLIP_NOT_FOUND 예외를 던진다")
//         void copyFailWhenClipNotFound() {
//             when(clipRepository.findById(CLIP_ID)).thenReturn(Optional.empty());

//             assertThatThrownBy(() -> clipService.copyClip(copyRequest(CLIP_ID), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_NOT_FOUND));
//         }

//         @Nested
//         @DisplayName("validate")
//         class ValidateTest {

//             @Test
//             @DisplayName("projectId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void projectIdNull() {
//                 ClipCopyRequest req = new ClipCopyRequest();
//                 req.setClipId(CLIP_ID);

//                 assertThatThrownBy(() -> clipService.copyClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("clipId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void clipIdNull() {
//                 ClipCopyRequest req = new ClipCopyRequest();
//                 req.setProjectId(PROJECT_ID);

//                 assertThatThrownBy(() -> clipService.copyClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }
//         }
//     }

//     @Nested
//     @DisplayName("createClip")
//     class CreateClipTest {

//         private static final Integer TRACK_ID = 2;
//         private static final Integer NEW_CLIP_ID = 10;
//         private static final Integer AUDIO_METADATA_ID = 42;
//         private static final Integer DURATION_MS = 8000;
//         private static final Double EXPECTED_DURATION_BARS = 4.0; // (8000/1000) * (120/60) / 4
//         private static final String CLIP_STATE_KEY = "project:1:clips";
//         private static final String CLIP_ID_SEQ_KEY = "global:clip:id_seq";

//         private Map<String, String> store;

//         @BeforeEach
//         void setUp() {
//             store = new HashMap<>();

//             Project mockProject = mock(Project.class);
//             lenient().when(mockProject.getTempo()).thenReturn(120.0);
//             lenient().when(mockProject.getTimeSigNumerator()).thenReturn(4);
//             lenient().when(projectService.getProjectOrThrow(PROJECT_ID)).thenReturn(mockProject);

//             AudioMetadata mockAudio = mock(AudioMetadata.class);
//             lenient().when(mockAudio.getId()).thenReturn(AUDIO_METADATA_ID);
//             lenient().when(mockAudio.getDurationMs()).thenReturn(DURATION_MS);
//             lenient().when(audioService.createAudioMetadata(any())).thenReturn(mockAudio);

//             lenient().when(valueOperations.increment(CLIP_ID_SEQ_KEY)).thenReturn(NEW_CLIP_ID.longValue());
//             lenient().when(trackRepository.findByIdAndProject_Id(TRACK_ID, PROJECT_ID)).thenReturn(Optional.of(mock(Track.class)));

//             lenient().doAnswer(inv -> {
//                 store.put(inv.getArgument(1).toString(), inv.getArgument(2).toString());
//                 return null;
//             }).when(hashOperations).put(eq(CLIP_STATE_KEY), any(), any());
//         }

//         private ClipCreateRequest createRequest() {
//             ClipCreateRequest req = new ClipCreateRequest();
//             req.setProjectId(PROJECT_ID);
//             req.setTrackId(TRACK_ID);
//             req.setStartBar(0.0);
//             req.setColor("#FF0000");
//             req.setObjectKey("projects/1/audios/test.mp3");
//             req.setOriginalName("test.mp3");
//             req.setStoredName("test.mp3");
//             req.setMimeType(MimeType.MPEG);
//             req.setSizeBytes(100000);
//             req.setDurationMs(DURATION_MS);
//             return req;
//         }

//         @Test
//         @DisplayName("생성 성공 시 clipId, duration, audioMetadataId, color 등을 반환한다")
//         void createSuccess() {
//             ClipCreateResponse response = clipService.createClip(createRequest(), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(NEW_CLIP_ID);
//             assertThat(response.getTrackId()).isEqualTo(TRACK_ID);
//             assertThat(response.getStartBar()).isEqualTo(0.0);
//             assertThat(response.getDuration()).isEqualTo(EXPECTED_DURATION_BARS);
//             assertThat(response.getColor()).isEqualTo("#FF0000");
//             assertThat(response.getAudioMetadataId()).isEqualTo(AUDIO_METADATA_ID);
//             assertThat(response.getAudioStartMs()).isEqualTo(0);
//             assertThat(response.getAudioDurationMs()).isEqualTo(DURATION_MS);
//         }

//         @Test
//         @DisplayName("duration은 (durationMs/1000) * (tempo/60) / timeSigNumerator 공식으로 계산된다")
//         void durationCalculation() {
//             // durationMs=8000, tempo=120, timeSigNumerator=4 → 4.0 bars
//             ClipCreateResponse response = clipService.createClip(createRequest(), USER_ID);
//             assertThat(response.getDuration()).isEqualTo(4.0);
//         }

//         @Test
//         @DisplayName("생성 시 audioService.createAudioMetadata가 호출된다")
//         void callsAudioServiceCreate() {
//             clipService.createClip(createRequest(), USER_ID);
//             verify(audioService).createAudioMetadata(any());
//         }

//         @Test
//         @DisplayName("생성 후 Redis Hash에 ClipState가 저장된다")
//         void savesClipStateToRedis() throws JsonProcessingException {
//             clipService.createClip(createRequest(), USER_ID);

//             ClipState saved = objectMapper.readValue(store.get(String.valueOf(NEW_CLIP_ID)), ClipState.class);
//             assertThat(saved.getClipId()).isEqualTo(NEW_CLIP_ID);
//             assertThat(saved.getTrackId()).isEqualTo(TRACK_ID);
//             assertThat(saved.getDuration()).isEqualTo(EXPECTED_DURATION_BARS);
//             assertThat(saved.getAudioMetadataId()).isEqualTo(AUDIO_METADATA_ID);
//             assertThat(saved.getAudioStartMs()).isEqualTo(0);
//             assertThat(saved.getAudioDurationMs()).isEqualTo(DURATION_MS);
//         }

//         @Test
//         @DisplayName("audioStartMs는 0으로 초기화된다 (전체 오디오 사용)")
//         void audioStartMsIsZero() {
//             ClipCreateResponse response = clipService.createClip(createRequest(), USER_ID);
//             assertThat(response.getAudioStartMs()).isEqualTo(0);
//             assertThat(response.getAudioDurationMs()).isEqualTo(DURATION_MS);
//         }

//         @Nested
//         @DisplayName("validate")
//         class ValidateTest {

//             @Test
//             @DisplayName("projectId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void projectIdNull() {
//                 ClipCreateRequest req = createRequest();
//                 req.setProjectId(null);

//                 assertThatThrownBy(() -> clipService.createClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("trackId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void trackIdNull() {
//                 ClipCreateRequest req = createRequest();
//                 req.setTrackId(null);

//                 assertThatThrownBy(() -> clipService.createClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("startBar가 null이면 INVALID_REQUEST 예외를 던진다")
//             void startBarNull() {
//                 ClipCreateRequest req = createRequest();
//                 req.setStartBar(null);

//                 assertThatThrownBy(() -> clipService.createClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("color가 null이면 INVALID_REQUEST 예외를 던진다")
//             void colorNull() {
//                 ClipCreateRequest req = createRequest();
//                 req.setColor(null);

//                 assertThatThrownBy(() -> clipService.createClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("objectKey가 null이면 INVALID_REQUEST 예외를 던진다")
//             void objectKeyNull() {
//                 ClipCreateRequest req = createRequest();
//                 req.setObjectKey(null);

//                 assertThatThrownBy(() -> clipService.createClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("durationMs가 null이면 INVALID_REQUEST 예외를 던진다")
//             void durationMsNull() {
//                 ClipCreateRequest req = createRequest();
//                 req.setDurationMs(null);

//                 assertThatThrownBy(() -> clipService.createClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }
//         }
//     }

//     @Nested
//     @DisplayName("pasteClip")
//     class PasteClipTest {

//         private static final Integer TARGET_TRACK_ID = 2;
//         private static final Double TARGET_START_BAR = 3.0;
//         private static final Double CLIPBOARD_DURATION = 4.0;
//         private static final Integer NEW_CLIP_ID = 300;
//         private static final String CLIP_STATE_KEY = "project:1:clips";
//         private static final String CLIP_ID_SEQ_KEY = "global:clip:id_seq";
//         private static final String CLIPBOARD_KEY = "project:1:user:1:clipboard";

//         private Map<String, String> store;

//         @BeforeEach
//         void setUp() throws JsonProcessingException {
//             store = new HashMap<>();

//             lenient().when(valueOperations.increment(CLIP_ID_SEQ_KEY)).thenReturn(NEW_CLIP_ID.longValue());
//             lenient().when(trackRepository.findByIdAndProject_Id(TARGET_TRACK_ID, PROJECT_ID)).thenReturn(Optional.of(mock(Track.class)));

//             lenient().doAnswer(inv -> {
//                 store.put(inv.getArgument(1).toString(), inv.getArgument(2).toString());
//                 return null;
//             }).when(hashOperations).put(eq(CLIP_STATE_KEY), any(), any());
//         }

//         private ClipPasteRequest pasteRequest() {
//             ClipPasteRequest req = new ClipPasteRequest();
//             req.setProjectId(PROJECT_ID);
//             req.setTargetTrackId(TARGET_TRACK_ID);
//             req.setTargetStartBar(TARGET_START_BAR);
//             return req;
//         }

//         private String clipboardStateJson() throws JsonProcessingException {
//             return objectMapper.writeValueAsString(ClipState.builder()
//                     .clipId(CLIP_ID).trackId(1).start(1.0).duration(CLIPBOARD_DURATION)
//                     .build());
//         }

//         @Test
//         @DisplayName("클립보드에 상태가 있을 때 붙여넣기 성공 시 새 clipId와 위치를 반환한다")
//         void pasteSuccess() throws JsonProcessingException {
//             String clipboard = clipboardStateJson();
//             when(valueOperations.get(CLIPBOARD_KEY)).thenReturn(clipboard);

//             ClipPasteResponse response = clipService.pasteClip(pasteRequest(), USER_ID);

//             assertThat(response.getClipId()).isEqualTo(NEW_CLIP_ID);
//             assertThat(response.getTargetTrackId()).isEqualTo(TARGET_TRACK_ID);
//             assertThat(response.getTargetStartBar()).isEqualTo(TARGET_START_BAR);
//         }

//         @Test
//         @DisplayName("붙여넣기 성공 시 클립보드 ClipState의 duration을 사용해 새 클립을 Redis에 저장한다")
//         void pasteSavesNewClipToRedisWithClipboardDuration() throws JsonProcessingException {
//             String clipboard = clipboardStateJson();
//             when(valueOperations.get(CLIPBOARD_KEY)).thenReturn(clipboard);

//             clipService.pasteClip(pasteRequest(), USER_ID);

//             ClipState saved = objectMapper.readValue(store.get(String.valueOf(NEW_CLIP_ID)), ClipState.class);
//             assertThat(saved.getClipId()).isEqualTo(NEW_CLIP_ID);
//             assertThat(saved.getTrackId()).isEqualTo(TARGET_TRACK_ID);
//             assertThat(saved.getStart()).isEqualTo(TARGET_START_BAR);
//             assertThat(saved.getDuration()).isEqualTo(CLIPBOARD_DURATION);
//         }

//         @Test
//         @DisplayName("붙여넣기 후 클립보드는 유지된다 (반복 paste 가능)")
//         void pasteDoesNotClearClipboard() throws JsonProcessingException {
//             String clipboard = clipboardStateJson();
//             when(valueOperations.get(CLIPBOARD_KEY)).thenReturn(clipboard);

//             clipService.pasteClip(pasteRequest(), USER_ID);

//             verify(valueOperations, never()).set(eq(CLIPBOARD_KEY), any());
//             verify(redisTemplate, never()).delete(eq(CLIPBOARD_KEY));
//         }

//         @Test
//         @DisplayName("클립보드가 비어있으면 CLIP_NOT_FOUND 예외를 던진다")
//         void pasteFailWhenClipboardEmpty() {
//             when(valueOperations.get(CLIPBOARD_KEY)).thenReturn(null);

//             assertThatThrownBy(() -> clipService.pasteClip(pasteRequest(), USER_ID))
//                     .isInstanceOf(BusinessException.class)
//                     .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                             .isEqualTo(ErrorCode.CLIP_NOT_FOUND));
//         }

//         @Nested
//         @DisplayName("validate")
//         class ValidateTest {

//             @Test
//             @DisplayName("projectId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void projectIdNull() {
//                 ClipPasteRequest req = new ClipPasteRequest();
//                 req.setTargetTrackId(TARGET_TRACK_ID);
//                 req.setTargetStartBar(TARGET_START_BAR);

//                 assertThatThrownBy(() -> clipService.pasteClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("targetTrackId가 null이면 INVALID_REQUEST 예외를 던진다")
//             void targetTrackIdNull() {
//                 ClipPasteRequest req = new ClipPasteRequest();
//                 req.setProjectId(PROJECT_ID);
//                 req.setTargetStartBar(TARGET_START_BAR);

//                 assertThatThrownBy(() -> clipService.pasteClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }

//             @Test
//             @DisplayName("targetStartBar가 null이면 INVALID_REQUEST 예외를 던진다")
//             void targetStartBarNull() {
//                 ClipPasteRequest req = new ClipPasteRequest();
//                 req.setProjectId(PROJECT_ID);
//                 req.setTargetTrackId(TARGET_TRACK_ID);

//                 assertThatThrownBy(() -> clipService.pasteClip(req, USER_ID))
//                         .isInstanceOf(BusinessException.class)
//                         .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
//                                 .isEqualTo(ErrorCode.INVALID_REQUEST));
//             }
//         }
//     }
// }
