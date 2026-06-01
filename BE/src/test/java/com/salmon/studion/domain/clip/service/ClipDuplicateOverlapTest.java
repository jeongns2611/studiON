package com.salmon.studion.domain.clip.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.clip.dto.ClipState;
import com.salmon.studion.domain.audio.repository.AudioMetadataRepository;
import com.salmon.studion.domain.audio.service.AudioService;
import com.salmon.studion.domain.clip.dto.request.ClipDuplicateRequest;
import com.salmon.studion.domain.clip.repository.ClipEventRepository;
import com.salmon.studion.domain.clip.repository.ClipRepository;
import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.domain.project.service.ProjectService;
import com.salmon.studion.domain.track.repository.TrackRepository;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.HashOperations;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.SetOperations;
import org.springframework.data.redis.core.ValueOperations;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("duplicateClip 겹침 체크")
class ClipDuplicateOverlapTest {

    @Mock private ProjectService projectService;
    @Mock private AudioService audioService;
    @Mock private ClipRepository clipRepository;
    @Mock private ClipEventRepository clipEventRepository;
    @Mock private TrackRepository trackRepository;
    @Mock private AudioMetadataRepository audioMetadataRepository;
    @Mock private RedisTemplate<String, String> redisTemplate;
    @Spy  private ObjectMapper objectMapper = new ObjectMapper();

    @InjectMocks private ClipService clipService;

    @Mock private ValueOperations<String, String> valueOperations;
    @Mock private HashOperations<String, Object, Object> hashOperations;
    @Mock private SetOperations<String, String> setOperations;

    private static final Integer PROJECT_ID = 1;
    private static final Integer CLIP_ID = 3;
    private static final Integer OTHER_CLIP_ID = 99;
    private static final Integer USER_ID = 1;
    private static final Integer TRACK_ID = 1;
    private static final Integer OTHER_TRACK_ID = 2;
    private static final Double ORIGINAL_START = 2.0;
    private static final Double ORIGINAL_DURATION = 4.0;
    private static final Double TARGET_START = ORIGINAL_START + ORIGINAL_DURATION; // 6.0
    private static final String CLIP_STATE_KEY = "project:1:clips";
    private static final String LOCK_KEY = "project:1:clip:3:lock";
    private static final String CLIP_ID_SEQ_KEY = "global:clip:id_seq";
    private static final String EVENT_SEQ_KEY = "project:1:clip:event:seq";

    private Map<String, String> store;

    @BeforeEach
    void setUp() {
        store = new HashMap<>();

        lenient().when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        lenient().when(redisTemplate.opsForHash()).thenReturn(hashOperations);
        lenient().when(redisTemplate.opsForSet()).thenReturn(setOperations);
        lenient().when(projectService.getProjectOrThrow(PROJECT_ID)).thenReturn(mock(Project.class));
        lenient().when(valueOperations.get(LOCK_KEY)).thenReturn(String.valueOf(USER_ID));
        lenient().when(valueOperations.increment(CLIP_ID_SEQ_KEY)).thenReturn(100L);
        lenient().when(valueOperations.increment(EVENT_SEQ_KEY)).thenReturn(1L);

        lenient().doAnswer(inv -> store.get(inv.getArgument(1).toString()))
                .when(hashOperations).get(eq(CLIP_STATE_KEY), any());
        lenient().doAnswer(inv -> {
            store.put(inv.getArgument(1).toString(), inv.getArgument(2).toString());
            return null;
        }).when(hashOperations).put(eq(CLIP_STATE_KEY), any(), any());
        lenient().doAnswer(inv -> new ArrayList<>(store.values()))
                .when(hashOperations).values(eq(CLIP_STATE_KEY));
    }

    private ClipDuplicateRequest duplicateRequest() {
        ClipDuplicateRequest req = new ClipDuplicateRequest();
        req.setProjectId(PROJECT_ID);
        req.setClipId(CLIP_ID);
        return req;
    }

    private String clipJson(Integer clipId, Integer trackId, Double start, Double duration) throws JsonProcessingException {
        return objectMapper.writeValueAsString(ClipState.builder()
                .clipId(clipId).trackId(trackId).start(start).duration(duration)
                .audioStartMs(0).audioDurationMs(4000)
                .build());
    }

