package com.salmon.studion.domain.clip.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.audio.dto.request.AudioMetadataCreateRequest;
import com.salmon.studion.domain.audio.entity.AudioMetadata;
import com.salmon.studion.domain.audio.repository.AudioMetadataRepository;
import com.salmon.studion.domain.audio.service.AudioService;
import com.salmon.studion.domain.clip.dto.ClipState;
import com.salmon.studion.domain.clip.dto.request.*;
import com.salmon.studion.domain.clip.dto.response.*;
import com.salmon.studion.domain.clip.entity.*;
import com.salmon.studion.domain.clip.repository.ClipEventRepository;
import com.salmon.studion.domain.clip.repository.ClipRepository;
import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.domain.project.service.ProjectService;
import com.salmon.studion.domain.track.entity.Track;
import com.salmon.studion.domain.track.repository.TrackRepository;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisOperations;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.SessionCallback;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ClipService {

    private static final String CLIP_LOCK_KEY = "project:%d:clip:%d:lock";
    private static final String CLIP_EVENT_SEQ_KEY = "project:%d:clip:event:seq";
    private static final String CLIP_STATE_KEY = "project:%d:clips";
    private static final String CLIP_ID_SEQ_KEY = "global:clip:id_seq";
    private static final String CLIP_CLIPBOARD_KEY = "project:%d:user:%d:clipboard";
    private static final String DELETED_CLIPS_KEY = "project:%d:deleted_clips";
    private static final int MAX_BAR_COUNT = 200;

    private final ProjectService projectService;
    private final AudioService audioService;
    private final ClipRepository clipRepository;
    private final ClipEventRepository clipEventRepository;
    private final TrackRepository trackRepository;
    private final AudioMetadataRepository audioMetadataRepository;
    private final RedisTemplate<String, String> redisTemplate;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    //////////////////////// RDB ////////////////////////

    /*
        특정 Track의 클립과 오디오 데이터를 가져오는 기능
     */
    public List<Clip> getClipsWithAudioMetadataByTrackIds(List<Integer> trackIds) {
        if (trackIds == null || trackIds.isEmpty()) {
            return List.of();
        }

        return clipRepository.findAllWithAudioMetadataByTrackIds(trackIds);
    }

    public boolean hasClipWorkingSet(Integer projectId) {
        return redisTemplate.hasKey(String.format(CLIP_STATE_KEY, projectId)) || redisTemplate.hasKey(String.format(DELETED_CLIPS_KEY, projectId));
    }

    public List<Clip> getClipsForProjectDetail(Integer projectId, List<Track> workingTracks) {
        List<Clip> persistedClips = clipRepository.findAllWithAudioMetadataByProjectId(projectId);

        Map<Integer, Clip> merged = persistedClips.stream()
                .map(this::copyClip)
                .collect(Collectors.toMap(
                        Clip::getId,
                        clip -> clip,
                        (left, right) -> left,
                        java.util.LinkedHashMap::new
                ));

        Map<Integer, Track> tracksById = workingTracks.stream()
                .collect(Collectors.toMap(Track::getId, track -> track));

        Map<Integer, AudioMetadata> audioById = persistedClips.stream()
                .map(Clip::getAudioMetadata)
                .collect(Collectors.toMap(AudioMetadata::getId, audio -> audio, (left, right) -> left));

        Map<Object, Object> redisEntries = redisTemplate.opsForHash().entries(String.format(CLIP_STATE_KEY, projectId));
        if (!redisEntries.isEmpty()) {
            java.util.Set<Integer> missingAudioIds = redisEntries.values().stream()
                    .map(value -> parseClipState((String) value).getAudioMetadataId())
                    .filter(audioId -> !audioById.containsKey(audioId))
                    .collect(Collectors.toSet());

            if (!missingAudioIds.isEmpty()) {
                audioMetadataRepository.findAllById(missingAudioIds)
                        .forEach(audio -> audioById.put(audio.getId(), audio));
            }

            for (Object value : redisEntries.values()) {
                ClipState state = parseClipState((String) value);

                merged.put(
                        state.getClipId(),
                        Clip.create(
                                state.getClipId(),
                                tracksById.get(state.getTrackId()),
                                audioById.get(state.getAudioMetadataId()),
                                state.getColor(),
                                state.getStart(),
                                state.getDuration(),
                                state.getAudioStartMs(),
                                state.getAudioDurationMs()
                        )
                );
            }
        }

        Set<String> deletedIds = redisTemplate.opsForSet().members(String.format(DELETED_CLIPS_KEY, projectId));
        if (deletedIds != null) {
            deletedIds.stream()
                    .map(Integer::parseInt)
                    .forEach(merged::remove);
        }

        return merged.values().stream().toList();
    }

    /*
        Redis의 클립에 대한 현재 상태를 RDB로 upsert + orphan delete
     */
    public void saveClipsByRedis(Integer projectId) {
        // 삭제된 clip RDB에서 제거
        String deletedKey = String.format(DELETED_CLIPS_KEY, projectId);
        Set<String> deletedIdStrs = redisTemplate.opsForSet().members(deletedKey);
        if (deletedIdStrs != null && !deletedIdStrs.isEmpty()) {
            List<Integer> deletedIds = deletedIdStrs.stream().map(Integer::parseInt).toList();
            clipRepository.deleteAllById(deletedIds);
        }

        // Redis 클립 upsert
        String clipKey = String.format(CLIP_STATE_KEY, projectId);
        Map<Object, Object> entries = redisTemplate.opsForHash().entries(clipKey);
        if (!entries.isEmpty()) {
            List<ClipState> redisClips = entries.values().stream()
                    .map(v -> parseClipState((String) v))
                    .toList();

            Map<Integer, Clip> rdbClipMap = clipRepository.findAllByProjectId(projectId).stream()
                    .collect(Collectors.toMap(Clip::getId, c -> c));

            List<Clip> toSave = redisClips.stream()
                    .map(state -> {
                        Clip existing = rdbClipMap.get(state.getClipId());
                        if (existing != null) {
                            existing.update(
                                    trackRepository.getReferenceById(state.getTrackId()),
                                    state.getStart(),
                                    state.getDuration(),
                                    state.getAudioStartMs(),
                                    state.getAudioDurationMs()
                            );
                            return existing;
                        }
                        return Clip.create(
                                state.getClipId(),
                                trackRepository.getReferenceById(state.getTrackId()),
                                audioMetadataRepository.getReferenceById(state.getAudioMetadataId()),
                                state.getColor(),
                                state.getStart(),
                                state.getDuration(),
                                state.getAudioStartMs(),
                                state.getAudioDurationMs()
                        );
                    })
                    .toList();

            clipRepository.saveAll(toSave);
        }

        // deleted set 초기화
        redisTemplate.delete(deletedKey);
    }


    //////////////////////// Redis ////////////////////////

    /*
        Clip Lock 실행/해제 메서드
        Redis 분산 락으로 구현
     */
    public ClipLockResponse lockClip(ClipLockRequest request, Integer userId) {
        // NPE 방지
        request.validate();

        // 프로젝트 존재여부 확인
        projectService.getProjectOrThrow(request.getProjectId());

        // 락을 위한 key
        String lockKey = String.format(CLIP_LOCK_KEY, request.getProjectId(), request.getClipId());

        // 락을 걸어달라는 요청의 경우
        if (request.getIsLocked()) {
            Boolean acquired = redisTemplate.opsForValue().setIfAbsent(lockKey, String.valueOf(userId));
            if (Boolean.FALSE.equals(acquired)) {
                throw new BusinessException(ErrorCode.CLIP_LOCKED);
            }
        }
        // 락을 풀어달라는 요청의 경우
        else {
            String currentLocker = redisTemplate.opsForValue().get(lockKey);
            if (currentLocker != null && !currentLocker.equals(String.valueOf(userId))) {
                throw new BusinessException(ErrorCode.CLIP_LOCKED);
            }
            redisTemplate.delete(lockKey);
        }

        Long sequenceNo = redisTemplate.opsForValue()
                .increment(String.format(CLIP_EVENT_SEQ_KEY, request.getProjectId()));

        try {
            clipEventRepository.save(ClipLockEventDocument.builder()
                    .event("CLIP_LOCK")
                    .projectId(request.getProjectId())
                    .clipId(request.getClipId())
                    .userId(userId)
                    .sequenceNo(sequenceNo)
                    .timestamp(clock.instant())
                    .isLocked(request.getIsLocked())
                    .build());
        } catch (Exception e) {
            log.error("[MongoDB 이벤트 저장 실패]: event=CLIP_LOCK, clipId={}", request.getClipId(), e);
        }

        return ClipLockResponse.builder()
                .clipId(request.getClipId())
                .isLocked(request.getIsLocked())
                .userId(userId)
                .build();
    }

    /*
        오디오를 트랙에 import할 때 클립을 생성하는 메서드
        audioDurationMs와 프로젝트 BPM/박자로 duration(bars)을 계산한다.
     */
    public ClipCreateResponse createClip(ClipCreateRequest request, Integer userId) {
        request.validate();

        Project project = projectService.getProjectOrThrow(request.getProjectId());

        validateTrackInProjectWorkingSet(request.getTrackId(), request.getProjectId());

        AudioMetadata audioMetadata = audioService.createAudioMetadata(
                AudioMetadataCreateRequest.builder()
                        .objectKey(request.getObjectKey())
                        .originalName(request.getOriginalName())
                        .storedName(request.getStoredName())
                        .mimeType(request.getMimeType())
                        .sizeBytes(request.getSizeBytes())
                        .durationMs(request.getDurationMs())
                        .build()
        );

        double durationBars = (audioMetadata.getDurationMs() / 1000.0)
                * (project.getTempo() / 60.0)
                / project.getTimeSigNumerator();

        validateBarLimit(request.getStartBar(), durationBars);

        Integer clipId = redisTemplate.opsForValue()
                .increment(CLIP_ID_SEQ_KEY).intValue();

        ClipState state = ClipState.builder()
                .clipId(clipId)
                .trackId(request.getTrackId())
                .start(request.getStartBar())
                .duration(durationBars)
                .audioMetadataId(audioMetadata.getId())
                .color(request.getColor())
                .audioStartMs(0)
                .audioDurationMs(audioMetadata.getDurationMs())
                .build();

        saveClipStateToRedis(request.getProjectId(), state);

        Long sequenceNo = redisTemplate.opsForValue()
                .increment(String.format(CLIP_EVENT_SEQ_KEY, request.getProjectId()));

        try {
            clipEventRepository.save(ClipCreateEventDocument.builder()
                    .event("CLIP_CREATE")
                    .projectId(request.getProjectId())
                    .clipId(clipId)
                    .userId(userId)
                    .sequenceNo(sequenceNo)
                    .timestamp(clock.instant())
                    .trackId(request.getTrackId())
                    .audioMetadataId(audioMetadata.getId())
                    .startBar(request.getStartBar())
                    .duration(durationBars)
                    .undoable(true)
                    .undone(false)
                    .build());
        } catch (Exception e) {
            log.error("[MongoDB 이벤트 저장 실패]: event=CLIP_CREATE, clipId={}", clipId, e);
        }

        return ClipCreateResponse.builder()
                .clipId(clipId)
                .trackId(request.getTrackId())
                .startBar(request.getStartBar())
                .duration(durationBars)
                .color(request.getColor())
                .audioMetadataId(audioMetadata.getId())
                .audioStartMs(0)
                .audioDurationMs(audioMetadata.getDurationMs())
                .build();
    }

    /*
        클립의 위치를 이동하는 메서드
     */
    public ClipMoveResponse moveClip(ClipMoveRequest request, Integer userId) {
        request.validate();

        projectService.getProjectOrThrow(request.getProjectId());

        validateTrackInProjectWorkingSet(request.getTargetTrackId(), request.getProjectId());

        String lockKey = String.format(CLIP_LOCK_KEY, request.getProjectId(), request.getClipId());
        String currentLocker = redisTemplate.opsForValue().get(lockKey);
        if (!String.valueOf(userId).equals(currentLocker)) {
            throw new BusinessException(ErrorCode.CLIP_LOCKED);
        }

        ClipState state = getOrLoadClipState(request.getProjectId(), request.getClipId());

        validateBarLimit(request.getTargetStartBar(), state.getDuration());

        Integer beforeTrackId = state.getTrackId();
        Double beforeStartBar = state.getStart();

        ClipState updated = ClipState.builder()
                .clipId(state.getClipId())
                .trackId(request.getTargetTrackId())
                .start(request.getTargetStartBar())
                .duration(state.getDuration())
                .audioMetadataId(state.getAudioMetadataId())
                .color(state.getColor())
                .audioStartMs(state.getAudioStartMs())
                .audioDurationMs(state.getAudioDurationMs())
                .build();
        saveClipStateToRedis(request.getProjectId(), updated);

        Long sequenceNo = redisTemplate.opsForValue()
                .increment(String.format(CLIP_EVENT_SEQ_KEY, request.getProjectId()));

        try {
            clipEventRepository.save(ClipMoveEventDocument.builder()
                    .event("CLIP_MOVE")
                    .projectId(request.getProjectId())
                    .clipId(request.getClipId())
                    .userId(userId)
                    .sequenceNo(sequenceNo)
                    .timestamp(clock.instant())
                    .before(ClipMoveEventDocument.ClipPosition.builder()
                            .trackId(beforeTrackId)
                            .startBar(beforeStartBar)
                            .build())
                    .after(ClipMoveEventDocument.ClipPosition.builder()
                            .trackId(request.getTargetTrackId())
                            .startBar(request.getTargetStartBar())
                            .build())
                    .undoable(true)
                    .undone(false)
                    .build());
        } catch (Exception e) {
            log.error("[MongoDB 이벤트 저장 실패]: event=CLIP_MOVE, clipId={}", request.getClipId(), e);
        }

        return ClipMoveResponse.builder()
                .clipId(request.getClipId())
                .before(ClipMoveResponse.ClipPosition.builder()
                        .trackId(beforeTrackId)
                        .startBar(beforeStartBar)
                        .build())
                .after(ClipMoveResponse.ClipPosition.builder()
                        .trackId(request.getTargetTrackId())
                        .startBar(request.getTargetStartBar())
                        .build())
                .build();
    }

    /*
        클립을 리사이징하는 메서드
     */
    public ClipResizeResponse resizeClip(ClipResizeRequest request, Integer userId) {
        request.validate();

        projectService.getProjectOrThrow(request.getProjectId());

        String lockKey = String.format(CLIP_LOCK_KEY, request.getProjectId(), request.getClipId());
        String currentLocker = redisTemplate.opsForValue().get(lockKey);
        if (!String.valueOf(userId).equals(currentLocker)) {
            throw new BusinessException(ErrorCode.CLIP_LOCKED);
        }

        ClipState state = getOrLoadClipState(request.getProjectId(), request.getClipId());

        Double beforeStart = state.getStart();
        Double beforeDuration = state.getDuration();

        validateBarLimit(request.getStartBar(), request.getLength());

        // 같은 트랙 내 다른 클립과 겹침 여부 확인
        String clipHashKey = String.format(CLIP_STATE_KEY, request.getProjectId());
        List<Object> allClipValues = redisTemplate.opsForHash().values(clipHashKey);
        for (Object val : allClipValues) {
            try {
                ClipState other = objectMapper.readValue((String) val, ClipState.class);
                if (!other.getClipId().equals(request.getClipId())
                        && other.getTrackId().equals(state.getTrackId())) {
                    boolean overlaps = request.getStartBar() < other.getStart() + other.getDuration()
                            && other.getStart() < request.getStartBar() + request.getLength();
                    if (overlaps) {
                        throw new BusinessException(ErrorCode.CLIP_OVERLAP);
                    }
                }
            } catch (JsonProcessingException e) {
                throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR);
            }
        }

        double msPerBar = (double) state.getAudioDurationMs() / state.getDuration();
        int newAudioStartMs = (int) Math.round(state.getAudioStartMs() + (request.getStartBar() - state.getStart()) * msPerBar);
        int newAudioDurationMs = (int) Math.round(request.getLength() * msPerBar);

        ClipState updated = ClipState.builder()
                .clipId(state.getClipId())
                .trackId(state.getTrackId())
                .start(request.getStartBar())
                .duration(request.getLength())
                .audioMetadataId(state.getAudioMetadataId())
                .color(state.getColor())
                .audioStartMs(newAudioStartMs)
                .audioDurationMs(newAudioDurationMs)
                .build();
        saveClipStateToRedis(request.getProjectId(), updated);

        Long sequenceNo = redisTemplate.opsForValue()
                .increment(String.format(CLIP_EVENT_SEQ_KEY, request.getProjectId()));

        try {
            clipEventRepository.save(ClipResizeEventDocument.builder()
                    .event("CLIP_RESIZE")
                    .projectId(request.getProjectId())
                    .clipId(request.getClipId())
                    .userId(userId)
                    .sequenceNo(sequenceNo)
                    .timestamp(clock.instant())
                    .before(ClipResizeEventDocument.ClipSize.builder()
                            .startBar(beforeStart)
                            .length(beforeDuration)
                            .build())
                    .after(ClipResizeEventDocument.ClipSize.builder()
                            .startBar(request.getStartBar())
                            .length(request.getLength())
                            .build())
                    .undoable(true)
                    .undone(false)
                    .build());
        } catch (Exception e) {
            log.error("[MongoDB 이벤트 저장 실패]: event=CLIP_RESIZE, clipId={}", request.getClipId(), e);
        }

        return ClipResizeResponse.builder()
                .clipId(request.getClipId())
                .before(ClipResizeResponse.ClipSize.builder()
                        .startBar(beforeStart)
                        .length(beforeDuration)
                        .build())
                .after(ClipResizeResponse.ClipSize.builder()
                        .startBar(request.getStartBar())
                        .length(request.getLength())
                        .build())
                .build();
    }

    /*
        클립을 삭제하는 메서드
     */
    public ClipDeleteResponse deleteClip(ClipDeleteRequest request, Integer userId) {
        request.validate();

        projectService.getProjectOrThrow(request.getProjectId());

        String lockKey = String.format(CLIP_LOCK_KEY, request.getProjectId(), request.getClipId());
        String currentLocker = redisTemplate.opsForValue().get(lockKey);
        if (!String.valueOf(userId).equals(currentLocker)) {
            throw new BusinessException(ErrorCode.CLIP_LOCKED);
        }

        getOrLoadClipState(request.getProjectId(), request.getClipId());

        String stateKey = String.format(CLIP_STATE_KEY, request.getProjectId());
        String deletedKey = String.format(DELETED_CLIPS_KEY, request.getProjectId());
        redisTemplate.opsForHash().delete(stateKey, String.valueOf(request.getClipId()));
        redisTemplate.delete(lockKey);
        redisTemplate.opsForSet().add(deletedKey, String.valueOf(request.getClipId()));

        Long sequenceNo = redisTemplate.opsForValue()
                .increment(String.format(CLIP_EVENT_SEQ_KEY, request.getProjectId()));

        try {
            clipEventRepository.save(ClipDeleteEventDocument.builder()
                    .event("CLIP_DELETE")
                    .projectId(request.getProjectId())
                    .clipId(request.getClipId())
                    .userId(userId)
                    .sequenceNo(sequenceNo)
                    .timestamp(clock.instant())
                    .undoable(true)
                    .undone(false)
                    .build());
        } catch (Exception e) {
            log.error("[MongoDB 이벤트 저장 실패]: event=CLIP_DELETE, clipId={}", request.getClipId(), e);
        }

        return ClipDeleteResponse.builder()
                .clipId(request.getClipId())
                .build();
    }

    /*
        클립을 분할하는 메서드
        splitBar 위치를 기준으로 원본 클립의 duration을 줄이고, 나머지 구간을 새 클립으로 생성한다.
     */
    public ClipSplitResponse splitClip(ClipSplitRequest request, Integer userId) {
        request.validate();

        projectService.getProjectOrThrow(request.getProjectId());

        // 접근 권한 확인
        String lockKey = String.format(CLIP_LOCK_KEY, request.getProjectId(), request.getClipId());
        String currentLocker = redisTemplate.opsForValue().get(lockKey);
        if (!String.valueOf(userId).equals(currentLocker)) {
            throw new BusinessException(ErrorCode.CLIP_LOCKED);
        }

        ClipState original = getOrLoadClipState(request.getProjectId(), request.getClipId());

        Double originalStart = original.getStart();
        Double originalEnd = originalStart + original.getDuration();
        Double splitBar = request.getSplitBar();

        // 클립 영역 밖에서 split 요청 시 (정상적인 경우 실행되지 않지만 방어용으로 추가)
        if (splitBar <= originalStart || splitBar >= originalEnd) {
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
        }

        Integer newClipId = redisTemplate.opsForValue()
                .increment(CLIP_ID_SEQ_KEY).intValue();

        double msPerBar = (double) original.getAudioDurationMs() / original.getDuration();

        // 기존 클립 수정 (split 기준 왼쪽, 락은 기존 클립만 유지)
        Double newOriginalDuration = splitBar - originalStart;
        ClipState updatedOriginal = ClipState.builder()
                .clipId(original.getClipId())
                .trackId(original.getTrackId())
                .start(originalStart)
                .duration(newOriginalDuration)
                .audioMetadataId(original.getAudioMetadataId())
                .color(original.getColor())
                .audioStartMs(original.getAudioStartMs())
                .audioDurationMs((int) Math.round(newOriginalDuration * msPerBar))
                .build();
        saveClipStateToRedis(request.getProjectId(), updatedOriginal);

        // 새로운 클립 생성 (split 기준 오른쪽)
        Double newClipDuration = originalEnd - splitBar;
        ClipState newClip = ClipState.builder()
                .clipId(newClipId)
                .trackId(original.getTrackId())
                .start(splitBar)
                .duration(newClipDuration)
                .audioMetadataId(original.getAudioMetadataId())
                .color(original.getColor())
                .audioStartMs((int) Math.round(original.getAudioStartMs() + (splitBar - originalStart) * msPerBar))
                .audioDurationMs((int) Math.round(newClipDuration * msPerBar))
                .build();
        saveClipStateToRedis(request.getProjectId(), newClip);

        Long sequenceNo = redisTemplate.opsForValue()
                .increment(String.format(CLIP_EVENT_SEQ_KEY, request.getProjectId()));

        // MongoDB에 이벤트 저장
        try {
            clipEventRepository.save(ClipSplitEventDocument.builder()
                    .event("CLIP_SPLIT")
                    .projectId(request.getProjectId())
                    .clipId(request.getClipId())
                    .userId(userId)
                    .sequenceNo(sequenceNo)
                    .timestamp(clock.instant())
                    .splitBar(splitBar)
                    .newClipId(newClipId)
                    .undoable(true)
                    .undone(false)
                    .build());
        } catch (Exception e) {
            log.error("[MongoDB 이벤트 저장 실패]: event=CLIP_SPLIT, clipId={}", request.getClipId(), e);
        }

        return ClipSplitResponse.builder()
                .clipId(request.getClipId())
                .splitBar(splitBar)
                .originalDuration(newOriginalDuration)
                .newClipId(newClipId)
                .newClipDuration(newClipDuration)
                .build();
    }

    /*
        클립을 오려두는 메서드
        타임라인에서 클립을 제거하고 클립보드(Redis)에 저장한다.
        MongoDB 로깅 없음 — 세션 종료 시 자동 Save로 RDB에 반영되므로 이벤트 재생 불필요
     */
    public ClipCutResponse cutClip(ClipCutRequest request, Integer userId) {
        request.validate();

        projectService.getProjectOrThrow(request.getProjectId());

        String lockKey = String.format(CLIP_LOCK_KEY, request.getProjectId(), request.getClipId());
        String currentLocker = redisTemplate.opsForValue().get(lockKey);
        if (!String.valueOf(userId).equals(currentLocker)) {
            throw new BusinessException(ErrorCode.CLIP_LOCKED);
        }

        ClipState state = getOrLoadClipState(request.getProjectId(), request.getClipId());

        String clipboardKey = String.format(CLIP_CLIPBOARD_KEY, request.getProjectId(), userId);
        String stateKey = String.format(CLIP_STATE_KEY, request.getProjectId());
        String deletedKey = String.format(DELETED_CLIPS_KEY, request.getProjectId());
        try {
            String clipboardValue = objectMapper.writeValueAsString(state);
            redisTemplate.execute(new SessionCallback<>() {
                @Override
                public Object execute(RedisOperations operations) {
                    operations.multi();
                    operations.opsForValue().set(clipboardKey, clipboardValue);
                    operations.opsForHash().delete(stateKey, String.valueOf(request.getClipId()));
                    operations.delete(lockKey);
                    operations.opsForSet().add(deletedKey, String.valueOf(request.getClipId()));
                    return operations.exec();
                }
            });
        } catch (JsonProcessingException e) {
            throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR);
        }

        return ClipCutResponse.builder()
                .clipId(request.getClipId())
                .build();
    }

    /*
        클립을 복사하는 메서드
        타임라인에서 클립을 제거하지 않고 클립보드(Redis)에 ClipState를 저장한다.
        락 없이 모든 사용자가 복사할 수 있으며 MongoDB 로깅 없음
     */
    public ClipCopyResponse copyClip(ClipCopyRequest request, Integer userId) {
        request.validate();

        projectService.getProjectOrThrow(request.getProjectId());

        ClipState state = getOrLoadClipState(request.getProjectId(), request.getClipId());

        String clipboardKey = String.format(CLIP_CLIPBOARD_KEY, request.getProjectId(), userId);
        try {
            redisTemplate.opsForValue().set(clipboardKey, objectMapper.writeValueAsString(state));
        } catch (JsonProcessingException e) {
            throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR);
        }

        return ClipCopyResponse.builder()
                .clipId(request.getClipId())
                .build();
    }

    /*
        클립을 붙여넣는 메서드
        클립보드(Redis)에서 ClipState를 읽어 지정 위치에 새 클립을 생성한다.
        붙여넣기 후 클립보드는 유지된다 (반복 paste 가능).
     */
    public ClipPasteResponse pasteClip(ClipPasteRequest request, Integer userId) {
        request.validate();

        projectService.getProjectOrThrow(request.getProjectId());

        validateTrackInProjectWorkingSet(request.getTargetTrackId(), request.getProjectId());

        String clipboardKey = String.format(CLIP_CLIPBOARD_KEY, request.getProjectId(), userId);
        String clipboardJson = redisTemplate.opsForValue().get(clipboardKey);
        if (clipboardJson == null) {
            throw new BusinessException(ErrorCode.CLIP_NOT_FOUND);
        }

        ClipState clipboardState;
        try {
            clipboardState = objectMapper.readValue(clipboardJson, ClipState.class);
        } catch (JsonProcessingException e) {
            throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR);
        }

        validateBarLimit(request.getTargetStartBar(), clipboardState.getDuration());

        Integer newClipId = redisTemplate.opsForValue()
                .increment(CLIP_ID_SEQ_KEY).intValue();

        ClipState newClip = ClipState.builder()
                .clipId(newClipId)
                .trackId(request.getTargetTrackId())
                .start(request.getTargetStartBar())
                .duration(clipboardState.getDuration())
                .audioMetadataId(clipboardState.getAudioMetadataId())
                .color(clipboardState.getColor())
                .audioStartMs(clipboardState.getAudioStartMs())
                .audioDurationMs(clipboardState.getAudioDurationMs())
                .build();
        saveClipStateToRedis(request.getProjectId(), newClip);

        Long sequenceNo = redisTemplate.opsForValue()
                .increment(String.format(CLIP_EVENT_SEQ_KEY, request.getProjectId()));

        try {
            clipEventRepository.save(ClipPasteEventDocument.builder()
                    .event("CLIP_PASTE")
                    .projectId(request.getProjectId())
                    .clipId(newClipId)
                    .userId(userId)
                    .sequenceNo(sequenceNo)
                    .timestamp(clock.instant())
                    .targetTrackId(request.getTargetTrackId())
                    .targetStartBar(request.getTargetStartBar())
                    .undoable(true)
                    .undone(false)
                    .build());
        } catch (Exception e) {
            log.error("[MongoDB 이벤트 저장 실패]: event=CLIP_PASTE, newClipId={}", newClipId, e);
        }

        return ClipPasteResponse.builder()
                .clipId(newClipId)
                .sourceClipId(clipboardState.getClipId())
                .targetTrackId(request.getTargetTrackId())
                .targetStartBar(request.getTargetStartBar())
                .build();
    }

    /*
        클립을 복제하는 메서드
        원본 클립의 바로 뒤(같은 트랙)에 동일한 duration의 새 클립을 생성한다.
        복제 후 새 클립에 락이 이전되고, 원본 클립의 락은 해제된다.
     */
    public ClipDuplicateResponse duplicateClip(ClipDuplicateRequest request, Integer userId) {
        request.validate();

        projectService.getProjectOrThrow(request.getProjectId());

        String lockKey = String.format(CLIP_LOCK_KEY, request.getProjectId(), request.getClipId());
        String currentLocker = redisTemplate.opsForValue().get(lockKey);
        if (!String.valueOf(userId).equals(currentLocker)) {
            throw new BusinessException(ErrorCode.CLIP_LOCKED);
        }

        ClipState original = getOrLoadClipState(request.getProjectId(), request.getClipId());

        Integer targetTrackId = original.getTrackId();
        Double targetStartBar = original.getStart() + original.getDuration();

        validateBarLimit(targetStartBar, original.getDuration());

        String clipHashKey = String.format(CLIP_STATE_KEY, request.getProjectId());
        List<Object> allClipValues = redisTemplate.opsForHash().values(clipHashKey);
        for (Object val : allClipValues) {
            try {
                ClipState other = objectMapper.readValue((String) val, ClipState.class);
                if (!other.getClipId().equals(request.getClipId())
                        && other.getTrackId().equals(targetTrackId)) {
                    boolean overlaps = targetStartBar < other.getStart() + other.getDuration()
                            && other.getStart() < targetStartBar + original.getDuration();
                    if (overlaps) {
                        throw new BusinessException(ErrorCode.CLIP_OVERLAP);
                    }
                }
            } catch (JsonProcessingException e) {
                throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR);
            }
        }

        Integer newClipId = redisTemplate.opsForValue()
                .increment(CLIP_ID_SEQ_KEY).intValue();

        ClipState newClip = ClipState.builder()
                .clipId(newClipId)
                .trackId(targetTrackId)
                .start(targetStartBar)
                .duration(original.getDuration())
                .audioMetadataId(original.getAudioMetadataId())
                .color(original.getColor())
                .audioStartMs(original.getAudioStartMs())
                .audioDurationMs(original.getAudioDurationMs())
                .build();
        saveClipStateToRedis(request.getProjectId(), newClip);

        String newLockKey = String.format(CLIP_LOCK_KEY, request.getProjectId(), newClipId);
        String userIdStr = String.valueOf(userId);
        redisTemplate.execute(new SessionCallback<>() {
            @Override
            public Object execute(RedisOperations operations) {
                operations.multi();
                operations.delete(lockKey);
                operations.opsForValue().set(newLockKey, userIdStr);
                return operations.exec();
            }
        });

        Long sequenceNo = redisTemplate.opsForValue()
                .increment(String.format(CLIP_EVENT_SEQ_KEY, request.getProjectId()));

        try {
            clipEventRepository.save(ClipDuplicateEventDocument.builder()
                    .event("CLIP_DUPLICATE")
                    .projectId(request.getProjectId())
                    .clipId(request.getClipId())
                    .userId(userId)
                    .sequenceNo(sequenceNo)
                    .timestamp(clock.instant())
                    .newClipId(newClipId)
                    .targetTrackId(targetTrackId)
                    .targetStartBar(targetStartBar)
                    .undoable(true)
                    .undone(false)
                    .build());
        } catch (Exception e) {
            log.error("[MongoDB 이벤트 저장 실패]: event=CLIP_DUPLICATE, clipId={}", request.getClipId(), e);
        }

        return ClipDuplicateResponse.builder()
                .clipId(request.getClipId())
                .newClipId(newClipId)
                .targetTrackId(targetTrackId)
                .targetStartBar(targetStartBar)
                .build();
    }

    private ClipState parseClipState(String json) {
        try {
            return objectMapper.readValue(json, ClipState.class);
        } catch (JsonProcessingException e) {
            throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR);
        }
    }

    private ClipState getOrLoadClipState(Integer projectId, Integer clipId) {
        String key = String.format(CLIP_STATE_KEY, projectId);
        String json = (String) redisTemplate.opsForHash().get(key, String.valueOf(clipId));
        if (json != null) {
            try {
                return objectMapper.readValue(json, ClipState.class);
            } catch (JsonProcessingException e) {
                throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR);
            }
        }
        Clip clip = clipRepository.findById(clipId)
                .orElseThrow(() -> new BusinessException(ErrorCode.CLIP_NOT_FOUND));
        ClipState state = ClipState.builder()
                .clipId(clip.getId())
                .trackId(clip.getTrack().getId())
                .start(clip.getStart())
                .duration(clip.getDuration())
                .audioMetadataId(clip.getAudioMetadata().getId())
                .color(clip.getColor())
                .audioStartMs(clip.getAudioStartMs())
                .audioDurationMs(clip.getAudioDurationMs())
                .build();
        saveClipStateToRedis(projectId, state);
        return state;
    }

    private void saveClipStateToRedis(Integer projectId, ClipState state) {
        try {
            String key = String.format(CLIP_STATE_KEY, projectId);
            String value = objectMapper.writeValueAsString(state);
            redisTemplate.opsForHash().put(key, String.valueOf(state.getClipId()), value);
        } catch (JsonProcessingException e) {
            throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR);
        }
    }

    // Mysql에서 삭제 예정인 clip 삭제하는 메서드
    public void deleteRemovedClipsFromMysql(Integer projectId) {
        String deletedKey = String.format(DELETED_CLIPS_KEY, projectId);
        Set<String> deletedIdStrs = redisTemplate.opsForSet().members(deletedKey);
        if (deletedIdStrs == null || deletedIdStrs.isEmpty()) {
            return;
        }
        List<Integer> deletedIds = deletedIdStrs.stream()
                .map(Integer::parseInt)
                .toList();
        clipRepository.deleteAllById(deletedIds);
    }

    // Redis의 deleted_clips 키 삭제 (DB 커밋 성공 후)
    public void clearDeletedClipKeys(Integer projectId) {
        redisTemplate.delete(String.format(DELETED_CLIPS_KEY, projectId));
    }

    public void upsertClipsFromRedis(Integer projectId) {
        String clipKey = String.format(CLIP_STATE_KEY, projectId);
        Map<Object, Object> entries = redisTemplate.opsForHash().entries(clipKey);
        if (entries.isEmpty()) {
            return;
        }

        List<ClipState> redisClips = entries.values().stream()
                .map(v -> parseClipState((String) v))
                .toList();

        Map<Integer, Clip> rdbClipMap = clipRepository.findAllByProjectId(projectId).stream()
                .collect(Collectors.toMap(Clip::getId, c -> c));

        List<Clip> toSave = redisClips.stream()
                .map(state -> {
                    Clip existing = rdbClipMap.get(state.getClipId());
                    if (existing != null) {
                        existing.update(
                                trackRepository.getReferenceById(state.getTrackId()),
                                state.getStart(),
                                state.getDuration(),
                                state.getAudioStartMs(),
                                state.getAudioDurationMs()
                        );
                        return existing;
                    }
                    return Clip.create(
                            state.getClipId(),
                            trackRepository.getReferenceById(state.getTrackId()),
                            audioMetadataRepository.getReferenceById(state.getAudioMetadataId()),
                            state.getColor(),
                            state.getStart(),
                            state.getDuration(),
                            state.getAudioStartMs(),
                            state.getAudioDurationMs()
                    );
                })
                .toList();

        clipRepository.saveAll(toSave);
    }

    public void deleteClipStatesByTrack(Integer projectId, Integer trackId) {
        String clipHashKey = String.format(CLIP_STATE_KEY, projectId);
        String deletedSetKey = String.format(DELETED_CLIPS_KEY, projectId);

        Map<Object, Object> entries = redisTemplate.opsForHash().entries(clipHashKey);
        if (entries.isEmpty()) return;

        List<Object> keysToDelete = new ArrayList<>();
        List<String> idsToAdd = new ArrayList<>();

        for (Map.Entry<Object, Object> entry : entries.entrySet()) {
            ClipState state = parseClipState((String) entry.getValue());
            if (state.getTrackId().equals(trackId)) {
                keysToDelete.add(entry.getKey());
                idsToAdd.add(String.valueOf(state.getClipId()));
            }
        }

        if (!keysToDelete.isEmpty()) {
            redisTemplate.opsForHash().delete(clipHashKey, keysToDelete.toArray());
            redisTemplate.opsForSet().add(deletedSetKey, idsToAdd.toArray(new String[0]));
        }
    }

    public void deleteClipsByTrackFromRdb(Integer trackId) {
        try {
            clipRepository.deleteAllByTrackId(trackId);
        } catch (Exception e) {
            log.error("[RDB 클립 삭제 실패]: trackId={}", trackId, e);
        }
    }

    private void validateTrackInProject(Integer trackId, Integer projectId) {
        trackRepository.findByIdAndProject_Id(trackId, projectId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TRACK_NOT_FOUND));
    }

    private void validateTrackInProjectWorkingSet(Integer trackId, Integer projectId) {
        String trackKey = String.format("project:%d:tracks", projectId);
        String deletedKey = String.format("project:%d:deleted_tracks", projectId);

        Object redisTrack = redisTemplate.opsForHash().get(trackKey, String.valueOf(trackId));
        if (redisTrack != null) {
            return;
        }

        Boolean isDeleted = redisTemplate.opsForSet().isMember(deletedKey, String.valueOf(trackId));
        if (Boolean.TRUE.equals(isDeleted)) {
            throw new BusinessException(ErrorCode.TRACK_NOT_FOUND);
        }

        trackRepository.findByIdAndProject_Id(trackId, projectId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TRACK_NOT_FOUND));
    }

    private void validateBarLimit(double startBar, double duration) {
        if (startBar + duration > MAX_BAR_COUNT) {
            throw new BusinessException(ErrorCode.CLIP_BAR_LIMIT_EXCEEDED);
        }
    }

    private Clip copyClip(Clip clip) {
        return Clip.create(
                clip.getId(),
                clip.getTrack(),
                clip.getAudioMetadata(),
                clip.getColor(),
                clip.getStart(),
                clip.getDuration(),
                clip.getAudioStartMs(),
                clip.getAudioDurationMs()
        );
    }
}
