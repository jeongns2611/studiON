package com.salmon.studion.domain.eq.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.ai.dto.request.ProjectEqBandRequest;
import com.salmon.studion.domain.ai.dto.request.ProjectTrackEqRequest;
import com.salmon.studion.domain.eq.dto.TrackEqCurrentState;
import com.salmon.studion.domain.eq.dto.TrackEqDraftState;
import com.salmon.studion.domain.eq.dto.request.TrackEqCommitRequest;
import com.salmon.studion.domain.eq.dto.request.TrackEqDraftSaveRequest;
import com.salmon.studion.domain.eq.dto.request.TrackEqLockRequest;
import com.salmon.studion.domain.eq.dto.request.TrackEqResetRequest;
import com.salmon.studion.domain.eq.dto.response.TrackEqListResponse;
import com.salmon.studion.domain.eq.dto.response.TrackEqLockResponse;
import com.salmon.studion.domain.eq.entity.TrackEq;
import com.salmon.studion.domain.eq.entity.TrackEqBand;
import com.salmon.studion.domain.eq.repository.TrackEqBandRepository;
import com.salmon.studion.domain.eq.repository.TrackEqRepository;
import com.salmon.studion.domain.eq.support.TrackEqRedisKeys;
import com.salmon.studion.domain.project.service.ProjectMemberService;
import com.salmon.studion.domain.project.service.ProjectService;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class TrackEqService {

    private final TrackEqRepository trackEqRepository;
    private final TrackEqBandRepository trackEqBandRepository;
    private final ProjectService projectService;
    private final ProjectMemberService projectMemberService;
    private final RedisTemplate<String, String> redisTemplate;
    private final TrackEqBandService trackEqBandService;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    public TrackEqListResponse getProjectTrackEqList(Integer projectId, Integer userId) {
        projectService.getProjectOrThrow(projectId);
        projectMemberService.validateProjectMember(projectId, userId);

        Set<Integer> deletedTrackIds = getDeletedTrackIds(projectId);
        List<TrackEq> trackEqs = trackEqRepository.findByProjectId(projectId).stream()
                .filter(trackEq -> !deletedTrackIds.contains(trackEq.getTrackId()))
                .toList();

        return TrackEqListResponse.builder()
                .trackEqs(trackEqs.stream()
                        .map(trackEq -> new TrackEqListResponse.TrackEqSummary(
                                trackEq.getId(),
                                trackEq.getTrackId(),
                                trackEq.getProjectId()
                        ))
                        .toList())
                .build();
    }

    public TrackEq getTrackEqOrThrow(Integer trackEqId) {
        return trackEqRepository.findById(trackEqId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TRACK_EQ_NOT_FOUND));
    }
    
    @Transactional
    public TrackEqLockResponse lockTrackEq(TrackEqLockRequest request, Integer userId) {
        request.validate();

        TrackEq trackEq = getAuthorizedTrackEq(request.getProjectId(), request.getTrackEqId(), userId);
        String lockKey = TrackEqRedisKeys.lockKey(request.getProjectId(), request.getTrackEqId());

        if (request.getIsLocked()) {
            Boolean acquired = redisTemplate.opsForValue().setIfAbsent(
                    lockKey,
                    String.valueOf(userId),
                    TrackEqRedisKeys.LOCK_TTL_SECONDS,
                    TimeUnit.SECONDS
            );
            if (Boolean.FALSE.equals(acquired)) {
                String currentLocker = redisTemplate.opsForValue().get(lockKey);
                if (!String.valueOf(userId).equals(currentLocker)) {
                    throw new BusinessException(ErrorCode.TRACK_EQ_LOCKED);
                }
                refreshLockTtl(lockKey);
            }
        } else {
            String currentLocker = redisTemplate.opsForValue().get(lockKey);
            if (currentLocker != null && !currentLocker.equals(String.valueOf(userId))) {
                throw new BusinessException(ErrorCode.TRACK_EQ_LOCKED);
            }
            redisTemplate.delete(lockKey);
        }

        return TrackEqLockResponse.builder()
                .trackEqId(trackEq.getId())
                .isLocked(request.getIsLocked())
                .userId(userId)
                .build();
    }

    public TrackEqDraftState saveDraft(TrackEqDraftSaveRequest request, Integer userId) {
        request.validate();

        TrackEq trackEq = getAuthorizedTrackEq(request.getProjectId(), request.getTrackEqId(), userId);
        validateBands(request.getBands());

        validateOwnedLockAndRefreshTtl(trackEq.getProjectId(), trackEq.getId(), userId);
        TrackEqDraftState currentDraft = getDraftState(trackEq.getProjectId(), trackEq.getId());
        List<TrackEqDraftState.DraftBand> nextBands;
        if (isAiBandMergeRequest(request.getBands())) {
            List<TrackEqDraftState.DraftBand> baseBands = currentDraft != null
                    ? currentDraft.getBands()
                    : getOrHydrateCurrentState(trackEq.getProjectId(), trackEq.getTrackId()).getBands().stream()
                    .map(this::toDraftBand)
                    .toList();
            nextBands = mergeAiDraftBands(
                    baseBands,
                    request.getBands().stream().map(this::toDraftBand).toList()
            );
        } else {
            nextBands = request.getBands().stream()
                    .map(this::toDraftBand)
                    .toList();
        }
        validateDraftBands(nextBands);
        TrackEqDraftState nextDraft = TrackEqDraftState.builder()
                .projectId(trackEq.getProjectId())
                .trackEqId(trackEq.getId())
                .updatedBy(userId)
                .updatedAt(clock.instant())
                .version(nextVersion(currentDraft))
                .bands(nextBands)
                .build();

        saveDraftState(nextDraft);
        saveCurrentState(buildDraftCurrentState(trackEq, nextDraft));
        return nextDraft;
    }

    public TrackEqDraftState resetDraft(TrackEqResetRequest request, Integer userId) {
        request.validate();

        TrackEq trackEq = getAuthorizedTrackEq(request.getProjectId(), request.getTrackEqId(), userId);
        validateOwnedLockAndRefreshTtl(trackEq.getProjectId(), trackEq.getId(), userId);
        TrackEqDraftState currentDraft = getDraftState(trackEq.getProjectId(), trackEq.getId());

        TrackEqDraftState resetDraft = TrackEqDraftState.builder()
                .projectId(trackEq.getProjectId())
                .trackEqId(trackEq.getId())
                .updatedBy(userId)
                .updatedAt(clock.instant())
                .version(nextVersion(currentDraft))
                .bands(List.of())
                .build();

        saveDraftState(resetDraft);
        saveCurrentState(buildDraftCurrentState(trackEq, resetDraft));
        return resetDraft;
    }

    @Transactional
    public TrackEqDraftState commitDraft(TrackEqCommitRequest request, Integer userId) {
        request.validate();

        TrackEq trackEq = getAuthorizedTrackEq(request.getProjectId(), request.getTrackEqId(), userId);
        String lockKey = validateOwnedLockAndRefreshTtl(trackEq.getProjectId(), trackEq.getId(), userId);
        TrackEqDraftState draftState = getDraftState(trackEq.getProjectId(), trackEq.getId());

        if (draftState == null) {
            throw new BusinessException(ErrorCode.INVALID_REQUEST, "저장할 EQ draft가 없습니다.");
        }

        validateDraftBands(draftState.getBands());
        trackEqBandService.replaceTrackEqBandsFromDraft(trackEq.getId(), userId, draftState.getBands());
        saveCurrentState(buildCommittedCurrentState(trackEq, draftState.getBands()));

        redisTemplate.delete(TrackEqRedisKeys.draftKey(trackEq.getProjectId(), trackEq.getId()));
        redisTemplate.delete(lockKey);

        return draftState;
    }
    
    public void createIfAbsent(Integer trackId, Integer projectId) {
        if (isTrackEqDeleted(projectId, trackId)) {
            return;
        }
        if (trackEqRepository.existsByTrackId(trackId)) {
            return;
        }

        TrackEq trackEq = TrackEq.create(trackId, projectId);
        TrackEq persisted = trackEqRepository.save(trackEq);
        saveCurrentState(buildCommittedCurrentState(persisted, List.of()));
    }

    @Transactional
    public void deleteByTrackIdIfExists(Integer trackId) {
        trackEqRepository.findByTrackId(trackId).ifPresent(this::markDeletedTrackEq);
    }


    @Transactional
    public void synchronizeWithTrackIds(Integer projectId, List<Integer> activeTrackIds) {
        List<TrackEq> currentTrackEqs = trackEqRepository.findByProjectId(projectId);
        Set<Integer> deletedTrackIds = getDeletedTrackIds(projectId);
        Set<Integer> activeTrackIdSet = new HashSet<>(activeTrackIds);

        List<TrackEq> toDelete = currentTrackEqs.stream()
                .filter(trackEq -> deletedTrackIds.contains(trackEq.getTrackId()) || !activeTrackIdSet.contains(trackEq.getTrackId()))
                .toList();

        if (!toDelete.isEmpty()) {
            List<Integer> deleteTrackEqIds = toDelete.stream()
                    .map(TrackEq::getId)
                    .toList();
            trackEqBandRepository.deleteAllByTrackEq_IdIn(deleteTrackEqIds);
            toDelete.forEach(this::clearWorkingSet);
            trackEqRepository.deleteAllByIdInBatch(deleteTrackEqIds);
        }

        Set<Integer> persistedTrackIds = currentTrackEqs.stream()
                .filter(trackEq -> !deletedTrackIds.contains(trackEq.getTrackId()) && activeTrackIdSet.contains(trackEq.getTrackId()))
                .map(TrackEq::getTrackId)
                .collect(Collectors.toSet());

        List<TrackEq> toCreate = activeTrackIds.stream()
                .filter(trackId -> !deletedTrackIds.contains(trackId))
                .filter(trackId -> !persistedTrackIds.contains(trackId))
                .map(trackId -> TrackEq.create(trackId, projectId))
                .toList();

        if (!toCreate.isEmpty()) {
            List<TrackEq> created = trackEqRepository.saveAll(toCreate);
            created.forEach(trackEq -> saveCurrentState(buildCommittedCurrentState(trackEq, List.of())));
        }
        clearDeletedTrackIds(projectId);
    }

    @Transactional
    public List<ProjectTrackEqRequest> getCurrentTrackEqPayloads(Integer projectId, List<Integer> trackIds) {
        if (trackIds == null || trackIds.isEmpty()) {
            return List.of();
        }

        List<ProjectTrackEqRequest> results = new ArrayList<>();
        for (Integer trackId : trackIds) {
            if (trackId == null) {
                continue;
            }
            if (isTrackEqDeleted(projectId, trackId)) {
                continue;
            }
            TrackEqCurrentState currentState = getOrHydrateCurrentState(projectId, trackId);
            if (currentState == null) {
                continue;
            }
            results.add(ProjectTrackEqRequest.create(
                    trackId,
                    currentState.getBands().stream()
                            .map(band -> ProjectEqBandRequest.create(
                                    band.getBandOrder(),
                                    band.getEqType(),
                                    band.getFrequencyHz(),
                                    band.getQ(),
                                    band.getGainDeltaDb()
                            ))
                            .toList()
            ));
        }
        return results;
    }

    private void validateBands(List<com.salmon.studion.domain.eq.dto.request.BandRequest> bands) {
        if (bands.size() > 5) {
            throw new BusinessException(ErrorCode.INVALID_INPUT_VALUE, "EQ 밴드는 최대 5개까지 저장할 수 있습니다.");
        }

        Set<Integer> bandOrders = new HashSet<>();
        for (com.salmon.studion.domain.eq.dto.request.BandRequest band : bands) {
            if (!bandOrders.add(band.getBandOrder())) {
                throw new BusinessException(ErrorCode.INVALID_INPUT_VALUE, "EQ bandOrder는 중복될 수 없습니다.");
            }
        }
    }

    private void validateDraftBands(List<TrackEqDraftState.DraftBand> bands) {
        if (bands.size() > 5) {
            throw new BusinessException(ErrorCode.INVALID_INPUT_VALUE, "EQ 밴드는 최대 5개까지 저장할 수 있습니다.");
        }

        Set<Integer> bandOrders = new HashSet<>();
        for (TrackEqDraftState.DraftBand band : bands) {
            if (!bandOrders.add(band.getBandOrder())) {
                throw new BusinessException(ErrorCode.INVALID_INPUT_VALUE, "EQ bandOrder는 중복될 수 없습니다.");
            }
        }
    }

    private String validateOwnedLockAndRefreshTtl(Integer projectId, Integer trackEqId, Integer userId) {
        String lockKey = TrackEqRedisKeys.lockKey(projectId, trackEqId);
        String currentLocker = redisTemplate.opsForValue().get(lockKey);

        if (!String.valueOf(userId).equals(currentLocker)) {
            throw new BusinessException(ErrorCode.TRACK_EQ_LOCKED);
        }

        refreshLockTtl(lockKey);
        return lockKey;
    }

    private void refreshLockTtl(String lockKey) {
        redisTemplate.expire(lockKey, TrackEqRedisKeys.LOCK_TTL_SECONDS, TimeUnit.SECONDS);
    }

    private TrackEqDraftState getDraftState(Integer projectId, Integer trackEqId) {
        String draftKey = TrackEqRedisKeys.draftKey(projectId, trackEqId);
        String value = redisTemplate.opsForValue().get(draftKey);
        if (value == null || value.isBlank()) {
            return null;
        }

        try {
            return objectMapper.readValue(value, TrackEqDraftState.class);
        } catch (JsonProcessingException e) {
            throw new BusinessException(ErrorCode.FAIL, "EQ draft 역직렬화에 실패했습니다.");
        }
    }

    private void saveDraftState(TrackEqDraftState draftState) {
        try {
            redisTemplate.opsForValue().set(
                    TrackEqRedisKeys.draftKey(draftState.getProjectId(), draftState.getTrackEqId()),
                    objectMapper.writeValueAsString(draftState),
                    TrackEqRedisKeys.DRAFT_TTL_SECONDS,
                    TimeUnit.SECONDS
            );
        } catch (JsonProcessingException e) {
            throw new BusinessException(ErrorCode.FAIL, "EQ draft 직렬화에 실패했습니다.");
        }
    }

    private TrackEqCurrentState getOrHydrateCurrentState(Integer projectId, Integer trackId) {
        if (isTrackEqDeleted(projectId, trackId)) {
            redisTemplate.delete(TrackEqRedisKeys.currentKey(projectId, trackId));
            return null;
        }

        String currentKey = TrackEqRedisKeys.currentKey(projectId, trackId);
        String cached = redisTemplate.opsForValue().get(currentKey);
        if (cached != null && !cached.isBlank()) {
            return readCurrentState(cached);
        }

        return hydrateCurrentState(projectId, trackId);
    }

    private TrackEqCurrentState hydrateCurrentState(Integer projectId, Integer trackId) {
        if (isTrackEqDeleted(projectId, trackId)) {
            return null;
        }

        TrackEq trackEq = trackEqRepository.findByTrackId(trackId)
                .filter(item -> item.getProjectId().equals(projectId))
                .orElse(null);

        if (trackEq == null) {
            TrackEqCurrentState emptyState = TrackEqCurrentState.builder()
                    .projectId(projectId)
                    .trackId(trackId)
                    .trackEqId(null)
                    .updatedAt(clock.instant())
                    .source("COMMITTED")
                    .bands(List.of())
                    .build();
            saveCurrentState(emptyState);
            return emptyState;
        }

        List<TrackEqBand> committedBands = trackEqBandRepository.findByTrackEq_IdOrderByBandOrderAsc(trackEq.getId());
        TrackEqCurrentState hydrated = buildCommittedCurrentStateFromBands(
                trackEq,
                committedBands.stream().map(this::toCurrentBand).toList()
        );
        saveCurrentState(hydrated);
        return hydrated;
    }

    private TrackEqCurrentState readCurrentState(String value) {
        try {
            return objectMapper.readValue(value, TrackEqCurrentState.class);
        } catch (JsonProcessingException e) {
            throw new BusinessException(ErrorCode.FAIL, "EQ current projection 역직렬화에 실패했습니다.");
        }
    }

    private void saveCurrentState(TrackEqCurrentState currentState) {
        try {
            redisTemplate.opsForValue().set(
                    TrackEqRedisKeys.currentKey(currentState.getProjectId(), currentState.getTrackId()),
                    objectMapper.writeValueAsString(currentState)
            );
        } catch (JsonProcessingException e) {
            throw new BusinessException(ErrorCode.FAIL, "EQ current projection 직렬화에 실패했습니다.");
        }
    }

    private TrackEqCurrentState buildDraftCurrentState(TrackEq trackEq, TrackEqDraftState draftState) {
        return TrackEqCurrentState.builder()
                .projectId(trackEq.getProjectId())
                .trackId(trackEq.getTrackId())
                .trackEqId(trackEq.getId())
                .updatedAt(draftState.getUpdatedAt() != null ? draftState.getUpdatedAt() : clock.instant())
                .source("DRAFT")
                .bands(draftState.getBands().stream()
                        .sorted(Comparator.comparing(TrackEqDraftState.DraftBand::getBandOrder))
                        .map(band -> TrackEqCurrentState.CurrentBand.builder()
                                .bandOrder(band.getBandOrder())
                                .eqType(band.getEqType())
                                .frequencyHz(band.getFrequencyHz())
                                .q(band.getQ())
                                .gainDeltaDb(band.getGainDeltaDb())
                                .sourceType(band.getSourceType())
                                .jobId(band.getJobId())
                                .suggestionActionId(band.getSuggestionActionId())
                                .appliedSuggestionId(band.getAppliedSuggestionId())
                                .build())
                        .toList())
                .build();
    }

    private TrackEqCurrentState buildCommittedCurrentState(
            TrackEq trackEq,
            List<TrackEqDraftState.DraftBand> draftBands
    ) {
        return TrackEqCurrentState.builder()
                .projectId(trackEq.getProjectId())
                .trackId(trackEq.getTrackId())
                .trackEqId(trackEq.getId())
                .updatedAt(clock.instant())
                .source("COMMITTED")
                .bands(draftBands.stream()
                        .sorted(Comparator.comparing(TrackEqDraftState.DraftBand::getBandOrder))
                        .map(band -> TrackEqCurrentState.CurrentBand.builder()
                                .bandOrder(band.getBandOrder())
                                .eqType(band.getEqType())
                                .frequencyHz(band.getFrequencyHz())
                                .q(band.getQ())
                                .gainDeltaDb(band.getGainDeltaDb())
                                .sourceType(band.getSourceType())
                                .jobId(band.getJobId())
                                .suggestionActionId(band.getSuggestionActionId())
                                .appliedSuggestionId(band.getAppliedSuggestionId())
                                .build())
                        .toList())
                .build();
    }

    private TrackEqCurrentState buildCommittedCurrentStateFromBands(
            TrackEq trackEq,
            List<TrackEqCurrentState.CurrentBand> bands
    ) {
        return TrackEqCurrentState.builder()
                .projectId(trackEq.getProjectId())
                .trackId(trackEq.getTrackId())
                .trackEqId(trackEq.getId())
                .updatedAt(clock.instant())
                .source("COMMITTED")
                .bands(bands.stream()
                        .sorted(Comparator.comparing(TrackEqCurrentState.CurrentBand::getBandOrder))
                        .toList())
                .build();
    }

    private TrackEqCurrentState.CurrentBand toCurrentBand(TrackEqBand band) {
        return TrackEqCurrentState.CurrentBand.builder()
                .bandOrder(band.getBandOrder())
                .eqType(toEqType(band.getEqTypeCode()))
                .frequencyHz(band.getFrequencyHz())
                .q(band.getQ())
                .gainDeltaDb(band.getGainDeltaDb())
                .sourceType(trackEqBandService.toSourceTypeForProjection(band.getSourceTypeCode()))
                .jobId(band.getJobId())
                .suggestionActionId(band.getSuggestionActionId())
                .appliedSuggestionId(band.getAppliedSuggestionId())
                .build();
    }

    private TrackEqDraftState.DraftBand toDraftBand(com.salmon.studion.domain.eq.dto.request.BandRequest band) {
        return TrackEqDraftState.DraftBand.builder()
                .bandOrder(band.getBandOrder())
                .eqType(band.getEqType())
                .frequencyHz(band.getFrequencyHz())
                .q(band.getQ())
                .gainDeltaDb(band.getGainDeltaDb())
                .sourceType(band.getSourceType())
                .jobId(band.getJobId())
                .suggestionActionId(band.getSuggestionActionId())
                .appliedSuggestionId(band.getAppliedSuggestionId())
                .build();
    }

    private TrackEqDraftState.DraftBand toDraftBand(TrackEqCurrentState.CurrentBand band) {
        return TrackEqDraftState.DraftBand.builder()
                .bandOrder(band.getBandOrder())
                .eqType(band.getEqType())
                .frequencyHz(band.getFrequencyHz())
                .q(band.getQ())
                .gainDeltaDb(band.getGainDeltaDb())
                .sourceType(band.getSourceType())
                .jobId(band.getJobId())
                .suggestionActionId(band.getSuggestionActionId())
                .appliedSuggestionId(band.getAppliedSuggestionId())
                .build();
    }

    private boolean isAiBandMergeRequest(List<com.salmon.studion.domain.eq.dto.request.BandRequest> bands) {
        return !bands.isEmpty() && bands.stream().allMatch(band -> isAiSourceType(band.getSourceType()));
    }

    private boolean isAiSourceType(String sourceType) {
        return "AI_CONFIRM".equals(sourceType) || "AI_APPLIED".equals(sourceType);
    }

    private List<TrackEqDraftState.DraftBand> mergeAiDraftBands(
            List<TrackEqDraftState.DraftBand> baseBands,
            List<TrackEqDraftState.DraftBand> incomingAiBands
    ) {
        List<TrackEqDraftState.DraftBand> merged = new ArrayList<>(baseBands);
        Set<Integer> usedOrders = merged.stream()
                .map(TrackEqDraftState.DraftBand::getBandOrder)
                .filter(Objects::nonNull)
                .collect(Collectors.toCollection(HashSet::new));

        for (TrackEqDraftState.DraftBand incomingBand : incomingAiBands) {
            int matchIndex = findMatchingAiBandIndex(merged, incomingBand);
            Integer assignedOrder = incomingBand.getBandOrder();
            if (matchIndex >= 0) {
                TrackEqDraftState.DraftBand existingBand = merged.remove(matchIndex);
                assignedOrder = existingBand.getBandOrder();
            } else if (assignedOrder == null || usedOrders.contains(assignedOrder)) {
                assignedOrder = nextAvailableBandOrder(usedOrders);
            }
            TrackEqDraftState.DraftBand normalizedBand = TrackEqDraftState.DraftBand.builder()
                    .bandOrder(assignedOrder)
                    .eqType(incomingBand.getEqType())
                    .frequencyHz(incomingBand.getFrequencyHz())
                    .q(incomingBand.getQ())
                    .gainDeltaDb(incomingBand.getGainDeltaDb())
                    .sourceType("AI_CONFIRM")
                    .jobId(incomingBand.getJobId())
                    .suggestionActionId(incomingBand.getSuggestionActionId())
                    .appliedSuggestionId(incomingBand.getAppliedSuggestionId())
                    .build();
            merged.add(normalizedBand);
            usedOrders.add(assignedOrder);
        }

        return merged.stream()
                .sorted(Comparator.comparing(TrackEqDraftState.DraftBand::getBandOrder))
                .toList();
    }

    private int findMatchingAiBandIndex(
            List<TrackEqDraftState.DraftBand> existingBands,
            TrackEqDraftState.DraftBand incomingBand
    ) {
        for (int index = 0; index < existingBands.size(); index++) {
            TrackEqDraftState.DraftBand existingBand = existingBands.get(index);
            if (!isAiSourceType(existingBand.getSourceType())) {
                continue;
            }
            if (
                    incomingBand.getAppliedSuggestionId() != null
                            && Objects.equals(existingBand.getAppliedSuggestionId(), incomingBand.getAppliedSuggestionId())
            ) {
                return index;
            }
            if (
                    incomingBand.getSuggestionActionId() != null
                            && Objects.equals(existingBand.getSuggestionActionId(), incomingBand.getSuggestionActionId())
            ) {
                return index;
            }
            if (
                    incomingBand.getJobId() != null
                            && Objects.equals(existingBand.getJobId(), incomingBand.getJobId())
                            && Objects.equals(existingBand.getBandOrder(), incomingBand.getBandOrder())
            ) {
                return index;
            }
        }
        return -1;
    }

    private int nextAvailableBandOrder(Set<Integer> usedOrders) {
        int nextBandOrder = 1;
        while (usedOrders.contains(nextBandOrder)) {
            nextBandOrder += 1;
        }
        return nextBandOrder;
    }

    private String toEqType(Integer eqTypeCode) {
        if (eqTypeCode == null) {
            return null;
        }

        return switch (eqTypeCode) {
            case 1 -> "BELL";
            case 2 -> "LOW_SHELF";
            case 3 -> "HIGH_SHELF";
            default -> throw new BusinessException(ErrorCode.FAIL, "알 수 없는 EQ type code 입니다. code=" + eqTypeCode);
        };
    }

    private long nextVersion(TrackEqDraftState currentDraft) {
        if (currentDraft == null || currentDraft.getVersion() == null) {
            return 1L;
        }
        return currentDraft.getVersion() + 1L;
    }

    private TrackEq getAuthorizedTrackEq(Integer projectId, Integer trackEqId, Integer userId) {
        projectService.getProjectOrThrow(projectId);

        TrackEq trackEq = getTrackEqOrThrow(trackEqId);
        if (!trackEq.getProjectId().equals(projectId)) {
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
        }
        if (isTrackEqDeleted(projectId, trackEq.getTrackId())) {
            throw new BusinessException(ErrorCode.TRACK_EQ_NOT_FOUND);
        }

        projectMemberService.validateProjectMember(projectId, userId);
        return trackEq;
    }

    private void markDeletedTrackEq(TrackEq trackEq) {
        clearWorkingSet(trackEq);
        redisTemplate.opsForSet().add(
                TrackEqRedisKeys.deletedTrackEqsKey(trackEq.getProjectId()),
                String.valueOf(trackEq.getTrackId())
        );
    }

    private void clearWorkingSet(TrackEq trackEq) {
        redisTemplate.delete(TrackEqRedisKeys.lockKey(trackEq.getProjectId(), trackEq.getId()));
        redisTemplate.delete(TrackEqRedisKeys.draftKey(trackEq.getProjectId(), trackEq.getId()));
        redisTemplate.delete(TrackEqRedisKeys.currentKey(trackEq.getProjectId(), trackEq.getTrackId()));
    }

    private boolean isTrackEqDeleted(Integer projectId, Integer trackId) {
        return Boolean.TRUE.equals(redisTemplate.opsForSet().isMember(
                TrackEqRedisKeys.deletedTrackEqsKey(projectId),
                String.valueOf(trackId)
        ));
    }

    private Set<Integer> getDeletedTrackIds(Integer projectId) {
        Set<String> deletedTrackIdValues = redisTemplate.opsForSet().members(TrackEqRedisKeys.deletedTrackEqsKey(projectId));
        if (deletedTrackIdValues == null || deletedTrackIdValues.isEmpty()) {
            return Set.of();
        }
        return deletedTrackIdValues.stream()
                .map(Integer::parseInt)
                .collect(Collectors.toSet());
    }

    private void clearDeletedTrackIds(Integer projectId) {
        redisTemplate.delete(TrackEqRedisKeys.deletedTrackEqsKey(projectId));
    }

}