    @Test
    @DisplayName("복제 공간에 다른 클립이 없으면 정상 복제된다")
    void duplicateSuccessWhenNoOverlap() throws JsonProcessingException {
        store.put(String.valueOf(CLIP_ID), clipJson(CLIP_ID, TRACK_ID, ORIGINAL_START, ORIGINAL_DURATION));

        assertThat(clipService.duplicateClip(duplicateRequest(), USER_ID)).isNotNull();
    }

    @Test
    @DisplayName("복제 위치에 다른 클립이 겹치면 CLIP_OVERLAP 예외를 던진다")
    void duplicateFailsWhenOverlapExists() throws JsonProcessingException {
        // 원본: [2, 6), 복제 위치: [6, 10), 다른 클립: [5, 9) → 겹침
        store.put(String.valueOf(CLIP_ID), clipJson(CLIP_ID, TRACK_ID, ORIGINAL_START, ORIGINAL_DURATION));
        store.put(String.valueOf(OTHER_CLIP_ID), clipJson(OTHER_CLIP_ID, TRACK_ID, 5.0, 4.0));

        assertThatThrownBy(() -> clipService.duplicateClip(duplicateRequest(), USER_ID))
                .isInstanceOf(BusinessException.class)
                .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
                        .isEqualTo(ErrorCode.CLIP_OVERLAP));
    }

    @Test
    @DisplayName("복제 위치 시작 지점에 다른 클립이 정확히 시작해도 CLIP_OVERLAP 예외를 던진다")
    void duplicateFailsWhenOtherClipStartsAtTargetStart() throws JsonProcessingException {
        // 원본: [2, 6), 복제 위치: [6, 10), 다른 클립: [6, 10) → 겹침
        store.put(String.valueOf(CLIP_ID), clipJson(CLIP_ID, TRACK_ID, ORIGINAL_START, ORIGINAL_DURATION));
        store.put(String.valueOf(OTHER_CLIP_ID), clipJson(OTHER_CLIP_ID, TRACK_ID, TARGET_START, ORIGINAL_DURATION));

        assertThatThrownBy(() -> clipService.duplicateClip(duplicateRequest(), USER_ID))
                .isInstanceOf(BusinessException.class)
                .satisfies(e -> assertThat(((BusinessException) e).getErrorCode())
                        .isEqualTo(ErrorCode.CLIP_OVERLAP));
    }

    @Test
    @DisplayName("복제 위치 바로 뒤에서 시작하는 클립은 겹치지 않아 정상 복제된다")
    void duplicateSuccessWhenOtherClipStartsAfterNewClipEnd() throws JsonProcessingException {
        // 원본: [2, 6), 복제 위치: [6, 10), 다른 클립: [10, 14) → 겹침 없음
        store.put(String.valueOf(CLIP_ID), clipJson(CLIP_ID, TRACK_ID, ORIGINAL_START, ORIGINAL_DURATION));
        store.put(String.valueOf(OTHER_CLIP_ID), clipJson(OTHER_CLIP_ID, TRACK_ID, TARGET_START + ORIGINAL_DURATION, ORIGINAL_DURATION));

        assertThat(clipService.duplicateClip(duplicateRequest(), USER_ID)).isNotNull();
    }

    @Test
    @DisplayName("다른 트랙에 같은 위치의 클립이 있어도 겹침 체크에 걸리지 않는다")
    void duplicateSuccessWhenOverlapIsOnDifferentTrack() throws JsonProcessingException {
        // 원본: track1 [2, 6), 복제 위치: track1 [6, 10), 다른 클립: track2 [6, 10) → 다른 트랙이므로 무시
        store.put(String.valueOf(CLIP_ID), clipJson(CLIP_ID, TRACK_ID, ORIGINAL_START, ORIGINAL_DURATION));
        store.put(String.valueOf(OTHER_CLIP_ID), clipJson(OTHER_CLIP_ID, OTHER_TRACK_ID, TARGET_START, ORIGINAL_DURATION));

        assertThat(clipService.duplicateClip(duplicateRequest(), USER_ID)).isNotNull();
    }
}
